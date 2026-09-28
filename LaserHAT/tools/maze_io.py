#!/usr/bin/env python3
"""Board <-> JSON bridge for tools/maze_route.py (KiCad bundled Python).

    $KICAD_PY tools/maze_io.py export board.kicad_pcb drc.rpt out.json [extra_requests.json]
    $KICAD_PY tools/maze_io.py import board.kicad_pcb routes.json

export: copper geometry (pads, tracks, vias, board edge) plus the signal
        connections the DRC report lists as unconnected.
import: adds the routed tracks/vias (locked) and refills the zones.
"""
import json
import os
import re
import sys

import pcbnew

MM = pcbnew.ToMM


def export(board_path, rpt, out, extra=None):
    board = pcbnew.LoadBoard(board_path)
    data = {"pads": [], "tracks": [], "vias": [], "edges": [], "requests": []}
    pads_by_key = {}
    for f in board.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            item = {"ref": f.GetReference(), "num": p.GetNumber(), "net": p.GetNetname(),
                    "box": [MM(bb.GetX()), MM(bb.GetY()), MM(bb.GetRight()), MM(bb.GetBottom())],
                    "center": list(MM(p.GetPosition())),
                    "F": p.IsOnLayer(pcbnew.F_Cu), "B": p.IsOnLayer(pcbnew.B_Cu),
                    "hole": MM(p.GetDrillSize().x) if p.GetAttribute() in
                    (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0}
            data["pads"].append(item)
            pads_by_key[(f.GetReference(), p.GetNumber())] = item
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            data["vias"].append({"net": t.GetNetname(), "pos": list(MM(t.GetPosition())),
                                 "d": MM(t.GetWidth())})
        else:
            data["tracks"].append({"net": t.GetNetname(), "a": list(MM(t.GetStart())),
                                   "b": list(MM(t.GetEnd())), "w": MM(t.GetWidth()),
                                   "layer": "F" if t.GetLayer() == pcbnew.F_Cu else "B"})
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            if d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                data["edges"].append([list(MM(d.GetStart())), list(MM(d.GetEnd()))])
            elif d.GetShape() == pcbnew.SHAPE_T_ARC:          # approximate arcs by chords
                pts = [d.GetStart(), d.GetArcMid(), d.GetEnd()]
                for a, b in zip(pts, pts[1:]):
                    data["edges"].append([list(MM(a)), list(MM(b))])
    bb = board.GetBoardEdgesBoundingBox()
    data["bbox"] = [MM(bb.GetX()), MM(bb.GetY()), MM(bb.GetRight()), MM(bb.GetBottom())]
    # unconnected signal items from the DRC report
    txt = open(rpt).read()
    for block in txt.split("[unconnected_items]")[1:]:
        lines = [l for l in block.split("\n")[1:4] if "@(" in l]
        ends = []
        for l in lines:
            m = re.search(r"@\(([\d.]+) mm, ([\d.]+) mm\): (.*)", l)
            if not m:
                continue
            x, y, what = float(m.group(1)), float(m.group(2)), m.group(3)
            if what.startswith("Zone"):
                break
            pm = re.search(r"[Pp]ad (\S+) \[(.*?)\] of (\S+)", what)
            tm = re.search(r"Track \[(.*?)\] on (\S)\.Cu", what)
            if pm:
                p = pads_by_key[(pm.group(3), pm.group(1))]
                ends.append({"net": p["net"], "pt": p["center"], "F": p["F"], "B": p["B"]})
            elif tm:
                ends.append({"net": tm.group(1), "pt": [x, y],
                             "F": tm.group(2) == "F", "B": tm.group(2) == "B"})
        if len(ends) == 2 and ends[0]["net"] == ends[1]["net"]:
            data["requests"].append(ends)
    if extra and os.path.exists(extra):
        data["requests"] += json.load(open(extra))
    # track width per net from the project's net-class patterns (exact net names)
    pro = os.path.splitext(board_path)[0] + ".kicad_pro"
    data["widths"] = {}
    if os.path.exists(pro):
        ns = json.load(open(pro))["net_settings"]
        width = {c["name"]: c["track_width"] for c in ns["classes"]}
        for pat in ns.get("netclass_patterns", []):
            data["widths"][pat["pattern"]] = width[pat["netclass"]]
        data["default_width"] = width.get("Default", 0.15)
    json.dump(data, open(out, "w"))
    print("exported", len(data["requests"]), "connection request(s)")


def do_import(board_path, routes):
    board = pcbnew.LoadBoard(board_path)
    r = json.load(open(routes))
    for t in r["tracks"]:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(t["a"][0]), pcbnew.FromMM(t["a"][1])))
        tr.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(t["b"][0]), pcbnew.FromMM(t["b"][1])))
        tr.SetWidth(pcbnew.FromMM(t["w"]))
        tr.SetLayer(pcbnew.F_Cu if t["layer"] == "F" else pcbnew.B_Cu)
        tr.SetNet(board.FindNet(t["net"]))
        tr.SetLocked(True)
        board.Add(tr)
    for v in r["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(v["pos"][0]), pcbnew.FromMM(v["pos"][1])))
        via.SetWidth(pcbnew.FromMM(v["d"]))
        via.SetDrill(pcbnew.FromMM(v["drill"]))
        via.SetNet(board.FindNet(v["net"]))
        via.SetLocked(True)
        board.Add(via)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(board_path, board)
    print("imported", len(r["tracks"]), "tracks,", len(r["vias"]), "vias")


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(*sys.argv[2:6])
    else:
        do_import(*sys.argv[2:4])
