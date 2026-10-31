#!/usr/bin/env python3
"""Card: 検証 — after each kind of day, how often the index moved more than
options implied, and in which direction. Data: data/study.json
(extract_study.py). Conditions that apply to the latest day come first.
"""

import json

MIN_EVENTS = 6     # fewer large moves than this: show counts, no badge
P_FLAG = 0.10      # direction split this unlikely by luck gets a badge
LIFT_FLAG = 1.5    # large-move rate this many times the base rate gets a badge


def data_script(st):
    return ('window.STUDY_DATA = %s;\n' % json.dumps(st, ensure_ascii=False, separators=(',', ':'))) if st else ''


def preview(st):
    if not st:
        return None
    by = {c['key']: c for c in st['conds']}
    names = [by[k]['name'].split('（')[0] for k in st.get('applies_today') or [] if k in by]
    return ('<div class="mini-metrics"><div class="mini-metric"><div class="mm-label">今日あてはまる条件</div>'
            '<div class="mm-value" style="font-size:14px">%s</div></div></div>'
            % ('%d件：%s' % (len(names), '、'.join(names)) if names else 'なし'))


STUDY_CARD_CSS = r"""
.sd-def{font-size:13px;color:var(--sub);line-height:1.7;margin:0 2px 10px}
.sd-sec{font-family:Outfit;font-weight:600;color:var(--sub);font-size:13px;margin:14px 2px 6px}
.sd-c{border:1px solid var(--border);border-radius:10px;padding:9px 11px;margin:6px 0;background:#141822}
.sd-c.today{border-color:#fbbf24}
.sd-n{font-size:14px;color:var(--text);font-weight:600;margin-bottom:4px}
.sd-n span{font-size:12px;color:var(--sub);font-weight:400;margin-left:6px}
.sd-l{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;font-size:13px;color:var(--text);margin:2px 0}
.sd-h{min-width:44px;color:var(--sub)}
.sd-r{font-family:'DM Mono',monospace;font-weight:600}
.sd-b{color:var(--sub);font-size:12px}
.sd-up{color:#86efac}.sd-dn{color:#fca5a5}
.sd-tag{font-size:11px;padding:1px 7px;border-radius:6px;white-space:nowrap}
.sd-tag.up{background:rgba(74,222,128,.14);color:#86efac}
.sd-tag.dn{background:rgba(248,113,113,.14);color:#fca5a5}
.sd-tag.lift{background:rgba(251,191,36,.14);color:#fbbf24}
.sd-base{font-size:13px;color:var(--text);line-height:1.7;margin:0 2px}
.sd-bar{position:relative;display:flex;height:8px;background:rgba(255,255,255,.06);border-radius:4px;margin:2px 0 8px}
.sd-bar i{display:block;height:100%}
.sd-bar i.u{background:#4ade80;border-radius:4px 0 0 4px}
.sd-bar i.d{background:#f87171}
.sd-bar b{position:absolute;top:-3px;width:2px;height:14px;background:#fbbf24}
.sd-leg{font-size:12px;color:var(--sub);line-height:1.8;margin:0 2px 8px}
.sd-leg span{margin-right:10px;white-space:nowrap}
.sd-leg i{display:inline-block;width:12px;height:8px;border-radius:2px;vertical-align:middle;margin-right:4px}
.sd-leg i.u{background:#4ade80}.sd-leg i.d{background:#f87171}
.sd-leg b{display:inline-block;width:2px;height:12px;background:#fbbf24;vertical-align:middle;margin-right:4px}
.sd-tabs{display:flex;gap:6px;margin:10px 0 8px;flex-wrap:wrap}
.sd-tabs button{flex:1;min-width:60px;padding:7px 4px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--text);font-size:13px;font-weight:600;cursor:pointer}
.sd-tabs button.on{background:#fbbf24;border-color:#fbbf24;color:#0b0e14}
.sd-pts{border:1px solid #fbbf24;border-radius:10px;padding:9px 11px;margin:0 0 6px;font-size:13px;color:var(--text);line-height:1.7}
.sd-pts>div{margin:3px 0}
.sd-pts .sd-pts-h{font-weight:700;color:#fbbf24;margin:0 0 2px}
.sd-more{margin:10px 0 0}
.sd-more summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--sub);padding:8px 2px}
.sd-note{font-size:11px;color:var(--sub);line-height:1.6;margin:12px 2px 0}
"""

STUDY_CARD_JS = r"""
function sdD(d){return (+d.slice(4,6))+'/'+(+d.slice(6));}
function sdLine(D,c,h){
  var s=c.stats[h],b=D.base[h],ev=s.up+s.dn;
  if(!s.n) return '';
  var rate=ev/s.n,br=(b.up+b.dn)/b.n,bu=b.up/(b.up+b.dn),tags='';
  if(ev>=__MIN__&&rate>=br*__LIFT__) tags+='<span class="sd-tag lift">普段の'+(rate/br).toFixed(1)+'倍</span>';
  if(ev>=__MIN__&&s.p_dir!==null&&s.p_dir<__P__){var upish=s.up/ev>bu;tags+='<span class="sd-tag '+(upish?'up':'dn')+'">'+(upish?'上に偏り':'下に偏り')+'（p='+s.p_dir.toFixed(2)+'）</span>';}
  return '<div class="sd-l"><span class="sd-r">'+Math.round(rate*100)+'%</span>'
    +'<span class="sd-b">（'+s.n+'日中'+ev+'回、普段'+Math.round(br*100)+'%）</span>'
    +'<span class="sd-up">上昇'+s.up+'回</span><span class="sd-dn">下落'+s.dn+'回</span>'
    +(s.big?'<span class="sd-b">うち1.5σ超え'+s.big+'回</span>':'')+tags+'</div>'
    // bar: the large-move rate split into up (green) and down (red), with the
    // usual rate marked, on a 0-100% scale like the walls card
    +'<div class="sd-bar"><i class="u" style="width:'+(s.up/s.n*100).toFixed(1)+'%"></i><i class="d" style="width:'+(s.dn/s.n*100).toFixed(1)+'%"></i>'
    +'<b style="left:'+(br*100).toFixed(1)+'%"></b></div>';
}
// One horizon at a time: the tabs are shared by both 検証 cards, so picking
// 5日 shows 5日 on each. Study has no SQまで and falls back to 5日 there.
var SD_H='5';
function sdTabs(hs,cur){
  return '<div class="sd-tabs">'+hs.map(function(x){return '<button type="button" class="'+(x[0]===cur?'on':'')+'" onclick="sdSet(\''+x[0]+'\')">'+x[1]+'</button>';}).join('')+'</div>';
}
function sdSet(h){
  SD_H=h;
  [['sd-root',sdInner],['sw-root',typeof swInner==='function'?swInner:null]].forEach(function(p){
    var el=document.getElementById(p[0]);if(!el||!p[1])return;
    var open=[].slice.call(el.querySelectorAll('details[open]')).map(function(d){return d.getAttribute('data-k');});
    el.innerHTML=p[1]();
    open.forEach(function(k){var d=el.querySelector('details[data-k="'+k+'"]');if(d)d.open=true;});
  });
}
function sdFlags(D,c,h){
  var s=c.stats[h],b=D.base[h],ev=s.up+s.dn,out=[];
  if(!s.n||ev<__MIN__) return out;
  var br=(b.up+b.dn)/b.n,bu=b.up/(b.up+b.dn);
  if(ev/s.n>=br*__LIFT__) out.push('普段の'+(ev/s.n/br).toFixed(1)+'倍');
  if(s.p_dir!==null&&s.p_dir<__P__) out.push(s.up/ev>bu?'上に偏り':'下に偏り');
  return out;
}
function sdCard(D,c,h,today){
  return '<div class="sd-c'+(today?' today':'')+'"><div class="sd-n">'+c.name+(c.last?'<span>直近 '+sdD(c.last)+'</span>':'')+'</div>'
    +sdLine(D,c,h)+'</div>';
}
function sdHs(D){return D.horizons.map(function(x){return [String(x.h),x.label];});}
// 要点: what today's conditions and the similar days say, over every horizon
function sdPoints(D){
  var by={},P=[];D.conds.forEach(function(c){by[c.key]=c;});
  var g=(D.similar||[])[0];
  if(g&&g.days.length>=__MIN__) P.push('今日と似た日（'+D.applies_today.length+'条件のうち'+g.m+'つ以上・'+g.days.length+'日）のその後の大きな動き：'
    +D.horizons.map(function(x){var s=g.stats[String(x.h)];return x.label+' <span class="sd-up">上'+s.up+'</span>・<span class="sd-dn">下'+s.dn+'</span>';}).join('／')
    +(D.horizons.every(function(x){var s=g.stats[String(x.h)];return s.up+s.dn<__MIN__;})?'（回数が少なくデータ不足）':''));
  else P.push('今日と似た日はまだ少なく、データ不足です。');
  var f=[];
  D.applies_today.forEach(function(k){var c=by[k];if(!c)return;
    D.horizons.forEach(function(x){var t=sdFlags(D,c,String(x.h));if(t.length)f.push(c.name.split('（')[0]+' → '+x.label+'：'+t.join('・'));});});
  P.push(f.length?'今日の条件で印が付いているもの：<br>'+f.join('<br>'):'今日あてはまる条件に、目立った偏りはありません。');
  return '<div class="sd-pts"><div class="sd-pts-h">今日の要点</div>'+P.map(function(x){return '<div>'+x+'</div>';}).join('')+'</div>';
}
function sdInner(){
  var D=window.STUDY_DATA,hs=sdHs(D),h=hs.some(function(x){return x[0]===SD_H;})?SD_H:'5';
  var by={};D.conds.forEach(function(c){by[c.key]=c;});
  var b=D.base[h],o=sdPoints(D)+sdTabs(hs,h);
  o+='<div class="sd-leg"><span><i class="u"></i>上昇</span><span><i class="d"></i>下落</span><span><b></b>普段の確率</span></div>';
  o+='<div class="sd-base">普段の確率：<b>'+Math.round((b.up+b.dn)/b.n*100)+'%</b>（'+b.n+'日中'+(b.up+b.dn)+'回：上昇'+b.up+'回・下落'+b.dn+'回）</div>';
  var S=D.similar||[];
  o+='<div class="sd-sec">総合：今日と似た日のその後</div>';
  if(!S.length) o+='<div class="sd-base">今日あてはまる条件が'+D.applies_today.length+'件で、似た日を選べません。</div>';
  S.forEach(function(g){
    o+='<div class="sd-c today"><div class="sd-n">'+D.applies_today.length+'条件のうち'+g.m+'つ以上が重なった日<span>'+g.days.length+'日'
      +(g.days.length?'・直近 '+g.days.slice(-3).map(sdD).join('、'):'')+'</span></div>';
    var s=g.stats[h];
    if(g.days.length<__MIN__) o+='<div class="sd-base">データ不足（'+g.days.length+'日）</div>';
    else o+=sdLine(D,g,h)+(s.up+s.dn<__MIN__?'<div class="sd-b">大きな動きが__MIN__回未満のため、偏りの判定なし（データ不足）</div>':'');
    o+='</div>';
  });
  o+='<div class="sd-sec">今日（'+sdD(D.as_of)+'）あてはまる条件</div>';
  if(!D.applies_today.length) o+='<div class="sd-base">なし</div>';
  D.applies_today.forEach(function(k){if(by[k])o+=sdCard(D,by[k],h,true);});
  var rest=D.conds.filter(function(c){return D.applies_today.indexOf(c.key)<0;});
  var flag=rest.filter(function(c){return sdFlags(D,c,h).length;}),other=rest.filter(function(c){return !sdFlags(D,c,h).length;});
  o+='<div class="sd-sec">印が付いたほかの条件</div>';
  o+=flag.length?flag.map(function(c){return sdCard(D,c,h,false);}).join(''):'<div class="sd-base">なし</div>';
  o+='<details class="sd-more" data-k="other"><summary>ほかの条件を見る（'+other.length+'件）</summary>'+other.map(function(c){return sdCard(D,c,h,false);}).join('')+'</details>';
  o+='<details class="sd-more" data-k="how"><summary>読み方</summary>'
    +'<div class="sd-def"><b>大きな動き</b>＝その日のIVが想定した値幅（'+D.sigma_k+'σ）を超えた終値の変化。翌日は ±IV÷√250、5日後は ±IV×√(5/250)、10日後は ±IV×√(10/250)。'
    +'期間 '+sdD(D.period[0])+'〜'+sdD(D.period[1])+'（'+sdD(D.iv_from)+'より前はIVの代わりに20日実現ボラ）。棒の長さ＝その条件の日に大きな動きが起きた割合（上昇・下落の内訳つき）、黄色の線＝普段の確率。</div>'
    +'<div class="sd-def"><b>今日と似た日</b>＝今日あてはまる条件のうち、いくつかが同じ日に重なった過去の日。条件どうしは重なり合う（IVが高い日は大きく動いた日でもある等）ため、条件ごとの確率は掛け合わせていません。</div>'
    +'<div class="sd-note">印は大きな動きが__MIN__回以上ある条件だけに付けています。<b>上に偏り／下に偏り</b>＝大きな動きの上下の比率が普段と違う度合い（p＝偶然でもこれだけ偏る確率、0.1未満で表示）。'
    +'<b>普段の○倍</b>＝大きな動きの起きやすさ。5日後・10日後の集計は期間が重なり合うため、偏りは実際より強く見えやすい点に注意。'
    +'数か月分の結果で、相場の局面（上昇相場など）にも左右されます。データが増えるほど確かになります。</div></details>';
  return o;
}
function sdBuild(){
  if(!window.STUDY_DATA)return '<div class="insight">データなし</div>';
  return '<div id="sd-root">'+sdInner()+'</div>';
}
""".replace('__MIN__', str(MIN_EVENTS)).replace('__LIFT__', str(LIFT_FLAG)).replace('__P__', str(P_FLAG))


# ---- 検証：壁と大口（data/study_walls.json, extract_study_walls.py) ----

def walls_data_script(sw):
    return ('window.WALLS_DATA = %s;\n' % json.dumps(sw, ensure_ascii=False, separators=(',', ':'))) if sw else ''


def walls_preview(sw):
    if not sw or not sw.get('today'):
        return None
    t = sw['today']
    by = {x['key']: x for x in sw['tests']}

    def five(key):
        r = next((r for r in (by.get(key) or {}).get('by_h', []) if r['h'] == 5), None)
        return ('%d%%（理論%d%%）' % (round(r['rate'] * 100), round(r['exp'] * 100))) if r else '—'
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">下値の壁 P%s を5日で割る率</div><div class="mm-value" style="font-size:14px">%s</div></div>'
            '<div class="mini-metric"><div class="mm-label">上値の壁 C%s を5日で超える率</div><div class="mm-value" style="font-size:14px">%s</div></div></div>'
            % (format(t['pw'], ',') if t.get('pw') else '—', five('put_wall'),
               format(t['cw'], ',') if t.get('cw') else '—', five('call_wall')))


WALLS_CARD_JS = r"""
function swN(n){return Math.round(n).toLocaleString();}
function swSq(e){var d=new Date(2000+(+e.slice(0,2)),+e.slice(2)-1,8);d.setDate(8+(5-d.getDay()+7)%7);return (d.getMonth()+1)+'/'+d.getDate();}
function swRow(r,verb){
  var tag='';
  var sq=r.h==='sq';
  // SQまで: a handful of expiries counted day after day, so no badge
  if(!sq&&r.p!==null&&r.p<__P__&&r.n>=20){tag=r.rate<r.exp?'<span class="sd-tag up">理論より'+verb+'にくい</span>':'<span class="sd-tag dn">理論より'+verb+'やすい</span>';}
  var w=Math.min(100,r.rate*100),e=Math.min(100,r.exp*100),d=Math.round(r.rate*100)-Math.round(r.exp*100);
  // one bar for what happened; the IV-implied rate is a labelled marker on it
  return '<div class="sd-l"><span class="sd-r">'+Math.round(r.rate*100)+'%</span>'
    +'<span class="sd-b">理論'+Math.round(r.exp*100)+'%より'+(d===0?'差なし':(d<0?Math.abs(d)+'pt低い':d+'pt高い'))+'（'+r.n+'件中'+r.hit+'件'+(sq?'・SQ'+r.sqs+'回分':'、p='+r.p.toFixed(2))+'）</span>'+tag+'</div>'
    +'<div class="sw-bar"><i style="width:'+w.toFixed(1)+'%"></i><b style="left:'+e.toFixed(1)+'%"></b><em style="'+(e<6?'left:0;transform:none':(e>94?'left:auto;right:0;transform:none':'left:'+e.toFixed(1)+'%'))+'">理論'+Math.round(r.exp*100)+'%</em></div>';
}
function swHs(){return [['1','翌日'],['5','5日'],['10','10日'],['sq','SQまで']];}
function swPoints(D){
  var t=D.today||{},P=[],f=[];
  P.push('今日の壁：下値 <b>P'+(t.pw?swN(t.pw):'—')+'</b>／上値 <b>C'+(t.cw?swN(t.cw):'—')+'</b>'+(t.front?'（'+(+t.front.slice(2))+'月限・SQ '+swSq(t.front)+'）':''));
  D.tests.forEach(function(x){
    var hit=x.by_h.filter(function(r){return r.h!=='sq'&&r.p!==null&&r.p<__P__&&r.n>=20;});
    if(!hit.length)return;
    var lo=hit.filter(function(r){return r.rate<r.exp;}),hi=hit.filter(function(r){return r.rate>=r.exp;});
    var lab=function(a){return a.map(function(r){return r.h===1?'翌日':r.h+'日';}).join('・');};
    f.push(x.name.replace(/(に届いた|を終値で.*)$/,'')+'：'+(lo.length?lab(lo)+'で理論より'+x.verb+'にくい':'')+(lo.length&&hi.length?'、':'')+(hi.length?lab(hi)+'で理論より'+x.verb+'やすい':''));
  });
  P.push(f.length?'理論との差に印が付いているもの：<br>'+f.join('<br>'):'理論との差に、目立った印はありません。');
  var rg=D.tests.filter(function(x){return x.key==='range';})[0],r=rg&&rg.by_h[0];
  if(r) P.push('SQ前日に壁の間に収まった：<b>'+Math.round(r.rate*100)+'%</b>（理論'+Math.round(r.exp*100)+'%・SQ'+r.sqs+'回分なので参考）');
  return '<div class="sd-pts"><div class="sd-pts-h">今日の要点</div>'+P.map(function(x){return '<div>'+x+'</div>';}).join('')+'</div>';
}
function swInner(){
  var D=window.WALLS_DATA,t=D.today||{},h=SD_H;
  var o=swPoints(D)+sdTabs(swHs(),h);
  o+='<div class="sd-sec">今日（'+sdD(D.as_of)+'）の価格帯</div><div class="sd-base">'
    +'下値の壁 <b>P'+(t.pw?swN(t.pw):'—')+'</b>（'+(t.pw_oi?swN(t.pw_oi):'—')+'枚）／ 上値の壁 <b>C'+(t.cw?swN(t.cw):'—')+'</b>（'+(t.cw_oi?swN(t.cw_oi):'—')+'枚）'
    +((t.builds&&t.builds.length)?'<br>+300枚以上の積み増し：'+t.builds.map(function(b){return b[0]+swN(b[2])+'（'+(+b[1].slice(2))+'月限 +'+swN(b[3])+'）';}).join('、'):'')
    +((t.blocks&&t.blocks.length)?'<br>大口の新規建て：'+t.blocks.map(function(b){return b[0]+swN(b[2])+'（'+swN(b[3])+'枚）';}).join('、'):'')+'</div>';
  o+='<div class="sd-sec">過去の結果（'+(h==='sq'?'SQまで':h==='1'?'翌日':h+'日以内')+'）</div>';
  D.tests.forEach(function(x){
    var r=x.by_h.filter(function(r){return String(r.h)===h;})[0];
    if(!r)return;
    o+='<div class="sd-c"><div class="sd-n">'+x.name+'</div>'+swRow(r,x.verb)+'</div>';
  });
  if(h!=='sq') o+='<div class="sd-b" style="margin:6px 2px">「SQ前日に壁の間に収まった」はSQまでのタブにあります。</div>';
  o+='<details class="sd-more" data-k="swhow"><summary>読み方</summary>'
    +'<div class="sd-def">壁や建玉が無かったとしても、IVの値動きからその価格に届く確率（<b>理論</b>）は計算できます。実際に届いた割合がそれより<b>低ければ止まりやすい</b>、<b>高ければ引き寄せられやすい</b>と読みます。終値で判定、期間 '+sdD(D.period[0])+'〜'+sdD(D.period[1])+'。</div>'
    +'<div class="sw-leg">棒＝実際に届いた（割った・超えた）割合。<b>│理論</b>の印＝壁や建玉が無くてもIVの値動きから届く確率。棒が印に届かなければ止まりやすい、印を越えていれば引き寄せられやすい。</div>'
    +'<div class="sd-note">壁は、SQまで7日以上ある一番近い限月で、現値から±10%以内の最大建玉。理論はその日のIV（6/12より前は20日実現ボラ）で日々の終値を4,000通り試算した確率。'
    +'<b>SQまで</b>＝SQ前日（オプション最終取引日）の終値までで判定、限月はその日の前限月の建玉だけ。理論はSQまでの営業日数で試算。SQの回数がまだ少なく、同じSQを毎日数え直しているので印は付けず数字だけ。'
    +'「間に収まった」の理論は、IVどおりに動いたときSQ前日の終値が二つの壁の間に入る確率。'
    +'印は20件以上・p＜__P__のときだけ。同じ壁が何日も続いたり、同じ日に複数の行使価格が積まれたりするため件数は独立ではなく、pは実際より良く見えやすい点に注意。</div></details>';
  return o;
}
function swBuild(){
  if(!window.WALLS_DATA)return '<div class="insight">データなし</div>';
  return '<div id="sw-root">'+swInner()+'</div>';
}
""".replace('__P__', str(P_FLAG))

WALLS_CARD_CSS = r"""
.sw-bar{position:relative;height:10px;background:rgba(255,255,255,.06);border-radius:5px;margin:20px 0 10px}
.sw-bar i{display:block;height:100%;background:#818cf8;border-radius:5px}
.sw-bar b{position:absolute;top:-4px;width:2px;height:18px;background:#fbbf24}
.sw-bar em{position:absolute;bottom:15px;transform:translateX(-50%);font-style:normal;font-size:11px;color:#fbbf24;white-space:nowrap;font-weight:600}
.sw-leg{font-size:12px;color:var(--sub);line-height:1.7;margin:6px 2px 0}
.sw-leg b{color:var(--text)}
"""
