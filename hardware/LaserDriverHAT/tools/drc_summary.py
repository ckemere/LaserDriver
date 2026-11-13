#!/usr/bin/env python3
"""Run DRC and print a summary: counts by type, then the placement-relevant violations with positions (mm).
    python tools/drc_summary.py [--all] [--out drc.json]"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "LaserDriverHAT.kicad_pcb")
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "drc.json")
subprocess.run([shutil.which("kicad-cli") or "kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "-o", out, BOARD],
               capture_output=True)
d = json.load(open(out))
v = [x for x in d["violations"] if x["type"] != "lib_footprint_issues"]
print(Counter((x["severity"], x["type"]) for x in v))
print("unconnected:", len(d["unconnected_items"]))
show = {"courtyards_overlap", "copper_edge_clearance", "silk_overlap", "hole_clearance", "hole_near_hole", "clearance",
        "shorting_items", "invalid_outline", "items_not_allowed", "silk_edge_clearance", "copper_sliver", "malformed_courtyard",
        "solder_mask_bridge", "silk_over_copper", "track_dangling", "via_dangling", "isolated_copper", "text_height", "text_thickness"}
if "--all" in sys.argv:
    show |= {x["type"] for x in v}
for x in v:
    if x["type"] in show and x["type"] not in ("silk_over_copper", "solder_mask_bridge") or "--all" in sys.argv:
        items = ", ".join(f"{i['description'][:45]} @({i['pos']['x']:.2f},{i['pos']['y']:.2f})" for i in x["items"][:2])
        print(f"  {x['severity'][:4]} {x['type']:22s} {x['description'][:60]:60s} {items}")
