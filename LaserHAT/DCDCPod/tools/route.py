#!/usr/bin/env python3
"""Scripted routing of DCDCPod.kicad_pcb: rips every track and via, then lays the tracks below (0.3 mm, F.Cu unless
noted; no vias).  Points are pad names "REF.PAD" (resolved to the pad centre on the current board) or (x, y) in mm;
consecutive points are joined by straight segments.  Channels: x 1.2 (+V_OUT) west of C105 / PS1 pin 6; x 6.1 (0V)
between L101 and C106; x 8.85 (-V_OUT) between C106 / L102 and between PS1 pins 5 and 4; the +V_F / -V_F buses at
y 4.6 through the top pads of the bottom row.  Re-run tools/place.py first if the placement changed.
    $KICAD_PY tools/route.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
mm = pcbnew.FromMM
WIDTH = 0.3
F, B = "F", "B"

ROUTES = [
    # ---- isolated side, front
    (F, "L101.1", (4.9, 12.8), "PS1.6"),                                  # +V_RAW
    (F, "L102.1", (10.1, 12.8), "PS1.4"),                                 # -V_RAW
    (F, "C105.1", (4.9, 4.6)),                                            # +V_F bus into L101.2
    (F, "Q101.3", (3.1375, 4.6)),
    (F, "R111.1", (4.75, 4.6)),
    (F, "C106.2", (12.9, 4.6), "Q102.3"),                                 # -V_F bus through L102.2, up between Q102's B / E
    (F, "R112.2", (10.15, 4.6)),
    (F, "Q101.1", "C107.1"),                                              # QB_P bus through R111.2
    (F, "C108.2", (11.0, 1.0), (11.0, 2.9875), "Q102.1"),                 # QB_N bus through R112.1
    (F, "C107.2", "C108.1"),                                              # 0V, top row
    (F, "C107.2", (6.1, 3.2), (6.1, 7.25), (7.58, 7.25), "PS1.5"),        # 0V down the 6.1 channel to PS1's COM
    (F, (7.3, 7.25), "C106.1"),
    (F, "PS1.5", (7.58, 14.2), (2.4, 14.2), "C105.2"),                    # 0V to C105 and J2.3
    (F, (4.0, 14.2), "J2.3"),
    (F, "Q101.2", (1.2, 2.9), (1.2, 15.9), "J2.4"),                       # +V_OUT down the west edge
    (F, "Q102.2", (13.85, 5.55), (8.85, 5.55), (8.85, 14.75), (6.0, 14.75), "J2.2"),   # -V_OUT down the 8.85 channel
    # ---- 5 V side, front
    (F, "J1.1", (27.0, 10.025), "C104.1", (20.9, 10.025), (20.9, 12.8), "PS1.1"),
    (F, "J1.2", (24.46, 11.575), "C104.2"),
    (F, (24.46, 14.4), (15.2, 14.4), "PS1.2"),
    # ---- back: CAB strap and the test points
    (B, "J2.3", (4.0, 17.6), (8.0, 17.6), "J2.1"),
    (B, (6.0, 17.6), "TP2.1"),
    (B, "J2.4", "TP1.1"),
    (B, "J2.2", (6.0, 14.6), (10.5, 14.6), "TP3.1"),
]

board = pcbnew.LoadBoard(BOARD)
# read everything first, mutate afterwards (pcbnew's wrappers degrade once the board is edited)
PADS = {}
for f in board.GetFootprints():
    for p in f.Pads():
        PADS[f"{f.GetReference()}.{p.GetNumber()}"] = ((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6), p.GetNetCode(),
                                                      p.GetBoundingBox().GetLeft() / 1e6, p.GetBoundingBox().GetRight() / 1e6,
                                                      p.GetBoundingBox().GetTop() / 1e6, p.GetBoundingBox().GetBottom() / 1e6,
                                                      p.IsOnLayer(pcbnew.F_Cu), p.IsOnLayer(pcbnew.B_Cu))
old = list(board.GetTracks())
laid = []                                                   # (a, b, layer, net) laid so far, for net_at()


def resolve(spec):
    if isinstance(spec, str):
        return PADS[spec][0], PADS[spec][1]
    return (spec[0], spec[1]), None


def net_at(pt, layer):
    """net of the pad or already laid track at a point (for routes that start on a bare point)"""
    for pos, net, x1, x2, y1, y2, onf, onb in PADS.values():
        if (onf if layer == pcbnew.F_Cu else onb) and x1 <= pt[0] <= x2 and y1 <= pt[1] <= y2:
            return net
    for a, b, lay, net in laid:
        if lay != layer:
            continue
        if a == pt or b == pt:
            return net
        if a[0] == b[0] == pt[0] and min(a[1], b[1]) <= pt[1] <= max(a[1], b[1]):
            return net
        if a[1] == b[1] == pt[1] and min(a[0], b[0]) <= pt[0] <= max(a[0], b[0]):
            return net
    raise SystemExit(f"no net at {pt}")


segments = []
for layer_c, *specs in ROUTES:
    layer = pcbnew.F_Cu if layer_c == F else pcbnew.B_Cu
    pts = [resolve(s) for s in specs]
    nets = {nc for _, nc in pts if nc is not None}
    assert len(nets) <= 1, f"route joins different nets: {specs}"
    net = nets.pop() if nets else net_at(pts[0][0], layer)
    for (a, _), (b, _) in zip(pts, pts[1:]):
        if a != b:
            segments.append((a, b, layer, net))
            laid.append((a, b, layer, net))
for t in old:
    board.Remove(t)
for a, b, layer, net in segments:
    tr = pcbnew.PCB_TRACK(board)
    tr.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); tr.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
    tr.SetWidth(mm(WIDTH)); tr.SetLayer(layer); tr.SetNetCode(net)
    board.Add(tr)
pcbnew.SaveBoard(BOARD, board)
print("laid", len(segments), "track segments (ripped", len(old), "); saved", BOARD)
