#!/usr/bin/env python3
"""Prove the pod's isolation gap and the schematic <-> board links, independent of the DRC rules:
  1. geometry: the smallest distance between any copper (pads, tracks, vias, on any layer) of an isolated net and any
     copper of a 5 V-side net, by shape (binary search on SHAPE.Collide), must be >= 2.5 mm; prints the closest pair
  2. regions: every isolated copper item lies inside iso_region, every 5 V-side item inside hat_region, nothing inside
     the barrier rule area
  3. negative DRC test: a copy of the project with an isolated-net track dropped into the 5 V region must fail DRC
     (shows DCDCPod.kicad_dru is really being applied)
  4. footprint paths: each footprint's path is "/<root uuid>/<symbol uuid>" of its symbol in tools/ref/DCDCPod.net
  5. connector geometry: the header pins' x positions mapped to HAT coordinates (HAT x = 46 - pod x)
    $KICAD_PY tools/check_isolation.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
from sch_parts import ISOLATED_NETS  # noqa: E402

BOARD = os.path.join(ROOT, "DCDCPod.kicad_pcb")
KICAD_CLI = shutil.which("kicad-cli") or "kicad-cli"
ok = True
board = pcbnew.LoadBoard(BOARD)
layers = [pcbnew.F_Cu, pcbnew.B_Cu]


def is_iso(net):
    return net.lstrip("/") in ISOLATED_NETS


items = []        # (description, netname, layer, shape, bbox)
for f in board.GetFootprints():
    for p in f.Pads():
        if not p.GetNetname():
            continue
        for lay in layers:
            if p.IsOnLayer(lay):
                items.append((f"{f.GetReference()}.{p.GetNumber()}", p.GetNetname(), lay, p.GetEffectiveShape(lay), p.GetBoundingBox()))
for t in board.GetTracks():
    lays = layers if t.GetClass() == "PCB_VIA" else [t.GetLayer()]
    for lay in lays:
        items.append((f"{t.GetClass()}@({t.GetStart().x / 1e6:.2f},{t.GetStart().y / 1e6:.2f})", t.GetNetname(), lay,
                      t.GetEffectiveShape(lay), t.GetBoundingBox()))
iso = [i for i in items if is_iso(i[1])]
hat = [i for i in items if not is_iso(i[1])]


def distance(a, b):
    """shape-to-shape distance in mm by bisection on Collide(clearance), 0.005 mm resolution"""
    lo, hi = 0.0, 10.0
    if not a.Collide(b, pcbnew.FromMM(hi)):
        return hi
    while hi - lo > 0.005:
        mid = (lo + hi) / 2
        if a.Collide(b, pcbnew.FromMM(mid)):
            hi = mid
        else:
            lo = mid
    return hi


best = (99.0, None, None)
for a in iso:
    for b in hat:
        if a[2] != b[2]:
            pass                                           # different layers: the 1.2 mm board is between, but count it anyway
        d = distance(a[3], b[3])
        if d < best[0]:
            best = (d, a, b)
print(f"1. smallest isolated <-> 5 V copper distance: {best[0]:.3f} mm  ({best[1][0]} [{best[1][1]}] vs {best[2][0]} [{best[2][1]}])")
if best[0] < 2.5:
    ok = False; print("   FAIL: < 2.5 mm")

# 2. regions
zones = {z.GetZoneName(): z for z in board.Zones() if z.GetIsRuleArea()}
for name in ("barrier", "iso_region", "hat_region"):
    assert name in zones, f"rule area {name} missing"


def inside(zone, bbox):
    o = zone.Outline()
    pts = [pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetTop()), pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetTop()),
           pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetBottom()), pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetBottom())]
    return all(o.Contains(p) for p in pts)


def touches(zone, bbox):
    o = zone.Outline()
    pts = [pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetTop()), pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetTop()),
           pcbnew.VECTOR2I(bbox.GetLeft(), bbox.GetBottom()), pcbnew.VECTOR2I(bbox.GetRight(), bbox.GetBottom()),
           pcbnew.VECTOR2I(bbox.GetCenter().x, bbox.GetCenter().y)]
    return any(o.Contains(p) for p in pts)


bad = [i[0] for i in iso if not inside(zones["iso_region"], i[4])] + [i[0] for i in hat if not inside(zones["hat_region"], i[4])]
bad += [i[0] for i in items if touches(zones["barrier"], i[4])]
print(f"2. copper outside its region or in the barrier: {bad or 'none'}  ({len(iso)} isolated items, {len(hat)} 5 V-side items)")
if bad:
    ok = False

# 3. negative DRC test
tmp = tempfile.mkdtemp(prefix="pod_drc_")
for ext in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
    shutil.copy(os.path.join(ROOT, "DCDCPod" + ext), tmp)
tb = pcbnew.LoadBoard(os.path.join(tmp, "DCDCPod.kicad_pcb"))
tr = pcbnew.PCB_TRACK(tb)
tr.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(25.0), pcbnew.FromMM(2.0))); tr.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(26.0), pcbnew.FromMM(2.0)))
tr.SetWidth(pcbnew.FromMM(0.3)); tr.SetLayer(pcbnew.F_Cu); tr.SetNet(tb.FindNet("0V"))
tb.Add(tr)
pcbnew.SaveBoard(os.path.join(tmp, "DCDCPod.kicad_pcb"), tb)
out = os.path.join(tmp, "drc.json")
subprocess.run([KICAD_CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", out, os.path.join(tmp, "DCDCPod.kicad_pcb")], capture_output=True)
v = [x for x in json.load(open(out))["violations"] if x["severity"] == "error"]
rules = sorted({re.search(r"rule '([^']+)'", x["description"]).group(1) for x in v if "rule '" in x["description"]})
print(f"3. a 0V track dropped at (25, 2) in the 5 V region: {len(v)} DRC errors, rules {rules}")
if not any(r in rules for r in ("iso_copper_in_hat_region", "isolation_gap")):
    ok = False; print("   FAIL: the isolation rules did not fire")
shutil.rmtree(tmp)

# 4. footprint paths
net = open(os.path.join(ROOT, "tools", "ref", "DCDCPod.net")).read()
paths = {}
for m in re.finditer(r'\(comp \(ref "([^"]+)"(.*?)\n\s*\(sheetpath \(names "/"\) \(tstamps "([^"]+)"\)\)\n\s*\(tstamps "([^"]+)"\)', net, re.S):
    paths[m.group(1)] = m.group(3) + m.group(4)
mism = [f.GetReference() for f in board.GetFootprints() if f.GetPath().AsString() != paths.get(f.GetReference())]
print(f"4. footprint paths vs netlist: {len(paths)} symbols, mismatches: {mism or 'none'}")
if mism or len(paths) != len(list(board.GetFootprints())):
    ok = False

# 5. connector geometry
pins = {}
for f in board.GetFootprints():
    if f.GetReference() in ("J1", "J2"):
        for p in f.Pads():
            pins[f"{f.GetReference()}.{p.GetNumber()}"] = (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, p.GetNetname())
print("5. header pins (pod x, pod y, net -> HAT x = 46 - pod x):")
for k in sorted(pins):
    x, y, n = pins[k]
    print(f"   {k:5s} ({x:6.2f}, {y:5.2f}) {n:7s} -> HAT x {46 - x:5.2f}")
d1 = pins["J1.1"][0] - pins["J2.1"][0]
d2 = pins["J1.1"][0] - pins["J2.4"][0]
print(f"   J1.1 (5V) to J2.1 (CAB): {d1:.2f} mm (HAT 19.0 -> 38.0 = 19.0);  to J2.4 (+V): {d2:.2f} mm (19.0 -> 44.0 = 25.0)")
if abs(d1 - 19.0) > 0.01 or abs(d2 - 25.0) > 0.01 or any(abs(pins[k][1] - pins["J2.1"][1]) > 0.01 for k in ("J2.2", "J2.3", "J2.4")) \
        or abs(pins["J1.2"][1] - pins["J1.1"][1]) > 0.01:
    ok = False; print("   FAIL: header geometry")
print("ISOLATION / LINK CHECKS", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
