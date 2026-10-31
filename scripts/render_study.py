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
  var lab=D.horizons.filter(function(x){return String(x.h)===h;})[0].label;
  return '<div class="sd-l"><span class="sd-h">'+lab+'</span><span class="sd-r">'+Math.round(rate*100)+'%</span>'
    +'<span class="sd-b">（'+s.n+'日中'+ev+'回、普段'+Math.round(br*100)+'%）</span>'
    +'<span class="sd-up">上'+s.up+'</span><span class="sd-dn">下'+s.dn+'</span>'
    +(s.big?'<span class="sd-b">うち1.5σ超え'+s.big+'</span>':'')+tags+'</div>';
}
function sdCard(D,c,today){
  return '<div class="sd-c'+(today?' today':'')+'"><div class="sd-n">'+c.name+(c.last?'<span>直近 '+sdD(c.last)+'</span>':'')+'</div>'
    +sdLine(D,c,'1')+sdLine(D,c,'5')+'</div>';
}
function sdBuild(){
  var D=window.STUDY_DATA;if(!D)return '<div class="insight">データなし</div>';
  var h='<div class="sd-def"><b>大きな動き</b>＝その日のIVが想定した値幅（'+D.sigma_k+'σ）を超えた終値の変化。翌日は ±IV÷√250、5日後は ±IV×√(5/250)。'
    +'期間 '+sdD(D.period[0])+'〜'+sdD(D.period[1])+'（'+sdD(D.iv_from)+'より前はIVの代わりに20日実現ボラ）。</div>';
  var b1=D.base['1'],b5=D.base['5'];
  h+='<div class="sd-base">普段の確率：翌日 <b>'+Math.round((b1.up+b1.dn)/b1.n*100)+'%</b>（'+b1.n+'日中'+(b1.up+b1.dn)+'回、上'+b1.up+'・下'+b1.dn+'）／ 5日後 <b>'+Math.round((b5.up+b5.dn)/b5.n*100)+'%</b>（'+b5.n+'日中'+(b5.up+b5.dn)+'回、上'+b5.up+'・下'+b5.dn+'）</div>';
  var by={};D.conds.forEach(function(c){by[c.key]=c;});
  h+='<div class="sd-sec">今日（'+sdD(D.as_of)+'）あてはまる条件</div>';
  if(!D.applies_today.length) h+='<div class="sd-base">なし</div>';
  D.applies_today.forEach(function(k){if(by[k])h+=sdCard(D,by[k],true);});
  h+='<div class="sd-sec">すべての条件</div>';
  D.conds.forEach(function(c){if(D.applies_today.indexOf(c.key)<0)h+=sdCard(D,c,false);});
  h+='<div class="sd-note">印は大きな動きが__MIN__回以上ある条件だけに付けています。<b>上に偏り／下に偏り</b>＝大きな動きの上下の比率が普段と違う度合い（p＝偶然でもこれだけ偏る確率、0.1未満で表示）。'
    +'<b>普段の○倍</b>＝大きな動きの起きやすさ。5日後の集計は期間が重なり合うため、偏りは実際より強く見えやすい点に注意。'
    +'数か月分の結果で、相場の局面（上昇相場など）にも左右されます。データが増えるほど確かになります。</div>';
  return h;
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
function swRow(r,verb){
  var tag='';
  if(r.p!==null&&r.p<__P__&&r.n>=20){tag=r.rate<r.exp?'<span class="sd-tag up">理論より'+verb+'にくい</span>':'<span class="sd-tag dn">理論より'+verb+'やすい</span>';}
  var w=Math.min(100,r.rate*100),e=Math.min(100,r.exp*100);
  return '<div class="sd-l"><span class="sd-h">'+r.h+'日以内</span><span class="sd-r">'+Math.round(r.rate*100)+'%</span>'
    +'<span class="sd-b">（'+r.n+'件中'+r.hit+'件、理論'+Math.round(r.exp*100)+'%、p='+r.p.toFixed(2)+'）</span>'+tag+'</div>'
    +'<div class="sw-bar"><i style="width:'+w.toFixed(0)+'%"></i><b style="left:'+e.toFixed(0)+'%"></b></div>';
}
function swBuild(){
  var D=window.WALLS_DATA;if(!D)return '<div class="insight">データなし</div>';
  var t=D.today||{},h='<div class="sd-def">壁や建玉が無かったとしても、IVの値動きからその価格に届く確率（<b>理論</b>）は計算できます。実際に届いた割合がそれより<b>低ければ止まりやすい</b>、<b>高ければ引き寄せられやすい</b>と読みます。終値で判定、期間 '+sdD(D.period[0])+'〜'+sdD(D.period[1])+'。</div>';
  h+='<div class="sd-sec">今日（'+sdD(D.as_of)+'）の価格帯</div><div class="sd-base">'
    +'下値の壁 <b>P'+(t.pw?swN(t.pw):'—')+'</b>（'+(t.pw_oi?swN(t.pw_oi):'—')+'枚）／ 上値の壁 <b>C'+(t.cw?swN(t.cw):'—')+'</b>（'+(t.cw_oi?swN(t.cw_oi):'—')+'枚）'
    +((t.builds&&t.builds.length)?'<br>+300枚以上の積み増し：'+t.builds.map(function(b){return b[0]+swN(b[2])+'（'+(+b[1].slice(2))+'月限 +'+swN(b[3])+'）';}).join('、'):'')
    +((t.blocks&&t.blocks.length)?'<br>大口の新規建て：'+t.blocks.map(function(b){return b[0]+swN(b[2])+'（'+swN(b[3])+'枚）';}).join('、'):'')+'</div>';
  h+='<div class="sd-sec">過去の結果</div>';
  D.tests.forEach(function(x){
    if(!x.by_h.length)return;
    h+='<div class="sd-c"><div class="sd-n">'+x.name+'</div>'+x.by_h.map(function(r){return swRow(r,x.verb);}).join('')+'</div>';
  });
  h+='<div class="sw-leg"><i></i>実際の割合　<b></b>理論（IVから見た確率）</div>';
  h+='<div class="sd-note">壁は、SQまで7日以上ある一番近い限月で、現値から±10%以内の最大建玉。理論はその日のIV（6/12より前は20日実現ボラ）で日々の終値を4,000通り試算した確率。'
    +'印は20件以上・p＜__P__のときだけ。同じ壁が何日も続いたり、同じ日に複数の行使価格が積まれたりするため件数は独立ではなく、pは実際より良く見えやすい点に注意。</div>';
  return h;
}
""".replace('__P__', str(P_FLAG))

WALLS_CARD_CSS = r"""
.sw-bar{position:relative;height:8px;background:rgba(255,255,255,.06);border-radius:4px;margin:2px 0 8px}
.sw-bar i{display:block;height:100%;background:#818cf8;border-radius:4px}
.sw-bar b{position:absolute;top:-3px;width:2px;height:14px;background:#fbbf24}
.sw-leg{font-size:12px;color:var(--sub);margin:4px 2px 0}
.sw-leg i{display:inline-block;width:14px;height:8px;background:#818cf8;border-radius:3px;vertical-align:middle;margin-right:4px}
.sw-leg b{display:inline-block;width:2px;height:12px;background:#fbbf24;vertical-align:middle;margin:0 4px 0 10px}
"""
