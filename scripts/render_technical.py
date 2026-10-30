#!/usr/bin/env python3
"""Card: テクニカル指標 — moving averages, Bollinger bands and RSI of the
Nikkei 225 close.

Computed from the daily cash-close series in data/futures_flow.json (every
session, the tp.csv underlying), not from data.json's technicals, which come
from a web OHLC fetch that fails in the pipeline and had stopped at 10/26.
Only closes are available, so indicators that need highs and lows (pivots,
ATR) are not shown.
"""

import json
import math


def _ma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _rsi(xs, n=14):
    """Wilder's RSI on closes."""
    if len(xs) < n + 1:
        return None
    ch = [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    gain = sum(max(c, 0) for c in ch[:n]) / n
    loss = sum(max(-c, 0) for c in ch[:n]) / n
    for c in ch[n:]:
        gain = (gain * (n - 1) + max(c, 0)) / n
        loss = (loss * (n - 1) + max(-c, 0)) / n
    return 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)


def build(flow):
    if not flow or not flow.get('dates'):
        return None
    pts = [(d, flow['rows'][d].get('close')) for d in flow['dates'] if flow['rows'][d].get('close')]
    if len(pts) < 26:
        return None
    dates = [d for d, _ in pts]
    xs = [c for _, c in pts]
    last = xs[-1]
    ma5, ma25 = _ma(xs, 5), _ma(xs, 25)
    win = xs[-20:]
    mid = sum(win) / 20
    sd = math.sqrt(sum((x - mid) ** 2 for x in win) / 20)
    # 40-day chart: close, 25-day MA and the ±2σ band
    series = []
    for i in range(max(25, len(xs) - 40), len(xs) + 1):
        w = xs[i - 20:i]
        m = sum(w) / 20
        s = math.sqrt(sum((x - m) ** 2 for x in w) / 20)
        series.append({'d': dates[i - 1], 'c': xs[i - 1], 'ma25': sum(xs[i - 25:i]) / 25,
                       'up': m + 2 * s, 'lo': m - 2 * s})
    return {
        'date': dates[-1], 'close': last,
        'ma5': ma5, 'ma25': ma25,
        'dev5': (last / ma5 - 1) * 100, 'dev25': (last / ma25 - 1) * 100,
        'bb_mid': mid, 'bb_sd': sd, 'bb_sigma': (last - mid) / sd if sd else None,
        'rsi': _rsi(xs),
        'hi20': max(xs[-20:]), 'lo20': min(xs[-20:]),
        'series': series,
    }


def data_script(flow):
    d = build(flow)
    return ('window.TECH_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))) if d else ''


def preview(flow):
    d = build(flow)
    if not d:
        return None
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">25日線からの乖離</div><div class="mm-value" style="font-size:14px">%+.1f%%</div></div>'
            '<div class="mini-metric"><div class="mm-label">ボリンジャー（20日）</div><div class="mm-value" style="font-size:14px">%+.1fσ</div></div>'
            '<div class="mini-metric"><div class="mm-label">RSI（14日）</div><div class="mm-value" style="font-size:14px">%.0f</div></div>'
            '</div>' % (d['dev25'], d['bb_sigma'] or 0, d['rsi'] or 0))


TECH_CARD_CSS = r"""
.tc-svg{width:100%;height:auto;display:block;border:1px solid var(--border);border-radius:9px;background:#0f1220}
.tc-leg{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--sub);margin:6px 2px 10px}
.tc-leg i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-right:5px;vertical-align:middle}
.tc-tbl{width:100%;border-collapse:collapse}
.tc-tbl td{padding:8px 6px;border-bottom:1px solid rgba(38,44,58,.5);font-size:13px;vertical-align:top}
.tc-tbl td.v{text-align:right;font-family:'DM Mono',monospace;white-space:nowrap;color:var(--text)}
.tc-tbl td.r{color:var(--sub);font-size:12px}
.tc-hi{color:#fca5a5}.tc-lo{color:#86efac}
.tc-note{font-size:11px;color:var(--sub);line-height:1.6;margin:10px 2px 0}
"""

TECH_CARD_JS = r"""
function tcN(n){return Math.round(n).toLocaleString();}
function tcChart(D){
  var S=D.series,n=S.length,W=360,H=170,L=6,R=6,T=10,B=20,lo=1e12,hi=0;
  for(var i=0;i<n;i++){lo=Math.min(lo,S[i].lo,S[i].c);hi=Math.max(hi,S[i].up,S[i].c);}
  var x=function(i){return L+i*(W-L-R)/(n-1);},y=function(v){return T+(1-(v-lo)/(hi-lo))*(H-T-B);};
  var line=function(k,col,w,dash){var p=[];for(var i=0;i<n;i++)p.push(x(i).toFixed(1)+','+y(S[i][k]).toFixed(1));
    return '<polyline points="'+p.join(' ')+'" fill="none" stroke="'+col+'" stroke-width="'+w+'"'+(dash?' stroke-dasharray="3,3"':'')+'/>';};
  var band=[];for(var i=0;i<n;i++)band.push(x(i).toFixed(1)+','+y(S[i].up).toFixed(1));
  for(var i=n-1;i>=0;i--)band.push(x(i).toFixed(1)+','+y(S[i].lo).toFixed(1));
  var s='<svg class="tc-svg" viewBox="0 0 '+W+' '+H+'"><polygon points="'+band.join(' ')+'" fill="rgba(129,140,248,.10)"/>'
    +line('up','#6366f1',1,true)+line('lo','#6366f1',1,true)+line('ma25','#fbbf24',1.4)+line('c','#e2e2f0',1.8);
  for(var i=0;i<n;i+=Math.ceil(n/5)){var d=S[i].d;s+='<text x="'+x(i).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="9" fill="#8888aa">'+(+d.slice(4,6))+'/'+(+d.slice(6))+'</text>';}
  return s+'</svg>';
}
function tcBuild(){
  var D=window.TECH_DATA;if(!D)return '<div class="insight">終値の蓄積が足りません</div>';
  var h=tcChart(D);
  h+='<div class="tc-leg"><span><i style="background:#e2e2f0"></i>日経平均</span><span><i style="background:#fbbf24"></i>25日移動平均</span><span><i style="background:#6366f1"></i>ボリンジャー±2σ（20日）</span></div>';
  var rs=D.rsi,rsT=rs>=70?'<span class="tc-hi">買われすぎの目安（70以上）</span>':rs<=30?'<span class="tc-lo">売られすぎの目安（30以下）</span>':'中立（30〜70）';
  var bs=D.bb_sigma,bsT=bs>=2?'<span class="tc-hi">+2σ超え</span>':bs<=-2?'<span class="tc-lo">−2σ割れ</span>':'±2σの内側';
  h+='<table class="tc-tbl">'
    +'<tr><td>終値</td><td class="v">'+tcN(D.close)+'</td><td class="r">直近20日の高値 '+tcN(D.hi20)+' ／ 安値 '+tcN(D.lo20)+'</td></tr>'
    +'<tr><td>5日移動平均</td><td class="v">'+tcN(D.ma5)+'</td><td class="r">乖離 '+(D.dev5>=0?'+':'')+D.dev5.toFixed(1)+'%</td></tr>'
    +'<tr><td>25日移動平均</td><td class="v">'+tcN(D.ma25)+'</td><td class="r">乖離 '+(D.dev25>=0?'+':'')+D.dev25.toFixed(1)+'%</td></tr>'
    +'<tr><td>ボリンジャー（20日）</td><td class="v">'+(bs>=0?'+':'')+bs.toFixed(2)+'σ</td><td class="r">'+bsT+'：中心 '+tcN(D.bb_mid)+'、±2σ '+tcN(D.bb_mid-2*D.bb_sd)+'〜'+tcN(D.bb_mid+2*D.bb_sd)+'</td></tr>'
    +'<tr><td>RSI（14日）</td><td class="v">'+rs.toFixed(0)+'</td><td class="r">'+rsT+'</td></tr>'
    +'</table>';
  h+='<div class="tc-note">日経平均の現物終値（毎営業日）から計算。高値・安値を使う指標（ピボットなど）は、日中の高値・安値が取れないため載せていません。テクニカル指標は過去の値動きの要約で、方向を保証するものではありません。</div>';
  return h;
}
"""
