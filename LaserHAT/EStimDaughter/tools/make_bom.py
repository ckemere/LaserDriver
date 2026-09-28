"""
Write bom_EStimDaughter.csv from sch_parts.py (the single source of truth), keeping per-part notes from the previous CSV.
Test points are bare pads and are left out.   Run:  micromamba run -n kicad python tools/make_bom.py
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
from sch_parts import PARTS  # noqa: E402

path = os.path.join(ROOT, "bom_EStimDaughter.csv")
notes = {}
if os.path.exists(path):
    for r in csv.DictReader(io.StringIO(open(path, newline="").read())):
        notes[r["Ref"]] = r.get("Note", "")
rows = [["Ref", "Value", "Footprint", "LCSC", "Note"]]
for p in PARTS:
    if p["sym"] == "TestPoint" or p.get("dnp"):
        continue
    rows.append([p["ref"], p["value"], p["fp"].split(":", 1)[1], p["lcsc"], notes.get(p["ref"], "")])
buf = io.StringIO()
csv.writer(buf, lineterminator="\r\n").writerows(rows)
open(path, "w", newline="").write(buf.getvalue())
print(f"wrote {path}: {len(rows) - 1} parts")
