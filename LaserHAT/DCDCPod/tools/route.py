#!/usr/bin/env python3
"""Scripted routing of DCDCPod.kicad_pcb: rips every track and via, then lays the tracks below (0.3 mm, F.Cu unless
noted; no vias: the THT pads of PS1 and J2 are the only layer changes).  Points are pad names "REF.PAD" (resolved to the
pad centre on the current board) or (x, y) in mm; consecutive points are joined by straight segments.
Layout since 2026-10-30 (pod facing south, PS1 at the top): +5V / GND straight down x 3.6 / 6.14 from PS1's pins
to J1 with C104 between them; +V_RAW east along y 1.3 under PS1's body to L101; -V_RAW straight down x 11.22 to L102;
front 0V from PS1.5 straight down x 13.76 to C106 and east along y 4.0 under the body to the positive block (C105,
C107), which drops it to J2.3 down x 27; the -V_F bus along y 10.6 under L102 / C106; C108's 0V goes along y 17.0 to
J2.1; -V_OUT from Q102 down x 17.65, east along y 15.8 and down x 25 to J2.2; +V_OUT down the east edge (x 30.3) to
J2.4.  Back: PS1.5 -> TP2 -> J2.1 (0V: joins the two front 0V pieces), the CAB strap J2.1 -> J2.3 below J2.2, and the
TP1 / TP3 links.  Both filter ripple loops (PS1.4 / 6 -> L -> C -> PS1.5) are on the front and short.  Re-run tools/place.py first if the placement
changed.
    $KICAD_PY tools/route.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
mm = pcbnew.FromMM
WIDTH = 0.3
F, B = "F", "B"

ROUTES = [
    # ---- 5 V side, front
    (F, "PS1.1", (3.6, 17.4), "J1.1"),                                    # +5V
    (F, (3.6, 7.6), "C104.1"),
    (F, "PS1.2", (6.14, 17.4), "J1.2"),                                   # GND
    (F, (6.14, 7.6), "C104.2"),
    # ---- isolated side, front: raw rails and filters
    (F, "PS1.6", "L101.1"),                                               # +V_RAW, y 1.3 under PS1's body
    (F, "PS1.4", "L102.1"),                                               # -V_RAW, x 11.22
    (F, "L101.2", (25.0, 1.3), "C105.1"),                                 # +V_F down x 25
    (F, "Q101.3", (25.0, 2.25)),
    (F, "R111.1", (26.34, 4.85), "C105.1"),
    (F, "L102.2", (11.22, 10.6), (16.7, 10.6), "Q102.3"),                 # -V_F bus y 10.6
    (F, "C106.2", (13.76, 10.6)),
    (F, "R112.2", (13.9, 10.6)),
    # ---- multiplier bases
    (F, "Q101.1", (28.337, 5.5), "R111.2"),                               # QB_P
    (F, (28.337, 5.5), (29.0, 5.5), "C107.1"),
    (F, "R112.1", "C108.2"),                                              # QB_N
    (F, "Q102.1", (15.75, 13.2), (13.9, 13.2)),
    # ---- 0V, front
    (F, "PS1.5", (13.76, 4.0), "C106.1"),                                 # converter COM to C106
    (F, (13.76, 4.0), (23.6, 4.0), (23.6, 6.75), "C105.2"),               # ... and to the positive block
    (F, "C105.2", (25.0, 9.65), (27.0, 9.65), "J2.3"),
    (F, "C107.2", (29.0, 9.65), (27.0, 9.65)),
    (F, "C108.1", (13.9, 17.0), (23.0, 17.0), "J2.1"),                    # C108 to J2.1
    # ---- outputs
    (F, "Q102.2", (17.65, 15.8), (25.0, 15.8), "J2.2"),                   # -V_OUT
    (F, "Q101.2", (30.3, 1.3), (30.3, 17.6), "J2.4"),                     # +V_OUT down the east edge
    # ---- back: converter 0V to J2.1 via TP2, the CAB strap, the test points
    (B, "PS1.5", (13.76, 15.5), "TP2.1", (23.0, 17.5), "J2.1"),
    (B, "J2.1", (23.0, 20.6), (27.0, 20.6), "J2.3"),
    (B, "J2.2", "TP3.1"),
    (B, "J2.4", "TP1.1"),
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
