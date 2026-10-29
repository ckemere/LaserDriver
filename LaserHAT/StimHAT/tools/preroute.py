#!/usr/bin/env python3
"""Hand-planned, locked pre-routes for the connections Freerouting keeps failing on (the MCU's south-east escape).
Runs after tools/fanout.py in the autoroute pipeline; coordinates in board mm.
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
