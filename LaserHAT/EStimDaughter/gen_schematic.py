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
# channel order follows the board (2026-09-29): U1 A = RELEASE (from J9 in the east), B = EN, C = CATH; U9's "SCL"
# channel (3/6) carries SDA and its "SDA" channel (2/7) carries SCL; J9.4 = SDA, J9.5 = SCL (spec section 7)
W("U1.6", ("x", 25 * u), "J8.3")          # FAULT_H   <- OUTD   -> J8.3 (TIMA0_FAULT0); J8.3/J8.5 swapped 2026-09-29
W("J8.4", ("x", 27 * u), "U1.5")          # CATH_H    (PWM_B)   -> INC
W("J8.5", ("x", 26 * u), "U1.4")          # EN_H      (PWM_A)   -> INB
W("J9.3", ("x", 31 * u), "U1.3")          # RELEASE_H ("DAC")   -> INA
W("J9.4", ("x", 29 * u), "U9.3")          # SDA_H     ("ADC_A") -> pin 3 ("SCL1" channel)
W("J9.5", ("x", 30 * u), "U9.2")          # SCL_H     ("ADC_B") -> pin 2 ("SDA1" channel)
for net, x, y in (("FAULT_H", 22, 20), ("CATH_H", 22, 21), ("EN_H", 22, 22), ("RELEASE_H", 22, 34), ("SDA_H", 22, 35), ("SCL_H", 22, 36)):
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
for i, c in enumerate(("C17",)):
    put(c, 52 + 4 * i, 55)
    PWR(f"{c}.1"); PWR(f"{c}.2")
sh.text("R1-R3: EN/CATH/RELEASE pulled low while the MCU pins are Hi-Z or the HAT 3V3 is off (zero current, electrode shorted).", 9 * u, 47 * u)
sh.text("R7/R8: I2C pull-ups, HAT side.  C1 at U1 pin 1, C2 between U1 pin 16 and U9 pin 5 (both VCC2), C17 at U9 pin 4.", 9 * u, 49 * u)
sh.text("J8 (underside): 1 GND, 2 +5V, 3 FAULT_n (HAT PA6), 4 PWM_B=CATH, 5 PWM_A=EN.  J9: 1 GND, 2 +3V3, 3 RELEASE, 4 SDA, 5 SCL.",
        9 * u, 13 * u)

# =========================================================================== 2. isolated power
sh.box(64 * u, 10 * u, 118 * u, 48 * u, "2. ISOLATED POWER  (A0515S +/-15 V, +5 V LDO)")
put("PS1", 78, 22, ref_at=(0, -8.89), val_at=(0, 8.89))
PWR("PS1.1", length=5.08); PWR("PS1.2", length=5.08)
PWR("PS1.6", length=5.08); PWR("PS1.5", length=5.08); PWR("PS1.4", length=5.08)
put("C3", 70, 32); PWR("C3.1"); PWR("C3.2")
put("C5", 90, 32, rot=180); PWR("C5.1"); PWR("C5.2")
put("U2", 102, 20, ref_at=(0, -6.35), val_at=(0, 6.35))
PWR("U2.2", length=5.08); PWR("U2.1", length=5.08); PWR("U2.3")
put("C6", 98, 32); PWR("C6.1"); PWR("C6.2")
put("C7", 106, 32); PWR("C7.1"); PWR("C7.2")
sh.text("C3 at PS1 pins 1-2, C5 at pin 4 (C6, the LDO input cap, is the +V bulk).  Load: +V ~9 mA (LDO -> U1, U9, U4), -V ~1.5 mA (U5, U8): below the 10 % minimum load",
        65 * u, 45 * u)
sh.text("of the Mornsun A0515S on the -V rail since the -5 V zener chain went (M4c); fit the RECOM RB-0515D/HP (0 % min load) or batteries.",
        65 * u, 47 * u)

exec(open(__file__.replace("gen_schematic.py", "_blocks_from_revE.py")).read())

put("TP2", 131, 95)
W("TP2.1", pt(131, 96))
PWR(None, "GND_ISO", at=pt(131, 96), up=(0, 1))

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("EStimDaughter.kicad_sch", "kbest e-stim module for LaserHAT Rev 2", "M4c", "2026-09-29")
print("wrote EStimDaughter.kicad_sch", n, "bytes")
