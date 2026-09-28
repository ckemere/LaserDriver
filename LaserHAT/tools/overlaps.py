#!/usr/bin/env python3
"""List footprint courtyard overlaps and pads too close to the board edge (KiCad bundled Python).

    $KICAD_PY tools/overlaps.py board.kicad_pcb
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
bb = board.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = (pcbnew.ToMM(v) for v in (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
boxes = {}
for f in board.GetFootprints():
    side = pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd
    c = f.GetCourtyard(side)
    if c.OutlineCount():
        b = c.BBox()
        boxes[f.GetReference()] = ("B" if f.IsFlipped() else "F",
                                   [pcbnew.ToMM(v) for v in (b.GetX(), b.GetY(), b.GetRight(), b.GetBottom())],
                                   f.GetFPIDAsString())
    for p in f.Pads():
        pb = p.GetBoundingBox()
        e = min(pcbnew.ToMM(pb.GetX()) - X0, X1 - pcbnew.ToMM(pb.GetRight()),
                pcbnew.ToMM(pb.GetY()) - Y0, Y1 - pcbnew.ToMM(pb.GetBottom()))
        if e < 0.5:
            print(f"edge: {f.GetReference()}.{p.GetNumber()} {e:.2f} mm from the board edge")
refs = sorted(boxes)
for i, a in enumerate(refs):
    for b in refs[i + 1:]:
        sa, A, fa = boxes[a]
        sb, B, fb = boxes[b]
        if sa != sb:
            continue
        ox = min(A[2], B[2]) - max(A[0], B[0])
        oy = min(A[3], B[3]) - max(A[1], B[1])
        if ox > 0 and oy > 0:
            print(f"overlap: {a} x {b}  ({ox:.2f} x {oy:.2f} mm)")
print("footprints:", {r: (v[2].split(':')[1][:28], [round(c, 2) for c in v[1]]) for r, v in boxes.items() if r in ("J4", "J5", "J2", "Q1", "Q2", "U3", "C12")})
