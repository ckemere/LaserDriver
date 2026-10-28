#!/usr/bin/env python3
"""Placement of BatteryPack.kicad_pcb (rev C, 100 x 100 mm, 2026-10-27): the two hobby 4S packs sit under the board (long
axis along y, 42 mm pitch, two 20 mm straps through the slots), their XT60 discharge plugs and balance leads come round the front edge
(y = 100) to the XT60 sockets J7 / J8 and the right-angle XH sockets J5 / J6 (pack A left, pack B right).  Top side: pack A's gauge top left, its balancers
mid left, its -V chain bottom left; the charger top right with the USB-C on the right edge; pack B's balancers mid right,
its gauge and +V chain bottom right; the toggle and the output header J3 in the right column.  H5-H8 are a
Raspberry Pi's holes (58 x 49): the Pi lies along the left edge (x 0-56, y 15-100) with its USB-C / HDMI face, which
is also the face the e-stim module's electrode wires leave over, flush with the board's left edge, SD-card end up, USB /
Ethernet over the front edge; the module hangs 9 mm past that edge at the top-left corner and its battery pads are at
(-3..3, 16-23), so J3 sits right below them in the top-left corner (4, 4), H1 moved to (12, 4).  The HAT's outline is drawn on User.Comments
and the Pi's on User.Drawings.  (The layout text above predates the Pi: gauge B's comparators are now top centre, pack B's
balancers below pack A's, both LED columns on the right edge, the toggle alone in the right column.)
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
at("H1", 12, 4); at("H2", 96, 4); at("H3", 4, 96); at("H4", 96, 96)      # H1 8 mm in from the corner: J3 has the corner
# ---- Raspberry Pi holes (58 x 49, M2.5): the Pi lies along the left edge (x 0-56, y 15-100) on standoffs with its
# header along x = 56 and its "bottom" face (USB-C power, micro-HDMI, opposite the OLED bonnet) flush with the board's left
# edge, SD-card end at y 15, USB / Ethernet end over the front edge.  The HAT (x 0..57, y 15-80) then has its south-west
# corner at the board's top-left corner: the e-stim module (HAT x 101-127.5, y 76-109 -> here x -9..24, y 16-43) hangs 9 mm
# past the left edge, its electrode header (-7, 27.5) points west, so the stimulation wires and the Pi's power / HDMI
# cables all leave over the left edge; its battery pads (PS1 position, HAT x 101-108 / y 97-103 -> here x -3..3, y 16-23)
# are right above J3 in the top-left corner.  The HAT's thumbwheel (west edge, y 81-93.5, 6 mm proud) is under the
# module's SW corner and sticks past the board's top edge at x 6.5-19, y 9-15: J3 and its cable stay west of x 6.5.
# Everything else user-facing is in the right column (x > 56: charger + USB-C, CHRG / DONE, toggle, both LED columns on
# the right edge) or the front strip (y > 85: the four pack sockets); under the Pi only gauges, balancers and the -V chain.
# PI_ROT 270 = the Pi's long axis along y, SD end up, header east; PI[0] is where the Pi's header-side / SD-end hole (the
# HAT's MH1) goes.  (PI_ROT 90 = header west / ports up, 0 = header up / SD end west.)
PI_ROT = 270
PI = ((52.5, 18.5), (52.5, 76.5), (3.5, 18.5), (3.5, 76.5))


def pi_xy(u, v):
    """Pi-local (u along the long axis from the SD end, v from the header edge) -> board coordinates"""
    du, dv = u - 3.5, v - 3.5
    if PI_ROT == 90:
        du, dv = dv, -du
    elif PI_ROT == 270:
        du, dv = -dv, du
    return PI[0][0] + du, PI[0][1] + dv
for ref, (x, y) in zip(("H5", "H6", "H7", "H8"), PI):
    at(ref, x, y)
# ---- pack sockets along the front edge (under the Pi's USB / Ethernet end for pack A): J5 (XH balance, opening toward
# the edge), XT60 J7 / J8 (face flush with the edge, "-" pin outboard) either side of x 52.5, J6 outboard; output header J3
# (pins along y, cable straight up to the module's pads 36 mm above) in the top-left corner; toggle (lever along x) in the
# right column beside the HAT's header edge
at("J5", 10.5, 91.5); at("J6", 76.5, 91.5)
at("J7", 35.5, 83.1, 180); at("J8", 68, 83.1, 180)
at("J3", 4, 4, -90)                                       # pin 1 at (4, 4), pins down to y 10; cable rises west of the thumbwheel (x > 6.5)
at("SW1", 74, 52)
at("F3", 46, 66, 90); at("R30", 46, 71)                  # link fuse and pull-down under the Pi, left of H7


def balancer(u, q, rv, c, rb, x0, y0):
    """HY2213 block (U, Q, bleed R 1206, VDD R, C): 14 x 8 mm, parts at y0 and y0 + 4"""
    at(u, x0 + 2, y0); at(q, x0 + 7, y0); at(rb, x0 + 11, y0, 90)
    at(rv, x0 + 2, y0 + 4); at(c, x0 + 7, y0 + 4)


# ---- balancers, all under the Pi: pack A (U6..U9, Q7..Q10, R35..R38 bleed, R31..R34, C12..C15) rows y 28-52 (right
# column one row up), pack B (U10..U13, Q15..Q18, R62..R65, R58..R61, C16..C19) rows y 58 / 68 below them, 2 x 2 each
for n in range(4):
    x0, y0 = 9 + 16 * (n % 2), 38 + 10 * (n // 2)
    balancer(f"U{6 + n}", f"Q{7 + n}", f"R{31 + n}", f"C{12 + n}", f"R{35 + n}", x0, y0 - 10 * (n % 2))
    balancer(f"U{10 + n}", f"Q{15 + n}", f"R{58 + n}", f"C{16 + n}", f"R{62 + n}", x0, y0 + 20)
# ---- pack A gauge, top left under the Pi: comparators, reference and ladder; its LEDs on the right edge at y 64-76
for ref, y in (("D4", 64), ("D3", 68), ("D2", 72), ("D1", 76)):
    at(ref, 97.5, y, 90)
for ref, y in (("R15", 64), ("R14", 68), ("R13", 72), ("R12", 76)):
    at(ref, 92.5, y)
at("C1", 16, 7.5); at("U1", 16, 12); at("U2", 16, 20); at("C2", 16, 25); at("Q14", 21, 28)
at("U3", 24, 8); at("R3", 24, 11)
for i, ref in enumerate(("R4", "R5", "R6", "R7", "R8")):
    at(ref, 24, 14 + 2.5 * i)
at("R9", 30, 12.5); at("R10", 30, 15); at("R11", 30, 17.5)
# ---- pack A -V chain, under the Pi above J7 (x 34-48, y 62-80)
at("F2", 46, 77, 90); at("Q11", 41, 78.5); at("R39", 36, 76); at("R40", 36, 78.5)
at("D15", 41, 65, 90); at("D16", 41, 72.5, 90)
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
# ---- pack B gauge: comparators, reference and ladder top centre under the Pi (x 37-56, y 5-23, right of gauge A's);
# its LEDs on the right edge at y 30-42 between D7 / L1 and the slot
for ref, y in (("D14", 30), ("D13", 34), ("D12", 38), ("D11", 42)):
    at(ref, 97.5, y, 90)
at("R57", 92.5, 34); at("R56", 92.5, 38); at("R55", 96, 25)        # R55 above the column: x 92.5 / y 42 is in the slot keep-out
at("U16", 39, 7); at("R45", 39, 10)
for i, ref in enumerate(("R46", "R47", "R48", "R49", "R50")):
    at(ref, 39, 12 + 2.5 * i)
at("R51", 44, 7); at("R52", 44, 9.5); at("R53", 44, 12)
at("C20", 46.5, 9, 90); at("U14", 52, 9); at("C21", 46.5, 27, 90); at("U15", 52, 27)   # U15 below the Pi standoff H5 (52.5, 18.5)
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


silk("LaserHAT BatteryPack rev C", 50, 5, 1.0, 0, pcbnew.B_SilkS)   # the top side is under the Pi / HAT or busy
silk("OUT +V 0V -V", 8.2, 7, 0.8, 90)
silk("USB-C 20V", 89.5, 2.5, 0.8)
silk("CHRG", 62, 2.5, 0.8); silk("DONE", 74.5, 2.5, 0.8)
for txt, y in (("80%", 64), ("50%", 68), ("20%", 72)):
    silk(txt, 95.1, y, 0.8); silk(txt, 95.1, y - 34, 0.8)
silk("ON", 95.1, 76, 0.8); silk("ON", 95.1, 42, 0.8)
silk("A", 95.1, 79.5, 0.8); silk("B", 95.1, 27, 0.8)
silk("RPi  58 x 49  M2.5", 28, 54.3, 0.8)
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
silk("LaserHAT outline (MH1-MH4 on H5-H8)", hx, hy - 8, 1.0, layer=pcbnew.Cmts_User)
print("HAT outline:", n_hat, "edges; MH1 on", PI[0], "rotated", PI_ROT)
r = 3.0
V = lambda u, v: pcbnew.VECTOR2I(mm(u), mm(v))
for (u1, v1, u2, v2) in ((r, 0, 85 - r, 0), (85, r, 85, 56 - r), (85 - r, 56, r, 56), (0, 56 - r, 0, r)):
    shape("seg", (V(u1, v1), V(u2, v2)), pcbnew.Dwgs_User)
for cu, cv, a0 in ((r, r, 180), (85 - r, r, 270), (85 - r, 56 - r, 0), (r, 56 - r, 90)):
    shape("arc", tuple(V(cu + r * math.cos(math.radians(a)), cv + r * math.sin(math.radians(a))) for a in (a0, a0 + 45, a0 + 90)),
          pcbnew.Dwgs_User)
px, py = pi_xy(42.5, 28)
silk("Raspberry Pi outline (85 x 56)", px, py + 8, 1.0, layer=pcbnew.Dwgs_User)
# bottom: the pack names at the sockets (the top side there is under the Pi), the pack envelopes and names (read from below)
silk("PACK A  -V", 35.5, 93.5, 1.0, 0, pcbnew.B_SilkS); silk("PACK B  +V", 68, 93.5, 1.0, 0, pcbnew.B_SilkS)
for (x1, x2), name in zip(PACKS, ("PACK A  (-V side, plugs to J7 / J5)", "PACK B  (+V side, plugs to J8 / J6)")):
    for (a, b), (c, d) in (((x1, 80), (x1, 10)), ((x1, 10), (x2, 10)), ((x2, 10), (x2, 80))):   # open toward the leads
        seg(a, b, c, d, pcbnew.B_SilkS, 0.15)
    silk(name, (x1 + x2) / 2 + (12 if x1 > 50 else 0), 48, 1.2, 90, pcbnew.B_SilkS)   # pack B label at x 82: no vias under it
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
