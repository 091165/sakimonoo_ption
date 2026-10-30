#!/usr/bin/env python3
"""Card: 先物 — open interest read together with price and volume.

The old card showed only today's OI change per product. On its own that
number cannot say who acted, so each day is classified by the sign of the
price move (Nikkei 225 cash close) and of the OI change:

    price up   + OI up   -> 新規買い   (new longs; the rise has fuel)
    price up   + OI down -> 買い戻し   (short covering)
    price down + OI up   -> 新規売り   (new shorts)
    price down + OI down -> 手仕舞い   (long liquidation)

Days with a tiny move in either are marked 横ばい instead of being forced into
a quadrant. The 20-day bar chart colours each day's OI change by its class,
with the price line on top, so a run of 新規売り or 手仕舞い is visible at a
glance. Data comes from data/futures_flow.json (extract_futures_flow.py).
"""

import datetime
import json

PRODUCTS = (('nk225_large', 'ラージ'), ('nk225_mini', 'mini'), ('topix', 'TOPIX'))
# Below these the day is 横ばい: price moves under 0.15% or OI changes under
# 0.1% of open interest are within ordinary day-to-day noise.
PRICE_FLAT_PCT = 0.15
OI_FLAT_FRAC = 0.001

VERDICTS = {
    'buy': ('新規買い', '価格↑・建玉↑'),
    'cover': ('買い戻し', '価格↑・建玉↓'),
    'short': ('新規売り', '価格↓・建玉↑'),
    'liq': ('手仕舞い', '価格↓・建玉↓'),
    'flat': ('横ばい', '価格か建玉の変化が小さい'),
    'sq': ('SQ', '限月交代で建玉が入れ替わる日'),
}
# mini has a monthly contract; large and TOPIX roll only in the quarter months.
_SQ_MONTHS = {'nk225_mini': range(1, 13), 'nk225_large': (3, 6, 9, 12), 'topix': (3, 6, 9, 12)}


def is_sq_day(dt, key):
    """Second Friday of a contract month: OI there is expiry, not positioning."""
    d = datetime.date(int(dt[:4]), int(dt[4:6]), int(dt[6:8]))
    return d.weekday() == 4 and 8 <= d.day <= 14 and d.month in _SQ_MONTHS[key]


def classify(price_pct, chg, oi):
    if price_pct is None or chg is None or not oi:
        return None
    if abs(price_pct) < PRICE_FLAT_PCT or abs(chg) < oi * OI_FLAT_FRAC:
        return 'flat'
    if price_pct > 0:
        return 'buy' if chg > 0 else 'cover'
    return 'short' if chg > 0 else 'liq'


def build(flow, s02=None, n=20):
    if not flow or not flow.get('dates'):
        return None
    rows = flow['rows']
    # Only days with OI: the history also holds close-only days (kept for the
    # HV calculation), and the price move must span the same days as the OI
    # change it is paired with.
    dates = [dt for dt in flow['dates'] if any((rows[dt].get(k) or {}).get('oi') for k, _ in PRODUCTS)]
    dates = dates[-(n + 1):]
    out = {'dates': [], 'close': [], 'pct': [], 'products': {}, 'months': {}}
    for i, dt in enumerate(dates):
        if i == 0 and len(dates) > n:
            continue  # only used as the previous close for the first shown day
        prev = rows.get(dates[i - 1], {}).get('close') if i > 0 else None
        c = rows.get(dt, {}).get('close')
        out['dates'].append(dt)
        out['close'].append(c)
        out['pct'].append(round((c / prev - 1) * 100, 2) if (c and prev) else None)
    for key, _ in PRODUCTS:
        p = {'oi': [], 'chg': [], 'vol': [], 'v': []}
        for dt, pct in zip(out['dates'], out['pct']):
            cell = rows.get(dt, {}).get(key, {})
            p['oi'].append(cell.get('oi'))
            p['chg'].append(cell.get('chg'))
            p['vol'].append(cell.get('vol'))
            p['v'].append('sq' if is_sq_day(dt, key) else classify(pct, cell.get('chg'), cell.get('oi')))
        out['products'][key] = p
        months = ((s02 or {}).get(key) or {}).get('months') or []
        out['months'][key] = [m for m in months if m.get('oi')][:3]
    out['labels'] = {k: v[0] for k, v in VERDICTS.items()}
    out['hints'] = {k: v[1] for k, v in VERDICTS.items()}
    return out


def futures_data_script(flow, s02):
    d = build(flow, s02)
    if not d:
        return ''
    # Bare JS: injected inside the dashboard's single <script> block.
    return 'window.FUT_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))


def preview_futures(flow, s02):
    d = build(flow, s02)
    if not d:
        return None
    h = '<div class="mini-metrics">'
    for key, label in PRODUCTS:
        p = d['products'][key]
        chg = p['chg'][-1]
        v = p['v'][-1]
        color = 'var(--green)' if (chg or 0) > 0 else 'var(--red)' if (chg or 0) < 0 else 'var(--sub)'
        h += ('<div class="mini-metric"><div class="mm-label">%s</div>'
              '<div class="mm-value" style="color:%s">%s</div>'
              '<div class="ft-chip ft-%s" style="margin-top:3px">%s</div></div>'
              % (label, color, format(chg, '+,') if chg is not None else '—', v or 'none',
                 VERDICTS[v][0] if v else '—'))
    return h + '</div>'


def detail_futures_js(flow):
    if not flow:
        return None
    return "return ftBuild();"


FUT_CARD_CSS = r"""
.ft-chip{display:inline-block;padding:1px 7px;border-radius:5px;font-size:12px;font-weight:600;white-space:nowrap}
.ft-buy{color:#4ade80;background:rgba(74,222,128,.14)}
.ft-cover{color:#86efac;background:rgba(134,239,172,.10)}
.ft-short{color:#f87171;background:rgba(248,113,113,.14)}
.ft-liq{color:#fbbf24;background:rgba(251,191,36,.13)}
.ft-flat,.ft-none{color:var(--sub);background:rgba(255,255,255,.05)}
.ft-sq{color:#c4b5fd;background:rgba(196,181,253,.12)}
.ft-head{font-size:13px;color:var(--text);margin:0 2px 10px;line-height:1.7}
.ft-tbl{width:100%;border-collapse:collapse;margin:0 0 12px}
.ft-tbl th{font-size:11px;color:var(--sub);font-weight:500;text-align:right;padding:6px 6px;border-bottom:1px solid var(--border)}
.ft-tbl th:first-child,.ft-tbl td:first-child{text-align:left}
.ft-tbl td{padding:8px 6px;border-bottom:1px solid rgba(38,44,58,.5);text-align:right;font-family:'DM Mono',monospace;white-space:nowrap}
.ft-tbl td.ft-v{font-family:inherit}
.ft-tabs{display:flex;gap:6px;margin:4px 0 8px}
.ft-tab{flex:1;text-align:center;padding:6px 0;border:1px solid var(--border);border-radius:7px;color:var(--sub);font-size:12px;cursor:pointer}
.ft-tab.on{border-color:var(--accent);color:var(--text);background:rgba(129,140,248,.14)}
.ft-svg{width:100%;height:auto;display:block;border:1px solid var(--border);border-radius:9px;background:#0f1220}
.ft-legend{display:flex;flex-wrap:wrap;gap:6px 8px;margin:8px 2px 4px}
.ft-sub{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:14px 2px 6px}
.ft-note{font-size:11px;color:var(--sub);line-height:1.6;margin:10px 2px 2px}
"""

FUT_CARD_JS = r"""
var FT_NAMES={nk225_large:'ラージ',nk225_mini:'mini',topix:'TOPIX'};
var FT_COL={buy:'#4ade80',cover:'#86efac',short:'#f87171',liq:'#fbbf24',flat:'#5b647a',sq:'#8b7fc7'};
function ftN(n){return (n===null||n===undefined)?'—':Math.round(n).toLocaleString();}
function ftS(n){return (n===null||n===undefined)?'—':((n>0?'+':'')+Math.round(n).toLocaleString());}
function ftChip(v){var D=window.FUT_DATA;return '<span class="ft-chip ft-'+(v||'none')+'">'+(v?D.labels[v]:'—')+'</span>';}
function ftChart(key){
  var D=window.FUT_DATA,p=D.products[key],n=D.dates.length;
  var W=360,H=190,L=8,R=8,T=14,B=26,cw=(W-L-R)/n;
  var mx=1;for(var i=0;i<n;i++){if(p.chg[i]!==null&&p.v[i]!=='sq')mx=Math.max(mx,Math.abs(p.chg[i]));}
  var mid=T+(H-T-B)/2,half=(H-T-B)/2-2;
  var s='<svg class="ft-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">';
  s+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+mid+'" y2="'+mid+'" stroke="#2a3142"/>';
  for(var i=0;i<n;i++){
    var c=p.chg[i];if(c===null||c===undefined)continue;
    var h=Math.max(1,Math.min(1,Math.abs(c)/mx)*half),x=L+i*cw+cw*0.18,y=c>0?mid-h:mid;
    s+='<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+(cw*0.64).toFixed(1)+'" height="'+h.toFixed(1)+'" fill="'+(FT_COL[p.v[i]]||'#5b647a')+'" rx="1.5"/>';
    if(p.v[i]==='sq')s+='<text x="'+(x+cw*0.32).toFixed(1)+'" y="'+(c>0?y-3:y+h+10).toFixed(1)+'" text-anchor="middle" font-size="8" fill="#c4b5fd">SQ</text>';
  }
  var cl=D.close,lo=1e12,hi=0;for(var i=0;i<n;i++){if(cl[i]){lo=Math.min(lo,cl[i]);hi=Math.max(hi,cl[i]);}}
  if(hi>lo){var pts=[];for(var i=0;i<n;i++){if(!cl[i])continue;pts.push((L+i*cw+cw/2).toFixed(1)+','+(T+(1-(cl[i]-lo)/(hi-lo))*(H-T-B)).toFixed(1));}
    s+='<polyline points="'+pts.join(' ')+'" fill="none" stroke="#c7d2fe" stroke-width="1.6"/>';
    s+='<text x="'+(W-R)+'" y="11" text-anchor="end" font-size="9" fill="#8888aa">日経平均 '+ftN(lo)+'〜'+ftN(hi)+'</text>';}
  s+='<text x="'+L+'" y="11" font-size="9" fill="#8888aa">建玉の前日比（目盛り ±'+ftN(mx)+'、SQ日を除く）</text>';
  for(var i=0;i<n;i+=Math.ceil(n/5)){var d=D.dates[i];s+='<text x="'+(L+i*cw+cw/2).toFixed(1)+'" y="'+(H-8)+'" text-anchor="middle" font-size="9" fill="#8888aa">'+(+d.slice(4,6))+'/'+(+d.slice(6,8))+'</text>';}
  return s+'</svg>';
}
function ftTab(el,key){
  var box=el.closest('.ft-wrap');var tabs=box.querySelectorAll('.ft-tab');
  for(var i=0;i<tabs.length;i++)tabs[i].classList.toggle('on',tabs[i]===el);
  box.querySelector('.ft-chart').innerHTML=ftChart(key);
}
function ftBuild(){
  var D=window.FUT_DATA;if(!D)return '<div class="insight">先物データなし</div>';
  var n=D.dates.length,last=n-1,pct=D.pct[last],cl=D.close[last];
  var h='<div class="ft-wrap"><div class="ft-head">日経平均 <b>'+ftN(cl)+'</b>（'+(pct===null?'—':((pct>0?'+':'')+pct.toFixed(2)+'%'))+'）と建玉の増減から、誰が動いたかを推定します。</div>';
  h+='<table class="ft-tbl"><thead><tr><th>商品</th><th>建玉</th><th>前日比</th><th>取引高</th><th>判定</th></tr></thead><tbody>';
  for(var k in FT_NAMES){var p=D.products[k];
    h+='<tr><td>'+FT_NAMES[k]+'</td><td>'+ftN(p.oi[last])+'</td><td style="color:'+((p.chg[last]||0)>0?'var(--green)':(p.chg[last]||0)<0?'var(--red)':'var(--sub)')+'">'+ftS(p.chg[last])+'</td><td>'+ftN(p.vol[last])+'</td><td class="ft-v">'+ftChip(p.v[last])+'</td></tr>';}
  h+='</tbody></table>';
  h+='<div class="ft-sub">直近'+n+'日の建玉の増減（棒）と日経平均（線）</div>';
  h+='<div class="ft-tabs">';var first=true;
  for(var k in FT_NAMES){h+='<div class="ft-tab'+(first?' on':'')+'" onclick="event.stopPropagation();ftTab(this,\''+k+'\')">'+FT_NAMES[k]+'</div>';first=false;}
  h+='</div><div class="ft-chart">'+ftChart('nk225_large')+'</div>';
  h+='<div class="ft-legend">';
  var ord=['buy','cover','short','liq','flat','sq'];for(var i=0;i<ord.length;i++){h+='<span class="ft-chip ft-'+ord[i]+'">'+D.labels[ord[i]]+'（'+D.hints[ord[i]]+'）</span>';}
  h+='</div>';
  h+='<div class="ft-sub">限月別の建玉（主な限月）</div><table class="ft-tbl"><thead><tr><th>限月</th><th>建玉</th><th>前日比</th></tr></thead><tbody>';
  for(var k in FT_NAMES){var ms=D.months[k]||[];for(var i=0;i<ms.length;i++){var m=ms[i];
    h+='<tr><td>'+FT_NAMES[k]+' '+m.label.replace('年','/').replace('月限','')+'</td><td>'+ftN(m.oi)+'</td><td style="color:'+((m.change||0)>0?'var(--green)':(m.change||0)<0?'var(--red)':'var(--sub)')+'">'+ftS(m.change)+'</td></tr>';}}
  h+='</tbody></table>';
  h+='<div class="ft-note">判定は価格（日経平均の終値）と建玉の増減の組み合わせからの推定で、売買の向きを直接示すデータではありません。価格の変化が0.15%未満、または建玉の変化が0.1%未満の日は「横ばい」。SQ当日は建玉が限月交代で大きく入れ替わるため判定せず、棒の長さも上限で切っています。SQ前の乗り換え（ロール）の日も判定がずれることがあります。取引高は日中・夜間の合計。</div></div>';
  return h;
}
"""
