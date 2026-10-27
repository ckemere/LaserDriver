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
BOARD = os.path.join(ROOT, "BatteryPack.kicad_pcb")
board = pcbnew.LoadBoard(BOARD)
changed = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    p = BY_REF[ref]
    if fp.GetValue() != p["value"]:
        fp.SetValue(p["value"]); changed.append(ref)
    if p["lcsc"]:
        f = fp.GetFieldByName(FIELD)
        if f is None or f.GetText() != p["lcsc"]:
            fp.SetField(FIELD, p["lcsc"])
            f = fp.GetFieldByName(FIELD)
            f.SetVisible(False); f.SetLayer(pcbnew.F_Fab)
            changed.append(ref)
        if fp.IsExcludedFromBOM() or fp.IsExcludedFromPosFiles():
            fp.SetExcludedFromBOM(False); fp.SetExcludedFromPosFiles(False); changed.append(ref)
        if fp.IsDNP() != bool(p.get("dnp")):
            fp.SetDNP(bool(p.get("dnp"))); changed.append(ref)
    else:                                   # mounting holes: no part
        if not (fp.IsExcludedFromBOM() and fp.IsExcludedFromPosFiles()):
            fp.SetExcludedFromBOM(True); fp.SetExcludedFromPosFiles(True); changed.append(ref)
if changed:
    pcbnew.SaveBoard(BOARD, board)
print(f"stamped {len(set(changed))} footprints: {sorted(set(changed))}")
