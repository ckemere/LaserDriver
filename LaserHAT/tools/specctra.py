#!/usr/bin/env python3
"""DSN export / SES import for freerouting (KiCad bundled Python).

    $KICAD_PY tools/specctra.py export board.kicad_pcb out.dsn
    $KICAD_PY tools/specctra.py import board.kicad_pcb in.ses

KiCad writes every rule area to the DSN as a routing keep-out, even ones that
only forbid footprints (the daughterboard area).  Those are stripped after
export so the router may run tracks under the module.
"""
import os
import re
import sys

import pcbnew

cmd, board_path, other = sys.argv[1:4]
board = pcbnew.LoadBoard(board_path)
if cmd == "export":
    footprint_only = []
    for z in board.Zones():
        if z.GetIsRuleArea() and not z.GetDoNotAllowTracks():
            bb = z.GetBoundingBox()
            footprint_only.append((round(pcbnew.ToMM(bb.GetX()) * 1000),
                                   round(-pcbnew.ToMM(bb.GetY()) * 1000)))
    ok = pcbnew.ExportSpecctraDSN(board, other)
    if ok:
        txt = open(other).read()
        # ROUTE_GND=1: don't declare the ground pour as a plane, so freerouting routes
        # GND as an ordinary net (guaranteed connectivity, but much more congestion).
        # By default the plane stays and tools/fix_islands.py mops up afterwards.
        if os.environ.get("ROUTE_GND"):
            txt, n = re.subn(r'\n\s*\(plane GND \(polygon [^)]*\)\)', "", txt)
            print("stripped", n, "GND plane(s)")
        # Bias the router toward F.Cu so B.Cu stays a mostly unbroken ground pour
        # (freerouting reads per-layer trace costs from an autoroute_settings block).
        settings = """
    (autoroute_settings
      (fanout off) (autoroute on) (postroute on) (vias on)
      (via_costs 30) (plane_via_costs 5) (start_ripup_costs 100)
      (layer_rule F.Cu (active on) (preferred_direction horizontal)
        (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 1.3))
      (layer_rule B.Cu (active on) (preferred_direction vertical)
        (preferred_direction_trace_costs 3.0) (against_preferred_direction_trace_costs 4.0))
    )"""
        txt = re.sub(r"(\n\s*\(boundary)", settings.replace("\\", "\\\\") + r"\1", txt, count=1)   # after the layer defs
        for x, y in footprint_only:
            # (keepout "" (polygon F.Cu 0  x y ...))
            txt, n = re.subn(r'\n\s*\(keepout "[^"]*" \(polygon \S+ 0\s+%d %d[^)]*\)\s*\)' % (x, y), "", txt)
            print("stripped", n, "footprint-only keep-out(s)")
        open(other, "w").write(txt)
else:
    ok = pcbnew.ImportSpecctraSES(board, other)
    if ok:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(board_path, board)
print(cmd, "ok" if ok else "FAILED")
