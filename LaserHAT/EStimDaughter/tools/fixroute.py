"""
Leftover router: finishes the few connections Freerouting leaves open (run by route_pcb.finish via DRC's list).
Grid maze search (Dijkstra, 0.05 mm cells, 8-neighbour moves, vias between F.Cu / In2.Cu / B.Cu; In1.Cu is the split
ground plane).  Obstacles are all other-net copper inflated by clearance + half the track width; the barrier rule areas
and the board edge are blocked.  A ground pad with no path to its plane is routed to the nearest legal via site.
"""
import heapq
import math
import re

import numpy as np
import pcbnew

STEP = 0.05
TRACK_W = 0.2
VIA_D, VIA_DRILL = 0.5, 0.3
CLR = 0.16                     # a hair over the 0.15 mm rule
EDGE = 0.32
VIA_COST = 12.0
LAYERS = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
mm = pcbnew.FromMM
T = pcbnew.ToMM


class Grid:
    def __init__(self, board, x0, x1, y0, y1, barriers):
        global LAYERS
        LAYERS = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if board.GetCopperLayerCount() == 4 else (pcbnew.F_Cu, pcbnew.B_Cu)
        self.b = board
        self.x0, self.y0 = x0, y0
        self.nx, self.ny = int(round((x1 - x0) / STEP)) + 1, int(round((y1 - y0) / STEP)) + 1
        xs = x0 + np.arange(self.nx) * STEP
        ys = y0 + np.arange(self.ny) * STEP
        self.X, self.Y = np.meshgrid(xs, ys, indexing="ij")
        self.edge = (self.X < x0 + EDGE) | (self.X > x1 - EDGE) | (self.Y < y0 + EDGE) | (self.Y > y1 - EDGE)
        self.edge_via = (self.X < x0 + VIA_D / 2 + 0.3) | (self.X > x1 - VIA_D / 2 - 0.3) | \
                        (self.Y < y0 + VIA_D / 2 + 0.3) | (self.Y > y1 - VIA_D / 2 - 0.3)
        self.bar = np.zeros_like(self.edge)
        for (a0, a1, b0, b1) in barriers:
            self.bar |= (self.X > a0 - TRACK_W / 2) & (self.X < a1 + TRACK_W / 2) & (self.Y > b0 - TRACK_W / 2) & (self.Y < b1 + TRACK_W / 2)
        r = VIA_D / 2 + 0.05
        self.bar_via = np.zeros_like(self.edge)
        for (a0, a1, b0, b1) in barriers:
            self.bar_via |= (self.X > a0 - r) & (self.X < a1 + r) & (self.Y > b0 - r) & (self.Y < b1 + r)

    def idx(self, x, y):
        return int(round((x - self.x0) / STEP)), int(round((y - self.y0) / STEP))

    def xy(self, i, j):
        return self.x0 + i * STEP, self.y0 + j * STEP

    def _win(self, xa, xb, ya, yb):
        i0, j0 = self.idx(xa, ya)
        i1, j1 = self.idx(xb, yb)
        return slice(max(i0, 0), min(i1 + 1, self.nx)), slice(max(j0, 0), min(j1 + 1, self.ny))

    def obstacles(self, net, infl):
        """per-layer boolean masks of cells whose centre is within `infl` of other-net copper"""
        m = {L: np.zeros((self.nx, self.ny), bool) for L in LAYERS}

        def seg(mask, ax, ay, bx, by, r):
            si, sj = self._win(min(ax, bx) - r, max(ax, bx) + r, min(ay, by) - r, max(ay, by) + r)
            X, Y = self.X[si, sj], self.Y[si, sj]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1) if L2 > 0 else 0
            d = np.hypot(X - (ax + t * dx), Y - (ay + t * dy))
            mask[si, sj] |= d < r

        for t in self.b.GetTracks():
            if t.GetNetname() == net:
                continue
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                for L in LAYERS:
                    seg(m[L], T(p.x), T(p.y), T(p.x), T(p.y), T(t.GetWidth(pcbnew.F_Cu)) / 2 + infl)
            elif t.GetLayer() in m:
                seg(m[t.GetLayer()], T(t.GetStart().x), T(t.GetStart().y), T(t.GetEnd().x), T(t.GetEnd().y), T(t.GetWidth()) / 2 + infl)
        for fp in self.b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == net and net:
                    continue
                bb = p.GetBoundingBox()
                a0, a1, b0, b1 = T(bb.GetLeft()), T(bb.GetRight()), T(bb.GetTop()), T(bb.GetBottom())
                si, sj = self._win(a0 - infl, a1 + infl, b0 - infl, b1 + infl)
                X, Y = self.X[si, sj], self.Y[si, sj]
                # rectangle distance (conservative for round pads)
                dx = np.maximum(np.maximum(a0 - X, X - a1), 0)
                dy = np.maximum(np.maximum(b0 - Y, Y - b1), 0)
                hit = np.hypot(dx, dy) < infl
                for L in LAYERS:
                    if p.IsOnLayer(L) or p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                        m[L][si, sj] |= hit
        return m

    def route(self, net, starts, goal_fn, via_ok_mask):
        """starts: set of (i, j, layer_index); goal_fn(i, j, li) -> bool.  Returns list of (i, j, li) or None."""
        track = self.obstacles(net, CLR + TRACK_W / 2)
        free = [~(track[L] | self.edge | self.bar) for L in LAYERS]
        dist, prev = {}, {}
        h = []
        for s in starts:
            dist[s] = 0.0
            heapq.heappush(h, (0.0, s))
        nb = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while h:
            d, cur = heapq.heappop(h)
            if d > dist.get(cur, 1e18):
                continue
            i, j, li = cur
            if cur not in starts and goal_fn(i, j, li):
                path = [cur]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return path[::-1]
            for di, dj, c in nb:
                a, b2 = i + di, j + dj
                if 0 <= a < self.nx and 0 <= b2 < self.ny and (free[li][a, b2] or (a, b2, li) in starts):
                    nxt = (a, b2, li)
                    nd = d + c
                    if nd < dist.get(nxt, 1e18):
                        dist[nxt], prev[nxt] = nd, cur
                        heapq.heappush(h, (nd, nxt))
            if via_ok_mask[i, j]:
                for lj in range(len(LAYERS)):
                    if lj != li:
                        nxt = (i, j, lj)
                        nd = d + VIA_COST
                        if nd < dist.get(nxt, 1e18):
                            dist[nxt], prev[nxt] = nd, cur
                            heapq.heappush(h, (nd, nxt))
        return None

    def via_mask(self, net, domain):
        vm = self.obstacles(net, CLR + VIA_D / 2)
        ok = ~(np.logical_or.reduce([vm[L] for L in LAYERS]) | self.edge_via | self.bar_via)
        for t in self.b.GetTracks():          # drill spacing to every via, same net included
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                ok &= np.hypot(self.X - T(p.x), self.Y - T(p.y)) >= 0.62
        if domain is not None:
            ok &= inside_poly(domain, self.X, self.Y)
        return ok

    def commit(self, path, net):
        """turn a cell path into tracks (collinear runs merged) and vias at layer changes"""
        ni = self.b.FindNet(net)
        added = 0
        run = [path[0]]

        def flush(run):
            nonlocal added
            if len(run) < 2:
                return
            pts = [run[0]]
            for k in range(1, len(run) - 1):
                a, b2, c = run[k - 1], run[k], run[k + 1]
                if (b2[0] - a[0], b2[1] - a[1]) != (c[0] - b2[0], c[1] - b2[1]):
                    pts.append(b2)
            pts.append(run[-1])
            for a, b2 in zip(pts, pts[1:]):
                tr = pcbnew.PCB_TRACK(self.b)
                tr.SetStart(pcbnew.VECTOR2I(mm(self.xy(a[0], a[1])[0]), mm(self.xy(a[0], a[1])[1])))
                tr.SetEnd(pcbnew.VECTOR2I(mm(self.xy(b2[0], b2[1])[0]), mm(self.xy(b2[0], b2[1])[1])))
                tr.SetWidth(mm(TRACK_W)); tr.SetLayer(LAYERS[a[2]]); tr.SetNet(ni)
                self.b.Add(tr); added += 1
        for k in range(1, len(path)):
            if path[k][2] != path[k - 1][2]:
                flush(run)
                v = pcbnew.PCB_VIA(self.b)
                x, y = self.xy(path[k][0], path[k][1])
                v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(ni)
                self.b.Add(v); added += 1
                run = [path[k]]
            else:
                run.append(path[k])
        flush(run)
        return added


def inside_poly(poly, X, Y):
    c = np.zeros(X.shape, bool)
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if y1 == y2:
            continue
        cond = ((y1 > Y) != (y2 > Y)) & (X < x1 + (Y - y1) * (x2 - x1) / (y2 - y1))
        c ^= cond
    return c


def item_cells(g, board, desc, x, y, net):
    """cells covered by the DRC item (pad or track) at (x, y)"""
    cells = set()
    p = pcbnew.VECTOR2I(mm(x), mm(y))
    if desc.startswith(("Pad", "PTH pad")):
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() == net and pad.HitTest(p, mm(0.01)):
                    bb = pad.GetBoundingBox()
                    a0, a1, b0, b1 = T(bb.GetLeft()), T(bb.GetRight()), T(bb.GetTop()), T(bb.GetBottom())
                    i0, j0 = g.idx(a0 + 0.05, b0 + 0.05)
                    i1, j1 = g.idx(a1 - 0.05, b1 - 0.05)
                    for li, L in enumerate(LAYERS):
                        if pad.IsOnLayer(L) or pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                            cells |= {(i, j, li) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
                    return cells
    if desc.startswith("Track"):
        best = None
        for t in board.GetTracks():
            if t.GetClass() != "PCB_VIA" and t.GetNetname() == net and t.HitTest(p, mm(0.02)):
                best = t
        if best is not None and best.GetLayer() in LAYERS:
            li = LAYERS.index(best.GetLayer())
            ax, ay, bx, by = T(best.GetStart().x), T(best.GetStart().y), T(best.GetEnd().x), T(best.GetEnd().y)
            n = max(2, int(math.hypot(bx - ax, by - ay) / STEP) + 1)
            for k in range(n):
                cells.add((*g.idx(ax + (bx - ax) * k / (n - 1), ay + (by - ay) * k / (n - 1)), li))
    if desc.startswith("Via"):
        for li in range(len(LAYERS)):
            cells.add((*g.idx(x, y), li))
    return cells


def fix(board, drc_txt, outline, barriers, domains):
    """route every non-zone unconnected pair in drc_txt; returns (fixed, failed)"""
    g = Grid(board, *outline, barriers)
    fixed, failed = [], []
    for blk in drc_txt.split("\n[")[1:]:
        if not blk.startswith("unconnected_items]"):
            continue
        items = re.findall(r"@\(([-0-9.]+) mm, ([-0-9.]+) mm\): (.*)", blk)
        if len(items) != 2:
            continue
        nets = [re.search(r"\[([^\]]+)\]", it[2]).group(1) for it in items]
        net = nets[0]
        zone = [("Zone" in it[2]) for it in items]
        if all(zone):
            continue
        if any(zone):      # pad/track to its ground zone: route to the nearest legal via site (the plane)
            it = items[zone.index(False)]
            starts = item_cells(g, board, it[2], float(it[0]), float(it[1]), net)
            vm = g.via_mask(net, domains.get(net))
            goal = lambda i, j, li: vm[i, j]
            path = g.route(net, starts, goal, vm) if starts else None
            if path:
                g.commit(path, net)
                i, j, _ = path[-1]
                v = pcbnew.PCB_VIA(board)
                x, y = g.xy(i, j)
                v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
                v.SetNet(board.FindNet(net)); board.Add(v)
                fixed.append(f"{it[2][:40]} -> plane")
            else:
                failed.append(it[2][:60])
            continue
        a = item_cells(g, board, items[0][2], float(items[0][0]), float(items[0][1]), net)
        b = item_cells(g, board, items[1][2], float(items[1][0]), float(items[1][1]), net)
        if not a or not b:
            failed.append(f"{net}: could not locate items")
            continue
        vm = g.via_mask(net, None)
        path = g.route(net, a, lambda i, j, li: (i, j, li) in b, vm)
        if path:
            g.commit(path, net)
            fixed.append(f"{net}: {items[0][2][:30]} <-> {items[1][2][:30]}")
        else:
            failed.append(f"{net}: no path")
    return fixed, failed
