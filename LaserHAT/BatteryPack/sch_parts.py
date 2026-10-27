"""
Battery board for the LaserHAT e-stim module, rev C (2026-10-27): two hobby 4S packs (JST-XH balance leads) on one board
give +V / 0 V / -V.  Single source of truth for symbol, value, footprint, LCSC code and pin -> net; gen_schematic.py draws
it, tools/netcheck.py proves the drawn schematic matches, tools/make_bom.py writes bom_BatteryPack.csv.

Rev C: one board, two packs, one charger.  Rev B (commit 6fa6e9d) was one 4S 18650 board, two of them stacked.
  packs     pack A (-V side): J5 = GND, C1, C2, C3, +BAT;  pack B (+V side): J6 = 0V, B1, B2, B3, +BATB.  Any 4S pack
            with a JST-XH 2.5 mm 5-pin balance plug (black = pin 1 = pack negative).  Per-cell HY2213-BB3A balancers
            (42 mA through 100 R above 4.200 V, release 4.19 V) on both packs.  The XT60 discharge lead plugs into J7 / J8
            (board-mount XT60PW-M) and carries the run and charge current; XH pins 1 and 5 parallel it.
  switch    SW1 DPDT centre-off toggle RUN / OFF / CHARGE.
            Pole 1 (common 0V = pack B negative): RUN -> +BAT (the packs in series: 0V = pack A positive = output 0 V);
            CHARGE -> GND (the two negatives joined).  Pole 2 (common +BATB): RUN -> +RUN (pack B's output chain);
            CHARGE -> +CHGB -> F3 (1.1 A PTC) -> +BAT (the two positives joined: packs in parallel on the charger).
            OFF opens both; R30 1M keeps 0V at GND then.
  chain B   +RUN -> F1 (100 mA PTC) -> +SW -> Q1 (P) -> +OUT = J3.1 (+V).  U15B pulls Q1's gate low through R2 (R1
            holds it off) while VSB > THCUTB: off below 12.0 V, back on above 12.8 V (R53 from +OUT).
  chain A   GND -> F2 (100 mA PTC) -> GNDF -> Q11 (N) -> -V = J3.3.  Q11's gate: R39 from 0V (= +BAT only in RUN) and
            R40 to GND give Vgs = +BAT/2; U2B pulls it low below 12.0 V (R11 470k from the gate for hysteresis).  In OFF
            and CHARGE 0V is at GND, so Q11 is off and -V floats.  Q14 lights D1 while Q11 is on.
  gauges    one per pack, each on its own rail: +GB = +SW (RUN) or +CHGB (CHARGE) through D5 / D6; +G = 0V (RUN) or
            +CHGB (CHARGE) through D15 / D16.  CJ431 2.495 V, ladder TH80 / TH50 / TH20 / THCUT, sample divider,
            LM393 pairs, three bar LEDs + ON LED.  OFF: both rails dead (about 40 uA from the packs in all).
  charger   J1 USB-C, U4 CH224A asks the brick for 20 V (R24 120k); Q13 (P) passes VBUS to VCHG only in CHARGE (Q12's
            gate sees +CHGB), so a brick plugged in while RUN or OFF does nothing.  U5 CN3704 buck charger at 16.8 V,
            1 A total (R25 + R26 = 0.2 R) into the two packs in parallel, terminates at 92 mA, trickles below 11.2 V,
            re-charges below 16.0 V, NTC RT1 stops it hot / cold; D9 CHRG, D10 DONE.  Everything is referenced to GND.
  output    J3 (+OUT, 0V, -V, nc) to the module, same cable as rev B.
"""

R0603 = "Resistor_SMD:R_0603_1608Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
CPEL = "Capacitor_SMD:CP_Elec_6.3x5.4"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT23_6 = "Package_TO_SOT_SMD:SOT-23-6"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
TSSOP16 = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
ESSOP10 = "Package_SO:SSOP-10-1EP_3.9x4.9mm_P1mm_EP2.1x3.3mm"
LED0603 = "LED_SMD:LED_0603_1608Metric"
LED0805 = "LED_SMD:LED_0805_2012Metric"
SMA = "Diode_SMD:D_SMA"
FUSE1812 = "Fuse:Fuse_1812_4532Metric"
IND = "Inductor_SMD:L_Sunlord_MWSA0603S"
PH4 = "Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical"
XH5 = "Connector_JST:JST_XH_S5B-XH-A-1_1x05_P2.50mm_Horizontal"
XT60 = "battpack:XT60PW-M"                              # KiCad's AMASS_XT60PW-M footprint + our 3D model (battpack.3dshapes)
USBC = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
TOGGLE = "battpack:SW_MTS-203"
HOLE = "MountingHole:MountingHole_3.2mm_M3"

# LCSC codes (JLCPCB basic parts unless noted "ext"; checked 2026-10-26/27 with tools/jlc_search.py).  Values of switches,
# LEDs, connectors and other named parts are JLC's model strings (JLC's BOM matcher compares the Comment with them);
# functions are in the net names and on the silk.
L = dict(R100k="C25803", R68k="C23231", R30k="C22984", R15k="C22809", R13k="C22797", R12k="C22790",
         R10k="C25804", R6k8="C23212", R6k2="C4260", R2k="C22975", R1M="C22935", R470k="C23178", R120k="C25808",
         R120="C22787", R100="C22775", R100_1206="C17901", R0R1_1206="C25334",
         C100n="C14663", C1u50="C15849", C470p="C1620", C220n="C21120", C10u25="C15850", C22u50el="C2836438",   # el: ext
         AO3401A="C15127", AO3400A="C20917", CJ431="C3113", LM393="C7955", SS14="C2480", SS34="C8678",
         CN3704="C51659", CH224A="C42459160", HY2213="C113632", NTC="C13564",                                      # ext x4
         TOGGLE="C55160018", USBC="C165948", L22u="C408453", PH4="C131334", PTC="C12430", PTC110="C210835",      # ext x6
         XH5="C163038", XT60="C98732",                                                                                            # ext
         LEDR="C2286", LEDY="C2296", LEDG="C2297")


def R(ref, val, a, b, lcsc="", fp=R0603):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, lcsc="", fp=C0603):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def nmos(ref, g, s, d):
    return dict(ref=ref, sym="Q_NMOS_GSD", value="AO3400A", fp=SOT23, lcsc=L["AO3400A"], nets={"1": g, "2": s, "3": d})


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


CELLS_A = [("GND", "C1"), ("C1", "C2"), ("C2", "C3"), ("C3", "+BAT")]        # (negative end, positive end) of cells 1..4
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
        R(r["l1"], "6.8k", vref, th80, L["R6k8"]),           # 2.495 V -> 2.137 V = 16.0 V (pack)
        R(r["l2"], "2k", th80, th50, L["R2k"]),              # 2.029 V = 15.2 V
        R(r["l3"], "2k", th50, th20, L["R2k"]),              # 1.920 V = 14.4 V
        R(r["l4"], "6.2k", th20, thcut, L["R6k2"]),          # 1.595 V = 12.0 V (on), 12.8 V (off)
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
    xh("J5", ["GND", "C1", "C2", "C3", "+BAT"]),
    xh("J6", ["0V", "B1", "B2", "B3", "+BATB"]),
    xt60("J7", "GND", "+BAT"),
    xt60("J8", "0V", "+BATB"),
    # ---------------------------------------------------------------- toggle, link, 0V pull-down
    dict(ref="SW1", sym="SW_DPDT_CO", value="CAX-MTS203M-YB-10.6JL", fp=TOGGLE, lcsc=L["TOGGLE"],
         nets={"2": "0V", "1": "+BAT", "3": "GND", "5": "+BATB", "4": "+RUN", "6": "+CHGB"}),
    ptc("F3", "MF-MSMF110/24X-2", L["PTC110"], "+CHGB", "+BAT"),      # packs in parallel while charging; 1.1 A hold
    R("R30", "1M", "0V", "GND", L["R1M"]),                              # defines 0V while the toggle is OFF
    # ---------------------------------------------------------------- chain B: +RUN -> fuse -> Q1 -> +OUT (+V)
    ptc("F1", "MF-MSMF010-2", L["PTC"], "+RUN", "+SW"),
    pmos("Q1", "Q1_G", "+SW", "+OUT"),
    R("R1", "100k", "+SW", "Q1_G", L["R100k"]),          # gate pull-up (off)
    R("R2", "100k", "Q1_G", GB["cut"], L["R100k"]),      # with R1: Vgs = -Vsw/2 when U15B pulls low (AO3401A Vgs max 12 V)
    schottky("D5", "SS14", L["SS14"], "+GB", "+SW"),     # pack B gauge rail from the RUN side
    schottky("D6", "SS14", L["SS14"], "+GB", "+CHGB"),   # ... and from the CHARGE side
    dict(ref=GB["ub"], sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20B", "2": "VSB", "1": "LED20B", "5": "THCUTB", "6": "VSB", "7": GB["cut"], "8": "+GB", "4": "0V"}),
    led("D11", "KT-0603R", L["LEDR"], "0V", "D11_A", fp=LED0603),      # ON (+V live)
    R("R54", "13k", "+OUT", "D11_A", L["R13k"]),
    # ---------------------------------------------------------------- chain A: GND -> fuse -> Q11 -> -V
    ptc("F2", "MF-MSMF010-2", L["PTC"], "GND", "GNDF"),
    nmos("Q11", "Q11_G", "GNDF", "-V"),
    R("R39", "100k", "0V", "Q11_G", L["R100k"]),         # 0V = +BAT only in RUN
    R("R40", "100k", "Q11_G", "GND", L["R100k"]),        # Vgs = +BAT/2 (AO3400A Vgs max 12 V)
    schottky("D15", "SS14", L["SS14"], "+G", "0V"),      # pack A gauge rail from the RUN side (0V = +BAT)
    schottky("D16", "SS14", L["SS14"], "+G", "+CHGB"),   # ... and from the CHARGE side (+CHGB = +BAT - F3)
    dict(ref=GA["ub"], sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20", "2": "VS", "1": "LED20", "5": "VS", "6": "THCUT", "7": "Q11_G", "8": "+G", "4": "GND"}),
    led("D1", "KT-0603R", L["LEDR"], "D1_K", "D1_A", fp=LED0603),      # ON (-V live)
    R("R12", "13k", "+G", "D1_A", L["R13k"]),
    nmos("Q14", "Q11_G", "GND", "D1_K"),                 # lights D1 while Q11 is on, without loading -V
    # ---------------------------------------------------------------- USB-C PD input, VBUS switch, CN3704 charger (all on GND)
    dict(ref="J1", sym="USB_C_16P", value="TYPE-C-31-M-12", fp=USBC, lcsc=L["USBC"],
         nets={"A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2",
               "A6": "DP", "B6": "DP", "A7": "DM", "B7": "DM", "A8": None, "B8": None,
               "A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "S1": "GND"}),
    dict(ref="U4", sym="CH224A", value="CH224A", fp=ESSOP10, lcsc=L["CH224A"],
         nets={"1": "VBUS", "8": "VBUS", "7": "CC1", "6": "CC2", "4": "DP", "5": "DM", "9": "CFG1",
               "2": None, "3": None, "10": None, "11": "GND"}),
    C("C3", "1u", "VBUS", "GND", L["C1u50"]),            # 50 V
    R("R24", "120k", "CFG1", "GND", L["R120k"]),         # single-resistor configuration: 20 V
    pmos("Q13", "Q13_G", "VBUS", "VCHG"),                # VBUS reaches the charger only in CHARGE
    R("R43", "100k", "VBUS", "Q13_G", L["R100k"]),
    R("R44", "100k", "Q13_G", "Q13_GD", L["R100k"]),     # Vgs(Q13) = -VBUS/2 = -10 V
    nmos("Q12", "Q12_G", "GND", "Q13_GD"),
    R("R41", "100k", "+CHGB", "Q12_G", L["R100k"]),      # +CHGB = +BAT in CHARGE, pulled to GND otherwise
    R("R42", "100k", "Q12_G", "GND", L["R100k"]),
    dict(ref="U5", sym="CN3704", value="CN3704", fp=TSSOP16, lcsc=L["CN3704"],
         nets={"15": "VCHG", "1": "VG", "16": "DRV", "4": "CHRG", "5": "DONE", "6": "TEMP", "7": "GND", "8": "COM1",
               "9": "COM2", "10": "GND", "11": "COM3", "12": None, "13": "CSP", "14": "+BAT", "2": "GND", "3": "GND"}),
    C("C4", "100n", "VG", "VCHG", L["C100n"]),
    dict(ref="C5", sym="CP", value="22u 50V", fp=CPEL, lcsc=L["C22u50el"], nets={"1": "VCHG", "2": "GND"}),
    C("C6", "1u", "VCHG", "GND", L["C1u50"]),
    pmos("Q6", "DRV", "VCHG", "SWA"),                    # buck switch
    schottky("D7", "SS34", L["SS34"], "SW", "SWA"),      # blocks battery -> input through Q6's body diode
    schottky("D8", "SS34", L["SS34"], "SW", "GND"),      # freewheel
    dict(ref="L1", sym="L", value="MWSA0603S-220MT", fp=IND, lcsc=L["L22u"], nets={"1": "SW", "2": "CSP"}),   # Sunlord
    R("R25", "0.1R", "CSP", "RCS", L["R0R1_1206"], fp=R1206),      # 200 mV / 0.2 R = 1 A
    R("R26", "0.1R", "RCS", "+BAT", L["R0R1_1206"], fp=R1206),
    C("C7", "10u", "+BAT", "GND", L["C10u25"], fp=C0805),
    C("C8", "10u", "+BAT", "GND", L["C10u25"], fp=C0805),
    dict(ref="RT1", sym="Thermistor", value="NCP18XH103F03RB", fp=R0603, lcsc=L["NTC"], nets={"1": "TEMP", "2": "GND"}),
    C("C9", "470p", "COM1", "GND", L["C470p"]),
    R("R27", "120", "COM2", "COM2C", L["R120"]),
    C("C10", "220n", "COM2C", "GND", L["C220n"]),
    C("C11", "100n", "COM3", "GND", L["C100n"]),
    led("D9", "KT-0603R", L["LEDR"], "CHRG", "D9_A", fp=LED0603),
    led("D10", "KT-0805G", L["LEDG"], "DONE", "D10_A"),
    R("R28", "15k", "VCHG", "D9_A", L["R15k"]),
    R("R29", "15k", "VCHG", "D10_A", L["R15k"]),
    # ---------------------------------------------------------------- output and mounting
    dict(ref="J3", sym="Conn_01x04", value="B4B-PH-K-S(LF)(SN)", fp=PH4, lcsc=L["PH4"],
         nets={"1": "+OUT", "2": "0V", "3": "-V", "4": None}),
    dict(ref="H1", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H2", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H3", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H4", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
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
