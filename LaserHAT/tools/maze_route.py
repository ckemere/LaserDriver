#!/usr/bin/env python3
"""Tiny two-layer grid maze router for the connections freerouting leaves behind.

    python tools/maze_route.py board.json routes.json   (kicad micromamba env: numpy)

Rasterises the board on a 0.1 mm grid, marks every cell that other-net copper,
holes or the board edge make unusable for a track (or a via), then runs A* on
(layer, x, y) with 8-way moves and a via move between layers.  The path is
simplified to straight segments.  Ground pour is ignored as an obstacle: it
simply re-flows around the new copper.
"""
import heapq
import json
import math
import sys

import numpy as np

PITCH = 0.1
TRACK_W, CLEAR, EDGE_CLEAR = 0.15, 0.15, 0.5
HOLE_CLEAR = 0.25                  # copper to any drilled hole (board setup)
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 25.0
SLACK = 0.06                     # grid discretisation margin


def main(src, dst):
    d = json.load(open(src))
    x0, y0, x1, y1 = d["bbox"]
    nx, ny = int((x1 - x0) / PITCH) + 1, int((y1 - y0) / PITCH) + 1
    X = x0 + np.arange(nx) * PITCH
    Y = y0 + np.arange(ny) * PITCH
    GX, GY = np.meshgrid(X, Y, indexing="xy")          # shape (ny, nx)

    def dist_rect(box):
        bx0, by0, bx1, by1 = box
        dx = np.maximum(np.maximum(bx0 - GX, 0), GX - bx1)
        dy = np.maximum(np.maximum(by0 - GY, 0), GY - by1)
        return np.hypot(dx, dy)

    def dist_seg(a, b):
        ax, ay = a
        bx, by = b
        L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-12
        t = np.clip(((GX - ax) * (bx - ax) + (GY - ay) * (by - ay)) / L2, 0, 1)
        return np.hypot(GX - (ax + t * (bx - ax)), GY - (ay + t * (by - ay)))

    # inside-board mask (even-odd ray cast against the edge segments)
    inside = np.zeros_like(GX, dtype=bool)
    edge_d = np.full(GX.shape, 1e9)
    for (a, b) in d["edges"]:
        (ax, ay), (bx, by) = a, b
        cond = ((ay > GY) != (by > GY))
        xint = ax + (GY - ay) * (bx - ax) / ((by - ay) if by != ay else 1e-12)
        inside ^= cond & (GX < xint)
        edge_d = np.minimum(edge_d, dist_seg(a, b))

    widths = d.get("widths", {})

    def net_width(net):
        return widths.get(net, d.get("default_width", TRACK_W))

    def obstacle_maps(net):
        """(track_blocked[2], via_blocked) for routing `net`."""
        rt = net_width(net) / 2 + CLEAR + SLACK
        rv = VIA_D / 2 + CLEAR + SLACK
        dF = np.full(GX.shape, 1e9)
        dB = np.full(GX.shape, 1e9)
        dH = np.full(GX.shape, 1e9)                     # holes (any net): vias keep off
        dHt = np.full(GX.shape, 1e9)                    # holes of other nets / unplated: tracks keep off
        for p in d["pads"]:
            if p["hole"]:
                c = p["center"]
                hd = np.hypot(GX - c[0], GY - c[1]) - p["hole"] / 2
                dH = np.minimum(dH, hd)
                if p["net"] != net:
                    dHt = np.minimum(dHt, hd)
            if p["net"] == net:
                continue
            dist = dist_rect(p["box"])
            if p["F"] or p["hole"]:
                dF = np.minimum(dF, dist)
            if p["B"] or p["hole"]:
                dB = np.minimum(dB, dist)
        for t in d["tracks"]:
            if t["net"] == net:
                continue
            dist = dist_seg(t["a"], t["b"]) - t["w"] / 2
            if t["layer"] == "F":
                dF = np.minimum(dF, dist)
            else:
                dB = np.minimum(dB, dist)
        for v in d["vias"]:
            dist = np.hypot(GX - v["pos"][0], GY - v["pos"][1]) - v["d"] / 2
            if v["net"] != net:
                dF = np.minimum(dF, dist)
                dB = np.minimum(dB, dist)
            dH = np.minimum(dH, dist)                   # never stack vias
        out = ~inside | (edge_d < EDGE_CLEAR + net_width(net) / 2)
        hole_t = dHt < HOLE_CLEAR + net_width(net) / 2 + SLACK   # board hole-clearance rule
        tb = np.stack([(dF < rt) | out | hole_t, (dB < rt) | out | hole_t])
        vb = (dF < rv) | (dB < rv) | (dH < VIA_D / 2 + 0.25) | ~inside | (edge_d < EDGE_CLEAR + VIA_D / 2)
        return tb, vb

    def cell(pt):
        return int(round((pt[1] - y0) / PITCH)), int(round((pt[0] - x0) / PITCH))

    def astar(net, start, goal):
        tb, vb = obstacle_maps(net)
        sy, sx = cell(start["pt"])
        tb[:, max(sy - 2, 0):sy + 3, max(sx - 2, 0):sx + 3] = False   # ends sit in their own pads
        starts = [(l, sy, sx) for l, ok in ((0, start["F"]), (1, start["B"])) if ok]
        if "polys" in goal:           # "anywhere inside these copper polygons"
            gmask = np.zeros((2,) + GX.shape, dtype=bool)
            for li, ln in ((0, "F"), (1, "B")):
                for ring_ in goal["polys"].get(ln, []):      # list of outlines [[x, y], ...]
                    pts_ = ring_ + ring_[:1]
                    m = np.zeros_like(GX, dtype=bool)
                    for (ax, ay), (bx, by) in zip(pts_, pts_[1:]):
                        cond = ((ay > GY) != (by > GY))
                        xint = ax + (GY - ay) * (bx - ax) / ((by - ay) if by != ay else 1e-12)
                        m ^= cond & (GX < xint)
                    gmask[li] |= m
            gmask &= ~tb
            ys, xs = np.nonzero(gmask.any(axis=0))
            gy, gx = (int(ys.mean()), int(xs.mean())) if len(ys) else (sy, sx)
            is_goal = lambda n: gmask[n]
        else:
            gy, gx = cell(goal["pt"])
            tb[:, max(gy - 2, 0):gy + 3, max(gx - 2, 0):gx + 3] = False
            goals = {(l, gy, gx) for l, ok in ((0, goal["F"]), (1, goal["B"])) if ok}
            is_goal = lambda n: n in goals
        g = {}
        heap = []
        for s in starts:
            g[s] = 0.0
            heapq.heappush(heap, (math.hypot(sx - gx, sy - gy), 0.0, s, None))
        came = {}
        moves = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1),
                 (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
        while heap:
            f, cost, node, parent = heapq.heappop(heap)
            if node in came:
                continue
            came[node] = parent
            if is_goal(node):
                path = [node]
                while came[path[-1]] is not None:
                    path.append(came[path[-1]])
                return path[::-1]
            l, y, x = node
            nbrs = []
            for dy, dx, c in moves:
                yy, xx = y + dy, x + dx
                if 0 <= yy < ny and 0 <= xx < nx and not tb[l, yy, xx]:
                    nbrs.append(((l, yy, xx), c))
            if not vb[y, x]:
                nbrs.append(((1 - l, y, x), VIA_COST))
            for nb, c in nbrs:
                ng = cost + c
                if ng < g.get(nb, 1e18):
                    g[nb] = ng
                    h = 0.0 if "polys" in goal else math.hypot(nb[1] - gy, nb[2] - gx)
                    heapq.heappush(heap, (ng + h, ng, nb, node))
        return None

    out = {"tracks": [], "vias": []}
    for a, b in d["requests"]:
        net = a["net"]
        n_tracks0, n_vias0 = len(out["tracks"]), len(out["vias"])
        path = astar(net, a, b)
        if path is None:
            print("NO ROUTE for", net)
            continue
        # pin the ends to the exact requested points
        pts = [(l, x0 + x * PITCH, y0 + y * PITCH) for l, y, x in path]
        pts[0] = (pts[0][0], a["pt"][0], a["pt"][1])
        if "pt" in b:
            pts[-1] = (pts[-1][0], b["pt"][0], b["pt"][1])
        # split into single-layer runs; a via sits wherever the layer changes
        runs = [[pts[0]]]
        for p in pts[1:]:
            if p[0] != runs[-1][-1][0]:
                out["vias"].append({"net": net, "pos": [round(p[1], 4), round(p[2], 4)],
                                    "d": VIA_D, "drill": VIA_DRILL})
                runs.append([p])
            else:
                runs[-1].append(p)
        for run in runs:
            keep = [run[0]]
            for i in range(1, len(run) - 1):          # drop collinear interior points
                (_, ax, ay), (_, bx, by), (_, cx, cy) = keep[-1], run[i], run[i + 1]
                if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-6:
                    keep.append(run[i])
            keep.append(run[-1])
            for (l, ax, ay), (_, bx, by) in zip(keep, keep[1:]):
                if (ax, ay) != (bx, by):
                    out["tracks"].append({"net": net, "layer": "FB"[l], "w": net_width(net),
                                          "a": [round(ax, 4), round(ay, 4)],
                                          "b": [round(bx, 4), round(by, 4)]})
        # later requests must see this route as an obstacle
        d["tracks"] += [tr for tr in out["tracks"][n_tracks0:]]
        d["vias"] += [v for v in out["vias"][n_vias0:]]
        print("routed", net, "in", len(path), "steps")
    json.dump(out, open(dst, "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
