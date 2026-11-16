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
    # JPX's OI file lists only the nearest few months, so a month appears some
    # weeks after the period starts: each month's view begins at its first day.
    start = {e: min((i for r in rows for i in range(len(dates)) if r[1][i] is not None or r[2][i] is not None),
                    default=0) for e, rows in out_exps.items()}
    return {'dates': dates, 'closes': closes, 'exps': sorted(out_exps), 'exp0': exp0, 'rows': out_exps, 'start': start}


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
.hm-date{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:2px 2px 4px}
.hm-date b{font-size:16px;font-family:'DM Mono',monospace;white-space:nowrap}
.hm-date .sub{font-size:12px;color:var(--sub);font-weight:500;white-space:nowrap}
.hm-playb{width:auto!important;padding:0 10px!important;font-size:12px!important}
.hm-date button,.hm-playb{background:transparent;border:1px solid var(--border);color:var(--text);border-radius:8px;width:36px;height:30px;font-size:14px;cursor:pointer;flex:none;padding:0}
.hm-range{display:block;width:100%;margin:2px 0 2px;accent-color:#d97706}
/* .card-detail scrolls sideways (overflow-x:auto), which would pin the dock to it instead of the page */
.card[data-card="oi_heatmap"] .card-detail{overflow:visible}
.hm-dock{position:sticky;bottom:0;z-index:5;background:var(--card);padding:6px 2px 4px;margin:4px -2px 0;border-top:1px solid var(--border)}
.hm-hint{font-size:11px;color:var(--sub);margin:0 2px 2px}
.hm-bars{touch-action:pan-y;user-select:none;-webkit-user-select:none;border:1px solid var(--border);border-radius:8px;padding:4px 0}
.hm-row{display:grid;grid-template-columns:1fr 58px 1fr;align-items:center;height:15px;cursor:pointer}
.hm-row:nth-child(even){background:rgba(127,127,127,.06)}
.hm-row.spot .hm-k{color:#1f1300!important;font-weight:700;background:#fbbf24;border-radius:4px}
.hm-row.sel{outline:1px solid var(--text);outline-offset:-1px}
.hm-k{text-align:center;font-size:10.5px;font-family:'DM Mono',monospace;color:var(--sub)}
.hm-side{position:relative;height:11px}
.hm-b{position:absolute;top:0;height:11px;border-radius:2px}
.hm-pl .hm-b{right:0}.hm-cl .hm-b{left:0}
.hm-b.dec{border:1px dashed currentColor;box-sizing:border-box}
.hm-dv{position:absolute;top:-1px;font-size:9.5px;font-family:'DM Mono',monospace;white-space:nowrap;color:var(--text)}
.hm-dv.in{color:#fff;font-weight:700}
.hm-axis{display:grid;grid-template-columns:1fr 58px 1fr;font-size:11px;color:var(--sub);margin:2px 0 2px;text-align:center}
"""

HM_CARD_JS = r"""
var HM_SIDE='P',HM_MODE='oi',HM_EXP=null,HM_SEL=null,HM_VIEW='bar',HM_DI=null,HM_PLAY=null;
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
function hmSet(k,v){if(HM_PLAY){clearInterval(HM_PLAY);HM_PLAY=null;}window[k]=v;if(k!=='HM_SEL')HM_SEL=null;var el=document.getElementById('hm-root');if(!el)return;
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
// ---- bar view: one day's distribution (P left / C right), date by slider or swipe
function hmBarRows(){
  var D=window.HM_DATA,n=D.dates.length;
  return D.rows[HM_EXP].filter(function(r){for(var i=0;i<n;i++){if(r[1][i]||r[2][i])return true;}return false;});
}
function hmBarScale(rows){
  var v=[];rows.forEach(function(r){r[1].concat(r[2]).forEach(function(x){if(x)v.push(x);});});
  v.sort(function(a,b){return a-b;});
  // 98th percentile, so one huge strike does not flatten all the others
  return Math.max(1,(v[Math.floor(v.length*0.98)]||v[v.length-1]||1)*1.05);
}
function hmSide(cls,v,w,mx,rgb){
  if(v===null) return '<div class="hm-side '+cls+'"></div>';
  var f=function(x){return Math.min(100,x/mx*100);};
  var put=cls==='hm-pl',far=put?'right':'left';
  var o='<div class="hm-side '+cls+'" style="color:rgb('+rgb+')">';
  var big=w!==null&&Math.abs(v-w)>=50;   // smaller moves are not drawn as change
  // decrease: dashed outline over the part that disappeared since yesterday
  if(big&&w>v) o+='<div class="hm-b dec" style="'+(put?'right':'left')+':'+f(v).toFixed(1)+'%;width:'+(f(w)-f(v)).toFixed(1)+'%"></div>';
  // today's size; when it grew, the new part is drawn darker
  if(v>0){
    var g='rgba('+rgb+',.45)';
    if(big&&v>w){var cut=(Math.min(w,v)/v*100).toFixed(1);
      g='linear-gradient(to '+(put?'left':'right')+',rgba('+rgb+',.45) 0,rgba('+rgb+',.45) '+cut+'%,rgb('+rgb+') '+cut+'%)';}
    o+='<div class="hm-b" style="width:'+f(v).toFixed(1)+'%;background:'+g+'"></div>';
  }
  var lab='';
  if(v>mx) lab=(v/1000).toFixed(1)+'k'+(w!==null&&v!==w?' '+hmS(v-w):'');
  else if(w!==null&&Math.abs(v-w)>=200) lab=hmS(v-w);
  if(lab){
    var e=Math.max(f(v),w!==null?f(w):0);
    if(e>70) o+='<span class="hm-dv in" style="'+far+':4px">'+lab+'</span>';
    else o+='<span class="hm-dv" style="'+far+':calc('+e.toFixed(1)+'% + 3px)">'+lab+'</span>';
  }
  return o+'</div>';
}
function hmBarHtml(){
  var D=window.HM_DATA,i=HM_DI,rows=hmBarRows(),mx=hmBarScale(rows),c=D.closes[i];
  window.HM_BROWS=rows;
  var sp=-1,bd=1e18;if(c)rows.forEach(function(r,ri){var x=Math.abs(r[0]-c);if(x<bd){bd=x;sp=ri;}});
  var o='<div class="hm-axis"><span style="color:rgb(220,80,80)">◀ プット</span><span>行使価格</span><span style="color:rgb(60,130,230)">コール ▶</span></div>';
  for(var ri=rows.length-1;ri>=0;ri--){
    var r=rows[ri],p=r[1][i],q=r[2][i],pw=i>0?r[1][i-1]:null,qw=i>0?r[2][i-1]:null;
    o+='<div class="hm-row'+(ri===sp?' spot':'')+(HM_SEL&&HM_SEL[0]===ri?' sel':'')+'" onclick="hmBarPick('+ri+')">'
      +hmSide('hm-pl',p,pw,mx,'220,80,80')+'<div class="hm-k">'+r[0].toLocaleString()+'</div>'+hmSide('hm-cl',q,qw,mx,'60,130,230')+'</div>';
  }
  return o;
}
function hmBarInfo(){
  var i=HM_DI;
  if(!HM_SEL) return '行をタップすると、その行使価格の数字を表示します。';
  var r=(window.HM_BROWS||[])[HM_SEL[0]];if(!r) return '';
  var f=function(s,a){var v=a[i],w=i>0?a[i-1]:null;if(v===null)return s+' —';return s+' '+v.toLocaleString()+(w!==null?'（'+hmS(v-w)+'）':'');};
  return r[0].toLocaleString()+'　'+f('P',r[1])+'　'+f('C',r[2]);
}
function hmBarPick(ri){HM_SEL=(HM_SEL&&HM_SEL[0]===ri)?null:[ri];hmBarDraw();}
function hmBarDraw(){
  var D=window.HM_DATA,i=HM_DI,c=D.closes[i],pc=i>0?D.closes[i-1]:null;
  var q=function(id){return document.getElementById(id);};
  if(!q('hm-bars')) return;
  q('hm-dl').innerHTML=hmD(D.dates[i])+(c?' <span class="sub">日経 '+c.toLocaleString()+(pc?'（'+hmS(c-pc)+'）':'')+'</span>':'');
  q('hm-bars').innerHTML=hmBarHtml();
  q('hm-info').innerHTML=hmBarInfo();
  var rg=q('hm-range');if(rg&&+rg.value!==i)rg.value=i;
}
function hmS0(){var D=window.HM_DATA;return (D.start&&D.start[HM_EXP])||0;}
function hmGo(i){var n=window.HM_DATA.dates.length;HM_DI=Math.max(hmS0(),Math.min(n-1,i));hmBarDraw();}
function hmPlay(){
  var b=document.getElementById('hm-play');
  if(HM_PLAY){clearInterval(HM_PLAY);HM_PLAY=null;if(b)b.textContent='再生';return;}
  var n=window.HM_DATA.dates.length;if(HM_DI>=n-1)HM_DI=hmS0();hmBarDraw();if(b)b.textContent='停止';
  HM_PLAY=setInterval(function(){if(HM_DI>=n-1){hmPlay();return;}hmGo(HM_DI+1);},700);
}
function hmSwipe(){
  setTimeout(function(){var el=document.getElementById('hm-bars');if(!el||el.dataset.sw)return;el.dataset.sw=1;
    var x0=null,y0=null;
    el.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;y0=e.touches[0].clientY;},{passive:true});
    el.addEventListener('touchend',function(e){if(x0===null)return;var t=e.changedTouches[0],dx=t.clientX-x0,dy=t.clientY-y0;x0=null;
      if(Math.abs(dx)>40&&Math.abs(dx)>Math.abs(dy)*1.5){hmGo(HM_DI+(dx<0?1:-1));}},{passive:true});
  },0);
}
function hmBarInner(){
  var D=window.HM_DATA,n=D.dates.length,s0=hmS0();if(HM_DI===null||HM_DI>=n)HM_DI=n-1;if(HM_DI<s0)HM_DI=s0;
  var o='<div class="hm-def">選んだ日の建玉の分布です（左がプット、右がコール）。<b>グラフを左右にスワイプ</b>するか、つまみを動かすと日付が変わります。'
    +'濃い色の部分は前日から<b>増えた</b>建玉、点線の枠は前日から<b>減った</b>分です。<b style="color:#92400e;background:rgba(251,191,36,.35);padding:0 3px;border-radius:3px">黄色</b>の行使価格はその日の終値に最も近いところです。</div>';
  o+='<div class="hm-info" id="hm-info"></div><div class="hm-bars" id="hm-bars"></div>';
  // date + Nikkei close and the slider, right under the chart; the block stays at the bottom of the screen while the chart scrolls
  o+='<div class="hm-dock"><div class="hm-date"><button type="button" onclick="hmGo(HM_DI-1)" aria-label="前の日">◀</button>'
    +'<div style="text-align:center;flex:1"><b id="hm-dl"></b></div>'
    +'<button type="button" onclick="hmGo(HM_DI+1)" aria-label="次の日">▶</button>'
    +'<button type="button" class="hm-playb" id="hm-play" onclick="hmPlay()" >再生</button></div>'
    +'<input type="range" class="hm-range" id="hm-range" min="'+s0+'" max="'+(n-1)+'" value="'+HM_DI+'" oninput="hmGo(+this.value)">'
    +'<div class="hm-hint">'+hmD(D.dates[s0])+' 〜 '+hmD(D.dates[n-1])+'（'+(n-s0)+'営業日）</div></div>';
  o+='<div class="hm-note">・棒の長さは期間を通した共通の目盛りです。とび抜けて大きい行使価格（例：P60,000）は棒を端で切り、建玉（k＝1,000枚）と前日比を数字で表示しています。<br>'
    +'・±200枚以上の増減は棒の先に数字を出しています。建玉の増減だけでは、買いか売りかは分かりません。<br>'
    +'・JPXの建玉ファイルには期近の3限月しか載らないため、限月によって始まりの日が違います。建玉ファイルが残っていない日は飛ばしていて、その翌日の増減は2日分以上の変化です。</div>';
  setTimeout(hmBarDraw,0);hmSwipe();
  return o;
}
function hmInner(){
  var D=window.HM_DATA;if(!HM_EXP||!D.rows[HM_EXP]) HM_EXP=D.exp0;
  var top='<div class="hm-ctl"><span class="hm-tabs">'+[['bar','棒グラフ（日付を動かす）'],['tbl','表（全日付）']].map(function(x){
      return '<button type="button" class="'+(x[0]===HM_VIEW?'on':'')+'" onclick="hmSet(\'HM_VIEW\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +(D.exps.length>1?'<select onchange="hmSet(\'HM_EXP\',this.value)">'+D.exps.map(function(e){
      return '<option value="'+e+'"'+(e===HM_EXP?' selected':'')+'>20'+e.slice(0,2)+'年'+(+e.slice(2))+'月限</option>';}).join('')+'</select>':'')+'</div>';
  if(HM_VIEW==='bar') return top+hmBarInner();
  var s0=(D.start&&D.start[HM_EXP])||0,dates=D.dates,n=dates.length;
  // only the strikes that have open interest on the selected side
  var all=D.rows[HM_EXP],rows=all.filter(function(r){for(var i=0;i<n;i++){var v=hmVal(r,i);if(v)return true;}return false;});
  window.HM_ROWS=rows;
  var mx=1;rows.forEach(function(r){for(var i=0;i<n;i++){var v=hmCell(r,i);if(v!==null)mx=Math.max(mx,Math.abs(v));}});
  var base=HM_SIDE==='P'?'248,113,113':HM_SIDE==='C'?'96,165,250':'167,139,250';
  // the strike nearest each day's close, to draw the price path
  var spot=dates.map(function(d,i){var c=D.closes[i];if(!c)return -1;var b=-1,bd=1e18;
    rows.forEach(function(r,ri){var x=Math.abs(r[0]-c);if(x<bd){bd=x;b=ri;}});return b;});
  var o=top+'<div class="hm-def">行使価格（縦）ごとの建玉を日付（横）に並べました。色が濃いほど建玉が多い（前日比では増減が大きい）行使価格です。'
    +'<b style="color:#fbbf24">黄色の枠</b>はその日の日経平均終値に最も近い行使価格で、値動きの通り道を示します。</div>';
  o+='<div class="hm-ctl"><span class="hm-tabs">'+[['P','プット'],['C','コール'],['T','合計']].map(function(x){
      return '<button type="button" class="'+(x[0]===HM_SIDE?'on':'')+'" onclick="hmSet(\'HM_SIDE\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +'<span class="hm-tabs">'+[['oi','建玉残高'],['chg','前日比']].map(function(x){
      return '<button type="button" class="'+(x[0]===HM_MODE?'on':'')+'" onclick="hmSet(\'HM_MODE\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +'</div>';
  o+='<div class="hm-info">'+hmInfo()+'</div>';
  o+='<div class="hm-wrap"><table class="hm-t"><thead><tr><th class="k">行使価格</th>'
    +dates.map(function(d,i){return i<s0?'':'<th>'+hmD(d)+'</th>';}).join('')+'</tr>'
    +'<tr class="cl"><th class="k">日経</th>'+D.closes.map(function(c,i){return i<s0?'':'<th>'+(c?(c/1000).toFixed(1)+'k':'')+'</th>';}).join('')+'</tr></thead><tbody>';
  for(var ri=rows.length-1;ri>=0;ri--){
    var r=rows[ri];
    o+='<tr><td class="k">'+r[0].toLocaleString()+'</td>';
    for(var i=s0;i<n;i++){
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
  var notes=['建玉ファイル（open_interest）の'+(n-s0)+'営業日分です。1k＝1,000枚。JPXの建玉ファイルには期近の3限月しか載らないため、限月によって始まりの日が違います。',
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
