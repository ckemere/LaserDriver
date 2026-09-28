"""
Output-stage stability: U5A loop gain (Tian double injection at the op-amp output, before R13) into the electrode,
with electrode-cable capacitance from J1.1 (E1_OUT) to GND_ISO.  The DG419's 8 pF off-capacitance on E1 and ISENSE
is included; V_IN is held at 0 V (the 4053 output impedance is R12's source).

  python stability.py [--quick]       -> results/stability.json, results/stability.png
Pass criterion used in the design: phase margin >= 45 deg for cable C up to 500 pF.
"""
import itertools
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spice import VALUES, RAIL, ELECTRODE, include_models, rails, output_stage, tian_loop_gain, phase_margin

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def loop(cable_c, Rs, Cdl, V=RAIL, v=VALUES):
    body = "\n".join([
        "* U5A loop gain", include_models(), ELECTRODE, rails(V),
        "VVIN V_IN 0 0",
        output_stage(v, cable_c=cable_c, loop_break=True),
        f"CDG_D E1 0 {v['COFF_DG419']}", f"CDG_S ISENSE 0 {v['COFF_DG419']}",
        # C16 blocks DC, so U5A has no DC feedback while the SHORT is open.  On the board the DG419 closes between
        # pulses and sets the operating point; here a 1 GH inductor E1-ISENSE does that at DC and vanishes at AC.
        "LDC E1 ISENSE 1e9",
        f"XEL E1_OUT ISENSE ELECTRODE params: Rs={Rs} Cdl={Cdl} Rct=2Meg",
    ])
    return tian_loop_gain(body)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    cables = [0, 470e-12] if quick else [0, 100e-12, 470e-12, 1e-9, 4.7e-9]
    Rss = [10e3] if quick else [5e3, 10e3, 15e3]
    Cdls = [2.2e-9] if quick else [1.6e-9, 3.2e-9]
    res = []
    fig, axs = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    for cc, Rs, Cdl in itertools.product(cables, Rss, Cdls):
        f, T = loop(cc, Rs, Cdl)
        fc, pm = phase_margin(f, T)
        res.append(dict(cable_c=cc, Rs=Rs, Cdl=Cdl, f_cross=fc, pm=pm))
        print(f"cable {cc * 1e12:6.0f} pF  Rs {Rs / 1e3:4.0f}k  Cdl {Cdl * 1e9:3.1f}n : crossover {fc / 1e3:8.1f} kHz, "
              f"phase margin {pm:5.1f} deg", flush=True)
        if Rs == Rss[0] and Cdl == Cdls[0]:
            axs[0].semilogx(f, 20 * np.log10(np.abs(T)), label=f"cable {cc * 1e12:.0f} pF")
            axs[1].semilogx(f, np.degrees(np.unwrap(np.angle(T))))
    json.dump(res, open(os.path.join(OUT, "stability.json"), "w"), indent=1)
    worst = {}
    for r in res:
        worst[r["cable_c"]] = min(worst.get(r["cable_c"], 999), r["pm"])
    print("worst-case phase margin by cable C:", {f"{k * 1e12:.0f} pF": round(v, 1) for k, v in worst.items()})
    axs[0].axhline(0, color="0.5", lw=0.8); axs[0].set_ylabel("|T| (dB)"); axs[0].legend(fontsize=7, frameon=False)
    axs[1].set_ylabel("∠T (deg)"); axs[1].set_xlabel("frequency (Hz)")
    axs[0].set_title(f"U5A loop gain, Rs {Rss[0] / 1e3:.0f}k, Cdl {Cdls[0] * 1e9:.1f}n", fontsize=10)
    for a in axs:
        a.grid(alpha=0.3, which="both")
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "stability.png"), dpi=120)
