"""
Pulse train with the real SHORT path: EN/CATH -> BAT54C -> HOLD (R15/C17) -> DG419 across E1-ISENSE.
Five cathodic-first pairs at 1 kHz.  Per cycle: net charge through the electrode, the double-layer voltage left at
the end of the cycle, and the faradaic charge (through Rct - what actually corrodes tungsten).  Compared with the
SHORT switch removed, to show what the passive short does.

  python train.py [--quick]           -> results/train.json, results/train.png
Expected with the SHORT: the double layer is reset every cycle, and what remains at the end of each cycle is set by
C16 (the 1 uF DC block in series with the electrode).  The net faradaic charge each pulse pair drives through Rct has
to come from C16, so C16 (and with it Vcdl after each short) creeps by about q_far / C16 per cycle (~0.8 mV per cycle
at 250 uA x 100 us in this electrode model) until the average DC current is zero (time constant ~ C16 * Rct ~ 2 s).
That is the DC block doing its job: no net DC charge in the long run.  Without the SHORT, Vcdl ratchets far larger.
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spice import code_for, module_deck, run_robust

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
T0, PERIOD = 10e-6, 1e-3


def train(I, pw, gap, n, short=True, Rs=10e3, Cdl=2.2e-9, Rct=2e6):
    tstop = n * PERIOD
    deck = module_deck(code_for(I), n, pw, gap, PERIOD, Rs=Rs, Cdl=Cdl, Rct=Rct, short=short) + \
        "\n{OPTS}\n" + f".tran 20n {tstop} 0 50n\n"
    vec = ["v(e1_out)", "v(xel.n1)", "v(isense)"] + (["v(hold)"] if short else [])
    r = run_robust(deck, vec, tstop)
    t = r["time"]
    i_el = (r["v(e1_out)"] - r["v(xel.n1)"]) / Rs
    vcdl = r["v(xel.n1)"] - r["v(isense)"]
    i_far = vcdl / Rct
    q_cyc, q_far, v_end = [], [], []
    for k in range(n):
        m = (t >= k * PERIOD) & (t < (k + 1) * PERIOD)
        q_cyc.append(np.trapezoid(i_el[m], t[m]))
        q_far.append(np.trapezoid(i_far[m], t[m]))
        v_end.append(vcdl[np.searchsorted(t, (k + 1) * PERIOD) - 1])
    return dict(t=t, vcdl=vcdl, hold=r.get("v(hold)"), q_cyc=np.array(q_cyc), q_far=np.array(q_far),
                v_end=np.array(v_end), q_phase=I * pw)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    n = 2 if quick else 5
    cases = [(250e-6, 100e-6, 50e-6)] if quick else [(250e-6, 100e-6, 50e-6), (20e-6, 20e-6, 20e-6)]
    res = []
    fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for I, pw, gap in cases:
        for short in (True, False):
            r = train(I, pw, gap, n, short)
            lab = f"{I * 1e6:.0f} µA × {pw * 1e6:.0f} µs, {'SHORT' if short else 'no SHORT'}"
            print(f"{lab:32s}: net charge/cycle " + " ".join(f"{q * 1e12:+8.2f}" for q in r["q_cyc"]) + " pC"
                  f" ({np.mean(r['q_cyc'][1:] if n > 1 else r['q_cyc']) / r['q_phase'] * 100:+.3f} % of phase);"
                  f"  Vcdl end " + " ".join(f"{v * 1e3:+7.2f}" for v in r["v_end"]) + " mV;"
                  f"  faradaic/cycle {np.mean(r['q_far']) * 1e12:+.2f} pC", flush=True)
            res.append(dict(case=lab, I=I, pw=pw, gap=gap, short=short, q_cyc=r["q_cyc"].tolist(),
                            v_end=r["v_end"].tolist(), q_far=r["q_far"].tolist()))
            if I == cases[0][0]:
                axs[0].plot(r["t"] * 1e3, r["vcdl"] * 1e3, lw=1, label=lab)
                if short:
                    axs[1].plot(r["t"] * 1e3, r["hold"], lw=1, label="HOLD (DG419 IN)")
                    axs[1].axhline(1.6, color="0.5", ls="--", lw=0.8)
                    axs[1].text(0.02, 1.8, "switch threshold 1.6 V: below = electrode shorted", fontsize=8, color="0.4")
    json.dump(res, open(os.path.join(OUT, "train.json"), "w"), indent=1)
    axs[0].set_ylabel("V_Cdl (mV)"); axs[0].legend(fontsize=8, frameon=False)
    axs[0].set_title("Double-layer voltage over a 1 kHz train", fontsize=10)
    axs[1].set_ylabel("V (HOLD)"); axs[1].set_xlabel("t (ms)"); axs[1].legend(fontsize=8, frameon=False)
    for a in axs:
        a.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "train.png"), dpi=120)
