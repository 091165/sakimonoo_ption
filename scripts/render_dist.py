#!/usr/bin/env python3
"""Card: OP建玉分布 — put and call open interest per strike, one expiry at a time.

The old card put six columns (P増減, P建玉, bar, 行使価格, bar, C建玉, C増減) for
three expiries at once; at phone width the headers broke, bars ran over the
strike labels and numbers collided. This version shows one expiry per tab and
three columns: puts | strike | calls, with the day's change under each OI
figure only when it moved, and a line where the index actually closed.

The walls are taken from the out-of-the-money side only: a put wall is the
largest put OI below the index, a call wall the largest call OI above it.
The old summary picked the largest call OI anywhere, which named C60,000
(deep in the money, no resistance at all) as the call wall.
"""

import json


WALL_RANGE = 0.10  # walls further than this from the index are not in play


def walls(be, spot):
    """(strike, oi) of the largest OTM put below and OTM call above the index.

    Candidates come from the displayed rows and the expiry's top-5 lists, so a
    wall just outside the ±5,000 window (C69,000 on 10/30) is still found;
    strikes more than 10% away (P35,000) are ignored.
    """
    lo, hi = spot * (1 - WALL_RANGE), spot * (1 + WALL_RANGE)
    puts = {r['strike']: r.get('put_oi') or 0 for r in be.get('distribution') or []}
    calls = {r['strike']: r.get('call_oi') or 0 for r in be.get('distribution') or []}
    for t in be.get('top_puts') or []:
        puts.setdefault(t['strike'], t['oi'])
    for t in be.get('top_calls') or []:
        calls.setdefault(t['strike'], t['oi'])
    p = max(((k, v) for k, v in puts.items() if lo <= k < spot and v), key=lambda x: x[1], default=None)
    c = max(((k, v) for k, v in calls.items() if spot < k <= hi and v), key=lambda x: x[1], default=None)
    return p, c


def build(s06, spot, ind=None):
    if not s06 or not s06.get('by_expiry'):
        return None
    exps = []
    for be in s06['by_expiry'][:3]:
        dist = be.get('distribution') or []
        if not dist:
            continue
        p, c = walls(be, spot)
        exps.append({
            'label': be.get('label', '').replace('2026年', '').replace('2027年', '27年'),
            'rows': [{'k': r['strike'], 'p': r.get('put_oi') or 0, 'pc': r.get('put_change') or 0,
                      'c': r.get('call_oi') or 0, 'cc': r.get('call_change') or 0} for r in dist],
            'pw': p[0] if p else None, 'pwo': p[1] if p else None,
            'cw': c[0] if c else None, 'cwo': c[1] if c else None,
        })
    if not exps:
        return None
    ind = ind or {}
    return {'spot': spot, 'exps': exps, 'max_pain': s06.get('max_pain_front'),
            'reinforced': ind.get('walls_reinforced') or [], 'weakened': ind.get('walls_weakened') or []}


def dist_data_script(s06, spot, ind=None):
    d = build(s06, spot, ind)
    return ('window.DIST_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))) if d else ''


def preview(s06, spot):
    d = build(s06, spot)
    if not d:
        return None
    e = d['exps'][0]
    pw = ('P%s（%s）' % (format(e['pw'], ','), format(e['pwo'], ','))) if e['pw'] else '—'
    cw = ('C%s（%s）' % (format(e['cw'], ','), format(e['cwo'], ','))) if e['cw'] else '—'
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">下値の壁（%s）</div><div class="mm-value" style="color:var(--put);font-size:14px">%s</div></div>'
            '<div class="mini-metric"><div class="mm-label">上値の壁（%s）</div><div class="mm-value" style="color:var(--call);font-size:14px">%s</div></div>'
            '</div>' % (e['label'], pw, e['label'], cw))


DIST_CARD_CSS = r"""
.ds-tabs{display:flex;gap:6px;margin:0 0 10px}
.ds-tab{flex:1;text-align:center;padding:6px 0;border:1px solid var(--border);border-radius:7px;color:var(--sub);font-size:13px;cursor:pointer}
.ds-tab.on{border-color:var(--accent);color:var(--text);background:rgba(129,140,248,.14)}
.ds-hd,.ds-row{display:grid;grid-template-columns:1fr 66px 1fr;align-items:center;column-gap:6px}
.ds-hd{font-size:12px;color:var(--sub);padding:0 0 6px;border-bottom:1px solid var(--border)}
.ds-hd .l{text-align:left;color:#fca5a5}.ds-hd .r{text-align:right;color:#93c5fd}.ds-hd .m{text-align:center}
.ds-row{padding:4px 0;border-bottom:1px solid rgba(38,44,58,.45)}
.ds-side{display:flex;align-items:center;gap:6px;min-width:0}
.ds-side.p{flex-direction:row}.ds-side.c{flex-direction:row-reverse}
.ds-num{flex:none;width:58px;font-family:'DM Mono',monospace;font-size:13px;line-height:1.25;color:var(--text)}
.ds-side.p .ds-num{text-align:left}.ds-side.c .ds-num{text-align:right}
.ds-num i{display:block;font-style:normal;font-size:11px}
.ds-up{color:#86efac}.ds-dn{color:#fca5a5}
.ds-track{flex:1;height:12px;display:flex;min-width:0}
.ds-side.p .ds-track{justify-content:flex-end}
.ds-bar{height:100%;border-radius:3px;min-width:1px}
.ds-side.p .ds-bar{background:linear-gradient(270deg,#f87171,rgba(248,113,113,.55))}
.ds-side.c .ds-bar{background:linear-gradient(90deg,#60a5fa,rgba(96,165,250,.55))}
.ds-k{text-align:center;font-family:'DM Mono',monospace;font-size:13px;font-weight:600;color:var(--text)}
.ds-wall{outline:1px solid rgba(251,191,36,.55);border-radius:6px;background:rgba(251,191,36,.06)}
.ds-wl{display:block;font-size:10px;color:#fbbf24;font-weight:500}
.ds-spot{display:flex;align-items:center;gap:8px;margin:2px 0;color:#fbbf24;font-size:12px}
.ds-spot:before,.ds-spot:after{content:'';flex:1;border-top:1px dashed rgba(251,191,36,.6)}
.ds-out{font-size:13px;color:#fbbf24;margin:8px 2px 0}
.ds-foot{font-size:13px;color:var(--text);line-height:1.7;margin:12px 2px 0}
.ds-note{font-size:11px;color:var(--sub);line-height:1.6;margin:8px 2px 0}
"""

DIST_CARD_JS = r"""
function dsN(n){return Math.round(n).toLocaleString();}
function dsChg(v){return v?('<i class="'+(v>0?'ds-up':'ds-dn')+'">'+(v>0?'+':'')+dsN(v)+'</i>'):'';}
function dsTable(i){
  var D=window.DIST_DATA,e=D.exps[i],mx=1;
  for(var j=0;j<e.rows.length;j++){mx=Math.max(mx,e.rows[j].p,e.rows[j].c);}
  var h='<div class="ds-hd"><span class="l">プット建玉</span><span class="m">行使価格</span><span class="r">コール建玉</span></div>';
  var spotDone=false;
  for(var j=e.rows.length-1;j>=0;j--){var r=e.rows[j];
    if(!spotDone&&r.k<D.spot){h+='<div class="ds-spot">現値 '+dsN(D.spot)+'</div>';spotDone=true;}
    var w=(r.k===e.pw||r.k===e.cw);
    h+='<div class="ds-row'+(w?' ds-wall':'')+'">'
      +'<div class="ds-side p"><span class="ds-num">'+dsN(r.p)+dsChg(r.pc)+'</span><span class="ds-track"><span class="ds-bar" style="width:'+(r.p/mx*100).toFixed(1)+'%"></span></span></div>'
      +'<div class="ds-k">'+dsN(r.k)+(r.k===e.pw?'<span class="ds-wl">下値の壁</span>':'')+(r.k===e.cw?'<span class="ds-wl">上値の壁</span>':'')+'</div>'
      +'<div class="ds-side c"><span class="ds-num">'+dsN(r.c)+dsChg(r.cc)+'</span><span class="ds-track"><span class="ds-bar" style="width:'+(r.c/mx*100).toFixed(1)+'%"></span></span></div>'
      +'</div>';}
  var ks=e.rows.map(function(r){return r.k;}),out=[];
  if(e.cw&&ks.indexOf(e.cw)<0)out.push('上値の壁 C'+dsN(e.cw)+'（'+dsN(e.cwo)+'）');
  if(e.pw&&ks.indexOf(e.pw)<0)out.push('下値の壁 P'+dsN(e.pw)+'（'+dsN(e.pwo)+'）');
  if(out.length)h+='<div class="ds-out">表の範囲外：'+out.join('、')+'</div>';
  return h;
}
function dsTab(el,i){
  var box=el.closest('.ds-wrap'),tabs=box.querySelectorAll('.ds-tab');
  for(var j=0;j<tabs.length;j++)tabs[j].classList.toggle('on',j===i);
  box.querySelector('.ds-body').innerHTML=dsTable(i);
}
function dsBuild(){
  var D=window.DIST_DATA;if(!D)return '<div class="insight">データなし</div>';
  var h='<div class="ds-wrap"><div class="ds-tabs">';
  for(var i=0;i<D.exps.length;i++)h+='<div class="ds-tab'+(i?'':' on')+'" onclick="event.stopPropagation();dsTab(this,'+i+')">'+D.exps[i].label+'</div>';
  h+='</div><div class="ds-body">'+dsTable(0)+'</div>';
  var f=[];
  if(D.max_pain)f.push('Max Pain（11月限）：<b>'+dsN(D.max_pain)+'</b>（現値の'+(D.max_pain>=D.spot?'+':'')+dsN(D.max_pain-D.spot)+'）');
  for(var i=0;i<D.reinforced.length;i++){var w=D.reinforced[i];f.push('壁の補強：'+w.type+dsN(w.strike)+' +'+dsN(w.change)+'（'+dsN(w.oi)+'）');}
  for(var i=0;i<D.weakened.length;i++){var w=D.weakened[i];f.push('壁の後退：'+w.type+dsN(w.strike)+' '+dsN(w.change)+'（'+dsN(w.oi)+'）');}
  if(f.length)h+='<div class="ds-foot">'+f.join('<br>')+'</div>';
  h+='<div class="ds-note">数字の下の小さな値は前日比。壁は、現値から±10%以内で、現値より下のプット・上のコールのうち建玉が最大の行使価格（現値の反対側にある建玉は壁として働かないため除外）。壁の補強・後退は全限月合計の変化。</div></div>';
  return h;
}
"""
