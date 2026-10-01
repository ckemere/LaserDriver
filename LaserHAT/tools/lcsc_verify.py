#!/usr/bin/env python3
"""Check every LCSC code in tools/lcsc_parts.py against the LCSC / JLCPCB catalogs.

    python tools/lcsc_verify.py [--refresh]        (kicad venv; network for --refresh)

--refresh queries LCSC (MPN, brand, package, description, parameter table, datasheet) and JLC
(basic/extended, stock) for every code and writes tools/lcsc_catalog.json, which stamp_lcsc.py
also uses for the Description / Datasheet fields.  Without it the cached file is used.
Then every reference on each board is compared with the catalog:
  * R / C / L: the number in the schematic Value (2k, 100nF, 0.47uF, 10uH, 2R ...) must equal LCSC's
    Resistance / Capacitance / Inductance parameter (or the number in its description)
  * other parts: the LCSC MPN must appear in the Value or the Value in the MPN; Values that are just
    labels (LED "MCU", switch "FIRE") are printed with the MPN for a human look, not failed
  * the footprint's size code (0402, 0603, 0805, 1206) must match the LCSC package
Exit code 1 on any mismatch.  Run before every fab export; jlc_fab.py refuses stale fields anyway.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "EStimDaughter", "tools"))
import lcsc_parts  # noqa: E402

CATALOG = os.path.join(HERE, "lcsc_catalog.json")
SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "R": 1, "": 1}
PARAM = {"R": "Resistance", "RS": "Resistance", "C": "Capacitance", "L": "Inductance"}


def refresh(codes):
    from lcsc_check import get_json, jlc
    out = {}
    for code in sorted(codes):
        r = get_json(f"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={code}")["result"] or {}
        params = {p.get("paramNameEn"): p.get("paramValueEn") for p in (r.get("paramVOList") or [])}
        d = dict(mpn=r.get("productModel"), brand=r.get("brandNameEn"), package=r.get("encapStandard"),
                 desc=r.get("productDescEn") or r.get("productIntroEn"), pdf=r.get("pdfUrl"),
                 price=(r.get("productPriceList") or [{}])[0].get("usdPrice"), lcsc_stock=r.get("stockNumber"),
                 params={k: v for k, v in params.items() if k in ("Resistance", "Capacitance", "Inductance", "Tolerance",
                                                                   "Power(Watts)", "Voltage Rating", "Voltage - Rated")})
        d.update(jlc(code))
        out[code] = d
        print(f"{code:10s} {str(d['mpn'])[:26]:26s} {str(d['package'])[:12]:12s} {str(d.get('jlc_type')):6s} "
              f"{str(d['params'].get('Resistance') or d['params'].get('Capacitance') or d['params'].get('Inductance') or ''):8s} "
              f"{str(d['desc'])[:60]}", flush=True)
        time.sleep(0.25)
    json.dump(out, open(CATALOG, "w"), indent=1, ensure_ascii=False)
    return out


def number(text):
    """First SI quantity in a string -> float: '4.7k' 4700, '100nF' 1e-7, '2R' 2, '2kΩ' 2000, '0.47uF' 4.7e-7, '2Ω' 2."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*([pnuµmkKMR]?)(?![0-9.])", text)
    return float(m.group(1)) * SI[m.group(2)] if m else None


def norm(s):
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


def check(board_name, table, cat, pcb_path):
    import pcbnew
    board = pcbnew.LoadBoard(pcb_path)
    bad = 0
    for ref, code in sorted(table.items()):
        fp = board.FindFootprintByReference(ref)
        e = cat.get(code)
        if fp is None:
            print(f"{board_name} {ref:5s} {code}: not on the board"); bad += 1; continue
        if not e or not e.get("mpn"):
            print(f"{board_name} {ref:5s} {code}: not in the catalog (run --refresh)"); bad += 1; continue
        value, fpn = fp.GetValue(), fp.GetFPID().GetLibItemName().wx_str()
        desc, pk = e.get("desc") or "", e.get("package") or ""
        kind = ref.rstrip("0123456789").upper()
        problems, note = [], ""
        if kind in PARAM:
            lcsc_val = (e.get("params") or {}).get(PARAM[kind]) or desc
            want, got = number(value), number(lcsc_val) if lcsc_val else None
            if want is None or got is None or abs(want - got) > 0.02 * max(want, got):
                problems.append(f"value {value!r} vs LCSC {lcsc_val!r}")
        else:
            v, m = norm(value), norm(e["mpn"])
            if not (m in v or v in m or m[:6] in v or norm(code) in v):
                if len(re.findall(r"\d", value)) >= 2:   # looks like a part number, so it must agree ("5V" is a label)
                    problems.append(f"value {value!r} vs MPN {e['mpn']!r}")
                else:
                    note = f"(label value; part is {e['mpn']})"
        size = re.search(r"_(0402|0603|0805|1206|1210)_", fpn)
        if size and size.group(1) not in pk:
            problems.append(f"footprint {fpn} vs package {pk!r}")
        if problems:
            bad += 1
            print(f"{board_name} {ref:5s} {code:10s} MISMATCH: " + "; ".join(problems))
        else:
            print(f"{board_name} {ref:5s} {code:10s} ok  {value[:22]:22s} = {e['mpn'][:22]:22s} {pk[:10]:10s} "
                  f"{str(e.get('jlc_type'))[:6]:6s} {desc[:48]} {note}")
    return bad


def estim_table():
    """The e-stim module's own list (EStimDaughter/bom_EStimDaughter.csv: Ref, Value, Footprint, LCSC, Note)."""
    import csv
    rows = list(csv.DictReader(open(os.path.join(ROOT, "EStimDaughter", "bom_EStimDaughter.csv"), newline="")))
    return {r["Ref"]: r["LCSC"] for r in rows if r.get("LCSC")}


def check_fields(board_name, table, pcb_path, field):
    """The footprint field the Fabrication Toolkit reads must carry the table's code."""
    import pcbnew
    board = pcbnew.LoadBoard(pcb_path)
    bad = 0
    for ref, code in sorted(table.items()):
        fp = board.FindFootprintByReference(ref)
        got = fp.GetFieldsText().get(field, "") if fp else None
        if got != code:
            bad += 1
            print(f"{board_name} {ref:5s} field {field!r} = {got!r}, list says {code}")
    return bad


def main():
    estim = estim_table()
    tables = (("HAT", lcsc_parts.HAT, "LaserDriver.kicad_pcb", "LCSC Part #"),
              ("LASER", lcsc_parts.LASER, os.path.join("LaserDaughter", "LaserDaughter.kicad_pcb"), "LCSC Part #"),
              ("ESTIM", estim, os.path.join("EStimDaughter", "EStimDaughter.kicad_pcb"), "LCSC"))
    codes = set().union(*(set(t.values()) for _, t, _, _ in tables))
    cat = json.load(open(CATALOG)) if os.path.exists(CATALOG) else {}
    if "--refresh" in sys.argv or codes - set(cat) or any("params" not in cat[c] for c in codes & set(cat)):
        cat = refresh(codes)
    bad = 0
    for name, table, pcb, field in tables:
        bad += check(name, table, cat, os.path.join(ROOT, pcb))
        bad += check_fields(name, table, os.path.join(ROOT, pcb), field)
    print("mismatches:", bad)
    sys.stdout.flush()
    os._exit(1 if bad else 0)


if __name__ == "__main__":
    main()
