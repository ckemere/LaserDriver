#!/usr/bin/env python3
"""Initial placement of BatteryPack.kicad_pcb (rev B, 100 x 96 mm): board outline, mounting holes, cells in four rows,
balancers in a band under the cells, electronics strip on the right.  Run once after board_init.py; afterwards the board
is edited in place (never rebuilt).      $KICAD_PY tools/place.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "BatteryPack.kicad_pcb")
W, H = 100.0, 96.0
ROWS = (17.0, 37.0, 57.0, 77.0)            # cell axes (y), 20 mm pitch
XL, XR = 11.0, 59.0                        # clip origins (pin-pair centres), 48.0 mm apart

mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot)


def at(ref, x, y, rot=0):
    P[ref] = (x, y, rot)


# ---- cells: all four the same way round, - (odd clip) on the left at x=11, + (even clip) on the right at x=59,
#      so every cell goes in with its button end to the right.  Series links C1..C3 run diagonally under the cells
#      (row n right clip -> row n+1 left clip); GND = BC1 row 1 left, +BAT = BC8 row 4 right.
for row in range(4):
    at(f"BC{2 * row + 1}", XL, ROWS[row], 0)
    at(f"BC{2 * row + 2}", XR, ROWS[row], 180)
# ---- balancers in the band under the cells
for n in range(1, 5):
    x0 = 14.0 + 12.5 * (n - 1)
    at(f"U{5 + n}", x0 + 2, 89.5); at(f"Q{6 + n}", x0 + 6, 89.5); at(f"R{34 + n}", x0 + 9.5, 89.5, 90)
    at(f"R{30 + n}", x0 + 2, 93.5); at(f"C{11 + n}", x0 + 6, 93.5)
at("J4", 67, 91.5); at("J3", 79, 91.5)
at("H1", 8, 4); at("H2", 96, 4); at("H3", 8, 92); at("H4", 96, 92)
# ---- switch, fuse, cutoff
at("SW1", 84, 12)
at("F1", 72.5, 7, 90); at("Q1", 72.5, 12); at("R1", 72.5, 15.5); at("R2", 72.5, 17.5)
at("D5", 75, 20.5); at("D6", 82, 20.5)
# ---- gauge
for ref, y in (("D4", 24.5), ("D3", 28), ("D2", 31.5), ("D1", 35)):
    at(ref, 97.5, y, 90)
for ref, y in (("R15", 24.5), ("R14", 28), ("R13", 31.5), ("R12", 35)):
    at(ref, 93.5, y)
at("U1", 85, 27); at("U2", 85, 35); at("C1", 80.5, 27, 90); at("C2", 80.5, 35, 90)
at("U3", 74, 24.5); at("R3", 74, 27.5)
for i, ref in enumerate(("R4", "R5", "R6", "R7", "R8")):
    at(ref, 74, 30 + 2.5 * i)
at("R9", 78, 40); at("R10", 78, 42.5); at("R11", 82, 42.5)
# ---- USB-C PD input
at("J1", 95.8, 52, 90)                     # front flush with the right edge (courtyard +y end = 4.2 mm from origin)
at("U4", 85, 52); at("C3", 85, 47.5); at("R24", 85, 56.5)
at("C5", 76, 50); at("C6", 76, 55.5); at("R30", 76, 59)
at("D9", 97.5, 42, 90); at("R28", 97.5, 38.5, 90)
at("D10", 97.5, 61, 90); at("R29", 97.5, 64.5, 90)
# ---- charger
at("U5", 84, 66); at("C4", 84, 61.5); at("Q6", 91.5, 62)
at("D7", 92, 68, 90); at("L1", 92, 76); at("D8", 84, 75)
at("R25", 90, 82); at("R26", 95, 82)
at("C7", 78, 74); at("C8", 78, 77)
at("C9", 81, 70.5); at("C10", 84, 70.5); at("C11", 87, 70.5); at("R27", 82, 72.5)
at("RT1", 70.5, 46, 90)
# ---- stack slave enable
for i, ref in enumerate(("Q2", "Q3", "Q4", "Q5")):
    at(ref, 71.5 + 4.0 * i, 85)
for i, ref in enumerate(("R16", "R17", "R18", "R19", "R20", "R21", "R22", "R23")):
    at(ref, 71 + 1.8 * i, 81.5, 90)

board = pcbnew.LoadBoard(BOARD)
# idempotent: a previous run's outline and board-level silk texts are collected now and removed at the very end
stale = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts or (d.GetLayer() == pcbnew.F_SilkS and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
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
    silk("-", 7, y - 9.9, 1.5); silk("+", 63, y - 9.9, 1.5)        # small marks outside each clip
    seg(14, y, 18, y)                                               # 4 mm "-" under the cell's negative end
    seg(52, y, 56, y); seg(54, y - 2, 54, y + 2)                    # 4 mm "+" under the positive (button) end
silk("LaserHAT BatteryPack rev B  4S 18650", 36, 3.2, 1.2)
silk("USB-C PD 20V", 84, 59, 1.0)
silk("OUT", 82, 87.4, 1.0); silk("LINK IN", 70, 87.4, 1.0)
silk("CHRG", 93.5, 42, 0.9); silk("DONE", 94.6, 64.5, 0.9)
silk("80%", 90.5, 24.5, 0.9); silk("50%", 90.5, 28, 0.9); silk("20%", 90.5, 31.5, 0.9); silk("ON", 90.5, 35, 0.9)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
