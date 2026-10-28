"""
Battery board for the LaserHAT e-stim module, rev D (2026-10-28): two hobby 4S packs permanently in series give
+V / 0 V / -V; one floating USB-C charger is switched between the packs by a relay under a small MCU.  Single source of
truth for symbol, value, footprint, LCSC code and pin -> net; gen_schematic.py draws it, tools/netcheck.py proves the
drawn schematic matches, tools/make_bom.py writes bom_BatteryPack.csv.

Rev C (commit 8b583b4) charged the packs in parallel through a RUN / OFF / CHARGE toggle: one half of the board jumped
by a pack voltage between the modes, the two negatives had to be joined, mismatched packs equalised through a PTC.
Rev D fixes the topology and moves the switching into the charger:
  packs     pack A (-V side): GND .. 0V (J5 = GND, C1, C2, C3, 0V; J7 = GND / 0V);  pack B (+V side): 0V .. +BATB
            (J6 = 0V, B1, B2, B3, +BATB; J8 = 0V / +BATB).  0V = pack A positive = pack B negative = the output reference,
            always.  Any 4S pack with a JST-XH 2.5 mm 5-pin balance plug and an XT60 discharge plug.  Per-cell HY2213
            balancers (42 mA through 100 R above 4.200 V, release 4.19 V) on both packs.
  switch    SW1 DPDT ON-ON toggle (MTS-202) = ON / OFF.  Pole 1 (common EN_A): ON -> 0V.  Pole 2 (common EN_B): ON -> +BATB.
            OFF opens both (R40 holds EN_A's divider at GND, R82 holds EN_B at 0V): outputs off, gauges dark, the packs
            see only the balancers and the charger's sleep current (about 40 uA).
  chain B   +BATB -> F1 (100 mA PTC) -> +SW -> Q1 (P) -> +OUT = J3.1 (+V).  Q22 (2N7002) pulls Q1's gate low through R2
            (R1 holds it off) while its gate ENB_G is high: ENB_G = EN_B through R81 1M, pulled to 0V by U15B below 12.0 V
            (back above 12.8 V, R53 from +OUT), by the opto U17 while a brick is plugged in, and by nothing else.
            Q22's source is J3.4 (CAB): the module's plug straps pin 4 to pin 2 (0V), so +V can only appear when 0V is
            connected (the module died twice from +V / -V without 0V: its isolated ground floats to a rail).
  chain A   GND -> F2 (100 mA PTC) -> GNDF -> Q11 (N) -> -V = J3.3.  Q11's gate: R39 from EN_A (= 0V when ON) and R40 to
            GND give Vgs = pack A / 2; U2B pulls it low below 12.0 V (R11 470k from the gate: back on at 12.9 V).
            Q14 lights D1 while Q11 is on.  -V alone is harmless to the module (nothing in it conducts without 0V), so
            chain A is not interlocked; +V is.
  gauges    one per pack, each on its own rail through a P-FET: +G = 0V through Q20 (Q21 from EN_A's divider),
            +GB = +BATB through Q23 (Q24 from EN_B).  CJ431 2.495 V, ladder TH80 / TH50 / TH20 / THCUT, sample divider,
            LM393 pairs, three bar LEDs + ON LED.  Both show while the toggle is ON (also while charging).
  charger   a floating island on its own ground CGND: J1 USB-C, U4 CH224A asks the brick for 20 V (R24 120k; its DP / DM
            are left open so the MCU owns the USB data lines), U18 TLV76033 makes +3V3 for U19 STM32F042F4P6 (USB DFU
            bootloader: hold SW2 BOOT while plugging into a PC, or SWD on TP1 / TP2), Q13 (P) passes VBUS to VCHG only
            while the MCU drives CHG_EN (Q12), U5 CN3704 buck charger at 16.8 V, 1 A (R25 + R26 = 0.2 R), termination
            92 mA, trickle below 11.2 V, NTC RT1, its output +CHG / CGND goes through relay K1 (Omron G6S-2 DC12, 12 V coil fed from VBUS
            through R86 680 R, Q19 driver, R85 pull-down, D19 flyback) to pack A (released: NC) or pack B (energised: NO).  The MCU reads CHRG / DONE
            (R28 / R29 pull-ups), the connected pack (R71 / R72 1M / 180k + C27) and VBUS (R73 / R74), and drives D9 / D10 (pack A
            charging / done) and D17 / D18 (pack B) through R66-R69.  The brick is mains-isolated, so the island riding at
            GND or at 0V is fine; it is the only part of the board whose potential moves.
  interlock U17 EL817: LED from VBUS through R76, transistor pulls ENB_G to 0V -> +V off (and -V with it: the module's
            fault line) whenever a brick is in, so the brick's mains leakage can never reach the electrode.
  output    J3 (+OUT, 0V, -V, CAB) to the module, a side-entry PH socket opening over the top edge: pins 1-3 as rev B / C, pin 4
            strapped to pin 2 in the plug.
"""

R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
CPEL = "Capacitor_SMD:CP_Elec_6.3x5.4"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT23_6 = "Package_TO_SOT_SMD:SOT-23-6"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
TSSOP16 = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
TSSOP20 = "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm"
ESSOP10 = "Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm"
LED0603 = "LED_SMD:LED_0603_1608Metric"
LED0805 = "LED_SMD:LED_0805_2012Metric"
SMA = "Diode_SMD:D_SMA"
SOD123 = "Diode_SMD:D_SOD-123"
FUSE1812 = "Fuse:Fuse_1812_4532Metric"
IND = "Inductor_SMD:L_Sunlord_MWSA0603S"
PH4 = "Connector_JST:JST_PH_S4B-PH-K_1x04_P2.00mm_Horizontal"     # side entry: the cable leaves over the top edge
XH5 = "Connector_JST:JST_XH_S5B-XH-A-1_1x05_P2.50mm_Horizontal"
XT60 = "battpack:XT60PW-M"                              # KiCad's AMASS_XT60PW-M footprint + our 3D model (battpack.3dshapes)
USBC = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
TOGGLE = "battpack:SW_MTS-202"
RELAY = "Relay_THT:Relay_DPDT_Omron_G6S-2"
OPTO = "battpack:EL817S1"
PUSH = "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A"
TP = "TestPoint:TestPoint_Pad_1.5x1.5mm"
HOLE = "MountingHole:MountingHole_3.2mm_M3"
HOLE25 = "MountingHole:MountingHole_2.7mm_M2.5"

# LCSC codes (JLCPCB basic parts unless noted "ext"; checked 2026-10-26/28 with tools/jlc_search.py).  Values of switches,
# LEDs, connectors and other named parts are JLC's model strings (JLC's BOM matcher compares the Comment with them);
# functions are in the net names and on the silk.
L = dict(R100k="C25803", R68k="C23231", R30k="C22984", R18k="C25810", R15k="C22809", R13k="C22797", R12k="C22790",
         R10k="C25804", R6k8="C23212", R6k2="C4260", R2k="C22975", R1M="C22935", R470k="C23178", R120k="C25808",
         R1k="C21190", R470="C23179", R680_0805="C17798", R180k="C22827", R120="C22787", R100="C22775", R100_1206="C17901", R0R1_1206="C25334",
         C100n="C14663", C1u50="C15849", C470p="C1620", C220n="C21120", C22u25="C12891", C22u50el="C2836438",   # el: ext
         AO3401A="C15127", AO3400A="C20917", N7002="C8545", CJ431="C3113", LM393="C7955", SS14="C2480", SS34="C8678",
         D4148="C81598", CN3704="C51659", CH224A="C42459160", HY2213="C113632", NTC="C13564",                   # ext x4
         STM32="C81002", RELAY="C1525289", OPTO="C2912100", LDO="C2683368",                                      # ext x4
         TOGGLE="C55159891", USBC="C165948", L22u="C408453", PH4="C157926", PTC="C12430",                       # ext x5
         XH5="C163038", XT60="C98732", PUSH="C318884",                                                           # ext x2
         LEDR="C2286", LEDY="C2296", LEDG="C2297")


def R(ref, val, a, b, lcsc="", fp=R0603):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, lcsc="", fp=C0603):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def nmos(ref, g, s, d):
    return dict(ref=ref, sym="Q_NMOS_GSD", value="AO3400A", fp=SOT23, lcsc=L["AO3400A"], nets={"1": g, "2": s, "3": d})


def nmos2(ref, g, s, d):
    """small-signal N-FET for logic duty (Vgs max +-20 V)"""
    return dict(ref=ref, sym="Q_NMOS_GSD", value="2N7002", fp=SOT23, lcsc=L["N7002"], nets={"1": g, "2": s, "3": d})


def pmos(ref, g, s, d):
    return dict(ref=ref, sym="Q_PMOS_GSD", value="AO3401A", fp=SOT23, lcsc=L["AO3401A"], nets={"1": g, "2": s, "3": d})


def led(ref, val, lcsc, k, a, fp=LED0805):
    return dict(ref=ref, sym="LED", value=val, fp=fp, lcsc=lcsc, nets={"1": k, "2": a})


def schottky(ref, val, lcsc, k, a):
    return dict(ref=ref, sym="D_Schottky", value=val, fp=SMA, lcsc=lcsc, nets={"1": k, "2": a})


def ptc(ref, val, lcsc, a, b):
    return dict(ref=ref, sym="Polyfuse", value=val, fp=FUSE1812, lcsc=lcsc, nets={"1": a, "2": b})


def xt60(ref, neg, pos):
    """board-mount XT60PW-M (pad 1 = the footprint's "-" pin, pad 2 = "+"); mates with the pack's XT60 discharge plug"""
    return dict(ref=ref, sym="Conn_01x02", value="XT60PW-M", fp=XT60, lcsc=L["XT60"], nets={"1": neg, "2": pos})


def xh(ref, nets):
    return dict(ref=ref, sym="Conn_01x05", value="S5B-XH-A-1(LF)(SN)", fp=XH5, lcsc=L["XH5"],
                nets={str(i + 1): n for i, n in enumerate(nets)})


def tp(ref, net):
    return dict(ref=ref, sym="TestPoint", value=net, fp=TP, lcsc="", nets={"1": net})


CELLS_A = [("GND", "C1"), ("C1", "C2"), ("C2", "C3"), ("C3", "0V")]        # (negative end, positive end) of cells 1..4
CELLS_B = [("0V", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "+BATB")]


def gauge(ref_u, ref_r, ref_c, ref_d, rails, hys):
    """reference + ladder + sample divider + two LM393 + three bar LEDs for one pack.
    ref_u: (comparator 1, comparator 2, CJ431); ref_r: first of 13 consecutive resistor numbers; ref_c: first of 2 caps;
    ref_d: (ON LED, 20 %, 50 %, 80 %); rails: (gauge rail, ground, output-live net for the ON LED, suffix for the labels);
    hys: (hysteresis resistor net, value, code).  Returns the parts; the cutoff comparator is unit B of comparator 2."""
    ua, ub, uref = ref_u
    g, gnd, live, sfx = rails
    r = {k: f"R{ref_r + i}" for i, k in enumerate(("ref", "l1", "l2", "l3", "l4", "l5", "s1", "s2", "hys", "on", "r20", "r50", "r80"))}
    vref, th80, th50, th20, thcut, vs = (f"{n}{sfx}" for n in ("VREF", "TH80", "TH50", "TH20", "THCUT", "VS"))
    l80, l50, l20, cut = (f"{n}{sfx}" for n in ("LED80", "LED50", "LED20", "CUT_OC"))
    d_on, d20, d50, d80 = ref_d
    hys_src, hys_val, hys_code = hys
    parts = [
        dict(ref=uref, sym="TL431_SOT23", value="CJ431", fp=SOT23, lcsc=L["CJ431"], nets={"1": vref, "2": vref, "3": gnd}),
        R(r["ref"], "6.8k", g, vref, L["R6k8"]),             # >= 1.3 mA into the CJ431 at 12 V (min 1 mA)
        R(r["l1"], "6.2k", vref, th80, L["R6k2"]),           # 2.495 V -> 2.162 V = 15.9 V (pack; the rail is the pack now)
        R(r["l2"], "2k", th80, th50, L["R2k"]),              # 2.054 V = 15.1 V
        R(r["l3"], "2k", th50, th20, L["R2k"]),              # 1.946 V = 14.3 V
        R(r["l4"], "6.2k", th20, thcut, L["R6k2"]),          # 1.613 V = 11.9 V (on), 12.7 V (off)
        R(r["l5"], "30k", thcut, gnd, L["R30k"]),
        R(r["s1"], "68k", g, vs, L["R68k"]),                 # VS = rail x 0.1357 with the output live, x 0.1271 cut off
        R(r["s2"], "10k", vs, gnd, L["R10k"]),
        R(r["hys"], hys_val, hys_src, vs, hys_code),         # cutoff hysteresis
        dict(ref=ua, sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
             nets={"3": th80, "2": vs, "1": l80, "5": th50, "6": vs, "7": l50, "8": g, "4": gnd}),
        C(f"C{ref_c}", "100n", g, gnd, L["C100n"]),
        C(f"C{ref_c + 1}", "100n", g, gnd, L["C100n"]),
        led(d20, "KT-0805Y", L["LEDY"], l20, f"{d20}_A"),
        led(d50, "KT-0805G", L["LEDG"], l50, f"{d50}_A"),
        led(d80, "KT-0805G", L["LEDG"], l80, f"{d80}_A"),
        R(r["r20"], "13k", g, f"{d20}_A", L["R13k"]),        # ~1 mA
        R(r["r50"], "12k", g, f"{d50}_A", L["R12k"]),        # green Vf ~2.8 V
        R(r["r80"], "12k", g, f"{d80}_A", L["R12k"]),
    ]
    return parts, dict(ub=ub, cut=cut, vs=vs, thcut=thcut, on_r=r["on"], d_on=d_on, l20=l20)


# ---------------------------------------------------------------- pack A gauge (GND domain): rev B's references
GAUGE_A, GA = gauge(("U1", "U2", "U3"), 3, 1, ("D1", "D2", "D3", "D4"), ("+G", "GND", None, ""), ("Q11_G", "470k", L["R470k"]))
# pack B gauge (0V domain)
GAUGE_B, GB = gauge(("U14", "U15", "U16"), 45, 20, ("D11", "D12", "D13", "D14"), ("+GB", "0V", "+OUT", "B"), ("+OUT", "1M", L["R1M"]))

PARTS = [
    # ---------------------------------------------------------------- packs
    xh("J5", ["GND", "C1", "C2", "C3", "0V"]),
    xh("J6", ["0V", "B1", "B2", "B3", "+BATB"]),
    xt60("J7", "GND", "0V"),
    xt60("J8", "0V", "+BATB"),
    # ---------------------------------------------------------------- ON / OFF toggle
    dict(ref="SW1", sym="SW_DPDT", value="CAX-MTS202B2-BB-20.5JL", fp=TOGGLE, lcsc=L["TOGGLE"],
         nets={"2": "EN_A", "1": "0V", "3": None, "5": "EN_B", "4": "+BATB", "6": None}),
    R("R82", "1M", "EN_B", "0V", L["R1M"]),                              # EN_B at 0V while OFF
    # ---------------------------------------------------------------- chain B: +BATB -> fuse -> Q1 -> +OUT (+V), interlocked
    ptc("F1", "MF-MSMF010-2", L["PTC"], "+BATB", "+SW"),
    pmos("Q1", "Q1_G", "+SW", "+OUT"),
    R("R1", "100k", "+SW", "Q1_G", L["R100k"]),          # gate pull-up (off)
    R("R2", "100k", "Q1_G", "Q22_D", L["R100k"]),        # with R1: Vgs = -Vsw/2 while Q22 conducts (AO3401A Vgs max 12 V)
    nmos2("Q22", "ENB_G", "CAB", "Q22_D"),               # source = J3.4: conducts only with the module plugged in
    R("R81", "1M", "EN_B", "ENB_G", L["R1M"]),           # ENB_G = +BATB when ON unless U15B / U17 pull it to 0V
    dict(ref=GB["ub"], sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20B", "2": "VSB", "1": "LED20B", "5": "VSB", "6": "THCUTB", "7": "ENB_G", "8": "+GB", "4": "0V"}),
    led("D11", "KT-0603R", L["LEDR"], "0V", "D11_A", fp=LED0603),      # ON (+V live)
    R("R54", "13k", "+OUT", "D11_A", L["R13k"]),
    # ---------------------------------------------------------------- chain A: GND -> fuse -> Q11 -> -V
    ptc("F2", "MF-MSMF010-2", L["PTC"], "GND", "GNDF"),
    nmos("Q11", "Q11_G", "GNDF", "-V"),
    R("R39", "100k", "EN_A", "Q11_G", L["R100k"]),       # EN_A = 0V (pack A positive) only when ON
    R("R40", "100k", "Q11_G", "GND", L["R100k"]),        # Vgs = pack A / 2 (AO3400A Vgs max 12 V)
    dict(ref=GA["ub"], sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20", "2": "VS", "1": "LED20", "5": "VS", "6": "THCUT", "7": "Q11_G", "8": "+G", "4": "GND"}),
    led("D1", "KT-0603R", L["LEDR"], "D1_K", "D1_A", fp=LED0603),      # ON (-V live)
    R("R12", "13k", "+G", "D1_A", L["R13k"]),
    nmos("Q14", "Q11_G", "GND", "D1_K"),                 # lights D1 while Q11 is on, without loading -V
    # ---------------------------------------------------------------- gauge rails: +G from 0V (pack A), +GB from +BATB (pack B)
    pmos("Q20", "Q20_G", "0V", "+G"),
    R("R77", "100k", "0V", "Q20_G", L["R100k"]),
    R("R78", "100k", "Q20_G", "Q21_D", L["R100k"]),      # Vgs(Q20) = -pack A / 2
    nmos2("Q21", "Q21_G", "GND", "Q21_D"),
    R("R79", "100k", "EN_A", "Q21_G", L["R100k"]),       # EN_A / 2 above GND when ON (2N7002 Vgs max 20 V)
    R("R80", "100k", "Q21_G", "GND", L["R100k"]),
    pmos("Q23", "Q23_G", "+BATB", "+GB"),
    R("R83", "100k", "+BATB", "Q23_G", L["R100k"]),
    R("R84", "100k", "Q23_G", "Q24_D", L["R100k"]),      # Vgs(Q23) = -pack B / 2
    nmos2("Q24", "EN_B", "0V", "Q24_D"),
    # ---------------------------------------------------------------- charging interlock (opto from the island)
    dict(ref="U17", sym="EL817", value="EL817S1(C)(TU)-F", fp=OPTO, lcsc=L["OPTO"],
         nets={"1": "U17_A", "2": "CGND", "4": "ENB_G", "3": "0V"}),
    R("R76", "10k", "VBUS", "U17_A", L["R10k"]),         # 1.9 mA at 20 V, 0.4 mA at 5 V: either holds ENB_G down
    # ---------------------------------------------------------------- USB-C PD input, PD sink, 3.3 V, VBUS switch (island, CGND)
    dict(ref="J1", sym="USB_C_16P", value="TYPE-C-31-M-12", fp=USBC, lcsc=L["USBC"],
         nets={"A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2",
               "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "A8": None, "B8": None,
               "A1": "CGND", "B1": "CGND", "A12": "CGND", "B12": "CGND", "S1": "CGND"}),
    dict(ref="U4", sym="CH224A", value="CH224A", fp=ESSOP10, lcsc=L["CH224A"],
         nets={"1": "VBUS", "8": "VBUS", "7": "CC1", "6": "CC2", "4": None, "5": None, "9": "CFG1",
               "2": None, "3": None, "10": None, "11": "CGND"}),
    C("C3", "1u", "VBUS", "CGND", L["C1u50"]),           # 50 V
    R("R24", "120k", "CFG1", "CGND", L["R120k"]),        # single-resistor configuration: 20 V
    dict(ref="U18", sym="TLV760", value="TLV76033DBZR", fp=SOT23, lcsc=L["LDO"],
         nets={"2": "VBUS", "1": "+3V3", "3": "CGND"}),
    C("C22", "1u", "VBUS", "CGND", L["C1u50"]),          # at the LDO input
    C("C23", "1u", "+3V3", "CGND", L["C1u50"]),
    pmos("Q13", "Q13_G", "VBUS", "VCHG"),                # VBUS reaches the charger only while the MCU says so
    R("R43", "100k", "VBUS", "Q13_G", L["R100k"]),
    R("R44", "100k", "Q13_G", "Q13_GD", L["R100k"]),     # Vgs(Q13) = -VBUS/2 = -10 V
    nmos2("Q12", "CHG_EN", "CGND", "Q13_GD"),
    R("R42", "100k", "CHG_EN", "CGND", L["R100k"]),      # charger off while the MCU is in reset / DFU
    # ---------------------------------------------------------------- CN3704 buck charger (island): +CHG / CGND to the relay
    dict(ref="U5", sym="CN3704", value="CN3704", fp=TSSOP16, lcsc=L["CN3704"],
         nets={"15": "VCHG", "1": "VG", "16": "DRV", "4": "CHRG", "5": "DONE", "6": "TEMP", "7": "CGND", "8": "COM1",
               "9": "COM2", "10": "CGND", "11": "COM3", "12": None, "13": "CSP", "14": "+CHG", "2": "CGND", "3": "CGND"}),
    C("C4", "100n", "VG", "VCHG", L["C100n"]),
    dict(ref="C5", sym="CP", value="22u 50V", fp=CPEL, lcsc=L["C22u50el"], nets={"1": "VCHG", "2": "CGND"}),
    C("C6", "1u", "VCHG", "CGND", L["C1u50"]),
    pmos("Q6", "DRV", "VCHG", "SWA"),                    # buck switch
    schottky("D7", "SS34", L["SS34"], "SW", "SWA"),      # blocks battery -> input through Q6's body diode
    schottky("D8", "SS34", L["SS34"], "SW", "CGND"),     # freewheel
    dict(ref="L1", sym="L", value="MWSA0603S-220MT", fp=IND, lcsc=L["L22u"], nets={"1": "SW", "2": "CSP"}),   # Sunlord
    R("R25", "0.1R", "CSP", "RCS", L["R0R1_1206"], fp=R1206),      # 200 mV / 0.2 R = 1 A
    R("R26", "0.1R", "RCS", "+CHG", L["R0R1_1206"], fp=R1206),
    C("C7", "22u", "+CHG", "CGND", L["C22u25"], fp=C1206),            # 25 V 1206: ~10 uF left at 16.8 V DC bias
    C("C8", "22u", "+CHG", "CGND", L["C22u25"], fp=C1206),
    dict(ref="RT1", sym="Thermistor", value="NCP18XH103F03RB", fp=R0603, lcsc=L["NTC"], nets={"1": "TEMP", "2": "CGND"}),
    C("C9", "470p", "COM1", "CGND", L["C470p"]),
    R("R27", "120", "COM2", "COM2C", L["R120"]),
    C("C10", "220n", "COM2C", "CGND", L["C220n"]),
    C("C11", "100n", "COM3", "CGND", L["C100n"]),
    R("R28", "10k", "+3V3", "CHRG", L["R10k"]),          # CN3704's open-drain flags -> MCU
    R("R29", "10k", "+3V3", "DONE", L["R10k"]),
    # ---------------------------------------------------------------- relay: charger output to pack A (released) or pack B
    dict(ref="K1", sym="G6S2", value="G6S-2 DC12", fp=RELAY, lcsc=L["RELAY"],
         nets={"1": "RLY_P", "12": "RLY_K", "4": "+CHG", "3": "0V", "5": "+BATB", "9": "CGND", "10": "GND", "8": "0V"}),
    R("R86", "680", "VBUS", "RLY_P", L["R680_0805"], fp="Resistor_SMD:R_0805_2012Metric"),   # 12 V coil (1028 R) on 20 V: 11.7 mA, 12 V
    nmos2("Q19", "RELAY", "CGND", "RLY_K"),
    R("R85", "100k", "RELAY", "CGND", L["R100k"]),       # coil off while the MCU is in reset / DFU
    dict(ref="D19", sym="D", value="1N4148W", fp=SOD123, lcsc=L["D4148"], nets={"1": "RLY_P", "2": "RLY_K"}),   # flyback across the coil
    # ---------------------------------------------------------------- MCU: STM32F042F4P6, USB DFU, senses, LEDs
    dict(ref="U19", sym="STM32F042F4", value="STM32F042F4P6", fp=TSSOP20, lcsc=L["STM32"],
         nets={"1": "BOOT0", "2": "LED_DB", "3": None, "4": "NRST", "5": "+3V3", "6": "VBAT_S", "7": "VBUS_S",
               "8": "CHRG", "9": "DONE", "10": "RELAY", "11": "CHG_EN", "12": "LED_CA", "13": "LED_DA", "14": "LED_CB",
               "15": "CGND", "16": "+3V3", "17": "USB_DM", "18": "USB_DP", "19": "SWDIO", "20": "SWCLK"}),
    C("C24", "100n", "+3V3", "CGND", L["C100n"]),        # VDD
    C("C25", "100n", "+3V3", "CGND", L["C100n"]),        # VDDA
    C("C26", "100n", "NRST", "CGND", L["C100n"]),
    R("R70", "10k", "BOOT0", "CGND", L["R10k"]),
    dict(ref="SW2", sym="SW_Push", value="TS-1187A-B-A-B", fp=PUSH, lcsc=L["PUSH"], nets={"1": "BOOT0", "2": "+3V3"}),
    R("R71", "1M", "+CHG", "VBAT_S", L["R1M"]),          # 16.8 V -> 2.56 V (18.1 V OV cut -> 2.76 V); 1M: 17 uA on pack A when idle
    R("R72", "180k", "VBAT_S", "CGND", L["R180k"]),
    C("C27", "100n", "VBAT_S", "CGND", L["C100n"]),      # holds the ADC input (the divider is 150k source impedance)
    R("R73", "100k", "VBUS", "VBUS_S", L["R100k"]),      # 20 V -> 3.05 V
    R("R74", "18k", "VBUS_S", "CGND", L["R18k"]),
    led("D9", "KT-0603R", L["LEDR"], "CGND", "D9_A", fp=LED0603),      # pack A charging
    led("D10", "KT-0805G", L["LEDG"], "CGND", "D10_A"),                 # pack A done
    led("D17", "KT-0603R", L["LEDR"], "CGND", "D17_A", fp=LED0603),    # pack B charging
    led("D18", "KT-0805G", L["LEDG"], "CGND", "D18_A"),                 # pack B done
    R("R66", "1k", "LED_CA", "D9_A", L["R1k"]),
    R("R67", "470", "LED_DA", "D10_A", L["R470"]),
    R("R68", "1k", "LED_CB", "D17_A", L["R1k"]),
    R("R69", "470", "LED_DB", "D18_A", L["R470"]),
    tp("TP1", "SWDIO"), tp("TP2", "SWCLK"), tp("TP3", "CGND"), tp("TP4", "+3V3"),
    # ---------------------------------------------------------------- output and mounting
    dict(ref="J3", sym="Conn_01x04", value="S4B-PH-K-S(LF)(SN)", fp=PH4, lcsc=L["PH4"],
         nets={"1": "+OUT", "2": "0V", "3": "-V", "4": "CAB"}),
    dict(ref="H1", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H2", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H3", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H4", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H5", sym="MountingHole", value="M2.5", fp=HOLE25, lcsc="", nets={}),       # Raspberry Pi (58 x 49)
    dict(ref="H6", sym="MountingHole", value="M2.5", fp=HOLE25, lcsc="", nets={}),       # Raspberry Pi (58 x 49)
    dict(ref="H7", sym="MountingHole", value="M2.5", fp=HOLE25, lcsc="", nets={}),       # Raspberry Pi (58 x 49)
    dict(ref="H8", sym="MountingHole", value="M2.5", fp=HOLE25, lcsc="", nets={}),       # Raspberry Pi (58 x 49)
] + GAUGE_A + GAUGE_B


def balancers(cells, u0, q0, rv0, c0, rb0, tag):
    """HY2213 block per cell: U, R (100 R VDD), C, Q (AO3400A), R (100 R 1206 bleed); tag keeps the local nets apart"""
    out = []
    for n, (lo, hi) in enumerate(cells):
        bv, bg, bd = f"BV{tag}{n + 1}", f"BG{tag}{n + 1}", f"BD{tag}{n + 1}"
        out += [
            dict(ref=f"U{u0 + n}", sym="HY2213", value="HY2213-BB3A", fp=SOT23_6, lcsc=L["HY2213"],
                 nets={"2": bv, "3": lo, "6": bg, "1": None, "4": None, "5": None}),
            R(f"R{rv0 + n}", "100", hi, bv, L["R100"]),
            C(f"C{c0 + n}", "100n", bv, lo, L["C100n"]),
            nmos(f"Q{q0 + n}", bg, lo, bd),
            R(f"R{rb0 + n}", "100", hi, bd, L["R100_1206"], fp=R1206),       # 42 mA bleed, 0.18 W (pin 1 = cell +)
        ]
    return out


# pack A: U6..U9, R31..R34 (VDD), C12..C15, Q7..Q10, R35..R38 (bleed) - rev B's references; pack B: U10..U13, R58..R61,
# C16..C19, Q15..Q18, R62..R65
PARTS += balancers(CELLS_A, 6, 7, 31, 12, 35, "")
PARTS += balancers(CELLS_B, 10, 15, 58, 16, 62, "B")

BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"
