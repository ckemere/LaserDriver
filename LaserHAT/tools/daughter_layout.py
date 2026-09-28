#!/usr/bin/env python3
"""Laser daughterboard outline + placement (KiCad bundled Python).

    $KICAD_PY tools/daughter_layout.py LaserDaughter/LaserDaughter.kicad_pcb

Uses the HAT's coordinate frame so the headers line up by construction:
J1 pin k sits over HAT J8 pin k (109 + 2.54(k-1), 78.5) and J3 pin k over
HAT J9 pin k (125.5, 82 + 2.54(k-1)).  Headers are male, on the underside.
"""
import sys

import pcbnew

MM = pcbnew.FromMM
OUTLINE = (101.0, 76.0, 127.5, 99.5)
J8_PIN1, J9_PIN1 = (109.0, 78.5), (125.5, 82.0)

# ref: (x, y, rot, side)
PLACE = {
    "J1": (J8_PIN1[0], J8_PIN1[1], None, "B"),
    "J3": (J9_PIN1[0], J9_PIN1[1], None, "B"),
    # ---- boost (MT3608): C8 -> L1 -> SW -> D1 -> C9 loop kept to a few mm ----
    "L1": (104.00, 80.00, 0, "F"),           # pad1 +5V left, pad2 SW right
    "U2": (109.00, 81.20, 0, "F"),           # pin1 SW sits against L1's SW pad
    "D1": (105.60, 84.60, 90, "F"),          # anode (SW) up under L1, cathode (+12V) down
    "C8": (102.40, 84.80, -90, "F"),         # input cap straight under L1's +5V pad
    "R6": (109.00, 83.55, 0, "F"),           # FB divider right under U2's FB pin
    "R5": (109.00, 84.60, 180, "F"),         # FB pad left, in line with R6.1 / U2 FB
    "C9": (104.00, 88.50, 180, "F"),         # output cap under D1: pad1 (+12V) right below D1 cathode
    "SW5": (104.00, 94.80, -90, "F"),        # 5 V / 12 V, actuator over the left edge
    # ---- LD socket and 4-terminal jumper ----
    "J2": (108.40, 91.70, 0, "F"),           # 1 anode, 2 cathode / 3 PD-K, 4 PD-A
    "J4": (108.40, 97.80, 90, "F"),          # solder jumper right under PD-K (J2.3)
    # ---- current sink: J2.2 -> Q1 -> Q2 -> Rs1 -> GND, op-amp between gate and sense ----
    "Q1": (116.10, 92.60, 0, "F"),
    "Q2": (121.60, 91.60, 90, "F"),          # SOT-223, tab up (drain), pour under it
    "Rs1": (121.00, 97.60, 180, "F"),        # IDrive pad right (under Q2.3/TP1), GND pad left
    "U3": (115.40, 97.40, 0, "F"),
    "C12": (118.08, 97.05, 270, "F"),        # V+ bypass in the U3/Rs1 gap: +5V pad up, level with U3.5
    "TP1": (125.90, 97.40, 0, "F"),
    "R3": (112.50, 97.60, 270, "F"),         # DAC pad up (open side), IREF pad in line with U3 +
    "R4": (110.30, 97.60, 90, "F"),          # IREF -> GND
    "C11": (111.40, 97.60, 90, "F"),         # IREF filter
    # ---- dummy load: LASER_V -> D3 -> D2 -> D4 (J5 = RED shunt across D4) -> Q1.6 ----
    "D2": (115.60, 81.60, 180, "F"),         # K right (from D3), A left, dropping to D4.K
    "D4": (115.80, 85.20, 0, "F"),           # K left under D2.A, A right toward Q1.6
    "D3": (110.00, 87.20, 180, "F"),         # anode (LASER_V) left toward J2.1, cathode right
    "J5": (114.35, 88.60, 90, "F"),          # RED shunt (2.00 mm) right under D4, between D3 and Q2
    # ---- photodiode load and compliance divider, next to J3 ----
    "R12": (121.20, 80.40, 0, "F"),
    "R11": (121.20, 81.50, 180, "F"),        # ADC pad faces J3, PD pad joins R12.1
    "R1": (121.20, 83.20, 0, "F"),
    "R2": (121.20, 84.30, 0, "F"),
}
SOCKET_DIR = {"J1": (1, 0), "J3": (0, 1)}


def v(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def seg(board, layer, a, b, w=0.05):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(v(*a))
    s.SetEnd(v(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def text(board, layer, s, x, y, size=1.0, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(v(x, y))
    t.SetTextAngleDegrees(angle)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.15))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


ANCHORED = {"J1", "J3", "SW5", "L1", "U2", "D1", "C8", "C9", "J2", "J4",
            "C11", "R4", "R3", "C12", "U3", "Rs1", "Q2", "TP1", "J5", "D3", "D4", "D2", "Q1"}


def legalize(board, fps, gap=0.05, rounds=60):
    """Nudge non-anchored top-side parts apart until no courtyards overlap."""
    x0, y0, x1, y1 = OUTLINE
    top = {r: f for r, f in fps.items() if not f.IsFlipped()}

    def box(f):
        b = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
        return [pcbnew.ToMM(b.GetX()), pcbnew.ToMM(b.GetY()), pcbnew.ToMM(b.GetRight()), pcbnew.ToMM(b.GetBottom())]
    for _ in range(rounds):
        moved = False
        refs = sorted(top)
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                A, B = box(top[a]), box(top[b])
                ox = min(A[2], B[2]) - max(A[0], B[0])
                oy = min(A[3], B[3]) - max(A[1], B[1])
                if ox <= 0 or oy <= 0:
                    continue
                mover = b if a in ANCHORED or (b not in ANCHORED and b > a) else a
                if mover in ANCHORED:
                    continue
                other = a if mover == b else b
                M, O = box(top[mover]), box(top[other])
                if ox < oy:
                    d = (ox + gap) * (1 if (M[0] + M[2]) > (O[0] + O[2]) else -1)
                    if M[0] + d < x0 + 0.2 or M[2] + d > x1 - 0.2:     # stay on the board
                        d = -d
                    top[mover].Move(pcbnew.VECTOR2I(pcbnew.FromMM(d), 0))
                else:
                    d = (oy + gap) * (1 if (M[1] + M[3]) > (O[1] + O[3]) else -1)
                    if M[1] + d < y0 + 0.2 or M[3] + d > y1 - 0.2:
                        d = -d
                    top[mover].Move(pcbnew.VECTOR2I(0, pcbnew.FromMM(d)))
                moved = True
        if not moved:
            return
    print("legalize: overlaps remain after", rounds, "rounds")


def main(path):
    board = pcbnew.LoadBoard(path)
    x0, y0, x1, y1 = OUTLINE
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        seg(board, pcbnew.Edge_Cuts, pts[i], pts[(i + 1) % 4])
    text(board, pcbnew.F_SilkS, "LASER MODULE v2.0", 118.0, 76.95, 0.8)
    text(board, pcbnew.F_SilkS, "5V", 102.2, 90.0, 0.8)
    text(board, pcbnew.F_SilkS, "12V", 106.05, 98.55, 0.8)
    text(board, pcbnew.F_SilkS, "RED", 114.35, 90.65, 0.8)     # under J5 (RED shunt)
    text(board, pcbnew.B_SilkS, "HAT J8", 114.0, 80.6, 0.8)
    text(board, pcbnew.B_SilkS, "HAT J9", 122.9, 87.0, 0.8, 90)

    fps = {f.GetReference(): f for f in board.GetFootprints()}
    missing = set(fps) - set(PLACE)
    if missing:
        raise SystemExit(f"no placement for {sorted(missing)}")
    for ref, (x, y, rot, side) in PLACE.items():
        f = fps[ref]
        if f.IsFlipped() != (side == "B"):
            f.Flip(f.GetPosition(), False)
        f.SetPosition(v(x, y))
        if rot is not None:
            f.SetOrientationDegrees(rot)
            continue
        dx, dy = SOCKET_DIR[ref]
        for r in (0, 90, 180, 270):
            f.SetOrientationDegrees(r)
            pads = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
            d = pads["5"] - pads["1"]
            if (d.x > 0) == (dx > 0) and (d.y > 0) == (dy > 0) and \
                    (abs(d.x) > 1000) == (dx != 0) and (abs(d.y) > 1000) == (dy != 0):
                break
        p1 = {p.GetNumber(): p.GetPosition() for p in f.Pads()}["1"]
        f.SetPosition(f.GetPosition() + (v(x, y) - p1))     # pin 1 exactly over the HAT pin 1
    legalize(board, fps)
    pcbnew.SaveBoard(path, board)
    for ref in ("J1", "J3"):
        pads = sorted((p.GetNumber(), pcbnew.ToMM(p.GetPosition())) for p in fps[ref].Pads())
        print(ref, [(n, round(a, 2), round(b, 2)) for n, (a, b) in pads])


if __name__ == "__main__":
    main(sys.argv[1])
