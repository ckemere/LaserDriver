#!/usr/bin/env python3
"""Tie ground items stranded on pour islands back to the main ground pour.

    $KICAD_PY tools/fix_islands.py board.kicad_pcb drc.rpt

Targets: GND pads the DRC report lists as unconnected, plus GND vias that land
in neither layer's main pour fragment.  For each target, rings around it are
searched for a point inside the main (largest) pour fragment of some copper
layer that a straight track on that layer can reach without coming near other
nets; failing that, a new via is dropped where either layer's main pour is
reachable.  Added copper is locked; the zones are refilled.
"""
import math
import re
import sys

import pcbnew

MM = pcbnew.FromMM
VIA_D, DRILL, TRACK_W, CLEAR = 0.6, 0.3, 0.3, 0.22
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)


def seg_dist(px, py, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1
    t = max(0, min(1, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2))
    return math.hypot(px - (ax + t * (bx - ax)), py - (ay + t * (by - ay)))


def main(path, rpt):
    bad_pads = set(re.findall(r"(?i)pad (\S+) \[GND\] of (\S+)", open(rpt).read()))
    board = pcbnew.LoadBoard(path)
    gnd = board.FindNet("GND")
    zone = next(z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea())
    main_frag = {}
    for layer in LAYERS:
        ps = zone.GetFilledPolysList(layer)
        outs = [ps.Outline(i) for i in range(ps.OutlineCount())]
        main_frag[layer] = max(outs, key=lambda o: o.Area()) if outs else None

    def in_main(x, y, layer):
        o = main_frag[layer]
        return o is not None and o.PointInside(pcbnew.VECTOR2I(int(x), int(y)))

    # obstacles: other-net copper per layer, and every via (any net)
    obst = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == "GND":
                continue
            bb = p.GetBoundingBox()
            obst.append(("box", (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()),
                         {l for l in LAYERS if p.IsOnLayer(l)}))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c, r = t.GetPosition(), t.GetWidth() / 2
            if t.GetNetname() != "GND":
                obst.append(("box", (c.x - r, c.y - r, c.x + r, c.y + r), set(LAYERS)))
        elif t.GetNetname() != "GND":
            s, e = t.GetStart(), t.GetEnd()
            obst.append(("seg", ((s.x, s.y), (e.x, e.y), t.GetWidth() / 2), {t.GetLayer()}))
    gnd_vias = [t.GetPosition() for t in board.GetTracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]

    def clear(x, y, r, layers):
        for kind, g, on in obst:
            if not (on & layers):
                continue
            if kind == "box":
                x0, y0, x1, y1 = g
                if math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < r:
                    return False
            elif seg_dist(x, y, g[0], g[1]) < r + g[2]:
                return False
        return True

    def track_ok(a, b, layer):
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / MM(0.1)))
        return all(clear(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n,
                         MM(TRACK_W / 2 + CLEAR), {layer}) for i in range(n + 1))

    def add_track(a, b, layer):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(int(a[0]), int(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(int(b[0]), int(b[1])))
        t.SetWidth(MM(TRACK_W))
        t.SetLayer(layer)
        t.SetNet(gnd)
        t.SetLocked(True)
        board.Add(t)

    def add_via(x, y):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
        v.SetWidth(MM(VIA_D))
        v.SetDrill(MM(DRILL))
        v.SetNet(gnd)
        v.SetLocked(True)
        board.Add(v)

    targets = []                                   # (label, (x, y), layers reachable)
    for f in board.GetFootprints():
        for p in f.Pads():
            if (p.GetNumber(), f.GetReference()) in bad_pads:
                c = p.GetPosition()
                targets.append((f"{f.GetReference()}.{p.GetNumber()}", (c.x, c.y),
                                {l for l in LAYERS if p.IsOnLayer(l)}))
    for c in gnd_vias:
        if not any(in_main(c.x, c.y, l) for l in LAYERS):
            targets.append(("via@%.2f,%.2f" % tuple(pcbnew.ToMM(c)), (c.x, c.y), set(LAYERS)))

    fixed = []
    for label, (cx, cy), layers in targets:
        done = False
        for ring in (0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0):
            for k in range(36):
                ang = 2 * math.pi * k / 36
                x, y = cx + MM(ring) * math.cos(ang), cy + MM(ring) * math.sin(ang)
                # 1) plain track on a layer into that layer's main pour
                for layer in layers:
                    if in_main(x, y, layer) and clear(x, y, MM(TRACK_W / 2 + CLEAR), {layer}) \
                            and track_ok((cx, cy), (x, y), layer):
                        add_track((cx, cy), (x, y), layer)
                        done = True
                        break
                # 2) track on the pad's layer to a new via that reaches either main pour
                if not done and pcbnew.F_Cu in layers and \
                        any(in_main(x, y, l) for l in LAYERS) and \
                        clear(x, y, MM(VIA_D / 2 + CLEAR), set(LAYERS)) and \
                        all(math.hypot(x - v.x, y - v.y) > MM(VIA_D + 0.3) for v in gnd_vias) and \
                        track_ok((cx, cy), (x, y), pcbnew.F_Cu):
                    add_via(x, y)
                    add_track((cx, cy), (x, y), pcbnew.F_Cu)
                    gnd_vias.append(pcbnew.VECTOR2I(int(x), int(y)))
                    done = True
                if done:
                    fixed.append(label)
                    break
            if done:
                break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("island fixes:", fixed, "of", [t[0] for t in targets])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
