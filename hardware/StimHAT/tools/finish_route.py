#!/usr/bin/env python3
"""Post-Freerouting housekeeping on StimHAT.kicad_pcb, each step in its own pcbnew process:
  1. widen any track narrower than the board minimum (Freerouting's neck-downs) to its net class width
  2. route whatever the DRC still lists as unconnected with ../../tools/maze_route.py (export, route, import)
  3. report
    $KICAD_PY tools/finish_route.py [--no-maze]"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
PRO = os.path.join(ROOT, "StimHAT.kicad_pro")
TOOLS = os.path.abspath(os.path.join(ROOT, "..", "tools"))
WORK = os.path.join(ROOT, "route")
KICAD_CLI = shutil.which("kicad-cli") or "kicad-cli"
mm = pcbnew.FromMM


def widen():
    board = pcbnew.LoadBoard(BOARD)
    import fnmatch
    ns = json.load(open(PRO))["net_settings"]
    widths = {c["name"]: c["track_width"] for c in ns["classes"]}
    pats = [(p["pattern"], p["netclass"]) for p in ns.get("netclass_patterns", [])]

    def width(net):
        for pat, cls in pats:
            if fnmatch.fnmatchcase(net, pat):
                return widths[cls]
        return widths["Default"]
    n = 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < mm(0.15):
            t.SetWidth(mm(width(t.GetNetname()))); n += 1
    pcbnew.SaveBoard(BOARD, board)
    return n


def drc_report():
    rpt = os.path.join(WORK, "drc_finish.rpt")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--severity-all", "--format", "report", "-o", rpt, BOARD], capture_output=True)
    return rpt


if __name__ == "__main__" and "--widen" in sys.argv:
    print("widened", widen(), "tracks"); sys.exit(0)

if __name__ == "__main__":
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--widen"], capture_output=True, text=True)
    print([l for l in r.stdout.splitlines() if "widened" in l])
    if "--no-maze" not in sys.argv:
        rpt = drc_report()
        out, routes = os.path.join(WORK, "maze_in.json"), os.path.join(WORK, "maze_out.json")
        subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "export", BOARD, rpt, out], check=True)
        r = subprocess.run(["python3", os.path.join(TOOLS, "maze_route.py"), out, routes], capture_output=True, text=True)
        print(r.stdout[-1500:], r.stderr[-500:])
        if os.path.exists(routes):
            subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "import", BOARD, routes], check=True)
    subprocess.run(["python3", os.path.join(ROOT, "tools", "drc_summary.py")])
