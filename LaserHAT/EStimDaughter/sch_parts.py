"""
kbest e-stim module (LaserHAT Rev 2 plug-in), rev M1: single source of truth for symbol, value, footprint, LCSC and
pin -> net.  Circuit = kbest rev E output stage, powered from the HAT's +5 V through an isolated +/-15 V DC-DC,
controlled over the J8/J9 headers (ESTIM_MODULE_SPEC.md, section 7 = the agreed contract):
  J8: 1 GND_H, 2 +5V_H, 3 FAULT_n (module -> HAT, TIMA0_FAULT0 on PA6), 4 PWM_B = CATH, 5 PWM_A = EN
      (J8.3 / J8.5 swapped on 2026-09-29 evening so FAULT lands opposite the ISO7741's reverse channel; HAT copper change)
  J9: 1 GND_H, 2 +3V3_H, 3 "DAC" = RELEASE (SHORT switch open while high), 4 "ADC_A" = SDA, 5 "ADC_B" = SCL
      (bit-banged I2C to the DAC60501, rev M4; M1-M3 carried bit-banged SPI to an MCP4921 here. SDA/SCL swapped on
      2026-09-29 for the layout: J9.4 = SDA, J9.5 = SCL; spec section 7)
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
L215k = "C185443"


def R(ref, val, a, b, fp=R0402, lcsc=""):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, fp=C0402, lcsc=""):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


PARTS = [
    # ---------------------------------------------------------------- HAT side (non-isolated)
    dict(ref="J8", sym="Conn_01x05", value="J8 power/timing (underside)", fp=HDR5, lcsc="",
         nets={"1": "GND_H", "2": "+5V_H", "3": "FAULT_H", "4": "CATH_H", "5": "EN_H"}),
    dict(ref="J9", sym="Conn_01x05", value="J9 I2C/release (underside)", fp=HDR5, lcsc="",
         nets={"1": "GND_H", "2": "+3V3_H", "3": "RELEASE_H", "4": "SDA_H", "5": "SCL_H"}),
    # safe defaults while the MCU pins are Hi-Z (Q1/Q3): EN/CATH/RELEASE pulled low (zero current, electrode shorted)
    R("R1", "100k", "EN_H", "GND_H", lcsc=L100k),
    R("R2", "100k", "CATH_H", "GND_H", lcsc=L100k),
    R("R3", "100k", "RELEASE_H", "GND_H", lcsc=L100k),
    # I2C pull-ups, HAT side (ISO1640 side 1 draws <= 3.5 mA: >= 1 k) and isolated side
    R("R7", "4.7k", "+3V3_H", "SDA_H", lcsc=L4k7),
    R("R8", "4.7k", "+3V3_H", "SCL_H", lcsc=L4k7),
    # U1: 3 forward (EN, CATH, RELEASE) + 1 reverse (FAULT_n), fail-safe low; EN1/EN2 output enables tied high.
    # Channel order follows the layout (U1 rotated -90, HAT pins run east -> west 1..8): A (3/14) = RELEASE, which
    # arrives from J9 in the east; B (4/13) = EN, C (5/12) = CATH (B/C swapped 2026-09-29 evening for the routing).
    # FAULT_n is fixed on the reverse channel D.
    dict(ref="U1", sym="ISO7741", value="ISO7741FDBQR", fp="Package_SO:SSOP-16_3.9x4.9mm_P0.635mm", lcsc="C2872241",
         nets={"1": "+3V3_H", "2": "GND_H", "3": "RELEASE_H", "4": "EN_H", "5": "CATH_H", "6": "FAULT_H", "7": "+3V3_H", "8": "GND_H",
               "9": "GND_ISO", "10": "+5V_ISO", "11": "FAULT_n", "12": "CATH", "13": "EN", "14": "RELEASE", "15": "GND_ISO", "16": "+5V_ISO"}),
    C("C1", "100n", "+3V3_H", "GND_H", lcsc=L100n),
    C("C2", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),     # between U1 pin 16 and U9 pin 5 (3.3 mm apart): serves both; C20 dropped 2026-09-29
    # U9: bidirectional I2C isolator to the DAC. Both ISO1640 channels are identical and bidirectional, so the channel
    # the datasheet calls SDA (pins 2/7) carries SCL and the SCL channel (3/6) carries SDA: with U9 rotated 180 this
    # puts J9.4 SDA / J9.5 SCL straight onto pins 3 / 2 and SDA / SCL on pins 6 / 7 in the order the DAC wants them.
    dict(ref="U9", sym="ISO1640", value="ISO1640BDR", fp="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", lcsc="C5122339",
         nets={"1": "GND_H", "2": "SCL_H", "3": "SDA_H", "4": "+3V3_H", "5": "+5V_ISO", "6": "SDA", "7": "SCL", "8": "GND_ISO"}),
    C("C17", "100n", "+3V3_H", "GND_H", lcsc=L100n),
    R("R9", "4.7k", "+5V_ISO", "SDA", lcsc=L4k7),
    R("R15", "4.7k", "+5V_ISO", "SCL", lcsc=L4k7),
    # ---------------------------------------------------------------- isolated +/-15 V, +5 V, -5 V
    # DNP: fitted by hand - A0515S-1WR3 (Mornsun), RECOM RB-0515D/HP (verified pin-compatible) or the YLPTEC clone (LCSC C5369388), in a SIP
    # socket or soldered; or leave empty and feed pins 6 / 5 / 4 = +V / 0V / -V from two battery packs (<= +/-18 V).
    dict(ref="PS1", sym="A0515S", value="A0515S-1WR3", fp="estim:DCDC_SIP6_A0515S", lcsc="", dnp=True,
         nets={"1": "+5V_H", "2": "GND_H", "6": "+V_STIM", "5": "GND_ISO", "4": "-V_STIM"}),
    C("C3", "4.7u", "+5V_H", "GND_H", fp=C0603, lcsc=L4u7),
    C("C5", "1u 50V", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L1u50),
    dict(ref="U2", sym="TLV760", value="TLV76050DBZR", fp=SOT23, lcsc="C2867465",
         nets={"2": "+V_STIM", "1": "+5V_ISO", "3": "GND_ISO"}),
    C("C6", "1u 50V", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L1u50),
    C("C7", "1u 50V", "+5V_ISO", "GND_ISO", fp=C0603, lcsc=L1u50),
    # ---------------------------------------------------------------- set-point: DAC60501 (I2C, internal 2.5 V ref / 2 -> 0..1.25 V)
    # SPI2C high = I2C; A0 = AGND -> address 1001000 (0x48); Z variant powers up at zero code.  Firmware: GAIN reg 0x04 =
    # 0x0100 (REF-DIV = 1, BUFF-GAIN = 0) before the first DAC write, then DAC reg 0x08 = code << 4.
    dict(ref="U4", sym="DAC60501", value="DAC60501ZDGSR", fp="Package_SO:VSSOP-10_3x3mm_P0.5mm", lcsc="C1852027",
         nets={"1": "+5V_ISO", "2": "VSET_P", "3": None, "4": "GND_ISO", "5": "+5V_ISO", "6": "SCL", "7": "GND_ISO", "8": "SDA",
               "9": None, "10": "VREFIO"}),
    C("C9", "100n", "VREFIO", "GND_ISO", lcsc=L100n),
    C("C10", "100n", "+5V_ISO", "GND_ISO", lcsc=L100n),
    # ---------------------------------------------------------------- U5: OPA2192 (A = V->I output stage, B = -VSET inverter)
    dict(ref="U5", sym="OPA2192", value="OPA2192IDGKR", fp=VSSOP8, lcsc="C2876419",
         nets={"3": "OA_IN", "2": "ISENSE", "1": "OA_OUT", "5": "GND_ISO", "6": "U5B_IN", "7": "VSET_N", "8": "+V_STIM", "4": "-V_STIM"}),
    C("C11", "100n", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L100n50),
    C("C12", "100n", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L100n50),
    R("R10", "10.0k 0.1%", "VSET_P", "U5B_IN", fp=R0603, lcsc="C95204"),
    R("R11", "10.0k 0.1%", "U5B_IN", "VSET_N", fp=R0603, lcsc="C95204"),
    # ---------------------------------------------------------------- U6: ADG1436 dual SPDT on the +/-V rails (M4c, 2026-09-29)
    # Replaces the 74HC4053 and its -5 V zener rail (R6, D1, C8).  ADG1436 LFCSP-16 (4 x 4 mm, CP-16-26, exposed pad = VSS):
    # 1 D1, 2 S1B, 3 VSS, 4 GND, 6 IN2, 8 S2A, 9 D2, 10 S2B, 11 VDD, 12 EN, 15 IN1, 16 S1A; 5/7/13/14 NC.  INx low = SxB on,
    # high = SxA on; EN low = all off (D floats), so EN is tied high and never used for gating.  EN goes to VDD (+V_STIM): the
    # logic inputs are rated to VDD + 0.3 V and IDD is ~1 nA with inputs at VDD against ~140 uA at 5 V (changed 2026-09-29 late).
    # Switch 2 (IN2 = CATH) picks VSET_P (0, S2B) / VSET_N (1, S2A) -> SW_P.  Switch 1 (IN1 = EN) picks 0 V (0, S1B) / SW_P (1, S1A)
    # -> V_IN.  (Channels swapped for the layout 2026-09-29: IN1 / S1x face east on the board.)
    # 1.5 ohm, 20 pC injection (harmless: SW_P and V_IN are always driven by a low-impedance throw), break before make.
    dict(ref="U6", sym="ADG1436", value="ADG1436YCPZ", fp="Package_DFN_QFN:QFN-16-1EP_4x4mm_P0.65mm_EP2.5x2.5mm", lcsc="C655227",
         nets={"15": "EN", "16": "SW_P", "2": "GND_ISO", "1": "V_IN", "6": "CATH", "8": "VSET_N", "10": "VSET_P", "9": "SW_P",
               "11": "+V_STIM", "3": "-V_STIM", "17": "-V_STIM", "4": "GND_ISO", "12": "+V_STIM", "5": None, "7": None, "13": None, "14": None}),
    C("C13", "100n", "+V_STIM", "GND_ISO", fp=C0603, lcsc=L100n50),      # +V / -V taps on the west feed near U6 (kept for now, 2026-09-29)
    C("C14", "100n", "GND_ISO", "-V_STIM", fp=C0603, lcsc=L100n50),
    # ---------------------------------------------------------------- output stage
    R("R12", "1k", "V_IN", "OA_IN", lcsc=L1k),
    C("C15", "100p", "OA_IN", "GND_ISO", lcsc=L100p),
    R("R13", "47", "OA_OUT", "E1", lcsc=L47),
    R("R14", "2.49k 0.1%", "ISENSE", "GND_ISO", fp=R0603, lcsc="C861299"),    # 1.25 V full scale / 2.49 k = 502 uA
    C("C16", "1u 50V", "E1", "E1_OUT", fp=C0805, lcsc=L1u50_0805),
    dict(ref="J1", sym="Conn_01x02", value="ELECTRODE E1/E2", fp=HDR2RA, lcsc="", nets={"1": "E1_OUT", "2": "ISENSE"}),
    dict(ref="TP1", sym="TestPoint", value="ISENSE", fp=TP, lcsc="", nets={"1": "ISENSE"}),
    dict(ref="TP2", sym="TestPoint", value="GND_ISO", fp=TP, lcsc="", nets={"1": "GND_ISO"}),
    # ---------------------------------------------------------------- SHORT switch (DG419B, throw 1 = on while IN low), driven by RELEASE
    # RELEASE comes straight from the HAT through U1: low (idle, unpowered, faulted) = E1 shorted to E2 (ISENSE); the M1-M3
    # hold timer (BAT54C + RC) is gone.  DG419B MSOP-8: 15 ohm, 38 pC injection, 12 pF off-capacitance.
    dict(ref="U7", sym="DG419", value="DG419BDQ", fp="Package_SO:MSOP-8_3x3mm_P0.65mm", lcsc="C2673354",
         nets={"1": "E1", "2": "ISENSE", "3": "GND_ISO", "4": "+V_STIM", "5": "+5V_ISO", "6": "RELEASE", "7": "-V_STIM", "8": None}),
    # ---------------------------------------------------------------- fault detector: TLV1702 window on E1 -> FAULT_n (M4b, 2026-09-29)
    # U8 runs from +/-V (36 V rail-to-rail-input comparator) and looks at E1 directly.  One string +V - 10k - 215k - 10k - -V
    # puts TH_P / TH_N at 0.0426 * (V+ + |V-|) inside each rail (= +/-0.915 V for symmetric packs; the average for unequal
    # packs, a missing pack holds FAULT_n low).  Both open collectors sink to -V, so the wired-OR output reaches the
    # isolator through R26 with D2 clamping FAULT_n at about -0.3 V; R19 pulls it high.  Unpowered isolated side: low.
    R("R19", "4.7k", "+5V_ISO", "FAULT_n", lcsc=L4k7),
    R("R23", "10k", "+V_STIM", "TH_P", lcsc=L10k),
    R("R24", "215k", "TH_P", "TH_N", lcsc=L215k),
    R("R25", "10k", "TH_N", "-V_STIM", lcsc=L10k),
    dict(ref="U8", sym="TLV1702", value="TLV1702AIDGKR", fp=VSSOP8, lcsc="C2870937",
         nets={"5": "TH_P", "6": "E1", "7": "FAULT_OC", "3": "E1", "2": "TH_N", "1": "FAULT_OC", "8": "+V_STIM", "4": "-V_STIM"}),   # B = upper (TH_P), A = lower (TH_N); swapped 2026-09-29 for the layout
    R("R26", "10k", "FAULT_OC", "FAULT_n", lcsc=L10k),
    dict(ref="D2", sym="D", value="BAT54WS", fp=SOD323, lcsc="C124205", nets={"1": "FAULT_n", "2": "GND_ISO"}),   # K = FAULT_n, A = GND_ISO
    C("C19", "100n", "+V_STIM", "-V_STIM", fp=C0603, lcsc=L100n50),
]

BY_REF = {p["ref"]: p for p in PARTS}
