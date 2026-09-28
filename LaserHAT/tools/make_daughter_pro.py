#!/usr/bin/env python3
"""Write LaserDaughter.kicad_pro from the HAT project (same rules, laser net classes)."""
import copy
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = json.load(open(os.path.join(HERE, "LaserDriver.kicad_pro")))
d = copy.deepcopy(p)
d["meta"]["filename"] = "LaserDaughter.kicad_pro"
d["sheets"] = [["212bfd25-f831-4b85-926b-000000000002", "Root"]]
d["boards"] = []
d["net_settings"]["netclass_patterns"] = (
    [{"netclass": "Power", "pattern": n} for n in ("LASER_V", "+12V", "GND", "/SW", "/LaserDrive", "/IDrive")]
    + [{"netclass": "Power_5V", "pattern": "+5V"}])
for c in d["net_settings"]["classes"]:      # small board: 0.6/0.3 vias everywhere
    c["via_diameter"], c["via_drill"] = 0.6, 0.3
json.dump(d, open(os.path.join(HERE, "LaserDaughter", "LaserDaughter.kicad_pro"), "w"), indent=2)
print("wrote LaserDaughter.kicad_pro")
