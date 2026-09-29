"""
Place (build_pcb.py), add the split ground planes, autoroute with Freerouting, pour, tidy silkscreen, run DRC.
    python tools/route_pcb.py        (a Python that imports pcbnew; SEEDS=0,1,... selects the placement variants)
In1.Cu is a plane layer: GND_H under the HAT domain, GND_ISO under the isolated domain, nothing in the barrier.
Freerouting routes F.Cu, In2.Cu and B.Cu and drops ground vias onto the planes.  The Freerouting command comes from
$FREEROUTING (whitespace-split, e.g. "java -jar ~/Tools/freerouting-2.4.1.jar"); the default is the macOS app.
Its "Auto-routing stage completed (N unrouted ...)" line is read from the process output, or from $FREEROUTING_LOG /
the usual log file when the build only logs to a file.
"""
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import build_pcb as B  # noqa: E402

FREEROUTING = [os.path.expanduser(a) for a in
               shlex.split(os.environ.get("FREEROUTING") or "/Applications/freerouting.app/Contents/MacOS/freerouting")]
FR_ARGS = ["-mp", "100", "-mt", "1", "--gui.enabled=false", "--router.automatic_neckdown=false"]
FR_LOGS = [os.environ.get("FREEROUTING_LOG"), "~/Library/Logs/freerouting/freerouting.log",
           "~/.freerouting/logs/freerouting.log", "~/.local/share/freerouting/logs/freerouting.log"]


def freeroute(dsn, ses):
    """run Freerouting on dsn -> ses; return the unrouted count of its last auto-routing stage"""
    p = subprocess.run(FREEROUTING + ["-de", dsn, "-do", ses] + FR_ARGS, check=True, capture_output=True, text=True,
                       timeout=1800)
    texts = [p.stdout + p.stderr]
    for lg in FR_LOGS:
        if lg and os.path.exists(os.path.expanduser(lg)):
            texts.append(open(os.path.expanduser(lg)).read())
    texts += [open(f).read() for f in glob.glob(os.path.expanduser("~/.freerouting/**/*.log"), recursive=True)]
    for txt in texts:
        done = [l for l in txt.splitlines() if "Auto-routing stage completed" in l]
        if done:
            return int(re.search(r"\((\d+) unrouted", done[-1]).group(1))
    raise RuntimeError("Freerouting finished without an 'Auto-routing stage completed' line (set FREEROUTING_LOG?)")
KICAD_CLI = B.KICAD_CLI
PCB = B.PCB
RT = os.path.join(ROOT, "route" if B.COPPER == 4 else "route_2L")
mm = pcbnew.FromMM
MIN_W = 0.15
GNDS = ("GND_H", "GND_ISO")
H = B.BARRIER_W / 2
HAT_POLY = [(B.X0, B.Y0), (B.X1, B.Y0), (B.X1, 107.0 - H), (122.0 + H, 107.0 - H), (122.0 + H, 81.6 - H),
            (108.0 - H, 81.6 - H), (108.0 - H, 83.58 - H), (B.X0, 83.58 - H)]
ISO_POLY = [(B.X0, 83.58 + H), (108.0 + H, 83.58 + H), (108.0 + H, 81.6 + H), (122.0 - H, 81.6 + H),
            (122.0 - H, 107.0 + H), (B.X1, 107.0 + H), (B.X1, B.Y1), (B.X0, B.Y1)]
LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def zone(board, net, layer, pts, priority=0, solid=False):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(priority)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(mm(x), mm(y))
    board.Add(z)
    return z


def planes(board):
    """In1.Cu: the two ground planes (present during routing so Freerouting treats In1 as their plane layer)"""
    if B.COPPER != 4:
        return
    zone(board, "GND_H", pcbnew.In1_Cu, HAT_POLY, solid=True)
    zone(board, "GND_ISO", pcbnew.In1_Cu, ISO_POLY, solid=True)


def pours(board):
    for layer in ((pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if B.COPPER == 4 else (pcbnew.F_Cu, pcbnew.B_Cu)):
        zone(board, "GND_H", layer, HAT_POLY)
        zone(board, "GND_ISO", layer, ISO_POLY)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def stitch(board, pitch=1.5):
    """ground stitching vias wherever F and B are both poured with the same ground and In2 has no other copper nearby"""
    zones = {}
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() in GNDS:
            zones.setdefault(z.GetNetname(), []).append(z)
    r = 0.25 + 0.3      # via radius + margin
    clr = mm(0.25 + 0.2)
    inner = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == pcbnew.In2_Cu]
    holes = [(v.GetPosition(), mm(0.25)) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    holes += [(p.GetPosition(), max(p.GetSize().x, p.GetSize().y) // 2) for fp in board.GetFootprints() for p in fp.Pads()
              if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    n = 0
    for net, zs in zones.items():
        poly = HAT_POLY if net == "GND_H" else ISO_POLY
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        y = min(ys) + 0.8
        while y < max(ys) - 0.5:
            x = min(xs) + 0.8
            while x < max(xs) - 0.5:
                pt = pcbnew.VECTOR2I(mm(x), mm(y))
                ok = all(any(z.GetLayer() == L and all(z.HitTestFilledArea(L, pcbnew.VECTOR2I(mm(x + dx), mm(y + dy)))
                                                        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)))
                             for z in zs) for L in (pcbnew.F_Cu, pcbnew.B_Cu))
                ok = ok and not any(t.GetNetname() != net and t.HitTest(pt, clr) for t in inner)
                ok = ok and all((h[0] - pt).EuclideanNorm() > h[1] + mm(0.25 + 0.3) for h in holes)
                if ok:
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(pt)
                    v.SetWidth(mm(0.5)); v.SetDrill(mm(0.3))
                    v.SetNet(board.FindNet(net))
                    board.Add(v); n += 1
                    holes.append((pt, mm(0.25)))
                x += pitch
            y += pitch
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return n


def _via_ok(board, pt, net, r=mm(0.25), clr=mm(0.17)):
    """a through via of `net` at pt clears all other-net copper on every layer and stays inside the net's domain"""
    poly = HAT_POLY if net == "GND_H" else ISO_POLY
    x, y = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)
    xs = [p[0] for p in poly]
    if not _inside(poly, x, y) or any(not _inside(poly, x + dx, y + dy) for dx, dy in ((0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5))):
        return False
    for t in board.GetTracks():
        if t.GetNetname() == net:
            if t.GetClass() == "PCB_VIA" and (t.GetPosition() - pt).EuclideanNorm() < mm(0.7):
                return False
            continue
        if t.GetClass() == "PCB_VIA":
            if (t.GetPosition() - pt).EuclideanNorm() < r + t.GetWidth(pcbnew.F_Cu) // 2 + clr:
                return False
        elif t.HitTest(pt, r + clr):
            return False
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net and p.HitTest(pt, r + clr):
                return False
            if p.GetNetname() == net and p.HitTest(pt, 0):
                return False
    return True


def _inside(poly, x, y):
    c = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def ground_fixup(board):
    """from DRC's unconnected list: drop a via (plus a short track for SMD pads) that ties the item to its plane"""
    kinds, txt = drc_board(board)
    added = 0
    for blk in txt.split("\n[")[1:]:
        if not blk.startswith("unconnected_items]"):
            continue
        for m in re.finditer(r"@\(([-0-9.]+) mm, ([-0-9.]+) mm\): Pad (\S+) \[(GND_H|GND_ISO)\] of (\S+) on ([FB])\.Cu", blk):
            x, y, num, net, ref, side = float(m.group(1)), float(m.group(2)), m.group(3), m.group(4), m.group(5), m.group(6)
            layer = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
            c = pcbnew.VECTOR2I(mm(x), mm(y))
            import math
            # (a) straight track on the pad's layer to an existing same-net via within 3 mm
            vias = sorted((t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net
                           and (t.GetPosition() - c).EuclideanNorm() < mm(3.0)), key=lambda t: (t.GetPosition() - c).EuclideanNorm())
            cands = [v.GetPosition() for v in vias]
            # (b) new via positions on rings around the pad
            cands += [pcbnew.VECTOR2I(mm(x + rr * math.cos(k * math.pi / 16)), mm(y + rr * math.sin(k * math.pi / 16)))
                      for rr in (0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0) for k in range(32)]
            nvia = len(vias)
            for i, pt in enumerate(cands):
                for w in (0.3, 0.2):
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(c); tr.SetEnd(pt); tr.SetWidth(mm(w)); tr.SetLayer(layer)
                    tr.SetNet(board.FindNet(net))
                    if (i >= nvia and not _via_ok(board, pt, net)) or _track_clash(board, tr, net):
                        continue
                    board.Add(tr)
                    if i >= nvia:
                        v = pcbnew.PCB_VIA(board); v.SetPosition(pt); v.SetWidth(mm(0.5)); v.SetDrill(mm(0.3))
                        v.SetNet(board.FindNet(net)); board.Add(v)
                    added += 1
                    break
                else:
                    continue
                break
            else:
                print(f"  ground fix-up: no legal via for {ref}.{num} ({net})")
    # zone fragments: any filled polygon with no same-net via/THT pad inside gets a via at a legal interior point
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in GNDS or z.GetLayer() == pcbnew.In1_Cu:
            continue
        net = z.GetNetname()
        fp_ = z.GetFilledPolysList(z.GetLayer())
        for i in range(fp_.OutlineCount()):
            ol = fp_.Outline(i)
            bb = ol.BBox()
            anchors = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == net]
            anchors += [p.GetPosition() for f in board.GetFootprints() for p in f.Pads()
                        if p.GetNetname() == net and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
            if any(ol.PointInside(a) for a in anchors):
                continue
            placed = False
            yy = bb.GetTop()
            while yy < bb.GetBottom() and not placed:
                xx = bb.GetLeft()
                while xx < bb.GetRight() and not placed:
                    pt = pcbnew.VECTOR2I(xx, yy)
                    if ol.PointInside(pt) and all(ol.PointInside(pcbnew.VECTOR2I(xx + dx, yy + dy))
                                                  for dx, dy in ((mm(.3), 0), (-mm(.3), 0), (0, mm(.3)), (0, -mm(.3)))) \
                            and _via_ok(board, pt, net):
                        v = pcbnew.PCB_VIA(board); v.SetPosition(pt); v.SetWidth(mm(0.5)); v.SetDrill(mm(0.3))
                        v.SetNet(board.FindNet(net)); board.Add(v)
                        added += 1; placed = True
                    xx += mm(0.2)
                yy += mm(0.2)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added


def _track_clash(board, tr, net, clr=mm(0.17)):
    for t in board.GetTracks():
        if t.GetNetname() != net and t.GetLayer() == tr.GetLayer() or (t.GetClass() == "PCB_VIA" and t.GetNetname() != net):
            if t.GetClass() == "PCB_VIA":
                if tr.HitTest(t.GetPosition(), t.GetWidth(pcbnew.F_Cu) // 2 + clr + tr.GetWidth() // 2):
                    return True
            elif t.GetNetname() != net:
                sh1, sh2 = tr.GetEffectiveShape(), t.GetEffectiveShape()
                if sh1.Collide(sh2, clr):
                    return True
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() != net and p.IsOnLayer(tr.GetLayer()) and \
                    tr.GetEffectiveShape().Collide(p.GetEffectiveShape(tr.GetLayer()), clr):
                return True
    return False


def drc_board(board):
    path = os.path.join(RT, "fixup.kicad_pcb")
    pcbnew.SaveBoard(path, board)
    shutil.copy(PCB.replace(".kicad_pcb", ".kicad_pro"), path.replace(".kicad_pcb", ".kicad_pro"))
    return drc(path)


def complete(board, passes=2):
    """re-feed the routed board to Freerouting so it only works on what is still open (keeps the existing wiring)"""
    for i in range(passes):
        path = os.path.join(RT, f"complete{i}.kicad_pcb")
        pcbnew.SaveBoard(path, board)
        dsn, ses = os.path.join(RT, f"complete{i}.dsn"), os.path.join(RT, f"complete{i}.ses")
        board = pcbnew.LoadBoard(path)
        B.setup_rules(board)
        assert pcbnew.ExportSpecctraDSN(board, dsn)
        unrouted = freeroute(dsn, ses)
        assert pcbnew.ImportSpecctraSES(board, ses)
        for t in board.GetTracks():
            if t.GetClass() in ("PCB_TRACK", "PCB_ARC") and t.GetWidth() < mm(MIN_W):
                t.SetWidth(mm(MIN_W))
        print(f"completion pass {i + 1}: {unrouted} unrouted", flush=True)
        if unrouted == 0:
            break
    return board


def autoroute(placed_path, attempts=6):
    """route the placed board from scratch several times (Freerouting is not deterministic); keep the best."""
    dsn = os.path.join(RT, "EStimDaughter.dsn")
    best = None
    for attempt in range(attempts):
        board = pcbnew.LoadBoard(placed_path)
        B.setup_rules(board)
        ses = os.path.join(RT, f"try{attempt}.ses")
        assert pcbnew.ExportSpecctraDSN(board, dsn)
        unrouted = freeroute(dsn, ses)
        txt = open(ses).read()
        narrow = sum(1 for w in re.findall(r"\(path \S+ (\d+)", txt) if int(w) < MIN_W * 1e4)
        vias = txt.count("(via ")
        score = unrouted * 10000 + narrow * 10 + vias
        print(f"freerouting attempt {attempt + 1}: {unrouted} unrouted, {narrow} tracks under {MIN_W} mm, {vias} vias", flush=True)
        if best is None or score < best[0]:
            best = (score, ses)
        if unrouted == 0 and narrow == 0 and attempt >= 2:
            break
    shutil.copy(best[1], os.path.join(RT, "EStimDaughter.ses"))
    board = pcbnew.LoadBoard(placed_path)
    B.setup_rules(board)
    assert pcbnew.ImportSpecctraSES(board, best[1])
    fixed = 0
    for t in board.GetTracks():
        if t.GetClass() in ("PCB_TRACK", "PCB_ARC") and t.GetWidth() < mm(MIN_W):
            t.SetWidth(mm(MIN_W)); fixed += 1
    return board, fixed, best[0] // 10000


def silk(board):
    """reference designators: beside the part on its own side where the box clears pads/other text/edges; else hidden"""
    items = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            box = (bb.GetLeft(), bb.GetRight(), bb.GetTop(), bb.GetBottom())
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                items[pcbnew.F_SilkS].append(box); items[pcbnew.B_SilkS].append(box)
            else:
                items[pcbnew.F_SilkS if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_SilkS].append(box)
        for g in fp.GraphicalItems():
            if g.GetLayer() in items and g.GetClass() != "PCB_FIELD":
                bb = g.GetBoundingBox()
                items[g.GetLayer()].append((bb.GetLeft(), bb.GetRight(), bb.GetTop(), bb.GetBottom()))
    for fp in board.GetFootprints():      # outline parts that overhang the board edge (J1 body): keep them on F.Fab only
        for g in fp.GraphicalItems():
            bb = g.GetBoundingBox()
            if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and g.GetClass() != "PCB_FIELD" and (
                    bb.GetBottom() > mm(B.Y1 - 0.5) or bb.GetTop() < mm(B.Y0 + 0.5) or
                    bb.GetLeft() < mm(B.X0 + 0.5) or bb.GetRight() > mm(B.X1 - 0.5)):
                g.SetLayer(pcbnew.F_Fab if g.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Fab)
    gap = mm(0.1)
    x0b, y0b, x1b, y1b = mm(B.X0 + 0.4), mm(B.Y0 + 0.4), mm(B.X1 - 0.4), mm(B.Y1 - 0.4)
    bars = [(mm(a), mm(b), mm(c), mm(d)) for (a, b, c, d) in B.barrier_polys()]
    hidden = []

    def clear(box, layer):
        l, r, t, b = box
        if l < x0b or t < y0b or r > x1b or b > y1b:
            return False
        for (a, c, d, e) in items[layer] + bars:
            if l < c + gap and r > a - gap and t < e + gap and b > d - gap:
                return False
        return True
    for fp in sorted(board.GetFootprints(), key=lambda f: -f.GetBoundingBox(False, False).GetArea()):
        ref = fp.Reference()
        layer = pcbnew.B_SilkS if fp.IsFlipped() else pcbnew.F_SilkS
        ref.SetTextAngleDegrees(0)
        cb = fp.GetBoundingBox(False, False)
        tw, th = ref.GetBoundingBox().GetWidth(), ref.GetBoundingBox().GetHeight()
        cx, cy = cb.GetCenter().x, cb.GetCenter().y
        cands = [(cx, cy)] if fp.GetReference()[0] in "UJP" else []
        cands += [(cx, cb.GetTop() - th // 2 - mm(0.15)), (cx, cb.GetBottom() + th // 2 + mm(0.15)),
                  (cb.GetLeft() - tw // 2 - mm(0.15), cy), (cb.GetRight() + tw // 2 + mm(0.15), cy)]
        cands += [(cx + dx, cy + dy) for dx in (-mm(1.2), 0, mm(1.2)) for dy in (-mm(1.8), mm(1.8))]
        for (x, y) in cands:
            box = (x - tw // 2, x + tw // 2, y - th // 2, y + th // 2)
            if clear(box, layer):
                ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                items[layer].append(box)
                break
        else:
            ref.SetVisible(False)
            hidden.append(fp.GetReference())
    return hidden


def text(board, s, x, y, layer=pcbnew.F_SilkS, size=0.8):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(0.12))
    t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    board.Add(t)


def drc(path):
    rpt = os.path.join(RT, "drc.rpt")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--severity-all", "-o", rpt, path], capture_output=True)
    txt = open(rpt).read()
    kinds = {}
    for k in re.findall(r"^\[([a-z_]+)\]", txt, re.M):
        kinds[k] = kinds.get(k, 0) + 1
    return kinds, txt


def route_once(placed_path, tag):
    board = pcbnew.LoadBoard(placed_path)
    B.setup_rules(board)
    dsn, ses = os.path.join(RT, f"{tag}.dsn"), os.path.join(RT, f"{tag}.ses")
    assert pcbnew.ExportSpecctraDSN(board, dsn)
    return freeroute(dsn, ses), ses


def leftover(board, rounds=3):
    """grid-route whatever DRC still reports as unconnected (see fixroute.py), then refill"""
    import fixroute
    domains = {"GND_H": HAT_POLY, "GND_ISO": ISO_POLY}
    for k in range(rounds):
        kinds, txt = drc_board(board)
        if not kinds.get("unconnected_items"):
            break
        fixed, failed = fixroute.fix(board, txt, (B.X0, B.X1, B.Y0, B.Y1), B.barrier_polys(), domains)
        print(f"leftover router round {k + 1}: fixed {fixed}; failed {failed}", flush=True)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        if not fixed:
            break


def dangling(board):
    """remove signal vias DRC reports as dangling (connected on fewer than two layers)"""
    kinds, txt = drc_board(board)
    n = 0
    for m in re.finditer(r"\[via_dangling\].*?\n.*?\n\s+@\(([-0-9.]+) mm, ([-0-9.]+) mm\): Via \[([^\]]+)\]", txt):
        if m.group(3) in GNDS:
            continue
        p = pcbnew.VECTOR2I(mm(float(m.group(1))), mm(float(m.group(2))))
        for v in list(board.GetTracks()):
            if v.GetClass() == "PCB_VIA" and v.GetNetname() == m.group(3) and (v.GetPosition() - p).EuclideanNorm() < mm(0.01):
                board.Remove(v); n += 1
    if n:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print("dangling vias removed:", n)


PS1_LABELS = {"1": "5V", "2": "GND", "4": "-V", "5": "0V", "6": "+V"}


def module_marks(board):
    """PS1 is DNP (hand-fitted converter, or battery leads): flag it, and name its pads on the top silk (under the body)"""
    fp = board.FindFootprintByReference("PS1")
    for f in ("SetDNP", "SetExcludedFromPosFiles", "SetExcludedFromBOM"):
        if hasattr(fp, f):
            getattr(fp, f)(True)
    for t in list(board.GetDrawings()):
        if t.GetClass() == "PCB_TEXT" and t.GetLayer() == pcbnew.F_SilkS and t.GetText() in set(PS1_LABELS.values()) | {"PS1 DNP"}:
            board.Remove(t)
    for num, name in PS1_LABELS.items():
        p = fp.FindPadByNumber(num).GetPosition()
        t = pcbnew.PCB_TEXT(board)
        t.SetText(name); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); t.SetTextThickness(mm(0.12))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetPosition(pcbnew.VECTOR2I(p.x + mm(1.3), p.y))
        board.Add(t)
    t = pcbnew.PCB_TEXT(board)
    t.SetText("PS1 DNP"); t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); t.SetTextThickness(mm(0.12))
    t.SetTextAngleDegrees(90)
    t.SetPosition(pcbnew.VECTOR2I(mm(106.3), mm(86.0)))
    board.Add(t)


def finish(placed, ses):
    board = pcbnew.LoadBoard(placed)
    B.setup_rules(board)
    assert pcbnew.ImportSpecctraSES(board, ses)
    for t in board.GetTracks():
        if t.GetClass() in ("PCB_TRACK", "PCB_ARC") and t.GetWidth() < mm(MIN_W):
            t.SetWidth(mm(MIN_W))
    if int(os.environ.get("COMPLETE_PASSES", "0")):   # opt-in: Freerouting re-fed the routed board rips up more than it finishes
        board = complete(board, passes=int(os.environ["COMPLETE_PASSES"]))
    pours(board)
    print("stitching vias:", stitch(board))
    print("ground fix-up vias:", ground_fixup(board))
    leftover(board)
    dangling(board)
    module_marks(board)
    hidden = silk(board)
    print("references hidden (no room):", len(hidden))
    pcbnew.SaveBoard(PCB, board)
    kinds, txt = drc(PCB)
    print("DRC:", kinds or "clean")


if __name__ == "__main__":
    # Freerouting is deterministic for a given input: search over small placement perturbations instead
    os.makedirs(RT, exist_ok=True)
    seeds = [int(v) for v in os.environ.get("SEEDS", "0,1,2,3,4,5").split(",")]
    best = None
    for seed in seeds:
        B.main(seed)
        placed = os.path.join(RT, f"placed{seed}.kicad_pcb")
        board = pcbnew.LoadBoard(PCB)
        B.setup_rules(board)
        planes(board)
        pcbnew.SaveBoard(placed, board)
        shutil.copy(PCB.replace(".kicad_pcb", ".kicad_pro"), placed.replace(".kicad_pcb", ".kicad_pro"))
        unrouted, ses = route_once(placed, f"seed{seed}")
        print(f"seed {seed}: {unrouted} unrouted", flush=True)
        if best is None or unrouted < best[0]:
            best = (unrouted, seed, placed, ses)
        if unrouted == 0:
            break
    print("best: seed", best[1], "with", best[0], "unrouted", flush=True)
    shutil.copy(best[2], os.path.join(RT, "placed.kicad_pcb"))
    finish(best[2], best[3])
