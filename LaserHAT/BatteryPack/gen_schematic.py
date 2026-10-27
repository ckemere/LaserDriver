#!/usr/bin/env python3
"""
Generates BatteryPack.kicad_sch (4S 18650 pack board for the LaserHAT e-stim module, rev B: on-board USB-C PD charger,
balancers, RUN/OFF/CHARGE toggle, stack slave enable) from sch_parts.py and sch_symbols.py, same engine as the e-stim
module.  Then: python tools/netcheck.py and ERC.
    python gen_schematic.py
"""
from sch_engine import Sheet
from sch_parts import BY_REF, CELLS

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


# =========================================================================== 1. cells + balancers
box(6, 8, 136, 44, "1. CELLS (4S 18650 in MY-18650-01 clips) AND PER-CELL BALANCERS (HY2213-BB3A, 42 mA above 4.20 V)")
for n in range(4):
    x0 = 14 + 24 * n
    put(f"BC{2 * n + 1}", x0, 16, hide_val=True)                       # negative end: contact pin on the outside (left)
    put(f"BC{2 * n + 2}", x0 + 9, 16, mirror=True, hide_val=True)      # positive end: pin on the right
    text(f"18650 #{n + 1}", x0 + 1.5, 13.5)
    text("-", x0 + 1, 19, 1.6, True)
    text("+", x0 + 7.5, 19, 1.6, True)
for n in range(3):
    x0 = 14 + 24 * n
    W(f"BC{2 * n + 2}.1", f"BC{2 * n + 3}.1")
    lab(f"C{n + 1}", x0 + 16, 16)
e = PWR("BC1.1", length=2.54); FLAG(e, up=(-1, 0))
e = PWR("BC8.1", length=2.54); FLAG(e, up=(1, 0))
for n, (lo, hi) in enumerate(CELLS, start=1):
    x0 = 14 + 24 * (n - 1)
    U, rv, cv, q, rb = f"U{5 + n}", f"R{30 + n}", f"C{11 + n}", f"Q{6 + n}", f"R{34 + n}"
    put(U, x0 + 6, 34)
    put(rv, x0 - 1, 29)
    NET(f"{rv}.1")                                   # cell + (C1..C3 / +BAT) via local label
    W(f"{rv}.2", f"{U}.2")
    put(cv, x0 - 3, 33.5)
    W(f"{cv}.1", f"{U}.2")
    W(f"{cv}.2", f"{U}.3")
    if lo == "GND":
        PWR(f"{U}.3")
    else:
        NET(f"{U}.3")
    put(q, x0 + 14, 33)
    W(f"{U}.6", f"{q}.1")
    put(rb, x0 + 15, 28)
    NET(f"{rb}.1")
    W(f"{rb}.2", f"{q}.3")
    if lo == "GND":
        PWR(f"{q}.2")
    else:
        NET(f"{q}.2")
text("Each cell: two clips 48.0 mm apart (pin rows), contact plates 65 mm apart.  Balancer per cell: HY2213 OUT drives an AO3400A that bleeds the", 7, 41)
text("cell through 100 R (42 mA, 0.18 W) above 4.200 V, off at 4.19 V; 2.5 uA standing.  Together with the charger's 16.8 V this is the balance.", 7, 43)

# =========================================================================== 2. switch, fuse, cutoff, slave enable
box(6, 48, 80, 108, "2. RUN / OFF / CHARGE TOGGLE, 100 mA PTC, UNDER-VOLTAGE CUTOFF, STACK SLAVE ENABLE")
put("SW1", 16, 58, val_at=(0, 10.16))
PWR("SW1.2", length=2.54)                                 # +BAT common, pole 1
W("SW1.1", (22, 56), (22, 52)); pwr_at("+RUN", 22, 52, (0, -1)); FLAG(pt(22, 52), up=(0, -1))   # RUN throw
W("SW1.3", (26, 57), (26, 62)); pwr_at("+CHG", 26, 62, (0, 1)); FLAG(pt(26, 62), up=(0, 1))        # CHARGE throw
put("F1", 34, 56, rot=90)
PWR("F1.1", length=2.54)                                  # <- +RUN
e = PWR("F1.2", length=2.54); FLAG(e, up=(1, 0))           # +SW
PWR("SW1.5", length=2.54)                                 # GND common, pole 2
NET("SW1.4", length=7.62)                                 # OUT_GND -> J3.2
PWR("SW1.6", length=2.54)                                 # CGND in CHARGE
put("Q1", 30, 68, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q1.2", length=2.54)                                  # source <- +SW
e = PWR("Q1.3", length=2.54); FLAG(e, up=(0, 1))          # drain -> +OUT
put("R1", 40, 62)
put("R2", 40, 74)
PWR("R1.1")
W("Q1.1", (40, 68))
W("R1.2", "R2.1")
lab("Q1_G", 36, 68)
NET("R2.2")                                               # CUT_OC
put("D5", 30, 80, rot=180)                                # K left (+G) ... drawn A right <- +SW
PWR("D5.2"); e = PWR("D5.1"); FLAG(e, up=(-1, 0))
put("D6", 30, 84, rot=180)
PWR("D6.2"); PWR("D6.1")
put("U2", 40, 88, unit=2)                                 # cutoff comparator
NET("U2.5"); NET("U2.6"); NET("U2.7")
# slave enable
put("Q2", 48, 60, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
NET("Q2.2")                                               # STACK_IN (source, top)
put("R16", 56, 56); put("R17", 56, 64)
NET("R16.1"); W("R16.2", "R17.1"); W("Q2.1", (56, 60)); PWR("R17.2")
put("R18", 47, 66); put("R19", 47, 72)
W("Q2.3", "R18.1"); W("R18.2", "R19.1"); PWR("R19.2")
lab("EN_G", 47, 69)
put("Q5", 60, 80, mirror=True, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
NET("Q5.3"); PWR("Q5.2")
put("R22", 66, 76); put("R23", 66, 84)
W("Q5.1", (66, 80)); W("R22.2", "R23.1"); PWR("R22.1"); PWR("R23.2")
put("Q3", 60, 94)
NET("Q3.1"); NET("Q3.3"); PWR("Q3.2")
put("Q4", 70, 60, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q4.2"); PWR("Q4.3")
put("R20", 76, 56); put("R21", 76, 64)
W("Q4.1", (76, 60)); W("R20.2", "R21.1"); PWR("R20.1"); NET("R21.2")
text("SW1 pole 1 (common +BAT): RUN -> +RUN -> F1 (100 mA hold, 300 mA trip) -> +SW -> Q1 -> +OUT; CHARGE -> +CHG.  Pole 2 (common GND): RUN -> OUT_GND (J3.2);", 7, 99)
text("CHARGE -> CGND (USB-C ground, charger return).  OFF opens both.  Gauge rail +G = +SW or +CHG through D5 / D6.  U2B pulls Q1's gate low", 7, 101)
text("(R1/R2: Vgs = -(+SW)/2) while VS > THCUT: +OUT off below 12.0 V, back on above 12.8 V (R11).  Slave: with the upper board in RUN its +RUN", 7, 103)
text("arrives on J3.4 (STACK_IN), Q2 (gate on +OUT = upper GND) sources into Q3's gate, Q3 pulls Q4's gate down, Q4 feeds +RUN.  Q5 blocks it in CHARGE.", 7, 105)

# =========================================================================== 3. reference, ladder, sample
box(82, 48, 136, 90, "3. 2.495 V REFERENCE, THRESHOLD LADDER, PACK SAMPLE (on +G)")
put("R3", 92, 52)
PWR("R3.1")
put("U3", 92, 60, ref_at=(3.81, -1.27), val_at=(3.81, 1.27))
W("R3.2", "U3.2")
lab("VREF", 92, 56)
W("U3.1", (88, 60), (88, 56), (92, 56))
PWR("U3.3")
for i, r in enumerate(("R4", "R5", "R6", "R7", "R8")):
    put(r, 106, 52 + 6 * i)
NET("R4.1")
for a, b, net, y in (("R4", "R5", "TH80", 55), ("R5", "R6", "TH50", 61), ("R6", "R7", "TH20", 67), ("R7", "R8", "THCUT", 73)):
    W(f"{a}.2", f"{b}.1")
    lab(net, 106, y)
PWR("R8.2")
put("R9", 120, 56)
put("R10", 120, 64)
put("R11", 130, 56)
PWR("R9.1")
W("R9.2", "R10.1")
lab("VS", 120, 60)
PWR("R10.2")
PWR("R11.1")
W("R11.2", ("y", 60 * u), (120, 60))
text("Ladder (107 uA): TH80 2.137 V, TH50 2.029 V, TH20 1.920 V, THCUT 1.595 V.  VS = +G x 0.1357 with +OUT live (R9 || R11 against R10), x 0.1271 cut off;", 83, 85)
text("+G = +BAT - 0.25 V (SS14).  Thresholds 16.0 / 15.2 / 14.4 V (pack) for D4 / D3 / D2, cutoff 12.0 V, re-enable 12.8 V.  R3: >= 1.3 mA in U3 at 12 V.", 83, 87)

# =========================================================================== 4. gauge comparators + LEDs
box(6, 112, 80, 152, "4. GAUGE: THREE COMPARATORS, FOUR LEDs (about 1 mA each)")
for unit, (ref, un, y, led, rl) in enumerate((("U1", 1, 118, "D4", "R15"), ("U1", 2, 126, "D3", "R14"), ("U2", 1, 134, "D2", "R13"))):
    put(ref, 20, y, unit=un)
    plus, minus, out = (("3", "2", "1") if un == 1 else ("5", "6", "7"))
    NET(f"{ref}.{plus}"); NET(f"{ref}.{minus}")
    put(led, 30, y)
    W(f"{ref}.{out}", f"{led}.1")
    put(rl, 36, y, rot=270)               # pin 2 (anode side) left, pin 1 (+G) right
    W(f"{led}.2", f"{rl}.2")
    PWR(f"{rl}.1", length=2.54)
put("R12", 50, 116, rot=90)
PWR("R12.1", length=2.54)
put("D1", 56, 116, rot=180)
W("R12.2", "D1.2")
PWR("D1.1", length=2.54)
put("U1", 46, 130, unit=3)
PWR("U1.8"); PWR("U1.4")
put("C1", 52, 130)
PWR("C1.1"); PWR("C1.2")
put("U2", 58, 130, unit=3)
PWR("U2.8"); PWR("U2.4")
put("C2", 64, 130)
PWR("C2.1"); PWR("C2.2")
text("Open collectors sink the LED cathodes: D4 >= 16.0 V (80 %), D3 >= 15.2 V (50 %), D2 >= 14.4 V (20 %) from +G, so the bar also shows while", 7, 147)
text("charging; D1 (from +OUT) = output live.  Bar reads the open-circuit voltage (the e-stim module draws ~10 mA).  C1 / C2 at pin 8 of U1 / U2.", 7, 149)

# =========================================================================== 5. output, stack link, mounting
box(82, 94, 136, 152, "5. OUTPUT, STACK LINK, MOUNTING HOLES")
put("J3", 94, 102, mirror=True, val_at=(0, 10.16)); text("OUT: +V / 0V / -V / STACK_IN  (to the module, or to the upper board's J4)", 84, 115)
NET("J3.1"); NET("J3.2"); NET("J3.3"); NET("J3.4")
put("J4", 118, 102, mirror=True, val_at=(0, 10.16)); text("LINK IN from the lower board's J3 (lower +OUT -> GND here)", 110, 118)
PWR("J4.1"); NET("J4.2"); PWR("J4.4")
for i, h in enumerate(("H1", "H2", "H3", "H4")):
    put(h, 94 + 6 * i, 122, ref_at=(0, -3.81), val_at=(0, 3.81))
text("Two identical boards stacked on 25 mm M3 standoffs; lower J3 -> upper J4 with a straight 4-wire JST-PH cable: lower +OUT -> upper GND", 83, 139)
text("(= 0 V), lower OUT_GND -> LINK_N -> upper J3.3 (= -V), upper +RUN -> lower STACK_IN (slave enable).  Upper J3 = +V / 0 V / -V / (+RUN) to the", 83, 141)
text("e-stim module.  Lower toggle: OFF normally (its output follows the upper toggle), CHARGE to charge; RUN only for a board on its own.", 83, 143)
text("Charging: either or both toggles in CHARGE, plug USB-C PD bricks in; a charging board has both output lines open, so grounds never loop.", 83, 145)

# =========================================================================== 6. USB-C PD input + charger
box(138, 8, 196, 110, "6. USB-C PD 20 V INPUT (CH224A) AND 4S BUCK CHARGER (CN3704, 1 A), ALL ON CGND")
put("J1", 150, 26, hide_val=True)
W("J1.A4", (144, 22), (144, 25), "J1.B9"); W("J1.B4", (144, 23)); W("J1.A9", (144, 24))
W((144, 22), (144, 20)); pwr_at("VBUS", 144, 20, (0, -1))
W("J1.A1", (148, 34), (152, 34), "J1.S1"); W("J1.B1", (149, 34)); W("J1.B12", (151, 34))
W("J1.A12", (150, 34), (150, 36)); pwr_at("CGND", 150, 36, (0, 1)); FLAG(pt(152, 34), up=(0, 1))
put("U4", 168, 28)
W("J1.A5", (161, 23), (161, 28), "U4.7")                  # CC1
W("J1.B5", (160, 24), (160, 29), "U4.6")                  # CC2
W("J1.A6", (159, 25), (159, 30), "U4.4"); W("J1.B6", (159, 26))      # D+
W("J1.A7", (158, 27), (158, 31), "U4.5"); W("J1.B7", (158, 28))      # D-
W("U4.8", (162, 26), (162, 25), "U4.1"); W((162, 25), (162, 21)); pwr_at("VBUS", 162, 21, (0, -1))
PWR("U4.11")
put("R24", 176, 26, rot=90)
W("U4.9", "R24.1"); PWR("R24.2")
put("C3", 182, 36)
e = PWR("C3.1"); FLAG(e, up=(0, -1)); PWR("C3.2")
# charger
put("U5", 166, 58)
W("U5.15", (157, 53), (157, 50)); pwr_at("VBUS", 157, 50, (0, -1))
put("C4", 159, 45, rot=180)                               # pin 1 (VG) at the bottom
W("U5.1", (159, 54), "C4.1"); PWR("C4.2")
put("Q6", 143, 60, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
W("U5.16", (147, 55), (147, 60), "Q6.1")                  # DRV
PWR("Q6.2")                                               # source <- VBUS
put("C5", 140, 42); put("C6", 146, 42)
PWR("C5.1"); PWR("C5.2"); PWR("C6.1"); PWR("C6.2")
put("D7", 146, 66, rot=180)                               # A left (SWA) -> K right (SW)
W("Q6.3", (142, 66), "D7.2")
put("L1", 154, 74)
W("D7.1", (150, 66), (150, 74), "L1.1")
put("D8", 147, 78)                                        # K left (SW), A right (CGND)
W("D8.1", (144, 78), (144, 74), (150, 74)); PWR("D8.2")
put("R25", 161, 74, rot=90); put("R26", 167, 74, rot=90)
W("L1.2", "R25.1"); W("R25.2", "R26.1"); PWR("R26.2")
lab("CSP", 158, 74); lab("SW", 146, 74)
NET("U5.13"); PWR("U5.14")
put("C7", 182, 78); put("C8", 186, 78)
PWR("C7.1"); PWR("C7.2"); PWR("C8.1"); PWR("C8.2")
put("C9", 184, 60)
W("U5.8", (184, 58), "C9.1"); PWR("C9.2")
put("R27", 176, 59, rot=90); put("C10", 180, 61)
W("U5.9", "R27.1"); W("R27.2", (180, 59), "C10.1"); PWR("C10.2")
put("C11", 173, 63)
W("U5.11", (173, 60), "C11.1"); PWR("C11.2")
PWR("U5.3"); PWR("U5.2")
NET("U5.4"); NET("U5.5")                                  # CHRG, DONE -> LEDs below
put("RT1", 153, 63)
W("U5.6", (153, 60), "RT1.1"); PWR("RT1.2")
W("U5.7", (159, 61), (159, 62), "U5.10"); W((159, 62), (159, 64)); pwr_at("CGND", 159, 64, (0, 1))
put("D9", 150, 86); put("R28", 155, 86, rot=270)
NET("D9.1"); W("D9.2", "R28.2"); PWR("R28.1")
put("D10", 150, 90); put("R29", 155, 90, rot=270)
NET("D10.1"); W("D10.2", "R29.2"); PWR("R29.1")
put("R30", 184, 86)
PWR("R30.1"); PWR("R30.2")
text("J1 / U4: the CH224A asks a PD brick for 20 V (R24 120k on CFG1); below 20 V the CN3704 cannot reach 16.8 V and nothing charges.  U5: buck at", 139, 99)
text("300 kHz, Q6 switch, D7 blocks the pack from the input through Q6's body diode, D8 freewheels, L1 22 uH, R25 + R26 = 0.2 R -> 1 A constant current,", 139, 101)
text("16.8 V +-1 % constant voltage, termination at 9 % (92 mA), trickle at 150 mA below 11.2 V, re-charge below 16.0 V, over-voltage cut at 18.1 V.", 139, 103)
text("RT1 10k NTC between the cells stops charging hot / cold (10k fixed resistor disables it).  D9 CHRG (red), D10 DONE (green).  CGND meets GND only", 139, 105)
text("in the CHARGE position (SW1 pole 2); R30 1M keeps it defined otherwise, so a brick plugged in while running does nothing.  20 uA from the pack idle.", 139, 107)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("BatteryPack.kicad_sch", "4S 18650 battery pack for the LaserHAT e-stim module", "B", "2026-10-26")
print("wrote BatteryPack.kicad_sch", n, "bytes")
