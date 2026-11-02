#!/usr/bin/env python3
"""
Generates SimpleBatteryPack.kicad_sch (two hobby 4S packs permanently in series = +V / 0 V / -V, ON / OFF toggle, plug
interlock, two gauges: the BatteryPack without its charger, relays, charge controller and balancers)
from sch_parts.py and sch_symbols.py, same engine as the e-stim module.  Then: python tools/netcheck.py and ERC.
    python gen_schematic.py
"""
from sch_engine import Sheet
from sch_parts import BY_REF  # noqa: F401

u = 2.54
sh = Sheet()


def put(ref, x, y, rot=0, mirror=False, **kw):
    sh.put(ref, x * u, y * u, rot, mirror, **kw)


def pt(x, y):
    return (x * u, y * u)


def W(*specs, **kw):
    return sh.W(*[pt(*s) if isinstance(s, tuple) and not isinstance(s[0], str) else s for s in specs], **kw)


PWR, LBL, FLAG, NET, LAB = sh.PWR, sh.LBL, sh.FLAG, sh.NET, sh.LAB


def pwr_at(net, x, y, up):
    return sh.PWR(None, net=net, at=pt(x, y), up=up)


def lab(net, x, y, d=(1, 0)):
    sh.LAB(net, pt(x, y), d)


def text(s, x, y, size=1.27, bold=False):
    sh.text(s, x * u, y * u, size, bold)


def box(x1, y1, x2, y2, title):
    sh.box(x1 * u, y1 * u, x2 * u, y2 * u, title)


# =========================================================================== 1. packs (XT60 discharge plugs)
def pack(x0, xt, title, flags):
    text(title, x0 + 1, 11.5, 1.6, True)
    put(xt, x0 + 6, 24, mirror=True, ref_at=(0, -3.81), val_at=(0, -6.35))      # XT60: pin 1 = -, pin 2 = +
    for pin in (f"{xt}.1", f"{xt}.2"):
        e = PWR(pin, length=5.08)
        if BY_REF[xt]["nets"][pin.split(".")[1]] in flags:
            FLAG(e, up=(1, 0))                            # the packs drive these


box(6, 8, 100, 48.5, "1. TWO 4S PACKS IN SERIES: XT60 DISCHARGE PLUGS (J7 / J8)")
pack(6, "J7", "PACK A (-V side): GND .. 0V", {"GND"})
pack(54, "J8", "PACK B (+V side): 0V .. +BATB", {"0V", "+BATB"})
text("Any 4S LiPo / Li-ion hobby pack with an XT60 discharge plug.  Pack A's positive and pack B's negative are one node, 0V,", 7, 41)
text("the output reference: the packs are never reconfigured.  Charge them off the board on a hobby balance charger.", 7, 43)


# =========================================================================== 2. toggle, chains, interlock
box(6, 50, 100, 112, "2. ON / OFF TOGGLE, OUTPUT CHAINS (+V: Q1, -V: Q11), PLUG INTERLOCK ON BOTH (Q22, Q26)")
put("SW1", 16, 60, val_at=(0, 10.16))
NET("SW1.2", length=2.54)                                 # EN_A common, pole 1
W("SW1.1", (22, 58), (22, 54)); pwr_at("0V", 22, 54, (0, -1))                                   # ON: EN_A = 0V
NET("SW1.5", length=2.54)                                 # EN_B common, pole 2
W("SW1.4", (30, 61), (30, 66)); pwr_at("+BATB", 30, 66, (0, 1))                                 # ON: EN_B = +BATB
put("R82", 12, 72)                                        # EN_B pull-down
NET("R82.1"); PWR("R82.2")
# chain B (0V domain): +BATB -> F1 -> +SW -> Q1 -> +OUT, enabled by Q22 (gate ENB_G, source = the plug's pin 4)
put("F1", 46, 58, rot=90)
PWR("F1.1", length=2.54)
e = PWR("F1.2", length=2.54); FLAG(e, up=(1, 0))           # +SW
put("Q1", 42, 70, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q1.2", length=2.54)                                  # source <- +SW
e = PWR("Q1.3", length=2.54); FLAG(e, up=(0, 1))          # drain -> +OUT
put("R1", 52, 64)
put("R2", 52, 76)
PWR("R1.1")
W("Q1.1", (52, 70))
W("R1.2", "R2.1")
lab("Q1_G", 48, 70)
NET("R2.2")                                               # Q22_D
put("Q22", 60, 84, ref_at=(5.08, 2.54), val_at=(5.08, 0))
NET("Q22.3"); NET("Q22.2"); NET("Q22.1")                  # drain Q22_D, source CAB (J3.4), gate ENB_G
put("R81", 68, 78)
NET("R81.1"); NET("R81.2")                                # EN_B -> ENB_G
put("U15", 52, 94, unit=2)                                # pack B cutoff comparator: pulls ENB_G low below 12.0 V
NET("U15.5"); NET("U15.6"); NET("U15.7")
# chain A (GND domain): GND -> F2 -> GNDF -> Q11 -> -V
put("F2", 78, 58, rot=90)
PWR("F2.1", length=2.54)
NET("F2.2")                                               # GNDF
put("Q11", 76, 70, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
NET("Q11.3"); NET("Q11.2")                                # -V (drain, top), GNDF (source, bottom)
put("R39", 68, 64)
put("R40", 68, 70)
NET("R39.1")                                              # EN_AI = CAB through Q26 only when ON
put("Q26", 90, 70, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
NET("Q26.2", length=2.54); NET("Q26.3", length=2.54); NET("Q26.1")   # source CAB (top), drain EN_AI (bottom), gate Q20_G
W("Q11.1", (68, 67))                                      # gate to the resistor stack's midpoint
W("R39.2", "R40.1")
lab("Q11_G", 68, 67, (0, -1))
PWR("R40.2")
put("U2", 80, 94, unit=2)                                 # pack A cutoff comparator (+ = VS, - = THCUT: output low = off)
NET("U2.5"); NET("U2.6"); NET("U2.7")
text("SW1 ON: pole 1 puts EN_A at 0V (= pack A positive), pole 2 puts EN_B at +BATB; OFF opens both (R40 / R82 hold them low).  Chain B: Q22 (2N7002) conducts when ENB_G is high", 7, 103)
text("and its source, J3.4 (CAB), is at 0V, i.e. the strap at the module end ties pin 4 to pin 2: then R1 / R2 give Q1 Vgs = -Vsw/2 and +V is live.  ENB_G = EN_B through R81 1M, pulled to 0V by", 7, 105)
text("U15B below 12.0 V (back above 12.8 V: R53 from +OUT).  Chain A: Q11 (N, in pack A's negative) gets Vgs = pack A / 2 from R39 / R40 off EN_AI = CAB through Q26,", 7, 107)
text("which conducts while the toggle is ON (its gate is Q20_G, pack A / 2 below 0V); U2B pulls Q11's gate low below 12.0 V (R11 470k: back on at 12.9 V).  So both rails need", 7, 109)
text("the toggle ON and 0V present at the module.  Gauge rails (box 2B) follow EN_A / EN_B, not the interlock: both gauges show whenever the toggle is ON.", 7, 111)


# =========================================================================== 2B. gauge rails
box(102, 94, 156, 112, "2B. GAUGE RAILS: +G = 0V THROUGH Q20, +GB = +BATB THROUGH Q23")
put("Q20", 110, 102, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q20.2", length=2.54)                                 # source <- 0V (top)
e = PWR("Q20.3", length=2.54); FLAG(e, up=(0, 1))         # drain -> +G
put("R77", 116, 98); put("R78", 116, 106)
PWR("R77.1"); W("Q20.1", (116, 102)); W("R77.2", "R78.1"); lab("Q20_G", 113, 102); NET("R78.2")
put("Q21", 124, 106, ref_at=(5.08, 2.54), val_at=(5.08, 0))
NET("Q21.3"); PWR("Q21.2"); NET("Q21.1")                  # drain Q21_D, source GND, gate Q21_G
put("R79", 131, 98); put("R80", 131, 106)
NET("R79.1"); NET("R79.2"); NET("R80.1"); PWR("R80.2")    # EN_A -> Q21_G -> GND
put("Q23", 138, 102, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q23.2", length=2.54)                                 # source <- +BATB
e = PWR("Q23.3", length=2.54); FLAG(e, up=(0, 1))         # drain -> +GB
put("R83", 144, 98); put("R84", 144, 106)
PWR("R83.1"); W("Q23.1", (144, 102)); W("R83.2", "R84.1"); lab("Q23_G", 141, 102); NET("R84.2")
put("Q24", 151, 106, ref_at=(5.08, 2.54), val_at=(5.08, 0))
NET("Q24.3"); PWR("Q24.2"); NET("Q24.1")                  # drain Q24_D, source 0V, gate EN_B


# =========================================================================== 3. reference, ladder, sample (one per pack)
def ladder(x0, y0, uref, rref, rl, rs1, rs2, rhys, sfx, hys_power):
    put(rref, x0 + 10, y0 + 4)
    PWR(f"{rref}.1")
    put(uref, x0 + 10, y0 + 12, ref_at=(3.81, -1.27), val_at=(3.81, 1.27))
    W(f"{rref}.2", f"{uref}.2")
    lab(f"VREF{sfx}", x0 + 10, y0 + 8)
    W(f"{uref}.1", (x0 + 6, y0 + 12), (x0 + 6, y0 + 8), (x0 + 10, y0 + 8))
    PWR(f"{uref}.3")
    for i, r in enumerate(rl):
        put(r, x0 + 24, y0 + 4 + 6 * i)
    NET(f"{rl[0]}.1")
    for i, net in enumerate(("TH80", "TH50", "TH20", "THCUT")):
        W(f"{rl[i]}.2", f"{rl[i + 1]}.1")
        lab(f"{net}{sfx}", x0 + 24, y0 + 7 + 6 * i)
    PWR(f"{rl[4]}.2")
    put(rs1, x0 + 38, y0 + 8)
    put(rs2, x0 + 38, y0 + 16)
    put(rhys, x0 + 48, y0 + 8)
    PWR(f"{rs1}.1")
    W(f"{rs1}.2", f"{rs2}.1")
    lab(f"VS{sfx}", x0 + 38, y0 + 12)
    PWR(f"{rs2}.2")
    (PWR if hys_power else NET)(f"{rhys}.1")
    W(f"{rhys}.2", ("y", (y0 + 12) * u), (x0 + 38, y0 + 12))


box(102, 50, 156, 92, "3A. PACK A: 2.495 V REFERENCE, LADDER, SAMPLE (on +G)")
ladder(102, 50, "U3", "R3", ("R4", "R5", "R6", "R7", "R8"), "R9", "R10", "R11", "", False)
box(158, 50, 212, 92, "3B. PACK B: THE SAME ON +GB, REFERENCED TO 0V")
ladder(158, 50, "U16", "R45", ("R46", "R47", "R48", "R49", "R50"), "R51", "R52", "R53", "B", True)
text("Ladder (108 uA): TH80 2.162 V, TH50 2.054 V, TH20 1.946 V, THCUT 1.613 V.  VS = rail x 0.1357 with the output live, x 0.1271 cut off; the rail is the pack itself (P-FET).", 103, 87)
text("Thresholds 15.9 / 15.1 / 14.3 V (pack) for the 80 / 50 / 20 % LEDs, cutoff 11.9 V, re-enable 12.7 V (pack B, R53 from +OUT) / 12.8 V (pack A, R11 from Q11's gate).", 103, 89)


# =========================================================================== 4. gauge comparators + LEDs (one per pack)
def leds(x0, y0, comps, r_on, d_on, units3, on_gnd):
    for k, (ref, un, led, rl) in enumerate(comps):
        y = y0 + 6 + 8 * k
        put(ref, x0 + 14, y, unit=un)
        plus, minus, out = (("3", "2", "1") if un == 1 else ("5", "6", "7"))
        NET(f"{ref}.{plus}"); NET(f"{ref}.{minus}")
        put(led, x0 + 24, y)
        W(f"{ref}.{out}", f"{led}.1")
        put(rl, x0 + 30, y, rot=270)                      # pin 2 (anode side) left, pin 1 (rail) right
        W(f"{led}.2", f"{rl}.2")
        PWR(f"{rl}.1", length=2.54)
    put(r_on, x0 + 44, y0 + 4, rot=90)
    PWR(f"{r_on}.1", length=2.54)
    put(d_on, x0 + 50, y0 + 4, rot=180)
    W(f"{r_on}.2", f"{d_on}.2")
    if on_gnd:
        PWR(f"{d_on}.1", length=2.54)
    else:
        NET(f"{d_on}.1", length=2.54)                     # D1_K -> Q14 drain
    for i, (ref, c) in enumerate(units3):
        put(ref, x0 + 40 + 12 * i, y0 + 18, unit=3)
        PWR(f"{ref}.8"); PWR(f"{ref}.4")
        put(c, x0 + 46 + 12 * i, y0 + 18)
        PWR(f"{c}.1"); PWR(f"{c}.2")


box(6, 114, 80, 154, "4A. PACK A GAUGE: THREE COMPARATORS, FOUR LEDs")
leds(6, 114, [("U1", 1, "D4", "R15"), ("U1", 2, "D3", "R14"), ("U2", 1, "D2", "R13")], "R12", "D1", [("U1", "C1"), ("U2", "C2")], False)
put("Q14", 64, 126)
NET("Q14.1"); PWR("Q14.2"); NET("Q14.3")                  # gate Q11_G, source GND, drain D1_K
text("D4 >= 15.9 V (80 %), D3 >= 15.1 V (50 %), D2 >= 14.3 V (20 %) from +G; D1 (ON) lit by Q14 while Q11 conducts (-V live).", 7, 149)
text("C1 / C2 at pin 8 of U1 / U2.  Bars read the open-circuit voltage (the module draws ~10 mA).", 7, 151)
box(82, 114, 156, 154, "4B. PACK B GAUGE (on +GB / 0V)")
leds(82, 114, [("U14", 1, "D14", "R57"), ("U14", 2, "D13", "R56"), ("U15", 1, "D12", "R55")], "R54", "D11", [("U14", "C20"), ("U15", "C21")], True)
text("D14 / D13 / D12 as pack A; D11 (ON) from +OUT = +V live.  C20 / C21 at pin 8 of U14 / U15.", 83, 149)

# =========================================================================== 5. output, mounting
box(158, 96, 212, 154, "5. OUTPUT AND MOUNTING HOLES")
put("J3", 170, 104, mirror=True, val_at=(0, 10.16)); text("OUT: +V / 0V / -V / CAB  (JST-PH 4, to the module)", 160, 117)
PWR("J3.1"); PWR("J3.2"); NET("J3.3"); NET("J3.4")
put("G1", 203, 103, ref_at=(0, -8.89), val_at=(0, 12.7), hide_val=True); PWR("G1.1")     # the owl: exposed copper on 0V
for i, h in enumerate(("H1", "H2", "H3", "H4", "H9", "H10", "H11", "H12")):
    put(h, 165 + 5.08 * i, 126, ref_at=(0, -3.81), val_at=(0, 3.81))
for i, h in enumerate(("H5", "H6", "H7", "H8")):
    put(h, 170 + 6 * i, 133, ref_at=(0, -3.81), val_at=(0, 3.81))
text("H1-H4 corners, H9 / H10 between the packs, H11 / H12 mid-edge: M3, the case.  H5-H8 M2.5: a Raspberry Pi above.", 159, 137)
text("The case holds the packs under the board; their XT60 leads come up through the front notches to J7 / J8.", 159, 139)
text("J3 pin 4 (CAB) is tied to 0V at the module end of the cable, on its own wire: both rails are enabled only", 159, 141)
text("while 0V really reaches the module.  Toggle ON powers the module and the gauges; OFF leaves only", 159, 143)
text("the cutoff comparators' few uA on the packs.", 159, 145)
text("-V floats whenever pack A is off (OFF, under-voltage), +V whenever pack B is or the plug is out:", 159, 147)
text("the module's fault comparator reports a missing rail.", 159, 149)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("SimpleBatteryPack.kicad_sch", "Battery board for the LaserHAT e-stim module: two 4S hobby packs in series, no charger", "A", "2026-10-31", paper="A2")
print("wrote SimpleBatteryPack.kicad_sch", n, "bytes")
