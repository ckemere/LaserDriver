"""
SimpleBatteryPack (2026-10-31): the BatteryPack (rev E) with the charging infrastructure cut out.  Two hobby 4S packs,
permanently in series, give +V / 0 V / -V to the LaserHAT e-stim module; they are charged off the board on an ordinary
hobby balance charger (unplug the XT60).  Single source of truth for symbol, value, footprint, LCSC code and pin -> net;
gen_schematic.py draws it, tools/netcheck.py proves the drawn schematic matches, tools/make_bom.py writes
bom_SimpleBatteryPack.csv.

Cut from BatteryPack: the USB-C PD charger island (J1, CH224A, LDO, VBUS switch, CN3704 buck), the relays K1 / K2 and
their drivers, the STM32 charge controller with its CHG / DONE LEDs, BOOT button and SWD pads, the charging interlock
opto U17, and the per-cell balancers with their JST-XH balance sockets (they only bleed above 4.2 V a cell, i.e. while
charging; the hobby charger balances).  Everything else is BatteryPack's, references kept:
  packs     pack A (-V side): GND .. 0V on J7 (XT60);  pack B (+V side): 0V .. +BATB on J8.  0V = pack A positive =
            pack B negative = the output reference, always.
  switch    SW1 DPDT ON-ON toggle (MTS-202) = ON / OFF.  Pole 1 (common EN_A): ON -> 0V.  Pole 2 (common EN_B): ON -> +BATB.
            OFF opens both (R40 holds EN_A's divider at GND, R82 holds EN_B at 0V): outputs off, gauges dark.
  chain B   +BATB -> F1 (100 mA PTC) -> +SW -> Q1 (P) -> +OUT = J3.1 (+V).  Q22 (2N7002) pulls Q1's gate low through R2
            (R1 holds it off) while its gate ENB_G is high: ENB_G = EN_B through R81 1M, pulled to 0V by U15B below 12.0 V
            (back above 12.8 V, R53 from +OUT).  Q22's source is J3.4 (CAB), which is at 0V only through the strap
            (pin 4 to pin 2) at the module end of the cable: +V can only appear when 0V reaches the module.
  chain A   GND -> F2 (100 mA PTC) -> GNDF -> Q11 (N) -> -V = J3.3.  Q11's gate: R39 from EN_AI and R40 to GND give
            Vgs = pack A / 2; U2B pulls it low below 12.0 V (R11 470k from the gate: back on at 12.9 V).  Interlocked like
            +V (2026-10-31): EN_AI = CAB through Q26 (P), whose gate is Q20_G (pack A / 2 below 0V while the toggle is ON,
            0V when OFF), so Q11 gets gate drive only with the toggle ON and CAB strapped to 0V.  Q14 lights D1 while
            Q11 is on.
  gauges    one per pack, each on its own rail through a P-FET: +G = 0V through Q20 (Q21 from EN_A's divider),
            +GB = +BATB through Q23 (Q24 from EN_B).  CJ431 2.495 V, ladder TH80 / TH50 / TH20 / THCUT, sample divider,
            LM393 pairs, three bar LEDs + ON LED.
  output    J3 (+OUT, 0V, -V, CAB) to the module, a side-entry PH socket opening over the top edge; pin 4 strapped to
            pin 2 in the plug.
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
         R1k="C21190", R470="C23179", R680_0805="C17798", R680_1206="C17975", C10n="C57112", R180k="C22827", R120="C22787", R100="C22775", R100_1206="C17901", R0R1_1206="C25334",
         C100n="C14663", C1u50="C15849", C470p="C1620", C220n="C21120", C22u25="C12891", C22u50el="C2836438",   # el: ext
         AO3401A="C15127", AO3400A="C20917", N7002="C8545", CJ431="C3113", LM393="C7955", SS14="C2480", SS34="C8678",
         D4148="C81598", CN3704="C51659", CH224A="C42459160", HY2213="C113632", NTC="C13564",                   # ext x4
         STM32="C81002", RELAY="C1525289", OPTO="C2912100", LDO="C2683368",                                      # ext x4
         TOGGLE="C55159891", USBC="C165948", L33u="C408454", PH4="C157926", PTC="C12430",                       # ext x5
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
    # ---------------------------------------------------------------- packs (XT60 discharge plugs only)
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
    R("R81", "1M", "EN_B", "ENB_G", L["R1M"]),           # ENB_G = +BATB when ON unless U15B pulls it to 0V
    dict(ref=GB["ub"], sym="LM393", value="LM393DR2G", fp=SOIC8, lcsc=L["LM393"],
         nets={"3": "TH20B", "2": "VSB", "1": "LED20B", "5": "VSB", "6": "THCUTB", "7": "ENB_G", "8": "+GB", "4": "0V"}),
    led("D11", "KT-0603R", L["LEDR"], "0V", "D11_A", fp=LED0603),      # ON (+V live)
    R("R54", "13k", "+OUT", "D11_A", L["R13k"]),
    # ---------------------------------------------------------------- chain A: GND -> fuse -> Q11 -> -V
    ptc("F2", "MF-MSMF010-2", L["PTC"], "GND", "GNDF"),
    nmos("Q11", "Q11_G", "GNDF", "-V"),
    R("R39", "100k", "EN_AI", "Q11_G", L["R100k"]),      # EN_AI = CAB (0V through the strap) only when ON
    pmos("Q26", "Q20_G", "CAB", "EN_AI"),               # -V interlock: Vgs = -pack A / 2 while ON (AO3401A Vgs max 12 V)
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
    dict(ref="H9", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),           # case: centre line between the packs
    dict(ref="H10", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),          # case: centre line between the packs
    dict(ref="H11", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),          # case: middle of the left edge
    dict(ref="H12", sym="MountingHole", value="M3", fp=HOLE, lcsc="", nets={}),          # case: middle of the right edge
    # the owl (board art, not in BOM / CPL), its exposed copper on 0V
    dict(ref="G1", sym="Logo", value="OwlLogo", fp="Footprints:OwlLogo_Eyes_14mm_R", lcsc="", nets={"1": "0V"}),
] + GAUGE_A + GAUGE_B


BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"
