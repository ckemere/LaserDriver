#!/usr/bin/env python3
"""Placement of BatteryPack.kicad_pcb (rev B, 100 x 120 mm since 2026-10-27): board outline, mounting holes, cells in four
rows (all the same way round), each balancer beside its cell's clips, switch / fuse / cutoff next to the output headers
at the bottom, charger in the lower right with the USB-C on the right edge, gauge and LEDs above it.
Idempotent: re-running moves every footprint back to the table and redraws the outline and board-level silk; copper is
left alone (rip it up first with tools/autoroute.py if the placement changes).      $KICAD_PY tools/place.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "BatteryPack.kicad_pcb")
W, H = 100.0, 120.0
ROWS = (17.0, 37.0, 57.0, 77.0)            # cell axes (y), 20 mm pitch
XL, XR = 11.0, 59.0                        # clip origins (pin-pair centres), 48.0 mm apart

mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot)


def at(ref, x, y, rot=0):
    P[ref] = (x, y, rot)


# ---- cells: all four the same way round, + (even clip, cell n's positive end) on the LEFT at x=11, - (odd clip) on the
#      right at x=59.  Right clips then carry GND, C1, C2, C3 (rows 1-4) and left clips C1, C2, C3, +BAT, so the series
#      links run diagonally (row n left -> row n+1 right), GND meets the electronics column at row 1 and +BAT at the
#      bottom left, next to the switch.
for row in range(4):
    at(f"BC{2 * row + 2}", XL, ROWS[row], 0)
    at(f"BC{2 * row + 1}", XR, ROWS[row], 180)


def balancer(n, x0, y0):
    """HY2213 block for cell n (U5+n, Q6+n, R34+n bleed, R30+n, C11+n): 14 x 8 mm, parts at y0 and y0+4"""
    at(f"U{5 + n}", x0 + 2, y0); at(f"Q{6 + n}", x0 + 7, y0); at(f"R{34 + n}", x0 + 11, y0, 90)
    at(f"R{30 + n}", x0 + 2, y0 + 4); at(f"C{11 + n}", x0 + 7, y0 + 4)


# ---- balancers 1-3 in the right column between the rows they tap (cell n's ends are the right clips of rows n and n+1);
#      balancer 4 (C3 / +BAT) bottom left beside the +BAT clip
for n in (1, 2, 3):
    balancer(n, 70.0, 25.0 + 20.0 * (n - 1))
balancer(4, 4.0, 90.0)
# ---- mounting holes
at("H1", 8, 4); at("H2", 96, 4); at("H3", 8, 116); at("H4", 96, 116)
# ---- switch, fuse, cutoff, gauge rail diodes: bottom centre, beside the headers
at("SW1", 48, 97)
at("F1", 60, 93, 90); at("Q1", 60, 99); at("R1", 60, 102.5); at("R2", 60, 104.5)
at("D5", 65, 96, 90); at("D6", 65, 104, 90)
# ---- output / link headers and the stack slave enable, bottom left of centre
at("J4", 22, 112); at("J3", 36, 112)
for i, ref in enumerate(("Q2", "Q3", "Q4", "Q5")):
    at(ref, 21 + 5.0 * i, 100)
for i, ref in enumerate(("R16", "R17", "R18", "R19", "R20", "R21", "R22", "R23")):
    at(ref, 20 + 1.8 * i, 95.5, 90)
# ---- reference, ladder, comparators and LEDs: right column above the charger
at("U3", 86, 22); at("R3", 86, 25)
for i, ref in enumerate(("R4", "R5", "R6", "R7", "R8")):
    at(ref, 86, 28 + 2.5 * i)
at("R9", 86, 42); at("R10", 86, 44.5); at("R11", 90, 44.5)
at("C1", 81.5, 50, 90); at("U1", 86.5, 50)
at("C2", 81.5, 58, 90); at("U2", 86.5, 58)
for ref, y in (("R15", 48), ("R14", 51.5), ("R13", 55), ("R12", 58.5)):
    at(ref, 92.5, y)
for ref, y in (("D4", 48), ("D3", 51.5), ("D2", 55), ("D1", 58.5)):
    at(ref, 97.5, y, 90)
# ---- USB-C PD input, lower right edge
at("J1", 95.8, 86, 90)                     # front flush with the right edge (courtyard +y end = 4.2 mm from origin)
at("U4", 85, 86); at("C3", 85, 81.5); at("R24", 85, 90.5)
at("C5", 76, 84); at("C6", 76, 89.5); at("R30", 76, 93)
at("D9", 97.5, 76, 90); at("R28", 97.5, 72.5, 90)
at("D10", 97.5, 95, 90); at("R29", 97.5, 98.5, 90)
# ---- charger, bottom right (clear of the hole at (96, 116))
at("U5", 82, 99); at("C4", 82, 94.5); at("Q6", 91.5, 93.5)
at("D7", 92, 100, 90); at("L1", 86, 110); at("D8", 76, 108)
at("R25", 78, 116); at("R26", 84, 116)
at("C7", 89, 116); at("C8", 73, 116)
at("C9", 79, 103.5); at("C10", 82, 103.5); at("C11", 85, 103.5); at("R27", 80, 105.5)
at("RT1", 70.5, 80, 90)

board = pcbnew.LoadBoard(BOARD)
# idempotent: a previous run's outline and board-level silk are collected now and removed at the very end
stale = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts
         or (d.GetLayer() == pcbnew.F_SilkS and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
fps = {f.GetReference(): f for f in board.GetFootprints()}
missing = [r for r in fps if r not in P]
assert not missing, f"unplaced: {missing}"
for ref, (x, y, rot) in P.items():
    f = fps[ref]
    f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    f.SetOrientationDegrees(rot)
# outline
for (x1, y1), (x2, y2) in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
    s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    board.Add(s)


def silk(txt, x, y, size=1.2, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetLayer(pcbnew.F_SilkS)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15 * size))
    t.SetTextAngleDegrees(rot)
    board.Add(t)


def seg(x1, y1, x2, y2, w=0.6):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_SEGMENT); d.SetLayer(pcbnew.F_SilkS); d.SetWidth(mm(w))
    d.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); d.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    board.Add(d)


for y in ROWS:
    silk("+", 7, y - 9.9, 1.5); silk("-", 63, y - 9.9, 1.5)        # small marks outside each clip
    seg(14, y, 18, y); seg(16, y - 2, 16, y + 2)                    # 4 mm "+" under the cell's positive (button) end
    seg(52, y, 56, y)                                               # 4 mm "-" under the negative end
silk("LaserHAT BatteryPack rev B  4S 18650", 36, 3.2, 1.2)
silk("USB-C PD 20V", 86, 78.5, 1.0)
silk("OUT", 36, 107.3, 1.0); silk("LINK IN", 22, 107.3, 1.0)
silk("CHRG", 93.5, 76, 0.9); silk("DONE", 97.5, 101.5, 0.8)
silk("80%", 95.1, 48, 0.8); silk("50%", 95.1, 51.5, 0.8); silk("20%", 95.1, 55, 0.8); silk("ON", 95.1, 58.5, 0.8)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
