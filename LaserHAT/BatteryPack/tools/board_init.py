#!/usr/bin/env python3
"""Create BatteryPack.kicad_pcb (once): design rules, netclasses, then pull every footprint in from the netlist.
    $KICAD_PY tools/board_init.py      (refuses to overwrite an existing board)"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BOARD = os.path.join(ROOT, "BatteryPack.kicad_pcb")
NET = os.path.join(ROOT, "tools", "ref", "BatteryPack.net")
POWER = ["+BAT", "GND", "/C1", "/C2", "/C3", "CGND", "VBUS", "/SW", "Net-(D7-A)", "/CSP", "Net-(R25-Pad2)", "+RUN", "+SW", "+OUT",
         "/OUT_GND", "/LINK_N", "+CHG"]     # board net names: local labels carry a "/" prefix

if os.path.exists(BOARD):
    sys.exit("board exists; delete it first if you really want to start over")
b = pcbnew.BOARD()
ds = b.GetDesignSettings()
ds.m_TrackMinWidth = pcbnew.FromMM(0.2)
ds.m_ViasMinSize = pcbnew.FromMM(0.6)
ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
ds.m_MinClearance = pcbnew.FromMM(0.2)
ds.m_HoleClearance = pcbnew.FromMM(0.25)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
ns = ds.m_NetSettings
dc = ns.GetDefaultNetclass()
dc.SetClearance(pcbnew.FromMM(0.2)); dc.SetTrackWidth(pcbnew.FromMM(0.3))
dc.SetViaDiameter(pcbnew.FromMM(0.7)); dc.SetViaDrill(pcbnew.FromMM(0.35))
pw = pcbnew.NETCLASS("Power")
pw.SetClearance(pcbnew.FromMM(0.25)); pw.SetTrackWidth(pcbnew.FromMM(0.8))
pw.SetViaDiameter(pcbnew.FromMM(0.9)); pw.SetViaDrill(pcbnew.FromMM(0.45))
ns.SetNetclass("Power", pw)
for n in POWER:
    ns.SetNetclassPatternAssignment(n, "Power")
pcbnew.SaveBoard(BOARD, b)
print("wrote", BOARD)
sys.path.insert(0, HERE)
from pcb_sync import sync  # noqa: E402
sync(BOARD, NET)
