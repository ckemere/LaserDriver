#!/usr/bin/env python3
"""
Generates BatteryPack.kicad_sch (rev C: two hobby 4S packs on JST-XH balance leads, one board = +V / 0 V / -V, one USB-C PD
charger, per-cell balancers, RUN/OFF/CHARGE toggle) from sch_parts.py and sch_symbols.py, same engine as the e-stim
module.  Then: python tools/netcheck.py and ERC.
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
def pack(x0, conn, cells, u0, q0, rv0, c0, rb0, title):
    put(conn, x0 + 6, 20, mirror=True, val_at=(0, 10.16))
    text(title, x0 + 1, 11.5, 1.6, True)
    for i, net in enumerate((cells[0][0],) + tuple(c[1] for c in cells)):
        pin = f"{conn}.{i + 1}"
        if net in ("GND", "0V", "+BAT", "+BATB"):
            e = PWR(pin, length=5.08)
            if net in ("0V", "+BATB"):
                FLAG(e, up=(1, 0))                        # pack B drives these (GND / +BAT are flagged elsewhere)
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


box(6, 8, 208, 46, "1. TWO 4S PACKS ON JST-XH BALANCE LEADS (pin 1 = black = pack negative) AND PER-CELL BALANCERS (HY2213-BB3A, 42 mA above 4.20 V)")
pack(6, "J5", CELLS_A, 6, 7, 31, 12, 35, "PACK A (-V side): GND .. +BAT")
pack(108, "J6", CELLS_B, 10, 15, 58, 16, 62, "PACK B (+V side): 0V .. +BATB")
text("Any 4S LiPo / Li-ion hobby pack with a JST-XH 2.5 mm 5-pin balance plug (XT60 lead unused).  Balancer per cell: HY2213 OUT drives an AO3400A that bleeds the cell", 7, 43)
text("through 100 R (42 mA, 0.18 W) above 4.200 V, off at 4.19 V; 2.5 uA standing.  With the charger's 16.8 V this is the balance.  Pack B's negative is the 0 V output node.", 7, 45)

# =========================================================================== 2. toggle, chains, link
box(6, 50, 100, 110, "2. RUN / OFF / CHARGE TOGGLE, OUTPUT CHAINS (+V: Q1, -V: Q11), PARALLEL LINK FOR CHARGING")
put("SW1", 16, 60, val_at=(0, 10.16))
PWR("SW1.2", length=2.54)                                 # 0V common, pole 1
W("SW1.1", (22, 58), (22, 54)); pwr_at("+BAT", 22, 54, (0, -1)); FLAG(pt(22, 54), up=(0, -1))   # RUN: packs in series
W("SW1.3", (26, 59), (26, 54)); pwr_at("GND", 26, 54, (0, -1))                                  # CHARGE: negatives joined
PWR("SW1.5", length=2.54)                                 # +BATB common, pole 2
W("SW1.6", (24, 62), (24, 68)); pwr_at("+CHGB", 24, 68, (0, 1)); FLAG(pt(24, 68), up=(0, 1))    # CHARGE: positives joined
W("SW1.4", (30, 61), (30, 66)); pwr_at("+RUN", 30, 66, (0, 1)); FLAG(pt(30, 66), up=(0, 1))      # RUN: pack B chain
put("F3", 12, 80, rot=90)                                 # parallel link, 1.1 A PTC
PWR("F3.1"); PWR("F3.2")
put("R30", 24, 80, rot=90)                                # 0V pull-down
PWR("R30.1"); PWR("R30.2")
# chain B (0V domain): +RUN -> F1 -> +SW -> Q1 -> +OUT
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
NET("R2.2")                                               # CUT_OCB
put("D5", 42, 82, rot=180)                                # K left (+GB) <- A right (+SW)
PWR("D5.2"); e = PWR("D5.1"); FLAG(e, up=(-1, 0))
put("D6", 42, 86, rot=180)
PWR("D6.2"); PWR("D6.1")
put("U15", 52, 92, unit=2)                                # pack B cutoff comparator
NET("U15.5"); NET("U15.6"); NET("U15.7")
# chain A (GND domain): GND -> F2 -> GNDF -> Q11 -> -V
put("F2", 72, 58, rot=90)
PWR("F2.1", length=2.54)
NET("F2.2")                                               # GNDF
put("Q11", 70, 70, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
NET("Q11.3"); NET("Q11.2")                                # -V (drain, top), GNDF (source, bottom)
put("R39", 62, 64)
put("R40", 62, 76)
PWR("R39.1")                                              # 0V = +BAT in RUN only
W("Q11.1", (62, 70))                                      # gate to the resistor stack's midpoint
W("R39.2", "R40.1")
lab("Q11_G", 62, 69, (0, -1))
PWR("R40.2")
put("D15", 74, 82, rot=180)                               # K left (+G) <- A right (0V)
PWR("D15.2"); e = PWR("D15.1"); FLAG(e, up=(-1, 0))
put("D16", 74, 86, rot=180)
PWR("D16.2"); PWR("D16.1")
put("U2", 80, 92, unit=2)                                 # pack A cutoff comparator (+ = VS, - = THCUT: output high = on)
NET("U2.5"); NET("U2.6"); NET("U2.7")
text("SW1 pole 1 (common 0V = pack B negative): RUN -> +BAT (packs in series, 0V = output 0 V); CHARGE -> GND (negatives joined).  Pole 2 (common +BATB):", 7, 101)
text("RUN -> +RUN -> F1 -> +SW -> Q1 -> +OUT (+V); CHARGE -> +CHGB -> F3 (1.1 A PTC) -> +BAT (positives joined: both packs on the one charger).  OFF opens both,", 7, 103)
text("R30 holds 0V at GND.  Q1: U15B pulls the gate low (R1/R2) while VSB > THCUTB.  Q11 (N, on pack A's negative): R39 from 0V and R40 give Vgs = +BAT/2 in RUN;", 7, 105)
text("U2B pulls the gate low below 12.0 V (R11 470k from the gate: back on at 12.9 V); in OFF and CHARGE 0V is at GND, so Q11 is off and -V floats.  Gauge rails:", 7, 107)
text("+GB = +SW or +CHGB (D5/D6), +G = 0V or +CHGB (D15/D16): both gauges run in RUN and CHARGE and are dead in OFF.", 7, 109)


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
text("Ladder (107 uA): TH80 2.137 V, TH50 2.029 V, TH20 1.920 V, THCUT 1.595 V.  VS = rail x 0.1357 with the output live, x 0.1271 cut off; rail = pack - 0.25 V (SS14).", 103, 87)
text("Thresholds 16.0 / 15.2 / 14.4 V (pack) for the 80 / 50 / 20 % LEDs, cutoff 12.0 V, re-enable 12.8 V (pack B, R53 from +OUT) / 12.9 V (pack A, R11 from Q11's gate).", 103, 89)


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
text("D4 >= 16.0 V (80 %), D3 >= 15.2 V (50 %), D2 >= 14.4 V (20 %) from +G; D1 (ON) lit by Q14 while Q11 conducts (-V live).", 7, 149)
text("C1 / C2 at pin 8 of U1 / U2.  Bars read the open-circuit voltage (the module draws ~10 mA).", 7, 151)
box(82, 114, 156, 154, "4B. PACK B GAUGE (on +GB / 0V)")
leds(82, 114, [("U14", 1, "D14", "R57"), ("U14", 2, "D13", "R56"), ("U15", 1, "D12", "R55")], "R54", "D11", [("U14", "C20"), ("U15", "C21")], True)
text("D14 / D13 / D12 as pack A; D11 (ON) from +OUT = +V live.  C20 / C21 at pin 8 of U14 / U15.", 83, 149)

# =========================================================================== 5. output, mounting
box(158, 96, 212, 154, "5. OUTPUT AND MOUNTING HOLES")
put("J3", 170, 104, mirror=True, val_at=(0, 10.16)); text("OUT: +V / 0V / -V / nc  (JST-PH 4, to the module)", 160, 117)
PWR("J3.1"); PWR("J3.2"); NET("J3.3")
for i, h in enumerate(("H1", "H2", "H3", "H4")):
    put(h, 170 + 6 * i, 126, ref_at=(0, -3.81), val_at=(0, 3.81))
text("Packs strapped under the board (two 20 mm straps through the slots), leads to J5 / J6 at the front edge.", 159, 139)
text("Toggle RUN powers the module; OFF; CHARGE joins the packs in parallel on the charger and opens", 159, 141)
text("both outputs.  -V floats whenever pack A is off (OFF, CHARGE, under-voltage), +V whenever pack B", 159, 143)
text("is: the module's fault comparator reports a missing rail.", 159, 145)
text("Standing draw in OFF about 40 uA (balancers, charger output stage).", 159, 147)

# =========================================================================== 6. USB-C PD input + VBUS switch + charger
X = 72                                                    # rev B charger block shifted right by 72 units
box(138 + X, 8, 196 + X, 124, "6. USB-C PD 20 V INPUT (CH224A), VBUS SWITCH (CHARGE ONLY), 4S BUCK CHARGER (CN3704, 1 A)")
put("J1", 150 + X, 26, hide_val=True)
W("J1.A4", (144 + X, 22), (144 + X, 25), "J1.B9"); W("J1.B4", (144 + X, 23)); W("J1.A9", (144 + X, 24))
W((144 + X, 22), (144 + X, 20)); pwr_at("VBUS", 144 + X, 20, (0, -1))
W("J1.A1", (148 + X, 34), (152 + X, 34), "J1.S1"); W("J1.B1", (149 + X, 34)); W("J1.B12", (151 + X, 34))
W("J1.A12", (150 + X, 34), (150 + X, 36)); pwr_at("GND", 150 + X, 36, (0, 1)); FLAG(pt(152 + X, 34), up=(0, 1))
put("U4", 168 + X, 28)
W("J1.A5", (161 + X, 23), (161 + X, 28), "U4.7")          # CC1
W("J1.B5", (160 + X, 24), (160 + X, 29), "U4.6")          # CC2
W("J1.A6", (159 + X, 25), (159 + X, 30), "U4.4"); W("J1.B6", (159 + X, 26))      # D+
W("J1.A7", (158 + X, 27), (158 + X, 31), "U4.5"); W("J1.B7", (158 + X, 28))      # D-
W("U4.8", (162 + X, 26), (162 + X, 25), "U4.1"); W((162 + X, 25), (162 + X, 21)); pwr_at("VBUS", 162 + X, 21, (0, -1))
PWR("U4.11")
put("R24", 176 + X, 26, rot=90)
W("U4.9", "R24.1"); PWR("R24.2")
put("C3", 182 + X, 36)
e = PWR("C3.1"); FLAG(e, up=(0, -1)); PWR("C3.2")
# VBUS switch: Q13 passes VBUS to VCHG while Q12 (gate on +CHGB) pulls its gate down
put("Q13", 143 + X, 46, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q13.2")                                              # source <- VBUS (top)
e = PWR("Q13.3"); FLAG(e, up=(0, 1))                       # drain -> VCHG (bottom)
put("R43", 153 + X, 40); put("R44", 153 + X, 52)
PWR("R43.1"); W("R43.2", "R44.1"); W("Q13.1", (153 + X, 46)); lab("Q13_G", 149 + X, 46)
NET("R44.2")                                              # Q13_GD
put("Q12", 165 + X, 50)
NET("Q12.1"); PWR("Q12.2"); NET("Q12.3")                  # gate Q12_G, source GND, drain Q13_GD
put("R41", 175 + X, 44); put("R42", 175 + X, 56)
PWR("R41.1"); W("R41.2", "R42.1"); lab("Q12_G", 175 + X, 50, (0, -1)); PWR("R42.2")
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
put("D8", 147 + X, 94)                                    # K left (SW), A right (GND)
W("D8.1", (144 + X, 94), (144 + X, 90), (150 + X, 90)); PWR("D8.2")
put("R25", 161 + X, 90, rot=90); put("R26", 167 + X, 90, rot=90)
W("L1.2", "R25.1"); W("R25.2", "R26.1"); PWR("R26.2")
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
NET("U5.4"); NET("U5.5")                                  # CHRG, DONE -> LEDs below
put("RT1", 153 + X, 79)
W("U5.6", (153 + X, 76), "RT1.1"); PWR("RT1.2")
W("U5.7", (159 + X, 77), (159 + X, 78), "U5.10"); W((159 + X, 78), (159 + X, 80)); pwr_at("GND", 159 + X, 80, (0, 1))
put("D9", 150 + X, 102); put("R28", 155 + X, 102, rot=270)
NET("D9.1"); W("D9.2", "R28.2"); PWR("R28.1")
put("D10", 150 + X, 106); put("R29", 155 + X, 106, rot=270)
NET("D10.1"); W("D10.2", "R29.2"); PWR("R29.1")
text("J1 / U4: the CH224A asks a PD brick for 20 V (R24 120k on CFG1).  Q13 passes VBUS to the charger only while Q12 sees +CHGB (toggle in", 139 + X, 113)
text("CHARGE); a brick plugged in while RUN or OFF does nothing.  U5: buck at 300 kHz, Q6 switch, D7 blocks the packs from the input, D8 freewheels,", 139 + X, 115)
text("L1 22 uH, R25 + R26 = 0.2 R -> 1 A constant current shared by the two packs in parallel (F3), 16.8 V +-1 % constant voltage, termination at", 139 + X, 117)
text("9 % (92 mA), trickle at 150 mA below 11.2 V, re-charge below 16.0 V, over-voltage cut at 18.1 V.  RT1 10k NTC (board temperature; a 10k", 139 + X, 119)
text("resistor disables it).  D9 CHRG (red), D10 DONE (green).  All of it on GND = pack A negative = the USB-C shell.", 139 + X, 121)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("BatteryPack.kicad_sch", "Battery board for the LaserHAT e-stim module: two 4S hobby packs, one charger", "C", "2026-10-27", paper="A1")
print("wrote BatteryPack.kicad_sch", n, "bytes")
