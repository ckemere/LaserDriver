#!/usr/bin/env python3
"""Fab outputs for JLCPCB into ../fab/LaserDriverHAT/: gerbers + drill (zipped), JLC BOM (from sch_parts.py) and CPL
(from kicad-cli pos), 3D renders of both sides.  Run:  python tools/make_fab.py      (needs kicad-cli on PATH)"""
import csv
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
from sch_parts import PARTS  # noqa: E402

OUT = os.path.abspath(os.path.join(ROOT, "..", "fab", "LaserDriverHAT"))
BOARD = os.path.join(ROOT, "LaserDriverHAT.kicad_pcb")
KICAD_CLI = shutil.which("kicad-cli") or "kicad-cli"
os.makedirs(OUT, exist_ok=True)
g = os.path.join(OUT, "gerbers")
shutil.rmtree(g, ignore_errors=True); os.makedirs(g)
subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--layers", "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
                "--no-x2", "--subtract-soldermask", "-o", g + "/", BOARD], check=True, capture_output=True)
subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th",
                "--generate-map", "--map-format", "gerberx2", "-o", g + "/", BOARD], check=True, capture_output=True)
zp = os.path.join(OUT, "LaserDriverHAT_gerbers.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(g)):
        z.write(os.path.join(g, f), f)
# CPL
pos = os.path.join(OUT, "pos_kicad.csv")
subprocess.run([KICAD_CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--smd-only", "false",
                "-o", pos, BOARD], check=True, capture_output=True) if False else None
subprocess.run([KICAD_CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", pos, BOARD],
               check=True, capture_output=True)
by_ref = {p["ref"]: p for p in PARTS}
fitted = {r for r, p in by_ref.items() if p["lcsc"] and not p.get("dnp")}
# JLC's rotation convention differs from KiCad's for many packages; the same table and formula as the Fabrication Toolkit
# (bennymeg/Fabrication-Toolkit plugins/transformations.csv, copied to tools/ref/jlc_rotations.csv), which the HAT is ordered with
ROT_DB = [(re.compile(row["footprint"]), float(row["rotation"])) for row in csv.DictReader(
    open(os.path.join(HERE, "ref", "jlc_rotations.csv"), newline=""), fieldnames=["footprint", "rotation", "x", "y"])
          if row["footprint"] != "Regex To Match"]
def jlc_rotation(fpid, rot, side):
    name = fpid.split(":", 1)[1] if ":" in fpid else fpid
    if side != "top":
        rot = 180.0 - rot
    for rx, off in ROT_DB:
        if rx.search(fpid if ":" in rx.pattern else name):
            rot += off
            break
    return rot % 360.0
cpl = [["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]]
for r in csv.DictReader(open(pos, newline="")):
    ref = r["Ref"]
    if ref in fitted:
        cpl.append([ref, r["PosX"], r["PosY"], "Top" if r["Side"] == "top" else "Bottom",
                    f"{jlc_rotation(by_ref[ref]['fp'], float(r['Rot']), r['Side']):g}"])
buf = io.StringIO(); csv.writer(buf, lineterminator="\r\n").writerows(cpl)
open(os.path.join(OUT, "LaserDriverHAT_cpl.csv"), "w", newline="").write(buf.getvalue())
os.remove(pos)
# BOM grouped by LCSC code
groups = {}
for p in PARTS:
    if p["ref"] in fitted:
        groups.setdefault(p["lcsc"], [p["value"], p["fp"].split(":", 1)[1], []])[2].append(p["ref"])
bom = [["Comment", "Designator", "Footprint", "LCSC Part #"]]
for code, (val, fp, refs) in sorted(groups.items(), key=lambda kv: kv[1][2][0]):
    bom.append([val, ",".join(refs), fp, code])
buf = io.StringIO(); csv.writer(buf, lineterminator="\r\n").writerows(bom)
open(os.path.join(OUT, "LaserDriverHAT_bom.csv"), "w", newline="").write(buf.getvalue())
for side in ("top", "bottom"):                 # 3D renders, as ../tools/jlc_fab.py makes them
    subprocess.run([KICAD_CLI, "pcb", "render", "-o", os.path.join(OUT, f"LaserDriverHAT_{side}.png"), "-w", "1600", "-h", "1200",
                    "--side", side, "--background", "opaque", "--quality", "high", BOARD], check=True, capture_output=True)
not_fitted = sorted(r for r in by_ref if r not in fitted)
print(f"{OUT}: {len(cpl) - 1} placements, {len(bom) - 1} BOM lines, not in BOM/CPL: {not_fitted}")
