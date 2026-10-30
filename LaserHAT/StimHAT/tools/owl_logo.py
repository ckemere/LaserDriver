#!/usr/bin/env python3
"""$KICAD_PY tools/owl_logo.py -- the lab's owl for the StimHAT, derived from ../Footprints.pretty/OwlLogo_Laser_14mm:
every coordinate scaled by SCALE, the exposed-copper EYES kept (pads 1 / 2, pruned to the eye polygons), the copper
BEAM primitives and the beam anchor pads dropped (the beams stay as silk lines), no courtyard.  Writes
stimhat.pretty/<NAME>.kicad_mod and places / refreshes it on the board as the board-only footprint G1 with its eyes on GND.
The eyes sit at (-0.8, -4.3) and (+2.7, -4.3) x SCALE from the centre (x negated when MIRROR), so the centre must stay west of the barrier by
3.6 x SCALE + clearance (the owl looks west, toward U7)."""
import math
import os
import re
import sys
import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")) + "/"
SRC = ROOT + "Footprints.pretty/OwlLogo_Laser_14mm.kicad_mod"
SCALE = 1.0
MIRROR = True               # the library owl looks left (west); mirrored it looks right, toward the isolated side
NAME = "OwlLogo_Eyes_14mm_R" if MIRROR else "OwlLogo_Eyes_14mm"
POS = (29.6, 18.05)         # only used when G1 is not on the board yet: an existing G1 keeps its position and rotation (the user places it by hand)
EYE_R = 1.4                 # primitives whose bbox lies within this radius of the pad anchor are eye copper, the rest are beams
NEURON = (48.0, 16.2)       # board position of the neuron the owl looks at (--neuron X Y): the centre of the empty pour square above "ISOLATED";
                            # the neuron drawing is moved there, the beams re-aimed from both eyes and the eye squares turned to the beam angle
if "--neuron" in sys.argv:
    i = sys.argv.index("--neuron"); NEURON = (float(sys.argv[i + 1]), float(sys.argv[i + 2]))


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
    fx = -SCALE if (MIRROR and m.group(1) != "size") else SCALE          # mirror = negate x of every point (not of sizes)
    return "(%s %s)" % (m.group(1), " ".join(["%.4f" % (float(vals[0]) * fx), "%.4f" % (float(vals[1]) * SCALE)] + vals[2:]))


s = re.sub(r"\((xy|at|start|end|mid|center|size) ((?:-?[\d.]+ ?){2,3})\)", sc, s)
s = re.sub(r"\(width ([\d.]+)\)", lambda m: "(width %.3f)" % (max(0.12, float(m.group(1)) * SCALE) if float(m.group(1)) > 0 else 0), s)
s = re.sub(r'\n  \(fp_line[^\n]*\n[^\n]*\(layer "F\.CrtYd"\)\)', "", s)              # no courtyard for a logo
s = s.replace('"OwlLogo_Laser_14mm"', '"%s"' % NAME)
s = re.sub(r'\(descr "[^"]*"\)', '(descr "Owl logo with exposed-copper eyes (tie to GND), beams in silk, %.1f mm tall: OwlLogo_Laser_14mm x %.2f%s")' % (13.96 * SCALE, SCALE, ", mirrored (looks right)" if MIRROR else ""), s)

# ---- where is G1 on the board?  (the user places the owl by hand; the neuron target is a board position)
M = 1e6
b = pcbnew.LoadBoard(ROOT + "StimHAT/StimHAT.kicad_pcb")
pos, rot = pcbnew.VECTOR2I(pcbnew.FromMM(POS[0]), pcbnew.FromMM(POS[1])), 0.0
for f in b.GetFootprints():
    if f.GetReference() == "G1":
        pos, rot = pcbnew.VECTOR2I(f.GetPosition()), f.GetOrientationDegrees()
POS = (pos.x / M, pos.y / M)
assert rot == 0, "re-aiming assumes G1 unrotated"
tx, ty = NEURON[0] - POS[0], NEURON[1] - POS[1]                     # neuron target in footprint coordinates

# ---- silk lines: the 4 beams go, the neuron (the cluster of short lines) moves to the target
LINE = re.compile(r'\n  \(fp_line \(start (-?[\d.]+) (-?[\d.]+)\) \(end (-?[\d.]+) (-?[\d.]+)\)\n\s*\(stroke \(width ([\d.]+)\) \(type solid\)\) \(layer "F\.SilkS"\)\)')
segs = [tuple(map(float, m.groups()[:4])) for m in LINE.finditer(s)]
neuron = [g for g in segs if math.hypot(g[2] - g[0], g[3] - g[1]) <= 2.0 * SCALE]
nx = (min(min(g[0], g[2]) for g in neuron) + max(max(g[0], g[2]) for g in neuron)) / 2
ny = (min(min(g[1], g[3]) for g in neuron) + max(max(g[1], g[3]) for g in neuron)) / 2
dx, dy = tx - nx, ty - ny


def move_line(m):
    x1, y1, x2, y2 = map(float, m.groups()[:4])
    if math.hypot(x2 - x1, y2 - y1) > 2.0 * SCALE:
        return ""                                                       # an old beam
    return '\n  (fp_line (start %.4f %.4f) (end %.4f %.4f)\n    (stroke (width %s) (type solid)) (layer "F.SilkS"))' % (x1 + dx, y1 + dy, x2 + dx, y2 + dy, m.group(5))


s = LINE.sub(move_line, s)

# ---- eyes: turn each copper square to its beam, draw two beam lines per eye from the socket edge to the neuron
PAD = re.compile(r'\(pad "1" smd custom \(at (-?[\d.]+) (-?[\d.]+)\)')
eyes = [tuple(map(float, m.groups())) for m in PAD.finditer(s)]
beams = ""
for ex, ey in eyes:
    ang = math.atan2(ty - ey, tx - ex)
    s = s.replace('(pad "1" smd custom (at %.4f %.4f)' % (ex, ey), '(pad "1" smd custom (at %.4f %.4f %.1f)' % (ex, ey, -math.degrees(ang)), 1)
    ux, uy = math.cos(ang), math.sin(ang); px, py = -uy, ux
    L = math.hypot(tx - ex, ty - ey)
    for side in (-0.28 * SCALE, 0.28 * SCALE):                          # a narrow cone, converging on the soma
        x1, y1 = ex + 1.3 * SCALE * ux + side * px, ey + 1.3 * SCALE * uy + side * py
        x2, y2 = ex + (L - 0.9 * SCALE) * ux, ey + (L - 0.9 * SCALE) * uy
        beams += '\n  (fp_line (start %.4f %.4f) (end %.4f %.4f)\n    (stroke (width %.3f) (type solid)) (layer "F.SilkS"))' % (x1, y1, x2, y2, max(0.12, 0.15 * SCALE))
k = s.rfind("\n)")
s = s[:k] + beams + s[k:]
print("neuron moved by (%.2f, %.2f) to (%.2f, %.2f) local = board (%.2f, %.2f); eyes turned to %s deg" % (dx, dy, tx, ty, NEURON[0], NEURON[1], ", ".join("%.0f" % math.degrees(math.atan2(ty - ey, tx - ex)) for ex, ey in eyes)))
open(ROOT + "StimHAT/stimhat.pretty/%s.kicad_mod" % NAME, "w").write(s)
print("wrote %s: %d eye polygons kept, %d beam polygons dropped" % (NAME, kept, dropped))

io = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
fp = io.FootprintLoad(ROOT + "StimHAT/stimhat.pretty", NAME)
bb = fp.GetBoundingBox(False, False)
print("silk %.1f x %.1f mm; eye pads:" % ((bb.GetRight() - bb.GetLeft()) / M, (bb.GetBottom() - bb.GetTop()) / M))
for p in fp.Pads():
    pb = p.GetBoundingBox()
    print("   x %.2f..%.2f y %.2f..%.2f" % (POS[0] + pb.GetLeft() / M, POS[0] + pb.GetRight() / M, POS[1] + pb.GetTop() / M, POS[1] + pb.GetBottom() / M))
if "--no-board" in sys.argv:
    sys.exit()
gnd = b.FindNet("GND")
for f in list(b.GetFootprints()):
    if f.GetReference() == "G1":
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
