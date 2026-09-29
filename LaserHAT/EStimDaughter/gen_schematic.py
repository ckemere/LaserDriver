#!/usr/bin/env python3
"""
Generates EStimDaughter.kicad_sch (kbest e-stim module for the LaserHAT, rev M4) from sch_parts.py and sch_symbols.py.
Blocks 3-6 are the kbest rev E set-point / output stage / SHORT / fault-detector drawings (renumbered, see
_blocks_from_revE.py; block 3 redrawn for the I2C DAC in M4); blocks 1-2 are new.  Then: tools/netcheck.py and ERC.
    python gen_schematic.py
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
sh.box(8 * u, 10 * u, 60 * u, 60 * u, "1. HAT INTERFACE / ISOLATION  (ISO7741F fail-safe low + ISO1640 I2C)")
put("J8", 12, 20, mirror=True, val_at=(0, 8.89))
put("J9", 12, 34, mirror=True, val_at=(0, 8.89))
put("U1", 40, 27, ref_at=(0, -13.97), val_at=(0, 13.97))
put("U9", 40, 50, ref_at=(0, -11.43), val_at=(0, 11.43))
# channel order follows the board (2026-09-29): U1 A = RELEASE (from J9 in the east), B = CATH, C = EN; U9's "SCL"
# channel (3/6) carries SDA and its "SDA" channel (2/7) carries SCL; J9.4 = SDA, J9.5 = SCL (spec section 7)
W("J8.3", ("x", 26 * u), "U1.5")          # EN_H      (PWM_A)   -> INC
W("J8.4", ("x", 27 * u), "U1.4")          # CATH_H    (PWM_B)   -> INB
W("U1.6", ("x", 25 * u), "J8.5")          # FAULT_H   <- OUTD   -> GPIO (TIMA0_FAULT0)
W("J9.3", ("x", 31 * u), "U1.3")          # RELEASE_H ("DAC")   -> INA
W("J9.4", ("x", 29 * u), "U9.3")          # SDA_H     ("ADC_A") -> pin 3 ("SCL1" channel)
W("J9.5", ("x", 30 * u), "U9.2")          # SCL_H     ("ADC_B") -> pin 2 ("SDA1" channel)
for net, x, y in (("EN_H", 22, 20), ("CATH_H", 22, 21), ("FAULT_H", 22, 22), ("RELEASE_H", 22, 34), ("SDA_H", 22, 35), ("SCL_H", 22, 36)):
    LAB(net, pt(x, y))
e = PWR("J8.1", length=2.54); FLAG(e, up=(1, 0))
e = PWR("J8.2", length=5.08); FLAG(e, up=(1, 0))
PWR("J9.1", length=2.54)
e = PWR("J9.2", length=5.08); FLAG(e, up=(1, 0))
PWR("U1.1"); PWR("U1.16"); PWR("U1.2", length=2.54); PWR("U1.8", length=5.08); PWR("U1.9", length=2.54); PWR("U1.15", length=5.08)
W("U1.7", pt(32, 29), pt(32, 31.5)); PWR(None, "+3V3_H", at=pt(32, 31.5), up=(0, 1))       # EN1: outputs enabled
W("U1.10", pt(49, 29), pt(49, 31.5)); PWR(None, "+5V_ISO", at=pt(49, 31.5), up=(0, 1))     # EN2
for pin in ("14", "13", "12", "11"):
    LBL(f"U1.{pin}", length=2.54)         # EN, CATH, RELEASE, FAULT_n
PWR("U9.4"); PWR("U9.5"); PWR("U9.1"); PWR("U9.8")
LBL("U9.7", length=2.54); LBL("U9.6", length=2.54)     # SCL, SDA (isolated)
# safe defaults while the MCU pins are Hi-Z (HAT answers Q1/Q3): EN, CATH, RELEASE low; I2C pull-ups
for i, (r, net) in enumerate((("R1", "EN_H"), ("R2", "CATH_H"), ("R3", "RELEASE_H"))):
    put(r, 14 + 4 * i, 43)
    NET(f"{r}.1", net, length=2.54)
    PWR(f"{r}.2")
for i, (r, net) in enumerate((("R7", "SDA_H"), ("R8", "SCL_H"))):
    put(r, 25 + 3 * i, 43)
    PWR(f"{r}.1")
    NET(f"{r}.2", net, length=2.54)
for i, c in enumerate(("C1", "C2")):
    put(c, 48 + 5 * i, 43)
    PWR(f"{c}.1"); PWR(f"{c}.2")
for i, c in enumerate(("C17", "C20")):
    put(c, 52 + 4 * i, 55)
    PWR(f"{c}.1"); PWR(f"{c}.2")
sh.text("R1-R3: EN/CATH/RELEASE pulled low while the MCU pins are Hi-Z or the HAT 3V3 is off (zero current, electrode shorted).", 9 * u, 47 * u)
sh.text("R7/R8: I2C pull-ups, HAT side.  C1 at U1 pin 1, C2 at pin 16, C17/C20 at U9 pins 4/5.", 9 * u, 49 * u)
sh.text("J8 (underside): 1 GND, 2 +5V, 3 PWM_A=EN, 4 PWM_B=CATH, 5 GPIO=FAULT_n.  J9: 1 GND, 2 +3V3, 3 RELEASE, 4 SDA, 5 SCL.",
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
sh.text("C3 at PS1 pins 1-2, C4/C5 at pins 4-6. PS1 needs >= 10 % load per rail (~3.4 mA): U1, U2, U4, U5, U6, U8, U9, D1 draw ~9 mA.",
        65 * u, 47 * u)

exec(open(__file__.replace("gen_schematic.py", "_blocks_from_revE.py")).read())

put("TP2", 131, 95)
W("TP2.1", pt(131, 96))
PWR(None, "GND_ISO", at=pt(131, 96), up=(0, 1))

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("EStimDaughter.kicad_sch", "kbest e-stim module for LaserHAT Rev 2", "M4", "2026-09-29")
print("wrote EStimDaughter.kicad_sch", n, "bytes")
