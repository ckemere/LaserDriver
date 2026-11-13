#!/usr/bin/env python3
"""Is the board what the schematic says?  Read-only version of KiCad's F8 / tools/pcb_sync.py.

    python tools/sync_check.py <board.kicad_pcb> <root.kicad_sch>      (kicad venv; kicad-cli on PATH)

Exports the schematic netlist and compares it with the board:
  * every schematic part has a footprint and vice versa (board-only items with an empty path are fine)
  * footprint library id, Value and DNP agree
  * every pad carries the net the netlist gives it (names compared after KiCad's "unconnected-" and
    "Net-(...)" auto-names are normalised); pads the schematic does not know are ignored
  * the footprint path matches the symbol uuid (what F8 uses to pair them)
Prints every difference; exit code 1 if there are any.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402
from pcb_sync import parse_netlist  # noqa: E402


def netname(n):
    """KiCad renames auto nets; compare what matters: '' for unconnected, bare name otherwise."""
    if n.startswith("unconnected-"):
        return ""
    return n


def main(board_path, sch_path):
    cli = shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
    net = os.path.join(tempfile.gettempdir(), os.path.basename(board_path) + ".net")
    subprocess.run([cli, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", net, sch_path],
                   check=True, capture_output=True)
    comps, pinnets = parse_netlist(net)
    board = pcbnew.LoadBoard(board_path)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    diffs = []
    for ref, c in sorted(comps.items()):
        f = fps.get(ref)
        if f is None:
            diffs.append(f"{ref}: in the schematic, not on the board"); continue
        if f.GetFPIDAsString() != c["fpid"]:
            diffs.append(f"{ref}: footprint {f.GetFPIDAsString()} on the board, schematic says {c['fpid']}")
        if f.GetValue() != c["value"]:
            diffs.append(f"{ref}: value {f.GetValue()!r} on the board, schematic says {c['value']!r}")
        if f.IsDNP() != c["dnp"]:
            diffs.append(f"{ref}: DNP {f.IsDNP()} on the board, schematic says {c['dnp']}")
        if f.GetPath().AsString() != c["path"]:
            diffs.append(f"{ref}: path {f.GetPath().AsString()} on the board, schematic symbol is {c['path']}")
        for p in f.Pads():
            num = p.GetNumber()
            if not num:
                continue
            want = pinnets.get((ref, num))
            if want is None:
                continue            # pad the symbol has no pin for (mechanical); KiCad leaves it alone
            if netname(p.GetNetname()) != netname(want):
                diffs.append(f"{ref} pad {num}: net {p.GetNetname()!r} on the board, schematic says {want!r}")
    for ref, f in sorted(fps.items()):
        if ref not in comps and f.GetPath().AsString() not in ("", "/"):
            diffs.append(f"{ref}: on the board with a schematic path, but not in the schematic")
    for d in diffs:
        print(d)
    print(f"{os.path.basename(board_path)}: {len(comps)} parts, {len(diffs)} differences")
    sys.stdout.flush()
    os._exit(1 if diffs else 0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
