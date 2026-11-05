#!/usr/bin/env python3
"""
JPX Market Analysis - Raw data collector (fetch_jpx.py)
=======================================================
Downloads the JPX files the pipeline reads into data/, so nobody has to
download and push them by hand.

How it finds the files
----------------------
JPX publishes each file as a link on a listing page. Instead of hard-coding
the file URLs (their folder names change), this script reads the listing
pages and picks the links whose *file name* matches a known pattern:

    ose<YYYYMMDD>tp.zip / .csv                        option theoretical prices
    <YYYYMMDD>open_interest.xlsx                      open interest
    <YYYYMMDD>_volume_by_participant_*.xlsx           volume by participant (4 files)
    <YYYYMMDD>_derivatives_market_data_whole_day.xlsx market data
    <YYYYMMDD>_nk225op_oi_by_tp.xlsx                  weekly option OI by participant
    <YYYYMMDD>_indexfut_oi_by_tp.xlsx                 weekly futures OI by participant

It starts from the known listing pages (SEED_PAGES). If a file type is not
found there, it follows links under /markets/derivatives/ (a few dozen pages
at most, one request per second) until every type is found.

Which files it downloads
------------------------
Daily files: every file of the newest date published on the site, if that date
is newer than the date the site was last built from (data/data.json). With
--require (default: open_interest, jnet, tp) the run counts as "ready" only when
those types exist for that date; otherwise nothing is kept so a later run can
pick up the complete set.
Weekly files: the newest week, if not already in data/.

Writes new_files, new_weekly, data_date and daily_status (ready / incomplete /
up_to_date / nothing) to $GITHUB_OUTPUT when set.

Usage:
    python scripts/fetch_jpx.py --datadir data
    python scripts/fetch_jpx.py --datadir data --date 20261104   # a given day
    python scripts/fetch_jpx.py --datadir data --dry-run         # list only
"""

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import deque
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen

BASE = 'https://www.jpx.co.jp'
CRAWL_PREFIX = '/markets/derivatives/'

# Known listing pages, visited first.
SEED_PAGES = [
    '/markets/derivatives/option-price/index.html',
    '/markets/derivatives/open-interest/index.html',
    '/markets/derivatives/participant-volume/index.html',
    '/markets/derivatives/trading-volume/index.html',
    '/markets/derivatives/participant-open-interest/index.html',
    '/markets/derivatives/index.html',
]

# type -> (regex on the file name, daily?)  The first group is the date.
TARGETS = {
    'tp': (re.compile(r'^ose(\d{8})tp\.(?:zip|csv)$', re.I), True),
    'open_interest': (re.compile(r'^(\d{8})_?open_interest\.xlsx$', re.I), True),
    'jnet': (re.compile(r'^(\d{8})_volume_by_participant_whole_day_J-NET\.xlsx$', re.I), True),
    'volume': (re.compile(r'^(\d{8})_volume_by_participant_(?:whole_day|night)(?:_J-NET)?\.xlsx$', re.I), True),
    'market_data': (re.compile(r'^(\d{8})_derivatives_market_data_whole_day\.xlsx$', re.I), True),
    'op_weekly': (re.compile(r'^(\d{8})_nk225op_oi_by_tp\.xlsx$', re.I), False),
    'fut_weekly': (re.compile(r'^(\d{8})_indexfut_oi_by_tp\.xlsx$', re.I), False),
}

USER_AGENT = 'Mozilla/5.0 (compatible; sakimonoo-ption-collector/1.0)'
DELAY_SEC = 1.0


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != 'a':
            return
        for k, v in attrs:
            if k.lower() == 'href' and v:
                self.links.append(v.strip())


class Fetcher:
    def __init__(self, delay=DELAY_SEC, timeout=30, retries=3):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self._last = 0.0

    def get(self, url):
        for attempt in range(self.retries):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                req = Request(url, headers={'User-Agent': USER_AGENT,
                                            'Accept-Language': 'ja,en;q=0.8'})
                with urlopen(req, timeout=self.timeout) as resp:
                    return resp.read()
            except HTTPError as e:
                if e.code in (403, 404, 410):
                    print('[fetch] %s -> HTTP %s' % (url, e.code), file=sys.stderr)
                    return None
                err = e
            except (URLError, OSError) as e:
                err = e
            print('[fetch] %s failed (%s), retry %d' % (url, err, attempt + 1), file=sys.stderr)
            time.sleep(2 ** (attempt + 1))
        return None


def file_name(url):
    return unquote(os.path.basename(urlparse(url).path))


def classify(name):
    """Return [(type, date)] for a file name (volume files also count as jnet)."""
    out = []
    for t, (rx, _daily) in TARGETS.items():
        m = rx.match(name)
        if m:
            out.append((t, m.group(1)))
    return out


def discover(fetcher, base, max_pages, need_types):
    """Crawl listing pages; return {type: {date: set(urls)}}."""
    found = {t: {} for t in TARGETS}
    seen = set()
    queue = deque(urljoin(base, p) for p in SEED_PAGES)
    pages = 0
    host = urlparse(base).netloc

    while queue and pages < max_pages:
        page = queue.popleft()
        page = page.split('#')[0]
        if page in seen:
            continue
        seen.add(page)
        body = fetcher.get(page)
        pages += 1
        if body is None:
            continue
        parser = LinkParser()
        try:
            parser.feed(body.decode('utf-8', errors='replace'))
        except Exception as e:  # malformed HTML: use what was parsed
            print('[parse] %s: %s' % (page, e), file=sys.stderr)
        for href in parser.links:
            url = urljoin(page, href).split('#')[0]
            pu = urlparse(url)
            if pu.netloc != host:
                continue
            name = file_name(url)
            for t, d in classify(name):
                found[t].setdefault(d, set()).add(url)
            if (pu.path.startswith(CRAWL_PREFIX)
                    and (pu.path.endswith('.html') or pu.path.endswith('/'))
                    and url not in seen):
                queue.append(url)
        if all(found[t] for t in need_types):
            break

    print('[crawl] visited %d page(s)' % pages)
    for t in TARGETS:
        dates = sorted(found[t])
        print('[crawl] %-13s %s' % (t, ('latest %s (%d dates)' % (dates[-1], len(dates))) if dates else 'not found'))
    return found


def local_name(url):
    """Name the file is saved under in data/ (tp zips are saved as the csv)."""
    name = file_name(url)
    if name.lower().endswith('tp.zip'):
        return name[:-4] + '.csv'
    return name


def save(fetcher, url, datadir):
    name = local_name(url)
    dest = os.path.join(datadir, name)
    body = fetcher.get(url)
    if body is None:
        return None
    if file_name(url).lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                csvs = [n for n in z.namelist() if n.lower().endswith('.csv')]
                if not csvs:
                    print('[save] no csv inside %s' % url, file=sys.stderr)
                    return None
                body = z.read(csvs[0])
        except zipfile.BadZipFile:
            print('[save] bad zip %s' % url, file=sys.stderr)
            return None
    elif name.lower().endswith('.xlsx') and not body.startswith(b'PK'):
        # An HTML error page served with 200 would break openpyxl later.
        print('[save] %s is not an xlsx, skipped' % url, file=sys.stderr)
        return None
    with open(dest, 'wb') as fh:
        fh.write(body)
    print('[save] %s (%d bytes)' % (name, len(body)))
    return dest


def last_built_date(datadir):
    try:
        with open(os.path.join(datadir, 'data.json'), encoding='utf-8') as fh:
            return (json.load(fh).get('metadata') or {}).get('date')
    except Exception:
        return None


def write_output(**kv):
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a') as fh:
        for k, v in kv.items():
            fh.write('%s=%s\n' % (k, v))


def main():
    ap = argparse.ArgumentParser(description='Download JPX raw files into data/')
    ap.add_argument('--datadir', default='data')
    ap.add_argument('--base-url', default=BASE)
    ap.add_argument('--date', default=None, help='daily files of this date (YYYYMMDD) instead of the newest')
    ap.add_argument('--require', default='open_interest,jnet,tp',
                    help='daily types that must exist for the date (comma separated, "" for none)')
    ap.add_argument('--max-pages', type=int, default=40)
    ap.add_argument('--delay', type=float, default=DELAY_SEC)
    ap.add_argument('--force', action='store_true',
                    help='download even if the date is not newer than the last build')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    datadir = args.datadir
    os.makedirs(datadir, exist_ok=True)
    required = [t for t in args.require.split(',') if t]
    for t in required:
        if t not in TARGETS or not TARGETS[t][1]:
            ap.error('unknown daily type in --require: %s' % t)

    fetcher = Fetcher(delay=args.delay)
    found = discover(fetcher, args.base_url, args.max_pages, list(TARGETS))

    # ---- daily files -------------------------------------------------------
    built = last_built_date(datadir)
    if args.date:
        day = args.date
    else:
        # newest date offered by the anchor type (open_interest), else any daily type
        anchor = found['open_interest'] or {}
        dates = sorted(anchor) or sorted({d for t, (_, daily) in TARGETS.items() if daily for d in found[t]})
        day = dates[-1] if dates else None

    to_get = []
    status = 'nothing'
    if day is None:
        print('[daily] no daily files found on the site')
    elif built and day <= built and not args.force and not args.date:
        print('[daily] newest on site %s, site already built from %s: up to date' % (day, built))
        status = 'up_to_date'
    else:
        missing = [t for t in required if day not in found[t]]
        if missing:
            print('[daily] %s: not published yet: %s (waiting for the next run)' % (day, ', '.join(missing)))
            status = 'incomplete'
        else:
            status = 'ready'
            urls = set()
            for t, (_, daily) in TARGETS.items():
                if daily:
                    urls |= found[t].get(day, set())
            to_get += sorted(urls)
            for t, (_, daily) in TARGETS.items():
                if daily and day not in found[t]:
                    print('[daily] %s: optional %s not found' % (day, t))

    # ---- weekly files ------------------------------------------------------
    weekly = set()
    for t in ('op_weekly', 'fut_weekly'):
        if found[t]:
            wk = sorted(found[t])[-1]
            weekly |= found[t][wk]
    to_get += sorted(weekly)
    weekly_names = {local_name(u) for u in weekly}

    new = []
    for url in to_get:
        name = local_name(url)
        if os.path.exists(os.path.join(datadir, name)):
            continue
        if args.dry_run:
            print('[dry-run] would save %s <- %s' % (name, url))
            new.append(name)
            continue
        if save(fetcher, url, datadir):
            new.append(name)

    # A daily set that failed to download part-way is not "ready".
    if status == 'ready' and not args.dry_run:
        for t in required:
            if not any(os.path.exists(os.path.join(datadir, local_name(u))) for u in found[t][day]):
                print('[daily] %s: %s failed to download' % (day, t), file=sys.stderr)
                status = 'incomplete'
        if status == 'incomplete':
            # do not leave a half set behind; the next run downloads it again
            for name in [n for n in new if n not in weekly_names]:
                os.remove(os.path.join(datadir, name))
                new.remove(name)

    new_weekly = len([n for n in new if n in weekly_names])
    print('[done] daily=%s date=%s new_files=%d (weekly %d)' % (status, day, len(new), new_weekly))
    write_output(new_files=len(new), new_weekly=new_weekly, data_date=day or '', daily_status=status)


if __name__ == '__main__':
    main()
