#!/usr/bin/env python3
"""Write the net classes, class patterns and board constraints into DCDCPod.kicad_pro (kicad-cli's DRC reads them from
the project file, not from the board).  Idempotent.      python tools/project_settings.py"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
from sch_parts import ISOLATED_NETS  # noqa: E402

PRO = os.path.join(ROOT, "DCDCPod.kicad_pro")


def cls(name, clearance, width, via, drill):
    return {"bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": name, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "priority": 2147483647, "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": width, "via_diameter": via,
            "via_drill": drill, "wire_width": 6}


d = json.load(open(PRO))
d["meta"]["filename"] = "DCDCPod.kicad_pro"
ns = d["net_settings"]
ns["classes"] = [cls("Default", 0.15, 0.3, 0.6, 0.3), cls("Iso", 0.15, 0.3, 0.6, 0.3)]
ns["netclass_patterns"] = [{"netclass": "Iso", "pattern": p} for n in sorted(ISOLATED_NETS) for p in (n, "/" + n)]
ns.pop("netclass_assignments", None)
r = d["board"]["design_settings"]["rules"]
r.update({"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
          "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3, "min_text_height": 0.8,
          "min_text_thickness": 0.08, "min_silk_clearance": 0.0, "min_via_annular_width": 0.1})
d["board"]["design_settings"]["drc_exclusions"] = []
d["boards"] = []
d["sheets"] = []
d.setdefault("text_variables", {})
json.dump(d, open(PRO, "w"), indent=2)
print("wrote", PRO, "classes", [c["name"] for c in ns["classes"]], "patterns", len(ns["netclass_patterns"]))
