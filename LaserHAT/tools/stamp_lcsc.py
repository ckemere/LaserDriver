#!/usr/bin/env python3
"""Write the LCSC part numbers from tools/lcsc_parts.py into the schematics and boards.

    python tools/stamp_lcsc.py [HAT] [LASER]          (kicad venv: pcbnew)

For every symbol / footprint whose reference is in the table:
  * one "LCSC Part #" field (what the Fabrication Toolkit reads first) with the table's code,
  * the misspelt Rev 1 variants ("LCSC Part#", "LCSC Parth#", "LCSC Part") removed,
  * the Value replaced where lcsc_parts.VALUES says so (part changed, e.g. CAT24C32 -> M24C32).
lcsc_parts.NOT_FITTED symbols get DNP (schematic + board); lcsc_parts.HAND_FIT ones get DNP cleared,
no part-number field at all, and the footprint attribute "exclude from position files".
Other references only lose the misspelt variants.  Schematics are patched as text (KiCad 9 files
are hand-edited; kiutils cannot round-trip them), boards through pcbnew.
Refuses to touch a board that pcbnew has open (~<board>.lck).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lcsc_parts  # noqa: E402
from sexpr_patch import parse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELD = "LCSC Part #"
CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lcsc_catalog.json")


def catalog():
    """LCSC data per code (tools/lcsc_verify.py --refresh writes it): mpn, brand, package, desc, pdf."""
    import json
    return json.load(open(CATALOG)) if os.path.exists(CATALOG) else {}


def describe(entry):
    """Description text for a symbol/footprint: '<MPN> (<brand>, <package>): <LCSC description>'."""
    if not entry:
        return None
    head = entry.get("mpn") or ""
    tail = ", ".join(x for x in (entry.get("brand"), entry.get("package")) if x)
    desc = entry.get("desc") or ""
    return f"{head} ({tail}): {desc}".replace("(): ", "").rstrip(": ").strip()
VARIANTS = {"LCSC Part #", "LCSC Part#", "LCSC Parth#", "LCSC Part", "LCSC PN", "LCSC"}
BOARDS = {
    "HAT": (["LaserDriver.kicad_sch", "mspm0_controller.kicad_sch", "usb_uart.kicad_sch", "bnc_daughter_io.kicad_sch"],
            "LaserDriver.kicad_pcb", lcsc_parts.HAT),
    "LASER": (["LaserDaughter/LaserDaughter.kicad_sch"], "LaserDaughter/LaserDaughter.kicad_pcb", lcsc_parts.LASER),
    # the e-stim schematic is the module's own generator (gen_schematic.py); only its board gets the attributes
    "ESTIM": ([], "EStimDaughter/EStimDaughter.kicad_pcb", {}),
}


def _tok(node, i):
    return node.tokens[i][2].strip('"')


def stamp_schematic(path, table, values, not_fitted=(), hand_fit=(), non_parts=()):
    txt = open(path).read()
    root = parse(txt)
    edits = []          # (start, end, replacement)
    changed = set()
    cat = catalog()
    for sym in root.children:
        if sym.head != "symbol":
            continue
        props = [c for c in sym.children if c.head == "property"]
        ref = next((_tok(p, 2) for p in props if _tok(p, 1) == "Reference"), None)
        if ref is None:
            continue
        at = sym.child("at")
        x, y = _tok(at, 1), _tok(at, 2)

        def set_prop(name, value):
            """Replace the property's text, or add it (hidden) after the last property."""
            p = next((q for q in props if _tok(q, 1) == name), None)
            if p is not None:
                if _tok(p, 2) != value:
                    s, e, _ = p.tokens[2]
                    edits.append((s, e, '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'))
                    changed.add(ref)
            else:
                last = props[-1]
                new = (f'\n\t\t(property "{name}" "{value}"\n\t\t\t(at {x} {y} 0)\n\t\t\t(effects\n\t\t\t\t(font\n'
                       f'\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')
                edits.append((last.end, last.end, new))
                changed.add(ref)

        if ref in table and ref not in hand_fit and table[ref] in cat:
            entry = cat[table[ref]]            # the Rev 1 sheets carry descriptions of parts long replaced
            set_prop("Description", describe(entry))
            if entry.get("pdf"):
                set_prop("Datasheet", entry["pdf"])
        lcsc = [p for p in props if _tok(p, 1) in VARIANTS]
        placed = ref in table and ref not in hand_fit and ref not in not_fitted and ref not in non_parts
        dnp = sym.child("dnp")
        want_dnp = "yes" if ref in not_fitted else "no" if (ref in hand_fit or placed) else None
        if dnp is not None and want_dnp is not None and _tok(dnp, 1) != want_dnp:
            s, e, _ = dnp.tokens[1]
            edits.append((s, e, want_dnp))
            changed.add(ref)
        in_bom = sym.child("in_bom")
        # JLC rejects a BOM designator that is missing from the CPL, so anything JLC does not place
        # (hand-fitted, DNP, non-parts) must be out of the BOM as well, not just out of the position file;
        # a machine-placed part gets the flags cleared again (it may have been hand-fitted before)
        want_bom = "no" if (ref in non_parts or ref in hand_fit or ref in not_fitted) else "yes" if placed else None
        if in_bom is not None and want_bom is not None and _tok(in_bom, 1) != want_bom:
            s, e, _ = in_bom.tokens[1]
            edits.append((s, e, want_bom))
            changed.add(ref)
        if ref in hand_fit:              # populated by us: JLC must not see a part number
            for p in lcsc:
                edits.append(_span_with_ws(txt, p))
                changed.add(ref)
        elif ref in table:
            code = table[ref]
            keep = next((p for p in lcsc if _tok(p, 1) == FIELD), None)
            for p in lcsc:
                if p is keep:
                    if _tok(p, 2) != code:
                        s, e, _ = p.tokens[2]
                        edits.append((s, e, f'"{code}"'))
                        changed.add(ref)
                else:
                    edits.append((_span_with_ws(txt, p)))
                    changed.add(ref)
            if keep is None:
                last = props[-1]
                new = (f'\n\t\t(property "{FIELD}" "{code}"\n\t\t\t(at {x} {y} 0)\n\t\t\t(effects\n\t\t\t\t(font\n'
                       f'\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)')
                edits.append((last.end, last.end, new))
                changed.add(ref)
            if ref in values:
                vp = next(p for p in props if _tok(p, 1) == "Value")
                if _tok(vp, 2) != values[ref]:
                    s, e, _ = vp.tokens[2]
                    edits.append((s, e, f'"{values[ref]}"'))
                    changed.add(ref)
        else:
            for p in lcsc:
                if _tok(p, 1) != FIELD:
                    edits.append(_span_with_ws(txt, p))
                    changed.add(ref)
    for s, e, rep in sorted(edits, reverse=True):
        txt = txt[:s] + rep + txt[e:]
    if edits:
        open(path, "w").write(txt)
    print(f"{os.path.relpath(path, ROOT)}: {len(edits)} edits, refs {sorted(changed)}")
    return changed


def _span_with_ws(txt, node):
    """Delete a node together with the whitespace before it (keeps the file tidy)."""
    s = node.start
    while s > 0 and txt[s - 1] in " \t\n":
        s -= 1
    return (s, node.end, "")


def stamp_board(path, table, values, not_fitted=(), hand_fit=(), non_parts=()):
    import pcbnew
    lock = os.path.join(os.path.dirname(path), "~" + os.path.basename(path) + ".lck")
    if os.path.exists(lock):
        raise SystemExit(f"{lock} exists: close the board in pcbnew first")
    board = pcbnew.LoadBoard(path)
    changed = set()
    cat = catalog()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fields = fp.GetFieldsText()
        if ref in table and ref not in hand_fit and table[ref] in cat:
            entry = cat[table[ref]]
            for name, value in (("Description", describe(entry)), ("Datasheet", entry.get("pdf"))):
                f = fp.GetFieldByName(name)
                if value and f is not None and f.GetText() != value:
                    f.SetText(value)
                    changed.add(ref)
        if ref in non_parts and not (fp.IsExcludedFromBOM() and fp.IsExcludedFromPosFiles()):
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
            changed.add(ref)
        if ref in table and ref not in hand_fit and ref not in not_fitted and ref not in non_parts:
            if fp.IsDNP() or fp.IsExcludedFromBOM() or fp.IsExcludedFromPosFiles():   # machine-placed: clear
                fp.SetDNP(False)
                fp.SetExcludedFromBOM(False)
                fp.SetExcludedFromPosFiles(False)
                changed.add(ref)
        if ref in not_fitted or ref in hand_fit:
            want = ref in not_fitted
            if fp.IsDNP() != want:
                fp.SetDNP(want)
                changed.add(ref)
            if not fp.IsExcludedFromBOM():          # JLC: BOM designators must all be in the CPL
                fp.SetExcludedFromBOM(True)
                changed.add(ref)
            if ref in hand_fit and not fp.IsExcludedFromPosFiles():
                fp.SetExcludedFromPosFiles(True)
                changed.add(ref)
        if not table and ref not in hand_fit:
            continue                     # board with its own part list (e-stim): flags only, leave its fields alone
        for name in list(fields):
            if ref in hand_fit and name in VARIANTS:
                fp.RemoveField(name) if hasattr(fp, "RemoveField") else fp.Remove(fp.GetFieldByName(name))
                changed.add(ref)
            elif name in VARIANTS and (name != FIELD or ref in table):
                if ref in table and name == FIELD and fields[name] == table[ref]:
                    continue
                f = fp.GetFieldByName(name)
                if f is not None:
                    fp.RemoveField(name) if hasattr(fp, "RemoveField") else fp.Remove(f)
                    changed.add(ref)
        if ref in table and ref not in hand_fit:
            if fp.GetFieldByName(FIELD) is None:
                fp.SetField(FIELD, table[ref])
                f = fp.GetFieldByName(FIELD)
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
                changed.add(ref)
            if ref in values and fp.GetValue() != values[ref]:
                fp.SetValue(values[ref])
                changed.add(ref)
    if changed:
        pcbnew.SaveBoard(path, board)
    print(f"{os.path.relpath(path, ROOT)}: refs {sorted(changed)}")
    sys.stdout.flush()


def main(names):
    for name in names:
        sheets, board, table = BOARDS[name]
        values = lcsc_parts.VALUES.get(name, {})
        nf, hf = lcsc_parts.NOT_FITTED.get(name, set()), lcsc_parts.HAND_FIT.get(name, set())
        np_ = lcsc_parts.NON_PARTS.get(name, set())
        for sh in sheets:
            stamp_schematic(os.path.join(ROOT, sh), table, values, nf, hf, np_)
        stamp_board(os.path.join(ROOT, board), table, values, nf, hf, np_)


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if a in BOARDS] or list(BOARDS))
    os._exit(0)
