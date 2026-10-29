#!/usr/bin/env python3
"""fixups.py maze, restricted to the given nets:  $KICAD_PY tools/maze_nets.py NET [NET ...]
(exports the DRC's open connections, keeps only those of the named nets, runs ../tools/maze_route.py, imports)"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew  # noqa: E402
from fixups import BOARD, TOOLS, WORK, drc  # noqa: E402

nets = set(sys.argv[1:])
rpt = drc("report")
src, routes = os.path.join(WORK, "maze_in.json"), os.path.join(WORK, "maze_out.json")
subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "export", BOARD, rpt, src], check=True)
d = json.load(open(src))
before = len(d["requests"])
d["requests"] = [r for r in d["requests"] if r and r[0].get("net") in nets]
b = pcbnew.LoadBoard(BOARD)
n = 0
for z in b.Zones():
    if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
        o = z.Outline().Outline(0)
        pts = [(o.CPoint(i).x / 1e6, o.CPoint(i).y / 1e6) for i in range(o.PointCount())]
        for i in range(len(pts)):
            a, c = pts[i], pts[(i + 1) % len(pts)]
            d["edges"].append([list(a), list(c)]); n += 1
print("requests:", before, "->", len(d["requests"]), "for", sorted(nets), "; barrier edges:", n)
json.dump(d, open(src, "w"))
if os.path.exists(routes):
    os.remove(routes)
r = subprocess.run(["python3", os.path.join(TOOLS, "maze_route.py"), src, routes], capture_output=True, text=True)
print(r.stdout[-1500:], r.stderr[-400:])
if os.path.exists(routes):
    subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "import", BOARD, routes], check=True)
