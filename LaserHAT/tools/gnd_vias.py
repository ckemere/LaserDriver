#!/usr/bin/env python3
"""Hand-style ground connections before autorouting (KiCad bundled Python).

    $KICAD_PY tools/gnd_vias.py board.kicad_pcb [NET ...]

For every top-side SMD pad on the given nets (default GND) that is not a
through-hole pad, drop a via to the inner/bottom pour right next to the pad
(first free spot, searching from the direction of the board centre) plus a short
track.  Special case: the MCU exposed pad gets a 2x2 via-in-pad array and VSS
(pin 5) is tied into it.  Everything added is locked so freerouting keeps it.
"""
import math
import sys

import pcbnew

MM = pcbnew.FromMM
VIA_D, VIA_DRILL, TRACK_W, CLEAR = 0.6, 0.3, 0.3, 0.22
EPAD = ("U7", "33")
VSS_TIE = ("U7", "5")


def v(x, y):
    return pcbnew.VECTOR2I(int(x), int(y))


def main(path, nets):
    board = pcbnew.LoadBoard(path)
    edge = board.GetBoardEdgesBoundingBox()
    net_items = {n: board.FindNet(n) for n in nets}
    # obstacles: every pad (with its net) and every existing via/track
    obstacles = []
    fps = list(board.GetFootprints())
    for f in fps:
        for p in f.Pads():
            bb = p.GetBoundingBox()
            # same-net SMD pads may be touched; through-hole pads never (no via-in-TH-pad)
            obstacles.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom(), p.GetNetname(),
                              p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD))
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    for tr in board.GetTracks():           # hand-routed copper is an obstacle too
        bb = tr.GetBoundingBox()
        obstacles.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom(), tr.GetNetname(),
                          tr.GetClass() == "PCB_VIA"))

    def free(x, y, r, net):
        c = MM(CLEAR)
        for (x0, y0, x1, y1, n, is_via) in obstacles:
            if n == net and not is_via:
                continue
            dx = max(x0 - x, 0, x - x1)
            dy = max(y0 - y, 0, y - y1)
            if math.hypot(dx, dy) < r + c:
                return False
        if not (edge.GetX() + MM(0.8) < x < edge.GetRight() - MM(0.8) and
                edge.GetY() + MM(0.8) < y < edge.GetBottom() - MM(0.8)):
            return False
        for d in edges:
            if d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
                a, b = d.GetStart(), d.GetEnd()
                ax, ay, bx, by = a.x, a.y, b.x, b.y
                L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1
                t = max(0, min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
                if math.hypot(x - (ax + t * (bx - ax)), y - (ay + t * (by - ay))) < r + MM(0.5):
                    return False
        return True

    def add_via(x, y, net):
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(v(x, y))
        via.SetWidth(MM(VIA_D))
        via.SetDrill(MM(VIA_DRILL))
        via.SetNet(net)
        via.SetLocked(True)
        board.Add(via)
        obstacles.append((x - MM(VIA_D / 2), y - MM(VIA_D / 2), x + MM(VIA_D / 2), y + MM(VIA_D / 2),
                          net.GetNetname(), True))

    def add_track(a, b, net, w=TRACK_W):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a)
        t.SetEnd(b)
        t.SetWidth(MM(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        t.SetLocked(True)
        board.Add(t)

    added, failed = 0, []
    for f in fps:
        fc = f.GetPosition()
        for p in f.Pads():
            name = p.GetNetname()
            if name not in net_items or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            if not p.IsOnLayer(pcbnew.F_Cu):
                continue          # bottom pads sit directly on the bottom pour
            net = net_items[name]
            key = (f.GetReference(), p.GetNumber())
            pc = p.GetPosition()
            if key == EPAD:
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        add_via(pc.x + sx * MM(0.65), pc.y + sy * MM(0.65), net)
                added += 4
                continue
            if key == VSS_TIE:
                epad = next(q for q in f.Pads() if q.GetNumber() == EPAD[1])
                ec = epad.GetPosition()
                add_track(pc, v(ec.x, pc.y) if abs(pc.y - ec.y) < abs(pc.x - ec.x) else v(pc.x, ec.y),
                          net, 0.25)
                added += 1
                continue
            bb = p.GetBoundingBox()
            half = max(bb.GetWidth(), bb.GetHeight()) / 2
            # search starts pointing at the board centre: the main pour is reliably there,
            # whereas vias pushed toward edges/corners tend to end up walled off
            bc = edge.GetCenter()
            base = math.atan2(bc.y - pc.y, bc.x - pc.x)
            done = False
            for dist_mm in (0.3, 0.45, 0.55, 0.8, 1.1, 1.5):   # close-in first (may touch its own pad)
                # try straight outward first, then fan out alternately +/- 22.5 deg steps
                for k in range(16):
                    ang = base + ((k + 1) // 2) * (math.pi / 8) * (1 if k % 2 else -1)
                    d = half + MM(dist_mm)
                    x, y = pc.x + d * math.cos(ang), pc.y + d * math.sin(ang)
                    # the via site and the whole stub from the pad must clear other nets
                    n = max(2, int(d / MM(0.1)))
                    path_ok = all(free(pc.x + (x - pc.x) * i / n, pc.y + (y - pc.y) * i / n,
                                       MM(TRACK_W / 2), name) for i in range(1, n))
                    if path_ok and free(x, y, MM(VIA_D / 2), name):
                        add_via(x, y, net)
                        add_track(pc, v(x, y), net)
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                failed.append("%s.%s" % key)
    pcbnew.SaveBoard(path, board)
    print("added", added, "ground connections; no room at:", failed)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or ["GND"])
