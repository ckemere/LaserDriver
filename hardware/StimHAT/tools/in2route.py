#!/usr/bin/env python3
"""Join a net's vias / through-hole pads with tracks on In2.Cu:  $KICAD_PY tools/in2route.py [--apply] [--w 0.3] NET ...
Minimum spanning tree over the net's terminals; each edge is laid as a straight segment, else an L (both orders), else
a Z through an offset mid-point, checking every segment against the other vias and through-hole pads (0.25 mm
clearance), the rule areas that forbid tracks, the board edge and the other nets' In2 tracks.  Failed edges are listed.
Written for the StimHAT's isolated power rails after the In2 islands were dropped (2026-10-29)."""
import math
import os
import sys
import pcbnew

M = 1e6
argv = sys.argv[1:]
apply = "--apply" in argv
w = 0.3
if "--w" in argv:
    w = float(argv[argv.index("--w") + 1]); del argv[argv.index("--w"):argv.index("--w") + 2]
nets = [a for a in argv if not a.startswith("--")]
BOARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "StimHAT.kicad_pcb")
b = pcbnew.LoadBoard(BOARD)
mm = pcbnew.FromMM
CLR = 0.25


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def seg_seg_dist(a, c):
    (x1, y1, x2, y2), (x3, y3, x4, y4) = a, c
    def ccw(ax, ay, bx, by, cx, cy):
        return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)
    if ccw(x1, y1, x3, y3, x4, y4) != ccw(x2, y2, x3, y3, x4, y4) and ccw(x1, y1, x2, y2, x3, y3) != ccw(x1, y1, x2, y2, x4, y4):
        return 0.0
    return min(seg_dist(x1, y1, x3, y3, x4, y4), seg_dist(x2, y2, x3, y3, x4, y4), seg_dist(x3, y3, x1, y1, x2, y2), seg_dist(x4, y4, x1, y1, x2, y2))


# obstacles on In2: round items (x, y, radius, net), rectangles (x0, y0, x1, y1) = rule areas forbidding tracks
rounds, rects = [], []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition(); rounds.append((p.x / M, p.y / M, t.GetWidth() / 2 / M, t.GetNetname()))
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            pos, sz = p.GetPosition(), p.GetSize()
            rounds.append((pos.x / M, pos.y / M, max(sz.x, sz.y) / 2 / M, p.GetNetname()))
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(pcbnew.In2_Cu):
        bb = z.GetBoundingBox(); rects.append((bb.GetLeft() / M, bb.GetTop() / M, bb.GetRight() / M, bb.GetBottom() / M))
others = [(t.GetNetname(), t.GetStart().x / M, t.GetStart().y / M, t.GetEnd().x / M, t.GetEnd().y / M, t.GetWidth() / M)
          for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In2_Cu]
edge_x, edge_y = (0.3 + w / 2, 65 - 0.3 - w / 2), (0.3 + w / 2, 57 - 0.3 - w / 2)


def seg_ok(net, x1, y1, x2, y2):
    for x, y, r, n in rounds:
        if n != net and seg_dist(x, y, x1, y1, x2, y2) < r + w / 2 + CLR:
            return False
    for x0, y0, xa, ya in rects:            # distance from the segment to the rectangle must exceed w/2 (plus a hair)
        cx, cy = min(max((x1 + x2) / 2, x0), xa), min(max((y1 + y2) / 2, y0), ya)
        for px, py in ((x1, y1), (x2, y2), ((x1 + x2) / 2, (y1 + y2) / 2)):
            if x0 - w / 2 - 0.05 < px < xa + w / 2 + 0.05 and y0 - w / 2 - 0.05 < py < ya + w / 2 + 0.05:
                return False
        # segment crossing the rectangle: sample along it
        n = int(math.hypot(x2 - x1, y2 - y1) / 0.2) + 1
        for k in range(n + 1):
            px, py = x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n
            if x0 - w / 2 - 0.05 < px < xa + w / 2 + 0.05 and y0 - w / 2 - 0.05 < py < ya + w / 2 + 0.05:
                return False
    for n, ax, ay, bx, by, ow in others:
        if n != net and seg_seg_dist((x1, y1, x2, y2), (ax, ay, bx, by)) < w / 2 + ow / 2 + CLR:
            return False
    for px, py in ((x1, y1), (x2, y2)):
        if not (edge_x[0] <= px <= edge_x[1] and edge_y[0] <= py <= edge_y[1]):
            return False
    return True


def path_ok(net, pts):
    return all(seg_ok(net, *pts[i], *pts[i + 1]) for i in range(len(pts) - 1))


def route_edge(net, a, c):
    cands = [[a, c], [a, (c[0], a[1]), c], [a, (a[0], c[1]), c]]
    for off in (1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0):
        mx = (a[0] + c[0]) / 2 + off
        cands.append([a, (mx, a[1]), (mx, c[1]), c])
        my = (a[1] + c[1]) / 2 + off
        cands.append([a, (a[0], my), (c[0], my), c])
    for off in (1.0, -1.0, 2.0, -2.0, 3.0, -3.0):
        cands.append([a, (a[0] + off, a[1] + off), (c[0] + off, a[1] + off), (c[0] + off, c[1] - off), c])
        cands.append([a, (a[0] + off, a[1] - off), (c[0] - off, a[1] - off), (c[0] - off, c[1] + off), c])
    for pts in cands:
        if path_ok(net, pts):
            return pts
    return None


new = []
for net in nets:
    term = [(x, y) for x, y, r, n in rounds if n == net]
    if len(term) < 2:
        print(net, ": fewer than 2 terminals on In2"); continue
    # Prim's MST
    done, todo = {term[0]}, set(term[1:])
    edges = []
    while todo:
        a, c = min(((p, q) for p in done for q in todo), key=lambda e: math.hypot(e[0][0] - e[1][0], e[0][1] - e[1][1]))
        edges.append((a, c)); done.add(c); todo.remove(c)
    ok = 0
    for a, c in edges:
        pts = route_edge(net, a, c)
        if pts is None:
            print("  %s: no path (%.2f, %.2f) -> (%.2f, %.2f)" % (net, a[0], a[1], c[0], c[1])); continue
        ok += 1
        for i in range(len(pts) - 1):
            x1, y1, x2, y2 = *pts[i], *pts[i + 1]
            if (x1, y1) != (x2, y2):
                new.append((net, x1, y1, x2, y2)); others.append((net, x1, y1, x2, y2, w))
    print("%s: %d terminals, %d / %d edges routed" % (net, len(term), ok, len(edges)))
if apply:
    for net, x1, y1, x2, y2 in new:
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(w)); t.SetLayer(pcbnew.In2_Cu); t.SetNetCode(b.GetNetcodeFromNetname(net)); b.Add(t)
    pcbnew.SaveBoard(BOARD, b)
    print("applied", len(new), "segments")
