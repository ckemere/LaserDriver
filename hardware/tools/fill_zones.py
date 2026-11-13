#!/usr/bin/env python3
"""Refill all copper zones (KiCad bundled Python):  $KICAD_PY tools/fill_zones.py board.kicad_pcb

Pour pieces that touch nothing are always removed, so floating copper never
shows up as an unconnected ground island.
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
for z in board.Zones():
    if not z.GetIsRuleArea():
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(sys.argv[1], board)
print("filled", sys.argv[1])
