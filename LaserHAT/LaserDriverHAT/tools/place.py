#!/usr/bin/env python3
"""Placement of LaserDriverHAT.kicad_pcb (2026-10-30), derived from the StimHAT's: 65 x 57 mm HAT outline with the Pi 5
fan / PoE notch (x 59-65, y 8-16.5).
  * top strip (y < 17.5) and the west half: the Rev 2 HAT core exactly as on the StimHAT, all under the Adafruit 4567
    bonnet (which sits on the stacking header 9 mm up), parts <= 7 mm tall; J10 (vertical socket for the 0.91" OLED
    module, unpopulated) at the strip's west end
  * west edge, top to bottom: SW10 (USB power), J5 USB-C, the three LEDs, FIRE (SW9), the five-way joystick (SW7, at
    135 degrees) in the south-west corner
  * two right-angle BNCs in the middle of the south edge (bodies x 17-49, y 43-57, barrels past the edge): TRIG IN, SYNC OUT
  * the laser driver: the LaserDaughter module's layout block (its footprints, tracks, vias and GND pour) translated by
    (-62.5, -57.25) from the module's coordinates, i.e. the module outline x 101-127.5 / y 76-99.5 sits at x 38.5-65 /
    y 18.75-42.25 against the east edge; J2 (laser diode socket, tall) and SW5 (5 / 12 V) south of the bonnet's edge
    (y 31), the boost and the steering pair under it (all <= 7 mm: J205's 2.0 mm shunt is the tallest, ~6 mm)
Idempotent: re-running moves every footprint back to the table and redraws the outline, the ground planes / pours,
the standoff keep-outs and the board-level drawings; copper is left alone.      $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "LaserDriverHAT.kicad_pcb")
W, H = 65.0, 57.0
NOTCH = (59.0, 8.0, 65.0, 16.5)
LASER_DX, LASER_DY = -62.5, -57.25         # LaserDaughter board coordinates -> HAT coordinates (block imported, not rotated)
mm = pcbnew.FromMM
P = {}                                     # ref -> (x, y, rot, flip)


def at(ref, x, y, rot=0, flip=False):
    P[ref] = (x, y, rot, flip)


# ---- mechanical: HAT holes and the Pi header exactly as on the Rev 2 HAT (shifted by -100, -43)
at("MH1", 3.5, 4.5); at("MH2", 61.5, 4.5); at("MH3", 3.5, 53.5); at("MH4", 61.5, 53.5)
at("J1", 8.37, 5.77, -90, True)
# ---- west edge, top to bottom
at("SW10", 2.2, 13.0, -90)
at("J5", 4.2, 24.0, -90)
at("R8", 10.3, 22.75, 0); at("R10", 10.1, 27.0, 270)
at("D5", 3, 31.5, 180); at("R13", 5.8, 31.5)
at("D7", 3, 33.1, 180); at("R15", 5.8, 33.1)
at("D9", 3, 34.7, 180); at("R18", 5.8, 34.7)
at("SW9", 10, 53.75, -90)
at("SW7", 8.16, 43.22, 135)
# ---- south edge: the two BNCs (rot 180 = barrel south, as on the HAT)
at("J6", 24.92, 44.42, 180); at("J7", 40.92, 44.42, 180)
# ---- core, west half under the bonnet: USB power path by the USB-C, LDOs above, MCU in the middle, UART bridge below
at("Q5", 16.5, 19.9, 0); at("R26", 14.2, 20.8, 90); at("Q3", 16.5, 15.5, 180); at("Q4", 16.8, 10.5, 0)
at("R21", 13.5, 9.55, 180); at("R22", 14.1, 12.9, 90)
at("U4", 23.0, 14.5, 180); at("C12", 20.6, 11.3, 0); at("C6", 23.1, 11.5, 180); at("C13", 23.08, 10.4, 180)
at("U5", 28.3, 11.64, 90); at("R7", 27.99, 9, 0); at("C2", 28.5, 15, 0); at("JP1", 53.5, 15.6, 180)
at("U7", 23.25, 26, -90)
at("C1", 23, 20.75, 180); at("C16", 32.25, 32, 90); at("C4", 27, 23.4, 90); at("R4", 21.2, 22, 180)
at("R3", 24.75, 20, -90); at("C3", 25.75, 20, 90); at("JP4", 14.28, 29.75, 180, True)
at("U6", 14.5, 25.91, 0); at("C17", 14.9, 29.2, 180)   # C17 at U6 (its 3V3 via at (15.5, 27.81))
at("U8", 28.75, 32.5, 0); at("R23", 26.5, 35.3); at("R24", 28.5, 35.3); at("R25", 30.5, 35.3)
# ---- top strip: the EEPROM by pins 27 / 28, JP5, BSL; the OLED socket J10 at the west end, JP1 at the strip's east end
at("R19", 8.9, 11.88, 0); at("R20", 8.9, 14.42, 0); at("C15", 7.92, 10.2, 180); at("JP5", 26.85, 10.75, 0, True)
at("SW6", 21.27, 34.25, 180); at("C18", 50.54, 15, -90); at("R2", 46.69, 12.2, 0)
at("U1", 53.4, 12.2, 180); at("R1", 48.29, 11.2, 0)
at("J10", 11.75, 19.5, 180)                 # pins x 22.81 (GND) 20.27 (VCC) 17.73 (SCL) 15.19 (SDA)
at("G1", 37.95, 12.57, 0)   # owl logo: board-only footprint laserdriverhat:OwlLogo_Eyes_14mm_R (tools/owl_logo.py), placed by the user
# ---- laser driver block (the LaserDaughter layout at module position + (LASER_DX, LASER_DY); J4 is on the back)
at("C208", 39.9, 26.75, -90); at("C209", 41.5, 31.25, 180); at("C211", 55.47, 39.26, -90); at("C212", 58.73, 34, 0)
at("D1", 43, 26.75, 90); at("D2", 46.9, 29.45, 0); at("D3", 45.5, 33.15, -90); at("D4", 48, 33.15, -90)
at("J2", 48.5, 37.61, 0); at("J205", 51, 25, 90); at("J4", 46, 38.75, 90, True); at("L1", 41.5, 21.75, 0)
at("Q1", 52.1, 32, -90); at("Q2", 58.5, 28.75, 90); at("R201", 63, 37.25, 0); at("R202", 63, 38.25, 180)
at("R203", 57.67, 39.26, 90); at("R204", 56.57, 39.26, -90); at("R205", 45.25, 27.35, 0); at("R206", 45.99, 26.25, 0)
at("R211", 63.01, 39.25, 180); at("R212", 62.99, 40.25, 0); at("Rs1", 60.4, 38.4125, -90); at("SW5", 41.5, 37.55, -90)
at("U202", 46.5, 23.95, 0); at("U203", 56.9875, 36.25, 0)

board = pcbnew.LoadBoard(BOARD)
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User, pcbnew.User_1)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea() or z.GetZoneName() in ("GND plane", "GND pour F", "GND pour B")]
board.SetCopperLayerCount(4)                                  # 4 layers: In1 = GND plane, In2 = routing (power)
fps = {f.GetReference(): f for f in board.GetFootprints()}
missing = [r for r in fps if r not in P]
assert not missing, f"unplaced: {missing}"
for ref, (x, y, rot, flip) in P.items():
    f = fps[ref]
    if f.IsFlipped() != flip:
        f.Flip(f.GetPosition(), False)
    f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    f.SetOrientationDegrees(rot)
    f.Reference().SetVisible(False)             # no designators or values on the silk (function labels instead)
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


# outline: 3 mm radii on the four HAT corners, the notch
R = 3.0
E = pcbnew.Edge_Cuts
seg(R, 0, W - R, 0, E, 0.1); arc(W - R, R, R, 270, 360)
seg(W, R, W, NOTCH[1], E, 0.1); seg(W, NOTCH[1], NOTCH[0], NOTCH[1], E, 0.1); seg(NOTCH[0], NOTCH[1], NOTCH[0], NOTCH[3], E, 0.1)
seg(NOTCH[0], NOTCH[3], W, NOTCH[3], E, 0.1); seg(W, NOTCH[3], W, H - R, E, 0.1); arc(W - R, H - R, R, 0, 90)
seg(W - R, H, R, H, E, 0.1); arc(R, H - R, R, 90, 180)
seg(0, H - R, 0, R, E, 0.1); arc(R, R, R, 180, 270)


def keepout(pts, vias_only=False):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(not vias_only); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


def plane(name, net, layer, pts, clearance=0.2):
    """a copper zone (filled by ../tools/fill_zones.py)"""
    z = pcbnew.ZONE(board)
    z.SetZoneName(name); z.SetLayer(layer); z.SetNetCode(board.GetNetcodeFromNetname(net))
    z.SetMinThickness(mm(0.2)); z.SetLocalClearance(mm(clearance))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


# One GND everywhere (the StimHAT's GND_ISO side is gone): In1 a full GND plane, F / B GND pours over the whole board
# (0.25 mm clearance so hand routing keeps room).  The laser block brings its own F / B GND pour ("Laser GND pour",
# priority 1, the module's 0.25 mm / 0.5 mm-spoke settings), which place.py leaves alone.  In2 is a routing layer.
FULL = [(0, 0), (65, 0), (65, 57), (0, 57)]
plane("GND plane", "GND", pcbnew.In1_Cu, FULL)
plane("GND pour F", "GND", pcbnew.F_Cu, FULL, 0.25); plane("GND pour B", "GND", pcbnew.B_Cu, FULL, 0.25)
# no copper under the standoffs / screw heads (M2.5 hardware up to 6.5 mm)
for cx, cy, r in ((3.5, 4.5, 3.25), (61.5, 4.5, 3.25), (3.5, 53.5, 3.25), (61.5, 53.5, 3.25)):
    keepout([(cx + r * math.cos(2 * math.pi * k / 24), cy + r * math.sin(2 * math.pi * k / 24)) for k in range(24)])


def silk(txt, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15 * size))
    t.SetTextAngleDegrees(rot)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


silk("LaserDriverHAT rev A", 32.5, 30.0, 1.0, 0, pcbnew.B_SilkS)
silk("FIRE", 14.0, 53.75, 1.0, 0); silk("USB", 9.6, 24.6, 1.0, 90); silk("PWR", 6.1, 13.0, 1.0, 90)
silk("5V", 8.0, 31.5, 0.8); silk("MCU", 8.0, 33.1, 0.8); silk("SYNC", 8.05, 34.7, 0.8)   # 0.8: no room for 1.0 between R13-R18 and the LEDs
silk("BSL", 16.9, 34.25, 1.0, 90)
silk("SYNC OUT", 40.92, 53.5, 1.0, 0, pcbnew.B_SilkS); silk("TRIG IN", 24.92, 53.5, 1.0, 0, pcbnew.B_SilkS)   # centred on J7 / J6
silk("TRIG IN", 16.3, 50.0, 1.0, 90); silk("SYNC OUT", 49.4, 50.0, 1.0, 90)   # front, on the jacks' outer sides (0.4 mm between the bodies)
# the laser module's own labels, at their module positions + (LASER_DX, LASER_DY): SW5's two ends, the RED shunt
for txt, mx, my in (("12V", 102.7, 90.0), ("5V", 106.5, 98.55), ("RED", 114.5, 80.25)):
    silk(txt, mx + LASER_DX, my + LASER_DY, 0.8)


def circle(cx, cy, r, layer, w=0.15):
    d = pcbnew.PCB_SHAPE(board)
    d.SetShape(pcbnew.SHAPE_T_CIRCLE); d.SetLayer(layer); d.SetWidth(mm(w))
    d.SetCenter(pcbnew.VECTOR2I(mm(cx), mm(cy))); d.SetEnd(pcbnew.VECTOR2I(mm(cx + r), mm(cy)))
    board.Add(d)


# Adafruit 128x64 1.3" OLED bonnet (4567) from Adafruit's EagleCAD board: 65 x 30.66 mm, 3 mm corner radii, four
# 2.8 mm holes at 3.5 / 61.5 x 3.5 / 26.5 (Eagle, y up), header rows 2.54 apart.  Its header rows coincide with J1's
# (y 3.23 / 5.77), so HAT y = 31.0 - Eagle y: the bonnet spans y 0.34-31.0, 9 mm above the HAT on the stacking header.
BON = pcbnew.User_1
board.SetLayerName(BON, "Bonnet")
seg(0, 28.0, 0, 3.34, BON); arc(3, 3.34, 3, 180, 270, BON, 0.15); seg(3, 0.34, 62, 0.34, BON); arc(62, 3.34, 3, 270, 360, BON, 0.15)
seg(65, 3.34, 65, 28.0, BON); arc(62, 28.0, 3, 0, 90, BON, 0.15); seg(62, 31.0, 3, 31.0, BON); arc(3, 28.0, 3, 90, 180, BON, 0.15)
for hx, hy in ((3.5, 4.5), (61.5, 4.5), (3.5, 27.5), (61.5, 27.5)):
    circle(hx, hy, 1.4, BON)
rect(7.6, 0.8, 57.4, 8.15, BON, 0.15)                                    # the 2x20 stacking socket
rect(15.26, 7.63, 49.76, 30.63, BON, 0.15); rect(17.8, 9.73, 47.2, 24.43, BON, 0.15)   # OLED module, active area
rect(3.13, 12.54, 13.13, 22.54, BON, 0.15); circle(8.13, 17.54, 2.9, BON)              # 5-way joystick
rect(58.09, 11.95, 64.09, 18.55, BON, 0.15); circle(61.09, 15.25, 1.5, BON)            # button #6
rect(50.85, 18.43, 56.85, 25.03, BON, 0.15); circle(53.85, 21.73, 1.5, BON)            # button #5
silk("Adafruit 4567 bonnet, 9 mm up (outline, holes, header, OLED, joystick, buttons)", 32.5, 33.0, 1.0, 0, BON)
# drawings: the laser module's outline where its block sits, the 0.91" OLED module when fitted, the Pi 5 notch note
rect(101 + LASER_DX, 76 + LASER_DY, 127.5 + LASER_DX, 99.5 + LASER_DY, pcbnew.Dwgs_User, 0.1)
silk("LaserDaughter block (module outline)", 51.75, 43.0 - 0.3, 0.8, 0, pcbnew.Dwgs_User)
rect(11.75, 9.9, 49.75, 21.5, pcbnew.Dwgs_User, 0.1)
silk("0.91in OLED module on J10: pins on its west (short) edge, right-angle pins into the vertical socket, lying flat eastward 8.5 mm up", 30.0, 23.0, 0.8, 0, pcbnew.Dwgs_User)
silk("Pi 4 PoE / Pi 5 fan", 56.0, 7.0, 0.8, 0, pcbnew.Dwgs_User)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
