#!/usr/bin/env python3
"""One-image daily summary (1080x1350, for sharing): builds summary/summary_<date>.html
from the day's data and Claude's analysis; scripts/summary_png.js turns it into a PNG.

Reads data/data.json, data/greeks.json, data/iv_timeseries.json,
data/study_base.json and data/manual_assessment_<date>.md (結論 and the
押し目買い・戻り売りの水準 table), plus the 答え合わせ tally (render_checks).

Usage: python scripts/render_summary.py [--data-dir data] [--out-dir summary]
"""
import argparse
import html
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import render_checks
except Exception:
    render_checks = None


def _load(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _md_parts(path):
    """(conclusion headlines, levels rows) from the manual analysis."""
    if not os.path.exists(path):
        return [], []
    lines = open(path, encoding='utf-8').read().splitlines()
    concl, levels, mode = [], [], None
    for ln in lines:
        t = ln.strip()
        if t.startswith('結論'):
            mode = 'c'
            continue
        if t.startswith('押し目買い・戻り売りの水準'):
            mode = 'l'
            continue
        if mode == 'c':
            if t.startswith('・'):
                # the bold lead-in if the bullet starts with one, else its first sentence
                b = re.match(r'・\s*\*\*(.+?)\*\*', t)
                s = b.group(1) if b else re.split(r'(?<=。)', t[1:])[0]
                concl.append(re.sub(r'\*\*', '', s).strip())
            elif t:
                mode = None
        elif mode == 'l':
            if t.startswith('|') and not set(t) <= set('|-: '):
                cells = [c.strip().replace('**', '') for c in t.strip('|').split('|')]
                if cells[0] != '水準' and len(cells) >= 2:
                    levels.append(cells[:3])
            elif t and not t.startswith('|'):
                mode = None
    return concl[:4], levels[:5]


def build(data_dir):
    d = _load(os.path.join(data_dir, 'data.json')) or {}
    meta = d.get('metadata') or {}
    date = meta.get('date')
    if not date:
        return None, None
    close = meta.get('nikkei_close') or (d.get('s01') or {}).get('nikkei_close')
    vi = meta.get('vi') or (d.get('s01') or {}).get('vi')
    base = _load(os.path.join(data_dir, 'study_base.json')) or {}
    ks = sorted(k for k in base if base[k].get('close') and k < date)
    prev = base[ks[-1]]['close'] if ks else None
    chg = (close - prev) if (close and prev) else None

    g = _load(os.path.join(data_dir, 'greeks.json')) or {}
    fe = (g.get('expiries') or [{}])[0]
    ivts = _load(os.path.join(data_dir, 'iv_timeseries.json')) or {}
    exp6 = fe.get('expiry') or ''
    iv = (ivts.get('atm_iv') or {}).get(exp6, [None])[-1]
    skew = (ivts.get('skew') or {}).get(exp6, [None])[-1]
    ind = d.get('indicators') or {}
    s01 = d.get('s01') or {}
    r1 = s01.get('range_1d') or {}
    # 1σ to SQ from the front month's ATM IV
    sq_lo = sq_hi = None
    # same basis as the analysis text: the IV of the strike nearest the close
    ps = fe.get('per_strike') or []
    k_iv = min(ps, key=lambda p: abs(p['strike'] - close))['iv'] if (ps and close) else None
    if k_iv and close and fe.get('T'):
        sd = close * k_iv * math.sqrt(fe['T'])
        sq_lo, sq_hi = close - sd, close + sd

    # OI around the index, front month
    rows = []
    for p in fe.get('per_strike') or []:
        k = p['strike']
        if close and abs(k - close) <= 4600 and k % 500 == 0:
            rows.append((k, p.get('put_oi') or 0, p.get('put_oi_chg') or 0,
                         p.get('call_oi') or 0, p.get('call_oi_chg') or 0))
    rows.sort(reverse=True)

    concl, levels = _md_parts(os.path.join(data_dir, 'manual_assessment_%s.md' % date))
    ck = render_checks.build(data_dir) if render_checks else None
    info = dict(date=date, label=meta.get('date_formatted', date), close=close, chg=chg,
                pct=(chg / prev * 100) if chg is not None else None, vi=vi, iv=iv, skew=skew,
                days_to_sq=meta.get('days_to_sq'), sq_label=meta.get('sq_label', ''),
                exp_label=fe.get('label', ''), max_pain=ind.get('max_pain'),
                r1=r1, sq_lo=sq_lo, sq_hi=sq_hi, rows=rows, concl=concl, levels=levels, ck=ck)
    return date, _html(info)


def _n(x, d=0):
    return '—' if x is None else format(round(x, d) if d else int(round(x)), ',')


def _html(i):
    e = html.escape
    up = (i['chg'] or 0) >= 0
    col = '#c2410c' if up else '#1d4ed8'
    chg = ('%s%s（%+.2f%%）' % ('+' if i['chg'] >= 0 else '−', format(abs(int(round(i['chg']))), ','), i['pct'])) if i['chg'] is not None else ''
    mx = max([max(r[1], r[3]) for r in i['rows']] or [1])
    spot = i['close'] or 0
    near = min(i['rows'], key=lambda r: abs(r[0] - spot))[0] if i['rows'] else None
    bars = ''
    for k, p, pc, c, cc in i['rows']:
        bars += ('<div class="br%s"><div class="pl"><span class="dv">%s</span><i style="width:%.1f%%"></i></div>'
                 '<div class="k">%s</div><div class="cl"><i style="width:%.1f%%"></i><span class="dv">%s</span></div></div>'
                 % (' at' if k == near else '', ('%+d' % pc) if abs(pc) >= 200 else '', min(100, p / mx * 100),
                    format(k, ','), min(100, c / mx * 100), ('%+d' % cc) if abs(cc) >= 200 else ''))
    concl = ''.join('<li>%s</li>' % e(s) for s in i['concl']) or '<li>Claudeの分析はまだありません</li>'
    lv = ''.join('<tr><td class="n">%s</td><td class="p">%s</td></tr>' % (e(r[0]), e(r[1])) for r in i['levels'])
    ck = i['ck']
    cks = ('答え合わせ（これまで）　<b class="h">○%d</b> <b class="pt">△%d</b> <b class="m">×%d</b>　的中率 <b>%s%%</b>'
           % (ck['count']['hit'], ck['count']['part'], ck['count']['miss'], ck['score'])) if ck else ''
    r1 = i['r1']
    return """<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>JPX summary %(date)s</title><style>
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1350px;background:#f6f3ee;color:#1c1917;font-family:'IPAPGothic','IPAGothic','Noto Sans CJK JP',sans-serif;padding:44px 52px}
.hd{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid #1c1917;padding-bottom:16px}
.hd .t{font-size:26px;color:#57534e}.hd .d{font-size:40px;font-weight:700}
.px{display:flex;align-items:baseline;gap:22px;margin:22px 0 6px}
.px .v{font-size:84px;font-weight:700;letter-spacing:-1px}.px .c{font-size:36px;font-weight:700;color:%(col)s}
.sub{font-size:24px;color:#57534e}
.kp{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:22px 0}
.kp div{background:#fff;border:1px solid #e7e5e4;border-radius:12px;padding:12px 14px}
.kp span{display:block;font-size:19px;color:#78716c}.kp b{font-size:32px}
.rg{display:flex;gap:12px;margin-bottom:22px}.rg div{flex:1;background:#1c1917;color:#fafaf9;border-radius:12px;padding:14px 18px;font-size:22px}
.rg b{font-size:32px;display:block;margin-top:2px}
.cols{display:grid;grid-template-columns:1.25fr 1fr;gap:26px}
h3{font-size:24px;margin-bottom:10px;border-left:8px solid #1c1917;padding-left:10px}
ul{list-style:none}li{font-size:25px;line-height:1.45;padding:8px 0 8px 26px;position:relative;border-bottom:1px dashed #d6d3d1}
li:before{content:'●';position:absolute;left:0;top:10px;font-size:16px;color:%(col)s}
table{width:100%%;border-collapse:collapse;margin-top:14px}td{font-size:23px;padding:7px 4px;border-bottom:1px solid #e7e5e4}
td.n{color:#57534e;white-space:nowrap}td.p{font-weight:700;text-align:right;white-space:nowrap}
.br{display:grid;grid-template-columns:1fr 96px 1fr;align-items:center;height:31px}
.br .k{text-align:center;font-size:20px;color:#57534e}.br.at .k{background:#fbbf24;color:#1c1917;font-weight:700;border-radius:6px}
.pl,.cl{position:relative;height:20px;display:flex;align-items:center}.pl{justify-content:flex-end}
.pl i{display:block;height:20px;background:#dc6b6b;border-radius:3px 0 0 3px}.cl i{display:block;height:20px;background:#5b8fd9;border-radius:0 3px 3px 0}
.dv{font-size:16px;color:#44403c;padding:0 5px;white-space:nowrap}
.lg{display:flex;justify-content:space-between;font-size:18px;color:#78716c;margin:4px 0}
.ft{position:absolute;left:52px;right:52px;bottom:36px;display:flex;justify-content:space-between;font-size:20px;color:#57534e;border-top:2px solid #1c1917;padding-top:12px}
.ft b.h{color:#16a34a}.ft b.pt{color:#d97706}.ft b.m{color:#dc2626}
</style></head><body>
<div class="hd"><div><div class="t">日経225オプション 日次サマリー</div><div class="d">%(label)s</div></div>
<div class="t">%(sq_label)s まで%(dsq)s営業日</div></div>
<div class="px"><div class="v">%(close)s</div><div class="c">%(chg)s</div></div>
<div class="sub">日経平均 終値</div>
<div class="kp"><div><span>日経VI</span><b>%(vi)s</b></div><div><span>ATM IV（%(exp)s）</span><b>%(iv)s</b></div>
<div><span>スキュー</span><b>%(skew)s</b></div><div><span>MaxPain</span><b>%(mp)s</b></div>
<div><span>建玉の壁</span><b style="font-size:22px;line-height:1.25;display:block">P %(pw)s<br>C %(cw)s</b></div></div>
<div class="rg"><div>明日の想定値幅（日経VIから）<b>%(r1lo)s 〜 %(r1hi)s</b></div><div>SQまでの想定レンジ（1σ）<b>%(sqlo)s 〜 %(sqhi)s</b></div></div>
<div class="cols"><div><h3>Claudeの分析（結論）</h3><ul>%(concl)s</ul><table>%(lv)s</table></div>
<div><h3>建玉の分布（%(exp)s）</h3><div class="lg"><span>◀ プット</span><span>数字は前日比（±200枚以上）</span><span>コール ▶</span></div>%(bars)s</div></div>
<div class="ft"><span>%(ck)s</span><span>投資助言ではありません</span></div>
</body></html>""" % dict(
        date=e(i['date']), label=e(i['label']), sq_label=e(i['sq_label']), dsq=i['days_to_sq'] or '—',
        close=_n(i['close']), chg=chg, col=col, vi=('%.1f' % i['vi']) if i['vi'] else '—',
        iv=('%.1f%%' % i['iv']) if i['iv'] else '—', skew=('%.1fpt' % i['skew']) if i['skew'] is not None else '—',
        exp=e(i['exp_label']), mp=_n(i['max_pain']),
        pw=_n(max(i['rows'], key=lambda r: r[1])[0]) if i['rows'] else '—',
        cw=_n(max(i['rows'], key=lambda r: r[3])[0]) if i['rows'] else '—',
        r1lo=_n(r1.get('low')), r1hi=_n(r1.get('high')), sqlo=_n(i['sq_lo']), sqhi=_n(i['sq_hi']),
        concl=concl, lv=lv, bars=bars, ck=cks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out-dir', default='summary')
    a = ap.parse_args()
    date, h = build(a.data_dir)
    if not h:
        print('[summary] no data')
        return 1
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, 'summary_%s.html' % date)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(h)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
