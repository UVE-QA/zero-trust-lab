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
    "idp": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5"/><circle cx="17.5" cy="9" r="2.5"/><path d="M16 14c3 0 5.5 2.3 5.5 5.5"/>',
    "mdm": '<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M9 7l2 2 4-4M9 13h6M9 16.5h4"/>',
    "clock": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2.5h6"/>',
    "logs": '<path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "org": '<rect x="9" y="2.5" width="6" height="5" rx="1"/><rect x="2.5" y="16.5" width="6" height="5" rx="1"/><rect x="15.5" y="16.5" width="6" height="5" rx="1"/><path d="M12 7.5v4.5M5.5 16.5V12h13v4.5"/>',
    "ca": '<path d="M12 2.5l8 3.5v5.5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
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

COL = {"future": "#9aa0a6", "home": "#3f8624", "tailnet": "#5b4fd6", "cloud": "#d45b07",
       "ci": "#57606a", "cp": "#1f6feb", "planned": "#8c8c8c", "off": "#8c8c8c"}

TW, TH = 180, 62
W, H = 1200, 972
VB_TOP = -28

NODES = {
    "gha":       (28, 48, "flow", "ci", "GitHub Actions", "validate · drift · plan",
                  "workflows", [], "Runs every check. Holds no network or cloud key: each job "
                  "gets a short-lived token by OIDC.", "D-041"),
    "tscp":      (262, 48, "dots", "cp", "Tailscale", "control plane · 36 tests",
                  "policy as code", [], "Evaluates the policy and refuses a save whose tests fail. "
                  "The policy is not in Terraform: two tools writing one global file fight.", "D-001"),
    "iam":       (488, 48, "key", "cloud", "CI plan role", "OIDC · 0 IAM users",
                  "terraform", [], "Lets CI run terraform plan and nothing more. Its trust names "
                  "this repository by immutable id; wildcards are refused three ways.", "D-028"),
    "bucket":    (686, 48, "bucket", "cloud", "Archive bucket", "S3 · encrypted · Glacier",
                  "terraform", [], "Where the collector's data is meant to land. It exists so the "
                  "certificate credential has something real to authorise.", "D-039"),
    "ra":        (884, 48, "cert", "off", "Roles Anywhere", "certificate → role · off",
                  "terraform", [], "Written, switched off: no certificate authority exists yet. "
                  "Cloud access for a machine that holds a certificate, not a key.", "Phase 5"),
    "state":     (1082, 48, "db", "cloud", "Terraform state", "existing bucket · lockfile",
                  "terraform", [], "State joins the account's existing bucket rather than "
                  "creating one; locking is the native lockfile.", "D-029"),

    "laptop":    (40, 246, "laptop", "tailnet", "Operator laptop", "posture: self-reported",
                  "by hand", ["autogroup:member"], "The physical console. Applies the policy "
                  "by hand after CI has validated it. Its posture attributes are reported by the "
                  "client on the device itself: they establish configuration, not integrity.", "D-040"),
    "phones":    (40, 330, "phone", "tailnet", "Operator phones", "break-glass path",
                  "by hand", ["autogroup:member"], "Posture subjects, and the way back in "
                  "if everything else fails — verified off-network.", "D-016"),
    "desktop":   (40, 432, "desktop", "tailnet", "Shared desktop", "not ours to tag",
                  "by hand", [], "Stays user-owned permanently: it is someone's daily "
                  "machine, so it gets no machine identity.", "Phase 1"),
    "appliance": (250, 432, "tv", "tailnet", "Media appliance", "tag:appliance",
                  "tag", ["tag:appliance"], "A device on the network that should reach "
                  "nothing — and is tested to reach nothing.", "D-019"),
    "gateway":   (500, 330, "hub", "tailnet", "Automation hub", "tag:gateway-home",
                  "tag", ["tag:gateway-home"], "The only door into the home: it advertises "
                  "one /32 route per exposed device, never the subnet.", "D-024"),
    "collector": (760, 330, "inbox", "planned", "Collector", "tag:collector · no host",
                  "planned", ["tag:collector"], "Telemetry sink. Declared in the policy, "
                  "awaiting dedicated hardware.", "Phase 6"),
    "drone":     (760, 432, "drone", "planned", "Mobile units", "tag:drone · ephemeral",
                  "planned", ["tag:drone"], "Simulated field units: send telemetry, "
                  "take control commands.", "Phase 6"),
    "sensor":    (980, 330, "antenna", "planned", "Sensors", "tag:sensor · push-only",
                  "planned", ["tag:sensor"], "Simulated sensors: may reach exactly one "
                  "port on one role.", "Phase 6"),
    "prod":      (980, 246, "server", "tailnet", "Production VM", "tag:prod · Lightsail",
                  "by hand", ["tag:prod"], "The production stand-in. A destination, never "
                  "a source. Outside Terraform; also where a person runs terraform apply.", "D-036"),

    "plug_g":    (500, 610, "plug", "home", "Smart plug", "granted · posture",
                  "one /32", ["actuator-granted"], "The action tier: operators may switch it, "
                  "only from a device whose client reports the required posture. On this plan the "
                  "report comes from the device itself, so a compromised node is not constrained by "
                  "it — which is what the device-management tile below would change.", "D-040"),
    "plug_c":    (700, 610, "plug", "home", "Smart plug", "identical · refused",
                  "one /32", ["actuator-control"], "The same model on the same port, never "
                  "granted. Proves least privilege is per host, not per protocol.", "D-010"),
}
# The growth path: not built. What a multi-user or company deployment adds,
# and where each part would plug in. Drawn so a reader can see the lab's
# shape grow, never mistaken for something that exists.
NODES.update({
    "idp":  (28, 870, "idp", "future", "Identity provider", "SSO · users, groups",
             "Standard $8/user/mo", [], "One login for many people; their groups become policy sources "
             "instead of every member. Plugs into the control plane and cloud sign-in.", "multi-user"),
    "mdm":  (224, 870, "mdm", "future", "MDM / EDR", "posture from the fleet",
             "Standard $8/user/mo", [], "Posture from the fleet's management system instead of the client's "
             "own report. An integration a paid plan adds.", "D-040"),
    "jit":  (420, 870, "clock", "future", "Just-in-time", "grants that expire",
             "Premium $18/user/mo", [], "Standing access to the action tier replaced by grants that "
             "expire. Needs a paid plan: one time-boxed month.", "Phase 4"),
    "siem": (616, 870, "logs", "future", "Log streaming", "flow + audit → SIEM",
             "Premium $18/user/mo", [], "Who connected to what, kept and searchable. The drills in "
             "Phase 6 would read it.", "Phase 6"),
    "sso":  (812, 870, "org", "future", "Identity Center", "people's cloud sign-in",
             "AWS: no charge", [], "Cloud sign-in for people through the identity provider. Lives in "
             "the organisation's management account, not this stack.", "D-030"),
    "ca":   (1008, 870, "ca", "future", "Private CA", "certs for the collector",
             "free, or $50+/mo", [], "The missing half of Roles Anywhere: machines get certificates, "
             "never keys. Switches the cloud tile above on.", "Phase 5"),
})
TWN = {"state": 106}          # the narrow state tile, far right of the cloud row

OPERATORS = ("laptop", "phones")


def role_to_node(role):
    if role == "autogroup:member":
        return "operators"
    for nid, n in NODES.items():
        if role in n[7] and nid not in OPERATORS:
            return nid
    return None


# Orthogonal routes: waypoints from the source tile's edge to the target's,
# and where the label sits. Keyed by (from, to), or (from, via, to) for the
# first leg of a grant routed through the hub. A grant whose pair is missing
# is still drawn -- straight -- and listed under the diagram as unplaced.
ROUTES = {
    ("operators", "gateway"):           ([(220, 345), (500, 345)], (362, 345)),
    ("operators", "gateway", "plug_g"): ([(220, 372), (500, 372)], None),
    ("gateway", "plug_g"):              ([(590, 392), (590, 610)], (590, 500)),
    ("operators", "prod"):              ([(220, 277), (980, 277)], (640, 277)),
    ("operators", "drone"):             ([(220, 388), (238, 388), (238, 414), (738, 414), (738, 463), (760, 463)], (420, 414)),
    ("collector", "gateway"):           ([(760, 348), (680, 348)], (720, 348)),
    ("sensor", "collector"):            ([(980, 361), (940, 361)], (960, 361)),
    ("drone", "collector"):             ([(850, 432), (850, 392)], (878, 412)),
    # refusals, drawn from the tests
    ("prod", "gateway"):                ([(980, 302), (640, 302), (640, 330)], (880, 302)),
    ("appliance", "gateway"):           ([(430, 463), (470, 463), (470, 386), (500, 386)], (560, 452)),
    ("gateway", "plug_c"):              ([(650, 392), (650, 560), (790, 560), (790, 610)], (760, 540)),
}


def ortho(pts, r=9):
    """A polyline with rounded corners."""
    if len(pts) == 2:
        (x1, y1), (x2, y2) = pts
        return f"M{x1},{y1} L{x2},{y2}"
    d = [f"M{pts[0][0]},{pts[0][1]}"]
    for i in range(1, len(pts) - 1):
        (xa, ya), (xb, yb), (xc, yc) = pts[i - 1], pts[i], pts[i + 1]
        def toward(x0, y0, x1, y1, k):
            dx, dy = x1 - x0, y1 - y0
            L = max(abs(dx), abs(dy)) or 1
            k = min(k, L / 2)
            return x0 + dx / L * k, y0 + dy / L * k
        p1 = toward(xb, yb, xa, ya, r)
        p2 = toward(xb, yb, xc, yc, r)
        d.append(f"L{p1[0]:.0f},{p1[1]:.0f} Q{xb},{yb} {p2[0]:.0f},{p2[1]:.0f}")
    d.append(f"L{pts[-1][0]},{pts[-1][1]}")
    return " ".join(d)


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


def label(x, y, text, colour, cls="lbl"):
    w = 6.6 * len(text) + 14
    return (f'<g class="{cls}"><rect x="{x - w / 2:.0f}" y="{y - 10:.0f}" width="{w:.0f}" height="19" '
            f'rx="9.5" fill="var(--card)" stroke="{colour}"/><text x="{x:.0f}" y="{y + 4:.0f}" '
            f'text-anchor="middle" fill="{colour}">{E(text)}</text></g>')


def tile(nid, counts):
    x, y, icon, col, title, sub, tool = NODES[nid][:7]
    w = TWN.get(nid, TW)
    dashed = ' stroke-dasharray="5 4"' if col in ("planned", "off", "future") else ""
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
                out[nid] = f"live · {roles[r]['online']}/{roles[r]['count']} online"
    uo = agg.get("user_owned") or {}
    if uo:
        out["laptop"] = f"live · {uo.get('count', 0)} user-owned"
    return out


def render(policy_text, agg=None, home=None):
    grants, refusals = parse_policy(policy_text)
    layers = {"grant": [], "refusal": [], "control": []}
    unplaced = []
    ok, no, mu, cp, cl = "var(--pass)", "var(--fail)", "var(--mut)", "var(--cp)", "var(--cl)"

    def route(key):
        r = ROUTES.get(key)
        if r is None:
            unplaced.append(" → ".join(key))
            f, t = key[0], key[-1]
            fx, fy = (220, 320) if f == "operators" else (NODES[f][0] + TW, NODES[f][1] + TH / 2)
            tx, ty = NODES[t][0], NODES[t][1] + TH / 2
            return [(fx, fy), (tx, ty)], ((fx + tx) / 2, (fy + ty) / 2)
        return r

    def arrow(layer, pts, colour, dash="", marker="ok", width=2):
        layers[layer].append(f'<path d="{ortho(pts)}" fill="none" stroke="{colour}" stroke-width="{width}"'
                             f'{dash} stroke-linejoin="round" marker-end="url(#m-{marker})"/>')

    # --- grants, parsed from the policy --------------------------------------
    for g in grants:
        port = ", ".join(p.replace("tcp:", "") for p in g.get("ip", []))
        via = role_to_node(g["via"][0]) if g.get("via") else None
        tag = " · posture" if g.get("srcPosture") else ""
        for src in g["src"]:
            for dst in g["dst"]:
                frm, to = role_to_node(src), role_to_node(dst)
                if not frm or not to:
                    unplaced.append(f"{src} → {dst}:{port}")
                    continue
                planned = any(n != "operators" and NODES[n][3] == "planned" for n in (frm, to))
                dash = ' stroke-dasharray="6 5"' if planned else ""
                if via:
                    pts, _ = route((frm, via, to))
                    arrow("grant", pts, ok, dash)
                    pts, lp = route((via, to))
                else:
                    pts, lp = route((frm, to))
                arrow("grant", pts, ok, dash)
                if lp:
                    layers["grant"].append(label(lp[0], lp[1], f"{port}{tag}", ok))

    # --- refusals, parsed from the tests -------------------------------------
    home_roles = {"tag:gateway-home", "camera-stream", "actuator-granted", "actuator-control"}
    for src in ("tag:prod", "tag:appliance"):
        denied = {r for s_, r, _ in refusals if s_ == src} & home_roles
        if denied:
            pts, lp = route((role_to_node(src), "gateway"))
            arrow("refusal", pts, no, ' stroke-dasharray="4 4"', "no")
            layers["refusal"].append(label(lp[0], lp[1], f"✗ refused · {len(denied)} tested", no))
    if "actuator-control" in {r for s_, r, _ in refusals if s_.startswith("@")}:
        pts, lp = route(("gateway", "plug_c"))
        arrow("refusal", pts, no, ' stroke-dasharray="4 4"', "no")
        layers["refusal"].append(label(lp[0], lp[1], "✗ operators refused · tested", no))

    # --- who changes what: the design, drawn by hand -------------------------
    control = [
        ([(208, 79), (262, 79)], mu, "", "mu", (235, 64), "read-only"),
        ([(190, 48), (190, -6), (578, -6), (578, 48)], mu, "", "mu", (384, -6), "terraform plan · OIDC"),
        ([(100, 246), (100, 172), (300, 172), (300, 110)], cp, ' stroke-dasharray="6 4"', "cp",
         (200, 172), "policy apply · a person"),
        ([(392, 110), (392, 200), (620, 200), (620, 330)], cp, ' stroke-dasharray="2 5"', "cp",
         (506, 200), "enforces"),
        ([(1070, 246), (1070, 176), (1135, 176), (1135, 110)], cl, ' stroke-dasharray="6 4"', "cl",
         (1070, 206), "terraform apply · a person"),
        ([(850, 330), (850, 214), (776, 214), (776, 110)], mu, ' stroke-dasharray="3 5"', "mu",
         (813, 160), "planned: certificate → archive"),
    ]
    for pts, c, dash, m, (lx, ly), txt in control:
        arrow("control", pts, c, dash, m, 1.6)
        layers["control"].append(label(lx, ly, txt, c, "lbl f"))

    counts = live_counts(agg)
    tiles = "".join(tile(n, counts) for n in NODES)

    proto, rest = "", ""
    if home:
        proto = (f'<text x="258" y="726" class="ctn">connected over: '
                 f'{E(" · ".join(home.get("protocols", [])))}</text>')
        cats = [c for c in home.get("categories", []) if isinstance(c.get("count"), int)]
        x0, y0 = 900, 596
        rows = []
        for i, c in enumerate(cats):
            cx, cy = x0 + 14 + (i % 2) * 134, y0 + 62 + (i // 2) * 19
            rows.append(f'<text x="{cx}" y="{cy}" class="chip"><tspan class="n">{c["count"]}</tspan> {E(c["type"])}</text>')
        rest = (f'<g class="tile"><rect x="{x0}" y="{y0}" width="276" height="184" rx="10" fill="var(--card)" stroke="var(--line)"/>'
                f'<text x="{x0 + 14}" y="{y0 + 22}" class="t">The rest of the house</text>'
                f'<text x="{x0 + 14}" y="{y0 + 39}" class="s">about {home.get("total_about")} devices · '
                f'{home.get("exposed_to_tailnet")} reachable from the tailnet</text>'
                + "".join(rows)
                + f'<text x="{x0 + 14}" y="{y0 + 62 + ((len(cats) + 1) // 2) * 19 + 2}" class="s">+ other, inactive or withheld</text>'
                f'<text x="{x0 + 14}" y="{y0 + 174}" class="b">counted {E(home.get("counted_at", ""))} · cameras withheld</text></g>')

    contours = f"""
<rect x="12" y="10" width="222" height="120" rx="12" class="ct ci"/>
<text x="24" y="30" class="ctl">CI · GitHub Actions</text>
<text x="24" y="124" class="ctn">no stored keys · OIDC per job</text>
<rect x="246" y="10" width="222" height="120" rx="12" class="ct cp"/>
<text x="258" y="30" class="ctl">Control plane · Tailscale</text>
<text x="258" y="124" class="ctn">SaaS · policy as code</text>
<rect x="480" y="10" width="708" height="120" rx="12" class="ct cloud"/>
<text x="1176" y="30" text-anchor="end" class="ctl">Cloud · AWS us-west-2 — managed by Terraform</text>
<text x="492" y="124" class="ctn">planned by CI · applied by a person</text>
<rect x="12" y="222" width="1176" height="290" rx="14" class="ct tailnet"/>
<text x="24" y="506" class="ctl">Tailnet — WireGuard overlay · 100.64/10 · one identity per node · deny by default</text>
<text x="40" y="410" class="ctn">laptop + phones = one policy role</text>
<text x="1176" y="506" text-anchor="end" class="ctn">grey: planned roles, declared in the policy, no host yet</text>
<rect x="246" y="572" width="942" height="228" rx="14" class="ct home"/>
<text x="258" y="706" class="ctn">one /32 route per exposed device, through the hub · the /24 itself is never advertised</text>
{proto}
<text x="258" y="790" class="ctl">Home network — flat private /24 · reached only through the hub</text>
{rest}
<rect x="12" y="820" width="1176" height="146" rx="14" class="ct future"/>
<text x="24" y="844" class="ctl">Growth path — not built. What a multi-user or company deployment adds, what it plugs into, and what it would cost</text>
"""
    defs = "".join(
        f'<marker id="m-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0L10,5L0,10z" fill="{v}"/></marker>'
        for k, v in (("ok", ok), ("no", no), ("mu", mu), ("cp", cp), ("cl", cl)))
    g = lambda k: f'<g class="layer-{k}">{"".join(x for x in layers[k] if x.startswith("<path"))}</g>'
    gl = lambda k: f'<g class="layer-{k}">{"".join(x for x in layers[k] if not x.startswith("<path"))}</g>'
    svg = (f'<svg id="labmap" viewBox="0 {VB_TOP} {W} {H - VB_TOP}" role="img" xmlns="http://www.w3.org/2000/svg" '
           f'aria-label="The lab: contours, subnets, tools and permitted paths"><defs>{defs}</defs>'
           f'{contours}{g("control")}{g("refusal")}{g("grant")}{tiles}'
           f'{gl("control")}{gl("refusal")}{gl("grant")}</svg>')

    toggles = ('<div class="layers"><span>Show:</span>'
               '<label><input type="checkbox" data-layer="grant" checked> <span class="k ok"></span>granted</label>'
               '<label><input type="checkbox" data-layer="refusal" checked> <span class="k no"></span>refused</label>'
               '<label><input type="checkbox" data-layer="control" checked> <span class="k cf"></span>who changes what</label></div>')
    legend = ('<p class="legend">Green arrows are grants parsed from the policy, with the port each names; '
              'dashed green goes to a role with no host yet. Red arrows are refusals asserted by the policy tests. '
              'Everything not drawn is refused by default.</p>')
    if unplaced:
        legend += ('<p class="legend warn">In the policy but not placed on this diagram: '
                   + "; ".join(E(u) for u in unplaced) + ".</p>")

    rows = "".join(
        f'<tr><td><span class="sw" style="background:{COL[n[3]]}"></span>{E(n[4])}</td>'
        f'<td><code>{E(n[6])}</code></td><td>{E(n[8])}</td><td>{E(n[9])}</td></tr>'
        for n in NODES.values())
    if home:
        rows += (f'<tr><td><span class="sw" style="background:{COL["home"]}"></span>The rest of the house</td>'
                 f'<td><code>no route</code></td><td>About {home.get("total_about")} devices by type, counted by hand '
                 f'on {E(home.get("counted_at", ""))} from the hub\'s registry. None is reachable from the '
                 f'tailnet; the hub talks to them locally. The camera count is withheld, and categories that '
                 f'would let it be subtracted are folded together.</td><td>D-008</td></tr>')
    table = (f'<table class="why"><thead><tr><th>Part</th><th>Managed by · cost</th><th>What it is for</th>'
             f'<th>Why</th></tr></thead><tbody>{rows}</tbody></table>')
    return toggles + svg, legend, table, unplaced
