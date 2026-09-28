#!/usr/bin/env python3
"""Tie a ground-pour island to the main plane with one via (KiCad bundled Python).

    $KICAD_PY tools/island_via.py board.kicad_pcb REF.PAD [radius_mm]

Searches a 0.05 mm grid around the island pad for a via position (0.6/0.3 mm) that sits inside the
pad's own F.Cu pour fragment (or on the pad) and inside the largest B.Cu GND fragment, and clears all
other-net copper by the board clearance.  Adds the first (closest) hit, locked, and refills.
"""
import math
import sys

import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
VIA_D, VIA_DRILL, CLEAR = 0.6, 0.3, 0.15


def main(path, target, radius=3.5):
    board = pcbnew.LoadBoard(path)
    ref, num = target.split(".")
    pad = next(p for f in board.GetFootprints() if f.GetReference() == ref for p in f.Pads() if p.GetNumber() == num)
    zone = next(z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea())
    fps = zone.GetFilledPolysList(pcbnew.F_Cu)
    bps = zone.GetFilledPolysList(pcbnew.B_Cu)
    bmain = max((bps.Outline(i) for i in range(bps.OutlineCount())), key=lambda o: o.Area())
    pc = pad.GetPosition()
    ring = [pcbnew.VECTOR2I(int(pc.x + MM(0.6) * math.cos(a / 8 * math.pi)),
                            int(pc.y + MM(0.6) * math.sin(a / 8 * math.pi))) for a in range(16)]
    ffrags = [fps.Outline(i) for i in range(fps.OutlineCount())
              if any(fps.Outline(i).PointInside(q) for q in ring + [pc])]
    others = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() != "GND" or p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    others += [t for t in board.GetTracks() if t.GetNetname() != "GND"]
    holes = [p for f in board.GetFootprints() for p in f.Pads() if p.GetDrillSize().x > 0]
    gvias = [t for t in board.GetTracks() if t.GetNetname() == "GND" and t.GetClass() == "PCB_VIA"]
    edge = board.GetBoardEdgesBoundingBox()
    best = None
    n = int(radius / 0.05)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            c = pcbnew.VECTOR2I(pc.x + MM(0.05 * i), pc.y + MM(0.05 * j))
            d = math.hypot(i, j) * 0.05
            if d > radius or (best and d >= best[0]) or not edge.Contains(c):
                continue
            if not (pad.HitTest(c) or any(o.PointInside(c) for o in ffrags)) or not bmain.PointInside(c):
                continue
            r = MM(VIA_D / 2 + CLEAR)
            bad = False
            for o in others:
                for L in (pcbnew.F_Cu, pcbnew.B_Cu):
                    if o.IsOnLayer(L) and o.GetEffectiveShape(L).Collide(c, r):
                        bad = True
                        break
                if bad:
                    break
            if bad or any(math.hypot(TO(c.x - h.GetPosition().x), TO(c.y - h.GetPosition().y)) <
                          VIA_D / 2 + TO(h.GetDrillSize().x) / 2 + 0.25 for h in holes) or \
                    any(math.hypot(TO(c.x - v.GetPosition().x), TO(c.y - v.GetPosition().y)) < VIA_D + 0.25 for v in gvias):
                continue
            best = (d, c)
    if not best:
        print(f"{target}: no legal via position within {radius} mm")
        return 1
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(best[1])
    v.SetWidth(MM(VIA_D))
    v.SetDrill(MM(VIA_DRILL))
    v.SetNet(board.FindNet("GND"))
    v.SetLocked(True)
    board.Add(v)
    if not pad.HitTest(best[1]):         # join via and pad with a short track as well
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pc)
        t.SetEnd(best[1])
        t.SetWidth(MM(0.25))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(board.FindNet("GND"))
        t.SetLocked(True)
        board.Add(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print(f"{target}: via at ({TO(best[1].x):.2f}, {TO(best[1].y):.2f}), {best[0]:.2f} mm from the pad")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], *(float(a) for a in sys.argv[3:])))
