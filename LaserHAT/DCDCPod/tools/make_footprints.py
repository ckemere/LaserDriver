#!/usr/bin/env python3
"""Project footprints into dcdcpod.pretty (plain text edits, no pcbnew needed):
  * DCDC_SIP6_RB0515D: the RECOM RB-0515D/HP SIP (body 19.6 x 6.0 x 10.2 on 0.5 mm standoffs, pin row 1.27 mm behind /
    4.73 mm in front of the marked face, 1.6 mm pads, pins 1 2 4 5 6 on 2.54 mm) with its VRML model in dcdcpod.3dshapes
  * PinHeader_1x02_P2.54mm_Horizontal_Pod, PinHeader_1x04_P2.00mm_Horizontal_Pod: KiCad's right-angle pin headers with
    the silk / fab drawing of the pins beyond the body removed (on the pod they hang over the bottom edge into the HAT,
    and silk crossing Edge.Cuts is a DRC warning) and the silk pin-1 corner mark removed (the square pad marks pin 1;
    the pod's pin-name silk sits where the mark was), and mirrored along the pin row (y -> (N - 1) * pitch - y,
    2026-10-30): pad 1 (square) is then at the far end of the row and pad N at the footprint origin.  The pod faces south
    since 2026-10-30, and a right-angle header on the front with its pins pointing at the bottom edge (rot 270) numbers
    its pins westward; mirrored, the numbers increase eastward on the HAT (J1.1 = 5 V on J103.1 at HAT x 19, J2.1 = CAB
    on HAT x 38 ... J2.4 = +V on 44) and the schematic keeps its pin -> net table.  The header is symmetric about the
    middle of its row, so the 3D model is unchanged
    python tools/make_footprints.py"""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = os.path.join(ROOT, "dcdcpod.pretty")
KICAD_FP = next(d for d in ("/usr/share/kicad/footprints", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
                if os.path.isdir(d))
os.makedirs(LIB, exist_ok=True)

# ---- RECOM RB-0515D/HP SIP-7 (the fitted part; pin-compatible with the Mornsun A0515S-1WR3 the pod was first drawn for).
# RECOM RB series drawing: body 19.6 x 6.0 x 10.2 on 0.5 mm standoffs, pins 0.51 x 0.25 on 2.54 mm (positions 1 2 4 5 6,
# no pin 3), pin 1 2.0 mm from the left end, the pin row 1.27 mm from the unmarked back face and 4.73 mm from the marked
# face; pin 1 on the left when the marked face is viewed with the pins down.  Footprint frame: pin 1 at the origin, pins
# along +x, marked face toward +y (KiCad's PCB top view = the datasheet's "Top View").  Holes 1.0 mm (+0.15/-0), 1.6 mm
# pads (0.3 mm annulus leaves room for a track between pins 1 and 2).
NAME = "DCDC_SIP6_RB0515D"
BX0, BX1, BY0, BY1 = -2.0, 17.6, -1.27, 4.73
PINS = (("1", 0.0), ("2", 2.54), ("4", 7.62), ("5", 10.16), ("6", 12.70))


def rect(x0, y0, x1, y1, layer, w):
    return (f'\t(fp_rect (start {x0:g} {y0:g}) (end {x1:g} {y1:g}) (stroke (width {w:g}) (type solid)) (fill no) '
            f'(layer "{layer}"))\n')


fp = ['(footprint "%s" (version 20240108) (generator "make_footprints") (generator_version "9.0") (layer "F.Cu")' % NAME,
      '\t(descr "RECOM RB-0515D/HP (SIP-7, 1 W isolated DC-DC 5 V to +/-15 V): body 19.6 x 6.0 x 10.2 mm on 0.5 mm '
      'standoffs, pin row 1.27 mm from the back face / 4.73 mm from the marked face (RECOM RB drawing), marked face toward '
      '+Y, pin 1 left; also fits the Mornsun A0515S-1WR3 (pins 0.9 / 5.1)")',
      '\t(tags "DC-DC SIP RECOM RB-0515D")',
      '\t(attr through_hole)',
      f'\t(property "Reference" "REF**" (at 7.62 -2.2 0) (layer "F.SilkS") (hide yes) (effects (font (size 1 1) (thickness 0.15))))',
      f'\t(property "Value" "RB-0515D/HP" (at 7.62 5.9 0) (layer "F.Fab") (hide yes) (effects (font (size 1 1) (thickness 0.15))))',
      f'\t(property "Footprint" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))',
      f'\t(property "Datasheet" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))',
      f'\t(property "Description" "" (at 0 0 0) (layer "F.Fab") (hide yes) (effects (font (size 1.27 1.27) (thickness 0.15))))',
      rect(BX0, BY0, BX1, BY1, "F.Fab", 0.1).rstrip("\n"),
      '\t(fp_text user "marked face" (at 7.62 4.0 0) (layer "F.Fab") (effects (font (size 0.6 0.6) (thickness 0.1))))',
      rect(BX0 - 0.12, BY0 - 0.12, BX1 + 0.12, BY1 + 0.12, "F.SilkS", 0.12).rstrip("\n"),
      '\t(fp_line (start -2.6 -1.0) (end -2.6 1.0) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))',   # pin-1 mark
      rect(BX0 - 0.25, BY0 - 0.25, BX1 + 0.25, BY1 + 0.25, "F.CrtYd", 0.05).rstrip("\n")]
for n, x in PINS:
    shape = "rect" if n == "1" else "circle"
    fp.append(f'\t(pad "{n}" thru_hole {shape} (at {x:g} 0) (size 1.6 1.6) (drill 1.0) (layers "*.Cu" "*.Mask") (remove_unused_layers no))')
fp.append(f'\t(model "${{KIPRJMOD}}/dcdcpod.3dshapes/{NAME}.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))')
fp.append(")")
open(os.path.join(LIB, NAME + ".kicad_mod"), "w").write("\n".join(fp) + "\n")


def _box(x0, y0, z0, x1, y1, z1, rgb):
    """VRML box in KiCad's model units (0.1 in); the model frame has Y = board -y"""
    k = 2.54
    return ("Transform { translation %.4f %.4f %.4f children [ Shape { appearance Appearance { material Material { "
            "diffuseColor %s } } geometry Box { size %.4f %.4f %.4f } } ] }\n"
            % ((x0 + x1) / 2 / k, -(y0 + y1) / 2 / k, (z0 + z1) / 2 / k, rgb, (x1 - x0) / k, (y1 - y0) / k, (z1 - z0) / k))


wrl = "#VRML V2.0 utf8\n" + _box(BX0, BY0, 0.5, BX1, BY1, 10.7, "0.12 0.12 0.12")        # 10.2 body on 0.5 mm standoffs
for _, px in PINS:
    wrl += _box(px - 0.255, -0.125, -4.1, px + 0.255, 0.125, 0.5, "0.8 0.8 0.8")           # 0.51 x 0.25 pins, 4.1 mm long
wrl += _box(-0.5, BY1, 1.8, 0.5, BY1 + 0.1, 2.8, "1 1 1")                                 # pin-1 dot on the marked face
os.makedirs(os.path.join(ROOT, "dcdcpod.3dshapes"), exist_ok=True)
open(os.path.join(ROOT, "dcdcpod.3dshapes", NAME + ".wrl"), "w").write(wrl)
print(f"wrote {NAME} (+ wrl)")
for stale in ("DCDC_SIP6_A0515S_BodyN.kicad_mod",):
    if os.path.exists(os.path.join(LIB, stale)):
        os.remove(os.path.join(LIB, stale))
if os.path.exists(os.path.join(ROOT, "dcdcpod.3dshapes", "DCDC_SIP6_A0515S_BodyN.wrl")):
    os.remove(os.path.join(ROOT, "dcdcpod.3dshapes", "DCDC_SIP6_A0515S_BodyN.wrl"))


def blocks(text):
    """split a footprint file into its top-level (...) items (after the header line)"""
    items, depth, start, q = [], 0, None, False
    for i, c in enumerate(text):
        if c == '"' and text[i - 1] != "\\":
            q = not q
        elif not q:
            if c == "(":
                if depth == 1:
                    start = i
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 1 and start is not None:
                    items.append(text[start:i + 1]); start = None
    return items


def mirror_row(text, length):
    """mirror every (at x y ...), (start x y) and (end x y) about the middle of the pin row (y -> length - y)"""
    def f(m):
        y = round(length - float(m.group(3)), 6)
        return f"{m.group(1)}{m.group(2)} {y:g}"
    return re.sub(r"(\((?:at|start|end)\s+)(-?[\d.]+)\s+(-?[\d.]+)", f, text)


def strip_pins(lib, name, body_end, row_length):
    """drop F.SilkS / F.Fab lines and rects that lie entirely beyond the body end (the pins), then mirror the row"""
    text = open(os.path.join(KICAD_FP, lib + ".pretty", name + ".kicad_mod")).read()
    head = text[:text.index("\n") + 1]
    keep, dropped = [], 0
    for it in blocks(text):
        if it.startswith(("(fp_line", "(fp_rect")) and ('"F.SilkS"' in it or '"F.Fab"' in it):
            xs = [float(m.group(1)) for m in re.finditer(r"\((?:start|end)\s+(-?[\d.]+)\s+-?[\d.]+\)", it)]
            if min(xs) >= body_end - 0.01 or ('"F.SilkS"' in it and max(xs) <= 0.01):   # pins, and the pin-1 corner mark
                dropped += 1
                continue
        if it.startswith("(footprint "):
            continue
        it = it.replace(f'"{name}"', f'"{name}_Pod"')
        keep.append(it)
    out = head.replace(f'"{name}"', f'"{name}_Pod"') + "\n".join("\t" + k for k in keep) + "\n)\n"
    out = mirror_row(out, row_length)
    out = out.replace('(descr "', '(descr "DC-DC pod copy, pin drawing beyond the body removed, pin numbering mirrored '
                                  '(pad 1 at the far end of the row); ')
    open(os.path.join(LIB, name + "_Pod.kicad_mod"), "w").write(out)
    print(f"wrote {name}_Pod: dropped {dropped} pin graphics")


strip_pins("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Horizontal", 4.15, 2.54)
strip_pins("Connector_PinHeader_2.00mm", "PinHeader_1x04_P2.00mm_Horizontal", 3.11, 6.0)
