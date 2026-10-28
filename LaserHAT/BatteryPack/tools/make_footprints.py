#!/usr/bin/env python3
"""
Writes the project footprints in battpack.pretty from the manufacturers' drawings (all dimensions mm):
  Clip_MY-18650-01   MYOUNG MY-18650-01 (LCSC C2979183) 18650 clip + end contact: pins 1.8 mm holes, pair at 5.0 mm pitch,
                     third pin 7.6 mm outboard; two clips face each other 48.0 mm apart (pair row to pair row) for an 18650
                     (drawing WD-CP-0056: "L" = 48.00 mm, contact plate ~8.5 mm outboard of the pair row -> 65 mm cell length).
  SW_MTS-203         MTS-203 DPDT centre-off toggle (LCSC C55160018): 2 x 3 flat lugs, 4.7 mm pitch, rows 4.8 mm apart,
                     body 12.8 x 11.5 mm, M6 bushing (drawing CAX-MTS203M-YB-10.6JL, 2024-11-14).
  SW_MTS-202         the ON-ON version (rev D, C55159891): same lugs and body, ON / OFF silk.
  Relay_HFD2         Hongfa HFD2 DPDT signal relay (C18198081), 8 pins on a DIP-16 grid, body 20.2 x 10.2 x 10.6 mm.
  EL817S1            Everlight EL817S1 SMD opto-coupler (C2912100), 4 gull-wing leads at 2.54 mm, pads 11.06 mm outer span.
  XT60PW-M           not written here: a copy of KiCad's Connector_AMASS AMASS_XT60PW-M_1x02_P7.20mm_Horizontal with its 3D model
                     pointed at ${KIPRJMOD}/battpack.3dshapes/XT60PW-M.step (tools/make_xt60_model.py; KiCad 9 ships no model
                     for the horizontal part).
Run: python tools/make_footprints.py
"""
import os
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "battpack.pretty")


def U():
    return str(uuid.uuid4())


def F(v):
    return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def line(x1, y1, x2, y2, layer, w=0.1):
    return (f'  (fp_line (start {F(x1)} {F(y1)}) (end {F(x2)} {F(y2)}) (stroke (width {w}) (type solid)) '
            f'(layer "{layer}") (uuid "{U()}"))')


def rect(x1, y1, x2, y2, layer, w=0.1):
    return "\n".join([line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w),
                      line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)])


def text(name, value, x, y, layer, hide=False):
    return (f'  (property "{name}" "{value}" (at {F(x)} {F(y)} 0) (layer "{layer}"){" (hide yes)" if hide else ""} '
            f'(uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))')


def pad_th(num, x, y, drill, size, shape="circle"):
    return (f'  (pad "{num}" thru_hole {shape} (at {F(x)} {F(y)}) (size {F(size)} {F(size)}) (drill {F(drill)}) '
            f'(layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{U()}"))')


def pad_slot(num, x, y, dw, dh, pw, ph):
    return (f'  (pad "{num}" thru_hole oval (at {F(x)} {F(y)}) (size {F(pw)} {F(ph)}) (drill oval {F(dw)} {F(dh)}) '
            f'(layers "*.Cu" "*.Mask") (remove_unused_layers no) (uuid "{U()}"))')


def pad_npth_slot(x, y, w, h):
    return (f'  (pad "" np_thru_hole oval (at {F(x)} {F(y)}) (size {F(w)} {F(h)}) (drill oval {F(w)} {F(h)}) '
            f'(layers "*.Cu" "*.Mask") (uuid "{U()}"))')


def footprint(name, descr, tags, value, body, attr="through_hole"):
    return (f'(footprint "{name}" (version 20240108) (generator "battpack") (generator_version "9.0")\n'
            f'  (layer "F.Cu")\n  (descr "{descr}")\n  (tags "{tags}")\n'
            + text("Reference", "REF**", 0, -11, "F.SilkS") + "\n"
            + text("Value", value, 0, 11, "F.Fab") + "\n"
            + text("Footprint", "", 0, 0, "F.Fab", True) + "\n"
            + text("Datasheet", "", 0, 0, "F.Fab", True) + "\n"
            + text("Description", "", 0, 0, "F.Fab", True) + "\n"
            f'  (attr {attr})\n' + body + "\n)\n")


def clip():
    # origin = centre of the pin pair (the row nearest the cell); the third pin and the contact plate lie at -x,
    # the cell extends toward +x.  Mate: a second clip rotated 180 deg with its origin 48.0 mm away.
    b = [pad_th("1", 0, -2.5, 1.8, 2.8), pad_th("1", 0, 2.5, 1.8, 2.8), pad_th("1", -7.6, 0, 1.8, 2.8)]
    b.append(rect(-9.0, -8.5, 1.0, 8.5, "F.Fab"))                       # clip body (arms 16 +-1 wide, 9.6 deep)
    b.append(line(-8.5, -4.45, -8.5, 4.45, "F.Fab", 0.15))               # contact plate (8.9 wide)
    b.append(rect(-9.5, -9.0, 1.5, 9.0, "F.CrtYd", 0.05))
    b.append(line(-9.0, -8.7, 1.2, -8.7, "F.SilkS", 0.12))
    b.append(line(-9.0, 8.7, 1.2, 8.7, "F.SilkS", 0.12))
    b.append(line(-9.2, -8.7, -9.2, 8.7, "F.SilkS", 0.12))
    # cell silhouette (65 x 18.5 mm) on the user layer, from the plate face toward +x
    b.append(rect(-8.5, -9.25, 56.5, 9.25, "Cmts.User", 0.08))
    b.append(f'  (fp_text user "cell" (at 24 0 0) (layer "Cmts.User") (uuid "{U()}") (effects (font (size 1.5 1.5) (thickness 0.15))))')
    return footprint("Clip_MY-18650-01",
                     "MYOUNG MY-18650-01 18650 battery clip with end contact, THT, pair 48.0 mm apart (pin rows) for a 65 mm cell",
                     "18650 battery clip MYOUNG", "MY-18650-01", "\n".join(b))


def toggle():
    # MTS-203 DPDT centre-off toggle, vertical: 2 rows of 3 flat lugs (2.0 x 0.7 mm), 4.7 mm pitch, rows 4.8 mm apart.
    # Pins 1-2-3 (pole 1, 2 = common) in the +y row, 4-5-6 (pole 2, 5 = common) in the -y row.  Body 12.8 x 11.5 mm,
    # M6 bushing in the centre, lever about 19 mm above the board.  Lever toward pins 3/6 closes 1/4 (RUN) and vice versa.
    b = []
    for i, x in enumerate((-4.7, 0.0, 4.7)):
        b.append(pad_slot(str(i + 1), x, 2.4, 2.6, 1.1, 3.4, 1.9))
        b.append(pad_slot(str(i + 4), x, -2.4, 2.6, 1.1, 3.4, 1.9))
    b.append(rect(-6.4, -5.75, 6.4, 5.75, "F.Fab"))
    b.append(f'  (fp_circle (center 0 0) (end 3 0) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab") (uuid "{U()}"))')
    b.append(rect(-6.9, -6.25, 6.9, 6.25, "F.CrtYd", 0.05))
    b.append(rect(-6.6, -5.95, 6.6, 5.95, "F.SilkS", 0.12))
    b.append(f'  (fp_text user "1" (at -4.7 4.4 0) (layer "F.Fab") (uuid "{U()}") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    b.append(f'  (fp_text user "CHG" (at -7.8 0 90) (layer "F.SilkS") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))')
    b.append(f'  (fp_text user "RUN" (at 7.8 0 90) (layer "F.SilkS") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))')
    return footprint("SW_MTS-203",
                     "MTS-203 DPDT ON-OFF-ON toggle switch, vertical, 6 lugs on 4.7 x 4.8 mm, M6 bushing",
                     "toggle switch DPDT MTS-203", "MTS-203", "\n".join(b))


def toggle2():
    # MTS-202 DPDT ON-ON toggle: the same body and lugs as the MTS-203 (2 x 3 flat lugs, 4.7 mm pitch, rows 4.8 mm apart,
    # 12.8 x 11.5 mm, M6 bushing).  Lever toward pins 3/6 closes 1/4 (ON), toward 1/4 closes 3/6 (OFF: the throws are open).
    b = []
    for i, x in enumerate((-4.7, 0.0, 4.7)):
        b.append(pad_slot(str(i + 1), x, 2.4, 2.6, 1.1, 3.4, 1.9))
        b.append(pad_slot(str(i + 4), x, -2.4, 2.6, 1.1, 3.4, 1.9))
    b.append(rect(-6.4, -5.75, 6.4, 5.75, "F.Fab"))
    b.append(f'  (fp_circle (center 0 0) (end 3 0) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab") (uuid "{U()}"))')
    b.append(rect(-6.9, -6.25, 6.9, 6.25, "F.CrtYd", 0.05))
    b.append(rect(-6.6, -5.95, 6.6, 5.95, "F.SilkS", 0.12))
    b.append(f'  (fp_text user "1" (at -4.7 4.4 0) (layer "F.Fab") (uuid "{U()}") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    b.append(f'  (fp_text user "OFF" (at -7.8 0 90) (layer "F.SilkS") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))')
    b.append(f'  (fp_text user "ON" (at 7.8 0 90) (layer "F.SilkS") (uuid "{U()}") (effects (font (size 1 1) (thickness 0.15))))')
    return footprint("SW_MTS-202",
                     "MTS-202 DPDT ON-ON toggle switch, vertical, 6 lugs on 4.7 x 4.8 mm, M6 bushing",
                     "toggle switch DPDT MTS-202", "MTS-202", "\n".join(b))


def relay():
    # Hongfa HFD2 single-side-stable DPDT signal relay (drawing HFD2 2023 rev 1.00): body 20.2 x 10.2 x 10.6 mm, 8 pins
    # 0.5 x 0.25 on a DIP-16 grid (2.54 mm pitch, rows 7.62 apart), holes 1.0 mm.  Top view with the orientation mark at
    # the lower left: back row (-y) 1, 4, 6, 8 from the left; front row (+y) 16, 13, 11, 9.  1 / 16 coil, 4 / 13 commons,
    # 6 / 11 NC, 8 / 9 NO.  Origin at the body centre.
    b = []
    for num, col in (("1", 0), ("4", 3), ("6", 5), ("8", 7)):
        b.append(pad_th(num, -8.89 + 2.54 * col, -3.81, 1.0, 1.7, "circle" if num != "1" else "rect"))
    for num, col in (("16", 0), ("13", 3), ("11", 5), ("9", 7)):
        b.append(pad_th(num, -8.89 + 2.54 * col, 3.81, 1.0, 1.7))
    b.append(rect(-10.1, -5.1, 10.1, 5.1, "F.Fab"))
    b.append(rect(-10.6, -5.6, 10.6, 5.6, "F.CrtYd", 0.05))
    b.append(rect(-10.3, -5.3, 10.3, 5.3, "F.SilkS", 0.12))
    b.append(f'  (fp_circle (center -11.0 -3.81) (end -10.75 -3.81) (stroke (width 0.12) (type solid)) (fill solid) (layer "F.SilkS") (uuid "{U()}"))')   # pin 1 dot
    b.append(f'  (fp_text user "A" (at 3.81 -5.9 0) (layer "F.Fab") (uuid "{U()}") (effects (font (size 0.8 0.8) (thickness 0.12))))')
    return footprint("Relay_HFD2",
                     "Hongfa HFD2 DPDT signal relay, single side stable, 20.2 x 10.2 x 10.6 mm, DIP-16 grid",
                     "relay DPDT HFD2 signal", "HFD2", "\n".join(b))


def pad_smd(num, x, y, w, h):
    return (f'  (pad "{num}" smd roundrect (at {F(x)} {F(y)}) (size {F(w)} {F(h)}) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(roundrect_rratio 0.25) (uuid "{U()}"))')


def opto():
    # Everlight EL817S1 (SMD gull-wing 4-pin, datasheet rev 20 "Option S1"): body 6.5 x 4.58 mm, leads 2.54 pitch, lead span
    # 10.3 max; recommended pads 1.68 x 1.71 at 11.06 mm outer span (centres 9.38 apart).  Pin 1 = anode (dot), 2 = cathode
    # below it, 3 = emitter (bottom right), 4 = collector (top right).
    b = []
    for num, (x, y) in (("1", (-4.69, -1.27)), ("2", (-4.69, 1.27)), ("3", (4.69, 1.27)), ("4", (4.69, -1.27))):
        b.append(pad_smd(num, x, y, 1.9, 1.8))
    b.append(rect(-3.25, -2.3, 3.25, 2.3, "F.Fab"))
    b.append(rect(-5.9, -2.6, 5.9, 2.6, "F.CrtYd", 0.05))
    b.append(line(-3.4, -2.45, 3.4, -2.45, "F.SilkS", 0.12))
    b.append(line(-3.4, 2.45, 3.4, 2.45, "F.SilkS", 0.12))
    b.append(f'  (fp_circle (center -2.4 -1.4) (end -2.1 -1.4) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS") (uuid "{U()}"))')
    return footprint("EL817S1",
                     "Everlight EL817S1 opto-coupler, 4-pin SMD gull wing, 2.54 mm pitch, 6.5 x 4.58 mm body",
                     "optocoupler EL817 SMD", "EL817S1", "\n".join(b), attr="smd")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, txt in (("Clip_MY-18650-01", clip()), ("SW_MTS-203", toggle()), ("SW_MTS-202", toggle2()),
                      ("Relay_HFD2", relay()), ("EL817S1", opto())):
        p = os.path.join(OUT, name + ".kicad_mod")
        open(p, "w").write(txt)
        print("wrote", os.path.relpath(p))
