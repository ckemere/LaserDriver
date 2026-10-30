"""$KICAD_PY tools/owl_logo.py -- silk-only owl, scaled from Footprints.pretty/OwlLogo_Laser_14mm: every coordinate x SCALE, the copper pads (eyes / beams) dropped
so the logo can sit anywhere on the HAT side without copper or barrier questions; line widths kept >= 0.12 mm.
Writes stimhat.pretty/OwlLogo_Silk_6mm.kicad_mod and places it on the board as G1."""
import re
import pcbnew
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")) + "/"
SRC = ROOT + "Footprints.pretty/OwlLogo_Laser_14mm.kicad_mod"
NAME = "OwlLogo_Silk_6mm"
SCALE = 0.45
s = open(SRC).read()
# drop the pads (balanced-paren scan from each "(pad ")
out = []
i = 0
while True:
    j = s.find("\n  (pad ", i)
    if j < 0:
        out.append(s[i:]); break
    out.append(s[i:j])
    k = j + 3; depth = 0
    while True:
        c = s[k]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                break
        k += 1
    i = k + 1
s = "".join(out)


def sc(m):
    vals = m.group(2).split()
    out = ["%.4f" % (float(v) * SCALE) for v in vals[:2]] + vals[2:]      # (at x y rot): the angle is not scaled
    return "(%s %s)" % (m.group(1), " ".join(out))


s = re.sub(r"\((xy|at|start|end|mid|center|size) ((?:-?[\d.]+ ?){2,3})\)", sc, s)
s = re.sub(r"\(width ([\d.]+)\)", lambda m: "(width %.3f)" % (max(0.12, float(m.group(1)) * SCALE) if float(m.group(1)) > 0 else 0), s)
s = s.replace('(footprint "OwlLogo_Laser_14mm"', '(footprint "%s"' % NAME).replace('"OwlLogo_Laser_14mm"', '"%s"' % NAME)
s = re.sub(r'\(descr "[^"]*"\)', '(descr "Owl logo, silkscreen only (eyes left dark, beams in silk), %.1f mm tall: OwlLogo_Laser_14mm scaled by %.2f")' % (13.96 * SCALE, SCALE), s)
# no courtyard for a logo (it would collide with its neighbours' courtyards for nothing)
s = re.sub(r'\n  \(fp_line[^\n]*\n[^\n]*\(layer "F\.CrtYd"\)\)', "", s)
open(ROOT + "StimHAT/stimhat.pretty/%s.kicad_mod" % NAME, "w").write(s)
print("wrote", NAME)

io = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
fp = io.FootprintLoad(ROOT + "StimHAT/stimhat.pretty", NAME)
bb = fp.GetBoundingBox(False, False)
print("owl bbox %.2f x %.2f mm, pads %d" % ((bb.GetRight() - bb.GetLeft()) / 1e6, (bb.GetBottom() - bb.GetTop()) / 1e6, len(list(fp.Pads()))))
b = pcbnew.LoadBoard(ROOT + "StimHAT/StimHAT.kicad_pcb")
for f in list(b.GetFootprints()):
    if f.GetReference() == "G1":
        b.Remove(f)
fp.SetFPID(pcbnew.LIB_ID("stimhat", NAME))
fp.SetReference("G1"); fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(30.1), pcbnew.FromMM(18.4)))
fp.SetOrientationDegrees(0)
b.Add(fp)
pcbnew.SaveBoard(ROOT + "StimHAT/StimHAT.kicad_pcb", b)
print("G1 placed at (30.1, 18.4)")
