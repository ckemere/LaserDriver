#!/usr/bin/env python3
"""Find ground-pour islands and deal with them (KiCad bundled Python).

    $KICAD_PY tools/gnd_islands.py board.kicad_pcb requests.json

Builds GND connectivity from geometry (pcbnew's own connectivity API does not
survive SWIG in this KiCad build):  pour fragments, pads, vias and tracks are
nodes, joined when they touch (via-in-pad, thermal spokes, tracks running into
the pour, ...).  Every component that does not contain the main pour is an
island:

* islands with no pad (only stitching vias / pour) -> their unlocked vias are
  deleted, so the refill drops the floating copper;
* islands with pads -> a maze-router request from one pad to "anywhere in the
  main pour" is written to requests.json for tools/maze_route.py.
"""
import json
import math
import sys

import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
LAYERS = {pcbnew.F_Cu: "F", pcbnew.B_Cu: "B"}


def ring(c, r, n=12):
    return [pcbnew.VECTOR2I(int(c.x + r * math.cos(2 * math.pi * k / n)),
                            int(c.y + r * math.sin(2 * math.pi * k / n))) for k in range(n)]


def main(path, out):
    board = pcbnew.LoadBoard(path)
    zone = next(z for z in board.Zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea())
    frags = []                                   # (layer, outline)
    for layer in LAYERS:
        ps = zone.GetFilledPolysList(layer)
        frags += [(layer, ps.Outline(i)) for i in range(ps.OutlineCount())]
    main_frag = {l: max((i for i, f in enumerate(frags) if f[0] == l),
                        key=lambda i: frags[i][1].Area()) for l in LAYERS}

    nodes = [("frag", i) for i in range(len(frags))]
    pads = [(f, p) for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == "GND"]
    vias, tracks = [], []
    for t in board.GetTracks():
        if t.GetNetname() == "GND":
            (vias if t.GetClass() == "PCB_VIA" else tracks).append(t)
    base_pad, base_via, base_trk = len(nodes), len(nodes) + len(pads), len(nodes) + len(pads) + len(vias)
    parent = list(range(base_trk + len(tracks)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    def frags_at(pts, layer):
        return {i for i, (l, o) in enumerate(frags) if l == layer and any(o.PointInside(p) for p in pts)}

    for k, (f, p) in enumerate(pads):
        bb = p.GetBoundingBox()
        pts = [pcbnew.VECTOR2I(x, y) for x in (bb.GetX() - MM(0.35), bb.GetCenter().x, bb.GetRight() + MM(0.35))
               for y in (bb.GetY() - MM(0.35), bb.GetCenter().y, bb.GetBottom() + MM(0.35))]
        for layer in LAYERS:
            if p.IsOnLayer(layer):
                for i in frags_at(pts, layer):
                    union(base_pad + k, i)
    for k, v in enumerate(vias):
        c, r = v.GetPosition(), v.GetWidth() / 2
        pts = [c] + ring(c, r + MM(0.15))
        for layer in LAYERS:
            for i in frags_at(pts, layer):
                union(base_via + k, i)
        for j, (f, p) in enumerate(pads):
            if p.HitTest(c):
                union(base_via + k, base_pad + j)
    for k, t in enumerate(tracks):
        a, b, w = t.GetStart(), t.GetEnd(), t.GetWidth()
        L = math.hypot(b.x - a.x, b.y - a.y) or 1
        nx, ny = -(b.y - a.y) / L, (b.x - a.x) / L
        n = max(2, int(L / MM(0.3)))
        pts = []
        for s in range(n + 1):
            x, y = a.x + (b.x - a.x) * s / n, a.y + (b.y - a.y) * s / n
            for side in (-1, 1):
                off = w / 2 + MM(0.12)
                pts.append(pcbnew.VECTOR2I(int(x + side * nx * off), int(y + side * ny * off)))
        for i in frags_at(pts, t.GetLayer()):
            union(base_trk + k, i)
        for end in (a, b):
            for j, (f, p) in enumerate(pads):
                if p.IsOnLayer(t.GetLayer()) and p.HitTest(end):
                    union(base_trk + k, base_pad + j)
            for j, v in enumerate(vias):
                if math.hypot(end.x - v.GetPosition().x, end.y - v.GetPosition().y) <= v.GetWidth() / 2:
                    union(base_trk + k, base_via + j)
            for j, t2 in enumerate(tracks):
                if j != k and t2.GetLayer() == t.GetLayer() and \
                        min(math.hypot(end.x - q.x, end.y - q.y) for q in (t2.GetStart(), t2.GetEnd())) < MM(0.01):
                    union(base_trk + k, base_trk + j)

    main = find(main_frag[pcbnew.F_Cu])
    comps = {}
    for idx in range(len(parent)):
        comps.setdefault(find(idx), []).append(idx)
    doomed, requests = [], []
    main_polys = {LAYERS[l]: [[list(TO(o.CPoint(i))) for i in range(o.PointCount())]]
                  for l in LAYERS for (ll, o) in [frags[main_frag[l]]] if ll == l}
    # both main fragments count as "main" if they are joined
    same = find(main_frag[pcbnew.B_Cu]) == main
    if not same:
        main_polys.pop("B")
    for root, members in comps.items():
        if root == main or (same and root == find(main_frag[pcbnew.B_Cu])):
            continue
        mpads = [pads[i - base_pad] for i in members if base_pad <= i < base_via]
        mvias = [vias[i - base_via] for i in members if base_via <= i < base_trk]
        mfr = [i for i in members if i < base_pad]
        if not mfr and not mpads and not mvias:
            continue
        if not mpads:
            doomed += [v for v in mvias if not v.IsLocked()]
            continue
        f, p = mpads[0]
        requests.append([{"net": "GND", "pt": list(TO(p.GetPosition())),
                          "F": p.IsOnLayer(pcbnew.F_Cu), "B": p.IsOnLayer(pcbnew.B_Cu),
                          "label": f"{f.GetReference()}.{p.GetNumber()}"},
                         {"net": "GND", "polys": main_polys}])
    n = len(doomed)
    for v in doomed:                   # removals last (SWIG)
        board.Remove(v)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    json.dump(requests, open(out, "w"))
    print("islands: pruned", n, "floating vias; routing requests for",
          [r[0]["label"] for r in requests])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
