#!/usr/bin/env python3
"""検証: do walls hold, and does the index go where open interest was built?

For each day this takes, from the option OI file and the J-NET blocks:
  * the put wall  (largest put OI below the index, within 10%)
  * the call wall (largest call OI above it, within 10%)
  * strikes whose OI rose by 300+ that day (within 10%)
  * strikes of J-NET blocks that opened new OI (opt_blocks verdict 新規建て)
and then checks, over the following days, whether a close went through the
wall or reached the strike.

Reaching a level is likely or unlikely depending only on how far away it is
and how volatile the index is, so each event is compared with the chance the
same move had if nothing were there: a Monte Carlo of daily closes with that
day's σ (front ATM IV, or 20-day realised vol before 6/12). Actual rate below
that baseline means the level held the index off; above it, that the index
was drawn to it.

Data: per-day level summaries in data/study_walls_base.json (upserted daily
from the latest OI file and opt_blocks.json; --backfill-git rebuilds the past
from committed files) and closes / σ from data/study_base.json.
Output: data/study_walls.json.
"""
import argparse
import datetime
import json
import math
import os
import random
import subprocess

from extract_opt_blocks import parse_oi, parse_jnet, build_day, _git_files, _merge, JNET_FILES

WALL_RANGE = 0.10
MIN_MOVE = 300
MIN_BLOCK = 100
HORIZONS = (5, 10)
PATHS = 4000


def _sq(exp4):
    y, m = 2000 + int(exp4[:2]), int(exp4[2:])
    d = datetime.date(y, m, 8)
    return d + datetime.timedelta(days=(4 - d.weekday()) % 7)


def _front(dt, exps):
    """Nearest monthly expiry with at least a week to SQ."""
    day = datetime.date(int(dt[:4]), int(dt[4:6]), int(dt[6:]))
    ok = sorted(e for e in exps if _sq(e) >= day + datetime.timedelta(days=7))
    return ok[0] if ok else None


def summarise(dt, oi, blocks, spot):
    """Levels of one day: walls of the front month, 300+ builds, new-OI blocks."""
    lo, hi = spot * (1 - WALL_RANGE), spot * (1 + WALL_RANGE)
    exps = {e for (_, e, _) in oi}
    fr = _front(dt, exps)
    puts = [(v[1], k) for (s, e, k), v in oi.items() if s == 'P' and e == fr and lo <= k < spot and v[1]]
    calls = [(v[1], k) for (s, e, k), v in oi.items() if s == 'C' and e == fr and spot < k <= hi and v[1]]
    out = {'front': fr,
           'pw': max(puts)[1] if puts else None, 'pw_oi': max(puts)[0] if puts else None,
           'cw': max(calls)[1] if calls else None, 'cw_oi': max(calls)[0] if calls else None,
           'builds': sorted([s, e, k, v[2]] for (s, e, k), v in oi.items()
                            if v[2] is not None and v[2] >= MIN_MOVE and lo <= k <= hi),
           'blocks': sorted([b['side'], b['exp'], b['k'], b['lots']] for b in (blocks or [])
                            if b.get('verdict') == '新規建て' and b['lots'] >= MIN_BLOCK and lo <= b['k'] <= hi)}
    return out


def _load(path, empty):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return empty


def _backfill(levels, base, repo):
    show = lambda sp: subprocess.check_output(['git', '-C', repo, 'show', '%s:%s' % sp])
    ois = _git_files(repo, 'open_interest.xlsx')
    day = _git_files(repo, JNET_FILES[0])
    night = _git_files(repo, JNET_FILES[1])
    for dt in sorted(ois):
        spot = (base.get(dt) or {}).get('close')
        if dt in levels or not spot:
            continue
        try:
            oi = parse_oi(show(ois[dt]))
            blocks = []
            if dt in day:
                jn = parse_jnet(show(day[dt]), 'day')
                if dt in night:
                    _merge(jn, parse_jnet(show(night[dt]), 'night'))
                blocks = build_day(oi, jn)['blocks']
            levels[dt] = summarise(dt, oi, blocks, spot)
        except Exception as e:
            print('[study_walls] backfill %s failed: %s' % (dt, e))


_cache = {}


def p_touch(x, sd, h, below):
    """Chance that some close within h days goes past log-distance x (MC, daily closes)."""
    key = (round(x / sd, 2), h, below)
    if key not in _cache:
        rng = random.Random(hash(key) & 0xffffffff)
        hit = 0
        for _ in range(PATHS):
            s = 0.0
            for _ in range(h):
                s += rng.gauss(0, 1)
                if (below and s <= key[0]) or (not below and s >= key[0]):
                    hit += 1
                    break
        _cache[key] = hit / PATHS
    return _cache[key]


def evaluate(levels, base):
    days = sorted(d for d, r in base.items() if r.get('close'))
    pos = {d: i for i, d in enumerate(days)}
    closes = [base[d]['close'] for d in days]

    def sigma_d(dt):
        i = pos[dt]
        r = base[dt]
        if r.get('iv'):
            return r['iv'] / 100 / math.sqrt(250)
        if i >= 20:
            lr = [math.log(closes[j] / closes[j - 1]) for j in range(i - 19, i + 1)]
            m = sum(lr) / 20
            return math.sqrt(sum((x - m) ** 2 for x in lr) / 19)
        return None

    groups = {}

    def add(key, dt, k, below, h):
        i = pos.get(dt)
        sd = sigma_d(dt) if i is not None else None
        if sd is None or i + h >= len(days):
            return
        spot = closes[i]
        path = closes[i + 1:i + 1 + h]
        hit = any(c <= k for c in path) if below else any(c >= k for c in path)
        g = groups.setdefault((key, h), {'n': 0, 'hit': 0, 'exp': 0.0, 'dates': []})
        g['n'] += 1
        g['hit'] += hit
        g['exp'] += p_touch(math.log(k / spot), sd, h, below)
        g['dates'].append(dt)

    for dt in sorted(levels):
        lv = levels[dt]
        for h in HORIZONS:
            if lv.get('pw'):
                add('put_wall', dt, lv['pw'], True, h)
            if lv.get('cw'):
                add('call_wall', dt, lv['cw'], False, h)
            spot = (base.get(dt) or {}).get('close')
            if not spot:
                continue
            for s, e, k, chg in lv.get('builds') or []:
                add('build_' + s, dt, k, k < spot, h)
            for s, e, k, lots in lv.get('blocks') or []:
                add('block_' + s, dt, k, k < spot, h)
    return groups


# name, verb stem for the card's "理論より○○にくい / ○○やすい" tag
LABELS = {
    'put_wall': ('下値の壁（最大のプット建玉）を終値で割った', '割れ'),
    'call_wall': ('上値の壁（最大のコール建玉）を終値で超えた', '超え'),
    'build_P': ('建玉が+300枚以上増えたプットの行使価格に届いた', '届き'),
    'build_C': ('建玉が+300枚以上増えたコールの行使価格に届いた', '届き'),
    'block_P': ('大口（J-NET・100枚以上）がプットを新規建てした行使価格に届いた', '届き'),
    'block_C': ('大口（J-NET・100枚以上）がコールを新規建てした行使価格に届いた', '届き'),
}


def _binom_p(k, n, p):
    """Two-sided exact binomial test of k hits in n against rate p."""
    from math import comb
    if not n:
        return None
    pk = comb(n, k) * p ** k * (1 - p) ** (n - k)
    return min(1.0, sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)
                        if comb(n, i) * p ** i * (1 - p) ** (n - i) <= pk + 1e-12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--backfill-git', action='store_true')
    a = ap.parse_args()
    base = _load(os.path.join(a.data_dir, 'study_base.json'), {})
    lv_path = os.path.join(a.data_dir, 'study_walls_base.json')
    levels = _load(lv_path, {})
    if a.backfill_git:
        _backfill(levels, base, os.path.dirname(os.path.abspath(a.data_dir)))

    # today: newest OI file in data/, blocks from opt_blocks.json
    oi_files = sorted(f for f in os.listdir(a.data_dir) if f.endswith('open_interest.xlsx'))
    if oi_files:
        dt = oi_files[-1][:8]
        spot = (base.get(dt) or {}).get('close')
        if spot:
            blocks = ((_load(os.path.join(a.data_dir, 'opt_blocks.json'), {}).get('days') or {}).get(dt) or {}).get('blocks')
            levels[dt] = summarise(dt, parse_oi(os.path.join(a.data_dir, oi_files[-1])), blocks, spot)
    with open(lv_path, 'w', encoding='utf-8') as f:
        json.dump({k: levels[k] for k in sorted(levels)}, f, ensure_ascii=False, separators=(',', ':'))

    groups = evaluate(levels, base)
    tests = []
    for key, (name, verb) in LABELS.items():
        row = {'key': key, 'name': name, 'verb': verb, 'by_h': []}
        for h in HORIZONS:
            g = groups.get((key, h))
            if not g or not g['n']:
                continue
            exp = g['exp'] / g['n']
            row['by_h'].append({'h': h, 'n': g['n'], 'hit': g['hit'], 'rate': g['hit'] / g['n'],
                                'exp': exp, 'p': _binom_p(g['hit'], g['n'], exp),
                                'first': g['dates'][0], 'last': g['dates'][-1]})
        tests.append(row)
    latest = max(levels) if levels else None
    out = {'as_of': latest, 'today': levels.get(latest), 'spot': (base.get(latest) or {}).get('close'),
           'tests': tests, 'period': [min(levels) if levels else None, latest]}
    with open(os.path.join(a.data_dir, 'study_walls.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print('[study_walls] %d days of levels | latest %s' % (len(levels), latest))


if __name__ == '__main__':
    main()
