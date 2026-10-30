#!/usr/bin/env python3
"""Futures volume by participant, all four session files, with history.

The old 大口 card ranked brokers by day-session J-NET volume only, so retail
mini flow (SBI / 楽天 crossing tens of thousands of lots) sat on top and the
institutional blocks were buried. This collects, per broker and per product
(large / mini / TOPIX), the volume through J-NET (off-auction blocks: the
大口の相対取引) and through the auction, day + night, and keeps a daily
history so a broker's block volume can be compared with its own normal level.

Volume has NO buy/sell side. It shows who was active and how unusually so,
never direction.

Output data/fut_brokers.json:
    {"dates": [...], "rows": {date: {broker: {"cat": str,
        "j": {"large", "mini", "topix"}, "a": {"large", "mini", "topix"}}}}}
"""
import argparse
import io
import json
import os
import re
import subprocess

import openpyxl

from extract_jnet import _classify

PRODUCTS = {'NK225F': 'large', 'NK225MF': 'mini', 'TOPIXF': 'topix'}
# (filename suffix, venue): 'j' = J-NET blocks, 'a' = auction
FILES = (('_volume_by_participant_whole_day_J-NET.xlsx', 'j'),
         ('_volume_by_participant_night_J-NET.xlsx', 'j'),
         ('_volume_by_participant_whole_day.xlsx', 'a'),
         ('_volume_by_participant_night.xlsx', 'a'))
KEEP = 60


def parse(src):
    """{broker: {product: volume}} for futures rows of one participant file."""
    wb = openpyxl.load_workbook(io.BytesIO(src) if isinstance(src, bytes) else src,
                                read_only=True, data_only=True)
    out = {}
    for r in wb.worksheets[0].iter_rows(values_only=True):
        r = [c for c in r if c is not None]
        if len(r) < 7:
            continue
        prod = PRODUCTS.get(str(r[0]).strip())
        if not prod:
            continue
        try:
            vol = float(r[-1])
        except (TypeError, ValueError):
            continue
        b = out.setdefault(str(r[5]).strip(), {})
        b[prod] = b.get(prod, 0) + vol
    return out


def _add(row, venue, parsed):
    for broker, prods in parsed.items():
        cell = row.setdefault(broker, {'cat': _classify(broker), 'j': {}, 'a': {}})
        for prod, v in prods.items():
            cell[venue][prod] = int(cell[venue].get(prod, 0) + v)


def _load(path):
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d.get('rows'), dict):
                return d
        except Exception:
            pass
    return {'dates': [], 'rows': {}}


def _backfill_git(flow, repo_root):
    """One-off: rebuild past days from participant files still in git history."""
    found = {}  # date -> {suffix: (sha, path)}
    for suffix, _ in FILES:
        try:
            log = subprocess.check_output(
                ['git', '-C', repo_root, 'log', '--diff-filter=A', '--format=%H', '--name-only',
                 '--', 'data/*' + suffix], text=True)
        except (OSError, subprocess.CalledProcessError) as e:
            print('[fut_brokers] git backfill skipped: %s' % e)
            return
        sha = None
        for ln in log.splitlines():
            ln = ln.strip()
            if re.fullmatch(r'[0-9a-f]{40}', ln):
                sha = ln
            elif sha and ln.endswith(suffix):
                m = re.search(r'(\d{8})' + re.escape(suffix) + '$', ln)
                if m:
                    found.setdefault(m.group(1), {}).setdefault(suffix, (sha, ln))
    for dt, files in sorted(found.items()):
        if dt in flow['rows'] or len(files) < len(FILES):
            continue  # keep only days with all four sessions, so totals compare
        row = {}
        try:
            for suffix, venue in FILES:
                sha, path = files[suffix]
                blob = subprocess.check_output(['git', '-C', repo_root, 'show', '%s:%s' % (sha, path)])
                _add(row, venue, parse(blob))
        except Exception as e:
            print('[fut_brokers] backfill %s failed: %s' % (dt, e))
            continue
        flow['rows'][dt] = row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data')
    ap.add_argument('--out', default=None, help='default: <data-dir>/fut_brokers.json')
    ap.add_argument('--backfill-git', action='store_true')
    a = ap.parse_args()
    out = a.out or os.path.join(a.data_dir, 'fut_brokers.json')
    flow = _load(out)

    # Today = the newest date for which all four session files are present.
    dates = {}
    for fn in os.listdir(a.data_dir):
        for suffix, _ in FILES:
            m = re.fullmatch(r'(\d{8})' + re.escape(suffix), fn)
            if m:
                dates.setdefault(m.group(1), set()).add(suffix)
    complete = sorted(dt for dt, s in dates.items() if len(s) == len(FILES))
    if complete:
        today = complete[-1]
        row = {}
        for suffix, venue in FILES:
            _add(row, venue, parse(os.path.join(a.data_dir, today + suffix)))
        flow['rows'][today] = row
    else:
        print('[fut_brokers] no date with all four participant files; history unchanged')

    if a.backfill_git:
        _backfill_git(flow, os.path.dirname(os.path.abspath(a.data_dir)))

    keep = sorted(flow['rows'])[-KEEP:]
    flow = {'dates': keep, 'rows': {dt: flow['rows'][dt] for dt in keep}}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(flow, f, ensure_ascii=False, separators=(',', ':'))
    print('[fut_brokers] wrote %s | %d days | latest %s'
          % (out, len(keep), keep[-1] if keep else '-'))


if __name__ == '__main__':
    main()
