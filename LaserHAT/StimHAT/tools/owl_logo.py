#!/usr/bin/env python3
"""$KICAD_PY tools/owl_logo.py -- the lab's owl for the StimHAT, derived from ../Footprints.pretty/OwlLogo_Laser_14mm:
every coordinate scaled by SCALE, the exposed-copper EYES kept (pruned to the eye polygons, pupils aimed at the neuron), the
source's beams dropped and redrawn toward the neuron: an exposed-copper line from each eye to the soma (one pad each, on F.Cu
across whatever is routed there, so check DRC), between an outer and an inner silk triangle; no courtyard.  Writes
stimhat.pretty/<NAME>.kicad_mod and places / refreshes it on the board as the board-only footprint G1 with all its pads on GND.
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
BEAM_GAP = 0.2              # the beams start outside the owl: this far past the last place a beam's stroke touches the body silk
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
lx0, lx1 = min(min(g[0], g[2]) for g in neuron), max(max(g[0], g[2]) for g in neuron)
ly0, ly1 = min(min(g[1], g[3]) for g in neuron), max(max(g[1], g[3]) for g in neuron)
# the soma (triangle) and the first stretch of the apical dendrite are small filled silk polygons next to the lines: they move too
POLY = re.compile(r'\n  \(fp_poly \(pts ((?:\(xy -?[\d.]+ -?[\d.]+\) ?)+)\)\n\s*\(stroke \(width [\d.]+\) \(type solid\)\) \(fill solid\) \(layer "F\.SilkS"\)\)')


def soma_pts(m):
    """the points of a silk polygon that belongs to the neuron (<= 2 mm across, touching the line cluster's box + 0.5 mm), else None"""
    pts = [tuple(map(float, p)) for p in re.findall(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", m.group(1))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    small = max(max(xs) - min(xs), max(ys) - min(ys)) <= 2.0 * SCALE
    near = min(xs) <= lx1 + 0.5 * SCALE and max(xs) >= lx0 - 0.5 * SCALE and min(ys) <= ly1 + 0.5 * SCALE and max(ys) >= ly0 - 0.5 * SCALE
    return pts if small and near else None


soma = [p for m in POLY.finditer(s) for p in (soma_pts(m) or [])]
nx = (min([lx0] + [p[0] for p in soma]) + max([lx1] + [p[0] for p in soma])) / 2
ny = (min([ly0] + [p[1] for p in soma]) + max([ly1] + [p[1] for p in soma])) / 2
dx, dy = tx - nx, ty - ny


# ---- eyes: each is one copper disc with the pupil as a notch in it, anchored at the disc's edge.  Re-anchor every eye pad on its
# disc centre and spin the copper about that centre so the notch faces the neuron (the notch side is opposite the area centroid).
def aim_eye(m):
    pad = m.group(0)
    ax, ay = map(float, re.search(r"\(at (-?[\d.]+) (-?[\d.]+)", pad).groups())
    pts = [tuple(map(float, p)) for p in re.findall(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", pad)]
    cx, cy = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2, (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    a2 = gx = gy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        c = x1 * y2 - x2 * y1; a2 += c; gx += (x1 + x2) * c; gy += (y1 + y2) * c
    gx, gy = gx / (3 * a2), gy / (3 * a2)
    ex, ey = ax + cx, ay + cy
    rot = math.atan2(ty - ey, tx - ex) - math.atan2(cy - gy, cx - gx)
    cr, sr = math.cos(rot), math.sin(rot)
    pad = re.sub(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", lambda q: "(xy %.4f %.4f)" % (cr * (float(q.group(1)) - cx) - sr * (float(q.group(2)) - cy),
                                                                               sr * (float(q.group(1)) - cx) + cr * (float(q.group(2)) - cy)), pad)
    eyes.append((ex, ey)); radii.append(max(math.hypot(x - cx, y - cy) for x, y in pts))
    return re.sub(r"\(at -?[\d.]+ -?[\d.]+\)", "(at %.4f %.4f)" % (ex, ey), pad, count=1)


eyes, radii = [], []
s = re.sub(r'\(pad "1" smd custom \(at [^)]*\).*?\n    \)\)', aim_eye, s, flags=re.S)
BEAM_W = max(0.12, 0.15 * SCALE)
INNER = 0.7                 # the inner triangle's apex, as a fraction of the way from the eyes' midpoint to the outer apex
COPPER_W = 0.267 * SCALE    # the exposed-copper laser lines (as in the source art), eye edge -> outer apex, between the two triangles
SILK_OFF = 0.6 * SCALE      # each silk line starts this far off its copper line (outer triangle outside it, inner triangle inside)
APEX_OFF = 0.35 * SCALE     # the outer silk lines end this far off the copper lines' common end


def beams_from(eyes):
    """(copper lines, silk lines): a copper line from each eye's edge to the outer apex just short of the soma; an outer silk
    triangle outside the copper (SILK_OFF at the start, APEX_OFF at the apex) and an inner one inside it closing at INNER of the
    way from the eyes' midpoint to the outer apex; every silk line starts just outside the owl"""
    mx, my = sum(e[0] for e in eyes) / len(eyes), sum(e[1] for e in eyes) / len(eyes)
    L = math.hypot(tx - mx, ty - my)
    ox, oy = mx + (L - 0.9 * SCALE) * (tx - mx) / L, my + (L - 0.9 * SCALE) * (ty - my) / L
    ix, iy = mx + INNER * (ox - mx), my + INNER * (oy - my)
    copper, silk = [], []
    for (ex, ey), r in zip(eyes, radii):
        d = math.hypot(ox - ex, oy - ey); ux, uy = (ox - ex) / d, (oy - ey) / d
        px, py = -uy, ux
        if px * (mx - ex) + py * (my - ey) > 0:                         # make (px, py) point away from the other eye (outward)
            px, py = -px, -py
        copper.append((ex + r * ux, ey + r * uy, ox, oy))
        sx, sy = ex + 1.3 * SCALE * ux, ey + 1.3 * SCALE * uy
        silk.append(outside_start(sx + SILK_OFF * px, sy + SILK_OFF * py, ox + APEX_OFF * px, oy + APEX_OFF * py))
        silk.append(outside_start(sx - SILK_OFF * px, sy - SILK_OFF * py, ix, iy))
    return copper, silk


BODY = [[tuple(map(float, p)) for p in re.findall(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", m.group(1))] for m in POLY.finditer(s) if soma_pts(m) is None]


def inside(x, y, poly):
    """even-odd point-in-polygon"""
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def outside_start(x1, y1, x2, y2):
    """the beam (x1, y1) -> (x2, y2) shortened so it starts BEAM_GAP past the last place its stroke touches the body silk"""
    L = math.hypot(x2 - x1, y2 - y1); ux, uy = (x2 - x1) / L, (y2 - y1) / L; h = BEAM_W / 2
    last, n = None, int(L / 0.01)
    for i in range(n + 1):
        t = L * i / n
        x, y = x1 + t * ux, y1 + t * uy
        if any(inside(x + a * -uy, y + a * ux, p) for a in (-h, 0, h) for p in BODY):
            last = t
    t = 0 if last is None else min(L, last + h + BEAM_GAP)
    return x1 + t * ux, y1 + t * uy, x2, y2


def move_poly(m):
    if soma_pts(m) is None:
        return m.group(0)
    return re.sub(r"\(xy (-?[\d.]+) (-?[\d.]+)\)", lambda q: "(xy %.4f %.4f)" % (float(q.group(1)) + dx, float(q.group(2)) + dy), m.group(0))


def move_line(m):
    x1, y1, x2, y2 = map(float, m.groups()[:4])
    if math.hypot(x2 - x1, y2 - y1) > 2.0 * SCALE:
        return ""                                                       # an old beam
    return '\n  (fp_line (start %.4f %.4f) (end %.4f %.4f)\n    (stroke (width %s) (type solid)) (layer "F.SilkS"))' % (x1 + dx, y1 + dy, x2 + dx, y2 + dy, m.group(5))


s = LINE.sub(move_line, s)
s = POLY.sub(move_poly, s)

# ---- beams: the copper laser lines (pads, GND like the eyes) and the nested silk triangles
copper, silk = beams_from(eyes)
beams = ""
for x1, y1, x2, y2 in copper:
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    beams += ('\n  (pad "1" smd custom (at %.4f %.4f) (size %.3f %.3f) (layers "F.Cu" "F.Mask") (zone_connect 2)\n    (options (clearance outline) (anchor circle))'
              '\n    (primitives\n      (gr_line (start %.4f %.4f) (end %.4f %.4f) (width %.3f))\n    ))') % (cx, cy, COPPER_W, COPPER_W, x1 - cx, y1 - cy, x2 - cx, y2 - cy, COPPER_W)
for x1, y1, x2, y2 in silk:
    beams += '\n  (fp_line (start %.4f %.4f) (end %.4f %.4f)\n    (stroke (width %.3f) (type solid)) (layer "F.SilkS"))' % (x1, y1, x2, y2, BEAM_W)
k = s.rfind("\n)")
s = s[:k] + beams + s[k:]
print("neuron moved by (%.2f, %.2f) to (%.2f, %.2f) local = board (%.2f, %.2f); pupils aimed at %s deg" % (dx, dy, tx, ty, NEURON[0], NEURON[1], ", ".join("%.0f" % math.degrees(math.atan2(ty - ey, tx - ex)) for ex, ey in eyes)))
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
