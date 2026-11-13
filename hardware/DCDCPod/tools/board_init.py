#!/usr/bin/env python3
"""Create DCDCPod.kicad_pcb (once): design rules, net classes, then pull every footprint in from the netlist.
    $KICAD_PY tools/board_init.py      (refuses to overwrite an existing board)
Then: tools/place.py (placement, outline, barrier, silk), tools/route.py (tracks), tools/project_settings.py,
tools/fresh_uuids.py, tools/stamp_fields.py, tools/drc_summary.py."""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
from sch_parts import ISOLATED_NETS  # noqa: E402

BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
NET = os.path.join(ROOT, "tools", "ref", "DCDCPod.net")

if os.path.exists(BOARD):
    sys.exit("board exists; delete it first if you really want to start over")
b = pcbnew.BOARD()
ds = b.GetDesignSettings()
ds.m_TrackMinWidth = pcbnew.FromMM(0.15)
ds.m_ViasMinSize = pcbnew.FromMM(0.5)
ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
ds.m_MinClearance = pcbnew.FromMM(0.15)
ds.m_HoleClearance = pcbnew.FromMM(0.25)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
ds.SetBoardThickness(pcbnew.FromMM(1.6))            # 1.6 mm (tools/place.py sets it too; was 1.2 until the pod was turned around, 2026-10-30)
ns = ds.m_NetSettings
dc = ns.GetDefaultNetclass()
dc.SetClearance(pcbnew.FromMM(0.15)); dc.SetTrackWidth(pcbnew.FromMM(0.3))
dc.SetViaDiameter(pcbnew.FromMM(0.6)); dc.SetViaDrill(pcbnew.FromMM(0.3))
iso = pcbnew.NETCLASS("Iso")                       # same geometry; the class carries the isolation rules (DCDCPod.kicad_dru)
iso.SetClearance(pcbnew.FromMM(0.15)); iso.SetTrackWidth(pcbnew.FromMM(0.3))
iso.SetViaDiameter(pcbnew.FromMM(0.6)); iso.SetViaDrill(pcbnew.FromMM(0.3))
ns.SetNetclass("Iso", iso)
for n in sorted(ISOLATED_NETS):
    ns.SetNetclassPatternAssignment(n, "Iso")
    ns.SetNetclassPatternAssignment("/" + n, "Iso")      # local-label spelling
pcbnew.SaveBoard(BOARD, b)
print("wrote", BOARD)
sys.path.insert(0, HERE)
from pcb_sync import sync  # noqa: E402
sync(BOARD, NET)
