"""Search the JLCPCB parts library (basic parts first, then by stock).  python tools/jlc_search.py "keyword" [n]"""
import sys
from lcsc_check import get_json


def search(kw, n=8):
    r = get_json("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList",
                 {"keyword": kw, "currentPage": 1, "pageSize": 30})
    lst = (r.get("data") or {}).get("componentPageInfo", {}).get("list") or []
    lst.sort(key=lambda c: (c["componentLibraryType"] != "base", -(c["stockCount"] or 0)))
    return lst[:n]


if __name__ == "__main__":
    for c in search(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 8):
        print(f"{c['componentCode']:9s} {c['componentLibraryType']:6s} {c['stockCount']:>9d}  {c['componentModelEn'][:28]:28s} "
              f"{c['componentBrandEn'][:18]:18s} {c['componentSpecificationEn'][:12]:12s} {(c.get('describe') or '')[:70]}")
