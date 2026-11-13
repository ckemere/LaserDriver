#!/usr/bin/env python3
"""Stitching vias for the outer-layer ground pours:  $KICAD_PY tools/stitch.py [--apply] [NET ...]
Every filled piece of a GND / GND_ISO pour on F.Cu or B.Cu that contains no via and no through-hole pad of its net gets
one 0.6 / 0.3 via at its visual centre (or the first interior grid point if the centre is outside the piece), so no
piece stays an island cut off by tracks.  Refill the zones (../tools/fill_zones.py) first, and again afterwards."""
import sys
import pcbnew

M = 1e6
apply = "--apply" in sys.argv
nets = [a for a in sys.argv[1:] if not a.startswith("--")] or ["GND", "GND_ISO"]
BOARD = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "StimHAT.kicad_pcb")
b = pcbnew.LoadBoard(BOARD)
mm = pcbnew.FromMM
vias = [(t.GetNetname(), t.GetPosition()) for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
tht = [(p.GetNetname(), p.GetPosition()) for f in b.GetFootprints() for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
added = []
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetNetname() not in nets:
        continue
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        if not z.IsOnLayer(layer):
            continue
        polys = z.GetFilledPolysList(layer)
        for i in range(polys.OutlineCount()):
            o = polys.Outline(i)
            poly = pcbnew.SHAPE_POLY_SET(); poly.AddOutline(o)
            for h in range(polys.HoleCount(i)):
                poly.AddHole(polys.Hole(i, h))
            if any(n == z.GetNetname() and poly.Contains(p) for n, p in vias + tht + added):
                continue
            bb = o.BBox()
            if bb.GetWidth() < mm(0.8) or bb.GetHeight() < mm(0.8):
                continue
            spot = None
            cx, cy = bb.Centre().x, bb.Centre().y
            cand = [(cx, cy)]
            for dx in range(-int(bb.GetWidth() / mm(0.5)) // 2, int(bb.GetWidth() / mm(0.5)) // 2 + 1):
                for dy in range(-int(bb.GetHeight() / mm(0.5)) // 2, int(bb.GetHeight() / mm(0.5)) // 2 + 1):
                    cand.append((cx + dx * mm(0.5), cy + dy * mm(0.5)))
            for x, y in cand:
                pt = pcbnew.VECTOR2I(int(x), int(y))
                # the via (0.3 mm radius) must lie inside the piece with its clearance: test 8 points on a 0.5 mm ring
                if all(poly.Contains(pcbnew.VECTOR2I(int(x + mm(0.38) * c), int(y + mm(0.38) * s)))
                       for c, s in ((1, 0), (-1, 0), (0, 1), (0, -1), (.7, .7), (-.7, .7), (.7, -.7), (-.7, -.7))):
                    spot = pt; break
            if spot is None:
                print("  no spot in a %s piece of %s at (%.1f, %.1f)" % (z.GetNetname(), z.GetZoneName(), bb.Centre().x / M, bb.Centre().y / M))
                continue
            added.append((z.GetNetname(), spot))
            print("  via %s at (%.2f, %.2f) for %s" % (z.GetNetname(), spot.x / M, spot.y / M, z.GetZoneName()))
print(len(added), "stitching vias")
if apply:
    for net, pt in added:
        v = pcbnew.PCB_VIA(b); v.SetPosition(pt); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNetCode(b.GetNetcodeFromNetname(net)); b.Add(v)
    pcbnew.SaveBoard(BOARD, b)
    print("applied")
