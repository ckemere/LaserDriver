#!/usr/bin/env python3
"""Hand-planned, locked pre-routes for the connections Freerouting keeps failing on: the MCU's south-east escape, the
HAT strip of the tab, and the tab's isolated part (five nets through the 5 mm corridor west of MH4, then around the
battery socket J102 to the electrode header J101 and PS1's pins 4-6: the socket's and PS1's pin orders are mirrored,
so +V_RAW / -V_RAW / GND_ISO must cross each other on alternate layers - the router only solves that by luck).
Runs after tools/fanout.py in the autoroute pipeline; coordinates in board mm.  The router connects to the free ends.
    $KICAD_PY tools/preroute.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
mm = pcbnew.FromMM

# net -> (segments [(layer, width, [points])], vias [(x, y)])
ROUTES = {
    # U7.21 -> its fan-out via, down between the south-row vias, east under U7's south side, north along x 28.3
    # (between the R101-103 column and C16/C4) to R107.2
    "SDA_H": ([("B.Cu", 0.15, [(20.25, 29.31), (20.25, 30.4)]),
               ("B.Cu", 0.2, [(20.25, 30.4), (28.3, 30.4), (28.3, 17.2)]),
               ("F.Cu", 0.2, [(28.3, 17.2), (27.5, 17.79)])],
              [(28.3, 17.2)]),
    # C1 (100 nF at U7's VDD, pin 4) straight down between the far fan-out vias into pin 4's via
    "MSPM0_3V3": ([("F.Cu", 0.2, [(20.1, 21.1), (20.1, 22.4), (20.25, 22.69)])], []),
    # the bottom LED's cathode to its resistor: boxed in by its neighbours at the board edge
    "Net-(D5-K)": ([("F.Cu", 0.2, [(1.81, 31.5), (1.81, 32.3), (5.29, 32.3), (5.29, 31.5)])], []),
    "Net-(D7-K)": ([("F.Cu", 0.2, [(1.81, 33.1), (1.81, 33.9), (5.29, 33.9), (5.29, 33.1)])], []),
    "Net-(D9-K)": ([("F.Cu", 0.2, [(1.81, 34.7), (1.81, 35.5), (5.29, 35.5), (5.29, 34.7)])], []),
    # +5V to the tab's HAT strip: from the power LED's anode down the west edge (nothing else fits through the core),
    # under the joystick's south corner, then on the back under the BNC bodies along y 52.5 to the passage east of J7,
    # down the passage (>= 2.5 mm from strip B's pads at x >= 50.1) to C104 and PS1.1 ...
    "+5V": ([("F.Cu", 0.3, [(3.39, 31.5), (3.39, 30.4), (0.7, 30.4), (0.7, 49.8), (4.3, 49.8), (5.3, 50.3), (7.0, 51.9),
                            (8.5, 52.5)]),
             # ... and from the LED's anode north: between the USB-C's shell pegs, under its body, past SW10, below
             # J1's lower row and up between J1's columns 4 and 6 to J1.4 (the router never joined the two halves)
             ("F.Cu", 0.3, [(3.39, 30.4), (5.0, 30.4), (5.0, 28.6), (5.0, 19.0), (5.4, 18.6), (5.4, 8.9), (5.7, 8.6),
                            (11.88, 8.6), (12.18, 8.3)]),
             ("B.Cu", 0.3, [(12.18, 8.3), (12.18, 1.59), (10.91, 1.59)]),           # J1's pads are SMD on the back
             ("B.Cu", 0.3, [(8.5, 52.5), (46.0, 52.5)]),
             ("F.Cu", 0.3, [(46.0, 52.5), (46.5, 52.5), (46.5, 66.28), (47.5, 66.28), (47.3, 67.2), (47.3, 68.2)])],
            [(12.18, 8.3), (8.5, 52.5), (46.0, 52.5)]),
    # +5V_ISO: U101.16 (VCC2) from its fan-out via up and along y 20.6 (just inside the barrier) to U109.8 (VCC2);
    # C102.1 to U105.1 (DAC VDD) and on to U109.8; C115.1 through a via and up the back along x 38.3 to the same via
    "+5V_ISO": ([("F.Cu", 0.3, [(38.9, 24.78), (38.9, 21.1), (39.4, 20.6), (43.3, 20.6), (43.91, 21.2), (43.91, 21.98)]),
                 ("F.Cu", 0.3, [(40.5, 24.78), (41.11, 24.19), (41.3, 24.0), (42.1, 24.0)]),          # C102.1 - U105.1
                 ("F.Cu", 0.2, [(41.11, 24.19), (41.08, 24.25), (41.08, 25.75), (41.3, 26.0), (42.1, 26.0)]),  # - U105.5
                 ("F.Cu", 0.3, [(40.5, 27.28), (40.82, 27.28), (42.1, 26.0)]),                       # C124.1 - U105.5
                 # C124.1 through a via, down the back and west to the lane along x 38.3 (U101's fan-out vias wall off
                 # the front between y 24.5 and 29.5); C115.1 through a via onto the same lane
                 ("F.Cu", 0.3, [(40.5, 27.28), (40.5, 27.9), (40.2, 28.2), (40.2, 28.6)]),
                 ("B.Cu", 0.3, [(40.2, 28.6), (40.2, 30.2), (38.9, 31.5), (38.3, 31.5)]),
                 ("F.Cu", 0.3, [(37.5, 32.28), (37.5, 33.9), (37.9, 34.3)]),
                 ("B.Cu", 0.3, [(37.9, 34.3), (38.3, 33.9), (38.3, 25.38), (38.9, 24.78)])],
                [(40.2, 28.6), (37.9, 34.3)]),
    # E1 (electrode node) from U110.6 up the lane between C116 and U107, along y 20.2 above U107 to C121.1
    # E1 (electrode node): U110.6 east above the R117-R120 row, then up the east side of U107 on the back
    # (the channel west of U107 is the only way into its pins 9-15 and must stay free) to a via at C121.1
    "E1": ([("F.Cu", 0.2, [(54.41, 32.33), (55.45, 32.33), (55.45, 31.75), (55.65, 31.55), (60.7, 31.55), (60.9, 31.35),
                           (60.9, 31.0)]),
            ("B.Cu", 0.2, [(60.9, 31.0), (60.9, 22.4), (60.8, 22.3)]),
            ("F.Cu", 0.2, [(60.8, 22.3), (61.55, 21.5)])],
           [(60.9, 31.0), (60.8, 22.3)]),
    # GND from J7's ground leg on the back, up through a via to C104.2 and on to PS1.2
    "GND": ([("B.Cu", 0.3, [(43.48, 49.48), (45.4, 49.48), (47.15, 51.2), (47.15, 63.3)]),
             ("F.Cu", 0.3, [(47.15, 63.3), (47.5, 64.72), (48.6, 65.6), (49.84, 66.9), (49.84, 68.2)]),
             # link the four thermal vias in U7's pad on the back so all stay connected
             ("B.Cu", 0.3, [(19.3, 25.3), (20.7, 25.3), (20.7, 26.7), (19.3, 26.7), (19.3, 25.3)])],
            [(47.15, 63.3)]),
    # tab, isolated part.  Corridor west of MH4 (x 53.2-58, y 49-57), on the back west -> east: +V_RAW 53.55 (from
    # L101.1 through a via), -V_RAW 54.2 (from L102.1 through a via, west along y 48.5), GND_ISO 54.9 (via up to
    # C110.1 / C108.1), E1_OUT 55.6 (from C121.2 down the east edge on the front, west along y 48.9, via at the
    # corridor), ISENSE 56.2 (from TP101 through a via, down the east edge on the back and along y 49.4).  -V_RAW
    # comes back to the front at y 53.3 for the tab.  Around J102 to PS1 4-6 (mirrored pin order: the three supply
    # nets cross on alternate layers) and to J101; ISENSE ends on the front above J101.1.
    "+V_RAW": ([("F.Cu", 0.3, [(50.64, 43.0), (50.64, 44.3)]),                                       # L101.1
                ("B.Cu", 0.3, [(50.64, 44.3), (50.64, 52.0), (51.6, 53.0), (53.55, 53.0), (53.55, 59.5), (54.5, 60.0)]),
                ("F.Cu", 0.3, [(54.5, 60.0), (54.5, 63.76), (57.44, 66.7), (58.5, 66.7), (60.0, 68.2)])],  # PS1.6
               [(50.64, 44.3)]),
    "-V_RAW": ([("F.Cu", 0.3, [(58.04, 43.0), (58.04, 43.75), (57.6, 44.2), (57.6, 44.5)]),             # L102.1
                ("B.Cu", 0.3, [(57.6, 44.5), (57.6, 48.5), (54.2, 48.5), (54.2, 53.3)]),
                ("F.Cu", 0.3, [(54.2, 53.3), (53.6, 53.95), (53.6, 66.83), (54.92, 68.2)]),             # PS1.4
                ("F.Cu", 0.3, [(53.6, 58.79), (56.88, 58.79), (57.95, 59.86), (58.5, 60.0)])],          # J102.3
               [(57.6, 44.5), (54.2, 53.3)]),
    "GND_ISO": ([("F.Cu", 0.3, [(54.6, 51.95), (56.8, 51.95)]),                                     # C110.1 - C108.1
                 ("F.Cu", 0.3, [(54.6, 51.95), (54.6, 52.5), (54.9, 52.9), (54.9, 53.6)]),
                 ("B.Cu", 0.3, [(54.9, 53.6), (54.9, 57.9), (56.2, 59.5), (56.5, 60.0)]),            # J102.2
                 ("B.Cu", 0.3, [(56.5, 60.0), (56.8, 60.9), (56.8, 67.54), (57.46, 68.2)]),          # PS1.5
                 ("B.Cu", 0.3, [(56.8, 61.2), (59.3, 61.2), (60.5, 60.0)]),                           # J102.4
                 ("F.Cu", 0.3, [(61.75, 43.0), (61.75, 43.9), (63.3, 45.45), (63.3, 48.05), (64.0, 48.05)]),  # C106.1 - D104.1
                 ("F.Cu", 0.3, [(56.5, 46.05), (56.5, 44.6), (56.35, 44.45), (56.35, 43.0)]),          # C107.2 - C105.2
                 ("F.Cu", 0.3, [(40.09, 21.98), (40.09, 23.41), (40.5, 23.82)])],                     # U109.5 - C102.2
                [(54.9, 53.6)]),
    "/E1_OUT": ([("F.Cu", 0.2, [(63.45, 21.5), (64.5, 22.55), (64.5, 48.5), (64.1, 48.9), (58.4, 48.9), (58.0, 49.3),
                                (58.0, 52.6), (57.7, 52.9), (56.0, 52.9), (55.6, 53.0)]),             # C121.2 ->
                 ("B.Cu", 0.2, [(55.6, 53.0), (55.6, 57.6), (62.2, 57.6), (62.2, 63.0), (60.5, 65.5)])],   # J101.1
                [(55.6, 53.0)]),
    "ISENSE": ([("F.Cu", 0.2, [(48.69, 24.68), (47.5, 24.68), (47.5, 30.0), (58.0, 30.0), (58.3, 29.7), (58.3, 29.45),
                               (60.6, 29.45), (61.2, 28.85), (61.2, 27.9), (61.8, 27.3), (62.5, 27.0)]),  # U106.2 - TP101
                ("F.Cu", 0.2, [(62.5, 27.0), (62.5, 28.3)]),                                           # TP101
                ("B.Cu", 0.2, [(62.5, 28.3), (64.0, 29.8), (64.0, 49.0), (63.6, 49.4), (56.2, 49.4), (56.2, 57.2),
                               (63.0, 57.2), (63.0, 63.9)]),
                ("F.Cu", 0.2, [(63.0, 63.9), (62.3, 64.3), (58.3, 64.3), (57.96, 65.5)])],            # J101.2
               [(62.5, 28.3), (63.0, 63.9)]),
}


def run(board):
    n = 0
    for net, (segs, vias) in ROUTES.items():
        code = board.GetNetcodeFromNetname(net)
        assert code > 0, net
        for layer, w, pts in segs:
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
                t.SetWidth(mm(w)); t.SetLayer(board.GetLayerID(layer)); t.SetNetCode(code); t.SetLocked(True)
                board.Add(t); n += 1
        for x, y in vias:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNetCode(code); v.SetLocked(True)
            board.Add(v); n += 1
    return n


if __name__ == "__main__":
    b = pcbnew.LoadBoard(BOARD)
    print("pre-routed items:", run(b))
    pcbnew.SaveBoard(BOARD, b)
