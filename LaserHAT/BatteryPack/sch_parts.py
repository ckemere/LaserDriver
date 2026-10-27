"""
4S 18650 battery pack board for the LaserHAT e-stim module (two identical boards stacked give +V / 0 V / -V).
Single source of truth for symbol, value, footprint, LCSC code and pin -> net; gen_schematic.py draws it,
tools/netcheck.py proves the drawn schematic matches, tools/make_bom.py writes bom_BatteryPack.csv.

Rev B (2026-10-26): on-board USB-C PD charger, per-cell balancers, RUN / OFF / CHARGE toggle, stack slave enable.
  cells     four 18650 in series between GND (B-) and +BAT, taps C1..C3; each cell sits in two MYOUNG MY-18650-01 clips.
  balance   one HY2213-BB3A per cell bleeds 42 mA (100 R) through an AO3400A above 4.200 V, releases at 4.19 V.
  switch    SW1 DPDT centre-off toggle.  Pole 1 (common +BAT): RUN -> +RUN, CHARGE -> +CHG.  Pole 2 (common GND):
            RUN -> OUT_GND (J3.2), CHARGE -> CGND (the USB-C ground and the charger's return).  OFF opens both.
            +RUN -> F1 (100 mA PTC) -> +SW -> Q1 -> +OUT.  The gauge rail +G is +SW or +CHG through D5 / D6 (SS14).
  cutoff    U2B compares the scaled rail (VS) with THCUT and pulls Q1's gate low through R2 (R1 holds it off);
            R11 from +OUT gives hysteresis: off below 12.0 V, back on above 12.8 V.
  slave     the stack cable's 4th wire (J4.4 = this board's +RUN, J3.4 = STACK_IN on the board below) lets the upper
            board's toggle run the lower board: Q2 sees STACK_IN against +OUT (= the upper GND), sources into Q3's
            gate, Q3 pulls Q4's gate down and Q4 feeds +RUN from +BAT.  Q5 blocks it while +CHG is live.
  gauge     U3 CJ431 2.495 V (R3), ladder R4..R8 taps TH80 / TH50 / TH20 / THCUT; sample divider R9 / R10 on +G
            (+R11).  U1A / U1B / U2A light D4 / D3 / D2 above 16.0 / 15.2 / 14.4 V; D1 is on whenever +OUT is live.
  charger   J1 USB-C, U4 CH224A asks the brick for 20 V (R24 120k on CFG1); U5 CN3704 buck charger at 16.8 V,
            1 A (R25 + R26 = 0.2 R), terminates at 92 mA, trickles below 11.2 V, re-charges below 16.0 V,
            NTC RT1 stops it hot/cold; D9 CHRG, D10 DONE.  All of it is referenced to CGND, which only touches GND
            in the CHARGE position (R30 1M keeps it defined otherwise).
  output    J3 (+OUT, OUT_GND, LINK_N, STACK_IN) is the pack output / stack-down link; J4 (GND, LINK_N, NC, +RUN)
            takes the lower board's J3 through a straight 4-wire cable: lower +OUT -> this GND (= 0 V), lower
            OUT_GND -> LINK_N -> J3.3 (= -V), this +RUN -> lower STACK_IN.
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
USBC = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
CLIP = "battpack:Clip_MY-18650-01"
TOGGLE = "battpack:SW_MTS-203"
HOLE = "MountingHole:MountingHole_3.2mm_M3"

# LCSC codes (JLCPCB basic parts unless noted "ext"; checked 2026-10-26 with tools/jlc_search.py).  Values of switches, LEDs,
# connectors and other named parts are JLC's model strings (JLC's BOM matcher compares the Comment with them); functions are
# in the net names and on the silk.
L = dict(R100k="C25803", R68k="C23231", R33k="C4216", R30k="C22984", R15k="C22809", R13k="C22797", R12k="C22790",
         R10k="C25804", R6k8="C23212", R6k2="C4260", R2k="C22975", R1M="C22935", R120k="C25808", R120="C22787",
         R100="C22775", R100_1206="C17901", R0R1_1206="C25334",
         C100n="C14663", C1u50="C15849", C470p="C1620", C220n="C21120", C10u25="C15850", C22u50el="C2836438",   # el: ext
         AO3401A="C15127", AO3400A="C20917", CJ431="C3113", LM393="C7955", SS14="C2480", SS34="C8678",
         CN3704="C51659", CH224A="C42459160", HY2213="C113632", NTC="C13564",                                      # ext x4
         TOGGLE="C55160018", USBC="C165948", L22u="C408453", PH4="C131334", PTC="C12430", CLIP="C2979183",        # ext x6
         LEDR="C2286", LEDY="C2296", LEDG="C2297")


def R(ref, val, a, b, lcsc="", fp=R0603):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, lcsc="", fp=C0603):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def clip(ref, net):
    return dict(ref=ref, sym="Clip18650", value="MY-18650-01", fp=CLIP, lcsc=L["CLIP"], nets={"1": net})


def nmos(ref, g, s, d):
    return dict(ref=ref, sym="Q_NMOS_GSD", value="AO3400A", fp=SOT23, lcsc=L["AO3400A"], nets={"1": g, "2": s, "3": d})


def pmos(ref, g, s, d):
    return dict(ref=ref, sym="Q_PMOS_GSD", value="AO3401A", fp=SOT23, lcsc=L["AO3401A"], nets={"1": g, "2": s, "3": d})


def led(ref, val, lcsc, k, a, fp=LED0805):
    return dict(ref=ref, sym="LED", value=val, fp=fp, lcsc=lcsc, nets={"1": k, "2": a})


def schottky(ref, val, lcsc, k, a):
    return dict(ref=ref, sym="D_Schottky", value=val, fp=SMA, lcsc=lcsc, nets={"1": k, "2": a})


CELLS = [("GND", "C1"), ("C1", "C2"), ("C2", "C3"), ("C3", "+BAT")]      # (negative end, positive end) of cells 1..4

PARTS = [
    # ---------------------------------------------------------------- cells: BC(2n-1) = cell n negative end, BC(2n) = positive end
    clip("BC1", "GND"), clip("BC2", "C1"),
    clip("BC3", "C1"), clip("BC4", "C2"),
    clip("BC5", "C2"), clip("BC6", "C3"),
    clip("BC7", "C3"), clip("BC8", "+BAT"),
    # ---------------------------------------------------------------- switch, fuse, under-voltage cutoff
    dict(ref="SW1", sym="SW_DPDT_CO", value="CAX-MTS203M-YB-10.6JL", fp=TOGGLE, lcsc=L["TOGGLE"],
         nets={"2": "+BAT", "1": "+RUN", "3": "+CHG", "5": "GND", "4": "OUT_GND", "6": "CGND"}),
    dict(ref="F1", sym="Polyfuse", value="MF-MSMF010-2", fp=FUSE1812, lcsc=L["PTC"], nets={"1": "+RUN", "2": "+SW"}),   # Bourns MF-MSMF010-2
    pmos("Q1", "Q1_G", "+SW", "+OUT"),
    R("R1", "100k", "+SW", "Q1_G", L["R100k"]),          # gate pull-up (off)
    R("R2", "100k", "Q1_G", "CUT_OC", L["R100k"]),       # with R1: Vgs = -Vsw/2 when U2B pulls low (AO3401A Vgs max 12 V)
    schottky("D5", "SS14", L["SS14"], "+G", "+SW"),      # gauge rail from the RUN side
    schottky("D6", "SS14", L["SS14"], "+G", "+CHG"),     # ... and from the CHARGE side
    # ---------------------------------------------------------------- stack slave enable (upper board's +RUN arrives on J3.4)
    pmos("Q2", "Q2_G", "STACK_IN", "EN_SRC"),            # on when STACK_IN is above +OUT (= the upper board's GND)
    R("R16", "100k", "STACK_IN", "Q2_G", L["R100k"]),
    R("R17", "100k", "Q2_G", "+OUT", L["R100k"]),        # Vgs(Q2) = -(upper pack)/2
    R("R18", "100k", "EN_SRC", "EN_G", L["R100k"]),
    R("R19", "33k", "EN_G", "GND", L["R33k"]),           # Vgs(Q3) = stack / 4, 3..8.4 V
    nmos("Q3", "EN_G", "GND", "Q4_GD"),
    R("R20", "100k", "+BAT", "Q4_G", L["R100k"]),
    R("R21", "100k", "Q4_G", "Q4_GD", L["R100k"]),       # Vgs(Q4) = -Vbat/2
    pmos("Q4", "Q4_G", "+BAT", "+RUN"),                  # feeds +RUN in place of the toggle
    nmos("Q5", "Q5_G", "GND", "EN_G"),                   # blocks the slave path in CHARGE
    R("R22", "100k", "+CHG", "Q5_G", L["R100k"]),
    R("R23", "100k", "Q5_G", "GND", L["R100k"]),
    # ---------------------------------------------------------------- reference, ladder, sample divider (on +G = +BAT - 0.25 V)
    dict(ref="U3", sym="TL431_SOT23", value="CJ431", fp=SOT23, lcsc=L["CJ431"], nets={"1": "VREF", "2": "VREF", "3": "GND"}),
    R("R3", "6.8k", "+G", "VREF", L["R6k8"]),            # >= 1.3 mA into the CJ431 at 12 V (min 1 mA)
    R("R4", "6.8k", "VREF", "TH80", L["R6k8"]),          # 2.495 V -> 2.137 V = 16.0 V (pack)
    R("R5", "2k", "TH80", "TH50", L["R2k"]),             # 2.029 V = 15.2 V
    R("R6", "2k", "TH50", "TH20", L["R2k"]),             # 1.920 V = 14.4 V
    R("R7", "6.2k", "TH20", "THCUT", L["R6k2"]),         # 1.595 V = 12.0 V (on), 12.8 V (off)
    R("R8", "30k", "THCUT", "GND", L["R30k"]),
    R("R9", "68k", "+G", "VS", L["R68k"]),               # VS = +G x 0.1357 with +OUT live (R11), x 0.1271 when cut off
    R("R10", "10k", "VS", "GND", L["R10k"]),
    R("R11", "1M", "+OUT", "VS", L["R1M"]),              # cutoff hysteresis
    # ---------------------------------------------------------------- comparators (open collector) and LEDs
    dict(ref="U1", sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH80", "2": "VS", "1": "LED80", "5": "TH50", "6": "VS", "7": "LED50", "8": "+G", "4": "GND"}),
    dict(ref="U2", sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20", "2": "VS", "1": "LED20", "5": "THCUT", "6": "VS", "7": "CUT_OC", "8": "+G", "4": "GND"}),
    C("C1", "100n", "+G", "GND", L["C100n"]),
    C("C2", "100n", "+G", "GND", L["C100n"]),
    led("D1", "KT-0603R", L["LEDR"], "GND", "D1_A", fp=LED0603),          # KT-0603R
    led("D2", "KT-0805Y", L["LEDY"], "LED20", "D2_A"),              # KT-0805Y
    led("D3", "KT-0805G", L["LEDG"], "LED50", "D3_A"),               # KT-0805G
    led("D4", "KT-0805G", L["LEDG"], "LED80", "D4_A"),
    R("R12", "13k", "+OUT", "D1_A", L["R13k"]),          # ~1 mA at 15 V (red Vf 2 V)
    R("R13", "13k", "+G", "D2_A", L["R13k"]),
    R("R14", "12k", "+G", "D3_A", L["R12k"]),            # green Vf ~2.8 V
    R("R15", "12k", "+G", "D4_A", L["R12k"]),
    # ---------------------------------------------------------------- USB-C PD input and CN3704 charger (all on CGND)
    dict(ref="J1", sym="USB_C_16P", value="TYPE-C-31-M-12", fp=USBC, lcsc=L["USBC"],
         nets={"A4": "VBUS", "B4": "VBUS", "A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2",
               "A6": "DP", "B6": "DP", "A7": "DM", "B7": "DM", "A8": None, "B8": None,
               "A1": "CGND", "B1": "CGND", "A12": "CGND", "B12": "CGND", "S1": "CGND"}),
    dict(ref="U4", sym="CH224A", value="CH224A", fp=ESSOP10, lcsc=L["CH224A"],
         nets={"1": "VBUS", "8": "VBUS", "7": "CC1", "6": "CC2", "4": "DP", "5": "DM", "9": "CFG1",
               "2": None, "3": None, "10": None, "11": "CGND"}),
    C("C3", "1u", "VBUS", "CGND", L["C1u50"]),           # 50 V
    R("R24", "120k", "CFG1", "CGND", L["R120k"]),        # single-resistor configuration: 20 V
    dict(ref="U5", sym="CN3704", value="CN3704", fp=TSSOP16, lcsc=L["CN3704"],
         nets={"15": "VBUS", "1": "VG", "16": "DRV", "4": "CHRG", "5": "DONE", "6": "TEMP", "7": "CGND", "8": "COM1",
               "9": "COM2", "10": "CGND", "11": "COM3", "12": None, "13": "CSP", "14": "+BAT", "2": "CGND", "3": "CGND"}),
    C("C4", "100n", "VG", "VBUS", L["C100n"]),
    dict(ref="C5", sym="CP", value="22u 50V", fp=CPEL, lcsc=L["C22u50el"], nets={"1": "VBUS", "2": "CGND"}),
    C("C6", "1u", "VBUS", "CGND", L["C1u50"]),
    pmos("Q6", "DRV", "VBUS", "SWA"),                    # buck switch
    schottky("D7", "SS34", L["SS34"], "SW", "SWA"),      # blocks battery -> input through Q6's body diode
    schottky("D8", "SS34", L["SS34"], "SW", "CGND"),     # freewheel
    dict(ref="L1", sym="L", value="MWSA0603S-220MT", fp=IND, lcsc=L["L22u"], nets={"1": "SW", "2": "CSP"}),   # Sunlord MWSA0603S-220MT
    R("R25", "0.1R", "CSP", "RCS", L["R0R1_1206"], fp=R1206),      # 200 mV / 0.2 R = 1 A
    R("R26", "0.1R", "RCS", "+BAT", L["R0R1_1206"], fp=R1206),
    C("C7", "10u", "+BAT", "CGND", L["C10u25"], fp=C0805),
    C("C8", "10u", "+BAT", "CGND", L["C10u25"], fp=C0805),
    dict(ref="RT1", sym="Thermistor", value="NCP18XH103F03RB", fp=R0603, lcsc=L["NTC"], nets={"1": "TEMP", "2": "CGND"}),   # NCP18XH103F03RB
    C("C9", "470p", "COM1", "CGND", L["C470p"]),
    R("R27", "120", "COM2", "COM2C", L["R120"]),
    C("C10", "220n", "COM2C", "CGND", L["C220n"]),
    C("C11", "100n", "COM3", "CGND", L["C100n"]),
    led("D9", "KT-0603R", L["LEDR"], "CHRG", "D9_A", fp=LED0603),
    led("D10", "KT-0805G", L["LEDG"], "DONE", "D10_A"),
    R("R28", "15k", "VBUS", "D9_A", L["R15k"]),
    R("R29", "15k", "VBUS", "D10_A", L["R15k"]),
    R("R30", "1M", "CGND", "GND", L["R1M"]),             # defines CGND while the toggle is not in CHARGE
    # ---------------------------------------------------------------- output and stacking
    dict(ref="J3", sym="Conn_01x04", value="B4B-PH-K-S(LF)(SN)", fp=PH4, lcsc=L["PH4"],
         nets={"1": "+OUT", "2": "OUT_GND", "3": "LINK_N", "4": "STACK_IN"}),
    dict(ref="J4", sym="Conn_01x04", value="B4B-PH-K-S(LF)(SN)", fp=PH4, lcsc=L["PH4"],
         nets={"1": "GND", "2": "LINK_N", "3": None, "4": "+RUN"}),
    dict(ref="H1", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H2", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H3", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
    dict(ref="H4", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),
]
# ---------------------------------------------------------------- per-cell balancers: U6..U9, R31..R34 (100 R VDD), C12..C15, Q7..Q10, R35..R38 (100 R bleed)
for n, (lo, hi) in enumerate(CELLS, start=1):
    PARTS += [
        dict(ref=f"U{5 + n}", sym="HY2213", value="HY2213-BB3A", fp=SOT23_6, lcsc=L["HY2213"],
             nets={"2": f"BV{n}", "3": lo, "6": f"BG{n}", "1": None, "4": None, "5": None}),
        R(f"R{30 + n}", "100", hi, f"BV{n}", L["R100"]),
        C(f"C{11 + n}", "100n", f"BV{n}", lo, L["C100n"]),
        nmos(f"Q{6 + n}", f"BG{n}", lo, f"BD{n}"),
        R(f"R{34 + n}", "100", hi, f"BD{n}", L["R100_1206"], fp=R1206),       # 42 mA bleed, 0.18 W (pin 1 = cell +)
    ]

BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"
