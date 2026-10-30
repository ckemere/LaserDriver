#!/usr/bin/env python3
"""
Generates StimHAT.kicad_sch from sch_parts.py and sch_symbols.py (same engine as the e-stim module and the battery
pack).  Connectivity inside a block is drawn with wires where it reads better, otherwise with global labels and power
symbols; tools/netcheck.py proves the result equals sch_parts.PARTS.
    python gen_schematic.py        then: python tools/netcheck.py && kicad-cli sch erc StimHAT.kicad_sch
"""
from sch_engine import Sheet
from sch_parts import BY_REF

u = 2.54
sh = Sheet()


def put(ref, x, y, rot=0, mirror=False, **kw):
    sh.put(ref, x * u, y * u, rot, mirror, **kw)


def pt(x, y):
    return (x * u, y * u)


def W(*specs, **kw):
    return sh.W(*[pt(*s) if isinstance(s, tuple) and not isinstance(s[0], str) else s for s in specs], **kw)


PWR, LBL, FLAG, NET, LAB = sh.PWR, sh.LBL, sh.FLAG, sh.NET, sh.LAB


def pwr_at(net, x, y, up):
    return sh.PWR(None, net=net, at=pt(x, y), up=up)


def lab(net, x, y, d=(1, 0)):
    sh.LAB(net, pt(x, y), d)


def text(s, x, y, size=1.27, bold=False):
    sh.text(s, x * u, y * u, size, bold)


def box(x1, y1, x2, y2, title):
    sh.box(x1 * u, y1 * u, x2 * u, y2 * u, title)


def pins(ref, nums, kind="LBL", lengths=(2.54,)):
    """label / power-symbol every listed pin, cycling the stub lengths so neighbours do not overlap"""
    for i, n in enumerate(nums):
        length = lengths[i % len(lengths)]
        (PWR if kind == "PWR" else LBL)(f"{ref}.{n}", length=length)


# =========================================================================== 1. Pi header, USB-C, 5 V / 3.3 V
box(6, 8, 100, 62, "1. RASPBERRY PI HEADER, USB-C (CH340N power path), 5 V / 3.3 V RAILS, HAT ID EEPROM")
put("J1", 20, 34, ref_at=(0, -30.48), val_at=(0, 30.48))
pins("J1", ("1", "17"), "PWR", (5.08, 2.54))                    # +3V3_PI (left, pins 1 and 17)
pins("J1", ("2", "4"), "PWR", (5.08, 2.54))                     # +5V (right)
pins("J1", ("9", "25", "39"), "PWR", (2.54,))                   # GND, left side (odd)
pins("J1", ("6", "14", "20", "30", "34"), "PWR", (5.08, 2.54))  # GND, right side (even)
for n in ("3", "5", "19", "21", "27"):
    LBL(f"J1.{n}", length=5.08)                                  # I2C_SDA, I2C_SCL, MCU_PWR_EN, NRST, ID_SDA (left)
for n in ("8", "10", "12", "18", "22", "28"):
    LBL(f"J1.{n}", length=5.08)                                  # PI_TXD, PI_RXD, PI_TRIGGER, SWCLK, SWDIO, ID_SCL (right)
e = PWR("J1.2", length=7.62); FLAG(e, up=(1, 0))                 # the Pi drives +5V ...
e = PWR("J1.1", length=7.62); FLAG(e, up=(-1, 0))                # ... and +3V3_PI
e = PWR("J1.9", length=5.08); FLAG(e, up=(-1, 0))                # GND
text("Pi header: 3.3 V (pins 1/17) feeds the ID EEPROM and the I2C pull-ups; 5 V (2/4) the LDO U4.  GPIO16 (pin 36) = NRST (was GPIO23:", 7, 57)
text("the Adafruit 4567 bonnet's joystick-right grounds GPIO23).  GPIO18 = MCU power enable, GPIO24/25 = SWD, GPIO26 = trigger, GPIO14/15 = UART.", 7, 59)
# USB-C
put("J5", 48, 20, ref_at=(0, -16.51), val_at=(0, 16.51), hide_val=True)
W("J5.A4", (41, 16), (41, 19), "J5.B9"); W("J5.B4", (41, 17)); W("J5.A9", (41, 18))
W((41, 16), (41, 13)); e = pwr_at("VBUS", 41, 13, (0, -1)); FLAG(e, up=(-1, 0))
W("J5.A1", (46, 28), (50, 28), "J5.S1"); W("J5.B1", (47, 28)); W("J5.B12", (49, 28))
W("J5.A12", (48, 28), (48, 30)); pwr_at("GND", 48, 30, (0, 1))
put("R8", 60, 14, rot=90); put("R10", 60, 18, rot=90)
W("J5.A5", "R8.1"); W("J5.B5", "R10.1")
PWR("R8.2"); PWR("R10.2")
W("J5.A6", (57, 20), (57, 24), (62, 24)); W("J5.B6", (56, 20), (56, 24), (57, 24)); LBL(None, "USB_DP", at=pt(62, 24), direction=(1, 0))
W("J5.A7", (55, 21), (55, 26), (62, 26)); W("J5.B7", (54, 22), (54, 26), (55, 26)); LBL(None, "USB_DM", at=pt(62, 26), direction=(1, 0))
sh.wired |= {("J5", "A6"), ("J5", "B6"), ("J5", "A7"), ("J5", "B7")}
# VBUS switch Q5 (SW10 grounds the gate), ideal diode Q3 / Q4 into +5V
put("Q5", 71, 14, rot=180, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q5.2"); LBL("Q5.3")                                         # source VBUS (top), drain VBUS_SW (bottom)
put("R26", 77, 10); PWR("R26.1"); W("R26.2", (77, 14), "Q5.1"); lab("PWR_EN", 75, 14)
put("SW10", 84, 14, ref_at=(0, -4.45), val_at=(0, 4.45))
W("SW10.2", (77, 14)); PWR("SW10.1", length=2.54)
put("Q3", 71, 28, ref_at=(-6.35, -1.27), val_at=(-6.35, 1.27))
PWR("Q3.2"); LBL("Q3.3")                                         # S = +5V (bottom), D = VBUS_SW (top)
put("Q4", 86, 30, ref_at=(0, -11.43), val_at=(0, 11.43))
W("Q4.2", (78, 28)); W("Q4.3", (78, 32)); W((78, 26), (78, 33)); lab("IDEAL_B", 78, 30, (0, -1))
put("R21", 76, 36, rot=0); W("R21.1", (76, 33), (78, 33)); PWR("R21.2")
W("Q4.1", (94, 27), (94, 24), (78, 24), (78, 26))
W("Q4.4", (95, 31), (95, 40), (71, 40), "Q3.1"); lab("IDEAL_G", 90, 40)
put("R22", 98, 36); W("R22.1", (98, 33), (95, 33)); PWR("R22.2")
PWR("Q4.5", length=2.54); LBL("Q4.6", length=2.54)
text("Q5 passes VBUS while SW10 holds its gate low (R26 100k pulls it off); Q3 / Q4 / R21 / R22 = ideal diode into +5V, so", 62, 44)
text("the USB-C supply and the Pi's 5 V never fight.  D5 lights on +5V.", 62, 46)
put("D5", 66, 50, rot=180); put("R13", 72, 50, rot=90)
PWR("D5.2", length=2.54); W("D5.1", "R13.1"); PWR("R13.2")
put("C12", 80, 52); PWR("C12.1"); PWR("C12.2")
# 3.3 V: U4 MCP1700 -> +3V3 (CH340N, U5 input); U5 AP2171W -> MSPM0_3V3 switched by the Pi (GPIO18)
put("U4", 14, 50, ref_at=(0, -6.35), val_at=(0, 6.35))
e = PWR("U4.2", length=5.08); PWR("U4.3", length=5.08); PWR("U4.1")
put("C6", 24, 52); PWR("C6.1"); PWR("C6.2")
put("C13", 30, 52); PWR("C13.1"); PWR("C13.2")
put("U5", 44, 46, ref_at=(0, -7.62), val_at=(0, 7.62))
PWR("U5.5", length=5.08); PWR("U5.1", length=5.08); PWR("U5.2"); LBL("U5.4", length=5.08)
put("R7", 34, 42); PWR("R7.1"); LBL("R7.2")
put("C1", 52, 54); put("C2", 57, 54); put("C16", 62, 54)
for c in ("C1", "C2", "C16"):
    PWR(f"{c}.1"); PWR(f"{c}.2")
put("JP5", 14, 42, ref_at=(0, -5.08), val_at=(0, 5.08))
PWR("JP5.1", length=5.08); PWR("JP5.2", length=5.08)
# ID EEPROM
put("U1", 86, 56, ref_at=(0, -10.16), val_at=(0, 10.16))
PWR("U1.8"); PWR("U1.4"); LBL("U1.5"); LBL("U1.6"); LBL("U1.7", length=2.54)
put("JP1", 72, 60, ref_at=(0, -5.08), val_at=(0, 5.08)); LBL("JP1.1", length=5.08); PWR("JP1.2", length=5.08)
put("R1", 94, 48, rot=0); put("R2", 98, 48, rot=0)
PWR("R1.1"); LBL("R1.2"); PWR("R2.1"); LBL("R2.2")
put("R19", 30, 60, rot=0); put("R20", 36, 60, rot=0); put("C15", 42, 60); put("C18", 47, 60); PWR("C18.1"); PWR("C18.2")
PWR("R19.1"); LBL("R19.2"); PWR("R20.1"); LBL("R20.2"); PWR("C15.1"); PWR("C15.2")

# =========================================================================== 2. MCU
box(102, 8, 200, 62, "2. MSPM0G1507 (Rev 2 pin map; the G3507 minus CAN-FD, same RHB pinout), USB-UART (CH340N), RESET, BSL, JOYSTICK / FIRE, LEDs, 0.91 in OLED SOCKET")
put("U7", 152, 32, ref_at=(0, -24.13), val_at=(0, 24.13))
PWR("U7.4"); PWR("U7.5"); PWR("U7.33", length=5.08)
put("C4", 160, 10, rot=90); W("U7.32", (154, 10), "C4.1"); PWR("C4.2")      # VCORE cap at the top
for n in ("1", "2", "3", "6", "8", "10", "11", "12", "13", "14", "15", "16"):   # 7 / 9 (PA3 / PA5) are spare
    LBL(f"U7.{n}", length=2.54)
for n in ("17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31"):
    LBL(f"U7.{n}", length=2.54)
put("R4", 108, 40, rot=0); LBL("R4.1"); PWR("R4.2")
put("R3", 108, 24, rot=0); PWR("R3.1"); LBL("R3.2")                           # NRST pull-up
put("C3", 114, 24, rot=0); LBL("C3.1"); PWR("C3.2")
put("JP4", 112, 32, ref_at=(0, -5.08), val_at=(0, 5.08)); LBL("JP4.1", length=5.08); LBL("JP4.2", length=5.08)
put("U6", 124, 50, ref_at=(0, -10.16), val_at=(0, 10.16))
LBL("U6.1"); LBL("U6.2"); LBL("U6.4"); LBL("U6.6"); LBL("U6.7"); PWR("U6.5"); PWR("U6.8", length=5.08); PWR("U6.3")
put("C17", 104, 47); PWR("C17.1"); PWR("C17.2")                               # CH340N decoupler, on the MCU rail
put("SW6", 112, 54, ref_at=(0, -4.45), val_at=(0, 3.81)); LBL("SW6.1", length=5.08); PWR("SW6.2", length=5.08)
put("D7", 176, 12, rot=180); put("R15", 182, 12, rot=90)
LBL("D7.2", length=2.54); W("D7.1", "R15.1"); PWR("R15.2")
put("SW7", 182, 28, ref_at=(0, -9.525), val_at=(0, 9.525))
for n in ("1", "3", "6", "4", "2"):
    LBL(f"SW7.{n}", length=5.08)
PWR("SW7.5", length=5.08)
put("SW9", 182, 42, ref_at=(0, -4.45), val_at=(0, 3.81)); LBL("SW9.1", length=5.08); PWR("SW9.2", length=5.08)
put("J10", 184, 54, mirror=True, ref_at=(0, -8.89), val_at=(0, 8.89))
PWR("J10.1", length=5.08); PWR("J10.2", length=5.08); LBL("J10.3", length=5.08); LBL("J10.4", length=5.08)
text("Module lines from the Rev 2 J8 / J9 pins: PA6 FAULT_H, PA7 EN_H, PA12 CATH_H, PA15 RELEASE_H, PA17 SDA_H, PA22 SCL_H (StimHAT: see the README's pin map).  Joystick SW7 (SKRHADE010, mounted at 135 deg): up PA12,", 103, 57)
text("down PA15, centre PA14, left PA7 (BACK), right PA13 (BUTTON6); FIRE SW9 PA16; LED PA6; all active low.  J10: unpopulated socket for a 0.91 in I2C OLED instead of the bonnet.", 103, 59)

# =========================================================================== 3. BNC I/O
box(202, 8, 252, 40, "3. BNC TRIGGER IN / STIM OUT (74LVC2G17 buffers)")
put("J6", 210, 16, mirror=True, val_at=(0, 6.35))
put("R23", 220, 15, rot=270); put("R24", 222, 21)
put("U8", 234, 16, ref_at=(0, -8.89), val_at=(0, 8.89))
put("R25", 247, 15, rot=270)
put("J7", 246, 32, mirror=True, val_at=(0, 6.35))
put("D9", 232, 30); put("R18", 226, 30, rot=270)
W("J6.1", (216, 15), "R23.2"); PWR("J6.2", length=2.54)
W("R23.1", (226, 15), "U8.1")
W("R24.1", (222, 18), (222, 15)); PWR("R24.2")
PWR("U8.5"); PWR("U8.2"); LBL("U8.3", length=2.54); LBL("U8.6", length=2.54)
W("U8.4", (244, 15), "R25.2"); W("R25.1", (251, 15), "J7.1")
W("J7.1", (251, 31), (251, 15)); PWR("J7.2", length=2.54)
W("D9.2", (238, 30), (238, 22), (244, 22), (244, 15))
W("D9.1", "R18.1"); PWR("R18.2", length=2.54)
text("J6 -> R23 1k / R24 100k -> U8A -> PA26 (TIMG8 capture).  PA25 (TIMG12) -> U8B -> R25 33 -> J7, D9 mirrors the pulses.", 203, 37)

# =========================================================================== 4. isolation
box(6, 64, 60, 112, "4. ISOLATION: ISO7741F (EN, CATH, RELEASE in; FAULT_n back, fail-safe low) + ISO1640 (I2C)")
put("U101", 36, 80, ref_at=(0, -13.97), val_at=(0, 13.97))
PWR("U101.1"); PWR("U101.16"); PWR("U101.2", length=2.54); PWR("U101.8", length=5.08); PWR("U101.9", length=2.54); PWR("U101.15", length=5.08)
for n in ("3", "4", "5", "6", "14", "13", "12", "11"):
    LBL(f"U101.{n}", length=2.54)
W("U101.7", (28, 82), (28, 84.5)); pwr_at("MSPM0_3V3", 28, 84.5, (0, 1))       # EN1 high
W("U101.10", (44, 82), (44, 84.5)); pwr_at("+5V_ISO", 44, 84.5, (0, 1))       # EN2 high
put("U109", 36, 100, ref_at=(0, -11.43), val_at=(0, 11.43))
PWR("U109.1"); PWR("U109.8"); PWR("U109.4"); PWR("U109.5")
LBL("U109.2", length=2.54); LBL("U109.3", length=2.54); LBL("U109.7", length=2.54); LBL("U109.6", length=2.54)
for i, (r, net) in enumerate((("R101", "EN_H"), ("R102", "CATH_H"), ("R103", "RELEASE_H"))):
    put(r, 10 + 4 * i, 72)
    LBL(f"{r}.1", length=2.54); PWR(f"{r}.2")
for i, (r, net) in enumerate((("R107", "SDA_H"), ("R108", "SCL_H"))):
    put(r, 10 + 4 * i, 84)
    PWR(f"{r}.1"); LBL(f"{r}.2", length=2.54)
for i, (r, net) in enumerate((("R109", "SDA"), ("R110", "SCL"))):
    put(r, 52 + 4 * i, 100)
    PWR(f"{r}.1"); LBL(f"{r}.2", length=2.54)
for i, c in enumerate(("C101", "C103")):
    put(c, 10 + 5 * i, 96); PWR(f"{c}.1"); PWR(f"{c}.2")
for i, c in enumerate(("C102", "C124")):
    put(c, 52 + 5 * i, 90); PWR(f"{c}.1"); PWR(f"{c}.2")
text("R101-R103 hold EN / CATH / RELEASE low while the MCU pins are Hi-Z (zero current, electrode shorted); R107 / R108", 7, 107)
text("and R109 / R110 are the I2C pull-ups.  ISO1640: side 1 (pins 1-4) = MCU side, side 2 = DAC side.  C101 at U101.1, C103 at U109.1.", 7, 109)

# =========================================================================== 5. isolated power
box(62, 64, 140, 112, "5. ISOLATED POWER: THE BATTERY PACK OR THE DC-DC POD ON J102, CLAMPS, +5 / -4.3 V")
put("J103", 72, 74, mirror=True, val_at=(0, 5.08))
PWR("J103.1", length=5.08); PWR("J103.2", length=5.08)
put("J102", 72, 92, mirror=True, val_at=(0, 8.89))
e = PWR("J102.1", length=5.08); FLAG(e, up=(-1, 0)); e = PWR("J102.2", length=5.08); FLAG(e, up=(-1, 0))
e = PWR("J102.3", length=5.08); FLAG(e, up=(-1, 0)); PWR("J102.4", length=5.08)       # the pack / pod drive +/-V_STIM and GND_ISO
put("C109", 100, 74); PWR("C109.1"); PWR("C109.2")
put("C110", 100, 96); PWR("C110.1"); PWR("C110.2")
put("D103", 108, 74, rot=90, ref_at=(2.54, -1.27), val_at=(2.54, 1.27)); PWR("D103.1"); PWR("D103.2")     # K up = +V_STIM
put("D104", 108, 96, rot=90, ref_at=(2.54, -1.27), val_at=(2.54, 1.27)); PWR("D104.1"); PWR("D104.2")     # K up = GND_ISO
put("U104", 72, 104, ref_at=(0, -6.35), val_at=(0, 6.35))
PWR("U104.2", length=5.08); PWR("U104.1", length=5.08); PWR("U104.3")
put("C111", 82, 106); PWR("C111.1"); PWR("C111.2")
put("C112", 88, 106); PWR("C112.1"); PWR("C112.2")
put("R113", 96, 106, rot=0); e = PWR("R113.1", length=2.54); FLAG(e, up=(-1, 0)); PWR("R113.2")
put("D102", 102, 106, rot=90, ref_at=(2.54, -1.27), val_at=(2.54, 1.27)); PWR("D102.1"); PWR("D102.2")   # K up = GND_ISO, A = -5V_ISO
put("C113", 108, 106, rot=0); PWR("C113.1"); PWR("C113.2")
text("J102 brings +/-12..16.8 V from the battery pack (pin 4 = pin 2 = GND_ISO: the pack's plug interlock), or from the DC-DC pod", 63, 109)
text("(A0515S + LC filter + capacitance multipliers on its own board) plugged into J102's holes and fed 5 V by J103.  D103 / D104", 63, 111)
text("clamp each rail to 20 V against GND_ISO (ICs are rated 25 V to their ground).  U104: +5V_ISO.  R113 / D102: -4.3 V for the 74HC4053.", 112, 68)

# =========================================================================== 6. set-point
box(6, 114, 95, 164, "6. SET-POINT: DAC60501 (I2C 0x48, 0..1.25 V = VSET_P), U106B INVERTS -> VSET_N, 74HC4053 PICKS SIGN (CATH) AND GATES (EN)")
put("U105", 24, 130, ref_at=(0, -11.43), val_at=(0, 11.43))
W("U105.6", (14, 128), (14, 124)); LBL(None, "SCL", at=pt(14, 124), direction=(0, -1))
W("U105.8", (15.5, 129), (15.5, 124)); LBL(None, "SDA", at=pt(15.5, 124), direction=(0, -1))
W("U105.5", (12, 130), (12, 122), (24, 122), (24, 124.5))   # SPI2C high = I2C mode, tied to the VDD stub end
PWR("U105.1")
W("U105.7", (14, 131), (14, 135)); pwr_at("GND_ISO", 14, 135, (0, 1))   # A0 = AGND -> 0x48
PWR("U105.4")
W("U105.2", (42, 130))                                           # VSET_P
put("C114", 32, 136); W("U105.10", (32, 131), "C114.1"); PWR("C114.2"); lab("VREFIO", 32, 131)
put("C115", 12, 140); PWR("C115.1"); PWR("C115.2")
# inverter U106B
put("U106", 52, 140, unit=2)
put("R105", 45.5, 141, rot=90); put("R106", 52, 147, rot=90)
W((42, 130), (42, 141), "R105.1"); W("R105.2", "U106.6"); LBL("U106.6", length=2.54)
W((48, 141), (48, 147), "R106.1"); W("R106.2", (57, 147), (57, 140))
W("U106.7", (57, 140)); W("U106.5", (48, 139), (48, 137)); pwr_at("GND_ISO", 48, 137, (0, -1))
lab("VSET_P", 44, 130); lab("VSET_N", 57, 144, (0, 1))
# 74HC4053
put("U107", 76, 136, ref_at=(0, -17.78), val_at=(0, 17.78))
W((42, 130), (60, 130), (60, 132), "U107.12"); W((57, 140), (62, 140), (62, 133), "U107.13")     # VSET_P -> 1Y0, VSET_N -> 1Y1
LBL("U107.14", length=2.54)                                       # SW_P
LBL("U107.1", length=2.54)                                        # SW_P -> 2Y1
PWR("U107.2", length=2.54)                                        # 2Y0 = 0 V
LBL("U107.15", length=2.54)                                       # V_IN
PWR("U107.5", length=2.54); PWR("U107.3", length=2.54)            # 3Y0 = +5V_ISO, 3Y1 = GND_ISO
LBL("U107.4", length=2.54)                                        # SHORT_IN
PWR("U107.16"); PWR("U107.8"); PWR("U107.7", length=5.08)
W("U107.6", (76, 148), (76, 150)); pwr_at("GND_ISO", 76, 150, (0, 1))          # ~E low = enabled
LBL("U107.11", length=5.08); LBL("U107.10", length=7.62); LBL("U107.9", length=10.16)
put("C118", 86, 118); put("C119", 91, 118, rot=180)
PWR("C118.1"); PWR("C118.2"); PWR("C119.1"); PWR("C119.2")
text("Switch 1: CATH picks VSET_P (0) / VSET_N (1) -> SW_P.  Switch 2: EN picks 0 V (0) / SW_P (1) -> V_IN.  Switch 3: RELEASE low -> SHORT_IN high", 7, 159)
text("(DG418 on, electrode shorted), high -> low.  Signals stay within +/-1.25 V; the 4053 runs on +5 / -4.3 V (<= 9.7 V worst case of its 10 V recommended maximum).", 7, 161)
text("DAC60501Z: write GAIN (0x04) = 0x0100 first, then DAC (0x08) = code << 4; readback over the same bus.  C115 at U105 VDD, C118 / C119 at U107.", 7, 163)

# =========================================================================== 7. output stage
box(98, 114, 137, 154, "7. OUTPUT STAGE (floating-load V->I, I = V_IN / R116)")
put("U106", 112, 130, unit=1)
put("R114", 104.5, 129, rot=90); put("C120", 107, 130.5)
LBL("R114.1", length=2.54); W("R114.2", "U106.3"); LBL("U106.3", length=2.54); sh.wired.add(("C120", "1")); PWR("C120.2")
put("R115", 118.5, 130, rot=90); put("C121", 124.5, 130, rot=90); put("J101", 132.5, 130.5, val_at=(0, 5.08))
W("U106.1", "R115.1"); LBL("U106.1", length=2.54); W("R115.2", "C121.1"); W("C121.2", "J101.1"); lab("E1_OUT", 127, 130)
W((122, 130), (122, 133)); LBL(None, "E1", at=pt(122, 133), direction=(0, 1))
put("R116", 116, 139.5); put("TP101", 112, 138)
W("U106.2", (108, 131), (108, 138), (129, 138), (129, 131), "J101.2"); sh.wired |= {("R116", "1"), ("TP101", "1")}
W((110, 138), (110, 141)); LBL(None, "ISENSE", at=pt(110, 141), direction=(0, 1))
PWR("R116.2")
put("U106", 104, 120, unit=3); PWR("U106.8"); PWR("U106.4")
put("C116", 110, 120); put("C117", 115, 120, rot=180)
PWR("C116.1"); PWR("C116.2"); PWR("C117.1"); PWR("C117.2")
text("R116 = 2.49 k 0.1 %: 502 uA full scale (0.123 uA / LSB).  C121: 1 uF DC block.  Cable: twisted pair, shield to E2.", 99, 151)

# =========================================================================== 8. SHORT switch
box(98, 156, 137, 190, "8. SHORT (DG418, normally open: on while SHORT_IN is high = RELEASE low)")
put("U108", 118, 166, ref_at=(0, -8.89), val_at=(0, 8.89))
LBL("U108.8", length=2.54); LBL("U108.1", length=2.54); LBL("U108.6", length=2.54)
PWR("U108.4"); PWR("U108.5"); PWR("U108.3"); PWR("U108.7")
text("RELEASE low (idle, HAT unpowered or faulted): E1 shorted to E2 through 20 ohm.  RELEASE high: open, tOFF 100 ns.", 99, 176)
put("C125", 108, 183); put("C126", 113, 183, rot=180)                          # DG418 V+ / V- decouplers
PWR("C125.1"); PWR("C125.2"); PWR("C126.1"); PWR("C126.2")

# =========================================================================== 9. fault detector
box(140, 114, 196, 158, "9. FAULT DETECTOR (TLV1702 window on E1 -> FAULT_n; low also = isolated side unpowered)")
put("R117", 148, 124); put("R118", 148, 133); put("R119", 148, 142)
PWR("R117.1", length=2.54); W("R117.2", "R118.1"); W("R118.2", "R119.1"); PWR("R119.2", length=2.54)
W((148, 128.5), (153, 128.5)); sh.wired.add(("R118", "1")); lab("TH_P", 150, 128.5)
W((148, 137.5), (153, 137.5)); sh.wired.add(("R119", "1")); lab("TH_N", 150, 137.5)
put("U110", 162, 130, unit=2)          # B: + = TH_P, - = E1
put("U110", 162, 143, unit=1)          # A: + = E1, - = TH_N
W((153, 128.5), (153, 129), "U110.5")
W((153, 137.5), (153, 144), "U110.2")
W("U110.6", (156, 131), (156, 122), (144, 122))
W("U110.3", (157, 142), (157, 131))
LBL(None, "E1", at=pt(144, 122), direction=(-1, 0))
W("U110.7", (168, 130), (168, 143)); W("U110.1", (168, 143))
lab("FAULT_OC", 168, 134)
put("R120", 172, 136, rot=90); W((168, 136), "R120.1")
put("R121", 179, 132.5); PWR("R121.1")
put("D101", 179, 140, rot=270, ref_at=(2.54, -1.27), val_at=(2.54, 1.27))
W("R120.2", (179, 136)); W("R121.2", (179, 136)); W("D101.1", (179, 136))
W((179, 136), (186, 136)); LBL(None, "FAULT_n", at=pt(186, 136), direction=(1, 0))
PWR("D101.2")
put("U110", 172, 122, unit=3); put("C122", 176, 122)
for s_ in ("U110.8", "U110.4", "C122.1", "C122.2"):
    PWR(s_)
put("TP102", 190, 148); W("TP102.1", (190, 149)); pwr_at("GND_ISO", 190, 149, (0, 1))
text("Taps at 0.043 x (V+ + |V-|) inside each rail (1.15 V at +/-13.5 V).  FAULT_n low while |E1| is past the trip point,", 141, 153)
text("while +5V_ISO is down and when one rail is missing.  R120 / D101 shift the -V-referenced open collectors to 0..5 V.", 141, 155)

# =========================================================================== 10. mounting
box(200, 64, 240, 84, "10. MOUNTING (M2.5, Pi HAT pattern)")
for i, h in enumerate(("MH1", "MH2", "MH3", "MH4")):
    put(h, 206 + 6 * i, 72, ref_at=(0, -3.81), val_at=(0, 3.81))

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("StimHAT.kicad_sch", "StimHAT: LaserHAT Rev 2 core + isolated constant-current stimulator", "A", "2026-10-29", paper="A1")
print("wrote StimHAT.kicad_sch", n, "bytes")
