#!/usr/bin/env python3
"""Dog-bone fan-out for the fine-pitch parts Freerouting keeps failing on: every netted pad of the listed footprints
gets a short outward stub and a via, alternately near and far so neighbouring vias stagger; all locked.  Runs as its
own pcbnew process between the rip and the DSN export (tools/autoroute.py stage "fanout").
    $KICAD_PY tools/fanout.py"""
import math
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "StimHAT.kicad_pcb")
FANOUT = {"U7": (0.45, 0.95), "U101": (0.45, 1.0)}        # via centre beyond the pad tip: near, far
SKIP_NETS = {"", "GND", "GND_ISO"}                           # the exposed pad and grounds are left to the router
STUB_W, VIA_D, VIA_DRILL = 0.2, 0.5, 0.3
mm = pcbnew.FromMM


def run(board):
    n = 0
    for ref, (near, far) in FANOUT.items():
        fp = board.FindFootprintByReference(ref)
        c = fp.GetPosition()
        pads = [p for p in fp.Pads() if p.GetNetname() not in SKIP_NETS and p.GetNumber() != "33"
                and not p.GetNetname().startswith("unconnected-")]
        # group by side so the alternation runs along each row
        rows = {}
        for p in pads:
            dx, dy = p.GetPosition().x - c.x, p.GetPosition().y - c.y
            side = ("E" if dx > 0 else "W") if abs(dx) >= abs(dy) else ("S" if dy > 0 else "N")
            rows.setdefault(side, []).append(p)
        for side, ps in rows.items():
            ps.sort(key=lambda p: (p.GetPosition().y if side in "EW" else p.GetPosition().x))
            ux, uy = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}[side]
            for i, p in enumerate(ps):
                bb = p.GetBoundingBox()
                tip = pcbnew.VECTOR2I(bb.GetRight() if ux > 0 else bb.GetLeft() if ux < 0 else p.GetPosition().x,
                                      bb.GetBottom() if uy > 0 else bb.GetTop() if uy < 0 else p.GetPosition().y)
                L = near if i % 2 == 0 else far
                end = pcbnew.VECTOR2I(int(p.GetPosition().x + ux * (abs(tip.x - p.GetPosition().x) + mm(L))) if ux else p.GetPosition().x,
                                      int(p.GetPosition().y + uy * (abs(tip.y - p.GetPosition().y) + mm(L))) if uy else p.GetPosition().y)
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(p.GetPosition().x, p.GetPosition().y)); t.SetEnd(end)
                t.SetWidth(mm(STUB_W)); t.SetLayer(pcbnew.F_Cu); t.SetNetCode(p.GetNetCode()); t.SetLocked(True)
                board.Add(t)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(end); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
                v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNetCode(p.GetNetCode()); v.SetLocked(True)
                board.Add(v)
                n += 1
    # thermal vias in the MCU's exposed GND pad: the only GND entry to the back under the fan-out ring
    fp = board.FindFootprintByReference("U7")
    pad33 = [p for p in fp.Pads() if p.GetNumber() == "33"][0]
    c = pad33.GetPosition()
    for dx, dy in ((-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(c.x + mm(dx), c.y + mm(dy))); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNetCode(pad33.GetNetCode()); v.SetLocked(True)
        board.Add(v); n += 1
    return n


if __name__ == "__main__":
    b = pcbnew.LoadBoard(BOARD)
    print("fan-out stubs + vias:", run(b))
    pcbnew.SaveBoard(BOARD, b)
