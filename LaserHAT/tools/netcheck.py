#!/usr/bin/env python3
"""Per-net copper connectivity check (KiCad bundled Python); ignores zones.

    $KICAD_PY tools/netcheck.py board.kicad_pcb [--skip GND]

For every net, pads, track segments and vias are joined when they touch
(pcbnew hit-testing), and nets that end up in more than one piece are listed
with the location of each piece.  kicad-cli's text DRC report sometimes pairs
items from different nets in "unconnected" entries, so this is used instead.
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
skip = set(sys.argv[sys.argv.index("--skip") + 1:]) if "--skip" in sys.argv else set()
items = {}
for f in board.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if n and not n.startswith("unconnected"):
            items.setdefault(n, []).append(("pad", p, f"{f.GetReference()}.{p.GetNumber()}"))
for t in board.GetTracks():
    items.setdefault(t.GetNetname(), []).append(("via" if t.GetClass() == "PCB_VIA" else "trk", t, ""))

bad = 0
for net, its in sorted(items.items()):
    if net in skip or len([i for i in its if i[0] == "pad"]) < 2:
        continue
    parent = list(range(len(its)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def pts(kind, it):
        if kind == "trk":
            return [(it.GetStart(), it.GetLayer()), (it.GetEnd(), it.GetLayer())]
        if kind == "via":
            return [(it.GetPosition(), pcbnew.F_Cu), (it.GetPosition(), pcbnew.B_Cu)]
        return [(it.GetPosition(), l) for l in (pcbnew.F_Cu, pcbnew.B_Cu) if it.IsOnLayer(l)]

    for i, (ka, a, _) in enumerate(its):
        for j, (kb, b, _) in enumerate(its):
            if i >= j:
                continue
            hit = False
            for (pt, layer) in pts(ka, a):
                if (kb == "via" or b.IsOnLayer(layer)) and b.HitTest(pt, 1000):
                    hit = True
                    break
            if not hit:
                for (pt, layer) in pts(kb, b):
                    if (ka == "via" or a.IsOnLayer(layer)) and a.HitTest(pt, 1000):
                        hit = True
                        break
            if hit:
                parent[find(i)] = find(j)
    groups = {}
    for i, (k, it, lab) in enumerate(its):
        groups.setdefault(find(i), []).append(lab or k)
    if len(groups) > 1:
        bad += 1
        print(f"{net}: {len(groups)} pieces:", [sorted(set(g))[:4] for g in groups.values()])
print("nets split:", bad)
