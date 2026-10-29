#!/usr/bin/env python3
"""Placement of StimHAT.kicad_pcb (2026-10-29), board coordinates = HAT coordinates - (100, 43): 65 x 57 mm HAT outline
with the Pi 5 fan / PoE notch (x 59-65, y 8-16.5) no tab since the DC-DC left for its pod.
Layout per the plan's panel 1g (claude_memory/stim-hat-plan):
  * top strip (y < 17.5) and the west half: the Rev 2 HAT core, all under the Adafruit 4567 bonnet (which sits on the
    stacking header 9 mm up), parts <= 7 mm tall; J10 (vertical socket for the 0.91" OLED module, unpopulated) at
    the strip's west end under the header: the module stands up along the header, facing south (text flipped in
    software), pins west to east SDA SCL VCC GND
  * west edge, top to bottom: SW10 (USB power), J5 USB-C, the three LEDs, FIRE (SW9), the five-way joystick (SW7, at
    45 degrees so its directions line up with the board) in the south-west corner
  * two right-angle BNCs in the middle of the south edge (bodies x 15-46, y 43-57, barrels past the edge); the band
    north of them (y 36.5-43) carries the battery socket J102 in an isolated pocket (x 36.5-47.7) and, 25 mm west on the
    HAT side, J103 (2-pin 5 V / GND): the DC-DC pod (A0515S + filter on its own board) plugs into J102's holes and J103
    and lies flat over the band, its own isolation gap over the HAT's barrier strip at x 34-36.5
  * the isolated stimulator: block A under the bonnet's east end (x 36.5-65, y 20-35), the pocket (x 36.5-65, y 35-38.5),
    strip B east of the BNCs (x 47.7-65, y 38.5-57) and J101 (vertical electrode header) in strip B's south.
    Barrier = 2.5 mm copper-free rule areas; only U101 / U109 / PS1 straddle it.  MH4 falls inside isolated copper:
    nylon standoff.
Idempotent: re-running moves every footprint back to the table and redraws the outline and board-level drawings; copper
is left alone (rip it up first with tools/autoroute.py if the placement changes).      $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
W, H = 65.0, 57.0                          # the south-east tab went with the DC-DC (2026-10-29)
NOTCH = (59.0, 8.0, 65.0, 16.5)
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
at("R8", 10.0, 20.5, 90); at("R10", 10.0, 27.5, 90)
at("D5", 2.6, 31.5); at("R13", 5.8, 31.5)
at("D7", 2.6, 33.1); at("R15", 5.8, 33.1)
at("D9", 2.6, 34.7); at("R18", 5.8, 34.7)
at("SW9", 10, 53.75, -90)
at("SW7", 8.16, 43.22, 45)
# ---- south edge: the two BNCs (rot 180 = barrel south, as on the HAT)
at("J6", 24.92, 44.42, 180); at("J7", 40.92, 44.42, 180)
# ---- core, west half under the bonnet: USB power path by the USB-C, LDOs above, MCU in the middle, UART bridge below
at("Q5", 14.5, 14.3, 90); at("R26", 14.5, 17.6, 90); at("Q3", 14.5, 20.5, 90); at("Q4", 18.5, 17.6, 90)
at("R21", 18.5, 14.3, 90); at("R22", 24.5, 20.5, 90)
at("U4", 23.0, 14.5, 180); at("C12", 19.7, 12.3, 0); at("C6", 26.5, 10.6, 180); at("C13", 26.5, 17.0, 90)
at("U5", 30.0, 14.5); at("R7", 26.5, 13.5, 90); at("C2", 33.3, 14.0, 90); at("JP1", 50.0, 10.0, 0)
at("U7", 20.0, 26.0, -90)
at("C1", 20.58, 21.1, 0); at("C16", 29.9, 31.5, 90); at("C4", 24.8, 24.3, 90); at("R4", 10.0, 30.0, 90)
at("R3", 17.4, 34); at("C3", 19.5, 34.0); at("JP4", 22.5, 34.0)
at("R107", 27.5, 18.3, 90); at("R108", 30.0, 18.3, 90)
at("U6", 13.4, 32.65, 90); at("C17", 12.02, 27.5, 0)
at("U8", 28.0, 32.0, 90); at("R23", 26.5, 35.3); at("R24", 28.5, 35.3); at("R25", 30.5, 35.3)
# ---- top strip: I2C pull-ups by the header's pins 3 / 5, the EEPROM by pins 27 / 28, JP5, BSL; the OLED socket J10
# right under the header at the west end (pins along x at y 10, pin 1 = GND east), JP1 moved to the strip's east end
at("R19", 12.0, 15.5, 90); at("R20", 12.0, 13.0, 90); at("C15", 7.5, 13.0, 90); at("JP5", 7.5, 16.0)
at("SW6", 31.0, 10.4); at("C103", 45.7, 16.5, 90); at("C18", 43.4, 11.4, 0); at("R2", 35.5, 16.0, 90)
at("U1", 40.5, 13.9); at("R1", 45.5, 11.0, 90)
at("J10", 22.81, 10.0, 270)                 # pins x 22.81 (GND) 20.27 (VCC) 17.73 (SCL) 15.19 (SDA)
# ---- isolation: ISO7741F across the vertical barrier (x 35.25; pins 1-8 west), ISO1640 across the horizontal one
# (y 18.75; pins 1-4 north)
at("U101", 35.25, 27.0, 0)
at("R101", 29.0, 22.0, 90); at("R102", 29.0, 25.0, 90); at("R103", 29.0, 28.0, 90); at("C101", 30.8, 24.0, 90)
at("U109", 42.0, 19.5, 270)
# ---- isolated block A (x 36.5-65, y 20-34): set-point, switches, output stage, SHORT, fault detector
at("C102", 38, 23, 90); at("C124", 45.5, 21.5, 90); at("C115", 51.8, 20.45, 180); at("C125", 61.4, 38.2, 90); at("TP101", 63.55, 44.55, 0)
at("U105", 49.95, 22.75, 180); at("C114", 47.25, 24.7, 180); at("R110", 40.85, 23.75, 0); at("R109", 43.15, 23.75, 180)
at("U106", 58.65, 25.25, 90); at("C117", 61.15, 26.6, -90); at("R105", 54.2, 21.85, 90); at("R106", 55.75, 21.82, -90); at("C116", 56, 24.88, -90)
at("R114", 55.24, 27.05, 0); at("C120", 55.8, 28.48, -90); at("R115", 57, 29.5, -90); at("R116", 59.15, 29.55, 0); at("C121", 53.15, 50, -90)
at("U107", 48, 28, 180); at("C118", 52.9, 28.2, -90); at("C119", 52.6, 25.9, -90)
at("U108", 56.88, 41.01, 180); at("C126", 51.85, 42.45, 90); at("U110", 56.94, 34.05, 0)
at("R117", 56.05, 31.7, 180); at("R118", 53.75, 31.7, 180); at("R119", 53.15, 34.3, -90); at("R120", 41.6, 30.8, 180)
at("R121", 39.59, 30.8, 0); at("D101", 40.85, 29.15, 0); at("C122", 56.91, 36.55, 180); at("TP102", 63.75, 21.75, 0)
# ---- isolated strip B (x 50-65, y 36.5-54.5): LDO and -4.3 V rail, LC filter, capacitance multipliers, clamps
at("U104", 48, 39.5, -90); at("C112", 50.5, 39, -90); at("C111", 48, 35.5, 90); at("R113", 42, 35.5, -90)
at("D102", 44, 35.5, 90); at("C113", 41, 33, 0); at("D103", 50.55, 36.25, 0)
at("D104", 40, 35.5, -90)
at("C109", 46, 35.55, 90); at("C110", 38, 35.55, -90)
# ---- the battery socket / pod end in the band north of the BNC bodies, the pod's 5 V end, J101 in strip B
# with the battery socket (vertical, cable from above) and the electrode header (pins out of the south edge)
at("J102", 44.0, 40.1, 180)                 # pin 1 east: +V 44.0, 0V 42.0, -V 40.0, CAB 38.0 (= GND_ISO); housing north
at("J103", 19.0, 40.1, 90)                  # 2-pin 5 V (west, square) / GND for the DC-DC pod, HAT side of the band
at("J101", 53.16, 54.15, 90)                  # vertical 1x2 on the tab; pin 1 (square) = E1 west

board = pcbnew.LoadBoard(BOARD)
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User, pcbnew.User_1)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea() or z.GetZoneName() in ("GND plane", "GND_ISO plane", "GND pour F", "GND pour B", "GND_ISO pour F", "GND_ISO pour B", "+5V plane", "MSPM0_3V3 plane", "+5V_ISO plane", "+V_STIM plane")]
board.SetCopperLayerCount(4)                                  # 4 layers (2026-10-29): In1 = ground planes, In2 = power
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


# outline: 3 mm radii on the three HAT corners, square tab and notch
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
    """a copper zone (filled by tools/fill_zones.py); the two ground planes on In1 are bounded by the barrier"""
    z = pcbnew.ZONE(board)
    z.SetZoneName(name); z.SetLayer(layer); z.SetNetCode(board.GetNetcodeFromNetname(net))
    z.SetMinThickness(mm(0.2)); z.SetLocalClearance(mm(clearance))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


# In1 ground planes: HAT GND everywhere west / north of the barrier (the BNC J7 area included, stopping 2.6 mm north
# of J7's tails = 2.5 mm from J102's pads), GND_ISO under block A, the pocket, strip B and the tab; the rule areas
# (all copper layers) keep the 2.5 mm barrier and the standoff circles copper-free
plane("GND plane", "GND", pcbnew.In1_Cu, [(0, 0), (65, 0), (65, 17.4), (34, 17.4), (34, 43.7), (47.7, 43.7), (47.7, 57), (0, 57)])

# (the isolated polygons are notched under U109, whose HAT-side pads end at y 18.0: isolated copper from y 20.6 there)
# named regions for the isolation DRC rules (StimHAT.kicad_dru): rule areas that keep nothing out by themselves, so the
# router draws no halos; the rules disallow HAT-side copper in 'isolated_region' and isolated copper in 'hat_region'.
# Together with the 2.5 mm strips above (which are exactly the gap between the two regions) that is the barrier.
def region(name, pts):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetZoneName(name)
    z.SetDoNotAllowTracks(False); z.SetDoNotAllowVias(False); z.SetDoNotAllowCopperPour(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(board.GetCopperLayerCount()))
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


# F / B ground pours (same shapes, 0.25 mm clearance so hand routing keeps room) and In2 power islands: HAT side
# +5V everywhere except the MCU area, which is MSPM0_3V3; isolated side +5V_ISO in the north-west (x < 54.5, y < 33), +V_STIM east and south of it
plane("GND pour F", "GND", pcbnew.F_Cu, [(0, 0), (65, 0), (65, 17.4), (34, 17.4), (34, 43.7), (47.7, 43.7), (47.7, 57), (0, 57)], 0.25); plane("GND pour B", "GND", pcbnew.B_Cu, [(0, 0), (65, 0), (65, 17.4), (34, 17.4), (34, 43.7), (47.7, 43.7), (47.7, 57), (0, 57)], 0.25)
plane("GND_ISO pour F", "GND_ISO", pcbnew.F_Cu, [(36.5, 20), (38.5, 20), (38.5, 20.6), (45.5, 20.6), (45.5, 20), (65, 20), (65, 57), (50.2, 57), (50.2, 41.2), (36.5, 41.2)], 0.25); plane("GND_ISO pour B", "GND_ISO", pcbnew.B_Cu, [(36.5, 20), (38.5, 20), (38.5, 20.6), (45.5, 20.6), (45.5, 20), (65, 20), (65, 57), (50.2, 57), (50.2, 41.2), (36.5, 41.2)], 0.25)
plane("MSPM0_3V3 plane", "MSPM0_3V3", pcbnew.In2_Cu, [(13, 18), (34, 18), (34, 37), (13, 37)])
plane("+5V plane", "+5V", pcbnew.In2_Cu, [(0, 0), (65, 0), (65, 17.4), (34, 17.4), (34, 18), (13, 18), (13, 37), (34, 37), (34, 43.7), (47.7, 43.7), (47.7, 57), (0, 57)])
plane("+5V_ISO plane", "+5V_ISO", pcbnew.In2_Cu, [(36.5, 20), (38.5, 20), (38.5, 20.6), (45.5, 20.6), (45.5, 20), (54.5, 20), (54.5, 33), (51, 33), (51, 34.2), (48.5, 34.2), (48.5, 33), (36.5, 33)])
plane("+V_STIM plane", "+V_STIM", pcbnew.In2_Cu, [(54.5, 20), (65, 20), (65, 57), (50.2, 57), (50.2, 41.2), (36.5, 41.2), (36.5, 33), (48.5, 33), (48.5, 34.2), (51, 34.2), (51, 33), (54.5, 33)])
region("hat_region", [(0, 0), (65, 0), (65, 17.4), (34, 17.4), (34, 43.7), (47.7, 43.7), (47.7, 57), (0, 57)])
region("isolated_region", [(36.5, 20), (38.5, 20), (38.5, 20.6), (45.5, 20.6), (45.5, 20), (65, 20), (65, 57), (50.2, 57), (50.2, 41.2), (36.5, 41.2)])
plane("GND_ISO plane", "GND_ISO", pcbnew.In1_Cu, [(36.5, 20), (38.5, 20), (38.5, 20.6), (45.5, 20.6), (45.5, 20), (65, 20), (65, 57), (50.2, 57), (50.2, 41.2), (36.5, 41.2)])


# isolation barrier (2.5 mm, copper-free on both layers), see the docstring
BAR = ((34.0, 17.4, 65.0, 20.0),      # north of block A (U109 straddles it); 17.4: C115's pad is 2.56 mm from the HAT plane
       (34.0, 17.5, 36.5, 43.7),      # west of block A and of J102's pocket (U101 straddles it)
       (36.5, 41.2, 50.2, 43.7),      # south of the pocket: J102's pads (to y 41.0) vs the BNC J7 tails (from y 43.6)
       (47.7, 43.7, 50.2, 57.0))      # east of the BNC J7 (its east post reaches x 47.7) / west of strip B
for x1, y1, x2, y2 in BAR:
    keepout(((x1, y1), (x2, y1), (x2, y2), (x1, y2)))
    rect(x1, y1, x2, y2, pcbnew.Cmts_User, 0.1)
# no copper under the standoffs / screw heads (M2.5 hardware up to 6.5 mm; MH4 sits in the isolated area: nylon, wider)
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


silk("StimHAT rev A", 32.5, 30.0, 1.0, 0, pcbnew.B_SilkS)
silk("FIRE", 6.2, 37.5, 1.0, 90); silk("USB", 11.8, 24.0, 1.0, 90); silk("PWR", 6.1, 13.0, 1.0, 90)
silk("5V", 8.0, 31.5, 0.8); silk("MCU", 8.0, 33.1, 0.8); silk("STIM", 8.05, 34.7, 0.8)   # 0.8: no room for 1.0 between R13-R18 and the LEDs
silk("BSL", 35.0, 10.4)
silk("ISOLATED", 49.5, 18.75); silk("5V", 19.0, 37.6, 0.9); silk("E1", 51.0, 63.4, 1.0); silk("+V 0V -V CAB", 41.0, 42.4, 0.9, 0, pcbnew.B_SilkS); silk("NYLON", 61.5, 50.0, 1.0)
silk("STIM OUT", 38.4, 53.5, 1.0, 0, pcbnew.B_SilkS); silk("TRIG IN", 22.8, 53.5, 1.0, 0, pcbnew.B_SilkS)
# drawings: the 0.91" OLED module when fitted, the Pi 5 notch note; the bonnet on its own layer User.1 "Bonnet"
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
rect(16.5, 36.8, 46.0, 43.0, pcbnew.Dwgs_User, 0.15); silk("DC-DC pod: J103 (5 V) to J102 (+/-V), lies over the band", 31.0, 35.0, 0.8, 0, pcbnew.Dwgs_User)
rect(0.0, 9.2, 38.0, 10.8, pcbnew.Dwgs_User, 0.15); silk("0.91in OLED module standing in J10 (38 x 12, 8.5 mm up)", 19.0, 19.6, 0.8, 0, pcbnew.Dwgs_User)
silk("Pi 4 PoE / Pi 5 fan", 56.0, 7.0, 0.8, 0, pcbnew.Dwgs_User)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
