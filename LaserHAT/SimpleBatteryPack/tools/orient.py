#!/usr/bin/env python3
"""Rotate parts in place to untangle the ratsnest (2026-10-31).    $KICAD_PY tools/orient.py [--write]
Score = crossings between airwires of different nets (each net's airwires = the minimum spanning tree over its pads;
0V is left out: it goes to the B.Cu plane), total airwire length breaks ties.  Every rotatable part (ICs, transistors,
diodes, two-pin R / C, ...) tries 0 / 90 / 180 / 270 at its table position; a rotation is taken when it lowers the score
and its courtyard stays clear of every other courtyard and inside the board.  Greedy passes until nothing improves.
Fixed: connectors, relays, switches, the gauge LED columns, holes, test points, and place.py's LOCKED parts.  --write records the result as the ROT
override block in tools/place.py (place.py applies it after its table); without it, only reports."""
import math
import os
import re
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "SimpleBatteryPack.kicad_pcb")
PLACE = os.path.join(ROOT, "tools", "place.py")
SKIP_NETS = {"0V", ""}
LED_COLUMNS = {"D1", "D2", "D3", "D4", "D9", "D10", "D11", "D12", "D13", "D14", "D17", "D18"}
FIXED_PREFIX = ("J", "K", "SW", "H", "TP")
NM = 1e6

b = pcbnew.LoadBoard(BOARD)
fps = {f.GetReference(): f for f in b.GetFootprints()}
edge = b.GetBoardEdgesBoundingBox()


_locked = re.search(r"^LOCKED = \((.*?)\)", open(PLACE).read(), re.S | re.M)
LOCKED = set(re.findall(r'"(\w+)"', _locked.group(1))) if _locked else set()      # place.py's hand-set rotations


def movable(ref):
    return not ref.startswith(FIXED_PREFIX) and ref not in LED_COLUMNS and ref not in LOCKED


def court(f):
    f.BuildCourtyardCaches()
    return pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd))


# pads per net (as (ref, pad object))
netpads = {}
for f in fps.values():
    for p in f.Pads():
        n = p.GetNetname()
        if n in SKIP_NETS or n.startswith("unconnected-"):
            continue
        netpads.setdefault(n, []).append(p)
netpads = {n: ps for n, ps in netpads.items() if len(ps) > 1}
nets_of = {}
for n, ps in netpads.items():
    for p in ps:
        nets_of.setdefault(p.GetParentFootprint().GetReference(), set()).add(n)


def mst(n):
    pts = [(p.GetX() / NM, p.GetY() / NM) for p in netpads[n]]
    pts = list(dict.fromkeys(pts))
    if len(pts) < 2:
        return []
    inT = [False] * len(pts); d = [math.inf] * len(pts); par = [-1] * len(pts); d[0] = 0; out = []
    for _ in range(len(pts)):
        i = min((k for k in range(len(pts)) if not inT[k]), key=lambda k: d[k])
        inT[i] = True
        if par[i] >= 0:
            out.append((pts[par[i]], pts[i]))
        for k in range(len(pts)):
            if not inT[k]:
                dd = math.dist(pts[i], pts[k])
                if dd < d[k]:
                    d[k], par[k] = dd, i
    return out


def cross(a, b2):
    (p1, p2), (p3, p4) = a, b2
    if p1 in (p3, p4) or p2 in (p3, p4):
        return False
    def o(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2, d3, d4 = o(p3, p4, p1), o(p3, p4, p2), o(p1, p2, p3), o(p1, p2, p4)
    return d1 * d2 < 0 and d3 * d4 < 0


edges = {n: mst(n) for n in netpads}


def score_nets(nets):
    """crossings involving the given nets' airwires (each pair once) and their total length"""
    c = 0
    others = [(m, e) for m, es in edges.items() for e in es]
    for n in nets:
        for e in edges[n]:
            for m, g in others:
                if m == n or (m in nets and m < n):
                    continue
                if cross(e, g):
                    c += 1
    length = sum(math.dist(*e) for n in nets for e in edges[n])
    return c, length


def total():
    allc = 0
    flat = [(n, e) for n, es in edges.items() for e in es]
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            if flat[i][0] != flat[j][0] and cross(flat[i][1], flat[j][1]):
                allc += 1
    return allc, sum(math.dist(*e) for _, e in flat)


courts = {r: court(f) for r, f in fps.items()}


def fits(ref):
    c = court(fps[ref])
    bb = c.BBox()
    if bb.GetLeft() < edge.GetLeft() or bb.GetRight() > edge.GetRight() or bb.GetTop() < edge.GetTop() or bb.GetBottom() > edge.GetBottom():
        return False
    for r, o in courts.items():
        if r == ref or o.OutlineCount() == 0:
            continue
        if not o.BBox().Intersects(bb):
            continue
        ob = o.BBox()                                       # courtyards here are rectangles: compare their boxes
        if min(bb.GetRight(), ob.GetRight()) - max(bb.GetLeft(), ob.GetLeft()) > 0.01 * NM and \
           min(bb.GetBottom(), ob.GetBottom()) - max(bb.GetTop(), ob.GetTop()) > 0.01 * NM:
            return False
    return True


c0, l0 = total()
print("start: %d crossings, %.0f mm of airwires" % (c0, l0))
start_rot = {r: f.GetOrientationDegrees() for r, f in fps.items()}
for it in range(8):
    improved = 0
    for ref in sorted(fps, key=lambda r: (-len(fps[r].Pads()), r)):
        if not movable(ref) or ref not in nets_of:
            continue
        f = fps[ref]; nets = nets_of[ref]
        cur = f.GetOrientationDegrees()
        best = (score_nets(nets), cur)
        for rot in (0, 90, 180, -90):
            if abs(((rot - cur) + 180) % 360 - 180) < 1:
                continue
            f.SetOrientationDegrees(rot)
            if not fits(ref):
                continue
            for n in nets:
                edges[n] = mst(n)
            s = score_nets(nets)
            if (s[0], s[1]) < (best[0][0], best[0][1] - 0.5):     # fewer crossings, or as many and 0.5 mm shorter
                best = (s, rot)
        f.SetOrientationDegrees(best[1])
        for n in nets:
            edges[n] = mst(n)
        courts[ref] = court(f)
        if abs(((best[1] - cur) + 180) % 360 - 180) > 1:
            improved += 1
    c1, l1 = total()
    print("pass %d: %d parts turned -> %d crossings, %.0f mm" % (it + 1, improved, c1, l1))
    if not improved:
        break

changed = {r: (start_rot[r], f.GetOrientationDegrees()) for r, f in fps.items() if abs(((f.GetOrientationDegrees() - start_rot[r]) + 180) % 360 - 180) > 1}
print("%d parts rotated:" % len(changed), ", ".join("%s %g->%g" % (r, a, c) for r, (a, c) in sorted(changed.items())))
if "--write" in sys.argv:
    s = open(PLACE).read()
    rot = {r: int(round(f.GetOrientationDegrees())) % 360 for r, f in fps.items() if movable(r)}
    old = re.search(r"\n# ---- rotation overrides \(tools/orient\.py\).*?\n# ---- end of rotation overrides\n", s, re.S)
    prev = {}
    if old:
        prev = dict(re.findall(r'"(\w+)": (-?\d+)', old.group(0)))
    block = ("\n# ---- rotation overrides (tools/orient.py): turns that untangle the ratsnest, applied on top of the table\n"
             "ROT = {%s}\nfor _r, _a in ROT.items():\n    P[_r] = (P[_r][0], P[_r][1], _a)\n# ---- end of rotation overrides\n"
             % ", ".join('"%s": %d' % (r, v) for r, v in sorted(rot.items()) if r in changed or r in prev))
    if old:
        s = s[:old.start()] + block + s[old.end():]
    else:
        i = s.index("board = pcbnew.LoadBoard(BOARD)")
        s = s[:i] + block.lstrip("\n") + s[i:]
    open(PLACE, "w").write(s)
    print("wrote the ROT block into", PLACE)
