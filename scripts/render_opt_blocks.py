#!/usr/bin/env python3
"""Card: オプションの大口（J-NET） — who crossed option blocks, with whom, and
whether the block stayed in open interest.

Replaces the strike card (建玉×手口×相対IV): that card mixed every venue and an
inferred IV direction, which made the one thing that matters for a seller —
"which blocks went through, between whom, and did they open or close" —
hard to see. Data comes from data/opt_blocks.json (extract_opt_blocks.py);
the day's option volume summary comes from data.json (s03).
"""

import json

KIND = {'pair': '相対', 'single': '単独クロス', 'multi': '複数'}
CAT_JA = {'domestic': '国内', 'us': '米系', 'eu': '欧系', 'hf': 'HF代理', 'other': ''}
LOG_DAYS = 10
LOG_MIN_LOTS = 300   # older days in the 10-day log keep only the large blocks;
                     # the latest day lists every block (50+ lots)


def _name(b):
    return b.replace('証券', '').replace('クリアリン', '').replace('グループ', '')


def build(store, s03=None):
    if not store or not store.get('dates'):
        return None
    dates = store['dates']
    today = dates[-1]
    day = store['days'][today]
    log, seen = [], {}
    for d in dates[-LOG_DAYS:]:
        for b in store['days'][d]['blocks']:
            if d != today and b['lots'] < LOG_MIN_LOTS:
                continue
            key = '%s%s-%d' % (b['side'], b['exp'], b['k'])
            seen[key] = seen.get(key, 0) + 1
            log.append(dict(b, date=d, key=key))
    for x in log:
        x['repeat'] = seen[x['key']] >= 2
    large = (s03 or {}).get('large') or {}
    # Puts normally out-trade calls in large options; a call-heavy day is the
    # exception worth flagging (2 of 26 sessions from mid-Sep to end-Oct).
    pcs = [{'date': d, 'put': store['days'][d]['pc']['put'], 'call': store['days'][d]['pc']['call']}
           for d in dates if (store['days'][d].get('pc') or {}).get('put')]
    for x in pcs:
        x['special'] = x['call'] > x['put']
    return {
        'pc_hist': pcs[-20:], 'pc_n': len(pcs), 'pc_special': [x['date'] for x in pcs if x['special']],
        'today_special': bool(pcs and pcs[-1]['date'] == today and pcs[-1]['special']),
        'date': today, 'blocks': day['blocks'], 'top_volume': day.get('top_volume', []),
        # Put/call from the same store as the special-day flag, so the two
        # can never disagree; the J-NET share comes from data.json.
        'summary': ({'put_volume': day['pc']['put'], 'call_volume': day['pc']['call'],
                     'jnet_ratio': large.get('jnet_ratio')} if day.get('pc') else
                    {k: large.get(k) for k in ('put_volume', 'call_volume', 'jnet_ratio')} if large else None),
        'log': list(reversed(log)), 'log_days': min(LOG_DAYS, len(dates)),
        'kind': KIND, 'cat': CAT_JA,
    }


def data_script(store, s03=None, s05=None):
    d = build(store, s03)
    if not d:
        return ''
    # ±300 OI changes for the volume card (data.json s05, all expiries)
    d['moves'] = sorted((m for m in (s05 or []) if isinstance(m, dict) and m.get('change')),
                        key=lambda m: -abs(m['change']))
    return 'window.OB_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))


def preview_volume(store, s03=None):
    """Card: オプションの取引高 — today's put/call volume, flagged when calls lead."""
    d = build(store, s03)
    if not d or not d.get('summary') or not d['summary'].get('call_volume'):
        return None
    sm = d['summary']
    flag = ('<div class="ob-flag" style="margin-bottom:6px">特異日：コールの取引高がプットを上回った</div>'
            if d['today_special'] else '')
    return (flag + '<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">プット / コール（ラージ）</div>'
            '<div class="mm-value" style="font-size:14px">%s / %s</div></div>'
            '<div class="mini-metric"><div class="mm-label">PCR（出来高）</div>'
            '<div class="mm-value" style="font-size:14px">%.2f</div></div></div>'
            % (format(sm['put_volume'], ','), format(sm['call_volume'], ','),
               sm['put_volume'] / sm['call_volume']))


def preview(store, s03=None):
    d = build(store, s03)
    if not d:
        return None
    if not d['blocks']:
        return '<span class="mm-label">本日の大口（50枚以上）なし</span>'
    b = d['blocks'][0]
    singles = sum(1 for x in d['blocks'] if x['kind'] == 'single')
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">本日最大の大口</div>'
            '<div class="mm-value" style="font-size:14px;color:%s">%s%s %s枚</div></div>'
            '<div class="mini-metric"><div class="mm-label">大口の件数（うち単独クロス）</div>'
            '<div class="mm-value" style="font-size:14px">%d件（%d件）</div></div></div>'
            % ('var(--put)' if b['side'] == 'P' else 'var(--call)', b['side'], format(b['k'], ','),
               format(b['lots'], ','), len(d['blocks']), singles))


OB_CARD_CSS = r"""
.ob-sec{font-family:Outfit;font-weight:600;color:var(--sub);font-size:13px;margin:14px 2px 6px}
.ob-sec:first-child{margin-top:0}
.ob-sum{font-size:13px;color:var(--text);line-height:1.7;margin:0 2px}
.ob-flag{font-size:13px;font-weight:600;color:#fbbf24;background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.45);border-radius:8px;padding:6px 10px;margin:6px 0}
.ob-pcs{display:flex;align-items:flex-end;gap:2px;height:34px;margin:8px 0 2px}
.ob-pcs i{flex:1;background:#5b647a;border-radius:2px 2px 0 0;min-height:2px}
.ob-pcs i.sp{background:#fbbf24}
.ob-pcl{display:flex;justify-content:space-between;font-size:11px;color:var(--sub)}
.ob-tv{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0}
.ob-tvi{font-family:'DM Mono',monospace;font-size:12px;padding:3px 8px;border-radius:6px;background:rgba(255,255,255,.04);border:1px solid var(--border)}
.ob-blk{border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:8px 0;background:#141822}
.ob-hd{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 8px;margin-bottom:6px}
.ob-k{font-family:'DM Mono',monospace;font-weight:700;font-size:15px}
.ob-p{color:#fca5a5}.ob-c{color:#93c5fd}
.ob-lots{font-size:14px;color:var(--text);font-weight:600}
.ob-chip{font-size:12px;padding:1px 7px;border-radius:6px;white-space:nowrap}
.ob-pair{background:rgba(129,140,248,.15);color:#c7d2fe}
.ob-single{background:rgba(251,191,36,.15);color:#fbbf24}
.ob-multi{background:rgba(255,255,255,.06);color:var(--sub)}
.ob-new{background:rgba(74,222,128,.14);color:#86efac}
.ob-close{background:rgba(248,113,113,.14);color:#fca5a5}
.ob-move,.ob-mix{background:rgba(255,255,255,.06);color:var(--sub)}
.ob-who{font-size:13px;color:var(--text);line-height:1.8}
.ob-b{display:inline-block;padding:0 6px;border-radius:5px;background:rgba(147,197,253,.10);margin:1px 0}
.ob-b.dom{background:rgba(248,113,113,.10)}
.ob-x{color:var(--sub);margin:0 4px}
.ob-oi{font-size:12px;color:var(--sub);margin-top:4px;line-height:1.6}
.ob-up{color:#86efac}.ob-dn{color:#fca5a5}
.ob-log{width:100%;border-collapse:collapse;font-size:12px}
.ob-log th{color:var(--sub);font-weight:500;text-align:left;padding:5px 4px;border-bottom:1px solid var(--border);white-space:nowrap}
.ob-log td{padding:6px 4px;border-bottom:1px solid rgba(38,44,58,.5);vertical-align:top}
.ob-log td.n{font-family:'DM Mono',monospace;white-space:nowrap;text-align:right}
.ob-rep{color:#fbbf24}
.ob-note{font-size:11px;color:var(--sub);line-height:1.6;margin:10px 2px 0}
"""

OB_CARD_JS = r"""
function obN(n){return (n===null||n===undefined)?'—':Math.round(n).toLocaleString();}
function obS(n){return (n===null||n===undefined)?'—':((n>0?'+':'')+Math.round(n).toLocaleString());}
function obNm(b){return String(b).replace('証券','').replace('クリアリン','').replace('グループ','');}
function obLeg(x){return '<span class="ob-b'+(x.cat==='domestic'?' dom':'')+'">'+obNm(x.broker)+' '+obN(x.vol)+'</span>';}
function obVcls(v){return v==='新規建て'?'ob-new':v==='決済'?'ob-close':v==='付け替え'?'ob-move':'ob-mix';}
function obWho(b){
  if(b.kind==='single') return obLeg(b.a[0])+'<span class="ob-x">＝</span>約'+obN(b.lots)+'枚を同じ社内で売り買い';
  if(b.kind==='pair') return b.a.map(obLeg).join('')+'<span class="ob-x">⟷</span>'+b.b.map(obLeg).join('<span class="ob-x">・</span>');
  return '参加：'+b.a.map(obLeg).join(' ');
}
function obBlock(b){
  var h='<div class="ob-blk"><div class="ob-hd"><span class="ob-k '+(b.side==='P'?'ob-p':'ob-c')+'">'+b.side+obN(b.k)+'</span>'
    +'<span class="ob-chip" style="color:var(--sub)">'+(+b.exp.slice(2))+'月限</span>'
    +'<span class="ob-lots">約'+obN(b.lots)+'枚</span>'
    +'<span class="ob-chip ob-'+b.kind+'">'+window.OB_DATA.kind[b.kind]+'</span>'
    +(b.verdict?'<span class="ob-chip '+obVcls(b.verdict)+'">'+b.verdict+'</span>':'')+'</div>';
  h+='<div class="ob-who">'+obWho(b)+'</div>';
  h+='<div class="ob-oi">建玉 '+obN(b.oi)+'（<span class="'+((b.chg||0)>0?'ob-up':(b.chg||0)<0?'ob-dn':'')+'">'+obS(b.chg)+'</span>）'
    +(b.vol?' ／ この日の取引高 '+obN(b.vol)+'枚のうち大口 '+obN(b.lots)+'枚':'')
    +' ／ '+b.sessions.map(function(s){return s==='day'?'日中':'夜間';}).join('・')+'</div></div>';
  return h;
}
function obVolBuild(){
  var D=window.OB_DATA;if(!D)return '<div class="insight">データなし</div>';
  var h='<div class="ob-sec">今日のオプション取引高（ラージ）</div>';
  if(D.summary&&D.summary.put_volume!==undefined){
    var s=D.summary;
    h+='<div class="ob-sum">プット <b>'+obN(s.put_volume)+'</b>枚 ／ コール <b>'+obN(s.call_volume)+'</b>枚'
      +(s.call_volume?'（PCR '+(s.put_volume/s.call_volume).toFixed(2)+'）':'')+' ／ J-NET比率 '+(s.jnet_ratio===null||s.jnet_ratio===undefined?'—':s.jnet_ratio+'%')+'</div>';
  }
  if(D.today_special) h+='<div class="ob-flag">特異日：コールの取引高がプットを上回った（普段はプットの方が多い）</div>';
  if(D.pc_hist&&D.pc_hist.length>2){
    var mx=0;for(var i=0;i<D.pc_hist.length;i++)mx=Math.max(mx,D.pc_hist[i].put/D.pc_hist[i].call);
    h+='<div class="ob-pcs">';
    for(var i=0;i<D.pc_hist.length;i++){var x=D.pc_hist[i],r=x.put/x.call;
      h+='<i class="'+(x.special?'sp':'')+'" style="height:'+(r/mx*100).toFixed(0)+'%" title="'+x.date+' PCR '+r.toFixed(2)+'"></i>';}
    var f=D.pc_hist[0].date,l=D.pc_hist[D.pc_hist.length-1].date;
    h+='</div><div class="ob-pcl"><span>'+(+f.slice(4,6))+'/'+(+f.slice(6))+'</span><span>プット÷コール（PCR）の推移・黄＝コールが多かった日</span><span>'+(+l.slice(4,6))+'/'+(+l.slice(6))+'</span></div>';
    h+='<div class="ob-sum" style="margin-top:4px;color:var(--sub)">直近'+D.pc_n+'営業日でコールが多かった日は<b style="color:var(--text)">'+D.pc_special.length+'日</b>'
      +(D.pc_special.length?'（'+D.pc_special.map(function(d){return (+d.slice(4,6))+'/'+(+d.slice(6));}).join('、')+'）':'')+'。</div>';
  }
  h+='<div class="ob-sec">建玉が前日比±300枚以上動いた銘柄</div>';
  if(!D.moves||!D.moves.length) h+='<div class="ob-sum">該当なし</div>';
  else{h+='<div class="ob-tv">';
    for(var i=0;i<D.moves.length;i++){var m=D.moves[i];
      h+='<span class="ob-tvi"><span class="'+(m.type==='P'?'ob-p':'ob-c')+'">'+m.type+obN(m.strike)+'</span> '+(+String(m.expiry).slice(2))+'月限 <span class="'+(m.change>0?'ob-up':'ob-dn')+'">'+obS(m.change)+'</span>（建玉 '+obN(m.oi)+'）</span>';}
    h+='</div>';}
  return h;
}
function obBuild(){
  var D=window.OB_DATA;if(!D)return '<div class="insight">データなし</div>';
  var h='';
  h+='<div class="ob-sec" style="margin-top:0">今日の大口（J-NET・50枚以上）</div>';
  if(!D.blocks.length) h+='<div class="ob-sum">該当なし</div>';
  for(var i=0;i<D.blocks.length;i++) h+=obBlock(D.blocks[i]);
  h+='<div class="ob-sec">直近'+D.log_days+'営業日の大口</div><div class="ob-sum" style="color:var(--sub);margin-bottom:4px">最新日（'+(+D.date.slice(4,6))+'/'+(+D.date.slice(6))+'）は50枚以上すべて、それより前は300枚以上</div>';
  if(!D.log.length) h+='<div class="ob-sum">該当なし</div>';
  else{
  h+='<table class="ob-log"><thead><tr><th>日付</th><th>銘柄</th><th style="text-align:right">枚数</th><th>種類</th><th>建玉</th></tr></thead><tbody>';
  for(var i=0;i<D.log.length;i++){var x=D.log[i];
    h+='<tr><td class="n" style="text-align:left">'+(+x.date.slice(4,6))+'/'+(+x.date.slice(6))+'</td>'
      +'<td class="n" style="text-align:left">'+(x.repeat?'<span class="ob-rep">★</span>':'')+'<span class="'+(x.side==='P'?'ob-p':'ob-c')+'">'+x.side+obN(x.k)+'</span><br><span style="color:var(--sub)">'+(+x.exp.slice(2))+'月限</span></td>'
      +'<td class="n">'+obN(x.lots)+'</td>'
      +'<td>'+D.kind[x.kind]+'<br><span style="color:var(--sub)">'+(x.kind==='single'?obNm(x.a[0].broker):x.kind==='pair'?obNm(x.a[0].broker)+'⟷'+x.b.map(function(y){return obNm(y.broker);}).join('・'):x.a.slice(0,2).map(function(y){return obNm(y.broker);}).join('・')+'…')+'</span></td>'
      +'<td class="n" style="text-align:left">'+obS(x.chg)+'<br><span style="color:var(--sub)">'+(x.verdict||'')+'</span></td></tr>';}
  h+='</tbody></table>';
  }
  h+='<div class="ob-note"><b>相対</b>＝一番多い社が片側、残りの社がもう片側（枚数がほぼ一致）。<b>単独クロス</b>＝1社しか出てこない取引で、その社の中で顧客同士または自社と顧客の売りと買いを付け合わせたもの（出来高は枚数の2倍で載る）。'
    +'<b>新規建て</b>＝建玉が大口の枚数の7割以上増えた、<b>決済</b>＝7割以上減った、<b>付け替え</b>＝増減が3割以内（玉が持ち主を移っただけ）。'
    +'★＝期間中に同じ銘柄で2回以上の大口。手口には売り買いの区別がないため、どちらが買ったかは分かりません。</div>';
  return h;
}
"""
