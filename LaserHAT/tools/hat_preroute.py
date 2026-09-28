#!/usr/bin/env python3
"""Hand-routed, locked copper for the HAT's high-current 5 V path (KiCad bundled Python).

    $KICAD_PY tools/hat_preroute.py LaserDriver.kicad_pcb

USB-C VBUS -> Q3 (ideal-diode PFET) -> Pi 5 V pins 2/4.  Up to 3 A flows here
when USB-C powers the Pi, so it is routed by hand at 0.6-0.8 mm rather than left
to the autorouter; the +5 V branch reuses Rev 1's B.Cu channel between the
header's pin holes.  Everything is locked so freerouting routes around it.
"""
import sys

import pcbnew

MM = pcbnew.FromMM

# (layer, net, width_mm, [points...])
TRACKS = [
    ("B.Cu", "+5V", 0.8, [(108.37, 44.59), (110.91, 44.59)]),            # Pi pins 2-4
    ("B.Cu", "+5V", 0.6, [(110.91, 44.59), (112.20, 45.88), (112.20, 51.55)]),
    # USB power chain (J5 at y 67 on the left edge): VBUS -> Q5 (switch) -> VBUS_SW -> Q3 (ideal diode) -> +5V
    ("F.Cu", "/USB-C UART/VBUS", 0.6, [(107.97, 64.60), (108.90, 64.60), (109.62, 63.88), (109.62, 61.13)]),  # A4/B9 -> Q5 S
    ("F.Cu", "/USB-C UART/VBUS", 0.4, [(109.62, 61.13), (110.93, 61.13)]),              # Q5 S row
    ("F.Cu", "/USB-C UART/VBUS", 0.6, [(107.97, 69.40), (108.90, 69.40), (109.30, 69.85)]),  # A9/B4 -> B.Cu jumper
    ("B.Cu", "/USB-C UART/VBUS", 0.6, [(109.30, 69.85), (109.26, 64.24)]),
    ("F.Cu", "/USB-C UART/VBUS_SW", 0.6, [(111.58, 58.07), (112.62, 56.93)]),            # Q5 D -> Q3 D
    ("F.Cu", "/USB-C UART/VBUS_SW", 0.4, [(114.58, 56.93), (115.40, 56.93), (116.18, 56.15), (116.66, 56.15)]),  # -> Q4 E1
    ("F.Cu", "+5V", 0.4, [(113.27, 53.87), (114.58, 53.87)]),                           # Q3 S row
    ("F.Cu", "+5V", 0.6, [(114.58, 53.87), (114.58, 53.10), (113.13, 51.65), (112.20, 51.55)]),  # -> header via
    # USB-C CC pull-downs R8/R10 either side of the D+/D- corridor to U6
    ("F.Cu", "GND", 0.3, [(110.81, 65.50), (111.60, 65.55)]),               # R8 GND -> via
    ("F.Cu", "GND", 0.3, [(110.91, 69.05), (112.35, 68.89)]),               # R10 GND -> U6 pin 3 (GND)
    # J5's GND pin pairs (A1/B12, A12/B1) are boxed in by the VBUS jumper: tie each to its shield pad
    ("F.Cu", "GND", 0.3, [(107.80, 63.80), (107.80, 62.68)]),
    ("F.Cu", "GND", 0.3, [(107.80, 70.20), (107.80, 71.32)]),
    # Pi header pin 25 (GND, bottom-side SMD pad) gets its own via; the autorouter tends to box it in
    ("B.Cu", "GND", 0.3, [(138.85, 50.41), (138.85, 52.00)]),
    # load switch U5's ground pad: its own via, east of the pad (the autorouter tends to box it in)
    ("F.Cu", "GND", 0.3, [(139.14, 60.50), (140.75, 60.50)]),
    # LDO input cap C12: its ground pad goes straight to U4's ground pad
    ("F.Cu", "GND", 0.3, [(120.60, 60.98), (121.80, 62.18), (122.50, 62.18)]),
]
# (net, x, y[, diameter, drill])
VIAS = [("+5V", 112.20, 51.55),
        ("/USB-C UART/VBUS", 109.26, 64.24), ("/USB-C UART/VBUS", 109.30, 69.85),
        ("GND", 111.60, 65.55, 0.6, 0.3),
        ("GND", 138.85, 52.00, 0.6, 0.3),
        ("GND", 140.75, 60.50, 0.6, 0.3)]


def main(path):
    board = pcbnew.LoadBoard(path)
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    for layer, net, w, pts in TRACKS:
        n = board.FindNet(net)
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
            t.SetWidth(MM(w))
            t.SetLayer(layers[layer])
            t.SetNet(n)
            t.SetLocked(True)
            board.Add(t)
    for net, x, y, *size in VIAS:
        d, drill = size or (0.8, 0.4)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(d))
        v.SetDrill(MM(drill))
        v.SetNet(board.FindNet(net))
        v.SetLocked(True)
        board.Add(v)
    pcbnew.SaveBoard(path, board)
    print("pre-routed", len(TRACKS), "paths")


if __name__ == "__main__":
    main(sys.argv[1])
