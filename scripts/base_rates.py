#!/usr/bin/env python3
"""Print the base rates that decide whether the day's analysis may state a
direction for the next day (rule 1 of the analysis template).

Reads data/study_base.json (daily closes and futures OI changes since March)
and data/study.json (the 検証 card's conditional statistics), and prints:

  - the latest day's move and, if it was >=2% or >=3%, how often the next
    day went the other way in the past;
  - how often the futures-flow rule (OI up on a down day = continuation)
    called the next day right — kept to show why it is not used alone;
  - which 検証 conditions are on for the latest day, with their next-day
    up/down counts.

Usage: python scripts/base_rates.py [--data-dir data]
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    a = ap.parse_args()
    base = json.load(open(os.path.join(a.data_dir, 'study_base.json'), encoding='utf-8'))
    ks = sorted(k for k in base if base[k].get('close'))
    c = [base[k]['close'] for k in ks]
    r = [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    last = r[-1]
    print('期間 %s〜%s（%d営業日）' % (ks[0], ks[-1], len(ks)))
    print('最新日 %s の前日比 %+.2f%%' % (ks[-1], last * 100))

    for th in (0.03, 0.02):
        same = rev = 0
        for i in range(len(r) - 1):
            if abs(r[i]) >= th:
                if r[i] * r[i + 1] > 0:
                    same += 1
                else:
                    rev += 1
        on = '★該当' if abs(last) >= th else '　非該当'
        print('%s ±%d%%以上動いた翌日: 反対方向 %d回 / 同じ方向 %d回（反対の割合 %d%%）'
              % (on, th * 100, rev, same, round(rev / max(1, rev + same) * 100)))

    # futures-flow rule: OI up -> continuation, OI down -> reversal
    hit = n = 0
    for i in range(1, len(ks) - 1):
        d = base[ks[i]]
        if d.get('fut_mini') is None or d.get('fut_large') is None:
            continue
        oi = (d.get('fut_mini') or 0) / 10 + (d.get('fut_large') or 0)
        ret = r[i - 1]
        if abs(ret) < 0.005 or abs(oi) < 1000:
            continue
        pred = ret if oi > 0 else -ret
        n += 1
        hit += (pred * r[i] > 0)
    print('参考 先物の建玉で翌日の方向を読むルール: %d回中%d回（%d%%）＝単独では使わない'
          % (n, hit, round(hit / max(1, n) * 100)))

    st_path = os.path.join(a.data_dir, 'study.json')
    if os.path.exists(st_path):
        st = json.load(open(st_path, encoding='utf-8'))
        latest = ks[-1]
        print('検証カードの条件（翌日の 上げ/下げ は大きな動きの回数、n は該当日数）:')
        for cnd in st.get('conds', []):
            s1 = (cnd.get('stats') or {}).get('1') or {}
            on = '★該当' if cnd.get('last') == latest else '　'
            print('%s %s: n=%s 上げ%s 下げ%s（偏りのp値 %.2f）'
                  % (on, cnd['name'], s1.get('n'), s1.get('up'), s1.get('dn'), s1.get('p_dir') or 1))


if __name__ == '__main__':
    main()
