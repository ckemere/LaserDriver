#!/usr/bin/env python3
"""Build Footprints.pretty/BNC_Amphenol_031-5540_031-5539_Dual.kicad_mod (KiCad bundled Python).

One footprint for either Amphenol BNC jack (Amphenol drawings 31-5540 rev H, 31-5431 rev L, 31-5539 rev H):
  * right angle 031-5540 / 031-5431 / 031-5486 (the placement is for these): signal and ground tails
    0.9 mm on 2.54 mm (ground on the left when the barrel points up); two 2.0 mm posts 10.16 mm apart,
    5.08 mm from the tail row toward the barrel; body 14.5 x 13.1, tails ~1.3 mm in from the rear face,
    front face 5.08 + 7.37 = 12.45 mm ahead of the tails; then the 1/2-28 thread (8.9) and bayonet (12).
  * vertical 031-5539 (Rev 1 part), fitted turned 180 deg relative to KiCad's footprint for it: same tails,
    posts on the diagonal of the same 10.16 mm square - it shares one right-angle post and needs one
    more at (-5.08, +5.08).
Frame: signal pin at the origin, right-angle barrel toward -y (place at 180 deg for a south-edge connector).
"""
import os

import pcbnew

MM = pcbnew.FromMM
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "Footprints.pretty")
NAME = "BNC_Amphenol_031-5540_031-5539_Dual"


def v(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def main():
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID("Footprints", NAME))
    fp.SetLibDescription("BNC jack, Amphenol 031-5540 / 031-5431 right angle (placed) or 031-5539 vertical "
                         "(turned 180); Amphenol drawings 31-5540, 31-5431, 31-5539")
    fp.SetKeywords("BNC coaxial Amphenol 031-5540 031-5431 031-5486 031-5539 right angle vertical")
    fp.SetAttributes(pcbnew.FP_THROUGH_HOLE)
    fp.Reference().SetPosition(v(0, 3.2))
    fp.Reference().SetLayer(pcbnew.F_SilkS)
    fp.Value().SetText(NAME)
    fp.Value().SetPosition(v(0, -35.0))
    fp.Value().SetLayer(pcbnew.F_Fab)

    def pad(num, x, y, size, drill):
        p = pcbnew.PAD(fp)
        p.SetNumber(num)
        p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        p.SetDrillSize(pcbnew.VECTOR2I(MM(drill), MM(drill)))
        p.SetLayerSet(pcbnew.PAD.PTHMask())
        p.SetPosition(v(x, y))
        fp.Add(p)

    pad("1", 0.0, 0.0, 1.6, 0.9)          # centre contact
    pad("2", -2.54, 0.0, 1.6, 0.9)        # grounding terminal
    pad("2", -5.08, -5.08, 3.4, 2.0)      # right-angle mounting posts, toward the barrel
    pad("2", 5.08, -5.08, 3.4, 2.0)       # (this one is shared with the 031-5539)
    pad("2", -5.08, 5.08, 3.4, 2.0)       # 031-5539 second (diagonal) post

    def rect(layer, x0, y0, x1, y1, w):
        s = pcbnew.PCB_SHAPE(fp)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(v(x0, y0))
        s.SetEnd(v(x1, y1))
        s.SetLayer(layer)
        s.SetWidth(MM(w))
        fp.Add(s)

    # fab: body, thread, bayonet
    rect(pcbnew.F_Fab, -7.25, -12.45, 7.25, 1.3, 0.1)
    rect(pcbnew.F_Fab, -6.35, -21.35, 6.35, -12.45, 0.1)
    rect(pcbnew.F_Fab, -4.8, -33.35, 4.8, -21.35, 0.1)
    # silk: the body outline on the board
    rect(pcbnew.F_SilkS, -7.37, -12.57, 7.37, 1.42, 0.12)
    # vertical 031-5539 alternative body (turned 180 from KiCad's BNC_Amphenol_031-5539_Vertical)
    rect(pcbnew.Dwgs_User, -7.25, -8.18, 7.25, 7.42, 0.05)
    # courtyard: union of the right-angle body + barrel and the vertical body
    rect(pcbnew.F_CrtYd, -7.79, -33.85, 7.79, 7.96, 0.05)

    # 3D: KiCad's B6252HB right-angle BNC as a stand-in (similar body), front face moved to the 031-5540's
    # (B6252HB front 12.70 ahead of its signal pin, 031-5540 12.45)
    m = pcbnew.FP_3DMODEL()
    m.m_Filename = "${KICAD9_3DMODEL_DIR}/Connector_Coaxial.3dshapes/BNC_Amphenol_B6252HB-NPP3G-50_Horizontal.step"
    m.m_Offset = pcbnew.VECTOR3D(0, -0.25, 0)
    fp.Models().append(m)

    io = pcbnew.PCB_IO_KICAD_SEXPR()
    io.FootprintSave(os.path.abspath(LIB), fp)
    print("wrote", os.path.join(os.path.abspath(LIB), NAME + ".kicad_mod"))


if __name__ == "__main__":
    main()
