#!/usr/bin/env python3
"""Card: expected price range implied by ATM IV (σレンジ).

Volatility is a standard deviation, so the ATM IV of the front expiry is a
direct statement about how wide the market expects the next day / week / month
to be. This card converts the annualised number into the horizons a trader
actually acts on, prices them off the current spot, and puts the strikes that
carry real open interest on the same σ scale — so "60,000のプット" becomes
"SQまでで−2.3σ" rather than just a number far below the market.

Two honesty guards are built into the card rather than left to the reader:
  * IV is a forecast of dispersion, not a promise — the ±1σ band is expected to
    be broken about a third of the time, and the tails of index returns are
    fatter than the normal distribution assumed here.
  * The realised volatility of the last 20 sessions is shown next to the IV, so
    the reader can see whether the market is charging above or below what the
    index has actually been doing.
"""

import json
import math


RANGE_CARD_CSS = r"""
.rg-sec{font-family:Outfit;font-weight:600;color:var(--sub);font-size:12px;margin:2px 2px 8px}
.rg-tbl{width:100%;border-collapse:collapse;font-size:12px;margin-bottom:10px}
.rg-tbl th{color:var(--sub);font-weight:600;text-align:right;padding:6px 6px;border-bottom:1px solid var(--border);font-size:11px}
.rg-tbl th:first-child{text-align:left}
.rg-tbl td{padding:7px 6px;border-bottom:1px solid rgba(38,44,58,.5);text-align:right;font-family:'DM Mono',monospace;white-space:nowrap}
.rg-tbl td:first-child{text-align:left;font-family:inherit}
.rg-hi{color:#86efac}
.rg-lo{color:#fca5a5}
.rg-2s{color:var(--sub);font-size:11px}
.rg-row-sq td{background:rgba(129,140,248,.12)}
.rg-k{display:flex;justify-content:space-between;gap:8px;padding:5px 6px;border-bottom:1px solid rgba(38,44,58,.5);font-size:12px}
.rg-k span:first-child{font-family:'DM Mono',monospace}
.rg-sig{font-family:'DM Mono',monospace}
.rg-in{color:#86efac}
.rg-out{color:var(--sub)}
.rg-far{color:#fca5a5}
.rg-note{font-size:11px;color:var(--sub);line-height:1.55;margin:10px 2px 2px}
.rg-lvl{display:flex;gap:10px;align-items:center;font-size:13px;line-height:1.7;color:var(--text);border:1px solid var(--border);border-radius:9px;padding:9px 11px;margin:0 0 12px;background:#141822}
.rg-lvl svg{flex:none}
.rg-warn{font-size:11px;color:#fcd34d;line-height:1.55;margin:8px 2px 2px}
"""


RANGE_CARD_JS = r"""
function rgNum(n){ return (n===null||n===undefined)?'—':Math.round(Number(n)).toLocaleString(); }
function rgPct(x){ return (x===null||x===undefined)?'—':(Number(x).toFixed(1)+'%'); }
function rgBuild(){
  var D = window.RANGE_DATA || null;
  if(!D || !D.spot || !D.iv){ return '<div class="insight">IVデータ未取込</div>'; }
  var h = '';
  if(D.iv_hist && D.iv_hist.length >= 5 && D.iv_hi > D.iv_lo){
    var pos = (D.iv - D.iv_lo) / (D.iv_hi - D.iv_lo);
    var lvl = pos >= 0.67 ? '<b class="rg-far">高め</b>' : (pos <= 0.33 ? '<b class="rg-in">低め</b>' : '<b>中ほど</b>');
    var gap = (D.hv ? D.iv - D.hv : null), edge = '';
    if(gap !== null){ edge = gap >= 2 ? '実際の値動きより<b class="rg-far">割高</b>（売り手に有利）' : (gap <= -2 ? '実際の値動きより<b class="rg-in">割安</b>（売り手に不利）' : '実際の値動きと<b>ほぼ同じ</b>（売りの優位は薄い）'); }
    var n = D.iv_hist.length, W = 120, H = 30, pts = [];
    for(var q=0;q<n;q++){ pts.push((q*(W-4)/(n-1)+2).toFixed(1)+','+(H-3-(D.iv_hist[q]-D.iv_lo)/(D.iv_hi-D.iv_lo)*(H-6)).toFixed(1)); }
    h += '<div class="rg-lvl"><svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'"><polyline points="'+pts.join(' ')+'" fill="none" stroke="#818cf8" stroke-width="1.6"/>'
       + '<circle cx="'+pts[n-1].split(',')[0]+'" cy="'+pts[n-1].split(',')[1]+'" r="2.6" fill="#fbbf24"/></svg>'
       + '<div>IVの水準：<b>'+rgPct(D.iv)+'</b>は直近'+n+'日（'+rgPct(D.iv_lo)+'〜'+rgPct(D.iv_hi)+'）の中で'+lvl+'。'
       + (edge ? '実現ボラ'+rgPct(D.hv)+'との差は'+(gap>=0?'+':'')+gap.toFixed(1)+'ptで、'+edge+'。' : '') + '</div></div>';
  }
  if(D.regime){
    var rt = D.regime==='neg' ? '値動きが<b class="rg-far">加速しやすい</b>（3つの計算方法すべてマイナス）'
           : D.regime==='pos' ? '値動きが<b class="rg-in">落ち着きやすい</b>（3つの計算方法すべてプラス）'
           : '計算方法によって判断が<b>割れている</b>';
    h += '<div class="rg-lvl"><div>地合い：'+rt+'。'
       + (D.flip ? '境目（ゼロガンマ）は<b>'+rgNum(D.flip)+'</b>（現値の'+(D.flip>=D.spot?'+':'')+rgNum(D.flip-D.spot)+'）で、'+(D.flip>D.spot?'これを上に抜けると':'これを下に割ると')+'地合いが切り替わりやすい。' : '')
       + '</div></div>';
  }
  h += '<div class="rg-sec">'+D.expiry_label+'のATM IV '+rgPct(D.iv)+' から見た想定レンジ（現値 '+rgNum(D.spot)+'）</div>';
  h += '<table class="rg-tbl"><thead><tr><th>期間</th><th>±1σ</th><th>下限</th><th>上限</th><th>±2σ</th></tr></thead><tbody>';
  for(var i=0;i<D.rows.length;i++){
    var r = D.rows[i];
    h += '<tr class="'+(r.is_sq?'rg-row-sq':'')+'">'
       + '<td>'+r.label+'</td>'
       + '<td>'+rgPct(r.pct)+'</td>'
       + '<td class="rg-lo">'+rgNum(r.low)+'</td>'
       + '<td class="rg-hi">'+rgNum(r.high)+'</td>'
       + '<td class="rg-2s">'+rgNum(r.low2)+' 〜 '+rgNum(r.high2)+'</td></tr>';
  }
  h += '</tbody></table>';
  if(D.strikes && D.strikes.length){
    h += '<div class="rg-sec">建玉の大きい行使価格はSQまでで何σか（建玉の大きい順）</div>';
    for(var j=0;j<D.strikes.length;j++){
      var s = D.strikes[j];
      var cls = (Math.abs(s.sigma) <= 1) ? 'rg-in' : (Math.abs(s.sigma) <= 2 ? 'rg-out' : 'rg-far');
      h += '<div class="rg-k"><span>'+s.side+rgNum(s.strike)+'（建玉 '+rgNum(s.oi)+'）</span>'
         + '<span class="rg-sig '+cls+'">'+(s.sigma>0?'+':'')+s.sigma.toFixed(2)+'σ ／ '+(s.dist>0?'+':'')+rgPct(s.dist)+'</span></div>';
    }
  }
  h += '<div class="rg-note">年率のIVを期間に直す式は σ×√(期間/年)。日次は√250、週次は√52、月次は√12で割った値、SQまでは残存日数（暦日）で計算しています。'
     + '±1σの中に収まる確率がおよそ<b>68%</b>、±2σでおよそ<b>95%</b>です。'
     + (D.hv ? ('実現ボラ（直近'+D.hv_n+'営業日のHV）は<b>'+rgPct(D.hv)+'</b>で、IVとの差は<b>'+((D.iv-D.hv)>=0?'+':'')+rgPct(D.iv-D.hv)+'</b>。'
         + 'IVが上ならオプションは実際の値動きより高く値付けされている状態です。') : '実現ボラ（HV）は終値の蓄積が足りず今回は非表示です。')
     + '</div>';
  h += '<div class="rg-warn">※これは「この範囲に収まる」という予想ではありません。±1σは<b>3回に1回は外れる前提</b>の幅で、株価指数の分布は正規分布より裾が厚く、急落時は2σも簡単に超えます。レンジの目安であって、売買の判断そのものではありません。</div>';
  return h;
}
"""


def _hv(closes, n=20):
    """Annualised realised volatility from the last n closes (250-day year).

    Returns (hv, sessions_used) or (None, 0) when there are too few closes —
    the card then simply omits the comparison rather than printing a 0.
    """
    cs = [c for c in (closes or []) if c]
    if len(cs) < 6:
        return None, 0
    cs = cs[-(n + 1):]
    rets = [math.log(cs[i] / cs[i - 1]) for i in range(1, len(cs)) if cs[i - 1]]
    if len(rets) < 5:
        return None, 0
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(250) * 100, len(rets)


def _close_series(greeks, oi_ts, ghist):
    """Index closes by date, from whichever store has them.

    greeks.json's regime_history and greeks_history both carry the spot used on
    each run, and oi_timeseries carries the close it was given. We merge them by
    date so the realised-vol window is as long as the data allows.
    """
    by_date = {}
    for r in ((greeks or {}).get('regime_history') or []):
        if r.get('date') and r.get('spot'):
            by_date[r['date']] = r['spot']
    for d, v in ((ghist or {}) if isinstance(ghist, dict) else {}).items():
        if isinstance(v, dict) and v.get('spot'):
            by_date[d] = v['spot']
    ot = oi_ts or {}
    dates, closes = ot.get('dates') or [], ot.get('nikkei')
    if isinstance(closes, dict):
        closes = closes.get('close') or closes.get('values') or []
    if isinstance(closes, list) and len(closes) == len(dates):
        for d, c in zip(dates, closes):
            if c:
                by_date.setdefault(d, c)
    return [by_date[d] for d in sorted(by_date)]


def build_range(greeks, ivts, oi_ts, ghist=None, top_n=8, closes=None):
    """Assemble the card payload. Returns None when the inputs are not there."""
    if not greeks or not greeks.get('expiries'):
        return None
    e = greeks['expiries'][0]
    spot = greeks.get('spot')
    iv = None
    series = []
    try:
        series = [x for x in ((ivts or {}).get('atm_iv', {}).get(e.get('expiry')) or []) if x]
        if series:
            iv = series[-1]
    except Exception:
        iv = None
    if not spot or not iv:
        return None

    t_days = e.get('T_days') or 0
    horizons = [
        ('1日', 1.0 / 250, False),
        ('1週間', 1.0 / 52, False),
        ('1か月', 1.0 / 12, False),
    ]
    if t_days:
        horizons.append(('SQまで（%d日）' % t_days, t_days / 365.0, True))

    rows = []
    for label, t, is_sq in horizons:
        pct = iv * math.sqrt(t)
        rows.append({
            'label': label, 'pct': pct, 'is_sq': is_sq,
            'low': spot * (1 - pct / 100), 'high': spot * (1 + pct / 100),
            'low2': spot * (1 - 2 * pct / 100), 'high2': spot * (1 + 2 * pct / 100),
        })

    sq_pct = (iv * math.sqrt(t_days / 365.0)) if t_days else None
    strikes = []
    if sq_pct:
        cand = []
        for r in (e.get('per_strike') or []):
            k = r.get('strike')
            if not k:
                continue
            for side, oi in (('P', r.get('put_oi') or 0), ('C', r.get('call_oi') or 0)):
                # only the side that is OTM — that is where the wall matters
                if (side == 'P' and k < spot) or (side == 'C' and k > spot):
                    cand.append((oi, side, k))
        cand.sort(reverse=True)
        for oi, side, k in cand[:top_n]:
            dist = (k - spot) / spot * 100
            strikes.append({'side': side, 'strike': k, 'oi': oi,
                            'dist': dist, 'sigma': dist / sq_pct})

    # Prefer the complete daily cash-close series (futures_flow.json). The
    # merged fallback skips days the pipeline did not run (10/19, 10/22, ...)
    # and mixes in futures closes, which overstated HV (32% vs 27.6% on 10/30).
    hv, hv_n = _hv(closes if closes else _close_series(greeks, oi_ts, ghist))
    # Where today's IV sits in its own recent range: this replaces the
    # separate IV推移 card, whose only trading use was "is IV high or low now".
    recent = series[-20:]
    # 相場の地合い in one line (replaces the separate GEX card): the sign of
    # dealer gamma under the three conventions, and the price where it flips.
    signs = [((e.get('net_' + k) or {}).get('gamma')) for k in ('A', 'B', 'B2')]
    signs = [g for g in signs if g is not None]
    regime = ('neg' if signs and all(g < 0 for g in signs) else
              'pos' if signs and all(g > 0 for g in signs) else 'mixed' if signs else None)
    flip = (e.get('zero_gamma_A') or {}).get('flip')
    return {
        'regime': regime, 'flip': flip,
        'spot': spot, 'iv': iv, 'hv': hv, 'hv_n': hv_n,
        'iv_hist': recent, 'iv_lo': min(recent) if recent else None,
        'iv_hi': max(recent) if recent else None,
        'expiry_label': e.get('label') or '',
        'rows': rows, 'strikes': strikes,
    }


def range_data_script(greeks, ivts, oi_ts, ghist=None, closes=None):
    d = build_range(greeks, ivts, oi_ts, ghist, closes=closes)
    if not d:
        return ''
    # Bare JS, no <script> wrapper: this is injected INSIDE the dashboard's
    # single script block, and a nested <script> tag would close it early.
    return ('window.RANGE_DATA = %s;\n'
            % json.dumps(d, ensure_ascii=False, separators=(',', ':')))


def preview_range(greeks, ivts, oi_ts):
    d = build_range(greeks, ivts, oi_ts)
    if not d:
        return '<span class="mm-label">IVレンジ 未取込</span>'
    day = d['rows'][0]
    sq = d['rows'][-1]
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">1日の想定値幅（±1σ）</div>'
            '<div class="mm-value">±%.1f%%</div></div>'
            '<div class="mini-metric"><div class="mm-label">%s</div>'
            '<div class="mm-value" style="font-size:12px">%s 〜 %s</div></div>'
            '</div>' % (day['pct'], sq['label'],
                        format(int(round(sq['low'])), ','),
                        format(int(round(sq['high'])), ',')))


def detail_range_js(greeks):
    if not greeks:
        return "return '<div class=\\'insight\\'>データなし</div>';"
    return "return rgBuild();"
