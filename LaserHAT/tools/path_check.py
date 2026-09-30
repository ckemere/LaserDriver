#!/usr/bin/env python3
"""Check that every footprint's KIID path matches its schematic symbol (what KiCad's F8 uses).

    python tools/path_check.py <board.kicad_pcb> <root.kicad_sch>      (kicad venv: pcbnew + kiutils)

Walks the sheet hierarchy from the root schematic.  KiCad writes a footprint's path as
"/<symbol uuid>" for a root-sheet symbol and "/<sheet uuid>/.../<symbol uuid>" for one on a
sub-sheet (the root sheet's own uuid never appears); a multi-unit symbol may carry any of its
units' uuids.  A mismatch means "Update PCB from Schematic" would delete that footprint and
add a fresh one, losing its placement.  Exit code 1 if anything is off.
"""
import os
import sys

import pcbnew
from kiutils.schematic import Schematic


def walk(sch_path, prefix, out):
    sch = Schematic.from_file(sch_path)
    for s in sch.schematicSymbols:
        ref = next((p.value for p in s.properties if p.key == "Reference"), None)
        if ref and not ref.startswith("#"):
            out.setdefault(ref, set()).add(prefix + "/" + s.uuid)
    for sh in sch.sheets:
        fn = sh.fileName.value if sh.fileName else None
        if fn:
            walk(os.path.join(os.path.dirname(sch_path), fn), prefix + "/" + sh.uuid, out)


def main(board_path, sch_path):
    expect = {}
    walk(sch_path, "", expect)
    board = pcbnew.LoadBoard(board_path)
    bad, boardonly = [], []
    for f in board.GetFootprints():
        ref, path = f.GetReference(), f.GetPath().AsString()
        if ref not in expect:
            if path:
                boardonly.append(ref)
            continue
        if path not in expect[ref]:
            bad.append((ref, path, sorted(expect[ref])))
    missing = sorted(r for r in expect if not board.FindFootprintByReference(r))
    for ref, got, want in sorted(bad):
        print(f"MISMATCH {ref}: board {got}  schematic {' | '.join(want)}")
    if boardonly:
        print("on the board with a path but not in the schematic:", sorted(boardonly))
    if missing:
        print("in the schematic but not on the board:", missing)
    print(f"{os.path.basename(board_path)}: {len(expect)} symbols, {len(bad)} path mismatches")
    sys.stdout.flush()
    os._exit(1 if bad or boardonly or missing else 0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
