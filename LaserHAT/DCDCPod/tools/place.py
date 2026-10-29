#!/usr/bin/env python3
"""Placement of DCDCPod.kicad_pcb (2026-10-29).  Pod coordinates: x 0-31 along the HAT's band (pod x = 46 - HAT x,
because the pod faces north and is seen from the north), y 0-19.5 down the pod (y 19.5 = bottom edge, 0.5 mm above the
HAT).  Headers J1 / J2 on the front, bottom edge, pins pointing down (rot 270): their horizontal pins run 1.27 / 1.0 mm
in front of the pod and land in the HAT's holes at HAT y 40.1, so the pod's front face is at HAT y ~41.2 and its back
(1.2 mm board) at ~42.4, 0.7 mm north of the BNC bodies.  PS1 stands on the front with its pins 1 / 2 (5 V) east of
the barrier, body toward the pod's top edge (marked face up).  Everything else on the front, above PS1:
  bottom row (y 5.55): C105 L101 | C106 L102 (0805, vertical);  top row (y 1.95): Q101 R111 C107 | C108 R112 Q102
  (courtyards 0.05-0.1 mm apart: the 6.4 mm between the top edge and PS1's courtyard hold exactly two rows).
  5 V side: C104 right of PS1's body, J1 below it.  Test points on the back (B.Cu), reachable with the pod unplugged.
Barrier: 2.5 mm copper-free rule area on both layers = the gap between the named regions iso_region / hat_region
(DCDCPod.kicad_dru disallows copper of the other side in each region and asks 2.5 mm between the two net classes):
vertical strip x 11.4-13.9 between PS1's pins 2 and 4 from y 6.65 down to the bottom edge, then across PS1's body at
y 6.65-9.15 to x 22.5 and up to the top edge at x 20-22.5, so the isolated parts may use the top strip over PS1.
Idempotent: re-running moves every footprint back and redraws the outline, rule areas and silk; copper is left alone.
    $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
W, H, R = 31.0, 19.5, 1.5
mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot, flip)


def at(ref, x, y, rot=0, flip=False):
    P[ref] = (x, y, rot, flip)


# ---- headers on the bottom edge (rot 270: pins toward +y, pin numbers increase toward -x)
at("J2", 8.0, 15.9, 270)                  # pins: 1 CAB x 8, 2 -V 6, 3 0V 4, 4 +V 2  (HAT J102: CAB 38, -V 40, 0V 42, +V 44)
at("J1", 27.0, 15.1, 270)                 # pins: 1 5V x 27, 2 GND 24.46            (HAT J103: 5V 19, GND 21.54)
# ---- the DC-DC module, pin 1 east (rot 180), body toward the top edge
at("PS1", 17.74, 12.8, 180)               # pins: 1 +Vin 17.74, 2 GND 15.2 | 4 -Vo 10.12, 5 0V 7.58, 6 +Vo 5.04; body y 7.7-13.7
# ---- isolated side, bottom row (0805 vertical; rot 90 = pad 1 at the bottom, rot 270 = pad 1 at the top)
at("C105", 2.4, 5.55, 270); at("L101", 4.9, 5.55, 90); at("C106", 7.3, 5.55, 90); at("L102", 10.1, 5.55, 90)
# ---- isolated side, top row
at("Q101", 2.2, 1.95, 0); at("R111", 4.75, 1.6, 90); at("C107", 6.4, 1.95, 270)
at("C108", 8.55, 1.95, 90); at("R112", 10.15, 1.6, 270); at("Q102", 12.9, 2.05, 90)   # Q102: C top, B left, E right
# ---- 5 V side
at("C104", 22.5, 10.8, 270)               # pad 1 (+5V) top
# ---- test points on the back
at("TP1", 2.0, 18.3, 0, True); at("TP2", 6.0, 18.5, 0, True); at("TP3", 10.5, 15.0, 0, True)

board = pcbnew.LoadBoard(BOARD)
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea()]
board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(mm(1.2))
fps = {f.GetReference(): f for f in board.GetFootprints()}
missing = [r for r in fps if r not in P]
assert not missing, f"unplaced: {missing}"
for ref, (x, y, rot, flip) in P.items():
    f = fps[ref]
    if f.IsFlipped() != flip:
        f.Flip(f.GetPosition(), False)
    f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    f.SetOrientationDegrees(rot)
    f.Reference().SetVisible(False)             # no designators or values on the silk
    f.Value().SetVisible(False)


def seg(x1, y1, x2, y2, layer=pcbnew.F_SilkS, w=0.15):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_SEGMENT); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); d.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    board.Add(d)


def arc(cx, cy, r, a0, a1, layer=pcbnew.Edge_Cuts, w=0.1):
    """arc on circle (cx, cy, r) from angle a0 to a1 (degrees, screen coordinates: y down)"""
    pts = [pcbnew.VECTOR2I(mm(cx + r * math.cos(math.radians(a))), mm(cy + r * math.sin(math.radians(a))))
           for a in (a0, (a0 + a1) / 2, a1)]
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_ARC); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetArcGeometry(*pts)
    board.Add(d)


def rect(x1, y1, x2, y2, layer, w):
    for (a, b), (c, d) in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        seg(a, b, c, d, layer, w)


# outline: rounded rectangle
E = pcbnew.Edge_Cuts
seg(R, 0, W - R, 0, E, 0.1); arc(W - R, R, R, 270, 360)
seg(W, R, W, H - R, E, 0.1); arc(W - R, H - R, R, 0, 90)
seg(W - R, H, R, H, E, 0.1); arc(R, H - R, R, 90, 180)
seg(0, H - R, 0, R, E, 0.1); arc(R, R, R, 180, 270)


def rule_area(name, pts, keepout):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(keepout); z.SetDoNotAllowVias(keepout); z.SetDoNotAllowCopperPour(keepout)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


# the 2.5 mm barrier (copper-free on both layers) and the two named regions whose gap it is
BARRIER = [(11.4, 6.65), (20.0, 6.65), (20.0, 0.0), (22.5, 0.0), (22.5, 9.15), (13.9, 9.15), (13.9, H), (11.4, H)]
ISO = [(0.0, 0.0), (20.0, 0.0), (20.0, 6.65), (11.4, 6.65), (11.4, H), (0.0, H)]
HAT = [(22.5, 0.0), (W, 0.0), (W, H), (13.9, H), (13.9, 9.15), (22.5, 9.15)]
rule_area("barrier", BARRIER, True)
rule_area("iso_region", ISO, False)
rule_area("hat_region", HAT, False)
for (a, b), (c, d) in zip(BARRIER, BARRIER[1:] + BARRIER[:1]):
    seg(a, b, c, d, pcbnew.Cmts_User, 0.1)


def silk(txt, x, y, size=0.8, rot=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15 * size))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


silk("DC-DC POD", 26.6, 3.2, 0.85); silk("5V -> \u00b115V", 26.5, 5.0, 0.8); silk("rev A", 26.6, 6.6, 0.8)
for txt, x in (("+V", 2.0), ("0V", 4.0), ("-V", 5.9), ("CAB", 8.3)):
    silk(txt, x, 14.6, 0.8)                  # between PS1's silk outline (y 13.82) and J2's pads (y 15.225)
for txt, x in (("5V", 27.0), ("GND", 24.46)):
    silk(txt, x, 13.5, 0.8)
silk("ISOLATED", 17.6, 1.2, 0.8); silk("5V SIDE", 26.0, 8.6, 0.8)
silk("DC-DC POD rev A", 15.5, 8.0, 0.9, 0, pcbnew.B_SilkS)
for txt, x, y in (("+V", 3.9, 18.3), ("0V", 7.9, 18.5), ("-V", 12.4, 15.0)):
    silk(txt, x, y, 0.8, 0, pcbnew.B_SilkS)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
# report the pad positions the router relies on
board = pcbnew.LoadBoard(BOARD)
for f in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
    pads = ", ".join(f"{p.GetNumber()}:{p.GetNetname()}@({p.GetPosition().x / 1e6:.3f},{p.GetPosition().y / 1e6:.3f})"
                     for p in f.Pads())
    print(f"  {f.GetReference():5s} {'B' if f.IsFlipped() else 'F'} {pads}")
