#!/usr/bin/env python3
"""Add a two-layer GND pour covering the board outline (KiCad bundled Python)."""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
bb = board.GetBoardEdgesBoundingBox()
z = pcbnew.ZONE(board)
ls = pcbnew.LSET()
ls.AddLayer(pcbnew.F_Cu)
ls.AddLayer(pcbnew.B_Cu)
z.SetLayerSet(ls)
z.SetNet(board.FindNet("GND"))
z.SetZoneName("GND Plane")
z.SetLocalClearance(pcbnew.FromMM(0.25))
z.SetMinThickness(pcbnew.FromMM(0.25))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
ol = z.Outline()
ol.NewOutline()
for x, y in ((bb.GetX(), bb.GetY()), (bb.GetRight(), bb.GetY()),
             (bb.GetRight(), bb.GetBottom()), (bb.GetX(), bb.GetBottom())):
    ol.Append(x, y)
board.Add(z)
pcbnew.SaveBoard(sys.argv[1], board)
print("GND pour added")
