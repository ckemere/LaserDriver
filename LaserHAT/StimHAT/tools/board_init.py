#!/usr/bin/env python3
"""Create StimHAT.kicad_pcb (once): design rules, netclasses, then pull every footprint in from the netlist.
    $KICAD_PY tools/board_init.py      (refuses to overwrite an existing board)
Footprints that live only on the Rev 2 HAT board (its project library) are copied from ../LaserDriver.kicad_pcb."""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
from sch_parts import ISOLATED_NETS  # noqa: E402

BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
NET = os.path.join(ROOT, "tools", "ref", "StimHAT.net")
HAT = os.path.join(ROOT, "..", "LaserDriver.kicad_pcb")
POWER = ["+5V", "+3V3", "+3V3_PI", "MSPM0_3V3", "VBUS", "VBUS_SW", "GND",
         "+V_RAW", "-V_RAW", "+V_F", "-V_F", "+V_STIM", "-V_STIM", "+5V_ISO", "GND_ISO"]
FINE = ["USB_DP", "USB_DM", "CC1", "CC2"]

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
ns = ds.m_NetSettings
dc = ns.GetDefaultNetclass()
dc.SetClearance(pcbnew.FromMM(0.15)); dc.SetTrackWidth(pcbnew.FromMM(0.25))
dc.SetViaDiameter(pcbnew.FromMM(0.6)); dc.SetViaDrill(pcbnew.FromMM(0.3))
pw = pcbnew.NETCLASS("Power")
pw.SetClearance(pcbnew.FromMM(0.2)); pw.SetTrackWidth(pcbnew.FromMM(0.5))
pw.SetViaDiameter(pcbnew.FromMM(0.8)); pw.SetViaDrill(pcbnew.FromMM(0.4))
ns.SetNetclass("Power", pw)
fn = pcbnew.NETCLASS("Fine")
fn.SetClearance(pcbnew.FromMM(0.15)); fn.SetTrackWidth(pcbnew.FromMM(0.2))
fn.SetViaDiameter(pcbnew.FromMM(0.6)); fn.SetViaDrill(pcbnew.FromMM(0.3))
ns.SetNetclass("Fine", fn)
iso = pcbnew.NETCLASS("Isolated")                      # same geometry as Default; the netclass carries the barrier rule
iso.SetClearance(pcbnew.FromMM(0.15)); iso.SetTrackWidth(pcbnew.FromMM(0.25))
iso.SetViaDiameter(pcbnew.FromMM(0.6)); iso.SetViaDrill(pcbnew.FromMM(0.3))
ns.SetNetclass("Isolated", iso)
isop = pcbnew.NETCLASS("IsolatedPower")
isop.SetClearance(pcbnew.FromMM(0.2)); isop.SetTrackWidth(pcbnew.FromMM(0.5))
isop.SetViaDiameter(pcbnew.FromMM(0.8)); isop.SetViaDrill(pcbnew.FromMM(0.4))
ns.SetNetclass("IsolatedPower", isop)
for n in POWER:
    ns.SetNetclassPatternAssignment(n, "IsolatedPower" if n in ISOLATED_NETS else "Power")
for n in FINE:
    ns.SetNetclassPatternAssignment(n, "Fine")
for n in sorted(ISOLATED_NETS):
    if n not in POWER:
        ns.SetNetclassPatternAssignment(n, "Isolated")
        ns.SetNetclassPatternAssignment("/" + n, "Isolated")      # local-label spelling
pcbnew.SaveBoard(BOARD, b)
print("wrote", BOARD)
sys.path.insert(0, HERE)
from pcb_sync import sync  # noqa: E402
sync(BOARD, NET, src_paths=[HAT])
