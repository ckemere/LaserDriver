#!/usr/bin/env python3
"""Write the net classes, class patterns and board constraints into LaserDriverHAT.kicad_pro (kicad-cli's DRC reads them
from the project file, not from the board).  Idempotent.      python tools/project_settings.py
(The StimHAT's Isolated / IsolatedPower / Rails classes are gone with the e-stim half; one GND.)
Power1A = the HAT core's supplies (+5V, VBUS, VBUS_SW, +3V3, MSPM0_3V3, as on the StimHAT) and the laser current's whole
path (5 V -> 12 V supply, diode / dummy branches, sink), sized for 1 A (about 300 mA expected): 0.5 mm, vias 0.8 / 0.4 (as the laser
module's Power class); LaserDriverHAT.kicad_dru enforces >= 0.5 mm on outer and >= 1.0 mm on inner layers for it.  Close
KiCad first: it rewrites the .kicad_pro from memory when it saves."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PRO = os.path.join(ROOT, "LaserDriverHAT.kicad_pro")
POWER = ["GND"]
POWER_1A = ["+5V", "VBUS", "VBUS_SW", "+3V3", "MSPM0_3V3", "+3V3_PI",  # the HAT core's supplies (as on the StimHAT), then
            "+12V", "/SW", "LASER_V",                                # USB / Pi 5 V -> MT3608 boost -> 12 V -> SW5 -> laser,
            "/LD_CATHODE", "/DUMMY_TOP", "/DUMMY_MID", "/DUMMY_BOT",  # then the diode or the dummy load -> Q1 steering pair
            "/LaserDrive", "/IDrive"]                                 # -> Q2 sink -> Rs1 -> GND (up to ~340 mA at DAC 3.3 V)
FINE = ["USB_DP", "USB_DM", "CC1", "CC2"]


def cls(name, clearance, width, via, drill):
    return {"bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": name, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "priority": 2147483647, "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": width, "via_diameter": via,
            "via_drill": drill, "wire_width": 6}


d = json.load(open(PRO))
d["meta"]["filename"] = "LaserDriverHAT.kicad_pro"
ns = d["net_settings"]
ns["classes"] = [cls("Default", 0.15, 0.2, 0.6, 0.3), cls("Power", 0.15, 0.3, 0.6, 0.3), cls("Power1A", 0.15, 0.5, 0.8, 0.4),
                 cls("Fine", 0.15, 0.2, 0.6, 0.3)]
pats = ([{"netclass": "Power", "pattern": n} for n in POWER] + [{"netclass": "Power1A", "pattern": n} for n in POWER_1A] +
        [{"netclass": "Fine", "pattern": n} for n in FINE])
ns["netclass_patterns"] = pats
ns.pop("netclass_assignments", None)
r = d["board"]["design_settings"]["rules"]
r.update({"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
          "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3, "min_text_height": 0.8,
          "min_text_thickness": 0.08, "min_silk_clearance": 0.0, "min_via_annular_width": 0.1})
d["board"]["design_settings"]["rule_severities"] = d["board"]["design_settings"].get("rule_severities", {})
json.dump(d, open(PRO, "w"), indent=2)
print("wrote", PRO, "classes", [c["name"] for c in ns["classes"]], "patterns", len(pats))
