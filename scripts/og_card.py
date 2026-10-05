#!/usr/bin/env python3
"""The link-preview card (og:image) for the evidence page.

A feed shows a preview at about 550 pixels wide, where the page's own diagram
is a texture: its labels cannot be read. So the card redraws the model in five
pieces, large: the devices, the tailnet that denies by default, the one way
into the house, everything else refused, and the cloud account beside it --
not behind the tailnet, because nothing reaches the cloud through it. Icons
and colours are the diagram's own (scripts/evidence_diagram.py).

The figures are read from a built page, the same build the page publishes, and
the script stops if one is missing rather than draw a card the page no longer
supports.

    ./scripts/evidence_page.py --out site
    ./scripts/og_card.py site/index.html og.svg
    qlmanage -t -s 1200 -o . og.svg && sips -c 627 1200 og.svg.png --out scripts/assets/og.png

Rendered by hand on macOS, with no extra tools: Quick Look's thumbnailer
renders into a square, so the 1200x627 card sits centred in a square canvas
and is centre-cropped. Re-run when a figure on it changes.
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evidence_diagram import COL, ICONS  # noqa: E402

FONT = '-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif'
MONO = "Menlo,monospace"
INK, MUT, BG, CARD, LINE = "#1d1d1b", "#5f5e5a", "#fbfaf8", "#ffffff", "#e4e1dc"
GREEN, RED = "#1f7a4d", "#b3261e"
# Not in the diagram's set: a refusal, drawn the same way as its icons.
ICONS = {**ICONS, "refused": '<circle cx="12" cy="12" r="9"/><path d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>'}


def figures(page):
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())

    def need(pattern, what):
        m = re.search(pattern, text)
        if not m:
            sys.exit(f"the page no longer says {what}; not drawing a card that does")
        return m.groups()

    tests, refusals = need(r"(\d+) policy assertions — (\d+) of them refusals", "how many assertions")
    reach, known = need(r"(\d+) of ~(\d+)", "how many devices are reachable")
    (users,) = need(r"(\d+) IAM users", "how many IAM users exist")
    return {"tests": tests, "refusals": refusals, "reach": reach, "known": known, "users": users}


def tile(x, y, icon, colour, size=56):
    s = size / 24 * 0.62
    off = (size - 24 * s) / 2
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="12" fill="{colour}"/>'
            f'<g transform="translate({x + off:.1f},{y + off:.1f}) scale({s:.3f})" fill="none" '
            f'stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>')


def node(x, y, w, h, colour, icons, title, lines, dashed=False):
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{CARD}" stroke="{colour}" stroke-width="3"{dash}/>']
    for i, icon in enumerate(icons):
        out.append(tile(x + 22 + i * 64, y + 22, icon, colour))
    ty = y + 22 + 56 + 38
    out.append(f'<text x="{x + 24}" y="{ty}" font-size="30" font-weight="700" fill="{INK}">{html.escape(title)}</text>')
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + 24}" y="{ty + 34 + i * 30}" font-size="23" fill="{MUT}">{html.escape(line)}</text>')
    return "".join(out)


def side_node(x, y, w, h, colour, icon, title, lines, dashed=False):
    """The icon beside the text, for the narrower boxes on the right."""
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{CARD}" stroke="{colour}" stroke-width="3"{dash}/>',
           tile(x + 22, y + 22, icon, colour),
           f'<text x="{x + 96}" y="{y + 60}" font-size="30" font-weight="700" fill="{INK}">{html.escape(title)}</text>']
    for i, line in enumerate(lines):
        out.append(f'<text x="{x + 96}" y="{y + 96 + i * 30}" font-size="23" fill="{MUT}">{html.escape(line)}</text>')
    return "".join(out)


def arrow(x1, y1, x2, y2, colour, label, dashed=False):
    dash = ' stroke-dasharray="10 8"' if dashed else ""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2 - 14}" y2="{y2}" stroke="{colour}" stroke-width="5"{dash}/>'
            f'<path d="M{x2} {y2} l-18 -10 v20 z" fill="{colour}"/>'
            f'<text x="{mx}" y="{my - 14}" text-anchor="middle" font-size="20" font-weight="700" fill="{colour}">{html.escape(label)}</text>')


def card(f):
    body = [
        f'<text x="40" y="62" font-size="21" font-weight="700" letter-spacing="3" fill="{MUT}">ZERO-TRUST-LAB · A REAL HOME NETWORK, BUILT IN THE OPEN</text>',
        node(40, 150, 250, 230, COL["tailnet"], ["laptop", "phone"], "Devices",
             ["identity", "+ posture"]),
        node(395, 110, 330, 310, COL["tailnet"], ["ca"], "Tailnet",
             ["deny by default", f"{f['tests']} tests run on", "the live network"]),
        side_node(830, 92, 330, 150, COL["home"], "hub", "Home network",
                  [f"{f['reach']} of ~{f['known']} reachable", "one port each"]),
        side_node(830, 284, 330, 150, RED, "refused", "Everything else",
                  ["refused by default", f"{f['refusals']} refusals tested"], dashed=True),
        arrow(290, 265, 395, 265, GREEN, "grant"),
        arrow(725, 167, 830, 167, GREEN, "allowed"),
        arrow(725, 359, 830, 359, RED, "refused", dashed=True),
        # The cloud account sits beside the tailnet, not behind it.
        f'<rect x="40" y="462" width="1120" height="74" rx="16" fill="{CARD}" stroke="{COL["cloud"]}" stroke-width="3"/>',
        tile(58, 471, "cert", COL["cloud"]),
        f'<text x="134" y="509" font-size="27" font-weight="700" fill="{INK}">Cloud account</text>',
        f'<text x="340" y="509" font-size="23" fill="{MUT}">{f["users"]} IAM users · CI signs in by OIDC · machines by certificate</text>',
        f'<rect x="0" y="565" width="1200" height="62" fill="{INK}"/>',
        f'<text x="40" y="605" font-size="28" font-weight="700" fill="#fff">Zero Trust Access Model — live evidence</text>',
        f'<text x="1160" y="605" text-anchor="end" font-family="{MONO}" font-size="23" fill="#b9b6ae">lab.uveapp.net</text>',
    ]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768" viewBox="0 0 1200 1200">'
            f'<rect width="1200" height="1200" fill="{BG}"/>'
            f'<g transform="translate(0,286.5)" font-family=\'{FONT}\'>{"".join(body)}</g></svg>')


def main(page_path, out_path):
    page = Path(page_path).read_text(encoding="utf-8")
    Path(out_path).write_text(card(figures(page)), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: og_card.py <built index.html> <out.svg>")
    main(sys.argv[1], sys.argv[2])
