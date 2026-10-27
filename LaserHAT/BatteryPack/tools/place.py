#!/usr/bin/env python3
"""Placement of BatteryPack.kicad_pcb (rev C, 100 x 100 mm, 2026-10-27): the two hobby 4S packs sit under the board (long
axis along y, 42 mm pitch, two 20 mm straps through the slots), their XT60 discharge plugs and balance leads come round the front edge
(y = 100) to the XT60 sockets J7 / J8 and the right-angle XH sockets J5 / J6 (pack A left, pack B right).  Top side: pack A's gauge top left, its balancers
mid left, its -V chain bottom left; the charger top right with the USB-C on the right edge; pack B's balancers mid right,
its gauge and +V chain bottom right; the toggle bottom centre with the output header J3 beside it.  H5-H8 are a
Raspberry Pi's holes (58 x 49): the Pi sits over y 4-60 on standoffs, ports end over the right edge; the HAT's
outline is drawn on User.Comments and the Pi's on User.Drawings.
Idempotent: re-running moves every footprint back to the table and redraws the outline, slots and board-level silk;
copper is left alone (rip it up first with tools/autoroute.py if the placement changes).      $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "BatteryPack.kicad_pcb")
W, H = 100.0, 100.0
PACKS = ((7.0, 45.0), (51.0, 89.0))                       # x extents of the two pack envelopes (y 10..90), bottom side
SLOTS = ((3.0, 6.5), (45.75, 50.25), (90.5, 94.0))        # strap slots, x extents; y 39..61

mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot)


def at(ref, x, y, rot=0):
    P[ref] = (x, y, rot)


# ---- mounting holes
at("H1", 4, 4); at("H2", 96, 4); at("H3", 4, 96); at("H4", 96, 96)
# ---- Raspberry Pi holes (58 x 49, M2.5): the Pi sits over the quiet half of the board (y 4-60) on standoffs, its ports
# end 10.5 mm past the right edge; the toggle, the pack sockets and every LED stay uncovered
PI = ((29.5, 7.5), (87.5, 7.5), (29.5, 56.5), (87.5, 56.5))
for ref, (x, y) in zip(("H5", "H6", "H7", "H8"), PI):
    at(ref, x, y)
# ---- pack sockets along the front edge: XH balance (J5 / J6, opening toward the edge) outboard, XT60 (J7 / J8, face flush
# with the edge, "-" pin outboard) inboard; toggle and output header between the XT60s; link fuse and pull-down above
at("J5", 10.5, 91.5); at("J6", 79.5, 91.5)
at("J7", 36, 83.1, 180); at("J8", 69, 83.1, 180)
at("J3", 45.5, 94.5)
at("SW1", 49, 84)
at("F3", 40, 70, 90); at("R30", 40, 76)


def balancer(u, q, rv, c, rb, x0, y0):
    """HY2213 block (U, Q, bleed R 1206, VDD R, C): 14 x 8 mm, parts at y0 and y0 + 4"""
    at(u, x0 + 2, y0); at(q, x0 + 7, y0); at(rb, x0 + 11, y0, 90)
    at(rv, x0 + 2, y0 + 4); at(c, x0 + 7, y0 + 4)


# ---- balancers: pack A (U6..U9, Q7..Q10, R35..R38 bleed, R31..R34, C12..C15) mid left, pack B mid right, 2 x 2 each
for n in range(4):
    x0, y0 = 9 + 16 * (n % 2), 38 + 10 * (n // 2)
    balancer(f"U{6 + n}", f"Q{7 + n}", f"R{31 + n}", f"C{12 + n}", f"R{35 + n}", x0, y0)
    balancer(f"U{10 + n}", f"Q{15 + n}", f"R{58 + n}", f"C{16 + n}", f"R{62 + n}", x0 + 44, y0)
# ---- pack A gauge, top left: LEDs on the left edge, comparators, reference and ladder
for ref, y in (("D4", 10), ("D3", 14), ("D2", 18), ("D1", 22)):
    at(ref, 3.5, y, 90)
for ref, y in (("R15", 10), ("R14", 14), ("R13", 18), ("R12", 22)):
    at(ref, 9.5, y)
at("C1", 16, 7.5); at("U1", 16, 12); at("U2", 16, 20); at("C2", 16, 25); at("Q14", 21, 28)
at("U3", 24, 8); at("R3", 24, 11)
for i, ref in enumerate(("R4", "R5", "R6", "R7", "R8")):
    at(ref, 24, 14 + 2.5 * i)
at("R9", 30, 12.5); at("R10", 30, 15); at("R11", 30, 17.5)
# ---- pack A -V chain, bottom left (above J5)
at("F2", 10, 70, 90); at("Q11", 16, 70); at("R39", 16, 73.5); at("R40", 16, 75.5)
at("D15", 28, 68, 90); at("D16", 28, 76, 90)
# ---- charger, top right: USB-C on the right edge, CH224A, VBUS switch, CN3704 and its passives, CHRG / DONE LEDs
at("J1", 95.8, 14, 90)                     # front flush with the right edge (courtyard +y end = 4.2 mm from origin)
at("U4", 84, 14); at("C3", 81.5, 9.5); at("R24", 84, 18.5)
at("Q13", 76, 9); at("R43", 71.5, 7.5); at("R44", 71.5, 10)
at("Q12", 76, 14); at("R41", 71.5, 13.5); at("R42", 71.5, 16)
at("C5", 64, 10); at("C6", 64, 16)
at("U5", 82, 27); at("C4", 82, 22.5); at("Q6", 91.5, 23); at("D7", 92, 29, 90); at("L1", 86, 35)
at("D8", 74, 31); at("R25", 70, 22); at("R26", 70, 25); at("C7", 64, 23); at("C8", 64, 26.5)
at("C9", 76, 20); at("C10", 79.5, 20); at("C11", 73, 20); at("R27", 76, 17.5)
at("RT1", 58, 30)
# CHRG / DONE LEDs on the top edge (y 2.5), outside the Pi's edge (y 4), above the charger
at("R28", 66.5, 2.5); at("D9", 70, 2.5); at("R29", 79, 2.5); at("D10", 82.5, 2.5)
# ---- pack B gauge, lower right: LEDs on the right edge
for ref, y in (("D14", 66), ("D13", 70), ("D12", 74), ("D11", 78)):
    at(ref, 97.5, y, 90)
for ref, y in (("R57", 66), ("R56", 70), ("R55", 74)):
    at(ref, 92.5, y)
at("U16", 63, 64); at("R45", 63, 67)
for i, ref in enumerate(("R46", "R47", "R48", "R49", "R50")):
    at(ref, 63, 69 + 2.5 * i)
at("R51", 68, 64); at("R52", 68, 66.5); at("R53", 68, 69)
at("C20", 70.5, 66, 90); at("U14", 76, 66); at("C21", 70.5, 74, 90); at("U15", 76, 74)
# ---- pack B +V chain, right of its gauge (x 81-90, y 62-80), above J6
at("F1", 83, 65, 90); at("Q1", 83, 70); at("R1", 87.5, 64); at("R2", 87.5, 66.5)
at("R54", 87.5, 69)                                      # ON LED resistor on +OUT; its thin net runs to D11 in the LED column
at("D5", 83, 77, 90); at("D6", 88, 76, 90)

board = pcbnew.LoadBoard(BOARD)
# idempotent: a previous run's outline, slots and board-level silk are collected now and removed at the very end
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea()]
fps = {f.GetReference(): f for f in board.GetFootprints()}
missing = [r for r in fps if r not in P]
assert not missing, f"unplaced: {missing}"
for ref, (x, y, rot) in P.items():
    f = fps[ref]
    f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    f.SetOrientationDegrees(rot)
    f.Reference().SetVisible(False)             # no designators on the silk


def seg(x1, y1, x2, y2, layer=pcbnew.F_SilkS, w=0.15):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_SEGMENT); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); d.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    board.Add(d)


def rect(x1, y1, x2, y2, layer, w):
    for (a, b), (c, d) in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        seg(a, b, c, d, layer, w)


rect(0, 0, W, H, pcbnew.Edge_Cuts, 0.1)                   # outline
for x1, x2 in SLOTS:                                      # strap slots, each with a copper keep-out 0.5 mm around it
    rect(x1, 39, x2, 61, pcbnew.Edge_Cuts, 0.1)
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    o = z.Outline(); o.NewOutline()
    for px, py in ((x1 - 0.5, 38.5), (x2 + 0.5, 38.5), (x2 + 0.5, 61.5), (x1 - 0.5, 61.5)):
        o.Append(mm(px), mm(py))
    board.Add(z)
for cx, cy in PI:                                         # no vias under the Pi standoffs (r 3.0; mask-covered tracks are fine)
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    o = z.Outline(); o.NewOutline()
    for k in range(24):
        a = 2 * math.pi * k / 24
        o.Append(mm(cx + 3.0 * math.cos(a)), mm(cy + 3.0 * math.sin(a)))
    board.Add(z)


def arc(start, mid, end, layer, w, dx=0.0, dy=0.0):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_ARC); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetArcGeometry(*(pcbnew.VECTOR2I(v.x + mm(dx), v.y + mm(dy)) for v in (start, mid, end)))
    board.Add(d)


def silk(txt, x, y, size=1.2, rot=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15 * size))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


silk("LaserHAT BatteryPack rev C", 14, 30, 1.0)                 # clear of the HAT (x >= 26)
silk("PACK A  -V", 15.5, 85.8, 1.0); silk("PACK B  +V", 84.5, 85.8, 1.0)
silk("OUT +V 0V -V", 48.5, 98.9, 0.8)
silk("USB-C 20V", 89.5, 2.5, 0.8)
silk("CHRG", 62, 2.5, 0.8); silk("DONE", 74.5, 2.5, 0.8)
for txt, y in (("80%", 10), ("50%", 14), ("20%", 18)):
    silk(txt, 6.3, y, 0.8); silk(txt, 95.1, y + 56, 0.8)
silk("ON", 6.3, 22, 0.8); silk("ON", 95.1, 78, 0.8)
silk("A", 6.3, 25.5, 0.8); silk("B", 95.1, 81.5, 0.8)
silk("RPi  58 x 49  M2.5", 40, 7.5, 0.8)
# User.Comments: the LaserHAT's outline (its Edge.Cuts, read live from ../LaserDriver.kicad_pcb) with its hole MH1 on H5, i.e.
# where the HAT sits when the Pi is on H5-H8; User.Drawings: the Raspberry Pi itself (85 x 56, r 3, holes 3.5 in from the
# left/top/bottom edges, ports end 23.5 beyond the right holes).  Both are drawings only (not in the gerbers).
HAT = os.path.join(ROOT, "..", "LaserDriver.kicad_pcb")
hat = pcbnew.LoadBoard(HAT)
mh1 = hat.FindFootprintByReference("MH1").GetPosition()
dx, dy = PI[0][0] - mh1.x / 1e6, PI[0][1] - mh1.y / 1e6
n_hat = 0
for d in hat.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts or d.GetClass() != "PCB_SHAPE":
        continue
    if d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        seg(d.GetStart().x / 1e6 + dx, d.GetStart().y / 1e6 + dy, d.GetEnd().x / 1e6 + dx, d.GetEnd().y / 1e6 + dy, pcbnew.Cmts_User, 0.15)
    elif d.GetShape() == pcbnew.SHAPE_T_ARC:
        arc(d.GetStart(), d.GetArcMid(), d.GetEnd(), pcbnew.Cmts_User, 0.15, dx, dy)
    else:
        raise SystemExit(f"HAT outline: unhandled shape {d.GetShape()}")
    n_hat += 1
hat_bb = hat.GetBoardEdgesBoundingBox()
silk("LaserHAT outline (MH1-MH4 on H5-H8)", (hat_bb.GetLeft() + hat_bb.GetRight()) / 2e6 + dx, hat_bb.GetBottom() / 1e6 + dy - 2, 1.0,
     layer=pcbnew.Cmts_User)
print("HAT outline:", n_hat, "edges, shifted by", round(dx, 3), round(dy, 3))
px, py, r = PI[0][0] - 3.5, PI[0][1] - 3.5, 3.0                                    # Pi top-left corner
for (x1, y1, x2, y2) in ((px + r, py, px + 85 - r, py), (px + 85, py + r, px + 85, py + 56 - r),
                         (px + 85 - r, py + 56, px + r, py + 56), (px, py + 56 - r, px, py + r)):
    seg(x1, y1, x2, y2, pcbnew.Dwgs_User, 0.15)
for cx, cy, a0 in ((px + r, py + r, 180), (px + 85 - r, py + r, 270), (px + 85 - r, py + 56 - r, 0), (px + r, py + 56 - r, 90)):
    pts = [pcbnew.VECTOR2I(mm(cx + r * math.cos(math.radians(a))), mm(cy + r * math.sin(math.radians(a)))) for a in (a0, a0 + 45, a0 + 90)]
    arc(pts[0], pts[1], pts[2], pcbnew.Dwgs_User, 0.15)
silk("Raspberry Pi outline (85 x 56)", px + 42.5, py + 56 + 2, 1.0, layer=pcbnew.Dwgs_User)
# bottom: the pack envelopes and names (read from below)
for (x1, x2), name in zip(PACKS, ("PACK A  (-V side, plugs to J7 / J5)", "PACK B  (+V side, plugs to J8 / J6)")):
    for (a, b), (c, d) in (((x1, 80), (x1, 10)), ((x1, 10), (x2, 10)), ((x2, 10), (x2, 80))):   # open toward the leads
        seg(a, b, c, d, pcbnew.B_SilkS, 0.15)
    silk(name, (x1 + x2) / 2, 48, 1.2, 90, pcbnew.B_SilkS)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
