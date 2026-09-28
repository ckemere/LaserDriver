#!/usr/bin/env python3
"""Remove unlocked GND stitching vias that sit only in floating pour fragments
(no GND pad on the fragment, not the main fragment), then refill so the
fragments disappear (zones use island removal "always").  KiCad bundled Python.

    $KICAD_PY tools/prune_stitch.py board.kicad_pcb
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
zone = next(z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea())
good = []
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    ps = zone.GetFilledPolysList(layer)
    outs = [ps.Outline(i) for i in range(ps.OutlineCount())]
    big = max(outs, key=lambda o: o.Area())
    gpads = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads()
             if p.GetNetname() == "GND" and p.IsOnLayer(layer)]
    good += [o for o in outs if o is big or any(o.PointInside(c) for c in gpads)]
doomed = [t for t in board.GetTracks()
          if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND" and not t.IsLocked()
          and not any(o.PointInside(t.GetPosition()) for o in good)]
n = len(doomed)
for t in doomed:           # removals last: pcbnew's SWIG wrappers degrade afterwards
    board.Remove(t)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(sys.argv[1], board)
print("pruned", n, "floating stitching vias")
