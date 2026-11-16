#!/usr/bin/env python3
"""Card: オプション建玉の推移（行使価格×日付） — a heatmap of option open
interest per strike (rows) and day (columns), with the Nikkei close marked in
each day's column.

Data: data/oi_timeseries.json, `_snapshots[date].options.per_strike[expiry]
[strike] = {put_oi, call_oi}` (extract_oi_timeseries.py keeps the last 20
days) and `_snapshots[date].nikkei` / top-level `nikkei` for the closes.

Views: プット / コール / 合計, 建玉残高 or 前日比, and the contract month.
"""

import json

MIN_OI = 300      # a strike is shown when its OI reached this on some day
RANGE = 0.12      # ... and it lies within ±12% of the period's closes


def _closes(oi_ts, dates):
    snaps = oi_ts.get('_snapshots') or {}
    top = dict(zip(oi_ts.get('dates') or [], oi_ts.get('nikkei') or []))
    out = []
    for d in dates:
        v = (snaps.get(d) or {}).get('nikkei')
        if not isinstance(v, (int, float)):
            v = top.get(d)
        out.append(round(v) if isinstance(v, (int, float)) and v > 0 else None)
    return out


def build(oi_ts):
    if not oi_ts or oi_ts.get('error'):
        return None
    snaps = oi_ts.get('_snapshots') or {}
    dates = [d for d in (oi_ts.get('dates') or sorted(snaps)) if d in snaps]
    if len(dates) < 2:
        return None
    closes = _closes(oi_ts, dates)
    cl = [c for c in closes if c]
    lo, hi = (min(cl) * (1 - RANGE), max(cl) * (1 + RANGE)) if cl else (0, 1e9)

    exps = {}
    for d in dates:
        ps = ((snaps[d].get('options') or {}).get('per_strike') or {})
        for e, by in ps.items():
            exps.setdefault(e, {})
            for k, v in by.items():
                exps[e].setdefault(int(float(k)), {})[d] = (int(v.get('put_oi') or 0), int(v.get('call_oi') or 0))

    out_exps = {}
    for e, by in exps.items():
        strikes = sorted(k for k, days in by.items()
                         if lo <= k <= hi and max(max(p, c) for p, c in days.values()) >= MIN_OI)
        if not strikes:
            continue
        # [strike, [put per date], [call per date]]; None = no data that day
        rows = [[k, [by[k].get(d, (None, None))[0] for d in dates],
                 [by[k].get(d, (None, None))[1] for d in dates]] for k in strikes]
        out_exps[e] = rows
    if not out_exps:
        return None
    last = dates[-1]
    lp = ((snaps[last].get('options') or {}).get('per_strike') or {})
    tot = lambda e: sum((v.get('put_oi') or 0) + (v.get('call_oi') or 0) for v in (lp.get(e) or {}).values())
    exp0 = (oi_ts.get('options') or {}).get('top_expiry')
    if exp0 not in out_exps or not tot(exp0):
        exp0 = max(out_exps, key=tot)
    return {'dates': dates, 'closes': closes, 'exps': sorted(out_exps), 'exp0': exp0, 'rows': out_exps}


def data_script(oi_ts):
    d = build(oi_ts)
    return ('window.HM_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))) if d else ''


def preview(oi_ts):
    d = build(oi_ts)
    if not d:
        return None
    rows = d['rows'][d['exp0']]
    best = []
    for k, p, c in rows:
        for side, s in (('P', p), ('C', c)):
            if s[-1] is not None and s[-2] is not None:
                best.append((s[-1] - s[-2], side, k))
    up = sorted(best, reverse=True)[:2]
    dn = sorted(best)[:1]
    fmt = lambda xs: '<br>'.join('<span style="color:%s">%s%s</span> %s%s' % (
        'var(--put)' if s == 'P' else 'var(--call)', s, format(k, ','), '+' if v > 0 else '', format(v, ','))
        for v, s, k in xs if v) or '—'
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">%s月限・増えた行使価格</div>'
            '<div class="mm-value" style="font-size:13px">%s</div></div>'
            '<div class="mini-metric"><div class="mm-label">減った行使価格</div>'
            '<div class="mm-value" style="font-size:13px">%s</div></div></div>'
            % (int(d['exp0'][2:]), fmt(up), fmt(dn)))


HM_CARD_CSS = r"""
.hm-def{font-size:12px;color:var(--sub);line-height:1.7;margin:0 2px 8px}
.hm-ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 8px}
.hm-ctl select{background:#141822;color:var(--text);border:1px solid var(--border);border-radius:8px;padding:5px 8px;font-size:13px;max-width:100%}
.hm-tabs{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.hm-tabs button{background:transparent;color:var(--sub);border:0;padding:5px 10px;font-size:13px;cursor:pointer}
.hm-tabs button.on{background:rgba(255,255,255,.10);color:var(--text);font-weight:600}
.hm-info{font-size:12px;color:var(--text);min-height:18px;margin:0 2px 6px;font-family:'DM Mono',monospace}
.hm-wrap{overflow:auto;max-height:520px;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:8px}
.hm-t{border-collapse:collapse;font-size:11px;font-family:'DM Mono',monospace;min-width:100%}
.hm-t th{position:sticky;top:0;background:#1a1f2b;color:var(--sub);font-weight:500;padding:4px 5px;white-space:nowrap;border-bottom:1px solid var(--border);z-index:2}
.hm-t td{padding:3px 5px;text-align:right;white-space:nowrap;cursor:pointer;border-bottom:1px solid rgba(38,44,58,.35);color:rgba(230,233,240,.85)}
.hm-t td.k,.hm-t th.k{position:sticky;left:0;background:#1a1f2b;text-align:center;font-weight:600;color:var(--text);z-index:1;cursor:default}
.hm-t th.k{z-index:3}
.hm-t td.spot{outline:2px solid #fbbf24;outline-offset:-2px}
.hm-t td.sel{outline:2px solid #fff;outline-offset:-2px}
.hm-t tr.cl th{top:22px;color:#fbbf24;font-weight:500}
.hm-key{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--sub);margin:8px 2px 0;flex-wrap:wrap}
.hm-key i{display:inline-block;width:14px;height:10px;border-radius:2px;vertical-align:middle;margin-right:3px}
.hm-note{font-size:11px;color:var(--sub);line-height:1.6;margin:8px 2px 0}
"""

HM_CARD_JS = r"""
var HM_SIDE='P',HM_MODE='oi',HM_EXP=null,HM_SEL=null;
function hmD(d){return (+d.slice(4,6))+'/'+(+d.slice(6));}
function hmS(n){return (n>0?'+':'')+n.toLocaleString();}
function hmVal(r,i){
  var p=r[1][i],c=r[2][i];
  if(p===null||c===null) return null;
  return HM_SIDE==='P'?p:HM_SIDE==='C'?c:p+c;
}
function hmCell(r,i){
  var v=hmVal(r,i);if(v===null) return null;
  if(HM_MODE==='oi') return v;
  if(i===0) return null;
  var w=hmVal(r,i-1);return w===null?null:v-w;
}
function hmSet(k,v){window[k]=v;if(k!=='HM_SEL')HM_SEL=null;var el=document.getElementById('hm-root');if(!el)return;
  var w=el.querySelector('.hm-wrap'),x=w?w.scrollLeft:0,y=w?w.scrollTop:0;el.innerHTML=hmInner();
  if(k==='HM_SEL'){var w2=el.querySelector('.hm-wrap');if(w2){w2.scrollLeft=x;w2.scrollTop=y;}}else hmScroll();}
// show the latest day and the strikes around its close
function hmScroll(){setTimeout(function(){var w=document.querySelector('#hm-root .hm-wrap');if(!w)return;
  w.scrollLeft=w.scrollWidth;var c=w.querySelectorAll('td.spot');c=c[c.length-1];
  if(c){var tr=c.parentNode;w.scrollTop=Math.max(0,tr.offsetTop-w.clientHeight/2);}},0);}
function hmPick(e,ri,i){HM_SEL=[ri,i];hmSet('HM_SEL',HM_SEL);}
function hmInfo(){
  var D=window.HM_DATA;if(!HM_SEL) return '行のセルをタップすると、その日の数字を表示します。';
  var r=(window.HM_ROWS||[])[HM_SEL[0]];if(!r) return '';var i=HM_SEL[1],d=D.dates[i];
  var f=function(s,a){var v=a[i],w=i>0?a[i-1]:null;if(v===null)return s+' —';return s+' '+v.toLocaleString()+(w!==null?'（'+hmS(v-w)+'）':'');};
  return hmD(d)+'　'+r[0].toLocaleString()+'　'+f('P',r[1])+'　'+f('C',r[2])+(D.closes[i]?'　日経 '+D.closes[i].toLocaleString():'');
}
function hmInner(){
  var D=window.HM_DATA;if(!HM_EXP||!D.rows[HM_EXP]) HM_EXP=D.exp0;
  var dates=D.dates,n=dates.length;
  // only the strikes that have open interest on the selected side
  var all=D.rows[HM_EXP],rows=all.filter(function(r){for(var i=0;i<n;i++){var v=hmVal(r,i);if(v)return true;}return false;});
  window.HM_ROWS=rows;
  var mx=1;rows.forEach(function(r){for(var i=0;i<n;i++){var v=hmCell(r,i);if(v!==null)mx=Math.max(mx,Math.abs(v));}});
  var base=HM_SIDE==='P'?'248,113,113':HM_SIDE==='C'?'96,165,250':'167,139,250';
  // the strike nearest each day's close, to draw the price path
  var spot=dates.map(function(d,i){var c=D.closes[i];if(!c)return -1;var b=-1,bd=1e18;
    rows.forEach(function(r,ri){var x=Math.abs(r[0]-c);if(x<bd){bd=x;b=ri;}});return b;});
  var o='<div class="hm-def">行使価格（縦）ごとの建玉を日付（横）に並べました。色が濃いほど建玉が多い（前日比では増減が大きい）行使価格です。'
    +'<b style="color:#fbbf24">黄色の枠</b>はその日の日経平均終値に最も近い行使価格で、値動きの通り道を示します。</div>';
  o+='<div class="hm-ctl"><span class="hm-tabs">'+[['P','プット'],['C','コール'],['T','合計']].map(function(x){
      return '<button type="button" class="'+(x[0]===HM_SIDE?'on':'')+'" onclick="hmSet(\'HM_SIDE\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +'<span class="hm-tabs">'+[['oi','建玉残高'],['chg','前日比']].map(function(x){
      return '<button type="button" class="'+(x[0]===HM_MODE?'on':'')+'" onclick="hmSet(\'HM_MODE\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +(D.exps.length>1?'<select onchange="hmSet(\'HM_EXP\',this.value)">'+D.exps.map(function(e){
      return '<option value="'+e+'"'+(e===HM_EXP?' selected':'')+'>20'+e.slice(0,2)+'年'+(+e.slice(2))+'月限</option>';}).join('')+'</select>':'')
    +'</div>';
  o+='<div class="hm-info">'+hmInfo()+'</div>';
  o+='<div class="hm-wrap"><table class="hm-t"><thead><tr><th class="k">行使価格</th>'
    +dates.map(function(d){return '<th>'+hmD(d)+'</th>';}).join('')+'</tr>'
    +'<tr class="cl"><th class="k">日経</th>'+D.closes.map(function(c){return '<th>'+(c?(c/1000).toFixed(1)+'k':'')+'</th>';}).join('')+'</tr></thead><tbody>';
  for(var ri=rows.length-1;ri>=0;ri--){
    var r=rows[ri];
    o+='<tr><td class="k">'+r[0].toLocaleString()+'</td>';
    for(var i=0;i<n;i++){
      var v=hmCell(r,i),cls=[],st='';
      if(spot[i]===ri) cls.push('spot');
      if(HM_SEL&&HM_SEL[0]===ri&&HM_SEL[1]===i) cls.push('sel');
      if(v){
        var a=(0.10+0.75*Math.sqrt(Math.abs(v)/mx)).toFixed(2);
        var rgb=HM_MODE==='oi'?base:(v>0?'248,113,113':'96,165,250');
        st=' style="background:rgba('+rgb+','+a+')"';
      }
      var txt=v===null?'':HM_MODE==='oi'?(v?(v>=1000?(v/1000).toFixed(1)+'k':v):''):(v?hmS(v):'');
      o+='<td'+(cls.length?' class="'+cls.join(' ')+'"':'')+st+' onclick="hmPick(event,'+ri+','+i+')">'+txt+'</td>';
    }
    o+='</tr>';
  }
  o+='</tbody></table></div>';
  if(HM_MODE==='chg') o+='<div class="hm-key"><span><i style="background:rgba(248,113,113,.8)"></i>増加（新規建て）</span><span><i style="background:rgba(96,165,250,.8)"></i>減少（手仕舞い・決済）</span><span><i style="outline:2px solid #fbbf24;outline-offset:-2px"></i>終値に最も近い行使価格</span></div>';
  var notes=['建玉ファイル（open_interest）の過去'+n+'営業日分です。1k＝1,000枚。',
    '表示するのは、期間中に建玉が'+(300).toLocaleString()+'枚以上になったことがあり、期間中の終値から±12%以内の行使価格です。',
    '建玉の増減だけでは、買いか売りかは分かりません。増加は新しい建玉ができたこと、減少は反対売買か権利行使で建玉が消えたことを示します。'];
  return o+'<div class="hm-note">'+notes.map(function(x){return '・'+x;}).join('<br>')+'</div>';
}
function hmBuild(){
  if(!window.HM_DATA) return '<div class="insight">データなし</div>';
  hmScroll();
  return '<div id="hm-root">'+hmInner()+'</div>';
}
"""
