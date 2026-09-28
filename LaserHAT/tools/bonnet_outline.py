#!/usr/bin/env python3
"""Draw the Adafruit 128x32 OLED bonnet (product 4567) footprint on Dwgs.User.

    $KICAD_PY tools/bonnet_outline.py board.kicad_pcb        (also used by hat_layout.py)

From Adafruit's fab print: 65.0 x 30.7 mm, top edge on the Pi's top edge (HAT
y = 44), mounting holes 3.5 mm in from the corners (top pair = Pi holes).
"""
import sys

import pcbnew

MM = pcbnew.FromMM
BONNET = (100.0, 44.0, 165.0, 74.7)
HOLES = [(103.5, 47.5), (161.5, 47.5), (103.5, 71.2), (161.5, 71.2)]


def draw(board):
    layer = pcbnew.Dwgs_User
    x0, y0, x1, y1 = BONNET
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        s.SetLayer(layer)
        s.SetWidth(MM(0.15))
        board.Add(s)
    for x, y in HOLES:
        c = pcbnew.PCB_SHAPE(board)
        c.SetShape(pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(pcbnew.VECTOR2I(MM(x), MM(y)))
        c.SetEnd(pcbnew.VECTOR2I(MM(x + 1.35), MM(y)))
        c.SetLayer(layer)
        c.SetWidth(MM(0.1))
        board.Add(c)
    t = pcbnew.PCB_TEXT(board)
    t.SetText("OLED BONNET (Adafruit 4567) 65 x 30.7 mm")
    t.SetPosition(pcbnew.VECTOR2I(MM(132.5), MM(73.6)))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
    t.SetTextThickness(MM(0.15))
    board.Add(t)


if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1])
    draw(b)
    pcbnew.SaveBoard(sys.argv[1], b)
    print("bonnet outline drawn")
