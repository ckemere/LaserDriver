#!/usr/bin/env python3
"""Placement of BatteryPack.kicad_pcb (rev D, 100 x 100 mm, 2026-10-28), mirror-symmetric about x = 50: pack A (-V side)
left, pack B (+V side) right.  The two hobby 4S packs sit under the board (long axis along y, two 20 mm straps through the
slots), their XT60 discharge plugs and balance leads come round the front edge (y = 100) to J7 / J5 (left) and J8 / J6
(right).  The Raspberry Pi (holes H5-H8, 58 x 49) lies along the top edge (x 7.5-92.5, y 0-56) with its USB-C / HDMI face,
which is also the face the e-stim module's electrode wires leave over, flush with the top edge, SD-card end to the right;
the HAT covers x 27.5-92.5, y 0-56 and the e-stim module hangs 9 mm past the top edge at the top-right corner (x 65-91.5,
y -9..24), its battery pads at x 84.5-91.5 right above J3 (84, 4).  Under the Pi: the two gauges (A left, B right), the
balancers (A left, B right), the output chains (top right, by J3) and the charger island in the centre column (x 37-64,
y 5-38).  Below the Pi, the user-facing strip (y 56-100): the two
gauge LED columns paired in the centre (A at x 46, B at x 54: 80 / 50 / 20 % / ON / CHG / DONE), the ON / OFF toggle (lever
along x, ON to the right), the CH224A and the USB-C in the middle of the front edge between the XT60s.
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


# ---- mounting holes (H2 a little in from the corner: J3 and the module's pads are there)
at("H1", 4, 4); at("H2", 96.5, 3.5); at("H3", 4, 96); at("H4", 96, 96)
# ---- Raspberry Pi holes (58 x 49, M2.5).  PI_ROT 180 = the Pi's long axis along x, its "bottom" face (USB-C power,
# micro-HDMI, opposite the OLED bonnet) flush with the board's top edge, SD-card end at the right (x 92.5), USB / Ethernet
# end at x 7.5, header along y = 56.  PI[0] is where the Pi's header-side / SD-end hole (the HAT's MH1) goes.  The HAT
# (65 x 56.5, x 27.5-92.5) has its south edge on the top edge too, so the e-stim module (HAT x 101-127.5, y 76-109 -> here
# x 65-91.5, y 24..-9) hangs 9 mm past the top edge with its electrode header at (80, -7) pointing up: stim wires and the
# Pi's power / HDMI cables all leave over the top edge.  Its battery pads (HAT x 101-108, y 97-103 -> x 84.5-91.5, y -3..3)
# are right above J3.  The HAT's thumbwheel (its west edge, 6 mm proud) is at x 88.7-98.5, y 6.5-19, 25 mm up: J3's cable
# rises straight past it.  All four Pi standoffs fall inside the pack envelopes (x 31 / 89): fix them from the top
# (threaded standoff + screw) or use low heads below.  Standoffs >= 11 mm (XT60 sockets, electrolytic under the Pi).
PI_ROT = 180
PI = ((89.0, 52.5), (31.0, 52.5), (89.0, 3.5), (31.0, 3.5))


def pi_xy(u, v):
    """Pi-local (u along the long axis from the SD end, v from the header edge) -> board coordinates"""
    du, dv = u - 3.5, v - 3.5
    if PI_ROT == 90:
        du, dv = dv, -du
    elif PI_ROT == 180:
        du, dv = -du, -dv
    elif PI_ROT == 270:
        du, dv = -dv, du
    return PI[0][0] + du, PI[0][1] + dv
for ref, (x, y) in zip(("H5", "H6", "H7", "H8"), PI):
    at(ref, x, y)
# ---- front edge: XH balance sockets outboard (opening toward the edge), XT60 sockets inboard (face flush with the edge,
# pad 1 = "-" at the right for both, so both plugs have + on the left), USB-C in the middle; the CH224A and the toggle
# behind the USB-C; J3 (pins along x, cable straight up to the module's pads 36 mm above) in the top-right corner
at("J5", 10.5, 91.5); at("J6", 79.5, 91.5)
at("J7", 35.5, 83.1, 180); at("J8", 71.7, 83.1, 180)
at("J1", 50, 95.8); at("C3", 42.5, 92)                   # opening toward +y, face flush with the edge; C3 beside it
at("SW1", 50, 83.5)                                      # lever along x, parallel to the Pi; ON to the right
at("J3", 76.5, 4)                                        # pins x 76.5-82.5, the module's pads at x 84.5-91.5 above; H7 (89, 3.5) has the corner
# ---- gauge LED columns, paired in the centre: A at x 46, B at x 54; rows 80 / 50 / 20 / ON / CHG / DONE, resistors outboard
ROWS = (62.5, 65, 67.5, 70, 72.5, 75)                   # below the middle slot (y 39-61)
for (a, b), y in zip((("D4", "D14"), ("D3", "D13"), ("D2", "D12"), ("D1", "D11"), ("D9", "D17"), ("D10", "D18")), ROWS):
    at(a, 46, y); at(b, 54, y)
for (a, b), y in zip((("R15", "R57"), ("R14", "R56"), ("R13", "R55"), ("R12", "R54"), ("R66", "R68"), ("R67", "R69")), ROWS):
    at(a, 41.5, y); at(b, 58.5, y)


def balancer(u, q, rv, c, rb, x0, y0):
    """HY2213 block (U, Q, bleed R 1206, VDD R, C): 14 x 8 mm, parts at y0 and y0 + 4"""
    at(u, x0 + 2, y0); at(q, x0 + 7, y0); at(rb, x0 + 11, y0, 90)
    at(rv, x0 + 2, y0 + 4); at(c, x0 + 7, y0 + 4)


# ---- balancers, all under the Pi, 2 x 2 per pack: pack A (U6..U9, Q7..Q10, R35..R38 bleed, R31..R34, C12..C15) at
# x 9-38, pack B (U10..U13, Q15..Q18, R62..R65, R58..R61, C16..C19) at x 62-91; rows y 28-52, the outer column one row up
for n in range(4):
    y0 = 38 + 10 * (n // 2) - 10 * (n % 2)
    balancer(f"U{6 + n}", f"Q{7 + n}", f"R{31 + n}", f"C{12 + n}", f"R{35 + n}", 9 + 16 * (n % 2), y0)
    balancer(f"U{10 + n}", f"Q{15 + n}", f"R{58 + n}", f"C{16 + n}", f"R{62 + n}", 62 + 16 * (n % 2), y0)
# ---- pack A gauge, top left under the Pi: comparators, reference and ladder (LEDs in the centre column), its rail switch
at("C1", 16, 7.5); at("U1", 16, 12); at("U2", 16, 20); at("C2", 16, 25); at("Q14", 21, 28)
at("U3", 24, 8); at("R3", 24, 11)
for i, ref in enumerate(("R4", "R5", "R6", "R7", "R8")):
    at(ref, 24, 14 + 2.5 * i)
at("R9", 30, 12.5); at("R10", 30, 15); at("R11", 30, 17.5)
at("Q20", 8, 12); at("R77", 8, 15.5); at("R78", 8, 18); at("Q21", 8, 22); at("R79", 8, 25.5); at("R80", 8, 28)
# ---- pack B gauge, mirrored top right (a little lower than A's: J3 is above it), and its rail switch
at("C20", 84, 8.7); at("U14", 84, 13); at("U15", 84, 21); at("C21", 84, 24.9)
at("U16", 76, 9.5); at("R45", 76, 12.5)
for i, ref in enumerate(("R46", "R47", "R48", "R49", "R50")):
    at(ref, 76, 15.5 + 2.5 * i)
at("R51", 72, 14); at("R52", 72, 16); at("R53", 72, 18)
at("Q23", 92, 12); at("R83", 92, 15.5); at("R84", 92, 18); at("Q24", 92, 22)
# ---- output chains: chain B (+V) at x 61-70 below J3, chain A (-V) along the top edge between the Pi hole and the MCU
at("Q1", 63.5, 8.5); at("R1", 68, 6.5); at("R2", 68, 8.3); at("F1", 68, 12.5, 90)
at("Q22", 63.9, 13.5); at("R81", 63.9, 16.8); at("R82", 63.9, 18.6)
at("F2", 39.5, 3); at("Q11", 44.5, 3); at("R39", 48.5, 2.5); at("R40", 51.6, 2.5)
# ---- charger island (CGND), centre column under the Pi: MCU row on top (test points on the edge, the BOOT button and
# the LDO well clear of the MCU's pin rows), decoupling row below it, the CN3704 with only its compensation parts beside
# it (its pin rows need room to fan out), the buck power parts above the middle slot, the opto on the slot's left flank
# and the sense dividers, pull-ups and VBUS switch on its right flank
at("U19", 41, 9); at("SW2", 50, 8.5); at("U18", 56.5, 10.2)
for i, ref in enumerate(("TP1", "TP2", "TP3", "TP4")):
    at(ref, 54.5 + 2.8 * i, 4.3)
for ref, x in (("C4", 39.5), ("C24", 42.7), ("C25", 45.9), ("R70", 49.1), ("C26", 52.3), ("C23", 55.5), ("C22", 58.7)):
    at(ref, x, 13.5)
at("U5", 41, 18)
at("C9", 48.3, 16.2); at("C10", 48.3, 18); at("C11", 48.3, 19.8); at("R27", 48.3, 21.6)
at("C6", 39, 21.8); at("RT1", 42.5, 21.8)
at("C5", 42.1, 27); at("Q6", 49, 24.2); at("D7", 55, 24.2); at("D8", 62.2, 24.2); at("L1", 51.5, 30.2)
at("R25", 59.3, 28.5, 90); at("R26", 59.3, 33.3, 90); at("C7", 62.8, 28.2, 90); at("C8", 62.8, 31.7, 90)
at("U17", 41, 41, 90); at("R76", 41, 48.5)
for ref, (x, y) in {"R71": (52.5, 37.5), "R72": (52.5, 39.3), "R73": (55.7, 37.5), "R74": (55.7, 39.3), "R28": (58.9, 37.5),
                    "R29": (58.9, 39.3), "R42": (52.5, 41.1), "R43": (55.7, 41.1), "R44": (58.9, 41.1)}.items():
    at(ref, x, y)
at("Q12", 53.5, 44); at("Q13", 58.5, 44)
# ---- front strip, outer thirds (visible, either side of the LED pair): the relay with its driver on the right by pack B's
# sockets (its contacts take 0V / +BATB from there), the PD sink on the left by pack A's (its CC lines run to J1 as fine tracks)
at("K1", 84.5, 70, 90); at("Q19", 78.5, 57); at("D19", 83, 56.8, 90)
at("U4", 15.5, 70, 90); at("R24", 15.5, 76); 
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


silk("LaserHAT BatteryPack rev D", 50, 5, 1.0, 0, pcbnew.B_SilkS)   # the top side is under the Pi / HAT or busy
silk("OUT +V 0V -V CAB", 80, 1.0, 0.8)
silk("PD 20V", 42.5, 96.5, 0.8, 90); silk("DFU", 57.5, 95.5, 0.8, 90)
silk("BOOT", 50, 4.6, 0.8)
silk("SWDIO SWCLK GND 3V3", 60.5, 1.5, 0.8)
for txt, y in zip(("80%", "50%", "20%", "ON", "CHG", "DONE"), ROWS):
    silk(txt, 50, y, 0.8)
silk("A", 41.5, 60.2, 0.8); silk("B", 58.5, 60.2, 0.8)
# User.Comments: the LaserHAT's outline (its Edge.Cuts, read live from ../LaserDriver.kicad_pcb) with its hole MH1 on H5 and
# the Pi's rotation, i.e. where the HAT sits when the Pi is on H5-H8; User.Drawings: the Raspberry Pi itself (85 x 56, r 3,
# holes 3.5 in from the SD-card end and the long edges, ports end 23.5 beyond the far holes).  Drawings only (not in the gerbers).
def xf(pt):
    """VECTOR2I in Pi-local mm (u, v) -> board VECTOR2I"""
    x, y = pi_xy(pt.x / 1e6, pt.y / 1e6)
    return pcbnew.VECTOR2I(mm(x), mm(y))


def shape(kind, pts, layer):
    """kind 'seg' (2 pts) or 'arc' (start, mid, end), Pi-local VECTOR2Is"""
    d = pcbnew.PCB_SHAPE(board)
    d.SetLayer(layer); d.SetWidth(mm(0.15))
    if kind == "seg":
        d.SetShape(pcbnew.SHAPE_T_SEGMENT); d.SetStart(xf(pts[0])); d.SetEnd(xf(pts[1]))
    else:
        d.SetShape(pcbnew.SHAPE_T_ARC); d.SetArcGeometry(*(xf(q) for q in pts))
    board.Add(d)


HAT = os.path.join(ROOT, "..", "LaserDriver.kicad_pcb")
hat = pcbnew.LoadBoard(HAT)
mh1 = hat.FindFootprintByReference("MH1").GetPosition()
hat_off = pcbnew.VECTOR2I(mm(3.5) - mh1.x, mm(3.5) - mh1.y)       # HAT board coords -> Pi-local (MH1 = Pi hole (3.5, 3.5))
n_hat = 0
for d in hat.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts or d.GetClass() != "PCB_SHAPE":
        continue
    if d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        shape("seg", (d.GetStart() + hat_off, d.GetEnd() + hat_off), pcbnew.Cmts_User)
    elif d.GetShape() == pcbnew.SHAPE_T_ARC:
        shape("arc", (d.GetStart() + hat_off, d.GetArcMid() + hat_off, d.GetEnd() + hat_off), pcbnew.Cmts_User)
    else:
        raise SystemExit(f"HAT outline: unhandled shape {d.GetShape()}")
    n_hat += 1
hat_bb = hat.GetBoardEdgesBoundingBox()
hx, hy = pi_xy((hat_bb.GetLeft() + hat_bb.GetRight()) / 2e6 + hat_off.x / 1e6, (hat_bb.GetTop() + hat_bb.GetBottom()) / 2e6 + hat_off.y / 1e6)
silk("LaserHAT outline (MH1-MH4 on H5-H8)", hx, hy + 8, 1.0, layer=pcbnew.Cmts_User)
print("HAT outline:", n_hat, "edges; MH1 on", PI[0], "rotated", PI_ROT)
r = 3.0
V = lambda u, v: pcbnew.VECTOR2I(mm(u), mm(v))
for (u1, v1, u2, v2) in ((r, 0, 85 - r, 0), (85, r, 85, 56 - r), (85 - r, 56, r, 56), (0, 56 - r, 0, r)):
    shape("seg", (V(u1, v1), V(u2, v2)), pcbnew.Dwgs_User)
for cu, cv, a0 in ((r, r, 180), (85 - r, r, 270), (85 - r, 56 - r, 0), (r, 56 - r, 90)):
    shape("arc", tuple(V(cu + r * math.cos(math.radians(a)), cv + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)),
          pcbnew.Dwgs_User)
px, py = pi_xy(42.5, 28)
silk("Raspberry Pi outline (85 x 56)", px, py + 12, 1.0, layer=pcbnew.Dwgs_User)
# bottom: the pack names at the sockets (the top side there is under the Pi), the pack envelopes and names (read from below)
silk("PACK A  -V", 35.5, 93.5, 1.0, 0, pcbnew.B_SilkS); silk("PACK B  +V", 64.5, 93.5, 1.0, 0, pcbnew.B_SilkS)
for (x1, x2), name in zip(PACKS, ("PACK A  (-V side, plugs to J7 / J5)", "PACK B  (+V side, plugs to J8 / J6)")):
    seg(x1, 10, x2, 10, pcbnew.B_SilkS, 0.15)                                             # open toward the leads
    for x in (x1, x2):                                                                   # sides, skipping the Pi standoffs
        ys = [10, 80 if x < 85 else 56]                                                  # pack B's right side stops at the relay
        for cx, cy in PI:
            if abs(cx - x) < 3.5 and 10 < cy < 80:
                ys += [cy - 3.5, cy + 3.5]
        ys.sort()
        for ya, yb in zip(ys[0::2], ys[1::2]):
            seg(x, ya, x, yb, pcbnew.B_SilkS, 0.15)
    silk(name, (x1 + x2) / 2 + (12 if x1 > 50 else 0), 28 if x1 > 50 else 48, 1.2, 90, pcbnew.B_SilkS)   # pack B label at x 82, above the relay
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
