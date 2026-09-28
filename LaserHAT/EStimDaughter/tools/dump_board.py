"""dump tracks/pads/unrouted links of EStimDaughter.kicad_pcb to route/board.json (KiCad python)"""
import json, os, re, pcbnew
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = pcbnew.LoadBoard(os.path.join(ROOT, "EStimDaughter.kicad_pcb"))
T = pcbnew.ToMM
L = {pcbnew.F_Cu: "F", pcbnew.In1_Cu: "In1", pcbnew.In2_Cu: "In2", pcbnew.B_Cu: "B"}
out = dict(tracks=[], vias=[], pads=[], links=[])
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        out["vias"].append((T(t.GetPosition().x), T(t.GetPosition().y)))
    else:
        out["tracks"].append((L.get(t.GetLayer(), "?"), T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y), T(t.GetWidth())))
for fp in b.GetFootprints():
    side = "B" if fp.IsFlipped() else "F"
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        s = "FB" if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else side
        out["pads"].append((s, T(bb.GetLeft()), T(bb.GetRight()), T(bb.GetTop()), T(bb.GetBottom()), fp.GetReference()))
txt = open(os.path.join(ROOT, "route", "drc.rpt")).read()
for blk in txt.split("\n["):
    if blk.startswith("unconnected_items]"):
        pts = re.findall(r"@\(([-0-9.]+) mm, ([-0-9.]+) mm\)", blk)
        if len(pts) == 2:
            out["links"].append([float(v) for p in pts for v in p])
json.dump(out, open(os.path.join(ROOT, "route", "board.json"), "w"))
