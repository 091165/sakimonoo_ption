#!/usr/bin/env python3
"""Render the "大口動向（週次の推移）" card from broker_history.json.

Shows, per major broker, the multi-week trend of futures net and option
put/call net (buy +, sell -), with a derived tendency tag. Futures and
options are the two separate battlegrounds, so each broker line carries both.
"""
import json


CAT_JA = {'us': '米系', 'eu': '欧系', 'hf': 'HF代理',
          'domestic': '国内', 'other': '', 'グローバルマクロ': 'マクロ'}


def _short(n):
    return str(n).replace('ＪＰモルガン', 'JPモルガン')[:8]


def bw_data_script(hist):
    dates = sorted(hist.keys())
    # Rank by futures footprint only. The weekly option file covers just the
    # five strikes around that week's ATM, which change as the index moves, so
    # per-broker put/call "nets" are not a series and are not charted here.
    foot = {}
    for d in dates:
        for b, v in hist[d].items():
            foot[b] = max(foot.get(b, 0), abs(v.get('fut', 0) or 0))
    order = [b for b, _ in sorted(foot.items(), key=lambda x: -x[1])]

    def series(b, field):
        return [hist[d].get(b, {}).get(field) for d in dates]

    rows = []
    for b in order:
        cat = ''
        for d in dates:
            if hist[d].get(b, {}).get('cat'):
                cat = hist[d][b]['cat']
                break
        rows.append({
            'broker': b, 'cat': CAT_JA.get(cat, cat),
            'fut': series(b, 'fut'), 'put': series(b, 'put'),
            'call': series(b, 'call'),
        })
    payload = {'dates': [d[4:6] + '/' + d[6:] for d in dates], 'rows': rows}
    return "window.BW_DATA=%s;" % json.dumps(payload, ensure_ascii=False)


BW_CARD_CSS = r"""
.bw-intro{font-size:13px;color:var(--sub);line-height:1.6;margin:2px 2px 10px}
.bw-row{border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin:8px 0;background:#141822}
.bw-name{font-family:Outfit;font-weight:700;font-size:15px;margin-bottom:8px}
.bw-cat{font-size:12px;color:var(--sub);font-weight:400;margin-left:6px}
.bw-metrics{display:flex;gap:10px}
.bw-metric{flex:1;min-width:0}
.bw-mlabel{font-size:12px;color:var(--sub);margin-bottom:3px}
.bw-spark{background:#0f131b;border-radius:5px;padding:2px 3px}
.bw-mval{font-family:'DM Mono',monospace;font-size:14px;font-weight:600;margin-top:3px;white-space:nowrap}
.bw-wow{font-size:12px;margin-left:2px;opacity:.85}
.bw-pos{color:#86efac}.bw-neg{color:#fca5a5}.bw-ze{color:var(--sub)}
.bw-read{font-size:13px;color:#cbd5e1;line-height:1.45;margin-top:8px;border-top:1px solid rgba(38,44,58,.6);padding-top:6px}
.bw-det{margin:14px 0 0;border:1px solid var(--border);border-radius:10px;padding:8px 10px}
.bw-det summary{cursor:pointer;color:var(--accent);font-size:13px;font-weight:600}
.bw-k{font-family:'DM Mono',monospace;font-size:13px;font-weight:600;color:var(--text);margin:10px 0 4px}
.bw-ln{display:flex;gap:6px;align-items:flex-start;font-size:12px;margin:2px 0}
.bw-tag{flex:none;min-width:34px;color:var(--sub)}
.bw-t{display:inline-block;padding:1px 6px;border-radius:5px;margin:1px 3px 1px 0;white-space:nowrap}
.bw-tb{background:rgba(74,222,128,.12);color:#86efac}.bw-ts{background:rgba(248,113,113,.12);color:#fca5a5}
.bw-note{font-size:12px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
"""

BW_CARD_JS = r"""
function bwOptSnap(){
  // Weekly option holdings by participant. JPX publishes them for only the
  // five strikes around that week's ATM, so this is a snapshot, not a trend,
  // and the large walls (e.g. P60,000) are not covered.
  var OW=window.OPTW_DATA||{}, st=OW.strikes||{};
  var ks=Object.keys(st).map(Number).sort(function(a,b){return b-a;});
  if(!ks.length) return '';
  function cell(list,buy){
    if(!list||!list.length) return '<span class="bw-ze">—</span>';
    return list.slice(0,3).map(function(x){
      return '<span class="bw-t '+(buy?'bw-tb':'bw-ts')+'">'+String(x[0]).replace('証券','').replace('クリアリン','')+' '+Math.round(x[1]).toLocaleString()+'</span>';
    }).join('');
  }
  var h='<details class="bw-det" onclick="event.stopPropagation()"><summary>参考：オプションの買い持ち・売り持ち（週次・'+(OW.as_of||'')+'）</summary>';
  h+='<div class="bw-note" style="margin-top:8px">取引所が参加者別に公表しているのは、その週のATM付近の<b>5本の行使価格だけ</b>です。壁になっている遠い行使価格（P60,000など）の持ち主は公表されず、5本も毎週入れ替わるため、推移ではなくその週の断面として見てください。</div>';
  for(var i=0;i<ks.length;i++){var sd=st[String(ks[i])];
    h+='<div class="bw-k">'+ks[i].toLocaleString()+'</div>';
    h+='<div class="bw-ln"><span class="bw-tag">P買</span><span>'+cell(sd.put.buyers,true)+'</span></div>';
    h+='<div class="bw-ln"><span class="bw-tag">P売</span><span>'+cell(sd.put.sellers,false)+'</span></div>';
    h+='<div class="bw-ln"><span class="bw-tag">C買</span><span>'+cell(sd.call.buyers,true)+'</span></div>';
    h+='<div class="bw-ln"><span class="bw-tag">C売</span><span>'+cell(sd.call.sellers,false)+'</span></div>';
  }
  return h+'</details>';
}
function bwBuild(){
  // The per-broker futures bar charts were removed: they repeated the weekly
  // net table above them. Only the option snapshot is added below the table.
  return bwOptSnap();
}
"""


def preview_broker_watch(hist):
    """Short preview: highlight the biggest futures long/short and a note."""
    dates = sorted(hist.keys())
    if not dates:
        return "var h='<div>データなし</div>';return h;"
    last = hist[dates[-1]]
    fut = [(b, v.get('fut', 0)) for b, v in last.items() if v.get('fut')]
    if not fut:
        return "var h='<div>週次データ待ち</div>';return h;"
    top_long = max(fut, key=lambda x: x[1])
    top_short = min(fut, key=lambda x: x[1])
    js = "var h='';"
    js += ("h+='<div style=\"font-size:12px;line-height:1.7\">"
           "先物ロング首位: <b>%s</b> (%+d)<br>"
           "先物ショート首位: <b>%s</b> (%+d)</div>';") % (
        _short(top_long[0]), round(top_long[1]),
        _short(top_short[0]), round(top_short[1]))
    return js


if __name__ == '__main__':
    import sys
    h = json.load(open(sys.argv[1], encoding='utf-8'))
    print(bw_data_script(h)[:200])
