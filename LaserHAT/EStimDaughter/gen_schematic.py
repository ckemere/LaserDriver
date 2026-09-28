#!/usr/bin/env python3
"""
Generates EStimDaughter.kicad_sch (kbest e-stim module for the LaserHAT, rev M1) from sch_parts.py and sch_symbols.py.
Blocks 3-6 are the kbest rev E set-point / output stage / SHORT / compliance-monitor drawings (renumbered, see
_blocks_from_revE.py); blocks 1-2 and the SHORT hold timer are new.  Then: tools/netcheck.py and ERC.
    micromamba run -n kicad python gen_schematic.py
"""
from sch_engine import Sheet
from sch_parts import BY_REF

u = 2.54
sh = Sheet()


def put(ref, x, y, rot=0, mirror=False, **kw):
    sh.put(ref, x * u, y * u, rot, mirror, **kw)


def pt(x, y):
    return (x * u, y * u)


W, PWR, LBL, FLAG, NET, LAB = sh.W, sh.PWR, sh.LBL, sh.FLAG, sh.NET, sh.LAB

# =========================================================================== 1. HAT interface + isolation
sh.box(8 * u, 10 * u, 60 * u, 48 * u, "1. HAT INTERFACE / ISOLATION  (ISO7761F, fail-safe low)")
put("J8", 12, 20, mirror=True, val_at=(0, 8.89))
put("J9", 12, 34, mirror=True, val_at=(0, 8.89))
put("U1", 40, 27, ref_at=(0, -13.97), val_at=(0, 13.97))
W("J8.3", ("x", 26 * u), "U1.6")          # EN_H   (PWM_A)
W("J8.4", ("x", 27 * u), "U1.5")          # CATH_H (PWM_B)
W("U1.7", ("x", 25 * u), "J8.5")          # FAULT_H -> GPIO (TIMA0_FAULT0)
W("J9.3", ("x", 29 * u), "U1.3")          # CS_H
W("J9.4", ("x", 30 * u), "U1.4")          # SCK_H
W("J9.5", ("x", 31 * u), "U1.2")          # MOSI_H
for net, x, y in (("EN_H", 22, 20), ("CATH_H", 22, 21), ("FAULT_H", 22, 22), ("CS_H", 22, 34), ("SCK_H", 22, 35), ("MOSI_H", 22, 36)):
    LAB(net, pt(x, y))
e = PWR("J8.1", length=2.54); FLAG(e, up=(1, 0))
e = PWR("J8.2", length=5.08); FLAG(e, up=(1, 0))
PWR("J9.1", length=2.54)
e = PWR("J9.2", length=5.08); FLAG(e, up=(1, 0))
PWR("U1.1"); PWR("U1.8"); PWR("U1.16"); PWR("U1.9")
for pin in ("15", "14", "13", "12", "11", "10"):
    LBL(f"U1.{pin}", length=2.54)
# safe defaults while the MCU pins are Hi-Z (HAT answers Q1/Q3)
for i, (r, net) in enumerate((("R1", "EN_H"), ("R2", "CATH_H"), ("R4", "SCK_H"), ("R5", "MOSI_H"))):
    put(r, 14 + 4 * i, 43)
    NET(f"{r}.1", net, length=2.54)
    PWR(f"{r}.2")
put("R3", 32, 43)
PWR("R3.1")
NET("R3.2", "CS_H", length=2.54)
for i, c in enumerate(("C1", "C2")):
    put(c, 48 + 5 * i, 43)
    PWR(f"{c}.1"); PWR(f"{c}.2")
sh.text("R1-R5: EN/CATH/SCK/MOSI pulled low, CS_n high, while the MCU pins are Hi-Z or the HAT 3V3 is off. C1 at U1 pin 1, C2 at pin 16.",
        9 * u, 47 * u)
sh.text("J8 (underside): 1 GND, 2 +5V, 3 PWM_A=EN, 4 PWM_B=CATH, 5 GPIO=FAULT_n.  J9: 1 GND, 2 +3V3, 3 CS_n, 4 SCK, 5 MOSI.",
        9 * u, 13 * u)

# =========================================================================== 2. isolated power
sh.box(64 * u, 10 * u, 118 * u, 48 * u, "2. ISOLATED POWER  (A0515S +/-15 V, +5 V LDO, -4.7 V zener)")
put("PS1", 78, 22, ref_at=(0, -8.89), val_at=(0, 8.89))
PWR("PS1.1", length=5.08); PWR("PS1.2", length=5.08)
PWR("PS1.6", length=5.08); PWR("PS1.5", length=5.08); PWR("PS1.4", length=5.08)
put("C3", 70, 32); PWR("C3.1"); PWR("C3.2")
put("C4", 86, 32); PWR("C4.1"); PWR("C4.2")
put("C5", 90, 32, rot=180); PWR("C5.1"); PWR("C5.2")
put("U2", 102, 20, ref_at=(0, -6.35), val_at=(0, 6.35))
PWR("U2.2", length=5.08); PWR("U2.1", length=5.08); PWR("U2.3")
put("C6", 98, 32); PWR("C6.1"); PWR("C6.2")
put("C7", 106, 32); PWR("C7.1"); PWR("C7.2")
# -5 V: R6 from -V, D1 4.7 V zener, C8
put("R6", 100, 40.5, rot=270)
put("D1", 104.5, 42, rot=90, ref_at=(2.54, -1.27), val_at=(2.54, 1.27))
put("C8", 108, 42, rot=180)
PWR("R6.2", length=2.54)
W("R6.1", pt(104.5, 40.5), pt(108, 40.5))
sh.wired |= {("D1", "2"), ("C8", "2")}
PWR("D1.1"); PWR("C8.1")
W(pt(108, 40.5), pt(112, 40.5), pt(112, 42))
PWR(None, "-5V_ISO", at=pt(112, 42), up=(0, 1))
FLAG(pt(110, 40.5), up=(0, -1))
sh.text("C3 at PS1 pins 1-2, C4/C5 at pins 4-6. PS1 needs >= 10 % load per rail (~3.4 mA): U1, U2, U4, U5, U6, R7, D1 draw ~8 mA.",
        65 * u, 47 * u)

exec(open(__file__.replace("gen_schematic.py", "_blocks_from_revE.py")).read())

put("TP2", 131, 95)
W("TP2.1", pt(131, 96))
PWR(None, "GND_ISO", at=pt(131, 96), up=(0, 1))

# =========================================================================== SHORT hold timer (added to block 5)
sh.box(76 * u, 106 * u, 96 * u, 132 * u, "5a. SHORT HOLD")
put("D2", 81, 112)
LBL("D2.1", "EN", length=2.54)
LBL("D2.2", "CATH", length=2.54)
put("R15", 86, 115.5)
put("C17", 88, 115.5)
W("D2.3", pt(92, 112))                             # HOLD (passes R15.1, C17.1)
W(pt(86, 112), "R15.1"); W(pt(88, 112), "C17.1")
PWR("R15.2"); PWR("C17.2")
sh.LAB("HOLD", pt(92, 112))
sh.text("EN or CATH high: HOLD high, SHORT released at once.", 77 * u, 127 * u)
sh.text("Both low ~200 us (R15*C17): SHORT on.", 77 * u, 129 * u)
sh.text("Firmware: CATH >= 5 us before EN.", 77 * u, 131 * u)

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("EStimDaughter.kicad_sch", "kbest e-stim module for LaserHAT Rev 2", "M1", "2026-09-26")
print("wrote EStimDaughter.kicad_sch", n, "bytes")
