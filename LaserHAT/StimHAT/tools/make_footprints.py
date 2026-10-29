#!/usr/bin/env python3
"""Project footprints into stimhat.pretty:
  * VQFN32_RHB_TEX: the MSPM0G3507 footprint copied out of the Rev 2 HAT board (its library, ELEC327-Kicad, is not in
    this repository)
  * SW_ALPS_SKRHADE010: ALPS SKRHADE010 five-way switch from the ALPS land-pattern drawing (2026-10-29): six 1.35 x 1.0 mm
    signal pads in two columns 5.8 mm apart (inner edges; pitch 1.85 mm), two 2.0 x 1.8 mm anchor pads top and bottom
    (inner edges 6.3 mm apart), guide-boss holes 0.75 and 1.05 mm.  Pins: 1 A, 2 centre, 3 C (left column, top to bottom),
    4 B, 5 common, 6 D (right column).  Mounted at 45 degrees so the stem's four directions line up with the board.
Run with KiCad's Python:  $KICAD_PY tools/make_footprints.py"""
import os

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = os.path.join(ROOT, "stimhat.pretty")
HAT = os.path.join(ROOT, "..", "LaserDriver.kicad_pcb")
mm = pcbnew.FromMM
io = pcbnew.PCB_IO_KICAD_SEXPR()
os.makedirs(LIB, exist_ok=True)

# ---- MSPM0 VQFN-32 from the HAT board
hat = pcbnew.LoadBoard(HAT)
u7 = hat.FindFootprintByReference("U7")
fp = pcbnew.FOOTPRINT(u7)
fp.SetPosition(pcbnew.VECTOR2I(0, 0))
fp.SetOrientationDegrees(0)
fp.SetReference("REF**"); fp.SetValue("MSPM0G1507SRHBR")
fp.SetFPID(pcbnew.LIB_ID("stimhat", "VQFN32_RHB_TEX"))
for pad in fp.Pads():
    pad.SetNet(None)
io.FootprintSave(LIB, fp)
print("saved VQFN32_RHB_TEX:", len(list(fp.Pads())), "pads")

# ---- ALPS SKRHADE010
j = pcbnew.FOOTPRINT(pcbnew.BOARD())
j.SetFPID(pcbnew.LIB_ID("stimhat", "SW_ALPS_SKRHADE010"))
j.SetReference("REF**"); j.SetValue("SKRHADE010")
j.SetAttributes(pcbnew.FP_SMD)
j.SetLibDescription("ALPS SKRHADE010 4-direction + centre-push switch, 7.5 x 7.5 mm, SMD; mount at 45 deg")


def smd(num, x, y, w, h):
    p = pcbnew.PAD(j)
    p.SetNumber(str(num)); p.SetShape(pcbnew.PAD_SHAPE_RECT); p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    p.SetSize(pcbnew.VECTOR2I(mm(w), mm(h))); p.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    p.SetLayerSet(pcbnew.LSET.FromHex("0" * 0 + pcbnew.LSET(pcbnew.F_Cu).FmtHex()) if False else pcbnew.PAD.SMDMask())
    j.Add(p)


def npth(x, y, d):
    p = pcbnew.PAD(j)
    p.SetNumber(""); p.SetShape(pcbnew.PAD_SHAPE_CIRCLE); p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetSize(pcbnew.VECTOR2I(mm(d), mm(d))); p.SetDrillSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    j.Add(p)


X = 5.8 / 2 + 1.35 / 2           # signal pad centre, 3.575
for num, y in ((1, -1.85), (2, 0.0), (3, 1.85)):
    smd(num, -X, y, 1.35, 1.0)
for num, y in ((4, -1.85), (5, 0.0), (6, 1.85)):
    smd(num, X, y, 1.35, 1.0)
smd("MP1", 0, -(6.3 / 2 + 0.9), 2.0, 1.8)      # anchors (no net)
smd("MP2", 0, (6.3 / 2 + 0.9), 2.0, 1.8)
npth(0, -1.05, 0.75)
npth(0, 1.10, 1.05)
for (x1, y1, x2, y2) in ((-3.75, -3.75, 3.75, -3.75), (3.75, -3.75, 3.75, 3.75), (3.75, 3.75, -3.75, 3.75), (-3.75, 3.75, -3.75, -3.75)):
    s = pcbnew.PCB_SHAPE(j); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.F_Fab); s.SetWidth(mm(0.1))
    s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2))); j.Add(s)
for (x1, y1, x2, y2) in ((-5.0, -5.0, 5.0, -5.0), (5.0, -5.0, 5.0, 5.0), (5.0, 5.0, -5.0, 5.0), (-5.0, 5.0, -5.0, -5.0)):
    s = pcbnew.PCB_SHAPE(j); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.F_CrtYd); s.SetWidth(mm(0.05))
    s.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); s.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2))); j.Add(s)
io.FootprintSave(LIB, j)
print("saved SW_ALPS_SKRHADE010:", len(list(j.Pads())), "pads")

import subprocess
subprocess.run(["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "silk_dedupe.py"),
                os.path.join(LIB, "VQFN32_RHB_TEX.kicad_mod")], check=True)   # TI ships the pin-1 star twice

# A0515S SIP-6 with the body on the other side of the pin row (the module turned over about the pin axis), so that it
# stands in the band north of the BNC bodies with its body south of the pin row.  Pure text mirror of the e-stim
# module's footprint (y -> -y for the graphics; the pads stay on y 0, pin order unchanged), body 0.9 / 5.1 mm from the
# pin row per the Mornsun drawing, 1.6 mm pads; no 3D model.
import re as _re
src = open(os.path.join(ROOT, "..", "EStimDaughter", "estim.pretty", "DCDC_SIP6_A0515S.kicad_mod")).read()
out = []
for line in src.splitlines():
    if line.strip().startswith("(model "):
        continue
    if line.strip().startswith(("(fp_line", "(fp_text", "(property")):
        line = _re.sub(r"\((start|end|at) (-?[\d.]+) (-?[\d.]+)", lambda m: f"({m.group(1)} {m.group(2)} {-float(m.group(3)):g}", line)
    if line.strip().startswith("(fp_line"):      # body 0.9 mm behind the pin row, 5.1 ahead (Mornsun A_S-1WR3 drawing)
        line = _re.sub(r"\((start|end) (-?[\d.]+) (-?[\d.]+)", lambda m: f"({m.group(1)} {m.group(2)} {float(m.group(3)) - 0.2:g}", line)
    line = line.replace('(footprint "DCDC_SIP6_A0515S"', '(footprint "DCDC_SIP6_A0515S_BodyN"')
    line = line.replace("(size 1.8 1.8) (drill 1.0)", "(size 1.6 1.6) (drill 1.0)")   # 0.3 mm annulus: room between pins 1 and 2 for a track
    line = line.replace('(descr "Isolated DC-DC,', '(descr "Body on the other side of the pin row (turned over about the pin axis). Isolated DC-DC,')
    out.append(line)
# 3D model (VRML, KiCad units of 0.1 in): body 19.65 x 6.00 x 10.16 on a 0.5 mm standoff, pins, white pin-1 dot on the
# marked face (the face 5.1 mm from the pin row, board +y); KiCad's model frame has Y = board -y
def _box(x0, y0, z0, x1, y1, z1, rgb):
    k = 2.54
    return ("Transform { translation %.4f %.4f %.4f children [ Shape { appearance Appearance { material Material { "
            "diffuseColor %s } } geometry Box { size %.4f %.4f %.4f } } ] }\n"
            % ((x0 + x1) / 2 / k, -(y0 + y1) / 2 / k, (z0 + z1) / 2 / k, rgb, (x1 - x0) / k, (y1 - y0) / k, (z1 - z0) / k))
wrl = "#VRML V2.0 utf8\n" + _box(-2.21, -0.9, 0.5, 17.44, 5.1, 10.66, "0.12 0.12 0.12")
for px in (0.0, 2.54, 7.62, 10.16, 12.7):
    wrl += _box(px - 0.25, -0.25, -1.6, px + 0.25, 0.25, 0.5, "0.8 0.8 0.8")
wrl += _box(-1.2, 5.1, 1.2, -0.4, 5.2, 2.0, "1 1 1")
os.makedirs(os.path.join(ROOT, "stimhat.3dshapes"), exist_ok=True)
open(os.path.join(ROOT, "stimhat.3dshapes", "DCDC_SIP6_A0515S_BodyN.wrl"), "w").write(wrl)
assert out[-1].strip() == ")"
out.insert(len(out) - 1, '  (model "${KIPRJMOD}/stimhat.3dshapes/DCDC_SIP6_A0515S_BodyN.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))')
open(os.path.join(LIB, "DCDC_SIP6_A0515S_BodyN.kicad_mod"), "w").write("\n".join(out) + "\n")
print("saved DCDC_SIP6_A0515S_BodyN (+ wrl)")


# Right-angle-only BNC (Amphenol 031-5540 / 031-5431 / 031-5486): the HAT's dual footprint without the vertical
# 031-5539's diagonal post pad, its body drawing and its courtyard; silk kept inside the board edge.  Pure text edit.
def _drop_block(text, marker):
    """remove the s-expression block that contains MARKER (search back to its opening '(pad' / '(fp_rect')"""
    i = text.index(marker)
    start = max(text.rfind("\n\t(pad ", 0, i), text.rfind("\n\t(fp_rect", 0, i)) + 1
    depth, j = 0, start
    while True:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    end = j + 1
    if text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


src = open(os.path.join(ROOT, "..", "Footprints.pretty", "BNC_Amphenol_031-5540_031-5539_Dual.kicad_mod")).read()
src = _drop_block(src, "(at -5.08 5.08)")
src = _drop_block(src, '(layer "Dwgs.User")')
src = src.replace("(start -7.79 -33.85)\n\t\t(end 7.79 7.96)", "(start -7.79 -33.85)\n\t\t(end 7.79 1.3)")
src = src.replace("(start -7.37 -12.57)\n\t\t(end 7.37 1.42)", "(start -7.37 -12.3)\n\t\t(end 7.37 1.42)")
src = src.replace('(footprint "BNC_Amphenol_031-5540_031-5539_Dual"', '(footprint "BNC_Amphenol_031-5540_RA"')
src = src.replace('(property "Value" "BNC_Amphenol_031-5540_031-5539_Dual"', '(property "Value" "BNC_Amphenol_031-5540_RA"')
src = _re.sub(r'\(descr "[^"]*"', '(descr "BNC jack, Amphenol 031-5540 / 031-5431 / 031-5486 right angle, front face at the board edge; Amphenol drawings 31-5540, 31-5431"', src)
src = _re.sub(r'\(tags "[^"]*"', '(tags "BNC coaxial Amphenol 031-5540 031-5431 031-5486 right angle"', src)
assert src.count("(pad ") == 4 and "Dwgs.User" not in src
open(os.path.join(LIB, "BNC_Amphenol_031-5540_RA.kicad_mod"), "w").write(src)
print("saved BNC_Amphenol_031-5540_RA")


# JST PH B4B top-entry socket without a courtyard: J102 shares PS1's space (only one of the two is fitted), and
# missing_courtyard is ignored in this project while courtyards_overlap is an error.  Pure text edit of KiCad's file.
def _drop_item(text, marker):
    i = text.index(marker)
    start = text.rfind("\n\t(", 0, i) + 1
    depth, j = 0, start
    while True:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    end = j + 1
    if text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


src = open("/usr/share/kicad/footprints/Connector_JST.pretty/JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical.kicad_mod").read()
while '(layer "F.CrtYd")' in src:
    src = _drop_item(src, '(layer "F.CrtYd")')
while '(layer "F.SilkS")' in src:                  # its silk would cross PS1's pad apertures
    src = _drop_item(src, '(layer "F.SilkS")')
src = src.replace('(footprint "JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical"', '(footprint "JST_PH_B4B-PH-K_NoCrtYd"')
src = src.replace('(property "Value" "JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical"', '(property "Value" "JST_PH_B4B-PH-K_NoCrtYd"')
src = _re.sub(r'\(descr "[^"]*"', '(descr "JST PH B4B-PH-K-S top entry, 4 pins, 2.0 mm pitch; KiCad library footprint without its courtyard and silk (shares the DC-DC PS1 space, one of the two fitted)"', src)
open(os.path.join(LIB, "JST_PH_B4B-PH-K_NoCrtYd.kicad_mod"), "w").write(src)
print("saved JST_PH_B4B-PH-K_NoCrtYd")
