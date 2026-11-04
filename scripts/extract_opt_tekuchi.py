#!/usr/bin/env python3
"""Option volume by strike and date, overall and per participant, with history.

Two sources, kept side by side because they answer different questions:

  * vol — the market's total volume per contract, from <date>open_interest.xlsx
    (day + night, auction + J-NET). Every strike that traded is here.
  * tk  — participant volume (手口) per contract, from the four session files
    <date>_volume_by_participant_{whole_day,night}[_J-NET].xlsx, kept per
    session: [day auction, night auction, day J-NET, night J-NET].

The 手口 files show volume only, with no buy/sell side, and every lot appears
once for the buyer and once for the seller, so the sum over participants is
about twice the market volume. JPX also lists only some contracts and only the
larger participants on each, so a strike can trade without appearing in 手口.

Matching the tables that circulate on social media (11/4 checked): their
"strike x date heatmap" is the sum over every participant of the two auction
sessions, and their "外資13社 / per-firm" tables are the same sum for those
firms across all four sessions. Neither is a net (buy - sell) figure; only the
weekly participant OI (opt_weekly.json) gives one.

Output data/opt_tekuchi.json:
    {"dates": [...], "days": {date: {"vol": {"P2611-62000": 400, ...},
                                     "tk": {"P2611-62000": {broker: [da, na, dj, nj]}}}}}
"""
import argparse
import json
import os
import re

import openpyxl

from extract_opt_blocks import parse_oi

KEEP = 40
# session order inside each [..] list
SESSIONS = [
    ('_volume_by_participant_whole_day.xlsx', 0),
    ('_volume_by_participant_night.xlsx', 1),
    ('_volume_by_participant_whole_day_J-NET.xlsx', 2),
    ('_volume_by_participant_night_J-NET.xlsx', 3),
]
_CONTRACT = re.compile(r'([PC])(\d{4})-(\d+)$')


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).lstrip('='))
    except (TypeError, ValueError):
        return None


def parse_tekuchi(path):
    """{'P2611-62000': {broker: lots}} for Nikkei 225 (large) options."""
    out = {}
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    for r in ws.iter_rows(values_only=True):
        if not r or len(r) < 8 or str(r[0] or '').strip() != 'NK225E':
            continue
        m = _CONTRACT.search(str(r[2] or '').strip())
        broker = str(r[5] or '').strip()
        v = _num(r[7])
        if not m or not broker or not v:
            continue
        key = '%s%s-%s' % (m.group(1), m.group(2), m.group(3))
        out.setdefault(key, {})
        out[key][broker] = out[key].get(broker, 0) + int(round(v))
    return out


def build_day(data_dir, dt):
    """Entry for one date, or None when the 手口 files are not all there."""
    paths = [(os.path.join(data_dir, dt + suffix), i) for suffix, i in SESSIONS]
    missing = [os.path.basename(p) for p, _ in paths if not os.path.exists(p)]
    if missing:
        return None, missing
    tk = {}
    for p, i in paths:
        for key, by in parse_tekuchi(p).items():
            for b, v in by.items():
                tk.setdefault(key, {}).setdefault(b, [0, 0, 0, 0])[i] += v
    vol = {}
    oi_path = os.path.join(data_dir, dt + 'open_interest.xlsx')
    if os.path.exists(oi_path):
        for (side, exp, k), (v, _oi, _chg) in parse_oi(oi_path).items():
            if v:
                vol['%s%s-%d' % (side, exp, k)] = v
    return {'vol': vol, 'tk': tk}, []


def _load(path):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d.get('days'), dict):
                return d
        except Exception:
            pass
    return {'dates': [], 'days': {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default=None, help='default: <data-dir>/opt_tekuchi.json')
    a = ap.parse_args()
    out = a.out or os.path.join(a.data_dir, 'opt_tekuchi.json')
    store = _load(out)

    dates = sorted({m.group(1) for m in (re.match(r'(\d{8})_volume_by_participant', f)
                                         for f in os.listdir(a.data_dir)) if m})
    for dt in dates:
        day, missing = build_day(a.data_dir, dt)
        if day is None:
            # The workflow's cleanup can leave only some session files behind;
            # keep whatever was built from the full set on an earlier run.
            print('[opt_tekuchi] %s: %s missing; %s' % (
                dt, ', '.join(missing), 'keeping stored entry' if dt in store['days'] else 'skipped'))
            continue
        store['days'][dt] = day

    keep = sorted(store['days'])[-KEEP:]
    store = {'dates': keep, 'days': {d: store['days'][d] for d in keep}}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, separators=(',', ':'))
    last = store['days'].get(keep[-1], {}) if keep else {}
    print('[opt_tekuchi] wrote %s | %d days | latest %s: %d contracts in 手口, %d traded'
          % (out, len(keep), keep[-1] if keep else '-', len(last.get('tk', {})), len(last.get('vol', {}))))


if __name__ == '__main__':
    main()
