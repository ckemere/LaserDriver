#!/usr/bin/env python3
"""The output bus to J3, drawn by hand and pre-routed locked (2026-11-01): writes route/preroute.json, which
tools/autoroute.py lays down after its rip, before Freerouting sees the board.     python tools/j3_bus.py

J3 is on the right edge at the Pi's SE corner (pins x 93.21, y 69.5 +OUT .. 63.5 CAB).  Only three nets leave it:
+OUT to chain B just below, -V to chain A (bottom left) and CAB (the interlock sense) to both chains; 0V reaches J3
through the B.Cu plane.  Left to the router, the long ones cut through the middle of the board (on the 4-layer version
they split the In2 rail pours; on 2 layers they would cut the 0V plane), so they run on B.Cu along the board's "basement", below the gauges and the XT60 / toggle pins (y 87.8 / 89.2, inside the notch
edges at y 90), the right edge (x 97.1 / 98.6) taking them down from J3:
  CAB     J3.4 east to x 98.6 (outer), down, west along y 89.2 to x 21.6, up, via, F.Cu to Q26.2; a branch at x 78.6 via
          to F.Cu up to Q22.2
  -V      J3.3 east to x 97.1 (inner), down, west along y 87.8 to x 23.6, up, via, F.Cu to Q11.3
  +OUT    J3.1 down x 93.21 to y 80.3, west, via, F.Cu to Q1.3
R53 / R54 (the other +OUT loads) and J3.2 (0V) are left to the router.  Power class: 0.8 mm tracks, 0.9 / 0.45 vias.
The chain FETs' rotations are LOCKED in tools/place.py so these pad coordinates hold."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "route", "preroute.json")
W, VIA, DRILL = 0.8, 0.9, 0.45

PATHS = [   # (net, layer, points)
    ("/CAB", "B", [(93.21, 63.5), (98.6, 63.5), (98.6, 89.2), (21.6, 89.2), (21.6, 86.55)]),
    ("/CAB", "F", [(21.6, 86.55), (19.9375, 86.55)]),
    ("/CAB", "F", [(78.6, 89.2), (78.6, 86.5625), (80.05, 86.5625)]),
    ("/-V", "B", [(93.21, 65.5), (97.1, 65.5), (97.1, 87.8), (23.6, 87.8), (23.6, 83.4375)]),
    ("/-V", "F", [(23.6, 83.4375), (19.0, 83.4375)]),
    ("+OUT", "B", [(93.21, 69.5), (93.21, 80.3), (87.0625, 80.3)]),
    ("+OUT", "F", [(87.0625, 80.3), (87.0625, 82.5)]),
]
VIAS = [("/CAB", (21.6, 86.55)), ("/CAB", (78.6, 89.2)), ("/-V", (23.6, 83.4375)), ("+OUT", (87.0625, 80.3))]

tracks = [dict(net=n, layer=lay, a=list(a), b=list(b), w=W) for n, lay, pts in PATHS for a, b in zip(pts, pts[1:])]
vias = [dict(net=n, at=list(p), d=VIA, drill=DRILL) for n, p in VIAS]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(dict(tracks=tracks, vias=vias), open(OUT, "w"), indent=1)
print("wrote", OUT, len(tracks), "tracks,", len(vias), "vias")
