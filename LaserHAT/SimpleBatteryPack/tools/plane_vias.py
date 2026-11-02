#!/usr/bin/env python3
"""Drop a via to a plane next to every SMD pad of a net that the DRC reports as unconnected (2026-10-31).
    $KICAD_PY tools/plane_vias.py NET [NET ...] [--pad REF.PAD ...] [--apply]
--pad also takes a pad the DRC does not name (a group of pads tied by tracks but off the plane shows up as a track).
For a net with a plane (0V: the B.Cu pour on 2 layers, In1.Cu on 4): each such pad gets a short stub on its own layer and a via; candidate spots
on rings 0.8-3.0 mm around the pad, nearest first, kept only where the via (0.6 / 0.3) and the stub clear every other
net's pads, tracks and vias on every layer by 0.3 mm (0.5 mm from the 33.6 V nets), holes by 0.25 mm, the board edge
and the no-via rule areas.  The plane re-flows around the result on the refill.  Without --apply: dry run."""
import json
import math
import os
import subprocess
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "SimpleBatteryPack.kicad_pcb")
KICAD_CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
PADS = {sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--pad"}
NETS = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--pad"]
HV = {"+BATB", "+SW", "+OUT"}
VIA_D, VIA_DRILL, CLR, CLR_HV, HOLE_CLR, EDGE_CLR = 0.6, 0.3, 0.3, 0.5, 0.25, 0.5
NM = 1e6
V = lambda x, y: pcbnew.VECTOR2I(int(round(x * NM)), int(round(y * NM)))  # noqa: E731

out = os.path.join(ROOT, "route", "plane_vias_drc.json")
subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "-o", out, BOARD], capture_output=True)
want = set()
for u in json.load(open(out))["unconnected_items"]:
    for i in u["items"]:
        if i["description"].startswith("Pad ") and any("[%s]" % n in i["description"] for n in NETS):
            want.add((round(i["pos"]["x"], 3), round(i["pos"]["y"], 3)))

b = pcbnew.LoadBoard(BOARD)
pads = [p for f in b.GetFootprints() for p in f.Pads()]
tracks = list(b.GetTracks())
keepouts = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
edge = b.GetBoardEdgesBoundingBox()
cu = list(pcbnew.LSET.AllCuMask(b.GetCopperLayerCount()).Seq())


def clear_of_others(shape, net, layers, is_via):
    for it in pads + tracks:
        if it.GetNetname() == net:
            continue
        c = int((CLR_HV if (it.GetNetname() in HV or net in HV) else CLR) * NM)
        for lay in layers:
            if it.IsOnLayer(lay) and it.GetEffectiveShape(lay).Collide(shape, c):
                return False
        if is_via and getattr(it, "HasHole", lambda: False)() and it.GetEffectiveHoleShape().Collide(shape, int(HOLE_CLR * NM)):
            return False
    return True


added = []
for p in pads:
    pos = (round(p.GetX() / NM, 3), round(p.GetY() / NM, 3))
    named = "%s.%s" % (p.GetParentFootprint().GetReference(), p.GetNumber()) in PADS
    if (pos not in want and not named) or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
        continue
    net = p.GetNetname()
    lay = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
    w = min(0.4, p.GetSize(lay).x / NM, p.GetSize(lay).y / NM)
    px, py = p.GetX() / NM, p.GetY() / NM
    done = False
    for r in [0.8 + 0.2 * k for k in range(12)]:
        for k in range(24):
            a = 2 * math.pi * k / 24
            x, y = px + r * math.cos(a), py + r * math.sin(a)
            vp = V(x, y)
            if not (edge.GetLeft() + EDGE_CLR * NM < vp.x < edge.GetRight() - EDGE_CLR * NM and edge.GetTop() + EDGE_CLR * NM < vp.y < edge.GetBottom() - EDGE_CLR * NM):
                continue
            if any(z.Outline().Contains(vp) for z in keepouts):
                continue
            via = pcbnew.SHAPE_CIRCLE(vp, int(VIA_D / 2 * NM))
            seg = pcbnew.SHAPE_SEGMENT(p.GetPosition(), vp, int(w * NM))
            if not clear_of_others(via, net, cu, True) or not clear_of_others(seg, net, [lay], False):
                continue
            v = pcbnew.PCB_VIA(b); v.SetPosition(vp); v.SetWidth(int(VIA_D * NM)); v.SetDrill(int(VIA_DRILL * NM)); v.SetNet(p.GetNet())
            t = pcbnew.PCB_TRACK(b); t.SetStart(p.GetPosition()); t.SetEnd(vp); t.SetWidth(int(w * NM)); t.SetLayer(lay); t.SetNet(p.GetNet())
            b.Add(v); b.Add(t)
            tracks += [v, t]
            added.append("%s %s.%s (%.2f, %.2f) -> via (%.2f, %.2f), %.1f mm" % (net, p.GetParentFootprint().GetReference(), p.GetNumber(), px, py, x, y, r))
            done = True
            break
        if done:
            break
    if not done:
        added.append("%s %s.%s (%.2f, %.2f): no room for a via within 3 mm" % (net, p.GetParentFootprint().GetReference(), p.GetNumber(), px, py))
for a in added:
    print(" ", a)
if "--apply" in sys.argv:
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(BOARD, b)
    print("saved", BOARD)
