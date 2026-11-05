#!/usr/bin/env python3
"""
Nikkei VI estimate from the OSE theoretical-price file (compute_vi.py)
=====================================================================
The official Nikkei Stock Average Volatility Index (日経平均VI) is not
available from any free source this pipeline can reach (stooq and Yahoo do not
carry it; the Nikkei index site blocks scripts). It is defined with the same
method as the CBOE VIX: the 30-day variance implied by the out-of-the-money
Nikkei 225 options of the near and the next monthly expiry. This script applies
that method to the per-strike theoretical prices in oseYYYYMMDDtp.csv, which
JPX publishes every day and fetch_jpx.py already downloads.

Differences from the official index (so the value is an estimate):
  - theoretical (closing) prices instead of live bid/ask mid quotes
  - interest rate taken as 0 (a 1% rate moves the result by ~0.01pt)
  - SQ is taken as the second Friday 09:00 JST (no holiday shift)

Steps (VIX white paper):
  T  = minutes from the day-session close (15:45 JST) to SQ (09:00) / 525600
  F  = K + (C - P) at the strike where |C - P| is smallest
  K0 = highest strike <= F
  sigma^2 = 2/T * sum(dK / K^2 * Q(K)) - 1/T * (F/K0 - 1)^2
     Q = put below K0, call above K0, their average at K0; walking outward
     from K0, stop after two consecutive strikes priced 0
  VI = 100 * sqrt(30-day interpolation of T*sigma^2 between the two expiries,
                  scaled to a year)
Expiries with under 2 days left are skipped (the near month rolls to the next).

Usage:
    python scripts/compute_vi.py data/ose20261105tp.csv
"""

import argparse
import calendar
import csv
import math
import os
import re
import sys
from datetime import datetime, timedelta

MIN_DAYS = 2
TARGET_MIN = 30 * 1440
YEAR_MIN = 365 * 1440


def _f(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def sq_datetime(expiry):
    """Second Friday of the expiry month, 09:00."""
    y, m = int(expiry[:4]), int(expiry[4:6])
    fridays = [d for d in range(1, calendar.monthrange(y, m)[1] + 1)
               if calendar.weekday(y, m, d) == calendar.FRIDAY]
    return datetime(y, m, fridays[1], 9, 0)


def load_monthly(path):
    """{expiry YYYYMM: {strike: (put, call)}} for NK225 monthly options."""
    out = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for row in csv.reader(fh):
            if len(row) < 14 or row[0].strip() != 'NK225E' or row[1].strip() != 'OOP':
                continue
            exp = row[2].strip()
            if not re.fullmatch(r'\d{6}', exp):  # weeklies carry YYYYMMDD
                continue
            k, put, call = _f(row[3]), _f(row[8]), _f(row[13])
            if k is None or put is None or call is None:
                continue
            out.setdefault(exp, {})[int(round(k))] = (put, call)
    return out


def variance(strikes, t):
    """VIX-style sigma^2 for one expiry; None if the chain is unusable."""
    ks = sorted(strikes)
    if len(ks) < 5 or t <= 0:
        return None
    pairs = [(k, strikes[k][0], strikes[k][1]) for k in ks
             if strikes[k][0] > 0 and strikes[k][1] > 0]
    if not pairs:
        return None
    k_star, p_star, c_star = min(pairs, key=lambda x: abs(x[2] - x[1]))
    fwd = k_star + (c_star - p_star)
    below = [k for k in ks if k <= fwd]
    if not below:
        return None
    k0 = below[-1]
    i0 = ks.index(k0)

    def q(i):
        k = ks[i]
        put, call = strikes[k]
        if i < i0:
            return put
        if i > i0:
            return call
        return (put + call) / 2.0

    used = {i0}
    for step in (-1, 1):
        zeros = 0
        i = i0 + step
        while 0 <= i < len(ks):
            if q(i) <= 0:
                zeros += 1
                if zeros >= 2:
                    break
            else:
                zeros = 0
                used.add(i)
            i += step

    total = 0.0
    for i in used:
        if i == 0:
            dk = ks[1] - ks[0]
        elif i == len(ks) - 1:
            dk = ks[-1] - ks[-2]
        else:
            dk = (ks[i + 1] - ks[i - 1]) / 2.0
        total += dk / (ks[i] ** 2) * q(i)
    return 2.0 / t * total - 1.0 / t * (fwd / k0 - 1.0) ** 2


def compute_vi(path, trade_date=None):
    """Return (vi, detail) or (None, reason)."""
    if trade_date is None:
        m = re.search(r'(\d{8})', os.path.basename(path))
        if not m:
            return None, 'no date in file name'
        trade_date = m.group(1)
    now = datetime.strptime(trade_date, '%Y%m%d') + timedelta(hours=15, minutes=45)

    chains = load_monthly(path)
    terms = []
    for exp in sorted(chains):
        mins = (sq_datetime(exp) - now).total_seconds() / 60.0
        if mins < MIN_DAYS * 1440:
            continue
        terms.append((exp, mins))
        if len(terms) == 2:
            break
    if len(terms) < 2:
        return None, 'need two monthly expiries'

    (e1, n1), (e2, n2) = terms
    t1, t2 = n1 / YEAR_MIN, n2 / YEAR_MIN
    v1, v2 = variance(chains[e1], t1), variance(chains[e2], t2)
    if v1 is None or v2 is None or v1 <= 0 or v2 <= 0:
        return None, 'variance not computable'

    w1 = (n2 - TARGET_MIN) / (n2 - n1)
    w2 = (TARGET_MIN - n1) / (n2 - n1)
    var30 = (t1 * v1 * w1 + t2 * v2 * w2) * YEAR_MIN / TARGET_MIN
    if var30 <= 0:
        return None, 'negative variance'
    vi = 100.0 * math.sqrt(var30)
    detail = {
        'near': e1, 'near_days': round(n1 / 1440, 2), 'near_vol': round(100 * math.sqrt(v1), 2),
        'next': e2, 'next_days': round(n2 / 1440, 2), 'next_vol': round(100 * math.sqrt(v2), 2),
    }
    return round(vi, 2), detail


def main():
    ap = argparse.ArgumentParser(description='Nikkei VI estimate from oseYYYYMMDDtp.csv')
    ap.add_argument('tp_csv')
    ap.add_argument('--date', default=None, help='trade date YYYYMMDD (default: from file name)')
    a = ap.parse_args()
    vi, detail = compute_vi(a.tp_csv, a.date)
    if vi is None:
        print('[compute_vi] not computed: %s' % detail, file=sys.stderr)
        sys.exit(1)
    print('VI %.2f  %s' % (vi, detail))


if __name__ == '__main__':
    main()
