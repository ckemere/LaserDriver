"""
DC-DC pod (2026-10-29): the isolated +/-15 V supply that left the StimHAT, on a small board that stands on the StimHAT's
top side and plugs into J103 (5 V, GND; 1 x 2, 2.54 mm) and J102's holes (+V, 0V, -V, CAB; 4 x 2.0 mm) with
right-angle pin headers.  Single source of truth for symbol, value, footprint, LCSC code and pin -> net;
tools/netcheck.py proves the drawn schematic matches it.

  5 V side   J1 (pin 1 = 5 V, pin 2 = GND, into HAT J103) -> C104 4.7 uF -> PS1 A0515S-1WR3 pins 1 / 2
  isolated   PS1 pin 6 (+Vo) -> L101 10 uH -> +V_F (C105 10 uF to 0V) -> Q101 MMBT3904 collector; base from +V_F through
             R111 4.7k, C107 10 uF base to 0V; emitter = +V_OUT.  Mirror image on the negative rail: pin 4 (-Vo) -> L102 ->
             -V_F (C106) -> Q102 MMBT3906, R112 / C108, emitter = -V_OUT.  Pin 5 = 0V.
             J2 (into HAT J102's holes): pin 1 = CAB (= 0V, the HAT's cable-detect return), 2 = -V_OUT, 3 = 0V, 4 = +V_OUT.
             J2's numbering is the mirror of the HAT's J102 (1 = +V ... 4 = CAB) because the pod faces north: see README.
  The capacitance multipliers drop about 0.6 V per rail (13.5-14.4 V out at 1-10 mA) and give ~60 dB ripple rejection
  above 100 Hz; the HAT keeps C109 / C110 and the 20 V clamps, so the pod has no output capacitors.
"""

R0402 = "Resistor_SMD:R_0402_1005Metric"
C0603, C0805 = "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0805_2012Metric"
L0805 = "Inductor_SMD:L_0805_2012Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
TP = "TestPoint:TestPoint_Pad_D1.0mm"
HDR2RA = "dcdcpod:PinHeader_1x02_P2.54mm_Horizontal_Pod"
HDR4RA = "dcdcpod:PinHeader_1x04_P2.00mm_Horizontal_Pod"
DCDC = "dcdcpod:DCDC_SIP6_A0515S_BodyN"

# LCSC codes (the StimHAT's table, StimHAT/sch_parts.py)
L = dict(C4u7="C69335", C10u="C15850", L10u="C139245", R4k7="C25900", NPN="C20526", PNP="C53444")


def R(ref, val, a, b, fp=R0402, lcsc=""):
    return dict(ref=ref, sym="R", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


def C(ref, val, a, b, fp=C0805, lcsc=""):
    return dict(ref=ref, sym="C", value=val, fp=fp, lcsc=lcsc, nets={"1": a, "2": b})


PARTS = [
    # ---- 5 V side
    dict(ref="J1", sym="Conn_01x02", value="5V IN (HAT J103)", fp=HDR2RA, lcsc="", nets={"1": "+5V", "2": "GND"}),
    C("C104", "4.7uF", "+5V", "GND", fp=C0603, lcsc=L["C4u7"]),
    dict(ref="PS1", sym="A0515S", value="A0515S-1WR3", fp=DCDC, lcsc="",
         nets={"1": "+5V", "2": "GND", "4": "-V_RAW", "5": "0V", "6": "+V_RAW"}),
    # ---- isolated side: LC filter
    dict(ref="L101", sym="L", value="10uH", fp=L0805, lcsc=L["L10u"], nets={"1": "+V_RAW", "2": "+V_F"}),
    dict(ref="L102", sym="L", value="10uH", fp=L0805, lcsc=L["L10u"], nets={"1": "-V_RAW", "2": "-V_F"}),
    C("C105", "10uF", "+V_F", "0V", lcsc=L["C10u"]),
    C("C106", "10uF", "0V", "-V_F", lcsc=L["C10u"]),
    # ---- capacitance multipliers (1 B, 2 E, 3 C)
    dict(ref="Q101", sym="Q_NPN_BEC", value="MMBT3904", fp=SOT23, lcsc=L["NPN"], nets={"1": "QB_P", "2": "+V_OUT", "3": "+V_F"}),
    R("R111", "4.7k", "+V_F", "QB_P", lcsc=L["R4k7"]),
    C("C107", "10uF", "QB_P", "0V", lcsc=L["C10u"]),
    dict(ref="Q102", sym="Q_PNP_BEC", value="MMBT3906", fp=SOT23, lcsc=L["PNP"], nets={"1": "QB_N", "2": "-V_OUT", "3": "-V_F"}),
    R("R112", "4.7k", "QB_N", "-V_F", lcsc=L["R4k7"]),
    C("C108", "10uF", "0V", "QB_N", lcsc=L["C10u"]),
    # ---- output header and test points
    dict(ref="J2", sym="Conn_01x04", value="+/-V OUT (HAT J102)", fp=HDR4RA, lcsc="",
         nets={"1": "0V", "2": "-V_OUT", "3": "0V", "4": "+V_OUT"}),
    dict(ref="TP1", sym="TestPoint", value="+V_OUT", fp=TP, lcsc="", nets={"1": "+V_OUT"}),
    dict(ref="TP2", sym="TestPoint", value="0V", fp=TP, lcsc="", nets={"1": "0V"}),
    dict(ref="TP3", sym="TestPoint", value="-V_OUT", fp=TP, lcsc="", nets={"1": "-V_OUT"}),
]

BY_REF = {p["ref"]: p for p in PARTS}
assert len(BY_REF) == len(PARTS), "duplicate reference"

# hand-fitted parts (no LCSC code, out of the BOM and CPL): the two headers and the DC-DC module
HAND_FIT = {"J1", "J2", "PS1"}
# nets on the isolated side of the barrier (board net class "Iso" and the isolation rules in DCDCPod.kicad_dru)
ISOLATED_NETS = {"+V_RAW", "-V_RAW", "+V_F", "-V_F", "0V", "QB_P", "QB_N", "+V_OUT", "-V_OUT"}
