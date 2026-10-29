#!/usr/bin/env python3
"""Small post-route fix-ups on StimHAT.kicad_pcb, one board edit per process (pcbnew):
    $KICAD_PY tools/fixups.py drop-locked NET        delete the locked (maze-routed) tracks / vias of NET
    $KICAD_PY tools/fixups.py narrow X Y W           set the width of the tracks that have an end at (X, Y) mm to W mm
    $KICAD_PY tools/fixups.py maze                   maze-route the DRC's unconnected items with the isolation barriers
                                                     (the rule areas) added as obstacles, then import the result
    $KICAD_PY tools/fixups.py drop-dangling-vias     delete vias DRC flags as connected on one layer only, keeping any
                                                     whose removal opens a connection
    $KICAD_PY tools/fixups.py track LAYER NET W X1 Y1 X2 Y2 [X3 Y3 ...]   add a hand-routed polyline (mm)
    $KICAD_PY tools/fixups.py via NET X Y            add a 0.6 / 0.3 through via
    $KICAD_PY tools/fixups.py silk-strip REF ...     delete the silkscreen graphics of edge-overhanging connectors (their
                                                     outlines are clipped by the board edge; the bodies cover them anyway)"""
import json
import re
import os
import shutil
import subprocess
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
TOOLS = os.path.abspath(os.path.join(ROOT, "..", "tools"))
WORK = os.path.join(ROOT, "route")
KICAD_CLI = shutil.which("kicad-cli") or "kicad-cli"
mm = pcbnew.FromMM


def drc(fmt="json"):
    out = os.path.join(WORK, "drc_fix." + ("json" if fmt == "json" else "rpt"))
    subprocess.run([KICAD_CLI, "pcb", "drc", "--severity-all", "--format", fmt, "-o", out, BOARD], capture_output=True)
    return out


def drop_locked(net):
    b = pcbnew.LoadBoard(BOARD)
    kill = [t for t in b.GetTracks() if t.IsLocked() and t.GetNetname() == net]
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(BOARD, b)
    print("dropped", len(kill), "locked items of", net)


def narrow(x, y, w):
    b = pcbnew.LoadBoard(BOARD)
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and any(abs(p.x / 1e6 - x) < 0.01 and abs(p.y / 1e6 - y) < 0.01 for p in (t.GetStart(), t.GetEnd())):
            t.SetWidth(mm(w)); n += 1
    pcbnew.SaveBoard(BOARD, b)
    print("set", n, "tracks to", w)


def maze():
    rpt = drc("report")
    src, routes = os.path.join(WORK, "maze_in.json"), os.path.join(WORK, "maze_out.json")
    subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "export", BOARD, rpt, src], check=True)
    d = json.load(open(src))
    b = pcbnew.LoadBoard(BOARD)
    n = 0
    for z in b.Zones():                                       # rule areas -> obstacle edges (both layers)
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            o = z.Outline().Outline(0)
            pts = [(o.CPoint(i).x / 1e6, o.CPoint(i).y / 1e6) for i in range(o.PointCount())]
            for i in range(len(pts)):
                a, c = pts[i], pts[(i + 1) % len(pts)]
                d["edges"].append([list(a), list(c)]); n += 1       # a closed polygon: its inside counts as off-board
    print("requests:", len(d["requests"]), "barrier edges added:", n)
    json.dump(d, open(src, "w"))
    if os.path.exists(routes):
        os.remove(routes)
    r = subprocess.run(["python3", os.path.join(TOOLS, "maze_route.py"), src, routes], capture_output=True, text=True)
    print(r.stdout[-1200:], r.stderr[-400:])
    if os.path.exists(routes):
        subprocess.run([sys.executable, os.path.join(TOOLS, "maze_io.py"), "import", BOARD, routes], check=True)


def drop_dangling_vias():
    rep = json.load(open(drc()))
    base = len(rep["unconnected_items"])
    pos = [(v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]) for v in rep["violations"] if v["type"] == "via_dangling"]
    removed = 0
    for x, y in pos:
        backup = os.path.join(WORK, "before_via.kicad_pcb")
        shutil.copy(BOARD, backup)
        subprocess.run([sys.executable, os.path.abspath(__file__), "drop-via", str(x), str(y)], capture_output=True, check=True)
        if len(json.load(open(drc()))["unconnected_items"]) > base:
            shutil.copy(backup, BOARD)
        else:
            removed += 1
    print("removed", removed, "of", len(pos), "dangling vias")


def drop_via(x, y):
    b = pcbnew.LoadBoard(BOARD)
    hit = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and abs(t.GetPosition().x / 1e6 - x) < 0.01 and abs(t.GetPosition().y / 1e6 - y) < 0.01]
    for t in hit:
        b.Remove(t)
    pcbnew.SaveBoard(BOARD, b)


def add_track(layer, net, w, pts):
    b = pcbnew.LoadBoard(BOARD)
    code = b.GetNetcodeFromNetname(net)
    lay = b.GetLayerID(layer)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
        t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNetCode(code)
        b.Add(t)
    pcbnew.SaveBoard(BOARD, b)
    print("added", len(pts) - 1, "segments of", net, "on", layer)


def add_via(net, x, y):
    b = pcbnew.LoadBoard(BOARD)
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNetCode(b.GetNetcodeFromNetname(net))
    b.Add(v)
    pcbnew.SaveBoard(BOARD, b)
    print("added via", net, x, y)


def silk_strip(refs):
    """text edit: pcbnew segfaults on FOOTPRINT.Remove(graphic) in this build"""
    text = open(BOARD).read()
    out, n, i = [], 0, 0
    while True:
        j = text.find("\n\t(footprint ", i)
        if j < 0:
            out.append(text[i:]); break
        k = _close(text, text.index("(", j))          # end of this footprint block
        block = text[j:k]
        out.append(text[i:j])
        m = re.search(r'\(property "Reference" "([^"]+)"', block)
        if m and m.group(1) in refs:
            block, dropped = _strip_silk(block)
            n += dropped
        out.append(block)
        i = k
    open(BOARD, "w").write("".join(out))
    print("stripped", n, "silk items from", refs)


def _close(text, i):
    """index just past the s-expression that starts at text[i] == '('"""
    depth, q = 0, False
    while True:
        c = text[i]
        if c == '"' and text[i - 1] != "\\":
            q = not q
        elif not q:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1


def _strip_silk(block):
    out, n, i = [], 0, 0
    while True:
        m = re.compile(r"\n\t\t\((fp_line|fp_rect|fp_circle|fp_arc|fp_poly|fp_text)\b").search(block, i)
        if not m:
            out.append(block[i:]); return "".join(out), n
        k = _close(block, block.index("(", m.start()))
        item = block[m.start():k]
        out.append(block[i:m.start()])
        if '(layer "F.SilkS")' in item or '(layer "B.SilkS")' in item:
            n += 1
        else:
            out.append(item)
        i = k


def drop_seg(x1, y1, x2, y2):
    """delete the track(s) with exactly these two end points (either order)"""
    b = pcbnew.LoadBoard(BOARD)
    def near(p, x, y):
        return abs(p.x / 1e6 - x) < 0.01 and abs(p.y / 1e6 - y) < 0.01
    kill = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"
            and ((near(t.GetStart(), x1, y1) and near(t.GetEnd(), x2, y2)) or (near(t.GetStart(), x2, y2) and near(t.GetEnd(), x1, y1)))]
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(BOARD, b)
    print("dropped", len(kill), "segments")


def move_via(x, y, nx, ny):
    """move the via at (x, y) to (nx, ny) and drag the ends of the tracks that meet it"""
    b = pcbnew.LoadBoard(BOARD)
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            if abs(t.GetPosition().x / 1e6 - x) < 0.01 and abs(t.GetPosition().y / 1e6 - y) < 0.01:
                t.SetPosition(pcbnew.VECTOR2I(mm(nx), mm(ny))); n += 1
        else:
            for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                p = get()
                if abs(p.x / 1e6 - x) < 0.01 and abs(p.y / 1e6 - y) < 0.01:
                    put(pcbnew.VECTOR2I(mm(nx), mm(ny))); n += 1
    pcbnew.SaveBoard(BOARD, b)
    print("moved", n, "items")


def swap_fp(ref, lib_dir, name, fpid):
    """replace REF's footprint by LIB_DIR/NAME.kicad_mod (same pad numbers / positions assumed): keeps position,
    orientation, side, reference, value, schematic path and pad nets; pcb_sync.py does not swap footprint ids"""
    b = pcbnew.LoadBoard(BOARD)
    old = [f for f in b.GetFootprints() if f.GetReference() == ref][0]
    new = pcbnew.PCB_IO_KICAD_SEXPR().FootprintLoad(lib_dir, name)
    new.SetFPIDAsString(fpid)
    new.SetReference(old.GetReference()); new.SetValue(old.GetValue())
    new.SetPath(old.GetPath())
    nets = {p.GetNumber(): p.GetNetCode() for p in old.Pads()}
    pos, rot, flipped = old.GetPosition(), old.GetOrientation(), old.IsFlipped()
    b.Add(new)
    new.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y))
    if flipped:
        new.Flip(new.GetPosition(), False)
    new.SetOrientation(rot)
    for p in new.Pads():
        p.SetNetCode(nets.get(p.GetNumber(), 0))
    b.Remove(old)
    pcbnew.SaveBoard(BOARD, b)
    print("swapped", ref, "->", fpid, [(p.GetNumber(), round(p.GetPosition().x / 1e6, 2), round(p.GetPosition().y / 1e6, 2)) for p in new.Pads()])


def drop_tiny(limit=0.02):
    """delete track segments shorter than LIMIT mm (zero-length leftovers of the router / of point moves)"""
    b = pcbnew.LoadBoard(BOARD)
    kill = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < mm(limit)]
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(BOARD, b)
    print("dropped", len(kill), "tiny segments")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "drop-tiny":
        drop_tiny()
    elif cmd == "swap-fp":
        swap_fp(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "drop-seg":
        drop_seg(*map(float, sys.argv[2:6]))
    elif cmd == "move-via":
        move_via(*map(float, sys.argv[2:6]))
    elif cmd == "silk-strip":
        silk_strip(sys.argv[2:])
    elif cmd == "track":
        v = [float(a) for a in sys.argv[5:]]
        add_track(sys.argv[2], sys.argv[3], float(sys.argv[4]), list(zip(v[::2], v[1::2])))
    elif cmd == "via":
        add_via(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
    if cmd == "drop-locked":
        drop_locked(sys.argv[2])
    elif cmd == "narrow":
        narrow(float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))
    elif cmd == "maze":
        maze()
    elif cmd == "drop-dangling-vias":
        drop_dangling_vias()
    elif cmd == "drop-via":
        drop_via(float(sys.argv[2]), float(sys.argv[3]))
