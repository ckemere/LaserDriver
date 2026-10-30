#!/usr/bin/env python3
"""
Generates LaserDriverHAT.kicad_sch from sch_parts.py and sch_symbols.py (same engine as the StimHAT, the e-stim module and
the battery pack).  Connectivity inside a block is drawn with wires where it reads better, otherwise with global labels and power
symbols; tools/netcheck.py proves the result equals sch_parts.PARTS.
    python gen_schematic.py        then: python tools/netcheck.py && kicad-cli sch erc LaserDriverHAT.kicad_sch
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


def pwr_jog(spec, dx, dy, net=None):
    """wire from a pin dx grid units sideways, then dy up (-) or down (+), power symbol at the end (clear of neighbouring labels)"""
    ref, num = spec.split(".")
    net = net or BY_REF[ref]["nets"][num]
    (x, y), _ = sh.pin(ref, num)
    gx, gy = x / u, y / u
    W(spec, (gx + dx, gy), (gx + dx, gy + dy))
    return pwr_at(net, gx + dx, gy + dy, (0, -1) if dy < 0 else (0, 1))


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
text("Pi header: 3.3 V (pins 1/17) feeds the ID EEPROM and the I2C pull-ups; 5 V (2/4) the LDO U4.  GPIO9 (pin 21) = NRST, GPIO10 (pin 19) = MCU power", 7, 57)
text("enable, GPIO18 (pin 12) = trigger, GPIO24/25 = SWD, GPIO14/15 = UART; GPIO 4/5/6/17/22/23/27 (the bonnet's buttons) stay free.  No SPI0 / I2S / PWM-on-18 overlays.", 7, 59)
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
for n in ("1", "2", "3", "6", "8", "9", "10", "11", "12", "13", "14", "15", "16"):   # 7 (PA3) is spare
    LBL(f"U7.{n}", length=2.54)
for n in ("17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "30", "31"):   # 28 / 29 (PA24 / PA25) are spare
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
text("Laser lines: PA22 DB_PWM_A (TIMA0_C1), PA23 DB_PWM_B (TIMA0_C3), PA15 DB_DAC (DAC0), PA26 / PA27 DB_ADC_A / B (ADC0 ch 1 / 0).  Joystick SW7 (SKRHADE010, at 135 deg): up PA7,", 103, 57)
text("down PA6, centre PA14, left PA12 (BACK), right PA13 (BUTTON6); FIRE SW9 PA16; LED PA5; all active low.  J10: unpopulated socket for a 0.91 in I2C OLED instead of the bonnet.", 103, 59)

# =========================================================================== 3. BNC I/O
box(202, 8, 252, 40, "3. BNC TRIGGER IN / SYNC OUT (74LVC2G17 buffers)")
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
text("J6 -> R23 1k / R24 100k -> U8A -> PA21 (TIMG8 capture).  PA17 -> U8B -> R25 33 -> J7, D9 mirrors the pulse envelope.  C16 (2.6 mm away) bypasses U8.", 203, 37)

# =========================================================================== 4. laser-diode driver
box(6, 64, 196, 118, "4. LASER-DIODE DRIVER (the LaserDaughter module rev 2.0 on the HAT): 5 V -> 12 V BOOST, LASER_V SELECT, CASCODE STEERING, CURRENT SINK, MONITORS")
# boost: U202 MT3608, L1, D1, C208 / C209, R205 / R206
put("C208", 12, 80); PWR("C208.1"); PWR("C208.2")
put("L1", 24, 74); PWR("L1.1", length=2.54); NET("L1.2", length=2.54)
put("U202", 26, 90, ref_at=(0, -7.62), val_at=(0, 7.62))
(x5, y5), _ = sh.pin("U202", "5"); W("U202.4", (x5 / u - 2, sh.pin("U202", "4")[0][1] / u), (x5 / u - 2, y5 / u)); pwr_jog("U202.5", -2, -2); PWR("U202.2"); NET("U202.1", length=2.54); NET("U202.3", length=2.54)
put("D1", 46, 76); NET("D1.2", length=2.54); e = PWR("D1.1", length=5.08); FLAG(e, up=(-1, 0))     # the boost drives +12V
put("C209", 56, 82); PWR("C209.1"); PWR("C209.2")
put("R205", 62, 82); PWR("R205.1"); NET("R205.2", length=2.54)
put("R206", 68, 92); NET("R206.1", length=2.54); PWR("R206.2")
text("MT3608: FB 0.6 V x (1 + 187k / 10k) = 11.8 V.  Loop C208 -> L1 -> U202 -> D1 -> C209 kept short (module layout).", 7, 104)
# LASER_V select
put("SW5", 80, 78, ref_at=(0, -4.45), val_at=(0, 4.45))
e = PWR("SW5.2", length=5.08); FLAG(e, up=(0, -1)); pwr_jog("SW5.1", 2, -2); pwr_jog("SW5.3", 2, 2)
text("SW5: LASER_V = 12 V (pin 1) or 5 V (pin 3).", 72, 88)
# laser diode socket, PD jumper
put("J2", 100, 80, mirror=True, ref_at=(0, -7.62), val_at=(0, 7.62))
pwr_jog("J2.1", 2, -2); NET("J2.2", length=5.08); NET("J2.3", length=5.08); NET("J2.4", length=5.08)
put("J4", 100, 94, mirror=True, ref_at=(0, -5.08), val_at=(0, 5.08)); NET("J4.1", length=5.08); pwr_jog("J4.2", 2, 2)
# steering pair Q1
put("Q1", 122, 80, ref_at=(0, -7.62), val_at=(0, 7.62))
LBL("Q1.2", length=5.08); NET("Q1.1", length=2.54); LBL("Q1.4", length=5.08); NET("Q1.3", length=2.54)
NET("Q1.8", length=2.54); NET("Q1.7", length=5.08); NET("Q1.6", length=2.54); NET("Q1.5", length=5.08)
text("Q1 AO9926B cascode: gates at 3.3 V (PWM_A laser / PWM_B dummy), sources on Q2's drain (LaserDrive ~2.3 V).", 103, 99)
# dummy load stack
put("D3", 150, 72); NET("D3.1", length=2.54); pwr_jog("D3.2", 1, -2)
put("D2", 150, 82); NET("D2.1", length=2.54); NET("D2.2", length=2.54)
put("D4", 150, 92); NET("D4.1", length=2.54); NET("D4.2", length=2.54)
put("J205", 168, 82, mirror=True, val_at=(0, 5.08)); NET("J205.1", length=5.08); NET("J205.2", length=5.08)
text("Dummy load: LASER_V -> D3 -> D2 2.7 V (J205 RED shorts it) -> D4 2.4 V -> Q1.", 138, 97)
# current sink: Q2, Rs1, U203 servo, set-point divider
put("Q2", 184, 74); NET("Q2.1", length=2.54); NET("Q2.2", length=2.54); NET("Q2.3", length=2.54)
put("Rs1", 190, 86); NET("Rs1.1", length=2.54); PWR("Rs1.2")
put("U203", 182, 100, ref_at=(2.54, -7.62), val_at=(2.54, 7.62)); NET("U203.3", length=2.54); NET("U203.4", length=2.54); NET("U203.1", length=2.54)
PWR("U203.5"); PWR("U203.2")
put("C212", 192, 100); PWR("C212.1"); PWR("C212.2")
put("R203", 150, 108); LBL("R203.1", length=2.54); NET("R203.2", length=2.54)
put("R204", 158, 108); NET("R204.1", length=2.54); PWR("R204.2")
put("C211", 166, 108); NET("C211.1", length=2.54); PWR("C211.2")
# monitors
put("R212", 80, 108); NET("R212.1", length=2.54); PWR("R212.2")
put("R211", 88, 108); LBL("R211.1", length=2.54); NET("R211.2", length=2.54)
put("R201", 112, 108); PWR("R201.1"); LBL("R201.2", length=2.54)
put("R202", 122, 108); LBL("R202.1", length=2.54); PWR("R202.2")
text("I_LD = DB_DAC x 10k / 49k / 2 ohm = 102 mA / V (DAC0 on PA15, zero between pulses).  DB_ADC_A = photodiode across R212 (R211 1k in series),", 7, 114)
text("DB_ADC_B = LASER_V x 33k / 133k (12 V -> 2.98 V).  The module's header lines are nets to U7: PWM_A PA22, PWM_B PA23, DAC PA15, ADC_A PA26, ADC_B PA27.", 7, 116)

# =========================================================================== 10. mounting
box(200, 64, 240, 84, "10. MOUNTING (M2.5, Pi HAT pattern)")
for i, h in enumerate(("MH1", "MH2", "MH3", "MH4")):
    put(h, 206 + 6 * i, 72, ref_at=(0, -3.81), val_at=(0, 3.81))

missing, unplaced, overlaps = sh.finish()
print("missing pins:", missing)
print("unplaced:", unplaced)
print("overlapping wires:", overlaps)
n = sh.write("LaserDriverHAT.kicad_sch", "LaserDriverHAT: LaserHAT Rev 2 core + laser-diode driver", "A", "2026-10-30", paper="A1")
print("wrote LaserDriverHAT.kicad_sch", n, "bytes")
