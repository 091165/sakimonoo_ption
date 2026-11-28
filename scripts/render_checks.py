#!/usr/bin/env python3
"""Card: 答え合わせ — what each day's Claude analysis said to watch, and how
it turned out the next business day.

Source: the 自己照合 block of data/manual_assessment_YYYYMMDD.md (and the
archived copies in data/assessments/). From 11/13 on, each item carries a
verdict mark:

    自己照合（11/12の注視点）：
    ・① × 「SQは60,000〜61,000付近に引き寄せられやすい」→ 61,000をやや上回って引けた…

    ○ 当たり / △ 一部当たり / × 外れ / － 判定対象外（条件が起きなかった、状態の説明など）

Older files are free text without marks and are skipped.
"""

import glob
import json
import os
import re

HEAD = re.compile(r'^自己照合（(\d{1,2})/(\d{1,2})の注視点）')
ITEM = re.compile(r'^・\s*([①②③④⑤⑥⑦⑧⑨⑩])\s*([○△×－])\s*「(.+?)」\s*→\s*(.*)$')
MARKS = {'○': 'hit', '△': 'part', '×': 'miss', '－': 'na'}


def _files(data_dir):
    fs = glob.glob(os.path.join(data_dir, 'manual_assessment_*.md'))
    fs += glob.glob(os.path.join(data_dir, 'assessments', 'manual_assessment_*.md'))
    out = {}
    for f in fs:
        m = re.search(r'manual_assessment_(\d{8})\.md$', f)
        if m:
            out[m.group(1)] = f      # the dated file, not "-1" / "_IV版" variants
    return sorted(out.items())


def build(data_dir='data'):
    days = []
    for date, f in _files(data_dir):
        try:
            lines = open(f, encoding='utf-8').read().splitlines()
        except Exception:
            continue
        # A file can hold several blocks: the previous day's points, and
        # 「M/Dの注視点・持ち越し」 for conditional points from earlier days whose
        # condition was met later (judged on the day it happened).
        block = None
        for ln in lines:
            t = ln.strip()
            h = HEAD.match(t)
            if h:
                block = {'date': date, 'target': '%s/%s' % (int(h.group(1)), int(h.group(2))),
                         'carry': '持ち越し' in t, 'items': []}
                days.append(block)
                continue
            if block is None:
                continue
            m = ITEM.match(t)
            if m:
                block['items'].append({'n': m.group(1), 'v': MARKS[m.group(2)], 'claim': m.group(3), 'result': m.group(4)})
            elif block['items'] and t and not t.startswith('・'):
                block = None
    days = [d for d in days if d['items']]
    if not days:
        return None
    cnt = {k: sum(1 for d in days for i in d['items'] if i['v'] == k) for k in MARKS.values()}
    judged = cnt['hit'] + cnt['part'] + cnt['miss']
    score = round((cnt['hit'] + 0.5 * cnt['part']) / judged * 100) if judged else None
    return {'days': days[::-1], 'count': cnt, 'judged': judged, 'score': score}


def data_script(data_dir='data'):
    d = build(data_dir)
    return ('window.CK_DATA = %s;\n' % json.dumps(d, ensure_ascii=False, separators=(',', ':'))) if d else ''


def preview(data_dir='data'):
    d = build(data_dir)
    if not d:
        return None
    c = d['count']
    return ('<div class="mini-metrics">'
            '<div class="mini-metric"><div class="mm-label">判定（%d件）</div><div class="mm-value" style="font-size:14px">'
            '<span class="ck-hit">○%d</span> <span class="ck-part">△%d</span> <span class="ck-miss">×%d</span></div></div>'
            '<div class="mini-metric"><div class="mm-label">的中率</div><div class="mm-value">%s</div></div></div>'
            % (d['judged'], c['hit'], c['part'], c['miss'], ('%d%%' % d['score']) if d['score'] is not None else '—'))


CK_CARD_CSS = r"""
.ck-hit{color:#16a34a;font-weight:700}.ck-part{color:#d97706;font-weight:700}.ck-miss{color:#dc2626;font-weight:700}.ck-na{color:var(--sub);font-weight:700}
.ck-sum{display:flex;gap:14px;flex-wrap:wrap;align-items:baseline;margin:0 2px 8px;font-size:13px}
.ck-sum b{font-size:18px;font-family:'DM Mono',monospace}
.ck-def{font-size:12px;color:var(--sub);line-height:1.7;margin:0 2px 10px}
.ck-day{border:1px solid var(--border);border-radius:8px;padding:8px 10px;margin:0 0 8px}
.ck-dh{font-size:12px;color:var(--sub);margin-bottom:4px}
.ck-dh b{color:var(--text)}
.ck-it{display:grid;grid-template-columns:22px 1fr;gap:2px 6px;padding:4px 0;border-top:1px dashed rgba(127,127,127,.25)}
.ck-it:first-of-type{border-top:0}
.ck-m{font-size:15px;text-align:center;line-height:1.3}
.ck-c{font-size:13px;line-height:1.5}
.ck-r{grid-column:2;font-size:12px;color:var(--sub);line-height:1.6}
"""

CK_CARD_JS = r"""
function ckE(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function ckBuild(){
  var D=window.CK_DATA;if(!D) return '<div class="insight">データなし</div>';
  var sym={hit:'○',part:'△',miss:'×',na:'－'},c=D.count;
  var o='<div class="ck-sum"><span>判定 <b>'+D.judged+'</b>件</span>'
    +'<span class="ck-hit">○ '+c.hit+'</span><span class="ck-part">△ '+c.part+'</span><span class="ck-miss">× '+c.miss+'</span>'
    +'<span class="ck-na">－ '+c.na+'</span>'+(D.score!==null?'<span>的中率 <b>'+D.score+'%</b></span>':'')+'</div>';
  o+='<div class="ck-def">Claudeの分析で挙げた注目点が、次の営業日にどうなったかの記録です。'
    +'<span class="ck-hit">○</span> 当たり、<span class="ck-part">△</span> 一部当たり、<span class="ck-miss">×</span> 外れ、'
    +'<span class="ck-na">－</span> 判定対象外（条件が起きなかった・状態の説明など）。的中率は ○＝1、△＝0.5 として、○△×の件数で割っています。</div>';
  D.days.forEach(function(d){
    var ds=(+d.date.slice(4,6))+'/'+(+d.date.slice(6));
    o+='<div class="ck-day"><div class="ck-dh"><b>'+d.target+'</b>の注目点'+(d.carry?'（持ち越し：条件がこの日に成立）':'')+' → <b>'+ds+'</b>の結果</div>';
    d.items.forEach(function(it){
      o+='<div class="ck-it"><div class="ck-m ck-'+it.v+'">'+sym[it.v]+'</div><div class="ck-c">'+it.n+' '+ckE(it.claim)+'</div>'
        +'<div class="ck-r">'+ckE(it.result)+'</div></div>';
    });
    o+='</div>';
  });
  return o+'<div class="ck-def" style="margin-top:6px">11/13以降の分析から記録しています。それより前の自己照合は判定記号の無い文章のため入っていません。</div>';
}
"""
