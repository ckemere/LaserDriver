#!/usr/bin/env python3
"""Placement of SimpleBatteryPack.kicad_pcb (100 x 100 mm, rounded corners): BatteryPack's holes and Pi drawings, without its
charger, relays, MCU, balancers and (2026-11-01) strap slots: the case holds the packs.  Pack A (-V side) left, pack B
(+V side) right, under the board (long axis along y); their XT60 leads come straight up through two notches in the front
edge to J7 (left) and J8 (right), set 10 mm back so the plugs stay inside the outline.  M3 holes for the case: the four
corners, two on the centre line between the packs (H9 / H10), one mid-edge each side (H11 / H12).  The Raspberry Pi
(holes H5-H8, 58 x 49) lies 5 mm in from the top edge (x 7.5-92.5, y 5-61), its USB-C / HDMI face toward the top edge,
SD-card end to the right; the HAT covers x 27.5-92.5, y 5-61 and the e-stim module hangs 4 mm past the top edge at the
top-right corner.  J3 (the output) is on the right edge with its body's top on the Pi's SE corner (y 61); its cable rises
past the Pi to the module.  Below the Pi, the user-facing strip (y 61-100): the two gauge LED columns paired in the centre
(A at x 46, B at x 54: 80 / 50 / 20 % / ON), the gauges either side of them, both output chains, the ON / OFF toggle
(lever along y) between the XT60s.
Idempotent: re-running moves every footprint back to the table and redraws the outline and board-level silk;
copper is left alone (rip it up first with tools/autoroute.py if the placement changes).      $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "SimpleBatteryPack.kicad_pcb")
W, H = 100.0, 100.0
PACKS = ((7.0, 45.0), (51.0, 89.0))                       # x extents of the two pack envelopes (y 10..90), bottom side
# XT60 notches (2026-11-01): each socket set 10 mm back from the front edge (its face on y = 90) over a notch 18 mm wide
# centred on the socket, so the plug sits inside the outline and its lead comes straight up from the pack below
SETBACK = 10.0
NOTCHES = ((22.4, 40.4), (59.6, 77.6))                     # x extents, y 90..100 (J7 centre 31.4, J8 centre 68.6)
R_CORNER, R_NOTCH = 3.0, 1.5                               # outer corners (as the Pi's), notch corners

mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot)


def at(ref, x, y, rot=0):
    P[ref] = (x, y, rot)


# ---- corner mounting holes (M3)
at("H1", 4, 4); at("H2", 96.5, 3.5); at("H3", 4, 96); at("H4", 96, 96)
# ---- Raspberry Pi holes (58 x 49, M2.5).  PI_ROT 180 = the Pi's long axis along x, its "bottom" face (USB-C power,
# micro-HDMI, opposite the OLED bonnet) toward the board's top edge, 5 mm in from it (2026-11-01; was flush), SD-card end at
# the right (x 92.5), USB / Ethernet end at x 7.5, header along y = 61.  PI[0] is where the Pi's header-side / SD-end hole
# (the HAT's MH1) goes.  The HAT (65 x 56.5, x 27.5-92.5) has its south edge 5 mm in too, so the e-stim module (HAT
# x 101-127.5, y 76-109 -> here x 65-91.5, y 29..-4) hangs 4 mm past the top edge, its electrode header pointing up.
# The HAT's thumbwheel (its west edge, 6 mm proud) is at x 88.7-98.5, y 11.5-24, 25 mm up.  All four Pi standoffs fall
# inside the pack envelopes (x 31 / 89): fix them from the top (threaded standoff + screw) or use low heads below.
# Standoffs >= 11 mm (XT60 sockets, electrolytic under the Pi).
PI_ROT = 180
PI = ((89.0, 57.5), (31.0, 57.5), (89.0, 8.5), (31.0, 8.5))     # 2026-11-01: 5 mm in from the top edge (was flush)


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
# ---- case holes (2026-11-01, the strap slots are gone: the case holds the packs): two on the centre line between the
# packs (x 48, the gap between the pack envelopes; both under the Pi, so fit the case before the Pi), one in the middle of
# each side edge
CASE = (("H9", 48, 25), ("H10", 48, 50), ("H11", 4, 50), ("H12", 96, 50))
for ref, x, y in CASE:
    at(ref, x, y)
# ---- the lab's owl (G1, 14 mm): the empty left half under the Pi
at("G1", 29.74, 35.49, 180)                               # where the user put it in pcbnew (2026-11-01)
# ---- front edge: XT60 sockets (face flush with the edge, pad 1 = "-" at the right for both, so both plugs have + on the
# left), the ON / OFF toggle between them; J3 (pins along x, cable straight up to the module's pads 36 mm above) in the
# top-right corner
at("J7", 35.0, 83.1 - SETBACK, 180); at("J8", 72.2, 83.1 - SETBACK, 180)   # faces on y = 90, over the notches
at("SW1", 50, 79.5, 90)                                  # lever along y (2026-11-01), ON toward the back (away from the front edge); lugs clear of the bus at y 87.8
at("J3", 93.21, 69.5, 90)                                # side entry, opening on the right edge, body y 61-72 (2026-11-01):
#                                                          pins x 93.21, y 69.5 (1 +OUT) .. 63.5 (4 CAB); the body's top on the Pi's SE corner (92.5, 61)
# ---- gauge LED columns, paired in the centre: A at x 46, B at x 54; rows 80 / 50 / 20 / ON, resistors outboard
ROWS = (62.5, 65, 67.5, 70)                             # just below the Pi (y 61)
for (a, b), y in zip((("D4", "D14"), ("D3", "D13"), ("D2", "D12"), ("D1", "D11")), ROWS):
    at(a, 46, y); at(b, 54, y)
for (a, b), y in zip((("R15", "R57"), ("R14", "R56"), ("R13", "R55"), ("R12", "R54")), ROWS):
    at(a, 41.5, y); at(b, 58.5, y)
# ---- the two gauges + output chains on a grid (2026-10-31, second layout): columns left to right towards the LEDs for
# pack A, mirrored about x = 50 for pack B.  Column order (A): rail switch | sense divider | CJ431 | ladder | comparators |
# decoupling + D1 driver.  The ladder and the dividers are literal stacks: 0603s turned 270 (pin 1 up) at a 3.2 mm pitch,
# so each node (VREF, TH80, TH50, TH20, THCUT, VS, the gate nodes) is the short gap between two resistors and the
# comparators tap the ladder from beside it.  The LM393s are turned so their inputs face the ladder and their outputs the
# LEDs (A 270: top row GND / IN+A / IN-A / OUTA, bottom row IN+B / IN-B / OUTB / VCC).  Rails: tracks (2 layers since
# 2026-11-01; B.Cu is the 0V plane, gauge B's ground).
PITCH = 3.2
STACK_Y = [58.5 + PITCH * k for k in range(6)]          # 58.5, 61.7, 64.9, 68.1, 71.3, 74.5


def stack(x, refs, y0=0, rot=270):
    for k, ref in enumerate(refs):
        if ref:
            at(ref, x, STACK_Y[y0 + k], rot)


def mx(x):
    return 100 - x                                       # mirror about the board's centre line


# pack A (left)
# rail switch, its own 3.2 mm resistor pairs with the SOT-23s between them: Q20, R77 (0V | Q20_G), R78 (Q20_G | Q21_D),
# Q21, R79 (EN_A | Q21_G), R80 (Q21_G | GND)
at("Q20", 11, 57.7); at("R77", 11, 61.2, 270); at("R78", 11, 64.4, 270)        # x 11 / mirrored 89: B's clears J3
at("Q21", 11, 68.0); at("R79", 11, 71.6, 270); at("R80", 11, 74.8, 270)
stack(14.3, ("R9", "R10"), 1); at("R11", 14.3, STACK_Y[3], 90)   # sense: R9 (+G | VS), R10 (VS | GND); R11 (VS up | Q11_G)
at("U3", 17.8, 60.1)                                     # CJ431 on the VREF node
stack(21.5, ("R3", "R4", "R5", "R6", "R7", "R8"))         # +G | VREF | TH80 | TH50 | TH20 | THCUT | GND
# the comparators side by side in one row (2026-11-01): J7, set back, now fills x 23.6-40.2 below y 70.5, and H6's standoff
# is right above; each decoupling cap under its VCC corner, Q14 (D1's driver) between the XT60s by the ON row
at("U1", 28.5, 64.3, 270); at("U2", 35.5, 64.3, 270)      # y 64.3: clear of H6's standoff (31, 57.5)
at("C1", 29.7, 69.2); at("C2", 36.7, 69.2); at("Q14", 41.8, 73.5, 90)
# pack B (right, mirrored; its rail switch one row lower)
at("Q23", mx(11), 63.5); at("R83", mx(11), 67, 270); at("R84", mx(11), 70.2, 270); at("Q24", mx(11), 74.0)
stack(mx(14.3), ("R51", "R52"), 1); at("R53", mx(14.3), STACK_Y[3], 90)
at("U16", mx(17.8), 60.1)
stack(mx(21.5), ("R45", "R46", "R47", "R48", "R49", "R50"))
at("U14", mx(28.5), 64.3, 90); at("U15", mx(35.5), 64.3, 90)
at("C20", mx(29.7), 69.2); at("C21", mx(36.7), 69.2)
# ---- output chains below their gauges, each beside its XT60, two rows each; only +OUT, -V and CAB run up to J3
at("F2", 12.5, 82.5); at("Q11", 19, 82.5, 270)                # chain A: GND -> F2 -> Q11 -> -V
at("R39", 10.5, 87.5); at("R40", 14, 87.5); at("Q26", 19, 87.5, 180)    # Q11's gate divider, -V interlock
at("F1", 81.5, 82.5); at("Q1", 88, 82.5, 180); at("R1", 92.5, 82.5); at("R2", 96, 82.5)   # chain B: +BATB -> F1 -> Q1 -> +OUT
at("Q22", 81, 87.5, 270); at("R81", 85, 87.5); at("R82", 88.5, 87.5)    # interlock / enable
# parts whose table rotation is the layout (the stacks and the comparators): tools/orient.py leaves them alone
LOCKED = ("R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R77", "R78", "R79", "R80", "U1", "U2",
          "R45", "R46", "R47", "R48", "R49", "R50", "R51", "R52", "R83", "R84", "U14", "U15",
          "Q1", "Q11", "Q22", "Q26", "Q14", "G1")                    # the chain FETs: tools/j3_bus.py ends on their pads
# ---- rotation overrides (tools/orient.py): turns that untangle the ratsnest, applied on top of the table
ROT = {"C1": 180, "C2": 0, "Q20": 90, "Q21": 90, "Q23": 180, "Q24": 90, "R11": 0, "R40": 180, "R53": 90, "R54": 180, "R55": 180, "R56": 180, "R57": 180, "R81": 90, "U3": 270}
for _r, _a in ROT.items():
    P[_r] = (P[_r][0], P[_r][1], _a)
# ---- end of rotation overrides
board = pcbnew.LoadBoard(BOARD)
# idempotent: a previous run's outline, rule areas and board-level silk are collected now and removed at the very end.
# Everything this script draws goes into one group, GROUP, and only that group's contents are removed on the next run:
# text, graphics or keep-outs added by hand in pcbnew stay (2026-11-01: the old rule took every free silk text and deleted
# the user's GLANCE / glanceneuro.org).  Edit the script's own items here, not in pcbnew: they are redrawn on every run.
GROUP = "place.py"
mine = [g for g in board.Groups() if g.GetName() == GROUP]
if mine:
    stale = [i for g in mine for i in g.GetItems()]
    for g in mine:
        g.RemoveAll()
        board.Remove(g)
else:                                       # boards from before the group: the script's items, recognised by layer / text
    OWN_TEXT = {"A", "B", "80%", "50%", "20%", "ON", "OUT", "PACK A  -V", "PACK B  +V", "LaserHAT SimpleBatteryPack rev A",
                "PACK A  (-V side, plugs to J7)", "PACK B  (+V side, plugs to J8)"}
    stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User)
             or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)
                 and (d.GetClass() == "PCB_SHAPE" or (d.GetClass() == "PCB_TEXT" and d.GetText() in OWN_TEXT)))]
    stale += [z for z in board.Zones() if z.GetIsRuleArea()]
before = {i.m_Uuid.AsString() for i in list(board.GetDrawings()) + list(board.Zones())}
fps = {f.GetReference(): f for f in board.GetFootprints()}
missing = [r for r in fps if r not in P]
assert not missing, f"unplaced: {missing}"
for ref, (x, y, rot) in P.items():
    f = fps[ref]
    f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    f.SetOrientationDegrees(rot)
    f.Reference().SetVisible(False)             # no designators on the silk
# SW1 stands with its lever along y: its own ON / OFF words would land on the LED rows and under the body, so they go
# beside the lever ends, east of the switch (ON toward the back)
for it in fps["SW1"].GraphicalItems():
    if it.GetClass() == "PCB_TEXT" and it.GetText() in ("ON", "OFF"):
        it.SetPosition(pcbnew.VECTOR2I(mm(58.2), mm(74.6 if it.GetText() == "ON" else 84.4)))
        it.SetTextAngleDegrees(0)


def seg(x1, y1, x2, y2, layer=pcbnew.F_SilkS, w=0.15):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_SEGMENT); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); d.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    board.Add(d)


def rect(x1, y1, x2, y2, layer, w):
    for (a, b), (c, d) in (((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)), ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))):
        seg(a, b, c, d, layer, w)


def outline(pts, radii):
    """closed Edge.Cuts polygon (clockwise, right-angle turns) with each corner filleted to its radius"""
    n = len(pts)
    for k in range(n):
        p0, p, p1 = pts[k - 1], pts[k], pts[(k + 1) % n]
        din = ((p[0] - p0[0]) / math.dist(p0, p), (p[1] - p0[1]) / math.dist(p0, p))
        dout = ((p1[0] - p[0]) / math.dist(p, p1), (p1[1] - p[1]) / math.dist(p, p1))
        r = radii[k]
        a = (p[0] - r * din[0], p[1] - r * din[1]); b = (p[0] + r * dout[0], p[1] + r * dout[1])
        c = (a[0] + r * dout[0], a[1] + r * dout[1])
        m = (c[0] + (din[0] - dout[0]) * r / math.sqrt(2), c[1] + (din[1] - dout[1]) * r / math.sqrt(2))
        d = pcbnew.PCB_SHAPE(board)
        d.SetShape(pcbnew.SHAPE_T_ARC); d.SetLayer(pcbnew.Edge_Cuts); d.SetWidth(mm(0.1))
        d.SetArcGeometry(*(pcbnew.VECTOR2I(mm(x), mm(y)) for x, y in (a, m, b)))
        board.Add(d)
        r1 = radii[(k + 1) % n]                            # straight run to the next corner's fillet
        q = (p1[0] - r1 * dout[0], p1[1] - r1 * dout[1])
        seg(b[0], b[1], q[0], q[1], pcbnew.Edge_Cuts, 0.1)


edge = [(0, 0), (W, 0), (W, H)]                           # clockwise; the front edge runs west through the notches
radii = [R_CORNER] * 3
for x1, x2 in sorted(NOTCHES, reverse=True):
    edge += [(x2, H), (x2, H - SETBACK), (x1, H - SETBACK), (x1, H)]
    radii += [R_NOTCH] * 4
edge.append((0, H)); radii.append(R_CORNER)
outline(edge, radii)                                      # outline: rounded corners, the two XT60 notches
for cx, cy in list(PI) + [(x, y) for _, x, y in CASE]:   # no vias under the Pi / case standoffs (r 3.0; mask-covered tracks are fine)
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
    o = z.Outline(); o.NewOutline()
    for k in range(24):
        a = 2 * math.pi * k / 24
        o.Append(mm(cx + 3.0 * math.cos(a)), mm(cy + 3.0 * math.sin(a)))
    board.Add(z)

# (The long runs to J3 are pre-routed along the board edges on B.Cu so they do not cut the 0V plane: tools/j3_bus.py.)

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


# board-level silk (row labels, OUT, pack names and envelopes, title) belongs to the user since 2026-11-01: drawn and
# edited in pcbnew, never touched here (this script used to redraw it and so reverted / deleted hand edits)
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
group = pcbnew.PCB_GROUP(board)
group.SetName(GROUP)
board.Add(group)
for i in list(board.GetDrawings()) + list(board.Zones()):
    if i.m_Uuid.AsString() not in before and i.GetClass() != "PCB_GROUP":
        group.AddItem(i)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
