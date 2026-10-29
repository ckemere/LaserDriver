#!/usr/bin/env python3
"""
Generates DCDCPod.kicad_sch from sch_parts.py and sch_symbols.py (the StimHAT / battery pack engine).  One sheet, drawn
with wires left to right: 5 V header, input capacitor, the A0515S, the LC filter, the capacitance multipliers, the
output header.  tools/netcheck.py proves the result equals sch_parts.PARTS.
    python gen_schematic.py        then: python tools/netcheck.py && kicad-cli sch erc DCDCPod.kicad_sch
"""
from sch_engine import Sheet

u = 2.54
sh = Sheet()


def put(ref, x, y, rot=0, mirror=False, **kw):
    sh.put(ref, x * u, y * u, rot, mirror, **kw)


def pt(x, y):
    return (x * u, y * u)


def W(*specs, **kw):
    return sh.W(*[pt(*s) if isinstance(s, tuple) and not isinstance(s[0], str) else s for s in specs], **kw)


PWR, LBL, FLAG, LAB = sh.PWR, sh.LBL, sh.FLAG, sh.LAB


def pwr_at(net, x, y, up):
    return sh.PWR(None, net=net, at=pt(x, y), up=up)


def lab(net, x, y, d=(1, 0)):
    sh.LAB(net, pt(x, y), d)


def text(s, x, y, size=1.27, bold=False):
    sh.text(s, x * u, y * u, size, bold)


def box(x1, y1, x2, y2, title):
    sh.box(x1 * u, y1 * u, x2 * u, y2 * u, title)


box(6, 6, 92, 50, "DC-DC POD: 5 V -> ISOLATED +/-15 V (A0515S-1WR3), LC FILTER, CAPACITANCE MULTIPLIERS")

# ---- 5 V side: J1 (into the HAT's J103), C104, PS1 pins 1 / 2
put("J1", 16, 20, mirror=True, ref_at=(0, -6.35), val_at=(0, 6.35))
W("J1.1", (21, 19.5), (21, 16)); e = pwr_at("+5V", 21, 16, (0, -1)); FLAG(e, up=(-1, 0))
W("J1.2", (21, 20.5), (21, 24)); e = pwr_at("GND", 21, 24, (0, 1)); FLAG(e, up=(-1, 0))
put("C104", 25, 20); PWR("C104.1"); PWR("C104.2")
put("PS1", 33, 20, ref_at=(0, -8.89), val_at=(0, 8.89))
W("PS1.1", (27, 19), (27, 16)); pwr_at("+5V", 27, 16, (0, -1))
W("PS1.2", (27, 21), (27, 24)); pwr_at("GND", 27, 24, (0, 1))

# ---- isolated side: +Vo / 0V / -Vo out of PS1, LC filter per rail
put("L101", 43, 19); put("L102", 43, 35)
W("PS1.6", "L101.1"); lab("+V_RAW", 38.5, 19)
W("PS1.5", (40.5, 20), (40.5, 25)); pwr_at("0V", 40.5, 25, (0, 1))
W("PS1.4", (39.5, 21), (39.5, 35), "L102.1"); lab("-V_RAW", 39.5, 30, (0, -1))
put("C105", 51, 20.5); put("C106", 51, 33.5)
put("R111", 55, 20.5); put("R112", 55, 33.5)
put("Q101", 62, 21, ref_at=(5.08, -1.27), val_at=(5.08, 1.27))
put("Q102", 62, 33, rot=180, mirror=True, ref_at=(5.08, -1.27), val_at=(5.08, 1.27))
W("L101.2", "Q101.3"); lab("+V_F", 47.5, 19)                  # +V_F line through C105.1 and R111.1
W("L102.2", "Q102.3"); lab("-V_F", 47.5, 35)                  # -V_F line through C106.2 and R112.2
sh.wired |= {("C105", "1"), ("R111", "1"), ("C106", "2"), ("R112", "2")}
PWR("C105.2"); PWR("C106.1")
# capacitance multipliers: base node = R from the rail + C to 0V
put("C107", 58, 25); put("C108", 58, 29)
W("R111.2", (55, 23.5), "C107.1", (59, 23.5)); W("Q101.1", (59, 21), (59, 23.5)); lab("QB_P", 56, 23.5)
W("R112.1", (55, 30.5), "C108.2", (59, 30.5)); W("Q102.1", (59, 33), (59, 30.5)); lab("QB_N", 56, 30.5)
W("C107.2", "C108.1"); W("C108.1", (54, 27.5)); pwr_at("0V", 54, 27.5, (-1, 0))
# outputs
W("Q101.2", (66, 23)); LBL(None, "+V_OUT", at=pt(66, 23), direction=(1, 0))
W("Q102.2", (66, 31)); LBL(None, "-V_OUT", at=pt(66, 31), direction=(1, 0))
put("J2", 80, 27, ref_at=(0, -8.89), val_at=(0, 8.89))
W("J2.1", (75.5, 25.5), (75.5, 23)); pwr_at("0V", 75.5, 23, (0, -1))
LBL("J2.2", length=5.08)
W("J2.3", (74, 27.5), (74, 30)); pwr_at("0V", 74, 30, (0, 1))
LBL("J2.4", length=5.08)
put("TP1", 70, 14); put("TP2", 74, 14); put("TP3", 78, 14)
LBL("TP1.1"); PWR("TP2.1"); LBL("TP3.1")

text("J1 plugs into the StimHAT's J103 (pin 1 = 5 V), J2 into J102's holes (the JST socket is not fitted then): J2.4 = +V, J2.3 = 0V,", 7, 43)
text("J2.2 = -V, J2.1 = CAB = 0V (the HAT's cable-detect return).  Both are right-angle headers on the pod's bottom edge; the pod", 7, 45)
text("stands on the HAT with its parts facing north.  A0515S: 1 W, min. load 10 %; L / C and the Q101 / Q102 multipliers (about 0.6 V", 7, 47)
text("drop per rail, 60 dB ripple rejection above 100 Hz) came off the StimHAT, which keeps C109 / C110 and the 20 V clamps.", 7, 49)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("DCDCPod.kicad_sch", "DC-DC pod: isolated +/-15 V for the StimHAT", "A", "2026-10-29", paper="A4")
print("wrote DCDCPod.kicad_sch", n, "bytes")
