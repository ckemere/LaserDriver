#!/usr/bin/env python3
"""Headless "Update PCB from Schematic" (run with KiCad's bundled Python: it needs pcbnew).

    $KICAD_PY tools/pcb_sync.py <board.kicad_pcb> <netlist.net> [--src other.kicad_pcb ...]
                                [--keep-tracks]

* footprints are matched by reference; the symbol path (KIID path) is rewritten from
  the netlist so schematic<->PCB links stay valid (CLAUDE.md UUID invariant)
* a footprint whose library ID changed is swapped in place (same position/side)
* new footprints are loaded from the KiCad libraries, or copied from a --src board
  that already contains the same reference+FPID, and parked to the right of the board
* footprints with no schematic symbol are deleted (board-only items with an empty
  path, e.g. mounting holes and logos, are kept)
* every pad gets its net from the netlist; tracks, vias and non-GND zones are removed
  unless --keep-tracks is given
"""
import argparse
import os
import re

import pcbnew
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr_patch import parse  # noqa: E402

STD_FP_DIR = os.environ.get("KICAD_FOOTPRINTS") or next((d for d in ("/usr/share/kicad/footprints", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints") if os.path.isdir(d)), "/usr/share/kicad/footprints")
PROJECT_FP_LIBS = {   # fp-lib-table nicknames of the project libraries
    "Footprints": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "Footprints.pretty"),
}


def parse_netlist(path):
    """-> ({ref: {value, fpid, path, dnp}}, {(ref, pin): netname}) from a kicadsexpr netlist."""
    t = open(path).read()
    root = parse(t)

    def s(tok):
        return tok[2][1:-1].replace('\\"', '"') if tok[2].startswith('"') else tok[2]

    comps = {}
    for c in root.child("components").children:
        f = {ch.head: ch for ch in c.children}
        ref = s(f["ref"].tokens[1])
        sp = s(f["sheetpath"].child("tstamps").tokens[1])
        ts = s(f["tstamps"].tokens[1])
        dnp = any(ch.head == "property" and s(ch.child("name").tokens[1]) == "dnp"
                  for ch in c.children)
        comps[ref] = dict(value=s(f["value"].tokens[1]),
                          fpid=s(f["footprint"].tokens[1]) if "footprint" in f else "",
                          path=sp + ts, dnp=dnp)
    nets = {}
    for n in root.child("nets").children:
        name = s(n.child("name").tokens[1])
        for node in n.children:
            if node.head == "node":
                nets[(s(node.child("ref").tokens[1]), s(node.child("pin").tokens[1]))] = name
    return comps, nets


def load_fp(fpid, library):
    """Copy of a footprint already present on a source board, else load from the KiCad libs."""
    if fpid in library:
        return pcbnew.FOOTPRINT(library[fpid])      # copy constructor
    nick, name = fpid.split(":")
    lib = PROJECT_FP_LIBS.get(nick) or os.path.join(STD_FP_DIR, nick + ".pretty")
    try:                                   # KiCad 9.0.8's pcbnew.FootprintLoad() loses its plugin after a LoadBoard()
        fp = pcbnew.PCB_IO_KICAD_SEXPR().FootprintLoad(lib, name)
    except Exception:                      # noqa: BLE001
        fp = pcbnew.FootprintLoad(lib, name)
    if fp is None:
        raise RuntimeError(f"cannot load footprint {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(nick, name))
    return fp


def sync(board_path, net_path, src_paths=(), keep_tracks=False, out=None):
    comps, pinnets = parse_netlist(net_path)
    board = pcbnew.LoadBoard(board_path)
    # pcbnew's SWIG wrappers degrade once a board starts being mutated, so do every
    # lookup and library load first, and all the mutation afterwards.
    sources = [pcbnew.LoadBoard(p) for p in (board_path, *src_paths)]
    library = {}
    for sb in sources:
        for f in sb.GetFootprints():
            library.setdefault(f.GetFPIDAsString(), f)
    existing = {f.GetReference(): f for f in board.GetFootprints()}
    matched = sum(1 for r in existing if r in comps)
    # guard against a mis-parsed netlist: most schematic parts should already exist
    if existing and matched < 0.4 * len(comps):
        raise SystemExit(f"only {matched} of {len(comps)} netlist parts are on the board; refusing")
    to_remove = [f for r, f in existing.items() if r not in comps and f.GetPath().AsString() != ""]
    new_fps = {}
    for ref, c in sorted(comps.items()):
        f = existing.get(ref)
        if f is None or f.GetFPIDAsString() != c["fpid"]:
            new_fps[ref] = load_fp(c["fpid"], library)
    names = sorted(set(pinnets.values()))
    nets = {n: board.FindNet(n) for n in names}
    for n in names:
        if nets[n] is None:
            nets[n] = pcbnew.NETINFO_ITEM(board, n)
    orphan = board.FindNet(0)
    tracks = [] if keep_tracks else list(board.GetTracks())
    zones = [z for z in board.Zones()
             if not keep_tracks and not z.GetIsRuleArea() and z.GetNetname() != "GND"]

    # ---- mutation ----
    for n in names:
        if board.FindNet(n) is None:
            board.Add(nets[n])
    park_x, park_y = 180.0, 45.0
    for ref, fp in new_fps.items():
        old = existing.get(ref)
        if old is not None:
            fp.SetPosition(old.GetPosition())
            if old.IsFlipped():
                fp.Flip(fp.GetPosition(), False)
            fp.SetOrientation(old.GetOrientation())
            to_remove.append(old)
            print("swapped footprint", ref, "->", comps[ref]["fpid"])
        else:
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(park_x), pcbnew.FromMM(park_y)))
            park_y += 6
            if park_y > 110:
                park_x, park_y = park_x + 10, 45.0
            print("added", ref, comps[ref]["fpid"])
        fp.SetReference(ref)
        board.Add(fp)
        existing[ref] = fp
    for ref, c in comps.items():
        f = existing[ref]
        f.SetValue(c["value"])
        f.SetPath(pcbnew.KIID_PATH(c["path"]))
        f.SetDNP(c["dnp"])
        for p in f.Pads():
            key = (ref, p.GetNumber())
            p.SetNet(nets[pinnets[key]] if key in pinnets else orphan)
    for f in board.GetFootprints():
        if f.GetReference() not in comps:
            for p in f.Pads():
                p.SetNet(orphan)
    for t_ in tracks:
        board.Remove(t_)
    for z in zones:
        board.Remove(z)
    for f in to_remove:
        print("removed", f.GetReference())
        board.Remove(f)
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() in nets:
            z.SetNet(nets[z.GetNetname()])
    pcbnew.SaveBoard(out or board_path, board)
    print("saved", out or board_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("netlist")
    ap.add_argument("--src", action="append", default=[])
    ap.add_argument("--keep-tracks", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    sync(a.board, a.netlist, a.src, a.keep_tracks, a.out)
