#!/usr/bin/env python3
"""Make an empty board that keeps a real board's setup (KiCad bundled Python).

    $KICAD_PY tools/blank_board.py template.kicad_pcb out.kicad_pcb

A bare pcbnew.BOARD() lacks the setup/stackup a KiCad-saved board carries, and
kicad-cli's DRC then pairs pads of different nets as "unconnected".  Copying a
real board and deleting its contents avoids that.
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
doomed = list(board.GetFootprints()) + list(board.GetTracks()) + list(board.Zones()) + \
    list(board.GetDrawings())
for item in doomed:            # all removals together, nothing else afterwards (SWIG)
    board.Remove(item)
pcbnew.SaveBoard(sys.argv[2], board)
print("blank board", sys.argv[2])
