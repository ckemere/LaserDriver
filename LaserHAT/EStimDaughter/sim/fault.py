"""
Fault detector: U8 TLV1702 window on E1 -> FAULT_n (J8.5 -> HAT TIMA0_FAULT0, which kills EN/CATH in hardware).
E1 is compared directly with the taps of a 10k / 215k / 10k string between +V and -V, so the trip points track the
rails: |E1| > 0.915*V for equal packs.  Checks, with the full module deck (U5A/U5B TI model, ADG1436 switches, DG419, hold timer
standing in for the RELEASE line, behavioural comparators with the R26 / D2 level shift):
  1. analytic trip points vs rail (12 / 15 / 16.8 / 18 V) and for unequal packs;
  2. 250 uA cathodic-first pair, phase width swept across the compliance limit: when FAULT_n fires relative to the
     moment the electrode current starts to fall (U5A running out of headroom), and the resulting charge mismatch;
  3. open electrode: time from EN rising to FAULT_n low;
  4. no false trip: in-compliance trains at 1 kHz (DG419 injection, hold-timer edges and the ISO7761F input load
     included) - FAULT_n stays high and the window margin is reported.

  python fault.py [--quick]           -> results/fault.json, results/fault.png
"""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from spice import VALUES, RAIL, ROBUST_OPTS, code_for, module_deck, run_robust, window_thresholds

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
T0, GAP, PERIOD = 10e-6, 50e-6, 1e-3
# gear with a 50 ns step; a 20 ns step or the trap solver can crawl for minutes once U5A saturates
FAULT_OPTS = [ROBUST_OPTS[0], ROBUST_OPTS[1], ROBUST_OPTS[2], ""]
VEC = ["v(e1_out)", "v(xel.n1)", "v(e1)", "v(oa_out)", "v(fault_n)", "v(th_p)", "v(th_n)", "v(hold)"]


def _run(I, pairs, pw, gap, period, V, Rs, Cdl, Rct, tstop, step):
    deck = module_deck(code_for(I), pairs, pw, gap, period, V=V, Rs=Rs, Cdl=Cdl, Rct=Rct, fault="full") + \
        "\n{OPTS}\n" + f".tran {step} {tstop} 0 {step}\n"
    r = run_robust(deck, VEC, tstop, opts=FAULT_OPTS, attempt_timeout=300)
    r["i_el"] = (r["v(e1_out)"] - r["v(xel.n1)"]) / Rs        # + = anodic (into E1)
    r["margin_p"] = r["v(th_p)"] - r["v(e1)"]                 # > 0 while U8B is quiet
    r["margin_n"] = r["v(e1)"] - r["v(th_n)"]                 # > 0 while U8A is quiet
    return r


def pair(I, pw, V, Rs, Cdl, Rct=2e6, tail=150e-6):
    """one cathodic-first pair; saturation = electrode current 1 % below its plateau (as compliance.py)"""
    tstop = T0 + 2 * pw + GAP + tail
    r = _run(I, 1, pw, GAP, PERIOD, V, Rs, Cdl, Rct, tstop, 50e-9)
    t, i, f = r["time"], r["i_el"], r["v(fault_n)"]
    mc = (t >= T0) & (t < T0 + pw + GAP / 2)
    ma = (t >= T0 + pw + GAP / 2) & (t < T0 + 2 * pw + GAP + 20e-6)
    qc, qa = np.trapezoid(i[mc], t[mc]), np.trapezoid(i[ma], t[ma])
    m = (t > T0 + 5e-6) & (t < T0 + 15e-6)
    plateau = np.mean(np.abs(i[m]))
    after = (t > T0 + 15e-6) & (t < T0 + pw)
    low = np.where(np.abs(i[after]) < 0.99 * plateau)[0]
    t_sat = (t[after][low[0]] - T0) if len(low) else np.nan
    fired = f < 1.5
    t_fire = (t[np.argmax(fired)] - T0) if fired.any() else np.nan
    k = np.where(fired)[0]
    return dict(I=I, pw=pw, V=V, Rs=Rs, Cdl=Cdl, mismatch=(qc + qa) / abs(qc) * 100, fired=bool(fired.any()),
                t_fire=t_fire, t_sat=t_sat, low_time=(t[k[-1]] - t[k[0]]) if len(k) else 0.0,
                e1_min=float(r["v(e1)"].min()), e1_max=float(r["v(e1)"].max()), f_min=float(f.min()), _r=r)


def open_electrode(I, V, pw=100e-6):
    """electrode lead broken: Rs -> 1 G, no double layer.  U5A slews to the rail; FAULT_n must follow."""
    tstop = T0 + 2 * pw + GAP + 100e-6
    r = _run(I, 1, pw, GAP, PERIOD, V, 1e9, 1e-12, 1e9, tstop, 50e-9)
    t, f = r["time"], r["v(fault_n)"]
    fired = f < 1.5
    t_fire = (t[np.argmax(fired)] - T0) if fired.any() else np.nan
    k = np.where(fired)[0]
    return dict(I=I, V=V, fired=bool(fired.any()), t_fire=t_fire, low_time=(t[k[-1]] - t[k[0]]) if len(k) else 0.0,
                e1_min=float(r["v(e1)"].min()), _r=r)


def train(I, pw, n, V, Rs, Cdl, gap=GAP):
    """n pairs at 1 kHz inside compliance: FAULT_n must stay high; report the window margin and FAULT_n's low point"""
    tstop = n * PERIOD
    r = _run(I, n, pw, gap, PERIOD, V, Rs, Cdl, 2e6, tstop, 50e-9)
    f = r["v(fault_n)"]
    return dict(I=I, pw=pw, n=n, V=V, Rs=Rs, Cdl=Cdl, f_min=float(f.min()), f_high=float(np.median(f)),
                margin_p=float(r["margin_p"].min()), margin_n=float(r["margin_n"].min()),
                e1_min=float(r["v(e1)"].min()), e1_max=float(r["v(e1)"].max()), false_trip=bool((f < 2.5).any()), _r=r)


def strip(d):
    return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in d.items() if not k.startswith("_")}


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    res = dict(thresholds=[], sweep=[], open=[], train=[])
    # 1. thresholds
    for V in (12.0, 15.0, 16.8, 18.0):
        p, n, a, b, thp, thn = window_thresholds(V)
        res["thresholds"].append(dict(V=V, e1_high=p, e1_low=n, th_p=thp, th_n=thn, a=a, b=b))
        print(f"rails +/-{V:4.1f} V: FAULT_n while E1 > {p:+6.2f} or E1 < {n:+6.2f} V  (margin {V - p:.2f} V to each rail)", flush=True)
    for Vp, Vn in ((16.8, -13.0), (16.8, -9.0)):
        p, n, *_ = window_thresholds(Vp, Vneg=Vn)
        print(f"rails +{Vp:4.1f} / {Vn:5.1f} V (unequal packs): FAULT_n while E1 > {p:+6.2f} or E1 < {n:+6.2f} V "
              f"(margins {Vp - p:.2f} / {n - Vn:.2f} V)", flush=True)
    # 2. phase-width sweep across the compliance limit, 250 uA cathodic-first
    I = 250e-6
    cases = [("15 V, Rs 15k / Cdl 1.6n (worst electrode)", RAIL, 15e3, 1.6e-9, np.arange(50, 90.1, 5)),
             ("12 V, Rs 10k / Cdl 2.2n", 12.0, 10e3, 2.2e-9, np.arange(60, 100.1, 5)),
             ("16.8 V, Rs 10k / Cdl 2.2n", 16.8, 10e3, 2.2e-9, np.arange(100, 140.1, 5)),
             ("18 V, Rs 15k / Cdl 1.6n", 18.0, 15e3, 1.6e-9, np.arange(70, 110.1, 5))]
    if quick:
        cases = [cases[0][:4] + (np.array([55, 65, 75]),)]
    wave = None
    for name, V, Rs, Cdl, pws in cases:
        for pw in pws * 1e-6:
            r = pair(I, pw, V, Rs, Cdl)
            r["case"] = name
            res["sweep"].append(strip(r))
            sat = f"{r['t_sat'] * 1e6:6.1f} us" if r["t_sat"] == r["t_sat"] else "   -    "
            fire = (f"FAULT at {r['t_fire'] * 1e6:6.1f} us, low {r['low_time'] * 1e6:6.1f} us"
                    if r["fired"] else "FAULT  -")
            print(f"{name:42s} pw {pw * 1e6:5.0f} us: E1 {r['e1_min']:+6.2f}..{r['e1_max']:+6.2f} V, "
                  f"current falls at {sat}, mismatch {r['mismatch']:+7.3f} %, {fire}", flush=True)
            if wave is None and r["fired"] and r["t_sat"] == r["t_sat"]:
                wave = r
    # 3. open electrode
    open_wave = None
    for V in ((RAIL,) if quick else (RAIL, 12.0, 18.0)):
        r = open_electrode(I, V)
        open_wave = open_wave or r
        res["open"].append(strip(r))
        print(f"open electrode at +/-{V:4.1f} V: E1 min {r['e1_min']:+6.2f} V, FAULT_n "
              f"{'low ' + format(r['t_fire'] * 1e6, '.1f') + ' us after EN' if r['fired'] else 'NOT fired'}, "
              f"low for {r['low_time'] * 1e6:.0f} us", flush=True)
    # 4. no false trip
    trains = [(250e-6, 60e-6, RAIL, 10e3, 2.2e-9), (100e-6, 100e-6, RAIL, 15e3, 1.6e-9), (20e-6, 20e-6, RAIL, 10e3, 2.2e-9)]
    if quick:
        trains = trains[:1]
    for I_, pw, V, Rs, Cdl in trains:
        r = train(I_, pw, 2 if quick else 5, V, Rs, Cdl)
        res["train"].append(strip(r))
        print(f"train {I_ * 1e6:3.0f} uA x {pw * 1e6:3.0f} us at +/-{V:.0f} V, Rs {Rs / 1e3:.0f}k / Cdl {Cdl * 1e9:.1f}n: "
              f"E1 {r['e1_min']:+6.2f}..{r['e1_max']:+6.2f} V, FAULT_n min {r['f_min']:.2f} V (high {r['f_high']:.2f} V), "
              f"window margin {r['margin_n'] * 1e3:.0f} mV below / {r['margin_p'] * 1e3:.0f} mV above"
              f"{'  FALSE TRIP' if r['false_trip'] else ''}", flush=True)
    json.dump(res, open(os.path.join(OUT, "fault.json"), "w"), indent=1)

    fig, axs = plt.subplots(1, 3, figsize=(15, 4.4))
    for name, V, Rs, Cdl, _ in cases:
        rr = [r for r in res["sweep"] if r["case"] == name]
        x = np.array([r["pw"] * 1e6 for r in rr]); mm = np.abs([r["mismatch"] for r in rr]) + 1e-4
        fired = np.array([r["fired"] for r in rr])
        (ln,) = axs[0].plot(x, mm, "-", lw=1.5, label=name)
        axs[0].plot(x[fired], mm[fired], "o", color=ln.get_color(), ms=5)
        axs[0].plot(x[~fired], mm[~fired], "o", color=ln.get_color(), ms=5, mfc="white")
    axs[0].set_yscale("log"); axs[0].set_xlabel("phase width (µs), 250 µA cathodic-first")
    axs[0].set_ylabel("|charge mismatch| (%)"); axs[0].set_title("filled = FAULT_n fired", fontsize=10)
    axs[0].legend(fontsize=7, frameon=False)
    if wave is not None:
        r = wave["_r"]
        t = r["time"] * 1e6
        axs[1].plot(t, r["v(e1)"], lw=1, label="E1")
        axs[1].plot(t, r["v(fault_n)"], lw=1, label="FAULT_n")
        axs[1].plot(t, r["i_el"] * 1e6 / 50, lw=1, label="I_el / 50 µA")
        axs[1].set_title(f"{wave['case']}, pw {wave['pw'] * 1e6:.0f} µs: FAULT {wave['t_fire'] * 1e6:.1f} µs, "
                         f"current falls {wave['t_sat'] * 1e6:.1f} µs", fontsize=9)
        axs[1].set_xlabel("t (µs)"); axs[1].legend(fontsize=8, frameon=False)
    if open_wave is not None:
        r = open_wave["_r"]
        t = r["time"] * 1e6
        axs[2].plot(t, r["v(e1)"], lw=1, label="E1")
        axs[2].plot(t, r["v(fault_n)"], lw=1, label="FAULT_n")
        axs[2].plot(t, r["v(hold)"], lw=1, label="HOLD")
        axs[2].set_title(f"open electrode at ±{open_wave['V']:.0f} V: FAULT_n low {open_wave['t_fire'] * 1e6:.1f} µs after EN",
                         fontsize=9)
        axs[2].set_xlim(0, 60); axs[2].legend(fontsize=8, frameon=False)
    axs[2].set_xlabel("t (µs)")
    for a in axs:
        a.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "fault.png"), dpi=120)
