#!/usr/bin/env python3
"""Card: 先物の大口（参加者別） — who put size through J-NET today, and how
unusual that was for them.

J-NET is where institutions cross blocks off the order book, so its volume is
the closest public trace of 大口 activity. Two things made the old ranking
hard to read and are handled here:
  * retail brokers (SBI, 楽天, ...) cross huge mini volume on J-NET for their
    clients; they are taken out of the main table and summarised in one line;
  * a big number means little without the broker's own baseline, so each
    broker's volume is shown against its average over the previous 20 days.

The auction leaders are shown only as context: the top of the book is
dominated by clearing firms for high-frequency flow (ABN, ソシエテ, バークレイズ)
every day. Volume carries no buy/sell side, so none of this is direction.
"""

import json

RETAIL = ('ＳＢＩ', '楽天', 'ｅスマート', '松井', 'マネックス', 'カブコム', 'ＧＭＯ')
CAT_LABEL = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'domestic': '国内', 'other': 'その他'}
BASE_DAYS = 20
MIN_BASE = 50  # below this average a ratio is noise ("普段はほぼ無し")


def _is_retail(name):
    return any(k in name for k in RETAIL)


def _short(name):
    return name.replace('証券', '').replace('クリアリン', '')


def build(fb):
    if not fb or not fb.get('dates'):
        return None
    dates = fb['dates']
    today = dates[-1]
    past = dates[-(BASE_DAYS + 1):-1]
    rows = fb['rows']
    cur = rows[today]

    def base(broker, prod):
        vals = [rows[d].get(broker, {}).get('j', {}).get(prod, 0) for d in past]
        return sum(vals) / len(vals) if vals else None

    inst = []
    for b, c in cur.items():
        if _is_retail(b):
            continue
        jl, jt = c['j'].get('large', 0), c['j'].get('topix', 0)
        if jl + jt <= 0:
            continue
        bl, bt = base(b, 'large'), base(b, 'topix')
        inst.append({
            'name': _short(b), 'cat': c.get('cat', 'other'),
            'jl': jl, 'jt': jt,
            'rl': (jl / bl) if (bl and bl >= MIN_BASE) else None,
            'rt': (jt / bt) if (bt and bt >= MIN_BASE) else None,
            'bl': bl, 'bt': bt,
        })
    by_large = sorted(inst, key=lambda x: -x['jl'])[:8]
    by_topix = sorted(inst, key=lambda x: -x['jt'])[:5]
    seen, table = set(), []
    for x in by_large + by_topix:
        if x['name'] not in seen:
            seen.add(x['name'])
            table.append(x)
    table.sort(key=lambda x: -(x['jl'] + x['jt']))

    mini_j = sum(c['j'].get('mini', 0) for c in cur.values())
    mini_retail = sum(c['j'].get('mini', 0) for b, c in cur.items() if _is_retail(b))

    def auction_top(prod, n=4):
        a = sorted(((c['a'].get(prod, 0), _short(b)) for b, c in cur.items()), reverse=True)
        return [(name, v) for v, name in a[:n] if v > 0]

    return {'date': today, 'n_base': len(past), 'table': table,
            'mini_j': mini_j, 'mini_retail': mini_retail,
            'auction': {'large': auction_top('large'), 'topix': auction_top('topix')}}


def _fmt(n):
    return format(int(round(n)), ',')


def _ratio_html(r):
    if r is None:
        return '<span class="fb-r fb-r-na">普段ほぼ無し</span>'
    cls = 'fb-r-hi' if r >= 2 else 'fb-r-lo' if r <= 0.5 else 'fb-r-mid'
    return '<span class="fb-r %s">%.1f倍</span>' % (cls, r)


def _cell(v, r):
    if not v:
        return '<td class="fb-n fb-zero">—</td>'
    return '<td class="fb-n">%s<br>%s</td>' % (_fmt(v), _ratio_html(r))


def detail_html(fb):
    d = build(fb)
    if not d:
        return '<div class="insight">先物の参加者別データなし</div>'
    h = ('<div class="fb-head">J-NET（立会外の相対取引）は機関投資家がまとまった枚数をやり取りする場で、'
         '大口の動きが最も表れやすい取引です。各社の枚数を、その社の<b>過去%d日の平均</b>と比べています。</div>'
         % d['n_base'])
    h += ('<table class="fb-tbl"><thead><tr><th>参加者</th><th>ラージ<br><span>普段比</span></th>'
          '<th>TOPIX<br><span>普段比</span></th></tr></thead><tbody>')
    for x in d['table']:
        h += ('<tr><td><span class="fb-name">%s</span><span class="fb-cat fb-%s">%s</span></td>%s%s</tr>'
              % (x['name'], x['cat'], CAT_LABEL.get(x['cat'], ''), _cell(x['jl'], x['rl']), _cell(x['jt'], x['rt'])))
    h += '</tbody></table>'
    hi = [x for x in d['table'] if (x['rl'] or 0) >= 2 or (x['rt'] or 0) >= 2]
    if hi:
        h += ('<div class="fb-flag">普段の2倍以上：%s</div>'
              % '、'.join('%s（%s）' % (x['name'], 'ラージ' if (x['rl'] or 0) >= (x['rt'] or 0) else 'TOPIX') for x in hi))
    if d['mini_j']:
        h += ('<div class="fb-sub">mini</div><div class="fb-line">miniのJ-NET %s枚のうち<b>%d%%</b>は個人向け証券（SBI・楽天など）経由。'
              '大口の動きを見るにはラージとTOPIXが中心になります。</div>'
              % (_fmt(d['mini_j']), round(d['mini_retail'] / d['mini_j'] * 100)))
    h += '<div class="fb-sub">参考：立会（板）の取引高上位</div>'
    for prod, label in (('large', 'ラージ'), ('topix', 'TOPIX')):
        items = d['auction'][prod]
        if items:
            h += '<div class="fb-line">%s：%s</div>' % (label, '、'.join('%s %s' % (n, _fmt(v)) for n, v in items))
    h += ('<div class="fb-note">立会の上位は、高頻度取引の清算を担う会社（ABN・ソシエテ・バークレイズなど）が毎日並ぶため、'
          '大口の意図は読み取りにくい。手口には売り買いの区別がないため、枚数から方向は判断できません。'
          '方向は先物カードの判定（価格×建玉）や週次の建玉残高と合わせて見てください。'
          '手口は各銘柄の上位20社までの集計で、日中・夜間の合計。</div>')
    return h


def detail_js(fb):
    html = detail_html(fb)
    return "return '%s';" % html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '')


def preview(fb):
    d = build(fb)
    if not d or not d['table']:
        return '<span class="mm-label">データなし</span>'
    top = max(d['table'], key=lambda x: x['jl'])
    hi = [x for x in d['table'] if (x['rl'] or 0) >= 2 or (x['rt'] or 0) >= 2]
    r = (' <span class="fb-r %s">%.1f倍</span>' % ('fb-r-hi' if top['rl'] >= 2 else 'fb-r-mid', top['rl'])) if top['rl'] else ''
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">ラージJ-NET最大</div>'
            '<div class="mm-value" style="font-size:14px">%s %s%s</div></div>'
            '<div class="mini-metric"><div class="mm-label">普段の2倍以上</div>'
            '<div class="mm-value" style="font-size:14px">%s</div></div></div>'
            % (top['name'], _fmt(top['jl']), r, ('%d社' % len(hi)) if hi else 'なし'))


FB_CARD_CSS = r"""
.fb-head{font-size:13px;color:var(--sub);line-height:1.7;margin:0 2px 10px}
.fb-tbl{width:100%;border-collapse:collapse;margin:0 0 8px}
.fb-tbl th{font-size:12px;color:var(--sub);font-weight:500;text-align:right;padding:6px;border-bottom:1px solid var(--border);line-height:1.3}
.fb-tbl th span{font-size:10px}
.fb-tbl th:first-child{text-align:left}
.fb-tbl td{padding:8px 6px;border-bottom:1px solid rgba(38,44,58,.5);vertical-align:top}
.fb-n{text-align:right;font-family:'DM Mono',monospace;color:var(--text);line-height:1.5}
.fb-zero{color:var(--sub)}
.fb-name{color:var(--text);margin-right:6px}
.fb-cat{font-size:11px;padding:1px 6px;border-radius:4px;white-space:nowrap}
.fb-us{color:#93c5fd;background:rgba(147,197,253,.12)}
.fb-eu{color:#c4b5fd;background:rgba(196,181,253,.12)}
.fb-hf{color:#fbbf24;background:rgba(251,191,36,.12)}
.fb-domestic{color:#fca5a5;background:rgba(248,113,113,.12)}
.fb-other{color:var(--sub);background:rgba(255,255,255,.05)}
.fb-r{font-size:12px;font-family:'Noto Sans JP',sans-serif}
.fb-r-hi{color:#fbbf24;font-weight:700}
.fb-r-mid{color:var(--sub)}
.fb-r-lo{color:#5b647a}
.fb-r-na{color:#5b647a;font-size:11px}
.fb-flag{font-size:13px;color:#fbbf24;margin:4px 2px 2px}
.fb-sub{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:14px 2px 4px}
.fb-line{font-size:13px;color:var(--text);line-height:1.7;margin:0 2px}
.fb-note{font-size:11px;color:var(--sub);line-height:1.6;margin:12px 2px 2px}
"""
