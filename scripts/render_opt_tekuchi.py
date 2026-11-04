#!/usr/bin/env python3
"""Card: オプションの手口（行使価格×日付） — volume per strike and day, for the
whole market, for the participants listed in 手口, for the 13 foreign firms,
or for one firm, next to that firm's weekly net OI.

Data: data/opt_tekuchi.json (extract_opt_tekuchi.py) and data/opt_weekly.json.
Every 手口 figure is volume with no buy/sell side; the only net figure is the
weekly OI column (前週末建玉), which comes from the weekly participant report.
"""

import json

DAYS = 10
# The 13 foreign firms of the "外資13社" tables (matched by name fragment).
# Checked against the 11/4 tables: Susquehanna and Interactive are not in it.
FOREIGN13 = ['ゴールドマン', 'ＪＰモルガン', 'モルガンＭＵＦＧ', 'シティ', 'ビーオブエー',
             'ＵＢＳ', 'ソシエテ', 'バークレイズ', 'ドイツ', 'ＢＮＰ', 'ＡＢＮ', 'ＨＳＢＣ', 'ナティクシス']


def _weekly_net(optw):
    """{'P62000': {broker: net}} from the weekly participant OI (front month)."""
    out = {}
    for k, sd in ((optw or {}).get('strikes') or {}).items():
        for side, s in (('put', 'P'), ('call', 'C')):
            d = sd.get(side) or {}
            net = {}
            for b, q, _ in d.get('buyers') or []:
                net[b] = net.get(b, 0) + q
            for b, q, _ in d.get('sellers') or []:
                net[b] = net.get(b, 0) - q
            net = {b: int(v) for b, v in net.items() if v}
            if net:
                out['%s%s' % (s, k)] = net
    return out


def build(store, optw=None):
    if not store or not store.get('dates'):
        return None
    dates = store['dates'][-DAYS:]
    days = {d: store['days'][d] for d in dates}
    tot = {}
    for d in dates:
        for by in days[d]['tk'].values():
            for b, v in by.items():
                tot[b] = tot.get(b, 0) + sum(v)
    exps = sorted({k[1:5] for d in dates for k in list(days[d]['vol']) + list(days[d]['tk'])})
    tk_exps = sorted({k[1:5] for d in dates for k in days[d]['tk']})
    return {
        'dates': dates, 'days': days,
        'brokers': sorted(tot, key=lambda b: -tot[b]),
        'f13': FOREIGN13,
        'exps': exps, 'exp0': (tk_exps or exps or [None])[0],
        'weekly': _weekly_net(optw), 'weekly_date': (optw or {}).get('date'),
        'weekly_as_of': (optw or {}).get('as_of'),
    }


def data_script(store, optw=None):
    d = build(store, optw)
    return ('window.TK_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))) if d else ''


def _is_f13(b):
    return any(k in b for k in FOREIGN13)


def preview(store):
    d = build(store)
    if not d:
        return None
    day = d['days'][d['dates'][-1]]
    exp = d['exp0']
    mk = sorted(((k, v) for k, v in day['vol'].items() if k[1:5] == exp), key=lambda x: -x[1])[:2]
    f13 = {}
    for k, by in day['tk'].items():
        if k[1:5] == exp:
            f13[k] = sum(sum(v) for b, v in by.items() if _is_f13(b))
    fk = sorted(((k, v) for k, v in f13.items() if v), key=lambda x: -x[1])[:2]
    fmt = lambda xs: '<br>'.join('<span style="color:%s">%s</span> %s' % (
        'var(--put)' if k[0] == 'P' else 'var(--call)', k[0] + format(int(k.split('-')[1]), ','), format(v, ','))
        for k, v in xs) or '—'
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">取引高（市場全体）</div>'
            '<div class="mm-value" style="font-size:13px">%s</div></div>'
            '<div class="mini-metric"><div class="mm-label">外資13社の手口</div>'
            '<div class="mm-value" style="font-size:13px">%s</div></div></div>' % (fmt(mk), fmt(fk)))


TK_CARD_CSS = r"""
.tk-def{font-size:12px;color:var(--sub);line-height:1.7;margin:0 2px 8px}
.tk-ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 8px}
.tk-ctl select{background:#141822;color:var(--text);border:1px solid var(--border);border-radius:8px;padding:5px 8px;font-size:13px;max-width:100%}
.tk-tabs{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.tk-tabs button{background:transparent;color:var(--sub);border:0;padding:5px 12px;font-size:13px;cursor:pointer}
.tk-tabs button.on{background:rgba(255,255,255,.10);color:var(--text);font-weight:600}
.tk-chk{font-size:12px;color:var(--sub);display:inline-flex;align-items:center;gap:4px}
.tk-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:8px}
.tk-t{border-collapse:collapse;font-size:12px;font-family:'DM Mono',monospace;min-width:100%}
.tk-t th{position:sticky;top:0;background:#1a1f2b;color:var(--sub);font-weight:500;padding:5px 6px;white-space:nowrap;border-bottom:1px solid var(--border)}
.tk-t td{padding:4px 6px;text-align:right;white-space:nowrap;border-bottom:1px solid rgba(38,44,58,.5)}
.tk-t td.k,.tk-t th.k{position:sticky;left:0;background:#1a1f2b;text-align:center;font-weight:600;color:var(--text);z-index:1}
.tk-t td.wk{border-left:1px solid var(--border);font-weight:600}
.tk-t td.net{border-left:1px solid var(--border)}
.tk-t tr.atm td.k{color:#fbbf24}
.tk-pos{color:#86efac}.tk-neg{color:#fca5a5}
.tk-note{font-size:11px;color:var(--sub);line-height:1.6;margin:8px 2px 0}
"""

TK_CARD_JS = r"""
var TK_MODE='f13',TK_SIDE='P',TK_JN=true,TK_EXP=null;
function tkD(d){return (+d.slice(4,6))+'/'+(+d.slice(6));}
function tkN(n){return n?Math.round(n).toLocaleString():'';}
function tkIsF13(b){return window.TK_DATA.f13.some(function(k){return b.indexOf(k)>=0;});}
function tkVal(day,key){
  if(TK_MODE==='mkt') return day.vol[key]||0;
  var by=day.tk[key];if(!by) return 0;
  var s=0;
  Object.keys(by).forEach(function(b){
    if(TK_MODE==='f13'&&!tkIsF13(b)) return;
    if(TK_MODE!=='f13'&&TK_MODE!=='sum'&&b!==TK_MODE) return;
    var v=by[b];s+=v[0]+v[1]+(TK_JN?v[2]+v[3]:0);
  });
  return s;
}
// weekly net OI for the selected group, or null when it does not apply
function tkNet(k){
  var D=window.TK_DATA;
  if(TK_MODE==='mkt'||TK_MODE==='sum'||!D.weekly_date||TK_EXP!==D.exp0) return null;
  var w=D.weekly[TK_SIDE+k];if(!w) return 0;
  var s=0;Object.keys(w).forEach(function(b){if(TK_MODE==='f13'?tkIsF13(b):b===TK_MODE) s+=w[b];});
  return s;
}
function tkWeek(dates){
  // dates of the latest day's week (Mon-Fri)
  var last=dates[dates.length-1],t=new Date(+last.slice(0,4),+last.slice(4,6)-1,+last.slice(6));
  var mon=new Date(t);mon.setDate(t.getDate()-((t.getDay()+6)%7));
  return dates.filter(function(d){var x=new Date(+d.slice(0,4),+d.slice(4,6)-1,+d.slice(6));return x>=mon&&x<=t;});
}
function tkSet(k,v){window[k]=v;var el=document.getElementById('tk-root');if(el)el.innerHTML=tkInner();}
function tkInner(){
  var D=window.TK_DATA;if(!TK_EXP) TK_EXP=D.exp0;
  var dates=D.dates,wk=tkWeek(dates),pre=TK_SIDE+TK_EXP+'-';
  var ks={};
  dates.forEach(function(d){var day=D.days[d];
    Object.keys(TK_MODE==='mkt'?day.vol:day.tk).forEach(function(key){if(key.indexOf(pre)===0&&tkVal(day,key))ks[+key.slice(pre.length)]=1;});});
  var showNet=tkNet(0)!==null;
  if(showNet) Object.keys(D.weekly).forEach(function(x){if(x[0]===TK_SIDE&&tkNet(+x.slice(1)))ks[+x.slice(1)]=1;});
  var strikes=Object.keys(ks).map(Number).sort(function(a,b){return b-a;});
  var mx=1;strikes.forEach(function(k){dates.forEach(function(d){mx=Math.max(mx,tkVal(D.days[d],pre+k));});});
  var rgb=TK_SIDE==='P'?'248,113,113':'96,165,250';
  var o='<div class="tk-def">行使価格ごとの取引高を日付ごとに並べた表です。<b>買いか売りかの区別はありません</b>（手口は取引高だけ）。'
    +'向きが分かるのは右端の「前週末建玉」（週次の参加者別建玉：買い越しが＋、売り越しが−）だけです。</div>';
  var opts=[['mkt','市場全体の取引高'],['sum','手口の合計（全社）'],['f13','外資13社']];
  o+='<div class="tk-ctl"><select onchange="tkSet(\'TK_MODE\',this.value)">'
    +opts.map(function(x){return '<option value="'+x[0]+'"'+(x[0]===TK_MODE?' selected':'')+'>'+x[1]+'</option>';}).join('')
    +'<optgroup label="会社別">'+D.brokers.map(function(b){return '<option value="'+b+'"'+(b===TK_MODE?' selected':'')+'>'+b+'</option>';}).join('')+'</optgroup></select>'
    +'<span class="tk-tabs">'+[['P','PUT'],['C','CALL']].map(function(x){return '<button type="button" class="'+(x[0]===TK_SIDE?'on':'')+'" onclick="tkSet(\'TK_SIDE\',\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</span>'
    +(D.exps.length>1?'<select onchange="tkSet(\'TK_EXP\',this.value)">'+D.exps.map(function(e){return '<option value="'+e+'"'+(e===TK_EXP?' selected':'')+'>20'+e.slice(0,2)+'年'+(+e.slice(2))+'月限</option>';}).join('')+'</select>':'')
    +(TK_MODE!=='mkt'?'<label class="tk-chk"><input type="checkbox"'+(TK_JN?' checked':'')+' onchange="tkSet(\'TK_JN\',this.checked)">J-NETを含む</label>':'')
    +'</div>';
  if(!strikes.length) return o+'<div class="insight">この条件の取引はありません。</div>';
  o+='<div class="tk-wrap"><table class="tk-t"><thead><tr><th class="k">行使価格</th>'
    +dates.map(function(d){return '<th>'+tkD(d)+'</th>';}).join('')+'<th>週合計</th>'
    +(showNet?'<th>前週末建玉</th>':'')+'</tr></thead><tbody>';
  strikes.forEach(function(k){
    var w=0;
    o+='<tr><td class="k">'+k.toLocaleString()+'</td>';
    dates.forEach(function(d){
      var v=tkVal(D.days[d],pre+k);if(wk.indexOf(d)>=0)w+=v;
      var a=v?(0.12+0.68*Math.sqrt(v/mx)).toFixed(2):0;
      o+='<td'+(v?' style="background:rgba('+rgb+','+a+')"':'')+'>'+tkN(v)+'</td>';
    });
    o+='<td class="wk">'+tkN(w)+'</td>';
    if(showNet){var n=tkNet(k);o+='<td class="net '+(n>0?'tk-pos':n<0?'tk-neg':'')+'">'+(n?(n>0?'+':'')+n.toLocaleString():'')+'</td>';}
    o+='</tr>';
  });
  o+='</tbody></table></div>';
  var notes=['市場全体の取引高は建玉ファイル（open_interest）から取っています。全部の行使価格が載ります。',
    '手口は、JPXが公表する一部の銘柄の、取引高の多い参加者だけです。手口に載らない行使価格や参加者は数字に入りません。',
    '手口では1枚の取引が買い手と売り手の両方に数えられるので、全社の合計は市場の取引高のおよそ2倍になります。',
    '「手口の合計（全社）」でJ-NETを外すと、SNSで出回っている行使価格別ヒートマップと同じ数字になります。外資13社と会社別は、J-NETを含めると同じになります。',
    '外資13社：'+D.f13.join('・')+'。サスケハナとインタラクティブは含めていません。',
    '週合計は'+tkD(wk[0])+'〜'+tkD(wk[wk.length-1])+'の合計です。'];
  if(D.weekly_date) notes.push('前週末建玉は'+(D.weekly_as_of||tkD(D.weekly_date))+'現在の週次データ（'+(+D.exp0.slice(2))+'月限）です。各行使価格の上位の参加者だけが載ります。');
  return o+'<div class="tk-note">'+notes.map(function(x){return '・'+x;}).join('<br>')+'</div>';
}
function tkBuild(){
  if(!window.TK_DATA) return '<div class="insight">データなし</div>';
  return '<div id="tk-root">'+tkInner()+'</div>';
}
"""
