#!/usr/bin/env python3
"""GND stitching vias on a grid wherever there is room (KiCad bundled Python).

    $KICAD_PY tools/stitch.py board.kicad_pcb [pitch_mm]

Ties the F.Cu and B.Cu ground pours together so no pour island is left
floating.  A via is dropped only where it clears every other-net pad, track
and via, the board edge, cut-outs and connector/switch courtyards.
"""
import math
import sys

import pcbnew

MM = pcbnew.FromMM
VIA_D, DRILL, CLEAR = 0.6, 0.3, 0.3


def main(path, pitch):
    board = pcbnew.LoadBoard(path)
    gnd = board.FindNet("GND")
    boxes = []
    for f in board.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            boxes.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
        # tented vias may sit under a part body, but not under connectors/switches/BNCs
        # (mechanical parts that sit flush or get hand-soldered)
        if f.GetReference()[:1] in "JS":
            for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                cy = f.GetCourtyard(layer)
                if cy.OutlineCount():
                    bb = cy.BBox()
                    boxes.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
    segs = []
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c, r = t.GetPosition(), t.GetWidth() / 2
            boxes.append((c.x - r, c.y - r, c.x + r, c.y + r))
        else:
            segs.append((t.GetStart(), t.GetEnd(), t.GetWidth() / 2))
    edges = [(d.GetStart(), d.GetEnd(), 0) for d in board.GetDrawings()
             if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT]
    rule_areas = [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    bb = board.GetBoardEdgesBoundingBox()
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline)

    def seg_dist(x, y, a, b):
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1
        t = max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
        return math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay)))

    # Pour fragments that are really part of the ground: the biggest one on each
    # layer plus any that hold a GND pad.  A stitching via must land in one of
    # those on at least one layer, otherwise it would just join two floating
    # fragments into a floating via "antenna".
    zone = next((z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea()), None)
    good = {}
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ps = zone.GetFilledPolysList(layer) if zone else pcbnew.SHAPE_POLY_SET()
        outs = [ps.Outline(i) for i in range(ps.OutlineCount())]
        biggest = max(outs, key=lambda o: o.Area()) if outs else None
        gpads = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads()
                 if p.GetNetname() == "GND" and p.IsOnLayer(layer)]
        good[layer] = [o for o in outs if o is biggest or any(o.PointInside(c) for c in gpads)]

    def in_good(pt):
        return any(o.PointInside(pt) for layer in good for o in good[layer])

    r = MM(VIA_D / 2) + MM(CLEAR)
    added = 0
    y = bb.GetY() + MM(1.5)
    while y < bb.GetBottom() - MM(1.5):
        x = bb.GetX() + MM(1.5)
        while x < bb.GetRight() - MM(1.5):
            pt = pcbnew.VECTOR2I(int(x), int(y))
            ok = outline.Contains(pt) and in_good(pt)   # real outline; main pour only
            ok = ok and all(not (x0 - r < x < x1 + r and y0 - r < y < y1 + r) for x0, y0, x1, y1 in boxes)
            ok = ok and all(seg_dist(x, y, a, b) > r + w for a, b, w in segs)
            ok = ok and all(seg_dist(x, y, a, b) > MM(1.0) for a, b, _ in edges)
            ok = ok and not any(z.Outline().Contains(pcbnew.VECTOR2I(int(x), int(y))) for z in rule_areas)
            if ok:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pt)
                v.SetWidth(MM(VIA_D))
                v.SetDrill(MM(DRILL))
                v.SetNet(gnd)
                board.Add(v)
                boxes.append((x - MM(VIA_D / 2), y - MM(VIA_D / 2), x + MM(VIA_D / 2), y + MM(VIA_D / 2)))
                added += 1
            x += MM(pitch)
        y += MM(pitch)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("stitching vias:", added)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 4.0)
