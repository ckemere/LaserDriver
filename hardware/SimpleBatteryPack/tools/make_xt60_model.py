#!/usr/bin/env python3
"""
3D model for battpack.pretty/XT60PW-M.kicad_mod (Amass XT60PW-M horizontal XT60, LCSC C98732): KiCad 9 ships models
for the vertical XT60-M / XT60-F but none for the horizontal PW part.  The nose (front 12 mm) is KiCad's vertical XT60-M housing
(the same plug body: 15.5 x 8.1 mm section, D-chamfers at the pin-1 "-" end) laid on its side with the plug face at the
footprint's front edge (fab outline y = -16.35); behind it a plain full-width block to the fab outline and the PW's
rear pin block, two bent pins (3.5 mm
bullets, 2.5 mm tails through the board) and the two retention legs, after Amass drawing XT60PW-M30 (2025V0: 18.2 x
15.5 x 8.4 mm, pin holes 2 x 2.9 at 7.2 mm, legs 0.8 x 1.9 at 13.5 mm, 6.0 mm ahead of the pins).
Model coordinates = footprint x, footprint y mirrored (KiCad's 3D y axis points to the footprint's -y), z up from the
board surface, mm.  Writes battpack.3dshapes/XT60PW-M.step with colours.
    pip install cadquery  (any python >= 3.10; not KiCad's)  ->  python tools/make_xt60_model.py
"""
import os

import cadquery as cq

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "battpack.3dshapes", "XT60PW-M.step")
SRC = "/usr/share/kicad/3dmodels/Connector_AMASS.3dshapes/AMASS_XT60-M_1x02_P7.2mm_Vertical.step"
PITCH, Z_PIN, FACE_Y = 7.2, 4.05, 16.35               # pin pitch, pin axis height (housing mid-height), plug face

src = cq.importers.importStep(SRC)
housing = max(src.solids().vals(), key=lambda v: v.Volume())      # x -4.15..11.35, y +-4.05, z 0..16 (face at z 16)
# lay it down: (x, y, z) -> (x, z, -y), face toward +y, base on the board
h = cq.Workplane("XY").add(housing).rotate((0, 0, 0), (1, 0, 0), -90).translate((0, FACE_Y - 16.0, 4.05))
nose = h.intersect(cq.Workplane("XY").box(20, 12.0, 10, centered=(True, False, False)).translate((PITCH / 2, FACE_Y - 12.0, -1)))
body = cq.Workplane("XY").box(15.5, 2.5, 8.1, centered=(True, False, False)).translate((PITCH / 2, FACE_Y - 12.1, 0))   # plain block behind the nose (fab outline)
rear = cq.Workplane("XY").box(7.5, 2.85, 7.0, centered=(True, False, False)).translate((PITCH / 2, -1.85, 0))         # pin block
housing_pw = nose.union(body).union(rear)

pins = None
for x in (0.0, PITCH):
    bullet = cq.Solid.makeCylinder(1.75, 12.0, cq.Vector(x, 3.0, Z_PIN), cq.Vector(0, 1, 0))     # y 3 .. 15 (1.35 in from the face)
    tail_h = cq.Solid.makeCylinder(1.25, 3.5, cq.Vector(x, -0.5, Z_PIN), cq.Vector(0, 1, 0))     # y -0.5 .. 3
    tail_v = cq.Solid.makeCylinder(1.25, Z_PIN + 3.5, cq.Vector(x, 0, -3.5), cq.Vector(0, 0, 1))  # z -3.5 .. pin axis
    p = cq.Workplane("XY").add(bullet).union(cq.Workplane("XY").add(tail_h)).union(cq.Workplane("XY").add(tail_v))
    pins = p if pins is None else pins.union(p)

legs = None
for x in (-3.15, PITCH + 3.15):
    leg = cq.Workplane("XY").box(0.5, 1.5, 3.0).translate((x, 6.0, -1.0))                      # z -2.5 .. 0.5
    legs = leg if legs is None else legs.union(leg)

a = cq.Assembly(name="XT60PW-M")
a.add(housing_pw, name="housing", color=cq.Color(0.93, 0.78, 0.12))
a.add(pins, name="pins", color=cq.Color(0.83, 0.69, 0.22))
a.add(legs, name="legs", color=cq.Color(0.75, 0.75, 0.75))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
a.save(OUT)
bb = housing_pw.val().BoundingBox()
print(f"wrote {OUT}: housing x {bb.xmin:.2f}..{bb.xmax:.2f} y {bb.ymin:.2f}..{bb.ymax:.2f} z {bb.zmin:.2f}..{bb.zmax:.2f}")
