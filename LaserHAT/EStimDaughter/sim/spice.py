"""
ngspice helpers for the e-stim module (rev M1).  Netlists here follow the schematic's reference designators.

Modelled parts
  U5A/U5B  OPA2192        TI PSpice macro-model (models/OPAx192.lib, subckt OPAx192: IN+ IN- VCC VEE OUT)
  U4       MCP4921        ideal voltage source VSET_P = code/4096 * VREF (its output buffer is not modelled)
  U3 etc.  TL431 + R8/R9  folded into VREF = 1.000 V
  U6       74HC4053       voltage-controlled switches, R_on = RON_4053, driven by EN / CATH (5 V logic)
  U7       DG419          behavioural: throw 1 (D=E1 to S1=ISENSE) closed while IN (= HOLD) is below 1.6 V;
                          20 ohm on, 8 pF off-capacitance per side, charge injection via 2 pF from a +/-15 V
                          internal gate node into each terminal (~60 pC per side per edge, datasheet typ.)
  D2       BAT54C         diode model (Schottky), EN and CATH OR'ed onto HOLD; R15 100k + C17 2.2n
  PS1      +/-V rails     ideal sources (A0515S / RB-0515D nominal +/-15 V, or battery packs up to +/-18 V)
  electrode               Randles cell: Rs + (Cdl || Rct), between J1.1 (E1_OUT) and J1.2 (ISENSE)

run(deck, vectors) runs ngspice in batch mode (PSpice-compatible, needed for the TI model) and returns
{name: numpy array} with 'time' (or 'frequency') plus every requested vector.
"""
import os
import shutil
import subprocess
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")
NGSPICE = os.environ.get("NGSPICE") or shutil.which("ngspice") or "/opt/homebrew/bin/ngspice"

# ---------------------------------------------------------------------------------------------- schematic values
VALUES = dict(
    VREF=1.000,          # MCP4921 VREF (TL431 2.495 V * R9 / (R8 + R9) = 10.0k / 25.0k), BUF=1, gain 1x
    R10=10.0e3,          # U5B inverter input  (0.1 %)
    R11=10.0e3,          # U5B inverter feedback (0.1 %)
    RON_4053=100.0,      # 74HC4053 on-resistance at VCC = +5 V, VEE = -4.7 V (datasheet typ. 70-100 ohm)
    R12=1.0e3,           # V_IN -> U5A +IN (OA_IN)
    C15=100e-12,         # OA_IN to GND_ISO
    R13=47.0,            # U5A output isolation -> E1
    R14=2.00e3,          # R_SENSE, ISENSE -> GND_ISO (0.1 %)
    C16=1e-6,            # DC block E1 -> J1.1 (E1_OUT)
    R15=100e3, C17=2.2e-9,   # SHORT hold timer
    RON_DG419=20.0, COFF_DG419=8e-12, CINJ_DG419=2e-12, VTH_DG419=1.6,
    V_LOGIC=5.0,         # ISO7761F side 2 / +5V_ISO
)
RAIL = 15.0              # PS1 nominal; use 16.8 for two 4S Li-ion packs

ELECTRODE = """
.subckt ELECTRODE E1 E2 params: Rs=10k Cdl=2.2n Rct=2Meg
Rs   E1 N1  {Rs}
Cdl  N1 E2  {Cdl}
Rct  N1 E2  {Rct}
.ends
"""


def include_models():
    return f".include {os.path.join(MODELS, 'OPAx192.lib')}"


def i_full_scale(v=VALUES):
    return v["VREF"] / v["R14"]


def code_for(current, v=VALUES):
    """DAC code (0..4095) for a phase current in A"""
    return int(round(current / i_full_scale(v) * 4096))


# ---------------------------------------------------------------------------------------------- netlist blocks
def rails(V=RAIL):
    return f"VP VP 0 {V}\nVN VN 0 {-V}\nV5 V5ISO 0 {VALUES['V_LOGIC']}\n"


def setpoint(code, v=VALUES):
    """U4 DAC (ideal) -> VSET_P; U5B unity inverter -> VSET_N"""
    vset = code / 4096 * v["VREF"]
    return f"""* U4 MCP4921 (ideal DAC output)
VDAC VSET_P 0 {vset:.9g}
* U5B: inverter, IN+ = GND_ISO
R10 VSET_P U5B_N {v['R10']}
R11 U5B_N VSET_N {v['R11']}
XU5B 0 U5B_N VP VN VSET_N OPAx192
"""


def switch_4053(v=VALUES):
    """U6: switch 1 (S1 = CATH) picks VSET_P (0) / VSET_N (1) onto SW_P; switch 2 (S2 = EN) picks GND (0) / SW_P (1)
    onto V_IN.  Break-before-make comes from the 0.1 V hysteresis of the ideal switches."""
    r = v["RON_4053"]
    return f"""* U6 74HC4053
S1A SW_P VSET_P CATH_N 0 SW4053
S1B SW_P VSET_N CATH 0 SW4053
S2A V_IN 0 EN_N 0 SW4053
S2B V_IN SW_P EN 0 SW4053
BCATHN CATH_N 0 V={v['V_LOGIC']}-V(CATH)
BENN EN_N 0 V={v['V_LOGIC']}-V(EN)
.model SW4053 SW(Ron={r} Roff=1G Vt={v['V_LOGIC'] / 2} Vh=0.1)
"""


def output_stage(v=VALUES, cable_c=0.0, loop_break=False):
    """U5A floating-load V->I.  Nodes: V_IN (4053), OA_IN, OA_OUT, E1, E1_OUT (J1.1), ISENSE (J1.2).
    The electrode goes between E1_OUT and ISENSE (instantiated by the caller).
    loop_break=True inserts the Tian probe (VTIAN/ITIAN) between the op-amp output (TX) and R13 (TY)."""
    out = "TX" if loop_break else "OA_OUT"
    lines = [
        "* U5A output stage",
        f"R12 V_IN OA_IN {v['R12']}",
        f"C15 OA_IN 0 {v['C15']}",
        f"XU5A OA_IN ISENSE VP VN {out} OPAx192",
    ]
    if loop_break:
        lines += ["VTIAN TX TY DC 0 AC {vi}", "ITIAN 0 TY DC 0 AC {ii}", f"R13 TY E1 {v['R13']}"]
    else:
        lines += [f"R13 OA_OUT E1 {v['R13']}"]
    lines += [
        f"C16 E1 E1_OUT {v['C16']}",
        f"R14 ISENSE 0 {v['R14']}",
    ]
    if cable_c:
        lines.append(f"CCABLE E1_OUT 0 {cable_c}")
    return "\n".join(lines) + "\n"


def short_switch(v=VALUES, fitted=True):
    """D2 BAT54C (EN, CATH -> HOLD), R15 || C17 hold timer, U7 DG419 throw 1 between E1 and ISENSE.
    Note: the DG419 shorts E1 (op-amp side of C16) to ISENSE, i.e. across C16 + electrode."""
    if not fitted:
        return "* U7 not fitted\n"
    return f"""* D2 BAT54C + hold timer
DA EN HOLD DBAT54
DB CATH HOLD DBAT54
R15 HOLD 0 {v['R15']}
C17 HOLD 0 {v['C17']}
.model DBAT54 D(IS=2e-7 N=1.0 RS=1.5 CJO=10p TT=5n BV=30)
* U7 DG419: throw 1 (D-S1) closed while IN < {v['VTH_DG419']} V (no hysteresis in the part; 5 mV here for the solver)
* internal gate node: +/-15 V, slewing with a 20 ns time constant (datasheet tON/tOFF ~ 40-110 ns); it drives the
* switch (closed while the gate is high) and couples charge into both terminals (2 pF x 30 V ~ 60 pC per edge)
BDGC DGG0 0 V=15*tanh(({v['VTH_DG419']}-V(HOLD))/0.05)
RDGG DGG0 DGG 1k
CDGG DGG 0 20p
SDG E1 ISENSE DGG 0 SWDG
.model SWDG SW(Ron={v['RON_DG419']} Roff=10G Vt=0 Vh=1)
CDG_D E1 0 {v['COFF_DG419']}
CDG_S ISENSE 0 {v['COFF_DG419']}
CINJ_D DGG E1 {v['CINJ_DG419']}
CINJ_S DGG ISENSE {v['CINJ_DG419']}
"""


def control(pairs, pw, gap, period, t0=10e-6, lead=5e-6, tr=5e-9, v=VALUES):
    """EN / CATH logic waveforms for `pairs` cathodic-first biphasic pairs (firmware contract):
    CATH rises `lead` before EN; EN high for pw; gap (CATH falls mid-gap); EN high for pw."""
    hi = v["V_LOGIC"]
    en, cath = [(0, 0)], [(0, 0)]
    for k in range(pairs):
        b = k * period + t0
        cath += [(b - lead, 0), (b - lead + tr, hi), (b + pw + gap / 2, hi), (b + pw + gap / 2 + tr, 0)]
        en += [(b, 0), (b + tr, hi), (b + pw, hi), (b + pw + tr, 0),
               (b + pw + gap, 0), (b + pw + gap + tr, hi), (b + 2 * pw + gap, hi), (b + 2 * pw + gap + tr, 0)]
    f = lambda pts: "PWL(" + " ".join(f"{t:.9g} {x:g}" for t, x in pts) + ")"
    return f"VEN EN 0 {f(en)}\nVCATH CATH 0 {f(cath)}\n"


def module_deck(code, pairs, pw, gap, period, V=RAIL, Rs=10e3, Cdl=2.2e-9, Rct=2e6, cable_c=0.0,
                short=True, t0=10e-6, v=VALUES):
    """complete transient deck body (no analysis line) for the final module driving one electrode"""
    return "\n".join([
        f"* e-stim module M1: code {code}, {pairs} pair(s), pw {pw * 1e6:g} us, gap {gap * 1e6:g} us, rails +/-{V} V",
        include_models(), ELECTRODE, rails(V), setpoint(code, v), switch_4053(v), output_stage(v, cable_c),
        f"XEL E1_OUT ISENSE ELECTRODE params: Rs={Rs} Cdl={Cdl} Rct={Rct}",
        short_switch(v, short), control(pairs, pw, gap, period, t0, v=v),
    ])


# ---------------------------------------------------------------------------------------------- running ngspice
def run(netlist, vectors, analysis_is_ac=False, timeout=600, keep=None):
    """netlist: full deck WITHOUT .control/.end, including the analysis line.  vectors: e.g. ['v(e1)', 'i(vp)']."""
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, ".spiceinit"), "w") as f:
            f.write("set ngbehavior=psa\nset num_threads=1\n")
        out = os.path.join(td, "out.txt")
        ctrl = ("\n.control\nset wr_singlescale\nset wr_vecnames\noption numdgt=9\nrun\n"
                f"wrdata {out} " + " ".join(vectors) + "\n.endc\n.end\n")
        deck = os.path.join(td, "deck.cir")
        with open(deck, "w") as f:
            f.write(netlist + ctrl)
        if keep:
            with open(keep, "w") as f:
                f.write(netlist + ctrl)
        p = subprocess.run([NGSPICE, "-b", deck], cwd=td, capture_output=True, text=True, timeout=timeout)
        if not os.path.exists(out):
            raise RuntimeError("ngspice failed:\n" + p.stdout[-3000:] + p.stderr[-3000:])
        with open(out) as f:
            header = f.readline().split()
        data = np.loadtxt(out, skiprows=1, ndmin=2)
    res = {}
    if analysis_is_ac:
        res["frequency"] = data[:, 0]
        for k, name in enumerate(vectors):
            res[name] = data[:, 1 + 2 * k] + 1j * data[:, 2 + 2 * k]
    else:
        res["time"] = data[:, 0]
        for k, name in enumerate(vectors):
            res[name] = data[:, 1 + k]
    return res


ROBUST_OPTS = [".options method=gear",
               ".options method=gear reltol=3e-3 itl4=200",
               ".options method=gear gmin=1e-9 reltol=2e-3 itl4=500 abstol=1e-9",
               ".options method=trap trtol=1"]


def run_robust(netlist, vectors, tstop, attempt_timeout=900, **kw):
    """switching transients can stall ngspice ('timestep too small'); try solver options in turn.
    The deck must contain the placeholder line '{OPTS}'."""
    last = "no attempt"
    for o in ROBUST_OPTS:
        try:
            r = run(netlist.replace("{OPTS}", o), vectors, timeout=attempt_timeout, **kw)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            last = f"{o!r}: {type(e).__name__}"
            continue
        if r["time"][-1] >= 0.999 * tstop:
            r["_opts"] = o
            return r
        last = f"{o!r}: stopped at {r['time'][-1]:.3g} s"
    raise RuntimeError(f"no solver option set reached tstop ({last})")


def tian_loop_gain(netlist_body, fstart=10, fstop=100e6, ppd=40):
    """Middlebrook/Tian double-injection loop gain; the deck must contain VTIAN TX TY ... AC {vi} and
    ITIAN 0 TY ... AC {ii} (see output_stage(loop_break=True)).  Returns f, T."""
    res = {}
    for vi, ii in ((1, 0), (0, 1)):
        body = netlist_body.replace("{vi}", str(vi)).replace("{ii}", str(ii))
        res[(vi, ii)] = run(body + f"\n.ac dec {ppd} {fstart} {fstop}\n", ["v(tx)", "v(ty)", "i(vtian)"],
                            analysis_is_ac=True)
    rv, ri = res[(1, 0)], res[(0, 1)]
    Tv = -rv["v(tx)"] / rv["v(ty)"]
    ix = -ri["i(vtian)"]
    iy = 1.0 - ix
    Ti = ix / iy
    T = (Tv * Ti - 1.0) / (Tv + Ti + 2.0)
    return rv["frequency"], T


def phase_margin(f, T):
    """(crossover frequency, phase margin in degrees) at the last |T| = 1 crossing"""
    mag = np.abs(T)
    k = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if not len(k):
        return np.nan, np.nan
    k = k[-1]
    x = np.log(mag[k]) / (np.log(mag[k]) - np.log(mag[k + 1]))
    fc = np.exp(np.log(f[k]) + x * (np.log(f[k + 1]) - np.log(f[k])))
    ph = np.unwrap(np.angle(T))
    d = np.degrees(ph[k] + x * (ph[k + 1] - ph[k]))
    d = (d + 180) % 360 - 180
    return fc, 180 - abs(d)
