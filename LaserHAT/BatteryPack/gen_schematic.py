#!/usr/bin/env python3
"""
Generates BatteryPack.kicad_sch (rev D: two hobby 4S packs permanently in series = +V / 0 V / -V, one floating USB-C PD
charger switched between the packs by a relay under an STM32F042, per-cell balancers, ON / OFF toggle, plug interlock)
from sch_parts.py and sch_symbols.py, same engine as the e-stim module.  Then: python tools/netcheck.py and ERC.
    python gen_schematic.py
"""
from sch_engine import Sheet
from sch_parts import BY_REF, CELLS_A, CELLS_B

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


# =========================================================================== 1. packs + balancers
def pack(x0, conn, xt, cells, u0, q0, rv0, c0, rb0, title, flags):
    put(conn, x0 + 6, 20, mirror=True, val_at=(0, 10.16))
    text(title, x0 + 1, 11.5, 1.6, True)
    put(xt, x0 + 6, 41, mirror=True, ref_at=(0, -3.81), val_at=(0, -6.35))      # XT60 discharge plug: pin 1 = -, pin 2 = +
    PWR(f"{xt}.1", length=5.08)
    PWR(f"{xt}.2", length=5.08)
    for i, net in enumerate((cells[0][0],) + tuple(c[1] for c in cells)):
        pin = f"{conn}.{i + 1}"
        if net in ("GND", "0V", "+BATB"):
            e = PWR(pin, length=5.08)
            if net in flags:
                FLAG(e, up=(1, 0))                        # the packs drive these
        else:
            NET(pin, length=5.08)
    for n, (lo, hi) in enumerate(cells):
        x = x0 + 20 + 20 * n
        U, rv, cv, q, rb = f"U{u0 + n}", f"R{rv0 + n}", f"C{c0 + n}", f"Q{q0 + n}", f"R{rb0 + n}"
        put(U, x + 6, 34)
        put(rv, x - 1, 29)
        NET(f"{rv}.1")                                   # cell + (tap or pack +) via local label
        W(f"{rv}.2", f"{U}.2")
        put(cv, x - 3, 33.5)
        W(f"{cv}.1", f"{U}.2")
        W(f"{cv}.2", f"{U}.3")
        (PWR if lo in ("GND", "0V") else NET)(f"{U}.3")
        put(q, x + 14, 33)
        W(f"{U}.6", f"{q}.1")
        put(rb, x + 15, 28)
        NET(f"{rb}.1")
        W(f"{rb}.2", f"{q}.3")
        (PWR if lo in ("GND", "0V") else NET)(f"{q}.2")
        text(f"cell {n + 1}", x + 2, 26)


box(6, 8, 208, 48.5, "1. TWO 4S PACKS IN SERIES: XT60 DISCHARGE PLUGS (J7 / J8, run + charge current) AND JST-XH BALANCE LEADS (pin 1 = black = pack negative), PER-CELL BALANCERS (HY2213-BB3A, 42 mA above 4.20 V)")
pack(6, "J5", "J7", CELLS_A, 6, 7, 31, 12, 35, "PACK A (-V side): GND .. 0V", {"GND"})
pack(108, "J6", "J8", CELLS_B, 10, 15, 58, 16, 62, "PACK B (+V side): 0V .. +BATB", {"0V", "+BATB"})
text("Any 4S LiPo / Li-ion hobby pack with a JST-XH 2.5 mm 5-pin balance plug and an XT60 discharge plug.  Pack A's positive and pack B's negative are one node, 0V, the output reference: the", 7, 45)
text("packs are never reconfigured.  Balancer per cell: HY2213 OUT drives an AO3400A that bleeds the cell through 100 R (42 mA, 0.18 W) above 4.200 V, off at 4.19 V; 2.5 uA standing.", 7, 47)

# =========================================================================== 2. toggle, chains, interlock
box(6, 50, 100, 112, "2. ON / OFF TOGGLE, OUTPUT CHAINS (+V: Q1, -V: Q11), PLUG INTERLOCK (Q22), CHARGING INTERLOCK (U17)")
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
NET("R39.1")                                              # EN_A = 0V (pack A positive) only when ON
W("Q11.1", (68, 67))                                      # gate to the resistor stack's midpoint
W("R39.2", "R40.1")
lab("Q11_G", 68, 67, (0, -1))
PWR("R40.2")
put("U2", 80, 94, unit=2)                                 # pack A cutoff comparator (+ = VS, - = THCUT: output low = off)
NET("U2.5"); NET("U2.6"); NET("U2.7")
# charging interlock: the island's VBUS lights U17, its transistor holds ENB_G at 0V
put("R76", 90, 60)
PWR("R76.1")                                              # VBUS (island)
put("U17", 92, 70)
W("R76.2", (90, 63), (85, 63), (85, 69), "U17.1")
PWR("U17.2")                                              # CGND (island)
NET("U17.4"); PWR("U17.3")                                # collector ENB_G, emitter 0V
text("SW1 ON: pole 1 puts EN_A at 0V (= pack A positive), pole 2 puts EN_B at +BATB; OFF opens both (R40 / R82 hold them low).  Chain B: Q22 (2N7002) conducts when ENB_G is high", 7, 103)
text("and its source, J3.4, is at 0V, i.e. the module's plug is in (it straps pin 4 to pin 2): then R1 / R2 give Q1 Vgs = -Vsw/2 and +V is live.  ENB_G = EN_B through R81 1M, pulled to 0V by", 7, 105)
text("U15B below 12.0 V (back above 12.8 V: R53 from +OUT) and by U17 while a brick is plugged in.  Chain A: Q11 (N, in pack A's negative) gets Vgs = pack A / 2 from R39 / R40 off EN_A;", 7, 107)
text("U2B pulls the gate low below 12.0 V (R11 470k: back on at 12.9 V).  -V without 0V is harmless to the module, +V without 0V kills it, so only +V is interlocked (and the", 7, 109)
text("module's fault line reports a missing rail either way).  Gauge rails (box 2B) follow EN_A / EN_B, not the interlocks: both gauges show whenever the toggle is ON.", 7, 111)


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
for i, h in enumerate(("H1", "H2", "H3", "H4")):
    put(h, 170 + 6 * i, 126, ref_at=(0, -3.81), val_at=(0, 3.81))
for i, h in enumerate(("H5", "H6", "H7", "H8")):
    put(h, 170 + 6 * i, 133, ref_at=(0, -3.81), val_at=(0, 3.81))
text("H1-H4 M3: pack standoffs below.  H5-H8 M2.5, 58 x 49 mm: a Raspberry Pi (3B+/4/5) on standoffs above the board.", 159, 137)
text("Packs strapped under the board (two 20 mm straps through the slots), XT60 plugs to J7 / J8 and balance leads to J5 / J6 at the front edge.", 159, 139)
text("J3 pin 4 (CAB) is strapped to pin 2 (0V) inside the module's plug: +V is enabled only with the plug in, so", 159, 141)
text("the module never sees +V without 0V.  Toggle ON powers the module and the gauges; OFF leaves about", 159, 143)
text("40 uA on the packs (balancers, charger sleep).  A brick plugged in disables the outputs (U17).", 159, 145)
text("-V floats whenever pack A is off (OFF, under-voltage), +V whenever pack B is or the plug is out or a", 159, 147)
text("brick is in: the module's fault comparator reports a missing rail.", 159, 149)

# =========================================================================== 6. USB-C PD input + 3.3 V + VBUS switch + charger (floating island)
X = 72                                                    # rev B charger block shifted right by 72 units
box(138 + X, 8, 206 + X, 124, "6. CHARGER ISLAND (floats on CGND): USB-C PD 20 V INPUT (CH224A), 3.3 V (TLV760), VBUS SWITCH (MCU), 4S BUCK CHARGER (CN3704, 1 A)")
put("J1", 150 + X, 26, hide_val=True)
W("J1.A4", (144 + X, 22), (144 + X, 25), "J1.B9"); W("J1.B4", (144 + X, 23)); W("J1.A9", (144 + X, 24))
W((144 + X, 22), (144 + X, 20)); pwr_at("VBUS", 144 + X, 20, (0, -1))
W("J1.A1", (148 + X, 34), (152 + X, 34), "J1.S1"); W("J1.B1", (149 + X, 34)); W("J1.B12", (151 + X, 34))
W("J1.A12", (150 + X, 34), (150 + X, 36)); pwr_at("CGND", 150 + X, 36, (0, 1)); FLAG(pt(152 + X, 34), up=(0, 1))
put("U4", 168 + X, 28)
W("J1.A5", (161 + X, 23), (161 + X, 28), "U4.7")          # CC1
W("J1.B5", (160 + X, 24), (160 + X, 29), "U4.6")          # CC2
W("J1.A6", (159 + X, 25), (159 + X, 38)); W("J1.B6", (159 + X, 26)); lab("USB_DP", 159 + X, 38, (0, 1))    # D+ -> MCU
W("J1.A7", (158 + X, 27), (158 + X, 40)); W("J1.B7", (158 + X, 28)); lab("USB_DM", 158 + X, 40, (0, 1))    # D- -> MCU
W("U4.8", (162 + X, 26), (162 + X, 25), "U4.1"); W((162 + X, 25), (162 + X, 21)); pwr_at("VBUS", 162 + X, 21, (0, -1))
PWR("U4.11")
put("R24", 176 + X, 26, rot=90)
W("U4.9", "R24.1"); PWR("R24.2")
put("C3", 182 + X, 36)
e = PWR("C3.1"); FLAG(e, up=(0, -1)); PWR("C3.2")
# 3.3 V for the MCU, straight from VBUS (5 V from a PC, 20 V from the brick)
put("U18", 192 + X, 46)
PWR("U18.2"); PWR("U18.1"); PWR("U18.3")
put("C22", 186 + X, 54); put("C23", 198 + X, 54)
PWR("C22.1"); PWR("C22.2"); PWR("C23.1"); PWR("C23.2")
# VBUS switch: Q13 passes VBUS to VCHG while Q12 (gate CHG_EN from the MCU) pulls its gate down
put("Q13", 143 + X, 46, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q13.2")                                              # source <- VBUS (top)
e = PWR("Q13.3"); FLAG(e, up=(0, 1))                       # drain -> VCHG (bottom)
put("R43", 153 + X, 40); put("R44", 153 + X, 52)
PWR("R43.1"); W("R43.2", "R44.1"); W("Q13.1", (153 + X, 46)); lab("Q13_G", 149 + X, 46)
NET("R44.2")                                              # Q13_GD
put("Q12", 165 + X, 50, ref_at=(5.08, 2.54), val_at=(5.08, 0))
NET("Q12.1"); PWR("Q12.2"); NET("Q12.3")                  # gate CHG_EN, source CGND, drain Q13_GD
put("R42", 175 + X, 50)
NET("R42.1"); PWR("R42.2")                                # CHG_EN pull-down
# charger
put("U5", 166 + X, 74)
W("U5.15", (157 + X, 69), (157 + X, 66)); pwr_at("VCHG", 157 + X, 66, (0, -1))
put("C4", 159 + X, 61, rot=180)                           # pin 1 (VG) at the bottom
W("U5.1", (159 + X, 70), "C4.1"); PWR("C4.2")
put("Q6", 143 + X, 76, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
W("U5.16", (147 + X, 71), (147 + X, 76), "Q6.1")          # DRV
PWR("Q6.2")                                               # source <- VCHG
put("C5", 140 + X, 60); put("C6", 146 + X, 60)
PWR("C5.1"); PWR("C5.2"); PWR("C6.1"); PWR("C6.2")
put("D7", 146 + X, 82, rot=180)                           # A left (SWA) -> K right (SW)
W("Q6.3", (142 + X, 82), "D7.2")
put("L1", 154 + X, 90)
W("D7.1", (150 + X, 82), (150 + X, 90), "L1.1")
put("D8", 147 + X, 94)                                    # K left (SW), A right (CGND)
W("D8.1", (144 + X, 94), (144 + X, 90), (150 + X, 90)); PWR("D8.2")
put("R25", 161 + X, 90, rot=90); put("R26", 167 + X, 90, rot=90)
W("L1.2", "R25.1"); W("R25.2", "R26.1"); e = PWR("R26.2"); FLAG(e, up=(1, 0))       # +CHG
lab("CSP", 158 + X, 90); lab("SW", 146 + X, 90)
NET("U5.13"); PWR("U5.14")
put("C7", 182 + X, 94); put("C8", 186 + X, 94)
PWR("C7.1"); PWR("C7.2"); PWR("C8.1"); PWR("C8.2")
put("C9", 184 + X, 76)
W("U5.8", (184 + X, 74), "C9.1"); PWR("C9.2")
put("R27", 176 + X, 75, rot=90); put("C10", 180 + X, 77)
W("U5.9", "R27.1"); W("R27.2", (180 + X, 75), "C10.1"); PWR("C10.2")
put("C11", 173 + X, 79)
W("U5.11", (173 + X, 76), "C11.1"); PWR("C11.2")
PWR("U5.3"); PWR("U5.2")
NET("U5.4"); NET("U5.5")                                  # CHRG, DONE -> MCU (box 7)
put("RT1", 153 + X, 79)
W("U5.6", (153 + X, 76), "RT1.1"); PWR("RT1.2")
W("U5.7", (159 + X, 77), (159 + X, 78), "U5.10"); W((159 + X, 78), (159 + X, 80)); pwr_at("CGND", 159 + X, 80, (0, 1))
text("Everything in this box and in box 7 is referenced to CGND, which the relay K1 puts on GND (pack A) or on 0V (pack B); the brick is", 139 + X, 103)
text("mains-isolated, so the island floating is fine.  J1 / U4: the CH224A asks a PD brick for 20 V (R24 120k on CFG1); its DP / DM stay", 139 + X, 105)
text("open, the USB data lines go to the MCU (DFU).  U18 makes 3.3 V from VBUS (5 V from a PC port, 20 V from the brick).  Q13 passes VBUS", 139 + X, 107)
text("to the charger only while the MCU drives CHG_EN (R42 keeps it off in reset / DFU): the MCU power-cycles the charger at every pack swap", 139 + X, 109)
text("so the CN3704 starts a fresh cycle (it would not restart on a pack above its 16.0 V recharge threshold).  U5: buck at 300 kHz, Q6 switch,", 139 + X, 111)
text("D7 blocks the pack from the input, D8 freewheels, L1 22 uH, R25 + R26 = 0.2 R -> 1 A constant current into one pack at a time,", 139 + X, 113)
text("16.8 V +-1 % constant voltage, termination at 9 % (92 mA), trickle at 150 mA below 11.2 V, over-voltage cut at 18.1 V.  RT1 10k NTC", 139 + X, 115)
text("(board temperature; a 10k resistor disables it).  CHRG / DONE are read by the MCU.  Up to 2 A: R25 + R26 = 0.1 R, L1 20 uH, 45 W brick.", 139 + X, 117)

# =========================================================================== 7. MCU, relay, status LEDs (island)
box(138 + X, 126, 228 + X, 194, "7. CHARGE CONTROLLER (island): STM32F042F4P6 (USB DFU), RELAY K1 TO PACK A / B, PER-PACK CHARGING / DONE LEDs")
put("U19", 236, 152)
PWR("U19.16"); PWR("U19.5"); PWR("U19.15")               # VDD, VDDA, VSS
for num in ("1", "4", "2", "17", "18", "19", "20", "6", "7", "8", "9", "10", "11", "12", "13", "14"):
    NET(f"U19.{num}")
put("R70", 214, 158)
NET("R70.1"); PWR("R70.2")                                # BOOT0 pull-down
put("SW2", 214, 166)
NET("SW2.1"); PWR("SW2.2")                                # BOOT0 -> +3V3 while pressed
put("C26", 221, 158)
NET("C26.1"); PWR("C26.2")                                # NRST
put("C24", 250, 140); put("C25", 256, 140)
PWR("C24.1"); PWR("C24.2"); PWR("C25.1"); PWR("C25.2")
for i, tpn in enumerate(("TP1", "TP2", "TP3", "TP4")):
    put(tpn, 244 + 6 * i, 170)
    (PWR if tpn in ("TP3", "TP4") else NET)(f"{tpn}.1")
# senses: the connected pack (the charger's BAT node) and VBUS
put("R71", 268, 136); put("R72", 268, 144); put("C27", 262, 146)
PWR("R71.1"); W("R71.2", "R72.1"); lab("VBAT_S", 268, 140); PWR("R72.2")
W("C27.1", (262, 141), (268, 141)); PWR("C27.2")
put("R73", 276, 136); put("R74", 276, 144)
PWR("R73.1"); W("R73.2", "R74.1"); lab("VBUS_S", 276, 140); PWR("R74.2")
put("R28", 284, 136); put("R29", 290, 136)
PWR("R28.1"); NET("R28.2"); PWR("R29.1"); NET("R29.2")    # CHRG / DONE pull-ups
# relay: 12 V coil from VBUS through R86 and Q19, D19 flyback, R85 keeps it off in reset; contacts: released = pack A, energised = pack B
put("K1", 276, 160, hide_val=False)
NET("K1.1"); NET("K1.12")                                 # RLY_P (coil +, from VBUS through R86), RLY_K (Q19)
PWR("K1.4", length=2.54); PWR("K1.5", length=7.62); PWR("K1.3", length=12.7)
PWR("K1.9", length=2.54); PWR("K1.8", length=7.62); PWR("K1.10", length=12.7)
put("R86", 258, 160)
PWR("R86.1"); NET("R86.2")                                # VBUS -> RLY_P
put("Q19", 258, 184, ref_at=(5.08, 2.54), val_at=(5.08, 0))
NET("Q19.1"); PWR("Q19.2"); NET("Q19.3")                  # gate RELAY, source CGND, drain RLY_K
put("R85", 250, 190)
NET("R85.1"); PWR("R85.2")                                # RELAY pull-down
put("D19", 266, 176)
NET("D19.1"); NET("D19.2")                                # K = RLY_P, A = RLY_K: flyback across the coil
# LEDs: pack A charging (red) / done (green), pack B the same; anodes driven by the MCU through 1k / 470 R
for k, (d, r) in enumerate((("D9", "R66"), ("D10", "R67"), ("D17", "R68"), ("D18", "R69"))):
    y = 176 + 4 * k
    put(d, 220, y); put(r, 226, y, rot=270)
    PWR(f"{d}.1", length=2.54); W(f"{d}.2", f"{r}.2"); NET(f"{r}.1")
text("U19 runs the charge: at every slot end it pauses the charger (CHG_EN low), reads the connected pack at rest (R71 / R72), compares it with the other", 139 + X, 187)
text("pack's last resting reading and keeps or swaps the relay (RELAY high = pack B), then restarts the charger.  DONE flags the pack as full; both full = idle.", 139 + X, 189)
text("D9 / D10 = pack A charging / done, D17 / D18 = pack B.  K1 G6S-2 12 V coil through R86 680 R from VBUS (11.7 mA; must-operate 9 V).  Program: hold SW2, plug into a PC, dfu-util; or SWD on TP1 / TP2.", 139 + X, 191)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("BatteryPack.kicad_sch", "Battery board for the LaserHAT e-stim module: two 4S hobby packs in series, one floating charger", "D", "2026-10-28", paper="A1")
print("wrote BatteryPack.kicad_sch", n, "bytes")
