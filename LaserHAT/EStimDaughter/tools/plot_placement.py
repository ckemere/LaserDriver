"""draw route/placement.json: top and bottom courtyards over the domains (micromamba run -n kicad python tools/plot_placement.py)"""
import json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "route", "placement.json")))
X0, X1, Y0, Y1 = d["outline"]
fig, axs = plt.subplots(1, 2, figsize=(14, 6.6))
for ax, side in zip(axs, ("F", "B")):
    for r in d["hat"]:
        ax.add_patch(Rectangle((r[0], r[2]), r[1]-r[0], r[3]-r[2], color="#f3d9c9", lw=0))
    for r in d["iso"]:
        ax.add_patch(Rectangle((r[0], r[2]), r[1]-r[0], r[3]-r[2], color="#d6e6f5", lw=0))
    for r in d["barrier"]:
        ax.add_patch(Rectangle((r[0], r[2]), r[1]-r[0], r[3]-r[2], color="#bbbbbb", lw=0))
    for k, b in d["boxes"][side].items():
        tht = "#" in k
        ax.add_patch(Rectangle((b[0], b[2]), b[1]-b[0], b[3]-b[2], fill=not tht, fc="#ffffff" if not tht else "none",
                               ec="#333" if not tht else "#999", lw=0.8, ls="-" if not tht else ":"))
        if not tht:
            ax.text((b[0]+b[1])/2, (b[2]+b[3])/2, k, ha="center", va="center", fontsize=6)
    ax.add_patch(Rectangle((X0, Y0), X1-X0, Y1-Y0, fill=False, ec="k", lw=1.2))
    for ref, n, x, y, net, sd in d.get("pads", []):
        if n == "1" and sd == side:
            ax.plot(x, y, "o", ms=2.5, color="#c0392b")
    tot = 0
    nets = {}
    for ref, n, x, y, net, sd in d.get("pads", []):
        nets.setdefault(net, []).append((x, y, sd))
    for net, pts in nets.items():
        if net.startswith("GND") or len(pts) < 2:
            continue
        inn, rest = [pts[0]], pts[1:]
        while rest:   # Prim MST
            best = min(((a, b) for a in inn for b in rest), key=lambda ab: (ab[0][0]-ab[1][0])**2 + (ab[0][1]-ab[1][1])**2)
            a, b = best
            inn.append(b); rest.remove(b)
            L = ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5
            tot += L
            if a[2] == side or b[2] == side:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#1a9850" if a[2] == b[2] else "#9e0142", lw=0.5)
    ax.set_xlabel(f"ratsnest (non-GND) total {tot:.0f} mm; green same side, purple crosses sides", fontsize=8)
    ax.set_xlim(X0-1, X1+1); ax.set_ylim(Y1+2, Y0-1); ax.set_aspect("equal")
    ax.set_title(("TOP" if side == "F" else "BOTTOM (seen from top)") + "   tan = HAT domain, blue = isolated, gray = barrier", fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(ROOT, "route", "placement.png"), dpi=110)
