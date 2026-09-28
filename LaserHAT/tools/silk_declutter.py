#!/usr/bin/env python3
"""Declutter the HAT silkscreen (KiCad bundled Python).

    $KICAD_PY tools/silk_declutter.py LaserDriver.kicad_pcb

* Hides every printed reference designator except the solder jumpers (KEEP), which go to 1.0 mm.
  The references stay on F.Fab, so KiCad and assembly drawings still show them.
* Adds short function labels beside the jumpers that have none (LABELS), trying a few spots.
* Grows the board's 0.8 mm labels to 1.5 mm, falling back to 1.25 / 1.0 mm (or leaving them at
  0.8 mm) where the bigger text would touch pads, other silkscreen or the board edge.
Each round is judged by kicad-cli DRC with the project's rules: only violations that the edit
creates count; the ones already on the board are left for hand clean-up.
"""
import os
import re
import shutil
import subprocess
import sys

import pcbnew

T, MM = pcbnew.ToMM, pcbnew.FromMM
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
KEEP = {"JP1", "JP4", "JP5"}
LABELS = {"JP1": "EEPROM WP", "JP4": "USB RST"}
SIZES = [1.5, 1.25, 1.0]
SILK_RULES = ("silk_overlap", "silk_over_copper", "silk_edge_clearance")


def stroke(h):
    return max(0.15, round(h * 0.14, 3))


def size(t, h):
    t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
    t.SetTextThickness(MM(stroke(h)))


def drc(board, path):
    """Silkscreen violations as a list of item descriptions, one list per violation."""
    here = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(here, "_silk.kicad_pcb")
    shutil.copy(os.path.join(here, "LaserDriver.kicad_pro"), os.path.join(here, "_silk.kicad_pro"))
    pcbnew.SaveBoard(tmp, board)
    rpt = os.path.join(here, "_silk.rpt")
    subprocess.run([CLI, "pcb", "drc", "-o", rpt, tmp], capture_output=True)
    out, cur = [], None
    for line in open(rpt):
        m = re.match(r"\[(\w+)\]", line)
        if m:
            cur = [] if m.group(1) in SILK_RULES else None
            if cur is not None:
                out.append(cur)
        elif cur is not None and line.strip().startswith("@("):
            cur.append(line.split("): ", 1)[1].strip())
    for f in ("_silk.kicad_pcb", "_silk.kicad_pro", "_silk.kicad_prl", "_silk.rpt"):
        if os.path.exists(os.path.join(here, f)):
            os.remove(os.path.join(here, f))
    return out


def involved(viol, needle):
    return sum(any(needle in item for item in v) for v in viol)


def main(path):
    b = pcbnew.LoadBoard(path)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    hidden = []
    for ref, f in fps.items():
        r = f.Reference()
        if r.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        if ref in KEEP:
            r.SetVisible(True)
            size(r, 1.0)
        elif r.IsVisible():
            r.SetVisible(False)
            hidden.append(ref)
    print(f"hid {len(hidden)} reference designators; kept {sorted(KEEP)} at 1.0 mm")
    base = drc(b, path)
    print(f"silkscreen violations after hiding: {len(base)}")

    def tag(text):
        return f"'{text}'" if "'" not in text else text

    # function labels beside the jumpers: try below, above, then either side of the footprint
    for ref, text in LABELS.items():
        f = fps[ref]
        bb = f.GetBoundingBox(False)
        cx, cy = T(f.GetPosition().x), T(f.GetPosition().y)
        spots = [(cx, T(bb.GetBottom()) + 0.8), (cx, T(bb.GetTop()) - 0.8)]
        placed = None
        for x, y in spots:
            t = pcbnew.PCB_TEXT(b)
            t.SetText(text)
            t.SetLayer(pcbnew.F_SilkS)
            t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            size(t, 1.0)
            b.Add(t)
            v = drc(b, path)
            if involved(v, text) == 0:
                placed = (x, y)
                break
            b.Remove(t)
        print(f"label '{text}' for {ref}: " + (f"placed at ({placed[0]:.2f}, {placed[1]:.2f})" if placed
                                                  else "no clean spot, skipped"))

    # grow the 0.8 mm board labels
    small = [t for t in b.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS
             and abs(T(t.GetTextHeight()) - 0.8) < 0.01]
    base = drc(b, path)
    before = {id(t): involved(base, t.GetText()) for t in small}
    level = {id(t): 0 for t in small}
    for t in small:
        size(t, SIZES[0])
    for _ in range(len(SIZES) + 1):
        v = drc(b, path)
        worse = [t for t in small if level[id(t)] is not None and involved(v, t.GetText()) > before[id(t)]]
        if not worse:
            break
        for t in worse:
            level[id(t)] += 1
            if level[id(t)] < len(SIZES):
                size(t, SIZES[level[id(t)]])
            else:
                level[id(t)] = None
                t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
                t.SetTextThickness(MM(0.12))
    for t in small:
        lv = level[id(t)]
        print(f"  {t.GetText()!r:20s} -> " + (f"{SIZES[lv]} mm" if lv is not None else "kept at 0.8 mm (no room)"))
    pcbnew.SaveBoard(path, b)
    print("saved", path)


if __name__ == "__main__":
    main(sys.argv[1])
