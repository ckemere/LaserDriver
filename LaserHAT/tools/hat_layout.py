#!/usr/bin/env python3
"""Rev 2 HAT placement, board-outline and keep-out edits (KiCad bundled Python).

    $KICAD_PY tools/hat_layout.py LaserDriver.kicad_pcb

Board frame: Pi HAT template coordinates (board spans x 100..165, y 43.1..100).
The OLED bonnet (65 x 30.7 mm) covers y 44..74.7, so everything that must be
seen or touched lives below that: daughterboard area bottom-left, right-angle
Right-angle BNCs on the bottom edge; FIRE, buffers and LEDs in the band above them.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bonnet_outline  # noqa: E402

MM = pcbnew.FromMM

# ref: (x, y, rotation_deg, side)   side: "F" or "B"
PLACE = {
    # ---- under the bonnet: USB-C, power path, MCU (mostly Rev 1 positions) ----
    # USB-C moved down the left edge (y 67) with its CC resistors and the CH340; the USB power switch
    # SW10 took its old spot under MH1; the power chain J5 -> Q5 (switch) -> Q3 (ideal diode) -> +5V
    # runs north from J5 to the header's 5 V pins
    "J5": (104.25, 67.00, -90, "F"),
    "R8": (110.30, 65.50, 0, "F"),          # CC1 pull-down, above the D+/D- corridor
    "R10": (110.40, 69.05, 0, "F"),         # CC2 pull-down, below the D+/D- corridor; GND pad ties to U6 pin 3
    "U6": (115.60, 68.25, 0, "F"),          # CH340N: USB pins face J5, UART pins face the MCU
    "C6": (116.25, 71.75, 180, "F"),
    "JP4": (113.22, 73.50, 180, "F"),
    "SW10": (102.15, 56.00, -90, "F"),       # USB PWR slide switch under MH1; lever ~0.9 mm past the edge
    "Q5": (110.60, 59.60, 0, "F"),          # USB power switch FET (PDFN3333): S row south (VBUS), D north
    "R26": (113.80, 62.60, 0, "F"),          # Q5 gate pull-up (off)
    "Q3": (113.60, 55.40, 180, "F"),        # ideal-diode FET (PDFN3333): D row south (VBUS_SW), S north (+5V)
    "Q4": (117.80, 55.20, 180, "F"),        # matched PNP pair sensing VBUS_SW / +5V
    "R21": (121.20, 54.00, 0, "F"),
    "R22": (116.00, 52.60, 0, "F"),          # IDEAL_G pull-down, next to Q3 gate
    "U4": (124.00, 60.50, 90, "F"),          # 3V3 LDO, moved into the old boost area
    "C12": (120.60, 60.50, 270, "F"),        # GND pad down, toward U4 GND (locked tie)
    "C13": (127.40, 60.50, 90, "F"),
    "JP5": (128.50, 53.20, 0, "F"),          # stand-alone 3V3 jumper, near header pins 1/17
    "R19": (132.40, 53.20, 0, "F"),
    "R20": (132.40, 54.60, 0, "F"),
    "JP1": (136.50, 56.00, 180, "F"),
    "U1": (142.75, 53.50, 180, "F"),
    "R1": (137.01, 52.50, 0, "F"),
    "R2": (136.99, 54.00, 0, "F"),
    "C15": (142.52, 56.50, 0, "F"),
    "U5": (138.00, 60.50, 180, "F"),
    "R7": (135.00, 60.40, 90, "F"),
    # MCU turned 270 deg and moved SW so each side faces its destinations (tools/pinopt; see the
    # U7 pin map in rev2_migrate.py): north = I2C/NRST/power/ROSC (header), west = J8/J9/buttons,
    # south = DAC/ADC/SWD, east = BNC buffer/LED/FIRE/Pi UART/VCORE
    "U7": (134.00, 71.00, 270, "F"),
    "C1": (134.00, 66.35, 90, "F"),          # VDD decoupler, straight north of VDD/VSS (pins 4/5)
    "R4": (133.00, 66.35, 90, "F"),          # ROSC, at pin 6
    "R3": (136.60, 66.35, 90, "F"),          # NRST pull-up, NE of pin 3
    "C3": (137.70, 66.35, 90, "F"),          # NRST filter
    "C4": (138.30, 69.25, 0, "F"),           # VCORE, off pin 32 (east side)
    "C2": (138.50, 63.60, 0, "F"),           # MCU rail bulk cap, near U5 (the rail's source)
    "SW6": (162.25, 72.00, 90, "F"),
    "REF**": (147.00, 62.00, 0, "B"),         # owl logo on the bottom silkscreen
    # ---- UI controls, all reachable with the bonnet and an output module fitted ----
    "SW7": (103.80, 87.30, 90, "F"),         # BL-DT thumbwheel, wheel ~6 mm past the left edge
    "SW8": (113.80, 97.41, 180, "F"),        # BACK: right-angle PTS645, plunger past the bottom edge
    "SW9": (162.25, 89.00, 90, "F"),         # FIRE: TS-1088 like SW6, right edge between the LEDs and MH4
    # ---- daughterboard sockets (L-shape keys the module) ----
    "J8": (109.00, 78.50, None, "F"),        # pins run +x
    "J9": (125.50, 82.00, None, "F"),        # pins run +y
    # ---- BNC I/O: dual footprint - placed for the Amphenol 031-5540 / 031-5431 right angle, front face
    #      flush with the bottom edge (signal pin 12.45 mm behind it); a vertical 031-5539 fits the same
    #      holes, its body filling the (now empty) band above ----
    "J6": (135.30, 87.55, 180, "F"),         # TRIG IN, next to the module (body from x 128.05)
    "J7": (150.60, 87.55, 180, "F"),         # STIM OUT (body to x 157.85, clear of MH4; ~0.8 mm between bodies)
    "U8": (152.00, 68.00, 0, "F"),          # BNC buffers, between the MCU and STIM OUT (old owl spot)
    "C16": (152.00, 65.80, 0, "F"),
    "R23": (149.00, 70.60, 90, "F"),         # TRIG IN series
    "R24": (150.40, 70.60, 90, "F"),         # TRIG IN pull-down
    "R25": (154.60, 70.60, 90, "F"),         # STIM OUT series
    # ---- LEDs to the right of the BNCs ----
    "D5": (162.60, 77.50, 180, "F"),         # PWR
    "R13": (159.70, 77.50, 0, "F"),
    "D7": (162.60, 80.50, 180, "F"),         # MCU
    "R15": (159.70, 80.50, 0, "F"),
    "D9": (162.60, 83.50, 180, "F"),         # STIM
    "R18": (159.70, 83.50, 0, "F"),
}
# pin-1 -> pin-5 direction for the 1x5 sockets
SOCKET_DIR = {"J8": (1, 0), "J9": (0, 1)}

DAUGHTER = (101.0, 76.0, 127.5, 99.5)             # module outline (x0, y0, x1, y1)
DAUGHTER_KEEPOUT = (108.0, 80.5, 123.5, 92.5)     # no HAT footprints under the module
PI4_POE_NOTCH = (159.0, 51.0, 165.0, 59.5)        # Pi 4 PoE pins + Pi 5 fan connector
BNC_TAB = None                                    # (x0, x1, edge y) for a bottom-edge tab under the BNCs; not needed now

STALE_TEXT = {"PD", "5V", "12V", "LD", "3V3", "MSP", "STIM\nMIRROR", "TRIGGER\nIN"}


def v(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def seg(board, layer, a, b, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(v(*a))
    s.SetEnd(v(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(width))
    board.Add(s)


def rect(board, layer, r, width=0.1):
    x0, y0, x1, y1 = r
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        seg(board, layer, pts[i], pts[(i + 1) % 4], width)


def text(board, layer, s, x, y, size=1.0, rot=0, justify=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(v(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.15))
    t.SetTextAngleDegrees(rot)
    if justify == "right":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    elif justify == "left":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)
    return t


def place(board):
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    missing = set(fps) - set(PLACE) - {"J1", "MH1", "MH2", "MH3", "MH4"}   # fixed by the HAT spec
    if missing:
        raise SystemExit(f"no placement for {sorted(missing)}")
    for ref, (x, y, rot, side) in PLACE.items():
        f = fps[ref]
        want_back = side == "B"
        if f.IsFlipped() != want_back:
            f.Flip(f.GetPosition(), False)
        f.SetPosition(v(x, y))
        if ref == "REF**":                  # logo: board-only, so schematic parity ignores it
            f.SetBoardOnly(True)
        if rot is not None:
            f.SetOrientationDegrees(rot)
        else:
            dx, dy = SOCKET_DIR[ref]
            for r in (0, 90, 180, 270):
                f.SetOrientationDegrees(r)
                pads = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
                d = pads["5"] - pads["1"]
                if (d.x > 0) == (dx > 0) and (d.y > 0) == (dy > 0) and \
                        (abs(d.x) > 1000) == (dx != 0) and (abs(d.y) > 1000) == (dy != 0):
                    break           # PinSocket footprints have pin 1 at the origin


def outline(board, doomed):
    """Right edge gets the Pi 4 PoE / Pi 5 fan notch (a Pi 5 carries its cooler, so the HAT sits on a
    header extender there and needs no Pi 5 PoE cut-out); the left edge loses the template's display
    flex-cable slot (no display cable in this system) and becomes straight; the bottom edge gets a
    ~4 mm tab under the BNCs so they sit far enough south for the vertical 031-5539 option."""
    for d in board.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        a, b = d.GetStart(), d.GetEnd()
        right = a.x == b.x == MM(165.0) and d.GetShape() == pcbnew.SHAPE_T_SEGMENT
        bottom = a.y == b.y == MM(100.0) and d.GetShape() == pcbnew.SHAPE_T_SEGMENT
        slot = min(a.x, b.x) >= MM(100.0) and max(a.x, b.x) <= MM(105.0) and \
            min(a.y, b.y) >= MM(46.0) and max(a.y, b.y) <= MM(97.1) and d.GetShape() != pcbnew.SHAPE_T_ARC or \
            d.GetShape() == pcbnew.SHAPE_T_ARC and MM(63.0) <= min(a.y, b.y) and max(a.y, b.y) <= MM(81.0)
        if right or slot or bottom:
            doomed.append(d)
    seg(board, pcbnew.Edge_Cuts, (100.0, 46.12132), (100.0, 97.0), 0.05)
    if BNC_TAB:
        t0, t1, ty = BNC_TAB
        pts = [(103.0, 100.0), (t0, 100.0), (t0, ty), (t1, ty), (t1, 100.0), (162.0, 100.0)]
    else:
        pts = [(103.0, 100.0), (162.0, 100.0)]
    for i in range(len(pts) - 1):
        seg(board, pcbnew.Edge_Cuts, pts[i], pts[i + 1], 0.05)
    x0, y0, x1, y1 = PI4_POE_NOTCH
    pts = [(165.0, 97.0), (165.0, y1), (x0, y1), (x0, y0), (165.0, y0), (165.0, 46.12132)]
    for i in range(len(pts) - 1):
        seg(board, pcbnew.Edge_Cuts, pts[i], pts[i + 1], 0.05)


def keepouts_and_marks(board):
    # footprint keep-out under the daughterboard (tracks and vias still allowed)
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowFootprints(True)
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False)
    z.SetLayer(pcbnew.F_Cu)
    z.SetZoneName("DAUGHTERBOARD")
    x0, y0, x1, y1 = DAUGHTER_KEEPOUT
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(MM(x), MM(y))
    board.Add(z)
    # module outline for reference (drawings + silkscreen corner ticks)
    rect(board, pcbnew.Dwgs_User, DAUGHTER, 0.1)
    X0, Y0, X1, Y1 = DAUGHTER
    for (cx, cy, sx, sy) in ((X0, Y0, 1, 1), (X1, Y0, -1, 1), (X1, Y1, -1, -1)):
        seg(board, pcbnew.F_SilkS, (cx, cy), (cx + 2 * sx, cy), 0.15)
        seg(board, pcbnew.F_SilkS, (cx, cy), (cx, cy + 2 * sy), 0.15)
    text(board, pcbnew.F_SilkS, "OUTPUT MODULE", 116.0, 88.0, 1.0)
    text(board, pcbnew.F_SilkS, "(laser / estim)", 116.0, 89.8, 0.8)


def silkscreen(board, doomed):
    X0, Y0, X1, Y1 = DAUGHTER
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_SHAPE":
            # Rev 1 laser-diode artwork in what is now the daughterboard area
            bb = d.GetBoundingBox()
            if d.GetLayer() == pcbnew.F_SilkS and MM(X0) <= bb.GetX() and \
                    bb.GetRight() <= MM(X1) and MM(Y0) <= bb.GetY() and bb.GetBottom() <= MM(Y1):
                doomed.append(d)
            continue
        if d.GetClass() != "PCB_TEXT":
            continue
        t = d.GetText()
        if t in STALE_TEXT and d.GetLayer() == pcbnew.F_SilkS:
            doomed.append(d)
        elif t.startswith("LaserHat v1.0"):
            d.SetText("LaserHat v2.0\nKemere Lab")
            d.SetPosition(v(152.4, 54.8))
            d.SetTextSize(pcbnew.VECTOR2I(MM(1.1), MM(1.1)))
        elif t == "(c) 2026":
            d.SetPosition(v(150.5, 74.2))
            d.SetTextAngleDegrees(0)
        elif t == "BSL":                     # SW6's Rev 1 label: beside the button, clear of the LEDs
            d.SetPosition(v(159.6, 72.0))
            d.SetTextAngleDegrees(90)
    text(board, pcbnew.F_SilkS, "FIRE", 159.6, 89.0, 0.8, rot=90)
    text(board, pcbnew.F_SilkS, "PWR", 157.9, 77.5, 0.8, justify="right")
    text(board, pcbnew.F_SilkS, "MCU", 157.9, 80.5, 0.8, justify="right")
    text(board, pcbnew.F_SilkS, "STIM", 157.9, 83.5, 0.8, justify="right")
    text(board, pcbnew.F_SilkS, "TRIG IN", 135.3, 77.5, 0.8)            # above the BNC
    # USB power slide switch SW10: lever toward J5 (pin 1, PWR_EN -> GND) = ON (datasheet: knob end = closed side)
    text(board, pcbnew.F_SilkS, "ON", 105.4, 52.6, 0.8, justify="left")
    text(board, pcbnew.F_SilkS, "OFF", 105.4, 59.4, 0.8, justify="left")
    text(board, pcbnew.F_SilkS, "USB PWR", 107.0, 56.0, 0.8, rot=90)
    text(board, pcbnew.F_SilkS, "STIM OUT", 150.6, 77.5, 0.8)
    text(board, pcbnew.F_SilkS, "STANDALONE", 128.5, 51.7, 0.8)
    text(board, pcbnew.Dwgs_User, "Pi 4 PoE / Pi 5 fan", 158.5, 60.6, 0.8, justify="right")


def main(path):
    board = pcbnew.LoadBoard(path)
    # pcbnew's SWIG wrappers stop resolving types once anything has been removed
    # from the board, so every removal is deferred to the very end.
    doomed = []
    silkscreen(board, doomed)
    outline(board, doomed)
    keepouts_and_marks(board)
    bonnet_outline.draw(board)
    place(board)
    for d in doomed:
        board.Remove(d)
    pcbnew.SaveBoard(path, board)
    print("saved", path)


if __name__ == "__main__":
    main(sys.argv[1])
