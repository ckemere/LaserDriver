"""draw route/board.json per copper layer with unrouted links (micromamba run -n kicad python tools/plot_board.py)"""
import json, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "route", "board.json")))
pl = json.load(open(os.path.join(ROOT, "route", "placement.json")))
X0, X1, Y0, Y1 = pl["outline"]
cols = {"F": "#c0392b", "In2": "#d4a017", "B": "#2a78d6"}
fig, axs = plt.subplots(1, 3, figsize=(20, 6.6))
for ax, lay in zip(axs, ("F", "In2", "B")):
    for r in pl["barrier"]:
        ax.add_patch(Rectangle((r[0], r[2]), r[1]-r[0], r[3]-r[2], color="#e5e5e5", lw=0))
    for s, a, b_, c, e, ref in d["pads"]:
        if lay in s or (lay == "In2" and s == "FB"):
            ax.add_patch(Rectangle((a, c), b_-a, e-c, color="#888" if s == "FB" else "#555", lw=0))
    for l, x1, y1, x2, y2, w in d["tracks"]:
        if l == lay:
            ax.plot([x1, x2], [y1, y2], color=cols[lay], lw=w*5, solid_capstyle="round")
    for x, y in d["vias"]:
        ax.plot(x, y, "o", ms=3, mfc="w", mec="k", mew=0.6)
    for x1, y1, x2, y2 in d["links"]:
        ax.plot([x1, x2], [y1, y2], color="#00a000", lw=0.8)
    ax.add_patch(Rectangle((X0, Y0), X1-X0, Y1-Y0, fill=False, ec="k", lw=1))
    ax.set_xlim(X0-1, X1+1); ax.set_ylim(Y1+2, Y0-1); ax.set_aspect("equal"); ax.set_title(lay + "  (green = unrouted)", fontsize=9)
plt.tight_layout(); plt.savefig(os.path.join(ROOT, "route", "board.png"), dpi=100)
