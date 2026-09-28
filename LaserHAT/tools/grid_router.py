#!/usr/bin/env python3
"""Deliberate two-layer grid router for small boards (kicad micromamba env: numpy, scipy).

    python tools/grid_router.py board.json plan.json routes.json

board.json comes from `tools/maze_io.py export` (pads, tracks, vias, edges).
plan.json says how to route:

    {"order":  ["/SW", "+5V", ...],          # nets, routed in this order
     "widths": {"/SW": 1.0, "+5V": 0.8, ...},
     "default_width": 0.25,
     "skip":   ["GND"],                        # nets left to pours/vias
     "bottom_cost": 3.0,                       # B.Cu step cost multiplier (keep it a plane)
     "via_cost": 40, "turn_cost": 4,
     "pad_widths": {"U3.5": 0.3}}             # thin branch onto low-current pads

Each net is built as a tree: its first pad seeds the tree, then every other pad
(nearest first) is routed to *any* copper already in the tree.  A* runs over
(layer, cell, heading) with 8 headings, so it pays for every bend and produces
long straight 45/90-degree runs instead of staircases.  Everything already
routed (and every other-net pad, hole and the board edge) is an obstacle with
proper clearance for the width being routed.
"""
import heapq
import json
import math
import os
import sys

import numpy as np
from scipy import ndimage

PITCH = 0.1
CLEAR = float(os.environ.get("GR_CLEAR", 0.2))          # copper clearance (board rule; HAT uses 0.15)
EDGE_CLEAR, SLACK = 0.5, 0.05
VIA_D, VIA_DRILL = 0.6, 0.3
DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]   # (dy, dx)


def main(board_json, plan_json, out_json):
    d = json.load(open(board_json))
    plan = json.load(open(plan_json))
    widths = plan.get("widths", {})
    wdef = plan.get("default_width", 0.25)
    bcost = plan.get("bottom_cost", 3.0)
    via_cost = plan.get("via_cost", 40)
    turn_cost = plan.get("turn_cost", 4)
    skip = set(plan.get("skip", []))
    pad_w = plan.get("pad_widths", {})

    x0, y0, x1, y1 = d["bbox"]
    nx, ny = int(round((x1 - x0) / PITCH)) + 1, int(round((y1 - y0) / PITCH)) + 1
    GX, GY = np.meshgrid(x0 + np.arange(nx) * PITCH, y0 + np.arange(ny) * PITCH)

    def dist_rect(b):
        dx = np.maximum(np.maximum(b[0] - GX, 0), GX - b[2])
        dy = np.maximum(np.maximum(b[1] - GY, 0), GY - b[3])
        return np.hypot(dx, dy)

    def dist_seg(a, b):
        ax, ay = a
        bx, by = b
        L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-12
        t = np.clip(((GX - ax) * (bx - ax) + (GY - ay) * (by - ay)) / L2, 0, 1)
        return np.hypot(GX - (ax + t * (bx - ax)), GY - (ay + t * (by - ay)))

    inside = np.zeros(GX.shape, bool)
    edge_d = np.full(GX.shape, 1e9)
    for a, b in d["edges"]:
        (ax, ay), (bx, by) = a, b
        cond = (ay > GY) != (by > GY)
        xint = ax + (GY - ay) * (bx - ax) / ((by - ay) if by != ay else 1e-12)
        inside ^= cond & (GX < xint)
        edge_d = np.minimum(edge_d, dist_seg(a, b))

    # copper that exists so far: list of (net, layer_set, kind, geometry, half_width)
    copper = []
    for p in d["pads"]:
        layers = {l for l, ok in (("F", p["F"] or p["hole"]), ("B", p["B"] or p["hole"])) if ok}
        copper.append((p["net"], layers, "box", p["box"], 0.0))
    for t in d["tracks"]:
        copper.append((t["net"], {t["layer"]}, "seg", (t["a"], t["b"]), t["w"] / 2))
    for v in d["vias"]:
        copper.append((v["net"], {"F", "B"}, "circ", v["pos"], v["d"] / 2))
    holes = [p for p in d["pads"] if p["hole"]]

    def item_dist(kind, g, hw):
        if kind == "box":
            return dist_rect(g)
        if kind == "seg":
            return dist_seg(*g) - hw
        return np.hypot(GX - g[0], GY - g[1]) - hw

    def maps(net, w):
        """blocked[layer] for a track of width w, via_blocked, own-net copper masks."""
        dF = np.full(GX.shape, 1e9)
        dB = np.full(GX.shape, 1e9)
        dV = np.full(GX.shape, 1e9)
        own = np.zeros((2,) + GX.shape, bool)
        for n, layers, kind, g, hw in copper:
            dd = item_dist(kind, g, hw)
            if n == net and n != "":
                if "F" in layers:
                    own[0] |= dd <= 0
                if "B" in layers:
                    own[1] |= dd <= 0
                continue
            if "F" in layers:
                dF = np.minimum(dF, dd)
            if "B" in layers:
                dB = np.minimum(dB, dd)
            dV = np.minimum(dV, dd)
        for p in d["pads"]:                              # no via-in-pad on SMD pads, any net
            if not p["hole"]:
                dV = np.minimum(dV, dist_rect(p["box"]))
        for p in holes:                                  # never drill next to a hole
            dV = np.minimum(dV, np.hypot(GX - p["center"][0], GY - p["center"][1]) - p["hole"] / 2 - 0.1)
        rt = w / 2 + CLEAR + SLACK
        out = ~inside | (edge_d < EDGE_CLEAR + w / 2)
        blocked = np.stack([(dF < rt) | out, (dB < rt) | out])
        vblocked = (np.minimum(dF, dB) < VIA_D / 2 + CLEAR + SLACK) | (dV < VIA_D / 2 + CLEAR) | \
            ~inside | (edge_d < EDGE_CLEAR + VIA_D / 2)
        return blocked, vblocked, own

    def cell(pt):
        return int(round((pt[1] - y0) / PITCH)), int(round((pt[0] - x0) / PITCH))

    def pad_cells(p):
        (r0, c0), (r1, c1) = cell((p["box"][0], p["box"][1])), cell((p["box"][2], p["box"][3]))
        return [(r, c) for r in range(max(r0, 0), min(r1, ny - 1) + 1)
                for c in range(max(c0, 0), min(c1, nx - 1) + 1)]

    def astar(sources, goal_mask, blocked, vblocked):
        """sources: set of (l, r, c); goal_mask[l, r, c] bool."""
        # admissible heuristic: distance (cells) to the nearest goal cell on any layer
        gd = ndimage.distance_transform_edt(~goal_mask.any(axis=0))
        INF = 1e18
        best = {}
        heap = []
        for (l, r, c) in sources:
            if blocked[l, r, c] and not goal_mask[l, r, c]:
                pass                                     # inside own pad: allowed to start
            st = (l, r, c, 8)
            best[st] = 0.0
            heapq.heappush(heap, (gd[r, c], 0.0, st, None))
        came = {}
        while heap:
            f, g, st, parent = heapq.heappop(heap)
            if st in came:
                continue
            came[st] = parent
            l, r, c, h = st
            if goal_mask[l, r, c]:
                path = [st]
                while came[path[-1]] is not None:
                    path.append(came[path[-1]])
                return path[::-1]
            cost_l = bcost if l == 1 else 1.0
            for k, (dr, dc) in enumerate(DIRS):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < ny and 0 <= cc < nx):
                    continue
                if blocked[l, rr, cc] and not goal_mask[l, rr, cc]:
                    continue
                if dr and dc and (blocked[l, r + dr, c] or blocked[l, r, c + dc]):
                    continue                             # no corner cutting past obstacles
                step = (1.414 if dr and dc else 1.0) * cost_l
                if h != 8 and k != h:
                    turn = min((k - h) % 8, (h - k) % 8)
                    if turn > 2:
                        continue                         # no sharper than 90 degrees
                    step += turn_cost * turn
                ns = (l, rr, cc, k)
                ng = g + step
                if ng < best.get(ns, INF):
                    best[ns] = ng
                    heapq.heappush(heap, (ng + gd[rr, cc], ng, ns, st))
            if not vblocked[r, c]:
                ns = (1 - l, r, c, 8)
                ng = g + via_cost
                if ng < best.get(ns, INF):
                    best[ns] = ng
                    heapq.heappush(heap, (ng + gd[r, c], ng, ns, st))
        return None

    out = {"tracks": [], "vias": []}
    pads_by_net = {}
    for p in d["pads"]:
        if p["net"] and not p["net"].startswith("unconnected"):
            pads_by_net.setdefault(p["net"], []).append(p)
    order = plan.get("order", [])
    order += sorted(n for n in pads_by_net if n not in order and n not in skip)
    def pad_landing(q, blocked):
        """Cells where a track may start on / end at pad q: its inscribed square
        (certainly copper even for a round pad), or any clear cell of its box."""
        b = q["box"]
        k = 0.15 * min(b[2] - b[0], b[3] - b[1])
        inner = dist_rect([b[0] + k, b[1] + k, b[2] - k, b[3] - k]) <= 0
        r, c = cell(q["center"])                         # fine-pitch pads (QFN): the inscribed square may
        inner[r, c] = True                               # hold no grid cell - the centre always counts
        full = dist_rect(b) <= 0
        return np.stack([inner | (full & ~blocked[0]), inner | (full & ~blocked[1])])

    def route_pad(net, p, tree, tree_copper):
        """Route pad p to this net's tree; returns False when there is no path."""
        # neck down onto small pads (0402s, SC-70 pins): the branch is never wider
        # than the pad it lands on, the rest of the net keeps its full width
        pw = min(p["box"][2] - p["box"][0], p["box"][3] - p["box"][1])
        w = max(min(widths.get(net, wdef), pw if not p["hole"] else 99), wdef)
        w = pad_w.get(f"{p['ref']}.{p['num']}", w)
        blocked, vblocked, _own = maps(net, w)
        # goal: only copper already joined to this net's tree (not stray same-net pads)
        goal = np.zeros((2,) + GX.shape, bool)
        for q in tree:
            land = pad_landing(q, blocked)
            for li, ln in ((0, "F"), (1, "B")):
                if q[ln] or q["hole"]:
                    goal[li] |= land[li]
        for kind, g, hw, layers in tree_copper:
            dd = item_dist(kind, g, hw)
            for li, ln in ((0, "F"), (1, "B")):
                if ln in layers:
                    goal[li] |= dd <= 0
        srcs = set()
        land = pad_landing(p, blocked)
        for (r, c) in pad_cells(p):
            for li, ln in ((0, "F"), (1, "B")):
                if p[ln] or p["hole"]:
                    goal[li, r, c] = False               # don't "arrive" on the start pad
                    if land[li, r, c]:
                        srcs.add((li, r, c))
        path = astar(srcs, goal, blocked, vblocked) if goal.any() else None
        if path is None:
            return False
        pts = [(l, x0 + c * PITCH, y0 + r * PITCH) for l, r, c, _h in path]
        pts[0] = (pts[0][0], p["center"][0], p["center"][1])
        # a route that ends on a pad's bounding box may miss round/rotated copper:
        # finish at that pad's centre instead, necked down to that pad's size (the
        # last grid step is the only part that may be closer to its neighbours)
        le, xe, ye = pts[-1]
        w_end = w
        for q in tree:
            bx0, by0, bx1, by1 = q["box"]
            if q is not p and bx0 <= xe <= bx1 and by0 <= ye <= by1 and (q["FB"[le]] or q["hole"]):
                pts.append((le, q["center"][0], q["center"][1]))
                if not q["hole"]:
                    w_end = max(min(w, bx1 - bx0, by1 - by0), wdef)
                break
        runs = [([pts[0]], w)]
        for q in pts[1:]:
            if q[0] != runs[-1][0][-1][0]:
                runs[-1][0].append((runs[-1][0][-1][0], q[1], q[2]))     # track into the via
                out["vias"].append({"net": net, "pos": [round(q[1], 4), round(q[2], 4)],
                                    "d": VIA_D, "drill": VIA_DRILL})
                copper.append((net, {"F", "B"}, "circ", [q[1], q[2]], VIA_D / 2))
                tree_copper.append(("circ", [q[1], q[2]], VIA_D / 2, {"F", "B"}))
                runs.append(([q], w))
            else:
                runs[-1][0].append(q)
        if w_end < w and len(runs[-1][0]) >= 3:
            last = runs[-1][0]
            runs[-1] = (last[:-2], w)
            runs.append((last[-3:], w_end))
        for run, rw in runs:
            keep = [run[0]]
            for i in range(1, len(run) - 1):
                (_, ax, ay), (_, bx, by), (_, cx, cy) = keep[-1], run[i], run[i + 1]
                if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-6:
                    keep.append(run[i])
            keep.append(run[-1])
            for (l, ax, ay), (_, bx, by) in zip(keep, keep[1:]):
                if (ax, ay) != (bx, by):
                    seg = {"net": net, "layer": "FB"[l], "w": rw,
                           "a": [round(ax, 4), round(ay, 4)], "b": [round(bx, 4), round(by, 4)]}
                    out["tracks"].append(seg)
                    copper.append((net, {"FB"[l]}, "seg", (seg["a"], seg["b"]), rw / 2))
                    tree_copper.append(("seg", (seg["a"], seg["b"]), rw / 2, {"FB"[l]}))
        return True

    def route_all(order):
        copper[:] = base_copper
        out["tracks"].clear()
        out["vias"].clear()
        failures = []
        trees, deferred = {}, []
        for net in order:
            if net in skip or net not in pads_by_net or len(pads_by_net[net]) < 2:
                continue
            # seed the tree with a full-width pad; thin (pad_widths) branches are routed
            # last, after every other net, so they cannot wall anything in
            pads = sorted(pads_by_net[net], key=lambda p: f"{p['ref']}.{p['num']}" in pad_w)
            tree, tree_copper = [pads[0]], []
            trees[net] = (tree, tree_copper)
            todo = [p for p in pads[1:] if f"{p['ref']}.{p['num']}" not in pad_w]
            deferred += [(net, p) for p in pads[1:] if f"{p['ref']}.{p['num']}" in pad_w]
            while todo:
                # nearest remaining pad to anything already in the tree
                todo.sort(key=lambda p: min(math.dist(p["center"], q["center"]) for q in tree))
                p = todo.pop(0)
                if not route_pad(net, p, tree, tree_copper):
                    failures.append(f"{net}:{p['ref']}.{p['num']}")
                tree.append(p)
        # thin branches: keep trying every pending pad (a failed one may succeed once a
        # neighbour has joined the tree) until no more progress is made
        while deferred:
            progress = False
            for net, p in list(deferred):
                tree, tree_copper = trees[net]
                if route_pad(net, p, tree, tree_copper):
                    tree.append(p)
                    deferred.remove((net, p))
                    progress = True
            if not progress:
                failures += [f"{net}:{p['ref']}.{p['num']}" for net, p in deferred]
                break
        return failures

    # rip-up and reroute: nets that failed move to the front of the order and the
    # whole board is routed again, until everything completes (or passes run out)
    base_copper = list(copper)
    best = None
    for attempt in range(plan.get("ripup_passes", 10)):
        failures = route_all(order)
        length = sum(math.dist(t["a"], t["b"]) for t in out["tracks"])
        score = (len(failures), len(out["vias"]) * 2 + length)
        print(f"pass {attempt}: {len(failures)} failure(s) {failures}, "
              f"{len(out['vias'])} vias, {length:.0f} mm")
        if best is None or score < best[0]:
            best = (score, json.loads(json.dumps(out)), failures, list(order))
        if not failures:
            break
        bad = [f.split(":")[0] for f in failures]
        order = [n for n in order if n in bad] + [n for n in order if n not in bad]
    _, out, failures, order = best
    print("order", order)
    json.dump(out, open(out_json, "w"))
    print("tracks", len(out["tracks"]), "vias", len(out["vias"]), "failures", failures)


if __name__ == "__main__":
    main(*sys.argv[1:4])
