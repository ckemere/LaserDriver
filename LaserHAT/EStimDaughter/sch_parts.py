"""
kbest e-stim module (LaserHAT Rev 2 plug-in), rev M1: single source of truth for symbol, value, footprint, LCSC and
pin -> net.  Circuit = kbest rev E output stage, powered from the HAT's +5 V through an isolated +/-15 V DC-DC,
controlled over the J8/J9 headers (ESTIM_MODULE_SPEC.md + QUESTIONS.md Q1-Q4):
  J8: 1 GND_H, 2 +5V_H, 3 PWM_A = EN, 4 PWM_B = CATH, 5 GPIO = FAULT_n (module -> HAT, TIMA0_FAULT0)
  J9: 1 GND_H, 2 +3V3_H, 3 "DAC" = CS_n, 4 "ADC_A" = SCK, 5 "ADC_B" = MOSI   (bit-banged SPI to the MCP4921)
"""

R0402, R0603, R0805 = "Resistor_SMD:R_0402_1005Metric", "Resistor_SMD:R_0603_1608Metric", "Resistor_SMD:R_0805_2012Metric"
C0402, C0603, C0805 = "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric"
SOT23, SOD323 = "Package_TO_SOT_SMD:SOT-23", "Diode_SMD:D_SOD-323"
VSSOP8 = "Package_SO:VSSOP-8_3x3mm_P0.65mm"
HDR5 = "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"
HDR2RA = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal"
TP = "TestPoint:TestPoint_Pad_D1.0mm"

# LCSC
L100k, L10k, L1k, L47, L2k2, L22k, L12k, L27k, L110k, L4k7 = ("C25741", "C25744", "C11702", "C137973", "C25879", "C25768",
                                                              "C25752", "C22369538", "C2909311", "C25900")
L100n, L100n50, L100p, L10n, L2n2 = "C1525", "C14663", "C1546", "C15195", "C106861"
L1u50, L4u7, L1u50_0805 = "C559769", "C69335", "C726584"


def R(ref, val, a, b, fp=R0402, lcsc=""):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, fp=C0402, lcsc=""):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


PARTS = [
    # ---------------------------------------------------------------- HAT side (non-isolated)
    dict(ref="J8", sym="Conn_01x05", value="J8 power/timing (underside)", fp=HDR5, lcsc="",
         nets={"1": "GND_H", "2": "+5V_H", "3": "EN_H", "4": "CATH_H", "5": "FAULT_H"}),
    dict(ref="J9", sym="Conn_01x05", value="J9 analog/SPI (underside)", fp=HDR5, lcsc="",
         nets={"1": "GND_H", "2": "+3V3_H", "3": "CS_H", "4": "SCK_H", "5": "MOSI_H"}),
    # safe defaults while the MCU pins are Hi-Z (Q1/Q3): EN/CATH/SCK/MOSI pulled low, CS_n pulled high
    R("R1", "100k", "EN_H", "GND_H", lcsc=L100k),
    R("R2", "100k", "CATH_H", "GND_H", lcsc=L100k),
    R("R3", "100k", "+3V3_H", "CS_H", lcsc=L100k),
    R("R4", "100k", "SCK_H", "GND_H", lcsc=L100k),
    R("R5", "100k", "MOSI_H", "GND_H", lcsc=L100k),
    dict(ref="U1", sym="ISO7761", value="ISO7761FDBQR", fp="Package_SO:SSOP-16_3.9x4.9mm_P0.635mm", lcsc="C2877505",
         # channels assigned for layout (A MOSI, B CS, C SCK, D CATH, E EN); any forward channel will do
         nets={"1": "+3V3_H", "2": "MOSI_H", "3": "CS_H", "4": "SCK_H", "5": "CATH_H", "6": "EN_H", "7": "FAULT_H", "8": "GND_H",
               "9": "GND_ISO", "10": "FAULT_n", "11": "EN", "12": "CATH", "13": "SCK", "14": "CS_n", "15": "MOSI", "16": "+5V_ISO"}),
    C("C1", "100n", "+3V3_H", "GND_H", lcsc=L100n),
    C("C2", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),
    # ---------------------------------------------------------------- isolated +/-15 V, +5 V, -5 V
    # DNP: fitted by hand - A0515S-1WR3 (Mornsun), RECOM RB-0515D/HP (verified pin-compatible) or the YLPTEC clone (LCSC C5369388), in a SIP
    # socket or soldered; or leave empty and feed pins 6 / 5 / 4 = +V / 0V / -V from two battery packs (<= +/-18 V).
    dict(ref="PS1", sym="A0515S", value="A0515S-1WR3", fp="estim:DCDC_SIP6_A0515S", lcsc="", dnp=True,
         nets={"1": "+5V_H", "2": "GND_H", "6": "+V_STIM", "5": "GND_ISO", "4": "-V_STIM"}),
    C("C3", "4.7u", "+5V_H", "GND_H", fp=C0603, lcsc=L4u7),
    C("C4", "1u 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L1u50),
    C("C5", "1u 50V", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L1u50),
    dict(ref="U2", sym="TLV760", value="TLV76050DBZR", fp=SOT23, lcsc="C2867465",
         nets={"2": "+V_STIM", "1": "+5V_ISO", "3": "GND_ISO"}),
    C("C6", "1u 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L1u50),
    C("C7", "1u 50V", "+5V_ISO", "GND_ISO", fp=C0603, lcsc=L1u50),
    R("R6", "1.5k", "-5V_ISO", "-V_STIM", fp=R0603, lcsc="C22843"),
    dict(ref="D1", sym="D_Zener", value="BZT52C4V7S", fp=SOD323, lcsc="C19077439", nets={"1": "GND_ISO", "2": "-5V_ISO"}),
    C("C8", "1u 50V", "GND_ISO", "-5V_ISO", fp=C0603, lcsc=L1u50),
    # ---------------------------------------------------------------- set-point: TL431 -> /2.5 -> MCP4921 VREF
    R("R7", "1.5k", "+5V_ISO", "VREF_2V5", fp=R0603, lcsc="C22843"),
    dict(ref="U3", sym="TL431_SOT23", value="TL431 (2.5V)", fp=SOT23, lcsc="C181103",
         nets={"1": "VREF_2V5", "2": "VREF_2V5", "3": "GND_ISO"}),
    R("R8", "15.0k 0.1%", "VREF_2V5", "VREF_DAC", fp=R0603, lcsc="C326733"),
    R("R9", "10.0k 0.1%", "VREF_DAC", "GND_ISO", fp=R0603, lcsc="C95204"),
    C("C9", "10n", "VREF_DAC", "GND_ISO", lcsc=L10n),
    dict(ref="U4", sym="MCP4921", value="MCP4921-E/MS", fp="Package_SO:MSOP-8_3x3mm_P0.65mm", lcsc="C185506",
         nets={"1": "+5V_ISO", "2": "CS_n", "3": "SCK", "4": "MOSI", "5": "GND_ISO", "6": "VREF_DAC", "7": "GND_ISO", "8": "VSET_P"}),
    C("C10", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),
    # ---------------------------------------------------------------- U5: OPA2192 (A = V->I output stage, B = -VSET inverter)
    dict(ref="U5", sym="OPA2192", value="OPA2192IDGKR", fp=VSSOP8, lcsc="C2876419",
         nets={"3": "OA_IN", "2": "ISENSE", "1": "OA_OUT", "5": "GND_ISO", "6": "U5B_IN", "7": "VSET_N", "8": "+V_STIM", "4": "-V_STIM"}),
    C("C11", "100n", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L100n50),
    C("C12", "100n", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L100n50),
    R("R10", "10.0k 0.1%", "VSET_P", "U5B_IN", fp=R0603, lcsc="C95204"),
    R("R11", "10.0k 0.1%", "U5B_IN", "VSET_N", fp=R0603, lcsc="C95204"),
    # ---------------------------------------------------------------- U6: 74HC4053 (S1 = CATH picks -/+VSET, S2 = EN picks that or 0)
    # M3: DHVQFN-16 (2.5 x 3.5 mm) instead of TSSOP-16, same pinout; the centre pad is not a supply pin (float or VCC) and is left open
    dict(ref="U6", sym="74HC4053", value="74HC4053BQ", fp="Package_DFN_QFN:DHVQFN-16-1EP_2.5x3.5mm_P0.5mm_EP1x2mm", lcsc="C547007",
         nets={"12": "VSET_P", "13": "VSET_N", "14": "SW_P", "2": "GND_ISO", "1": "SW_P", "15": "V_IN", "5": "GND_ISO",
               "3": "GND_ISO", "4": "GND_ISO", "11": "CATH", "10": "EN", "9": "GND_ISO", "6": "GND_ISO", "8": "GND_ISO",
               "7": "-5V_ISO", "16": "+5V_ISO"}),
    C("C13", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),
    C("C14", "100n", "GND_ISO", "-5V_ISO", lcsc=L100n),
    # ---------------------------------------------------------------- output stage
    R("R12", "1k", "V_IN", "OA_IN", lcsc=L1k),
    C("C15", "100p", "OA_IN", "GND_ISO", lcsc=L100p),
    R("R13", "47", "OA_OUT", "E1", lcsc=L47),
    R("R14", "2.00k 0.1%", "ISENSE", "GND_ISO", fp=R0603, lcsc="C328425"),
    C("C16", "1u 50V", "E1", "E1_OUT", fp=C0805, lcsc=L1u50_0805),
    dict(ref="J1", sym="Conn_01x02", value="ELECTRODE E1/E2", fp=HDR2RA, lcsc="", nets={"1": "E1_OUT", "2": "ISENSE"}),
    dict(ref="TP1", sym="TestPoint", value="ISENSE", fp=TP, lcsc="", nets={"1": "ISENSE"}),
    dict(ref="TP2", sym="TestPoint", value="GND_ISO", fp=TP, lcsc="", nets={"1": "GND_ISO"}),
    # ---------------------------------------------------------------- SHORT switch (DG419, throw 1 = on while IN low) + hold timer
    # HOLD stays high while EN or CATH is high and ~200 us after (R15*C17); then the switch shorts E1 to E2 (ISENSE).
    dict(ref="D2", sym="BAT54C", value="BAT54C", fp=SOT23, lcsc="C37704", nets={"1": "EN", "2": "CATH", "3": "HOLD"}),
    R("R15", "100k", "HOLD", "GND_ISO", lcsc=L100k),
    C("C17", "2.2n", "HOLD", "GND_ISO", lcsc=L2n2),
    # M3: DG419B in MSOP-8 (15 ohm, 38 pC injection, 12 pF off-capacitance) instead of the DG419DY SOIC-8 (20 ohm, 60 pC, 8 pF)
    dict(ref="U7", sym="DG419", value="DG419BDQ", fp="Package_SO:MSOP-8_3x3mm_P0.65mm", lcsc="C2673354",
         nets={"1": "E1", "2": "ISENSE", "3": "GND_ISO", "4": "+V_STIM", "5": "+5V_ISO", "6": "HOLD", "7": "-V_STIM", "8": None}),
    # ---------------------------------------------------------------- fault detector: LM393 window on E1 -> FAULT_n (open collector into U1 INF)
    # E1_LS = 0.0767*E1 + 1.42 V against TH_P (from +V) and TH_N (from -V): FAULT_n low while |E1| > ~0.915*V, i.e.
    # just before U5A saturates (compliance / open electrode).  Unpowered isolated side: R19 unpowered -> FAULT_n low.
    R("R19", "4.7k", "+5V_ISO", "FAULT_n", lcsc=L4k7),
    R("R20", "100k", "E1", "E1_LS", lcsc=L100k),
    R("R21", "12k", "E1_LS", "GND_ISO", lcsc=L12k),
    R("R22", "27k", "+5V_ISO", "E1_LS", lcsc=L27k),
    C("C18", "100p", "E1_LS", "GND_ISO", lcsc=L100p),
    R("R23", "110k", "+V_STIM", "TH_P", lcsc=L110k),
    R("R24", "12k", "TH_P", "GND_ISO", lcsc=L12k),
    R("R25", "27k", "+5V_ISO", "TH_P", lcsc=L27k),
    R("R26", "110k", "TH_N", "-V_STIM", lcsc=L110k),
    R("R27", "12k", "TH_N", "GND_ISO", lcsc=L12k),
    R("R28", "27k", "+5V_ISO", "TH_N", lcsc=L27k),
    dict(ref="U8", sym="LM393", value="LM393DGKR", fp=VSSOP8, lcsc="C34440",
         nets={"3": "TH_P", "2": "E1_LS", "1": "FAULT_n", "5": "E1_LS", "6": "TH_N", "7": "FAULT_n", "8": "+5V_ISO", "4": "GND_ISO"}),
    C("C19", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),
]

BY_REF = {p["ref"]: p for p in PARTS}
