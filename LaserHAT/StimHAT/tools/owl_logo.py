#!/usr/bin/env python3
"""$KICAD_PY tools/owl_logo.py -- the lab's owl for the StimHAT, derived from ../Footprints.pretty/OwlLogo_Laser_14mm:
every coordinate scaled by SCALE, the exposed-copper EYES kept (pads 1 / 2, pruned to the eye polygons), the copper
BEAM primitives and the beam anchor pads dropped (the beams stay as silk lines), no courtyard.  Writes
stimhat.pretty/<NAME>.kicad_mod and places / refreshes it on the board as the board-only footprint G1 with its eyes on GND.
The eyes sit at (-0.8, -4.3) and (+2.7, -4.3) x SCALE from the centre, so the centre must stay west of the barrier by
3.6 x SCALE + clearance (the owl looks west, toward U7)."""
import os
import re
import sys
import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")) + "/"
SRC = ROOT + "Footprints.pretty/OwlLogo_Laser_14mm.kicad_mod"
SCALE = 1.0
NAME = "OwlLogo_Eyes_14mm"
POS = (29.6, 18.05)         # only used when G1 is not on the board yet: an existing G1 keeps its position and rotation (the user places it by hand)
EYE_R = 1.4                 # primitives whose bbox lies within this radius of the pad anchor are eye copper, the rest are beams


def blocks(s, head):
    """yield (start, end) of every top-level '(head ...' block in s (balanced parentheses)"""
    i = 0
    while True:
        j = s.find(head, i)
        if j < 0:
            return
        k = j; depth = 0
        while True:
            c = s[k]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        yield j, k + 1
        i = k + 1


src = open(SRC).read()
out, last, kept, dropped = [], 0, 0, 0
for j, k in list(blocks(src, "\n  (pad ")):
    out.append(src[last:j]); last = k
    pad = src[j:k]
    ax, ay = map(float, re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", pad).groups())
    prims, pstart = [], None
    for pj, pk in blocks(pad, "(gr_poly"):
        pts = [tuple(map(float, m)) for m in re.findall(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", pad[pj:pk])]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if max(abs(min(xs)), abs(max(xs))) <= EYE_R and max(abs(min(ys)), abs(max(ys))) <= EYE_R:
            prims.append(pad[pj:pk]); kept += 1
        else:
            dropped += 1
    if not prims:
        continue                                             # a beam anchor: drop the whole pad
    head = pad[:pad.find("(primitives")]
    out.append("%s(primitives\n      %s\n    ))" % (head, "\n      ".join(prims)))
out.append(src[last:])
s = "".join(out)


def sc(m):
    vals = m.group(2).split()
    return "(%s %s)" % (m.group(1), " ".join(["%.4f" % (float(v) * SCALE) for v in vals[:2]] + vals[2:]))


s = re.sub(r"\((xy|at|start|end|mid|center|size) ((?:-?[\d.]+ ?){2,3})\)", sc, s)
s = re.sub(r"\(width ([\d.]+)\)", lambda m: "(width %.3f)" % (max(0.12, float(m.group(1)) * SCALE) if float(m.group(1)) > 0 else 0), s)
s = re.sub(r'\n  \(fp_line[^\n]*\n[^\n]*\(layer "F\.CrtYd"\)\)', "", s)              # no courtyard for a logo
s = s.replace('"OwlLogo_Laser_14mm"', '"%s"' % NAME)
s = re.sub(r'\(descr "[^"]*"\)', '(descr "Owl logo with exposed-copper eyes (tie to GND), beams in silk, %.1f mm tall: OwlLogo_Laser_14mm x %.2f")' % (13.96 * SCALE, SCALE), s)
open(ROOT + "StimHAT/stimhat.pretty/%s.kicad_mod" % NAME, "w").write(s)
print("wrote %s: %d eye polygons kept, %d beam polygons dropped" % (NAME, kept, dropped))

io = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
fp = io.FootprintLoad(ROOT + "StimHAT/stimhat.pretty", NAME)
M = 1e6
bb = fp.GetBoundingBox(False, False)
print("silk %.1f x %.1f mm; eye pads:" % ((bb.GetRight() - bb.GetLeft()) / M, (bb.GetBottom() - bb.GetTop()) / M))
for p in fp.Pads():
    pb = p.GetBoundingBox()
    print("   x %.2f..%.2f y %.2f..%.2f" % (POS[0] + pb.GetLeft() / M, POS[0] + pb.GetRight() / M, POS[1] + pb.GetTop() / M, POS[1] + pb.GetBottom() / M))
if "--no-board" in sys.argv:
    sys.exit()
b = pcbnew.LoadBoard(ROOT + "StimHAT/StimHAT.kicad_pcb")
gnd = b.FindNet("GND")
pos, rot = pcbnew.VECTOR2I(pcbnew.FromMM(POS[0]), pcbnew.FromMM(POS[1])), 0.0
for f in list(b.GetFootprints()):
    if f.GetReference() == "G1":
        pos, rot = pcbnew.VECTOR2I(f.GetPosition()), f.GetOrientationDegrees()
        b.Remove(f)
fp.SetFPID(pcbnew.LIB_ID("stimhat", NAME))
fp.SetReference("G1"); fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
fp.SetPosition(pos); fp.SetOrientationDegrees(rot)
POS = (pos.x / M, pos.y / M)
for p in fp.Pads():
    p.SetNet(gnd)
b.Add(fp)
pcbnew.SaveBoard(ROOT + "StimHAT/StimHAT.kicad_pcb", b)
print("G1 at (%.2f, %.2f) rot %g, eyes on GND" % (POS[0], POS[1], rot))
