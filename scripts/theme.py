#!/usr/bin/env python3
"""Warm light theme (ウォームライト), applied to finished HTML.

Every card was written for a dark background, and many colours live in inline
styles, in JS that builds HTML on click, and in SVG attributes, not only in
CSS variables. Rather than rewriting each card, the page is re-coloured as a
whole: each colour keeps its hue, its lightness is inverted (dark surfaces
become light, pale text becomes dark), near-white surfaces lose most of their
tint and are blended toward cream.

Applying the transform twice would undo it, so a themed page is marked and
warm() leaves marked pages alone. warm_fragment() is for snippets inserted into
an already themed page (the archive entry).

Usage as a script: python scripts/theme.py FILE... (themes files in place)
"""

import colorsys
import re
import sys

MARKER = '<!--theme:warm-->'
CREAM = (0.988, 0.965, 0.918)
CARD = (222, 222, 222)   # darkest themed surface (table headers); text must read on it
MIN_RATIO = 4.6          # WCAG AA for body text, with a little margin
# Rules added after re-colouring: white text that sat on a coloured fill
# (strong table cells, accent buttons) stays white, because the fill turns
# dark too and inverting the text would leave dark on dark.
EXTRA_CSS = ('<style>.wt-cell-pos-strong,.wt-cell-neg-strong,.latest-btn,.btn:not(.btn-outline),'
             'a[style*="background:var(--accent)"]{color:#fff!important}</style>')


def _lum(c):
    v = [x / 255 for x in c]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


_HEX = re.compile(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b(?![0-9a-zA-Z_-])')
_RGB = re.compile(r'(rgba?)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[.\d]+)?\)')


def _rgb(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    l = 1 - l
    if l < 0.5:
        l *= 0.85        # text and accents: dark enough on a light page
    if l > 0.8:
        s *= 0.25        # surfaces: neutral, not tinted by the old navy
        r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
        m = min(1.0, (l - 0.8) / 0.2) * 0.85
        return tuple(round((x * (1 - m) + c * m) * 255) for x, c in zip((r2, g2, b2), CREAM))
    out = tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, l, s))
    # Text and accent colours (borders sit above 0.6 and are left alone):
    # darken, keeping the hue, until they read on the cream card.
    while l < 0.6 and l > 0.02 and _ratio(out, CARD) < MIN_RATIO:
        l -= 0.02
        out = tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, l, s))
    return out


def _hex(m):
    t = m.group(1)
    if len(t) == 3:
        t = ''.join(c * 2 for c in t)
    return '#%02x%02x%02x' % _rgb(int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))


def _rgbfn(m):
    r, g, b = _rgb(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return '%s(%d,%d,%d%s)' % (m.group(1), r, g, b, m.group(5) or '')


def warm_fragment(text):
    return _RGB.sub(_rgbfn, _HEX.sub(_hex, text))


def warm(html):
    if MARKER in html:
        return html
    out = warm_fragment(html)
    j = out.find('</head>')
    if j >= 0:
        out = out[:j] + EXTRA_CSS + out[j:]
    i = out.find('<head>')
    return (out[:i + 6] + MARKER + out[i + 6:]) if i >= 0 else MARKER + out


if __name__ == '__main__':
    for path in sys.argv[1:]:
        with open(path, encoding='utf-8') as f:
            src = f.read()
        dst = warm(src)
        if dst != src:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(dst)
            print('[theme] warm: %s' % path)
        else:
            print('[theme] already themed: %s' % path)
