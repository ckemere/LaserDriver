#!/usr/bin/env python3
"""Stamp the board footprints from sch_parts.py so a BOM/CPL made from the PCB (e.g. with the Fabrication Toolkit) carries
the part numbers: an "LCSC Part #" field (hidden, F.Fab) on every part with a code, the Value synced to sch_parts, and the
mounting holes excluded from the BOM and position files.  Idempotent.      $KICAD_PY tools/stamp_fields.py"""
import os
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
from sch_parts import BY_REF  # noqa: E402

FIELD = "LCSC Part #"
BOARD = os.path.join(ROOT, "LaserDriverHAT.kicad_pcb")
board = pcbnew.LoadBoard(BOARD)
changed = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    p = BY_REF.get(ref)
    if p is None:                           # board-only graphics (the owl logo G1): no part, nothing to stamp
        if not (fp.IsExcludedFromBOM() and fp.IsExcludedFromPosFiles()):
            fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True); changed.append(ref)
        if ref == "G1":                     # the owl's exposed-copper eyes are GND (a netlist sync clears nets of symbol-less footprints)
            gnd = board.FindNet("GND")
            for pad in fp.Pads():
                if pad.GetNetname() != "GND":
                    pad.SetNet(gnd); changed.append(ref)
        continue
    if fp.GetValue() != p["value"]:
        fp.SetValue(p["value"]); changed.append(ref)
    if p["lcsc"]:
        f = fp.GetFieldByName(FIELD)
        if f is None or f.GetText() != p["lcsc"]:
            fp.SetField(FIELD, p["lcsc"])
            f = fp.GetFieldByName(FIELD)
            f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
            changed.append(ref)
        dnp = bool(p.get("dnp"))
        if fp.IsExcludedFromBOM() or fp.IsExcludedFromPosFiles() != dnp:      # DNP parts stay out of the CPL whatever exports it
            fp.SetExcludedFromBOM(False); fp.SetExcludedFromPosFiles(dnp); changed.append(ref)
        if fp.IsDNP() != dnp:
            fp.SetDNP(dnp); changed.append(ref)
    else:                                   # hand-fitted / mounting holes: no part, and no stale code left behind
        if not (fp.IsExcludedFromBOM() and fp.IsExcludedFromPosFiles()):
            fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True); changed.append(ref)
        f = fp.GetFieldByName(FIELD)
        if f is not None and f.GetText():
            try:
                fp.RemoveField(FIELD)
            except Exception:
                f.SetText("")
            changed.append(ref)
if changed:
    pcbnew.SaveBoard(BOARD, board)
print(f"stamped {len(set(changed))} footprints: {sorted(set(changed))}")
