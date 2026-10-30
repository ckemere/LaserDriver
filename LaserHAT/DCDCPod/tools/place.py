#!/usr/bin/env python3
"""Placement of DCDCPod.kicad_pcb (2026-10-29; turned around 2026-10-30).  Pod coordinates: x 0-31 along the HAT's band,
y 0-22.5 down the pod (y 22.5 = bottom edge, 0.5 mm above the HAT; height above the HAT z = 23.0 - y).  The front
(F.Cu, every part) faces SOUTH, toward the BNC bodies, and is seen from the south, so HAT east is on the right:
HAT x = pod x + 15.  Headers J1 / J2 on the front, bottom edge, pins pointing down (rot 270; their footprints are
mirrored along the row by tools/make_footprints.py so the pin numbers increase eastward): their horizontal pins run
1.27 / 1.0 mm in front of the pod and land in the HAT's holes at HAT y 39.0, so the pod's front face is at HAT y
~37.9 and its back (1.6 mm board) at ~36.3, 5.3 mm south of the OLED bonnet's edge (y 31.0).
PS1 stands on the front at the TOP (pin row y 1.7, rot 0: pins 1 / 2 (5 V) west, 4 / 5 / 6 east, body y 0.43-6.43
below the pins), i.e. 16.6-22.6 mm above the HAT: its 10.16 mm body hangs south over the BNC bodies (15.6 mm tall).
Everything else below PS1, on the front (nothing below PS1 stands more than 1.3 mm out of the face; the BNC bodies
are 5.2 mm away):
  5 V side (x < 7.43): C104 between the +5V / GND tracks that run from PS1's pins 1 / 2 down to J1.
  negative block (x 10.3-18.4, y 6.7-16.4): L102 under PS1.4 and C106 under PS1.5 (the filter's ripple loop
  PS1.4 -> L102 -> C106 -> PS1.5 stays short), the -V_F bus below them, Q102 / R112 / C108 below the bus
  positive block (x 21.8-30.7, y 0.4-9.4, beside PS1's body): L101, Q101, C105, R111, C107
  test points on the back (B.Cu) over J2, reachable with the pod unplugged.
Barrier: 2.5 mm copper-free rule area on both layers = the gap between the named regions iso_region / hat_region
(DCDCPod.kicad_dru disallows copper of the other side in each region and asks 2.5 mm between the two net classes):
the vertical strip x 7.43-9.93 from the top edge to the bottom edge (between PS1's pins 2 and 4, 3.48 mm apart, and
east of J1.2), plus a strip x 9.93-21.5 along the bottom edge (y > 19.5, i.e. less than 3.5 mm above the HAT) where the
pod's face is over the HAT's own 5 V copper, so isolated copper near the HAT stays at x >= 21.5 (HAT x >= 36.5,
the HAT's isolated side).
Idempotent: re-running moves every footprint back and redraws the outline, rule areas and silk; copper is left alone.
    $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
W, H, R = 31.0, 22.5, 1.0                  # R 1.0 (was 1.5): keeps PS1's pin-1 silk mark (x 1.0, y 0.7-2.7) inside the corner
HAT_DX = 15.0                              # HAT x = pod x + HAT_DX (seen from the south)
mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot, flip)


def at(ref, x, y, rot=0, flip=False):
    P[ref] = (x, y, rot, flip)


# ---- headers on the bottom edge (rot 270, mirrored footprints: pins toward +y, pin numbers increase toward +x,
#      the footprint origin is the last pin).  Pads 3.6 mm (J2) / 4.4 mm (J1) above the bottom edge, as in rev A.
at("J2", 44.0 - HAT_DX, H - 3.6, 270)      # pins: 1 CAB x 23, 2 -V 25, 3 0V 27, 4 +V 29  (HAT J102: CAB 38, -V 40, 0V 42, +V 44)
at("J1", 21.54 - HAT_DX, H - 4.4, 270)     # pins: 1 5V x 4.0, 2 GND 6.54                (HAT J103: 5V 19, GND 21.54)
# ---- the DC-DC module at the top, pin 1 west (rot 0), body below the pin row
at("PS1", 3.6, 1.7, 0)                     # pins: 1 +Vin 3.6, 2 GND 6.14 | 4 -Vo 11.22, 5 0V 13.76, 6 +Vo 16.3; body y 0.43-6.43 (RECOM: 1.27 behind / 4.73 in front)
# ---- 5 V side
at("C104", 4.87, 7.6, 0)                   # pad 1 (+5V) west on the +5V track, pad 2 (GND) east on the GND track
# ---- negative block (0805 vertical: rot 90 = pad 1 at the bottom, rot 270 = pad 1 at the top)
at("L102", 11.22, 8.6, 270)                # pad 1 (-V_RAW) top, under PS1.4
at("C106", 13.76, 8.6, 270)                # pad 1 (0V) top, under PS1.5; pad 2 (-V_F) bottom
at("Q102", 16.7, 11.54, 90)                # C top on the -V_F bus (y 10.6), B south-west, E south-east
at("R112", 13.9, 12.0, 90)                 # pad 2 (-V_F) top, pad 1 (QB_N) bottom
at("C108", 13.9, 14.7, 90)                 # pad 2 (QB_N) top, pad 1 (0V) bottom
# ---- positive block, east of PS1's body
at("L101", 23.6, 1.3, 0)                   # pad 1 (+V_RAW) west
at("Q101", 27.4, 2.25, 180)                # C west, E north-east, B south-east
at("C105", 25.0, 5.8, 270)                 # pad 1 (+V_F) top, pad 2 (0V) bottom
at("R111", 27.5, 5.5, 0)                   # pad 1 (+V_F) west, pad 2 (QB_P) east
at("C107", 29.0, 7.7, 270)                 # pad 1 (QB_P) top, pad 2 (0V) bottom
# ---- test points on the back, over J2
at("TP2", 21.0, 15.5, 0, True); at("TP3", 25.0, 15.5, 0, True); at("TP1", 29.0, 15.5, 0, True)

board = pcbnew.LoadBoard(BOARD)
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea()]
board.SetCopperLayerCount(2)
board.GetDesignSettings().SetBoardThickness(mm(1.6))   # 1.6 mm since 2026-10-30 (the back faces the bonnet, 5.3 mm away)
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
BX0, BX1 = 7.43, 9.93                      # vertical strip: PS1.2 pad edge 6.94 / PS1.4 10.42, J1.2 pad edge 7.39
BY, BX2 = 19.5, 21.5                       # bottom strip y > 19.5 (< 3.5 mm above the HAT: 2.5 mm over the band's 1 mm parts) up to HAT x 36.5
BARRIER = [(BX0, 0.0), (BX1, 0.0), (BX1, BY), (BX2, BY), (BX2, H), (BX0, H)]
ISO = [(BX1, 0.0), (W, 0.0), (W, H), (BX2, H), (BX2, BY), (BX1, BY)]
HAT = [(0.0, 0.0), (BX0, 0.0), (BX0, H), (0.0, H)]
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


# front: pin names over the headers (between their courtyards' top and the pads), the two sides
for txt, x in (("CAB", 23.0), ("-V", 25.0), ("0V", 27.0), ("+V", 29.0)):
    silk(txt, x, 17.3, 0.8)
for txt, x in (("5V", 4.0), ("GND", 6.54)):
    silk(txt, x, 16.3, 0.8)
silk("ISOLATED", 22.4, 11.5, 0.8, 90)
silk("5V SIDE", 1.7, 11.5, 0.8, 90)
# back (mirrored): title and the test-point names
silk("DC-DC POD", 15.5, 4.0, 0.9, 0, pcbnew.B_SilkS)
silk("5V -> \u00b115V  rev A", 15.5, 6.0, 0.8, 0, pcbnew.B_SilkS)
for txt, x in (("0V", 21.0), ("-V", 25.0), ("+V", 29.0)):
    silk(txt, x, 13.9, 0.8, 0, pcbnew.B_SilkS)
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
