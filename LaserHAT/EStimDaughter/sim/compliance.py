"""
Compliance: how long can the module hold a constant cathodic current into a worst-case electrode before U5A saturates?

The load voltage during a phase is  I*Rs + I*t/Cdl (+ I*t/C16), and the stage runs out of headroom when it nears
V_rail - I*(R13 + R14) - ~0.5 V.  Simulated with the full module deck (U5A/U5B TI models, ADG1436 switches, DG419, hold timer):
one long cathodic phase, t_max = time the electrode current first falls 1 % below its plateau.

  python compliance.py [--quick]      -> results/compliance.json, results/compliance.png
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spice import VALUES, RAIL, code_for, module_deck, run_robust

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
T0, PW = 10e-6, 1.0e-3          # one 1 ms cathodic phase (longer than any real phase)


def t_max(I, V, Rs, Cdl):
    deck = module_deck(code_for(I), 1, PW, 50e-6, 10e-3, V=V, Rs=Rs, Cdl=Cdl) + "\n{OPTS}\n" + \
        f".tran 50n {T0 + PW} 0 100n\n"
    r = run_robust(deck, ["v(e1_out)", "v(xel.n1)", "v(e1)"], T0 + PW)
    t = r["time"]
    i = (r["v(e1_out)"] - r["v(xel.n1)"]) / Rs          # + = into E1 (anodic); cathodic phase is negative
    m = (t > T0 + 5e-6) & (t < T0 + 20e-6)
    plateau = np.mean(np.abs(i[m]))
    after = (t > T0 + 20e-6) & (t < T0 + PW)
    low = np.where(np.abs(i[after]) < 0.99 * plateau)[0]
    return (t[after][low[0]] - T0) if len(low) else PW, plateau, np.min(r["v(e1)"])


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    currents = [100e-6, 500e-6] if quick else [50e-6, 100e-6, 200e-6, 300e-6, 400e-6, 500e-6]
    cases = [(RAIL, 15e3, 1.6e-9, "±15 V, Rs 15k, Cdl 1.6n (worst electrode)")]
    if not quick:
        cases += [(0.95 * RAIL, 15e3, 1.6e-9, "±14.25 V (converter −5 %), worst electrode"),
                  (RAIL, 10e3, 2.2e-9, "±15 V, Rs 10k, Cdl 2.2n (nominal)"),
                  (16.8, 15e3, 1.6e-9, "±16.8 V (4S Li-ion packs), worst electrode")]
    res = []
    for V, Rs, Cdl, label in cases:
        for I in currents:
            tm, plateau, e1min = t_max(I, V, Rs, Cdl)
            res.append(dict(label=label, V=V, Rs=Rs, Cdl=Cdl, I=I, t_max=tm, plateau=plateau, e1_min=e1min))
            print(f"{label:48s} I {I * 1e6:5.0f} uA: plateau {plateau * 1e6:7.2f} uA, "
                  f"max phase {'>= 1000' if tm >= PW else f'{tm * 1e6:7.1f}'} us, E1 min {e1min:+.2f} V", flush=True)
    json.dump(res, open(os.path.join(OUT, "compliance.json"), "w"), indent=1)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for label in dict.fromkeys(r["label"] for r in res):
        rr = [r for r in res if r["label"] == label]
        ax.plot([r["I"] * 1e6 for r in rr], [min(r["t_max"], PW) * 1e6 for r in rr], "-o", ms=4, label=label)
    ax.axhline(100, color="0.5", lw=0.8, ls="--"); ax.text(55, 110, "100 µs (longest spec phase)", fontsize=8, color="0.4")
    ax.set_yscale("log"); ax.set_xlabel("phase current (µA)"); ax.set_ylabel("max phase width before compliance (µs)")
    ax.set_title("Compliance: max cathodic phase width vs current", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, frameon=False)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "compliance.png"), dpi=120)
