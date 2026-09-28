"""
Phase 2 - check every LCSC number in the BOM: manufacturer part, package, LCSC stock, JLCPCB stock / basic-vs-extended,
datasheet URL.  Writes parts/lcsc.json and prints a table.  Optional: --pdf C1234 ... downloads datasheets to parts/ds/.
Run:  micromamba run -n kicad python tools/lcsc_check.py [--pdf C528652 C2833 ...]
"""
import csv
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def get_json(url, data=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def lcsc(code):
    r = get_json(f"https://wmsc.lcsc.com/ftps/wm/product/detail?productCode={code}")["result"]
    if not r:
        return None
    return dict(mpn=r.get("productModel"), brand=r.get("brandNameEn"), package=r.get("encapStandard"),
                lcsc_stock=r.get("stockNumber"), desc=r.get("productDescEn"), pdf=r.get("pdfUrl"),
                price=(r.get("productPriceList") or [{}])[0].get("usdPrice"))


def jlc(code):
    """JLCPCB parts library: stock and basic/extended.  Returns None if the endpoint refuses."""
    try:
        r = get_json("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList",
                     {"keyword": code, "currentPage": 1, "pageSize": 5})
        for c in (r.get("data") or {}).get("componentPageInfo", {}).get("list") or []:
            if c.get("componentCode") == code:
                return dict(jlc_stock=c.get("stockCount"), jlc_type=c.get("componentLibraryType"))
    except Exception as e:  # noqa: BLE001
        return dict(jlc_error=type(e).__name__)
    return dict(jlc_stock=None, jlc_type=None)


if __name__ == "__main__":
    rows = list(csv.DictReader(open(os.path.join(ROOT, "bom_EStimDaughter.csv"), newline="")))
    codes = {}
    for r in rows:
        if r["LCSC"]:
            codes.setdefault(r["LCSC"], []).append(r["Ref"])
    out = {}
    for code, refs in codes.items():
        d = lcsc(code) or {"error": "not found"}
        d.update(jlc(code))
        d["refs"] = refs
        d["value"] = next(r["Value"] for r in rows if r["Ref"] == refs[0])
        out[code] = d
        print(f"{code:9s} {','.join(refs):22s} {d['value'][:18]:18s} -> {str(d.get('mpn'))[:26]:26s} {str(d.get('brand'))[:16]:16s} "
              f"{str(d.get('package'))[:12]:12s} LCSC {str(d.get('lcsc_stock')):>8s}  JLC {str(d.get('jlc_stock')):>8s} "
              f"{str(d.get('jlc_type') or d.get('jlc_error') or '')}", flush=True)
        time.sleep(0.3)
    os.makedirs(os.path.join(ROOT, "parts"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "parts", "lcsc.json"), "w"), indent=1)
    if "--pdf" in sys.argv:
        os.makedirs(os.path.join(ROOT, "parts", "ds"), exist_ok=True)
        for code in sys.argv[sys.argv.index("--pdf") + 1:]:
            url = out.get(code, {}).get("pdf") or lcsc(code)["pdf"]
            dst = os.path.join(ROOT, "parts", "ds", f"{code}.pdf")
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
                f.write(r.read())
            print("saved", dst)
