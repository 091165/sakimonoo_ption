#!/usr/bin/env python3
"""検証: how often the index moved more than options implied, after each kind of day.

A "大きな動き" is a close-to-close move beyond 1σ of what that day's front ATM
IV implied: σ = IV × √(horizon / 250), for the next day and five days out.
Measuring in σ makes calm and volatile periods comparable; before 6/12, when
there is no IV history, the 20-day realised volatility stands in.

For each condition (a kind of day: IV jump, futures new shorts, high PCR, ...)
the rate of large moves after it is compared with the rate after all days,
and the split between up and down is tested against the usual split with an
exact binomial test. The p-value says how often a split that lopsided would
appear by luck; overlapping five-day windows make it look better than it is,
which the card states.

Inputs, kept in data/study_base.json (one row per day, upserted daily):
  close            Nikkei 225 cash close (futures_flow.json / tp.csv)
  iv, skew, front  front-month ATM IV and skew (iv_timeseries.json snapshots)
  fut_large/mini   futures OI change (data.json s02)
  put_vol/call_vol large option volume (data.json s03)
  moves300         contracts whose OI moved ±300 or more (data.json s05)
--backfill-git rebuilds past rows from the files committed over time.

Output data/study.json: definitions, base rates, per-condition stats and the
conditions that apply to the latest day.
"""
import argparse
import datetime
import json
import math
import os
import re
import subprocess
from math import comb

SIGMA_K = 1.0
BIG_K = 1.5
HORIZONS = ((1, '翌日'), (5, '5日後'))
FUT_FLAT_OI = 170          # large OI changes under this are noise
PRICE_FLAT = 0.0015


def _load(path, empty):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return empty


def _signals(d):
    """Per-day features from one data.json."""
    s02, s03 = d.get('s02') or {}, (d.get('s03') or {}).get('large') or {}
    return {
        'fut_large': (s02.get('nk225_large') or {}).get('total_change'),
        'fut_mini': (s02.get('nk225_mini') or {}).get('total_change'),
        'put_vol': s03.get('put_volume'), 'call_vol': s03.get('call_volume'),
        'moves300': len(d.get('s05') or []),
    }


def _iv_rows(base, data_dir):
    snaps = (_load(os.path.join(data_dir, 'iv_timeseries.json'), {}) or {}).get('_snapshots') or {}
    for dt, sn in snaps.items():
        e = (sn.get('expiries') or {}).get(sn.get('front')) or {}
        if e.get('atm_iv'):
            row = base.setdefault(dt, {})
            row.update({'iv': e['atm_iv'], 'skew': e.get('skew_10pct'), 'front': sn.get('front')})


BLOCK_MIN = 100      # J-NET block size that counts as 大口
BLOCK_RANGE = 0.10   # strikes within this distance of the close


def _blocks(base, data_dir):
    """blk_P / blk_C: lots of new-OI J-NET blocks (100+) within 10% that day.

    History comes from the walls study's daily levels (4/1 onward); recent
    days from opt_blocks.json, which this step runs before the walls step
    has added today.
    """
    levels = _load(os.path.join(data_dir, 'study_walls_base.json'), {}) or {}
    for dt, lv in levels.items():
        row = base.setdefault(dt, {})
        for side in ('P', 'C'):
            row['blk_' + side] = sum(b[3] for b in lv.get('blocks') or [] if b[0] == side)
    days = (_load(os.path.join(data_dir, 'opt_blocks.json'), {}) or {}).get('days') or {}
    for dt, day in days.items():
        close = (base.get(dt) or {}).get('close')
        if not close:
            continue
        row = base[dt]
        for side in ('P', 'C'):
            row['blk_' + side] = sum(b['lots'] for b in day.get('blocks') or []
                                     if b['side'] == side and b.get('verdict') == '新規建て'
                                     and b['lots'] >= BLOCK_MIN and abs(b['k'] / close - 1) <= BLOCK_RANGE)


def _closes(base, data_dir):
    flow = _load(os.path.join(data_dir, 'futures_flow.json'), {}) or {}
    for dt, r in (flow.get('rows') or {}).items():
        if r.get('close'):
            base.setdefault(dt, {})['close'] = r['close']


def _backfill_git(base, repo):
    git = lambda *a: subprocess.check_output(['git', '-C', repo] + list(a))
    # closes: every committed OHLC history, then the tp.csv underlying (authoritative)
    for sha in git('log', '--format=%H', '--', 'data/market_latest.json').decode().split():
        try:
            m = json.loads(git('show', sha + ':data/market_latest.json'))
        except Exception:
            continue
        for b in m.get('ohlc_history') or []:
            dt = str(b.get('date', '')).replace('-', '')
            if b.get('close') and not base.get(dt, {}).get('close'):
                base.setdefault(dt, {})['close'] = round(float(b['close']), 2)
    sha = None
    for ln in git('log', '--diff-filter=A', '--format=%H', '--name-only', '--', 'data/ose*tp.csv').decode().splitlines():
        ln = ln.strip()
        if re.fullmatch(r'[0-9a-f]{40}', ln):
            sha = ln
            continue
        m = re.search(r'ose(\d{8})tp\.csv$', ln)
        if not (sha and m):
            continue
        for line in git('show', '%s:%s' % (sha, ln)).decode('utf-8', 'replace').splitlines():
            q = line.split(',')
            if len(q) > 15 and q[0].strip() == 'NK225E':
                base.setdefault(m.group(1), {})['close'] = round(float(q[15]), 2)
                break
    # signals: the last committed data.json of each date (log is newest first)
    seen = set()
    for sha in git('log', '--format=%H', '--', 'data/data.json').decode().split():
        try:
            d = json.loads(git('show', sha + ':data/data.json'))
        except Exception:
            continue
        dt = (d.get('metadata') or {}).get('date')
        if not dt or dt in seen:
            continue
        seen.add(dt)
        base.setdefault(dt, {}).update({k: v for k, v in _signals(d).items() if k not in base.get(dt, {})})


def _is_sq(dt):
    x = datetime.date(int(dt[:4]), int(dt[4:6]), int(dt[6:]))
    return x.weekday() == 4 and 8 <= x.day <= 14


def _binom_p(k, n, p):
    if not n:
        return None
    pk = comb(n, k) * p ** k * (1 - p) ** (n - k)
    return min(1.0, sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)
                        if comb(n, i) * p ** i * (1 - p) ** (n - i) <= pk + 1e-12))


def build_rows(base):
    days = sorted(d for d, r in base.items() if r.get('close'))
    closes = [base[d]['close'] for d in days]
    rows = []
    for i, d in enumerate(days):
        r = dict(base[d], d=d)
        r['r0'] = closes[i] / closes[i - 1] - 1 if i else None
        if i >= 20:
            lr = [math.log(closes[j] / closes[j - 1]) for j in range(i - 19, i + 1)]
            m = sum(lr) / 20
            r['hv'] = math.sqrt(sum((x - m) ** 2 for x in lr) / 19) * math.sqrt(250) * 100
        vol = r.get('iv') or r.get('hv')
        r['vol_src'] = 'iv' if r.get('iv') else ('hv' if r.get('hv') else None)
        for h, _ in HORIZONS:
            if vol and i + h < len(days):
                ret = closes[i + h] / closes[i] - 1
                sig = vol / 100 * math.sqrt(h / 250.0)
                r['z%d' % h] = ret / sig
        prev = base[days[i - 1]] if i else {}
        if r.get('iv') and prev.get('iv') and r.get('front') == prev.get('front'):
            r['div'] = r['iv'] - prev['iv']
            if r.get('skew') is not None and prev.get('skew') is not None:
                r['dsk'] = r['skew'] - prev['skew']
        rows.append(r)
    return rows


def _pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[int(q * (len(xs) - 1))] if xs else None


def conditions(rows):
    pcr = [r['put_vol'] / r['call_vol'] for r in rows if r.get('put_vol') and r.get('call_vol')]
    pcr_hi, pcr_lo = _pct(pcr, 0.8), _pct(pcr, 0.2)
    mini_hi = _pct([abs(r['fut_mini']) for r in rows if r.get('fut_mini') is not None], 0.8)
    mv_hi = _pct([r.get('moves300') for r in rows if r.get('moves300') is not None], 0.8)
    sk = [r.get('skew') for r in rows if r.get('skew') is not None]
    sk_hi, sk_lo = _pct(sk, 0.8), _pct(sk, 0.2)

    def fut(r):
        if r.get('fut_large') is None or r.get('r0') is None or _is_sq(r['d']):
            return None
        if abs(r['r0']) < PRICE_FLAT or abs(r['fut_large']) < FUT_FLAT_OI:
            return None
        if r['r0'] > 0:
            return '新規買い' if r['fut_large'] > 0 else '買い戻し'
        return '新規売り' if r['fut_large'] > 0 else '手仕舞い'

    pcr_of = lambda r: (r['put_vol'] / r['call_vol']) if (r.get('put_vol') and r.get('call_vol')) else None
    gap = lambda r: (r['iv'] - r['hv']) if (r.get('iv') and r.get('hv')) else None
    return [
        ('iv_up', 'IVが前日比+2pt以上', lambda r: (r.get('div') or 0) >= 2),
        ('iv_dn', 'IVが前日比−2pt以下', lambda r: (r.get('div') or 0) <= -2),
        ('skew_up', 'スキューが前日比+1.5pt以上', lambda r: (r.get('dsk') or 0) >= 1.5),
        ('skew_hi', 'スキューが高い（%.1fpt以上・上位20%%）' % (sk_hi or 0),
            lambda r: r.get('skew') is not None and r['skew'] >= (sk_hi or 1e9)),
        ('skew_lo', 'スキューが低い（%.1fpt以下・下位20%%）' % (sk_lo or 0),
            lambda r: r.get('skew') is not None and r['skew'] <= (sk_lo if sk_lo is not None else -1e9)),
        ('iv_rich', 'IVが実現ボラより+4pt以上高い', lambda r: (gap(r) or 0) >= 4),
        ('iv_cheap', 'IVが実現ボラより低い', lambda r: gap(r) is not None and gap(r) < 0),
        ('moved', '当日すでに1σ以上動いた', lambda r: r.get('r0') is not None and r.get('iv') and
            abs(r['r0']) >= r['iv'] / 100 / math.sqrt(250)),
        ('fut_short', '先物：新規売り（価格↓・建玉↑）', lambda r: fut(r) == '新規売り'),
        ('fut_long', '先物：新規買い（価格↑・建玉↑）', lambda r: fut(r) == '新規買い'),
        ('fut_liq', '先物：手仕舞い（価格↓・建玉↓）', lambda r: fut(r) == '手仕舞い'),
        ('fut_cover', '先物：買い戻し（価格↑・建玉↓）', lambda r: fut(r) == '買い戻し'),
        ('mini_big', 'mini建玉の大きな増減（上位20%%：±%s枚以上）' % format(int(mini_hi or 0), ','),
            lambda r: r.get('fut_mini') is not None and abs(r['fut_mini']) >= (mini_hi or 1e18)),
        ('call_day', '特異日：コール取引高＞プット', lambda r: (pcr_of(r) or 9) < 1),
        ('pcr_hi', 'PCR（出来高）が高い（%.2f以上）' % (pcr_hi or 0), lambda r: (pcr_of(r) or 0) >= (pcr_hi or 1e9)),
        ('pcr_lo', 'PCR（出来高）が低い（%.2f以下）' % (pcr_lo or 0), lambda r: pcr_of(r) is not None and pcr_of(r) <= (pcr_lo or -1)),
        ('oi_moves', '建玉±300枚以上の銘柄が多い（%d件以上）' % (mv_hi or 0), lambda r: (r.get('moves300') or 0) >= (mv_hi or 1e9)),
        ('blk_put', '大口（J-NET・100枚以上）がプットを新規建て', lambda r: (r.get('blk_P') or 0) > 0),
        ('blk_call', '大口（J-NET・100枚以上）がコールを新規建て', lambda r: (r.get('blk_C') or 0) > 0),
    ]


def _count(sub, h):
    zs = [r['z%d' % h] for r in sub if r.get('z%d' % h) is not None]
    up = sum(1 for z in zs if z >= SIGMA_K)
    dn = sum(1 for z in zs if z <= -SIGMA_K)
    big = sum(1 for z in zs if abs(z) >= BIG_K)
    return {'n': len(zs), 'up': up, 'dn': dn, 'big': big}


def study(base):
    rows = build_rows(base)
    out_rows = [r for r in rows if any(r.get('z%d' % h) is not None for h, _ in HORIZONS)]
    base_stats = {str(h): _count(out_rows, h) for h, _ in HORIZONS}
    conds = []
    for key, name, f in conditions(rows):
        sub = [r for r in out_rows if f(r)]
        st = {}
        for h, _ in HORIZONS:
            c = _count(sub, h)
            b = base_stats[str(h)]
            bu = b['up'] / (b['up'] + b['dn']) if (b['up'] + b['dn']) else 0.5
            c['p_dir'] = _binom_p(c['up'], c['up'] + c['dn'], bu)
            st[str(h)] = c
        hits = [r['d'] for r in rows if f(r)]   # includes today, which has no outcome yet
        conds.append({'key': key, 'name': name, 'stats': st, 'last': hits[-1] if hits else None})
    today = rows[-1] if rows else {}
    applies = [c['key'] for c, (_, _, f) in zip(conds, conditions(rows)) if today and f(today)]
    first = next((r['d'] for r in out_rows), None)
    iv_from = next((r['d'] for r in out_rows if r.get('vol_src') == 'iv'), None)
    return {
        'as_of': today.get('d'), 'period': [first, out_rows[-1]['d'] if out_rows else None],
        'iv_from': iv_from, 'sigma_k': SIGMA_K, 'big_k': BIG_K,
        'horizons': [{'h': h, 'label': lab} for h, lab in HORIZONS],
        'base': base_stats, 'conds': conds, 'applies_today': applies,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--backfill-git', action='store_true')
    a = ap.parse_args()
    base_path = os.path.join(a.data_dir, 'study_base.json')
    base = _load(base_path, {})
    if a.backfill_git:
        _backfill_git(base, os.path.dirname(os.path.abspath(a.data_dir)))
    _iv_rows(base, a.data_dir)
    _closes(base, a.data_dir)
    _blocks(base, a.data_dir)
    d = _load(os.path.join(a.data_dir, 'data.json'), {})
    dt = (d.get('metadata') or {}).get('date')
    if dt:
        base.setdefault(dt, {}).update(_signals(d))
    with open(base_path, 'w', encoding='utf-8') as f:
        json.dump({k: base[k] for k in sorted(base)}, f, ensure_ascii=False, separators=(',', ':'))
    res = study(base)
    with open(os.path.join(a.data_dir, 'study.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
    print('[study] %d days in base | period %s | applies today: %s'
          % (len(base), res['period'], ','.join(res['applies_today']) or '-'))


if __name__ == '__main__':
    main()
