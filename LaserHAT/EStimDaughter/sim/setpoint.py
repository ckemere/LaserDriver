"""
Set-point accuracy and phase matching across the DAC range: one cathodic-first pair (100 us / 50 us / 100 us) into the
nominal electrode at each current.  Plateau current of each phase vs the ideal code/4096 * VREF / R14, and the
cathodic/anodic mismatch (which sets charge balance).  Component tolerances (0.1 % resistors, TL431, DAC INL/offset)
are not in the model: this checks the circuit, i.e. U5A/U5B offsets and gain, ADG1436 switches R_on, C15 settling, C16.

  python setpoint.py [--quick]        -> results/setpoint.json, results/setpoint.png
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spice import VALUES, code_for, i_full_scale, module_deck, run_robust

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
T0, PW, GAP = 10e-6, 100e-6, 50e-6


def pair(I, Rs=10e3, Cdl=2.2e-9):
    code = code_for(I)
    ideal = code / 4096 * i_full_scale()
    tstop = T0 + 2 * PW + GAP + 30e-6
    deck = module_deck(code, 1, PW, GAP, 10e-3, Rs=Rs, Cdl=Cdl) + "\n{OPTS}\n" + f".tran 20n {tstop} 0 50n\n"
    r = run_robust(deck, ["v(e1_out)", "v(xel.n1)"], tstop)
    t = r["time"]
    i = (r["v(e1_out)"] - r["v(xel.n1)"]) / Rs
    mc = (t > T0 + 0.5 * PW) & (t < T0 + PW)
    ma = (t > T0 + PW + GAP + 0.5 * PW) & (t < T0 + 2 * PW + GAP)
    ic, ia = -np.mean(i[mc]), np.mean(i[ma])
    qc = -np.trapezoid(i[(t > T0 - 1e-6) & (t < T0 + PW + GAP / 2)], t[(t > T0 - 1e-6) & (t < T0 + PW + GAP / 2)])
    qa = np.trapezoid(i[(t >= T0 + PW + GAP / 2) & (t < tstop)], t[(t >= T0 + PW + GAP / 2) & (t < tstop)])
    return dict(I=I, code=code, ideal=ideal, cath=ic, anod=ia, err_c=(ic / ideal - 1) * 100, err_a=(ia / ideal - 1) * 100,
                q_mismatch=(qa - qc) / qc * 100, t=t.tolist() if I == 250e-6 else None, i=i.tolist() if I == 250e-6 else None)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    currents = [250e-6] if quick else [20e-6, 50e-6, 100e-6, 250e-6, 500e-6]
    res = []
    for I in currents:
        r = pair(I)
        res.append(r)
        print(f"I {I * 1e6:5.0f} uA (code {r['code']:4d}, ideal {r['ideal'] * 1e6:8.3f} uA): cathodic {r['cath'] * 1e6:8.3f} uA "
              f"({r['err_c']:+.3f} %), anodic {r['anod'] * 1e6:8.3f} uA ({r['err_a']:+.3f} %), "
              f"pair charge mismatch {r['q_mismatch']:+.4f} %", flush=True)
    json.dump([{k: v for k, v in r.items() if k not in ("t", "i")} for r in res],
              open(os.path.join(OUT, "setpoint.json"), "w"), indent=1)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.2))
    r250 = next(r for r in res if r["t"] is not None)
    axs[0].plot(np.array(r250["t"]) * 1e6, np.array(r250["i"]) * 1e6, lw=1)
    axs[0].set_xlabel("t (µs)"); axs[0].set_ylabel("electrode current (µA, + = into E1)")
    axs[0].set_title("250 µA cathodic-first pair, 100 / 50 / 100 µs", fontsize=10)
    axs[1].plot([r["I"] * 1e6 for r in res], [r["err_c"] for r in res], "-o", label="cathodic error vs ideal")
    axs[1].plot([r["I"] * 1e6 for r in res], [r["err_a"] for r in res], "-o", label="anodic error vs ideal")
    axs[1].plot([r["I"] * 1e6 for r in res], [r["q_mismatch"] for r in res], "-o", label="pair charge mismatch")
    axs[1].set_xscale("log"); axs[1].set_xlabel("set current (µA)"); axs[1].set_ylabel("%")
    axs[1].legend(fontsize=8, frameon=False)
    for a in axs:
        a.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "setpoint.png"), dpi=120)
