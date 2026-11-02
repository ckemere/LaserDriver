#!/usr/bin/env python3
"""Route SimpleBatteryPack.kicad_pcb from scratch with Freerouting (headless).
  1. rip up all tracks and vias
  2. pre-route a short stub out of every SMD pad that is narrower than its net class's track width (TSSOP / SOIC /
     SOT-23 pins on the 0.8 mm pack nets), so the wide track can attach beyond the pad row
  3. export DSN, run Freerouting, import SES
  4. delete stubs that stayed dangling (KiCad's track_dangling check, repeated), keeping copper that is in use
  5. DRC summary
Every board edit (rip, stubs, DSN export, SES import) runs in its own process: pcbnew segfaults when they share one.
Env: FREEROUTING_JAVA (default ~/Tools/jdk-25.0.4.1+1-jre/bin/java), FREEROUTING_JAR (~/Tools/freerouting-2.4.1.jar).
Run with KiCad's Python (-u: pcbnew may crash on exit and lose buffered output):
  $KICAD_PY -u tools/autoroute.py [--passes 60] [--keep-stubs]      full pipeline
  $KICAD_PY -u tools/autoroute.py --continue [--passes N]           route what is still open, keeping the copper
  $KICAD_PY -u tools/autoroute.py --cleanup-only | --trim-stubs       stub housekeeping on a routed board"""
import fnmatch
import json
import math
import os
import re
import shutil
import subprocess
import sys

import pcbnew

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "SimpleBatteryPack.kicad_pcb")
PRO = os.path.join(ROOT, "SimpleBatteryPack.kicad_pro")
WORK = os.path.join(ROOT, "route")                     # intermediates (git-ignored)
JAVA = os.environ.get("FREEROUTING_JAVA", os.path.expanduser("~/Tools/jdk-25.0.4.1+1-jre/bin/java"))
JAR = os.environ.get("FREEROUTING_JAR", os.path.expanduser("~/Tools/freerouting-2.4.1.jar"))
FREEROUTING_APP = os.environ.get("FREEROUTING_APP", "/Applications/freerouting.app/Contents/MacOS/freerouting")
KICAD_CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
PASSES = int(sys.argv[sys.argv.index("--passes") + 1]) if "--passes" in sys.argv else 60
KEEP_STUBS = "--keep-stubs" in sys.argv
CLEANUP_ONLY = "--cleanup-only" in sys.argv                  # just drop unused stubs and report
STUB_BEYOND = 0.8                                       # mm past the pad tip
STUB_REFS = {"U5", "U19"}                               # every signal pad of these gets a 0.2 mm escape stub too (fine-pitch rows that got boxed in)
PREROUTE = os.path.join(WORK, "preroute.json")         # optional hand pre-routes (maze_io format), added locked after the rip
STUB_MIN = 0.3                                          # shortest useful stub past the tip
CLR = 0.25                                              # keep this far from any other pad
mm = pcbnew.FromMM
os.makedirs(WORK, exist_ok=True)


def class_widths():
    """net name -> track width (mm) from the project's netclasses and patterns"""
    ns = json.load(open(PRO))["net_settings"]
    widths = {c["name"]: c["track_width"] for c in ns["classes"]}
    pats = [(p["pattern"], p["netclass"]) for p in ns.get("netclass_patterns", [])]

    def width(net):
        for pat, cls in pats:
            if fnmatch.fnmatchcase(net, pat):
                return widths[cls]
        return widths["Default"]
    return width


def rip(board):
    tracks = list(board.GetTracks())
    for t in tracks:
        board.Remove(t)
    return len(tracks)


def add_stubs(board):
    width = class_widths()
    pads = [(pad, fp) for fp in board.GetFootprints() for pad in fp.Pads()]
    n = 0
    for pad, fp in pads:
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not pad.GetNetname():
            continue
        sx, sy = pad.GetSize().x / 1e6, pad.GetSize().y / 1e6
        w = width(pad.GetNetname())
        forced = fp.GetReference() in STUB_REFS and w <= min(sx, sy) + 0.05
        if w <= min(sx, sy) + 0.05 and not forced:
            continue
        ang = math.radians(pad.GetOrientation().AsDegrees())
        # pad long axis in board coordinates (KiCad: y down, angles counter-clockwise on screen)
        if sx >= sy:
            ax, ay, half = math.cos(ang), -math.sin(ang), sx / 2
        else:
            ax, ay, half = math.sin(ang), math.cos(ang), sy / 2
        pc = pad.GetPosition()
        fc = fp.GetPosition()
        dx, dy = (pc.x - fc.x) / 1e6, (pc.y - fc.y) / 1e6
        if dx * ax + dy * ay < 0:
            ax, ay = -ax, -ay
        sw = 0.2 if forced else min(sx, sy)
        # fine-pitch pads (TSSOP) on wide nets get a long stub, so the wide track attaches clear of the neighbours' tracks
        L = half + STUB_BEYOND + (1.2 if (w >= 0.6 and sw < 0.5) else 0.0)
        px, py = pc.x / 1e6, pc.y / 1e6
        while L >= half + STUB_MIN:
            ex, ey = px + ax * L, py + ay * L
            r = sw / 2 + CLR
            clash = False
            for other, ofp in pads:
                if other is pad or other.GetNetCode() == pad.GetNetCode():
                    continue
                bb = other.GetBoundingBox()
                if (bb.GetLeft() / 1e6 - r <= ex <= bb.GetRight() / 1e6 + r
                        and bb.GetTop() / 1e6 - r <= ey <= bb.GetBottom() / 1e6 + r):
                    clash = True
                    break
            if not clash:
                break
            L -= 0.1
        else:
            continue                                     # no room for a stub here
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(pc.x, pc.y))
        t.SetEnd(pcbnew.VECTOR2I(mm(ex), mm(ey)))
        t.SetWidth(mm(sw))
        t.SetLayer(pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
        t.SetNetCode(pad.GetNetCode())
        board.Add(t)
        n += 1
    return n


def drc(path):
    out = os.path.join(WORK, "drc.json")
    subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--all-track-errors", "-o", out, path],
                   capture_output=True)
    return json.load(open(out))


def remove_track_at(path, x, y):
    """delete the one track that has an end at (x, y) mm; a separate process per call, pcbnew does not survive
    many LoadBoard/SaveBoard cycles in one interpreter"""
    board = pcbnew.LoadBoard(path)
    hit = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"
           and any(abs(p.x / 1e6 - x) < 0.01 and abs(p.y / 1e6 - y) < 0.01 for p in (t.GetStart(), t.GetEnd()))]
    if hit:
        board.Remove(hit[0])
        pcbnew.SaveBoard(path, board)
    return bool(hit)


def remove_dangling(path):
    """delete tracks that KiCad reports as dangling, one at a time, keeping any whose removal would open a connection
    (Freerouting sometimes joins a stub part-way along); repeated until nothing more can go"""
    total = 0
    tried = set()
    for _ in range(40):
        rep = drc(path)
        base = len(rep["unconnected_items"])
        pos = [(v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]) for v in rep["violations"]
               if v["type"] == "track_dangling" and (v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]) not in tried]
        if not pos:
            break
        x, y = pos[0]
        tried.add((x, y))
        backup = os.path.join(WORK, "before_cleanup.kicad_pcb")
        shutil.copy(path, backup)
        subprocess.run([sys.executable, os.path.abspath(__file__), "--remove-track", str(x), str(y)],
                       capture_output=True, check=True)
        if len(drc(path)["unconnected_items"]) > base:
            shutil.copy(backup, path)                    # that stub carries a connection: keep it
        else:
            total += 1
    return total


def trim_stubs(path):
    """delete pre-routed stubs that Freerouting did not use: at each dangling position (a pad centre shared by the stub
    and the router's own track) the track whose other end touches nothing of its net goes.  One process, one save;
    the board is put back if a connection opened"""
    rep = drc(path)
    pos = [(v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]) for v in rep["violations"]
           if v["type"] == "track_dangling"]
    if not pos:
        return 0
    base = len(rep["unconnected_items"])
    backup = os.path.join(WORK, "before_trim.kicad_pcb")
    shutil.copy(path, backup)
    board = pcbnew.LoadBoard(path)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]

    def near(p, q):
        return abs(p.x - q.x) < 10000 and abs(p.y - q.y) < 10000          # 0.01 mm

    def free(t, q):
        """nothing of t's net touches point q on t's layer (same-layer tracks, vias, pads on that layer)"""
        net, layer = t.GetNetCode(), t.GetLayer()
        if any(p.GetNetCode() == net and p.IsOnLayer(layer) and p.GetBoundingBox().Contains(q) for p in pads):
            return False
        if any(v.GetNetCode() == net and near(v.GetPosition(), q) for v in vias):
            return False
        return not any(u is not t and u.GetNetCode() == net and u.GetLayer() == layer
                       and (near(u.GetStart(), q) or near(u.GetEnd(), q) or u.HitTest(q, 0))      # ends or a T-junction
                       for u in tracks)
    kill = []
    for x, y in pos:
        at = pcbnew.VECTOR2I(mm(x), mm(y))
        for t in tracks:
            if t in kill:
                continue
            if near(t.GetStart(), at) and free(t, t.GetEnd()):
                kill.append(t)
            elif near(t.GetEnd(), at) and free(t, t.GetStart()):
                kill.append(t)
    for t in kill:
        board.Remove(t)
    pcbnew.SaveBoard(path, board)
    if len(drc(path)["unconnected_items"]) > base:
        shutil.copy(backup, path)
        print("  pruning opened a connection; board restored")
        return 0
    return len(kill)


def report():
    rep = drc(BOARD)
    errs = [v for v in rep["violations"] if v["severity"] == "error"]
    warns = [v for v in rep["violations"] if v["severity"] != "error" and v["type"] != "lib_footprint_issues"]
    print(f"DRC: {len(errs)} errors, {len(warns)} warnings, {len(rep['unconnected_items'])} unconnected")
    for v in errs[:20] + warns[:20]:
        print("  ", v["severity"], v["type"], v["description"][:80], v["items"][0]["pos"])


if __name__ == "__main__" and "--remove-track" in sys.argv:
    i = sys.argv.index("--remove-track")
    sys.exit(0 if remove_track_at(BOARD, float(sys.argv[i + 1]), float(sys.argv[i + 2])) else 1)

if __name__ == "__main__" and "--trim-stubs" in sys.argv:
    print("trimmed", trim_stubs(BOARD), "stubs")
    report()
    sys.exit(0)

if __name__ == "__main__" and CLEANUP_ONLY:
    print("removed", remove_dangling(BOARD), "dangling stubs")
    report()
    sys.exit(0)

PLANE_LAYERS = ("In1.Cu",)                              # a 4-layer board's 0V plane: not routed on, reached by vias
PLANE_NET = "0V"                                        # 2 layers (tools/layers2.py): the B.Cu pour is the 0V plane; the router
#                                                         leaves 0V alone (tools/plane_vias.py drops its vias) unless ROUTE_0V=1
HV_NETS = ("+BATB", "+SW", "+OUT")                     # the 33.6 V nets: SimpleBatteryPack.kicad_dru's hv34 asks 0.5 mm
POWER_CLR, HV_CLR = 300, 500                            # um: the .kicad_dru's power_tracks / hv34 margins


def patch_dsn(path):
    """give Freerouting the board's stricter rules, in the DSN only (KiCad's netclasses keep 0.2 mm so the pad rows inside
    one footprint stay legal): plane layers as power layers, the Power class at 0.3 mm, the 33.6 V nets in their own class
    at 0.5 mm"""
    s = open(path).read()
    planes = [lay for lay in PLANE_LAYERS if re.search(r"\(layer %s\s" % re.escape(lay), s)]
    for lay in planes:
        s, n = re.subn(r"(\(layer %s\s*\(type )signal\)" % re.escape(lay), r"\1power)", s)
        assert n == 1, lay
    if not planes and os.environ.get("ROUTE_0V") != "1":    # no inner plane: keep the router off the plane net by leaving
        m = re.search(r"\(net %s\s*\(pins ([^)]*)\)" % re.escape(PLANE_NET), s)   # it one pin (its other pads reach the
        assert m, "no %s net in the DSN" % PLANE_NET                                    # B.Cu pour through plane_vias / THT)
        s = s[:m.start(1)] + m.group(1).split()[0] + s[m.end(1):]
        planes = ["%s left to the B.Cu pour" % PLANE_NET]
    m = re.search(r"\(class Power ([^(]*)\(circuit\s*\(use_via ([^)]*)\)\s*\)\s*\(rule\s*\(width (\d+)\)\s*\(clearance \d+\)\s*\)\s*\)", s)
    assert m, "no Power class in the DSN"
    nets = m.group(1).split()
    hv = [n for n in nets if n.strip('"') in HV_NETS]
    rest = [n for n in nets if n not in hv]
    block = ("(class Power %s\n      (circuit\n        (use_via %s)\n      )\n      (rule\n        (width %s)\n        (clearance %d)\n      )\n    )\n"
             "    (class HV %s\n      (circuit\n        (use_via %s)\n      )\n      (rule\n        (width %s)\n        (clearance %d)\n      )\n    )"
             % (" ".join(rest), m.group(2), m.group(3), POWER_CLR, " ".join(hv), m.group(2), m.group(3), HV_CLR))
    s = s[:m.start()] + block + s[m.end():]
    open(path, "w").write(s)
    print("DSN: %s, Power %d um, HV %s %d um" % (",".join(planes) or "no plane", POWER_CLR, " ".join(hv), HV_CLR))


def stage(name):
    """one board edit per process: pcbnew does not survive rip + stub + export in a single interpreter"""
    board = pcbnew.LoadBoard(BOARD)
    if name == "rip":
        print("ripped", rip(board), "tracks/vias")
        if os.path.exists(PREROUTE):
            sys.path.insert(0, os.path.join(ROOT, "..", "tools"))
            r = json.load(open(PREROUTE))
            for t in r["tracks"]:
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(mm(t["a"][0]), mm(t["a"][1]))); tr.SetEnd(pcbnew.VECTOR2I(mm(t["b"][0]), mm(t["b"][1])))
                tr.SetWidth(mm(t["w"])); tr.SetLayer(pcbnew.F_Cu if t["layer"] == "F" else pcbnew.B_Cu)
                tr.SetNet(board.FindNet(t["net"])); tr.SetLocked(True); board.Add(tr)
            for v in r.get("vias", []):                  # through vias (tools/j3_bus.py)
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(pcbnew.VECTOR2I(mm(v["at"][0]), mm(v["at"][1]))); via.SetWidth(mm(v["d"])); via.SetDrill(mm(v["drill"]))
                via.SetNet(board.FindNet(v["net"])); via.SetLocked(True); board.Add(via)
            print("pre-routed", len(r["tracks"]), "locked tracks and", len(r.get("vias", [])), "vias from", PREROUTE)
    elif name == "stubs":
        print("stubs:", add_stubs(board))
    elif name == "dsn":
        assert pcbnew.ExportSpecctraDSN(board, os.path.join(WORK, "SimpleBatteryPack.dsn")), "DSN export failed"
        patch_dsn(os.path.join(WORK, "SimpleBatteryPack.dsn"))
        return
    elif name == "ses":
        assert pcbnew.ImportSpecctraSES(board, os.path.join(WORK, "SimpleBatteryPack.ses")), "SES import failed"
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())         # refill: stale fills read as hundreds of clearance errors
    pcbnew.SaveBoard(BOARD, board)


if __name__ == "__main__" and "--stage" in sys.argv:
    stage(sys.argv[sys.argv.index("--stage") + 1])
    sys.exit(0)


def run_stage(name):
    r = subprocess.run([sys.executable, "-u", os.path.abspath(__file__), "--stage", name], capture_output=True, text=True)
    out = [l for l in (r.stdout + r.stderr).splitlines() if "Debug:" not in l and "memory leak" not in l]
    print("\n".join(out[-3:]))
    if r.returncode != 0:
        sys.exit(f"stage {name} failed (exit {r.returncode})")


if __name__ == "__main__":                              # the full pipeline (--continue: keep the routing, finish what is open)
    if "--continue" not in sys.argv:
        run_stage("rip")
        run_stage("stubs")
    run_stage("dsn")
    dsn, ses = os.path.join(WORK, "SimpleBatteryPack.dsn"), os.path.join(WORK, "SimpleBatteryPack.ses")
    if os.path.exists(ses):
        os.remove(ses)
    log = open(os.path.join(WORK, "freerouting.log"), "w")
    cmd = [JAVA, "-jar", JAR] if os.path.exists(JAR) else [FREEROUTING_APP]      # the macOS app's own launcher otherwise
    subprocess.run(cmd + ["-de", dsn, "-do", ses, "-mp", str(PASSES), "--gui.enabled=false"],
                   stdout=log, stderr=subprocess.STDOUT, timeout=3600)
    assert os.path.exists(ses), "Freerouting produced no SES (see route/freerouting.log)"
    run_stage("ses")
    shutil.copy(BOARD, os.path.join(WORK, "before_cleanup.kicad_pcb"))
    if not KEEP_STUBS:
        print("removed", remove_dangling(BOARD), "dangling stubs")
    report()
