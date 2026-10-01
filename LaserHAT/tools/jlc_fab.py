#!/usr/bin/env python3
"""JLCPCB fabrication + assembly outputs for the three boards (KiCad bundled Python).

    $KICAD_PY tools/jlc_fab.py            -> fab/<Board>/ for LaserHAT, LaserDaughter, EStimDaughter

Per board:
  <Board>_gerbers.zip   Gerbers (Protel extensions) + Excellon drill (PTH / NPTH), upload for the PCB quote
  <Board>_BOM.csv       Comment, Designator, Footprint, LCSC Part #   (machine-assembled parts only)
  <Board>_CPL.csv       Designator, Mid X, Mid Y, Layer, Rotation      (same parts; KiCad's own pos export)
  <Board>_top.png / _bottom.png   3D renders
  README.md             stack-up, size, assembly sides, hand-fit parts, extended-part count

LCSC numbers come from tools/lcsc_parts.py (HAT, laser module) and EStimDaughter/bom_EStimDaughter.csv.
Three kinds of real part (tools/lcsc_parts.py + tools/stamp_lcsc.py keep the flags in step):
  * machine-placed: LCSC number in the table and in the "LCSC Part #" field -> BOM + CPL
  * hand-fitted (lcsc_parts.HAND_FIT): no number, footprint "exclude from position files" -> README list
  * not fitted (lcsc_parts.NOT_FITTED): DNP in the schematic -> README list
Footprints excluded from both the BOM and the position files (logo, holes, jumpers, test pads) are not parts.
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import zipfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import lcsc_parts  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
TO = pcbnew.ToMM


def estim_codes():
    rows = csv.DictReader(open(os.path.join(ROOT, "EStimDaughter", "bom_EStimDaughter.csv"), newline=""))
    return {r["Ref"]: r["LCSC"] for r in rows if r.get("LCSC")}


BOARDS = [
    ("LaserHAT", "LaserDriver.kicad_pcb", lcsc_parts.HAT),
    ("LaserDaughter", "LaserDaughter/LaserDaughter.kicad_pcb", lcsc_parts.LASER),
    ("EStimDaughter", "EStimDaughter/EStimDaughter.kicad_pcb", None),
]
BASIC = set()      # filled from parts/lcsc.json-style checks when available; see extended_count()


def cli(*args):
    p = subprocess.run([KICAD_CLI, *args], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(" ".join(args) + "\n" + p.stdout + p.stderr)


def gerbers(pcb, board, out, name):
    gdir = os.path.join(out, "gerbers")
    os.makedirs(gdir, exist_ok=True)
    for f in os.listdir(gdir):
        os.remove(os.path.join(gdir, f))
    inner = [f"In{i}.Cu" for i in range(1, board.GetCopperLayerCount() - 1)]
    layers = ["F.Cu", *inner, "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen",
              "F.Mask", "B.Mask", "Edge.Cuts"]
    cli("pcb", "export", "gerbers", "--layers", ",".join(layers), "--subtract-soldermask", "-o", gdir, pcb)
    cli("pcb", "export", "drill", "--excellon-separate-th", "--format", "excellon", "-u", "mm", "-o", gdir + "/", pcb)
    zpath = os.path.join(out, f"{name}_gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    return zpath, len(layers), sorted(os.listdir(gdir))


def cpl(pcb, out, name, refs):
    tmp = os.path.join(out, "_pos.csv")
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", tmp, pcb)
    rows = list(csv.DictReader(open(tmp, newline="")))
    os.remove(tmp)
    path = os.path.join(out, f"{name}_CPL.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            if r["Ref"] in refs:
                w.writerow([r["Ref"], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                            "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):.1f}"])
    return path


def main():
    only = set(sys.argv[1:])
    for name, rel, table in BOARDS:
        if only and name not in only:
            continue
        pcb = os.path.join(ROOT, rel)
        out = os.path.join(ROOT, "fab", name)
        os.makedirs(out, exist_ok=True)
        board = pcbnew.LoadBoard(pcb)
        codes = table if table is not None else estim_codes()
        fitted, hand, notfit, nonparts, sides = {}, [], [], [], set()
        for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
            ref = fp.GetReference()
            code = codes.get(ref)
            fpn = fp.GetFPID().GetLibItemName().wx_str()
            ftxt = fp.GetFieldsText()       # the Fabrication Toolkit's field names, in its order of preference
            field = next((ftxt[k] for k in ("LCSC Part #", "LCSC Part", "JLCPCB Part #", "LCSC") if ftxt.get(k)), "")
            if not fp.Pads() or ref.startswith(("MH", "REF", "JP", "TP")) or fpn.startswith("SolderJumper") or \
                    (fp.IsExcludedFromBOM() and fp.IsExcludedFromPosFiles()):
                nonparts.append(ref)
            elif fp.IsDNP():
                notfit.append((ref, fp.GetValue(), fpn))          # DNP = not populated at all
            elif code and not fp.IsExcludedFromBOM() and not fp.IsExcludedFromPosFiles():
                fitted[ref] = (fp.GetValue(), fpn, code)
                sides.add("Bottom" if fp.IsFlipped() else "Top")
                if field != code:            # the Fabrication Toolkit reads the field: keep them equal
                    print(f"{name}: {ref} field 'LCSC Part #' = {field!r} but lcsc_parts says {code}; run tools/stamp_lcsc.py")
            else:                            # populated by us: no number for JLC, excluded from the position file
                hand.append((ref, fp.GetValue(), fpn))
                if field or not fp.IsExcludedFromPosFiles():
                    print(f"{name}: hand-fitted {ref} should have no 'LCSC Part #' and 'exclude from position files' set; "
                          f"add it to lcsc_parts.HAND_FIT and run tools/stamp_lcsc.py")
        missing = [r for r in codes if r not in fitted and r not in [n[0] for n in notfit]]
        if missing:
            print(f"{name}: LCSC table refs not on the board / not fitted: {missing}")

        # BOM, grouped by LCSC number
        groups = {}
        for ref, (val, fpn, code) in fitted.items():
            groups.setdefault(code, [val, [], fpn])[1].append(ref)
        bom = os.path.join(out, f"{name}_BOM.csv")
        with open(bom, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
            for code, (val, refs, fpn) in sorted(groups.items(), key=lambda g: sorted(g[1][1])[0]):
                w.writerow([val, ",".join(sorted(refs, key=lambda r: (r.rstrip("0123456789"), int(r[len(r.rstrip("0123456789")):] or 0)))), fpn, code])
        cpl(pcb, out, name, set(fitted))
        zpath, nlayers, files = gerbers(pcb, board, out, name)
        for side in ("top", "bottom"):
            cli("pcb", "render", "-o", os.path.join(out, f"{name}_{side}.png"), "-w", "1600", "-h", "1200",
                "--side", side, "--background", "opaque", "--quality", "high", pcb)

        bb = board.GetBoardEdgesBoundingBox()
        w_mm, h_mm = TO(bb.GetWidth()), TO(bb.GetHeight())
        with open(os.path.join(out, "README.md"), "w") as f:
            f.write(f"# {name} — JLCPCB order files\n\n")
            f.write(f"- Board: {w_mm:.1f} × {h_mm:.1f} mm, **{board.GetCopperLayerCount()} layers**, 1.6 mm FR-4\n")
            f.write(f"- PCB quote: upload `{os.path.basename(zpath)}`\n")
            f.write(f"- Assembly: `{name}_BOM.csv` + `{name}_CPL.csv`. "
                    f"{len(fitted)} placements, {len(groups)} unique parts, sides: **{' + '.join(sorted(sides, reverse=True))}**\n")
            f.write("- Check part rotations in JLC's placement preview; KiCad and JLC orientations differ for some packages.\n\n")
            f.write("## Hand-fitted (no LCSC number, excluded from the position file; not placed by JLC)\n\n")
            for ref, val, fpn in hand:
                f.write(f"- {ref}: {val} ({fpn})\n")
            if notfit:
                f.write("\n## Not fitted (DNP)\n\n")
                for ref, val, fpn in notfit:
                    f.write(f"- {ref}: {val} ({fpn})\n")
            if nonparts:
                f.write(f"\nNot parts (jumpers, holes, logo, test pads, padless footprints): {', '.join(nonparts)}\n")
        print(f"{name}: {len(fitted)} placements / {len(groups)} unique, sides {sorted(sides)}, "
              f"{board.GetCopperLayerCount()}L {w_mm:.1f}x{h_mm:.1f} mm, hand-fit {[h[0] for h in hand]}")


if __name__ == "__main__":
    main()
