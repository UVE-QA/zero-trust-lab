"""The lab on one picture: contours, subnets, tools, and who may reach what.

Imported by evidence_page.py. The layout -- where each part sits, which
contour it belongs to, the words on each tile, which tool manages it and why --
is editorial, like any hand-drawn architecture diagram. What is NOT editorial:

  * every green arrow inside the network is a grant parsed from
    policy/policy.hujson.tmpl, labelled with the port the grant names; a grant
    routed `via` the hub is drawn through the hub;
  * every red arrow is a refusal asserted in the policy's `tests` section;
  * a grant between roles this layout does not know is not dropped silently --
    it is listed under the diagram as unplaced;
  * node counts come from the tailnet aggregate, and say so, or are absent.

So the picture cannot show a path the policy does not grant, and a new grant
appears the next time the page is built. No address, name or model is drawn:
subnets are given by size and purpose only.
"""
import html
import re

E = html.escape

ICONS = {
    "laptop": '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19h20"/>',
    "phone": '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M11 18.5h2"/>',
    "desktop": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M9 20h6M12 16v4"/>',
    "tv": '<rect x="2.5" y="5" width="19" height="12" rx="1.5"/><path d="M8 20h8M12 17v3"/>',
    "hub": '<path d="M3 11l9-7 9 7v9H3z"/><circle cx="12" cy="14" r="2.2"/>',
    "server": '<rect x="4" y="3.5" width="16" height="7" rx="1.5"/><rect x="4" y="13.5" width="16" height="7" rx="1.5"/><path d="M8 7h.01M8 17h.01"/>',
    "camera": '<rect x="2.5" y="7" width="13" height="10" rx="2"/><path d="M15.5 11l6-3.5v9l-6-3.5"/>',
    "plug": '<path d="M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4"/>',
    "mesh": '<circle cx="5" cy="12" r="2"/><circle cx="19" cy="5.5" r="2"/><circle cx="19" cy="18.5" r="2"/><path d="M7 11l10-4.5M7 13l10 4.5M19 7.5v9"/>',
    "dots": ''.join(f'<circle cx="{x}" cy="{y}" r="1.8" fill="#fff" stroke="none"/>'
                    for x in (6, 12, 18) for y in (6, 12, 18)),
    "bucket": '<path d="M4 6.5h16l-2 13.5H6z"/><ellipse cx="12" cy="6.5" rx="8" ry="2.5"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16.5 6.5l3 3"/>',
    "cert": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M7 8h10M7 11h6"/><circle cx="16" cy="17" r="3"/><path d="M14.5 19.5L14 22l2-1 2 1-.5-2.5"/>',
    "db": '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    "flow": '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M6 9v5a4 4 0 0 0 4 4h5"/>',
    "inbox": '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1.5 2.5h5L16 13h5"/>',
    "antenna": '<path d="M12 12v9"/><circle cx="12" cy="10" r="2"/><path d="M7.5 6a6.5 6.5 0 0 1 9 0M4.5 3a11 11 0 0 1 15 0"/>',
    "drone": '<circle cx="5.5" cy="5.5" r="2.5"/><circle cx="18.5" cy="5.5" r="2.5"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M7.5 7.5L9 9M16.5 7.5L15 9M7.5 16.5L9 15M16.5 16.5L15 15"/>',
}

COL = {"home": "#3f8624", "tailnet": "#5b4fd6", "cloud": "#d45b07",
       "ci": "#57606a", "cp": "#1f6feb", "planned": "#8c8c8c", "off": "#8c8c8c"}

TW, TH = 180, 62
W, H = 1200, 760

# id: x, y, icon, colour, title, subtitle, tool, policy roles, why, decision
NODES = {
    "gha":       (28, 48, "flow", "ci", "GitHub Actions", "validate · drift · plan · page",
                  "workflows", [], "Runs every check. Holds no network or cloud key: each job "
                  "gets a short-lived token by OIDC.", "D-041"),
    "tscp":      (262, 48, "dots", "cp", "Tailscale control plane", "the policy · its 36 tests",
                  "policy as code", [], "Evaluates the policy and refuses a save whose tests fail. "
                  "The policy is not in Terraform: two tools writing one global file fight.", "D-001"),
    "iam":       (488, 48, "key", "cloud", "CI plan role", "OIDC · 0 IAM users",
                  "terraform", [], "Lets CI run terraform plan and nothing more. Its trust names "
                  "this repository by immutable id; wildcards are refused three ways.", "D-028"),
    "bucket":    (686, 48, "bucket", "cloud", "Archive bucket", "S3 · encrypted · to Glacier",
                  "terraform", [], "Where the collector's data is meant to land. It exists so the "
                  "certificate credential has something real to authorise.", "D-039"),
    "ra":        (884, 48, "cert", "off", "Roles Anywhere", "certificate → role · off",
                  "terraform", [], "Written, switched off: no certificate authority exists yet. "
                  "Cloud access for a machine that holds a certificate, not a key.", "Phase 5"),
    "state":     (1082, 48, "db", "cloud", "Terraform state", "existing bucket · lockfile",
                  "terraform", [], "State joins the account's existing bucket rather than "
                  "creating one; locking is the native lockfile.", "D-029"),

    "laptop":    (28, 258, "laptop", "tailnet", "Operator laptop", "posture-checked",
                  "by hand", ["autogroup:member"], "The physical console. Applies the policy "
                  "by hand after CI has validated it.", "D-041"),
    "phones":    (28, 336, "phone", "tailnet", "Operator phones", "break-glass path",
                  "by hand", ["autogroup:member"], "Posture subjects, and the way back in "
                  "if everything else fails — verified off-network.", "D-016"),
    "desktop":   (28, 424, "desktop", "tailnet", "Shared desktop", "another person's machine",
                  "by hand", [], "Stays user-owned permanently: it is someone's daily "
                  "machine, so it gets no machine identity.", "Phase 1"),
    "appliance": (248, 424, "tv", "tailnet", "Media appliance", "tag:appliance",
                  "tag", ["tag:appliance"], "A device on the network that should reach "
                  "nothing — and is tested to reach nothing.", "D-019"),
    "gateway":   (478, 336, "hub", "tailnet", "Automation hub", "tag:gateway-home",
                  "tag", ["tag:gateway-home"], "The only door into the home: it advertises "
                  "one /32 route per exposed device, never the subnet.", "D-024"),
    "collector": (724, 258, "inbox", "planned", "Collector", "tag:collector · no host",
                  "planned", ["tag:collector"], "Telemetry sink. Declared in the policy, "
                  "awaiting dedicated hardware.", "Phase 6"),
    "drone":     (724, 424, "drone", "planned", "Mobile units", "tag:drone · ephemeral",
                  "planned", ["tag:drone"], "Simulated field units: send telemetry, "
                  "take control commands.", "Phase 6"),
    "sensor":    (980, 258, "antenna", "planned", "Sensors", "tag:sensor · push-only",
                  "planned", ["tag:sensor"], "Simulated sensors: may reach exactly one "
                  "port on one role.", "Phase 6"),
    "prod":      (980, 424, "server", "tailnet", "Production VM", "tag:prod · Lightsail",
                  "by hand", ["tag:prod"], "The production stand-in. A destination, never "
                  "a source. Outside Terraform; also where a person runs terraform apply.", "D-036"),

    "camera":    (262, 638, "camera", "home", "Camera stream", "collector only",
                  "one /32", ["camera-stream"], "The stream tier: one camera exposed, to "
                  "one role, on one port.", "D-024"),
    "plug_g":    (486, 638, "plug", "home", "Smart plug", "granted · with posture",
                  "one /32", ["actuator-granted"], "The action tier: operators may switch it, "
                  "only from a device that passes the posture check.", "D-040"),
    "plug_c":    (710, 638, "plug", "home", "Smart plug", "identical · refused",
                  "one /32", ["actuator-control"], "The same model on the same port, never "
                  "granted. Proves least privilege is per host, not per protocol.", "D-010"),
    "mesh":      (934, 638, "mesh", "home", "Matter / Thread", "not exposed",
                  "—", [], "The rest of the house. No route reaches it; the hub talks to it "
                  "locally.", "D-008"),
}
TWN = {"state": 106}          # the narrow state tile, far right of the cloud row

OPERATORS = ("laptop", "phones")


def role_to_node(role):
    if role == "autogroup:member":
        return "operators"
    for nid, n in NODES.items():
        if role in n[7] and nid not in OPERATORS:
            return nid
    return None


def box(nid):
    if nid == "operators":
        return 28, 258, TW, 140
    x, y = NODES[nid][:2]
    return x, y, TWN.get(nid, TW), TH


def anchor(nid, side, shift=0):
    x, y, w, h = box(nid)
    return {"l": (x, y + h / 2 + shift), "r": (x + w, y + h / 2 + shift),
            "t": (x + w / 2 + shift, y), "b": (x + w / 2 + shift, y + h)}[side]


# (from, to): (side out, side in, bend, shift-out, shift-in), or an explicit
# ("path", d, label-position) where the arrow has to use the lane between rows.
ROUTES = {
    ("operators", "gateway"): ("r", "l", 0, -18, -10),
    ("operators", "prod"):    ("path", "M208,392 L470,410 L955,410 Q975,410 980,440", (835, 410)),
    ("operators", "drone"):   ("path", "M208,380 L700,440 L724,450", (600, 428)),
    ("collector", "gateway"): ("b", "t", 0, -30, 30),
    ("sensor", "collector"):  ("l", "r", 0, 0, 0),
    ("drone", "collector"):   ("t", "b", 0, 30, 30),
    ("gateway", "camera"):    ("b", "t", 0, -40, 0),
    ("gateway", "plug_g"):    ("b", "t", 0, 0, 0),
    ("gateway", "plug_c"):    ("b", "t", 0, 40, 0),
    ("prod", "gateway"):      ("l", "r", 0, 10, 10),
    ("appliance", "gateway"): ("r", "l", 0, 0, 18),
}


def parse_policy(text):
    # Placeholders are braces too: `{{operator_identity}}` would otherwise be
    # read as a nested block and hide the operator's tests. Name them first.
    t = re.sub(r"\{\{\s*(\w+)\s*\}\}", r"@\1", re.sub(r"//[^\n]*", "", text))
    grants = []
    body = t[t.index('"grants"'):t.index('"ssh"')]
    for blk in re.findall(r"\{([^{}]*)\}", body):
        f = {k: re.findall(r'"([^"]+)"', v) for k, v in re.findall(r'"(\w+)":\s*\[([^\]]*)\]', blk)}
        if f.get("src") and f.get("dst"):
            grants.append(f)
    refusals = []
    for blk in re.findall(r"\{((?:[^{}]|\{[^{}]*\})*)\}", t[t.index('"tests"'):]):
        src = re.search(r'"src":\s*"([^"]+)"', blk)
        den = re.search(r'"deny":\s*\[([^\]]*)\]', blk)
        if src and den:
            for d in re.findall(r'"([^"]+)"', den.group(1)):
                role, _, port = d.rpartition(":")
                refusals.append((src.group(1), role, port))
    return grants, refusals


def curve(a, b, bend):
    (x1, y1), (x2, y2) = a, b
    if not bend:
        return f"M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}", ((x1 + x2) / 2, (y1 + y2) / 2)
    cy = max(y1, y2) + bend
    return (f"M{x1:.0f},{y1:.0f} C{x1 + 140:.0f},{cy:.0f} {x2 - 40:.0f},{cy:.0f} {x2:.0f},{y2:.0f}",
            ((x1 + x2) / 2 + 20, cy - bend * 0.28))


def label(x, y, text, colour, cls="lbl"):
    w = 6.6 * len(text) + 14
    return (f'<g class="{cls}"><rect x="{x - w / 2:.0f}" y="{y - 10:.0f}" width="{w:.0f}" height="19" '
            f'rx="9.5" fill="var(--card)" stroke="{colour}"/><text x="{x:.0f}" y="{y + 4:.0f}" '
            f'text-anchor="middle" fill="{colour}">{E(text)}</text></g>')


def tile(nid, counts):
    x, y, icon, col, title, sub, tool = NODES[nid][:7]
    w = TWN.get(nid, TW)
    dashed = ' stroke-dasharray="5 4"' if col in ("planned", "off") else ""
    t = [f'<g class="tile" id="n-{nid}"><title>{E(title)} — {E(NODES[nid][8])}</title>',
         f'<rect x="{x}" y="{y}" width="{w}" height="{TH}" rx="8" fill="var(--card)" stroke="var(--line)"{dashed}/>',
         f'<rect x="{x + 9}" y="{y + 11}" width="40" height="40" rx="7" fill="{COL[col]}"/>',
         f'<g transform="translate({x + 17},{y + 19})" fill="none" stroke="#fff" stroke-width="1.7" '
         f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>']
    if w >= TW:
        t += [f'<text x="{x + 58}" y="{y + 20}" class="t">{E(title)}</text>',
              f'<text x="{x + 58}" y="{y + 35}" class="s">{E(sub)}</text>',
              f'<text x="{x + 58}" y="{y + 51}" class="b">{E(counts.get(nid) or tool)}</text>']
    else:
        t += [f'<text x="{x + 56}" y="{y + 26}" class="t">State</text>',
              f'<text x="{x + 56}" y="{y + 42}" class="b">{E(tool)}</text>']
    return "".join(t) + "</g>"


def live_counts(agg):
    if not agg:
        return {}
    out, roles = {}, agg.get("tagged_roles", {})
    for nid, n in NODES.items():
        for r in n[7]:
            if r in roles:
                out[nid] = f"live · {roles[r]['count']} node · {roles[r]['online']} online"
    uo = agg.get("user_owned") or {}
    if uo:
        out["laptop"] = "live · " + ", ".join(f"{v} {k}" for k, v in uo.get("by_os", {}).items())
    return out


def render(policy_text, agg=None):
    grants, refusals = parse_policy(policy_text)
    arrows, labels, unplaced = [], [], []
    ok, no, mu, cp, cl = "var(--pass)", "var(--fail)", "var(--mut)", "var(--cp)", "var(--cl)"

    def seg(frm, to):
        r = ROUTES.get((frm, to))
        if r and r[0] == "path":
            return r[1], r[2]
        if r is None:
            unplaced.append(f"{frm} → {to}")
            return curve(anchor(frm, "r"), anchor(to, "l"), 0)
        return curve(anchor(frm, r[0], r[3]), anchor(to, r[1], r[4]), r[2])

    def arrow(d, colour, dash="", marker="ok", width=2):
        arrows.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"{dash} '
                      f'marker-end="url(#m-{marker})"/>')

    # --- the network: grants and refusals, parsed from the policy ------------
    for g in grants:
        port = ", ".join(p.replace("tcp:", "") for p in g.get("ip", []))
        via = role_to_node(g["via"][0]) if g.get("via") else None
        tag = " · posture" if g.get("srcPosture") else ""
        for s in g["src"]:
            for d in g["dst"]:
                frm, to = role_to_node(s), role_to_node(d)
                if not frm or not to:
                    unplaced.append(f"{s} → {d}:{port}")
                    continue
                planned = any(n != "operators" and NODES[n][3] == "planned" for n in (frm, to))
                dash = ' stroke-dasharray="6 5"' if planned else ""
                if via:
                    p1, _ = seg(frm, via)
                    arrow(p1, ok, dash)
                    p2, (lx, ly) = seg(via, to)
                else:
                    p2, (lx, ly) = seg(frm, to)
                arrow(p2, ok, dash)
                labels.append(label(lx, ly, f"{port}{tag}", ok))

    home = {"tag:gateway-home", "camera-stream", "actuator-granted", "actuator-control"}
    for src in ("tag:prod", "tag:appliance"):
        denied = {r for s, r, _ in refusals if s == src} & home
        if denied:
            frm = role_to_node(src)
            p, _ = seg(frm, "gateway")
            arrow(p, no, ' stroke-dasharray="4 4"', "no")
            # label near the source end, so it never sits on a crossing grant
            r = ROUTES[(frm, "gateway")]
            (x1, y1), (x2, y2) = anchor(frm, r[0], r[3]), anchor("gateway", r[1], r[4])
            labels.append(label(x1 + (x2 - x1) * 0.27, y1 + (y2 - y1) * 0.27 - 12,
                                f"✗ refused · {len(denied)} tested", no))

    # The identical smart plug: operators may switch one, and the tests assert
    # they are refused the other -- least privilege per host, not per protocol.
    op = {r for s_, r, _ in refusals if s_.startswith("@")}
    if "actuator-control" in op:
        p, _ = seg("gateway", "plug_c")
        arrow(p, no, ' stroke-dasharray="4 4"', "no")
        x, y = anchor("plug_c", "t")
        labels.append(label(x + 70, y - 34, "✗ operators refused · tested", no))

    # --- who changes what: the control flows, drawn from the design ---------
    gx, gy, _, _ = box("gha")
    flows = [
        (f"M{gx + TW},{gy + 22} L262,{gy + 22}", mu, "", "mu", (235, gy + 6), "read-only"),
        (f"M{gx + TW / 2 + 40},{48 + TH} C{gx + TW / 2 + 40},172 {488 + TW / 2},172 {488 + TW / 2},{48 + TH}",
         mu, "", "mu", (300, 162), "terraform plan (OIDC)"),
        (f"M{980 + TW / 2},424 C{980 + TW / 2},300 {1082 + 53},220 {1082 + 53},{48 + TH}", cl,
         ' stroke-dasharray="6 4"', "cl", (1090, 190), "terraform apply · a person"),
        (f"M{28 + 120},258 C{28 + 120},170 {262 + 40},170 {262 + 40},{48 + TH}", cp,
         ' stroke-dasharray="6 4"', "cp", (150, 200), "policy apply · a person"),
        (f"M{262 + TW - 30},{48 + TH} C{262 + TW - 30},250 {478 + 60},250 {478 + 60},336", cp,
         ' stroke-dasharray="2 5"', "cp", (440, 214), "enforces"),
        (f"M{724 + TW / 2},258 C{724 + TW / 2},190 {686 + TW / 2},170 {686 + TW / 2},{48 + TH}", mu,
         ' stroke-dasharray="3 5"', "mu", (748, 176), "planned: certificate → archive"),
    ]
    for d, c, dash, m, (lx, ly), txt in flows:
        arrow(d, c, dash, m, 1.6)
        labels.append(label(lx, ly, txt, c, "lbl f"))

    counts = live_counts(agg)
    tiles = "".join(tile(n, counts) for n in NODES)

    contours = f"""
<rect x="12" y="10" width="222" height="120" rx="12" class="ct ci"/>
<text x="24" y="30" class="ctl">CI · GitHub Actions</text>
<text x="24" y="124" class="ctn">no stored keys · OIDC per job</text>
<rect x="246" y="10" width="222" height="120" rx="12" class="ct cp"/>
<text x="258" y="30" class="ctl">Control plane · Tailscale</text>
<text x="258" y="124" class="ctn">SaaS · policy as code</text>
<rect x="480" y="10" width="708" height="120" rx="12" class="ct cloud"/>
<text x="492" y="30" class="ctl">Cloud · AWS us-west-2 — managed by Terraform</text>
<text x="492" y="124" class="ctn">planned by CI, applied by a person · no IAM users · no access keys</text>
<rect x="12" y="232" width="1176" height="262" rx="14" class="ct tailnet"/>
<text x="24" y="252" class="ctl">Tailnet — WireGuard overlay · 100.64/10 · one identity per node · deny by default</text>
<text x="30" y="414" class="ctn">laptop + phones = one policy role: every member</text>
<rect x="246" y="590" width="942" height="160" rx="14" class="ct home"/>
<text x="258" y="610" class="ctl">Home network — flat private /24 · reached only through the hub · one /32 route per exposed device</text>
<text x="258" y="744" class="ctn">the subnet itself is never advertised; the rest of the /24 has no route in</text>
"""
    defs = "".join(
        f'<marker id="m-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="{v}"/></marker>'
        for k, v in (("ok", ok), ("no", no), ("mu", mu), ("cp", cp), ("cl", cl)))
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" xmlns="http://www.w3.org/2000/svg" '
           f'aria-label="The lab: contours, subnets, tools and permitted paths"><defs>{defs}</defs>'
           f'{contours}{"".join(arrows)}{tiles}{"".join(labels)}</svg>')

    legend = ('<p class="legend"><span class="k ok"></span>granted — parsed from the policy, with the '
              'port it names <span class="k pl"></span>granted to a role with no host yet '
              '<span class="k no"></span>refused — asserted by the policy tests '
              '<span class="k cf"></span>who changes what. Everything not drawn is refused by default.</p>')
    if unplaced:
        legend += ('<p class="legend warn">In the policy but not placed on this diagram: '
                   + "; ".join(E(u) for u in unplaced) + ".</p>")

    rows = "".join(
        f'<tr><td><span class="sw" style="background:{COL[n[3]]}"></span>{E(n[4])}</td>'
        f'<td><code>{E(n[6])}</code></td><td>{E(n[8])}</td><td>{E(n[9])}</td></tr>'
        for n in NODES.values())
    table = (f'<table class="why"><thead><tr><th>Part</th><th>Managed by</th><th>What it is for</th>'
             f'<th>Why</th></tr></thead><tbody>{rows}</tbody></table>')
    return svg, legend, table, unplaced
