#!/usr/bin/env python3
"""Placement of StimHAT.kicad_pcb (2026-10-29), board coordinates = HAT coordinates - (100, 43): 65 x 57 mm HAT outline
with the Pi 5 fan / PoE notch (x 59-65, y 8-16.5) and a 7.5 mm tab on the south-east (x 46-65, y 57-64.5).
Layout per the plan's panel 1g (claude_memory/stim-hat-plan):
  * top strip (y < 17.5) and the west half: the Rev 2 HAT core, all under the Adafruit 4567 bonnet (which sits on the
    stacking header 9 mm up), parts <= 7 mm tall; J10 (0.91" OLED socket, unpopulated) at the strip's east end
  * west edge, top to bottom: SW10 (USB power), J5 USB-C, the three LEDs, FIRE (SW9), the five-way joystick (SW7, at
    45 degrees so its directions line up with the board) in the south-west corner
  * two right-angle BNCs in the middle of the south edge (bodies x 15-46, y 43-57, barrels past the edge); PS1 (the
    DC-DC, hand-fitted) stands in the band north of them (body x 28-48, y 36.65-42.65, 10 mm tall, outside the bonnet):
    pins 1-2 (+5V / GND) west of x 34 on the HAT side, pins 4-6 in an isolated pocket that joins block A and strip B
  * the isolated stimulator: block A under the bonnet's east end (x 36.5-65, y 20-35), the pocket (x 36.5-65, y 35-38.5),
    strip B east of the BNCs (x 47.7-65, y 38.5-57) and the whole tab (J102 battery socket, J101 electrode header).
    Barrier = 2.5 mm copper-free rule areas; only U101 / U109 / PS1 straddle it.  MH4 falls inside isolated copper:
    nylon standoff.
Idempotent: re-running moves every footprint back to the table and redraws the outline and board-level drawings; copper
is left alone (rip it up first with tools/autoroute.py if the placement changes).      $KICAD_PY tools/place.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
W, H, TAB_X, TAB_Y = 65.0, 57.0, 46.0, 64.5
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
at("SW9", 2.2, 38.6, 270)
at("SW7", 7.5, 45.8, 45)
# ---- south edge: the two BNCs (rot 180 = barrel south, as on the HAT)
at("J6", 22.8, 44.4, 180); at("J7", 38.4, 44.4, 180)
# ---- core, west half under the bonnet: USB power path by the USB-C, LDOs above, MCU in the middle, UART bridge below
at("Q5", 14.5, 14.3, 90); at("R26", 14.5, 17.6, 90); at("Q3", 14.5, 20.5, 90); at("Q4", 18.5, 17.6, 90)
at("R21", 18.5, 14.3, 90); at("R22", 24.5, 20.5, 90)
at("U4", 23.0, 14.5, 180); at("C12", 17.0, 11.5); at("C6", 24.5, 10.8); at("C13", 26.5, 17.0, 90)
at("U5", 30.0, 14.5); at("R7", 26.5, 13.5, 90); at("C2", 33.3, 14.0, 90); at("JP1", 21.0, 10.3)
at("U7", 20.0, 26.0, -90)
at("C1", 20.58, 21.1, 0); at("C16", 29.9, 31.5, 90); at("C4", 24.8, 24.3, 90); at("R4", 10.0, 30.0, 90)
at("R3", 17.0, 34.0); at("C3", 19.5, 34.0); at("JP4", 22.5, 34.0)
at("R107", 27.5, 18.3, 90); at("R108", 30.0, 18.3, 90)
at("U6", 12.0, 35.5, 90); at("C17", 12.0, 31.3, 0)
at("U8", 28.0, 32.0, 90); at("R23", 26.5, 35.3); at("R24", 28.5, 35.3); at("R25", 30.5, 35.3)
# ---- top strip: I2C pull-ups by the header's pins 3 / 5, the EEPROM by pins 27 / 28, JP5, BSL, the OLED socket
# (J10's housing, when fitted, covers x 46.4-59, y 6.6-18: nothing else there)
at("R19", 12.0, 15.5, 90); at("R20", 12.0, 13.0, 90); at("C15", 7.5, 13.0, 90); at("JP5", 7.5, 16.0)
at("SW6", 31.0, 10.4); at("C103", 45.7, 16.5, 90); at("C18", 43.4, 11.4, 0); at("R2", 35.5, 16.0, 90)
at("U1", 40.5, 13.9); at("R1", 45.5, 11.0, 90)
at("J10", 57.0, 8.4, 0)
# ---- isolation: ISO7741F across the vertical barrier (x 35.25; pins 1-8 west), ISO1640 across the horizontal one
# (y 18.75; pins 1-4 north)
at("U101", 35.25, 27.0, 0)
at("R101", 29.0, 22.0, 90); at("R102", 29.0, 25.0, 90); at("R103", 29.0, 28.0, 90); at("C101", 30.8, 24.0, 90)
at("U109", 42.0, 19.5, 270)
# ---- isolated block A (x 36.5-65, y 20-34): set-point, switches, output stage, SHORT, fault detector
at("C102", 38.6, 22.3, 270); at("C124", 40.5, 26.8, 90); at("C115", 37.5, 31.8, 90); at("C125", 38.9, 33.0, 90); at("TP101", 62.5, 27.0)
at("U105", 44.3, 25.0); at("C114", 42.5, 28.3, 90); at("R110", 44.5, 28.3, 90); at("R109", 45.7, 22.6, 0)
at("U106", 50.8, 25.0); at("C117", 48.3, 28.4, 90); at("R105", 49.9, 28.4, 90); at("R106", 51.6, 28.4, 90); at("C116", 53.3, 28.4, 90)
at("R114", 46.7, 21.5); at("C120", 48.75, 21.5); at("R115", 50.75, 21.5); at("R116", 53.3, 21.5, 90); at("C121", 62.5, 21.5)
at("U107", 57.5, 25.5, 90); at("C118", 55.9, 20.9, 0); at("C119", 59.1, 30.5, 90)
at("U108", 43.5, 32.2); at("C126", 48.2, 32.0, 90); at("U110", 52.3, 32.0)
at("R117", 56.3, 32.6, 90); at("R118", 58.3, 32.6, 90); at("R119", 60.3, 32.6, 90); at("R120", 62.3, 32.6, 90)
at("R121", 64.0, 33.0, 90); at("D101", 57.0, 35.6, 90); at("C122", 54.5, 34.8); at("TP102", 62.5, 24.0)
# ---- isolated strip B (x 50-65, y 36.5-54.5): LDO and -4.3 V rail, LC filter, capacitance multipliers, clamps
at("U104", 51.8, 39.6); at("C112", 51.8, 36.9, 0); at("C111", 54.7, 39.6, 90); at("R113", 58.3, 39.0, 90)
at("D102", 60.0, 39.0, 90); at("C113", 61.7, 39.0, 90); at("D103", 63.4, 39.0, 90)
at("L101", 51.7, 43.0); at("C105", 55.4, 43.0); at("L102", 59.1, 43.0); at("C106", 62.8, 43.0)
at("Q101", 51.8, 47.0); at("R111", 54.3, 47.0, 90); at("C107", 56.5, 47.0, 90); at("Q102", 59.5, 47.0); at("R112", 62.3, 47.0, 90)
at("D104", 64.0, 47.0, 90)
at("C109", 51.8, 51.0); at("C110", 54.6, 51.0, 90); at("C108", 56.6, 51.0, 90)
# ---- DC-DC in the band north of the BNC bodies, and the tab (x 46-65, y 57-64.5, all isolated: J102 + J101)
# with the battery socket (vertical, cable from above) and the electrode header (pins out of the south edge)
at("PS1", 30.3, 37.55, 0)                   # body south of the pin row (y 36.65-42.65): pins 1-2 x 30.3 / 32.8 (HAT), 4-6 x 37.9-43.0 (isolated)
at("C104", 26.3, 38.6, 0)                   # input cap west of PS1's body (+5V west pad, GND east pad)
at("J102", 55.5, 60.0, 0)                   # pin 1 west: +V, 0V (GND_ISO), -V, CAB (= GND_ISO)
at("J101", 48.0, 60.5, 90)                  # vertical 1x2 west of J102; pin 1 (square) = E1 west

board = pcbnew.LoadBoard(BOARD)
stale = [d for d in board.GetDrawings() if d.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Cmts_User, pcbnew.Dwgs_User)
         or (d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.GetClass() in ("PCB_TEXT", "PCB_SHAPE"))]
stale += [z for z in board.Zones() if z.GetIsRuleArea()]
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
seg(NOTCH[0], NOTCH[3], W, NOTCH[3], E, 0.1); seg(W, NOTCH[3], W, TAB_Y, E, 0.1)
seg(W, TAB_Y, TAB_X, TAB_Y, E, 0.1); seg(TAB_X, TAB_Y, TAB_X, H, E, 0.1)
seg(TAB_X, H, R, H, E, 0.1); arc(R, H - R, R, 90, 180)
seg(0, H - R, 0, R, E, 0.1); arc(R, R, R, 180, 270)


def keepout(pts, vias_only=False):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(not vias_only); z.SetDoNotAllowVias(True); z.SetDoNotAllowCopperPour(True)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    o = z.Outline(); o.NewOutline()
    for px, py in pts:
        o.Append(mm(px), mm(py))
    board.Add(z)


# isolation barrier (2.5 mm, copper-free on both layers), see the docstring
BAR = ((34.0, 17.5, 65.0, 20.0),      # north of block A (the 2.5 mm from U109 side-1 pads is checked by the .kicad_dru rule)
       (34.0, 17.5, 36.5, 42.8),      # west of block A and of the pocket (PS1 pin 2 at x 32.8 is HAT side)
       (36.5, 39.4, 47.7, 42.8),      # south of the pocket: PS1's output pads (to y 38.55) vs the BNC J7 tails (y 44.4)
       (45.2, 42.8, 47.7, 57.0))      # east of the BNC J7 (its posts reach x 45.2) / west of strip B and the tab
for x1, y1, x2, y2 in BAR:
    keepout(((x1, y1), (x2, y1), (x2, y2), (x1, y2)))
    rect(x1, y1, x2, y2, pcbnew.Cmts_User, 0.1)
# no copper under the standoffs / screw heads (M2.5 hardware up to 6.5 mm; MH4 sits in the isolated area: nylon, wider)
for cx, cy, r in ((3.5, 4.5, 3.25), (61.5, 4.5, 3.25), (3.5, 53.5, 3.25), (61.5, 53.5, 2.85)):
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
silk("TRIG IN", 22.8, 42.3); silk("STIM OUT", 38.4, 42.3)        # STIM OUT is covered when PS1 is fitted; also on the back
silk("FIRE", 6.2, 37.5, 0.8, 90); silk("USB", 11.8, 24.0, 0.8, 90); silk("PWR", 6.6, 13.0, 0.8, 90)
silk("5V", 8.0, 31.5, 0.8); silk("MCU", 8.0, 33.1, 0.8); silk("STIM", 8.05, 34.7, 0.8)
silk("BSL", 35.0, 10.4); silk("OLED", 61.5, 18.8)
silk("ISOLATED", 49.5, 18.75); silk("E1", 48.0, 63.4, 0.8); silk("+V", 55.3, 57.0, 0.8); silk("0V", 57.5, 57.0, 0.8); silk("-V", 59.4, 57.0, 0.8); silk("CAB", 61.9, 57.0, 0.8); silk("NYLON", 61.5, 50.0, 0.8)
silk("STIM OUT", 38.4, 53.5, 1.0, 0, pcbnew.B_SilkS); silk("TRIG IN", 22.8, 53.5, 1.0, 0, pcbnew.B_SilkS)
# drawings: the bonnet (65 x 30.7 on the header), the 0.91" OLED module when fitted, the Pi 5 notch note
rect(0, 0, 65, 30.7, pcbnew.Dwgs_User, 0.15); silk("Adafruit 4567 bonnet (9 mm up)", 20, 2.5, 1.0, 0, pcbnew.Dwgs_User)
rect(19.0, 5.0, 57.0, 17.0, pcbnew.Dwgs_User, 0.15); silk("0.91in OLED module on J10", 38.0, 16.0, 0.8, 0, pcbnew.Dwgs_User)
silk("Pi 4 PoE / Pi 5 fan", 56.0, 7.0, 0.8, 0, pcbnew.Dwgs_User)
# PS1 stands under the tab with its body past the tab's west edge by design: drop its silk outline (it would be
# clipped by the edge; the part is hand-fitted and its pins are marked on the top side)
for it in list(fps["PS1"].GraphicalItems()):
    if it.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        fps["PS1"].Remove(it)
for d in stale:
    board.Remove(d)
pcbnew.SaveBoard(BOARD, board)
print("placed", len(P), "footprints; saved", BOARD)
