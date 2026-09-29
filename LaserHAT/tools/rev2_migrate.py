#!/usr/bin/env python3
"""Rev 1 -> Rev 2 schematic migration for the LaserHAT.

Always starts from the Rev 1 files as committed at REV1 (so it is re-runnable),
applies the minimal edits listed below, and writes the result into LaserHAT/.

Rev 2 changes (see REV2_NOTES.md):
  * Pi UART moves to MCU UART2 (PA23 TX -> Pi RXD, PA24 RX <- Pi TXD); fixes the
    Rev 1 TX<->TX wiring.  CH340N keeps UART0 (PA10/PA11, the BSL port) exclusively.
  * Dedicated Pi trigger: GPIO26 -> PA25.
  * PA0/PA1 (5 V-tolerant open-drain I2C0) -> Pi GPIO2/3, so the MCU can drive the
    OLED bonnet stand-alone.  JP5 (normally open) back-feeds HAT +3V3 onto the
    header 3V3 pins for stand-alone use; R19/R20 are the bus pull-ups.
  * Laser-diode power stage leaves the HAT (-> daughterboard); the HAT gets two
    1x5 daughterboard sockets (J8 power/timing, J9 analog).
  * BNC I/O buffered by a 74LVC2G17; right-angle BNCs.
  * USB-C VBUS reaches the Pi 5 V rail through a PFET ideal diode.
  * CH340N V3 tied to VCC (3.3 V operation); MCU EPAD grounded; IC1 (unused
    48-pin MCU) and the eink sheet deleted; LED current reduced.
"""
import os
import subprocess
import sys
import tempfile
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schlib import *  # noqa: E402,F401
from kiutils.schematic import Schematic  # noqa: E402
from kiutils.items.schitems import Text  # noqa: E402
from sexpr_patch import patch  # noqa: E402

REV1 = "a722d88"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HERE)
ROOT_UUID = "e63e39d7-6ac0-4ffd-8aa3-1841a4541b55"
MSPM0_PATH = f"/{ROOT_UUID}/212bfd25-f831-4b85-926b-000000000003"
USB_PATH = f"/{ROOT_UUID}/212bfd25-f831-4b85-926b-000000000004"
IO_SHEET_UUID = "7a1c0d2e-5b4f-4c8e-9d3a-2e6f1b0a9c01"
IO_PATH = f"/{ROOT_UUID}/{IO_SHEET_UUID}"
IO_FILE = "bnc_daughter_io.kicad_sch"

FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_C = "Capacitor_SMD:C_0402_1005Metric"
FP_LED = "Diode_SMD:D_0603_1608Metric"
FP_BNC = "Footprints:SMA_Amphenol_901-143_Horizontal"   # 2026-09-28: right-angle SMA jacks (were 031-5540/5539 BNC dual footprint)
FP_SOCKET = "Connector_PinSocket_2.54mm:PinSocket_1x05_P2.54mm_Vertical"
FP_SJ = "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"


def rev1(name):
    """Load a Rev 1 schematic straight from git."""
    data = subprocess.check_output(["git", "show", f"{REV1}:LaserHAT/{name}"], cwd=REPO)
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    os.write(fd, data)
    os.close(fd)
    sch = Schematic.from_file(path)
    sch._orig = Schematic.from_file(path)     # pristine copy for the diff
    sch._orig_text = data.decode()
    return sch


def text(sch, s, x, y, size=1.27):
    t = Text(text=s.replace("\n", "\\n"), position=Position(X=x, Y=y, angle=0), effects=eff(justify="left"), uuid=uid())
    t.effects.font.height = t.effects.font.width = size
    sch.texts.append(t)


def labels_named(sch, *names):
    return [lb for lb in sch.labels + sch.globalLabels + sch.hierarchicalLabels if lb.text in names]


def drop(sch, lb):
    for coll in (sch.labels, sch.globalLabels, sch.hierarchicalLabels):
        if lb in coll:
            coll.remove(lb)


def pin_label(sch, sym, pin):
    """The label object sitting on a pin tip (Rev 1 MSPM0 style), or None."""
    x, y, _ = sym_pins(sch, sym)[pin]
    for lb in sch.labels + sch.globalLabels + sch.hierarchicalLabels:
        if abs(lb.position.X - x) < 1e-3 and abs(lb.position.Y - y) < 1e-3:
            return lb
    return None


# ═════════════════════════════════════════════════════════════════════════════
# MSPM0 controller sheet
# ═════════════════════════════════════════════════════════════════════════════
def migrate_mspm0():
    s = rev1("mspm0_controller.kicad_sch")
    kw = dict(project="LaserDriver", sheet_path=MSPM0_PATH)

    # IC1: unused 48-pin footprint variant -> delete it and the labels on its pins
    ic1 = find_sym(s, "IC1")
    for n, (x, y, _d) in sym_pins(s, ic1).items():
        wl, labs = trace(s, x, y)
        for lb in labs:
            drop(s, lb)
        for w in wl:
            s.graphicalItems.remove(w)
    s.schematicSymbols.remove(ic1)

    u7 = find_sym(s, "U7")
    for p in u7.properties:                 # Rev 1 field lacked the library nickname
        if p.key == "Footprint":
            p.value = "ELEC327-Kicad:VQFN32_RHB_TEX"
    # Pin map, chosen to untangle the fan-out (tools/pinopt: U7 turned 270 deg, each function on the
    # pin that faces its destination).  Fixed by silicon/ROM: PA0/PA1 I2C0 (5 V-tolerant OD, pins 1-2),
    # NRST 3, PA2 ROSC 6, PA10/PA11 UART0 = BSL 14-15, PA15 DAC 19, PA18 BSL_INVOKE 22, PA19/PA20 SWD 23-24.
    # Re-optimised 2026-09-28 against the hand placement (fewest vias).  I2C stays on PA0/PA1: the only
    # fail-safe open-drain pins, so an unpowered MCU (GPIO23 low) can't clamp the Pi's I2C bus.  The Pi
    # UART moved to UART1 on the west side (pins 12/13), facing the header.
    PIN_MAP = {
        "1": ("I2C_SDA", "global"),        # PA0  I2C0_SDA
        "2": ("I2C_SCL", "global"),        # PA1  I2C0_SCL
        "10": ("DB_GPIO", "global"),       # PA6  GPIO / TIMA0_FAULT0
        "11": ("DB_PWM_A", "global"),      # PA7  TIMA0_CCP1 (EN)
        "12": ("PI_RXD", "global"),        # PA8  UART1_TX -> Pi GPIO15 (RXD)
        "13": ("PI_TXD", "global"),        # PA9  UART1_RX <- Pi GPIO14 (TXD)
        "16": ("DB_PWM_B", "global"),      # PA12 TIMA0_CCP3 (CATH)
        "17": ("BUTTON4", "local"),        # PA13 wheel roll
        "18": ("BUTTON2", "local"),        # PA14 wheel push (select)
        "19": ("DB_DAC", "global"),        # PA15 DAC0 (fixed)
        "20": ("BUTTON3", "local"),        # PA16 wheel roll
        "21": ("DB_ADC_A", "global"),      # PA17 ADC1_2 (e-stim: bit-banged SCK)
        "25": ("BUTTON1", "local"),        # PA21 BACK
        "26": ("DB_ADC_B", "global"),      # PA22 ADC1_8 (e-stim: bit-banged MOSI)
        "27": ("BUTTON5", "local"),        # PA23 FIRE
        "28": ("LED_MCU", "global"),       # PA24 status LED
        "29": ("MCU_STIM_OUT", "global"),  # PA25 -> 74LVC2G17 -> BNC out (TIMG12_CCP1)
        "30": ("MCU_STIM_IN", "global"),   # PA26 <- 74LVC2G17 <- BNC in (TIMG8_CCP0 capture)
        "31": ("PI_TRIGGER", "global"),    # PA27 <- Pi GPIO26 (TIMG7_CCP1 capture)
    }
    SPARE = ("7", "8", "9")                # PA3, PA4, PA5
    for pin, (name, kind) in PIN_MAP.items():
        lb = pin_label(s, u7, pin)
        if lb is not None:
            relabel(s, lb, name, kind=kind)
        else:
            stub_label(s, u7, pin, name, kind=kind)
    for pin in SPARE:
        lb = pin_label(s, u7, pin)
        if lb is not None:
            drop(s, lb)
        x, y, _ = sym_pins(s, u7)[pin]
        no_connect(s, x, y)
    stub_power(s, u7, "33", "power:GND", **kw)          # EPAD -> GND

    # UI buttons: the Rev 1 top-actuated tactiles SW1-SW4 end up under the output
    # module, so they are replaced by edge-operated parts:
    #   SW7 thumbwheel (SHOUHAN BL-DT, LCSC C53223909) on the left edge:
    #       roll = BUTTON3/BUTTON4 (down/up), push = BUTTON2 (select)
    #   SW8 right-angle BACK button on the bottom edge  = BUTTON1
    #   SW9 small FIRE button (TS-1088, like SW6), right edge above MH4 = BUTTON5 (PA22)
    # All switch to GND (active low, MCU internal pull-ups): the commons drop straight into the
    # ground pour instead of dragging MSPM0_3V3 to three board edges.  (SW6 BSL stays active high:
    # the ROM samples PA18 high at reset.)
    for ref in ("SW1", "SW2", "SW3", "SW4"):
        sw = find_sym(s, ref)
        for n, (x, y, _d) in sym_pins(s, sw).items():
            wl, labs = trace(s, x, y)
            for lb in labs:
                drop(s, lb)
            for w in wl:
                s.graphicalItems.remove(w)
        s.schematicSymbols.remove(sw)
    sw7 = add_symbol(s, "LaserHAT:BL-DT", "SW7", "BL-DT (LCSC C53223909)", 99.06, 190.5,
                     footprint="Footprints:SW-SMD_BL-DT", **kw)
    stub_power(s, sw7, "A", "power:GND", **kw)
    stub_label(s, sw7, "C", "BUTTON2", kind="local")
    stub_label(s, sw7, "B", "BUTTON4", kind="local")
    stub_label(s, sw7, "D", "BUTTON3", kind="local")
    sw8 = add_symbol(s, "Switch:SW_Push", "SW8", "BACK", 96.52, 208.28,
                     footprint="Button_Switch_THT:SW_Tactile_SPST_Angled_PTS645Vx39-2LFS", **kw)
    stub_label(s, sw8, "1", "BUTTON1", kind="local")
    stub_power(s, sw8, "2", "power:GND", **kw)
    sw9 = add_symbol(s, "Switch:SW_Push", "SW9", "FIRE", 96.52, 218.44,
                     footprint="Button_Switch_SMD:SW_SPST_TS-1088-xR020", **kw)
    stub_label(s, sw9, "1", "BUTTON5", kind="local")
    stub_power(s, sw9, "2", "power:GND", **kw)
    text(s, "UI: SW7 thumbwheel (left edge) roll = BUTTON3/4, push = BUTTON2 (select)\n"
            "SW8 BACK (bottom edge) = BUTTON1; SW9 FIRE (right edge) = BUTTON5 / PA22",
         60, 175)

    # Hierarchical labels with no parent sheet pin are really local nets
    for lb in list(s.hierarchicalLabels):
        if lb.text.startswith("BUTTON") or lb.text == "MSPM0_BSL_INVOKE":
            relabel(s, lb, lb.text, kind="local")

    text(s, "Rev 2 pin map: PA0/PA1 I2C0 -> Pi GPIO2/3 (OLED bonnet, stand-alone mode)\n"
            "PA8/PA9 UART1 TX/RX <-> Pi (GPIO15 RXD / GPIO14 TXD); PA10/PA11 UART0 <-> CH340N (+BSL)\n"
            "PA27 <- Pi GPIO26 trigger; PA25/PA26 BNC out/in via U8; PA24 status LED\n"
            "Buttons (active LOW, internal pull-ups): PA21 BACK, PA14 select, PA16/PA13 wheel, PA23 FIRE\n"
            "Daughterboard: PA7/PA12 PWM_A/B (TIMA0 CCP1/3), PA15 DAC, PA17/PA22 ADC_A/B, PA6 GPIO (FAULT0)",
         230, 205)
    prune(s)
    return s


# ═════════════════════════════════════════════════════════════════════════════
# USB-C / CH340N sheet
# ═════════════════════════════════════════════════════════════════════════════
def migrate_usb():
    s = rev1("usb_uart.kicad_sch")
    kw = dict(project="LaserDriver", sheet_path=USB_PATH)

    # CH340N at 3.3 V: V3 must be tied to VCC; C5 goes away.
    u6 = find_sym(s, "U6")
    c5 = find_sym(s, "C5")
    x1, y1, _ = sym_pins(s, c5)["1"]
    for w in list(wires(s)):
        if any(abs(p.X - x1) < 1e-3 and abs(p.Y - y1) < 1e-3 for p in w.points):
            s.graphicalItems.remove(w)
    v3x, v3y, _ = sym_pins(s, u6)["8"]
    for w in trace(s, v3x, v3y)[0]:
        s.graphicalItems.remove(w)
    s.schematicSymbols.remove(c5)
    stub_power(s, u6, "8", "power:+3.3V", value="+3V3", **kw)

    # VBUS no longer tied straight to the Pi 5 V rail
    j5 = find_sym(s, "J5")
    vx, vy, _ = sym_pins(s, j5)["A4"]
    for w in trace(s, vx, vy)[0]:
        s.graphicalItems.remove(w)
    prune(s)
    stub_label(s, j5, "A4", "VBUS", kind="local")

    # PFET ideal diode (Pi HAT back-powering guidance): D=VBUS, S=+5V.
    # Q4A (input side) is diode-connected; Q4B turns the PFET off when +5V > VBUS.
    q3 = add_symbol(s, "Transistor_FET:AO3401A", "Q3", "AP30P30Q", 157.48, 40.64,
                    footprint="Footprints:PDFN3333-8_PMOS_GSD", **kw)
    stub_label(s, q3, "3", "VBUS_SW", kind="local")
    stub_power(s, q3, "2", "power:+5V", **kw)
    stub_label(s, q3, "1", "IDEAL_G", kind="local")
    q4a = add_symbol(s, "Transistor_BJT:DMMT5401", "Q4", "DMMT5401", 139.7, 58.42, unit=1,
                     footprint="Package_TO_SOT_SMD:SOT-23-6", **kw)
    stub_label(s, q4a, "6", "VBUS_SW", kind="local")
    stub_label(s, q4a, "2", "IDEAL_B", kind="local")
    stub_label(s, q4a, "1", "IDEAL_B", kind="local")
    q4b = add_symbol(s, "Transistor_BJT:DMMT5401", "Q4", "DMMT5401", 175.26, 58.42, unit=2,
                     footprint="Package_TO_SOT_SMD:SOT-23-6", **kw)
    stub_power(s, q4b, "5", "power:+5V", **kw)
    stub_label(s, q4b, "3", "IDEAL_B", kind="local")
    stub_label(s, q4b, "4", "IDEAL_G", kind="local")
    r21 = add_symbol(s, "Device:R", "R21", "47k", 200.66, 45.72, footprint=FP_R, **kw)
    stub_label(s, r21, "1", "IDEAL_B", kind="local")
    stub_power(s, r21, "2", "power:GND", **kw)
    r22 = add_symbol(s, "Device:R", "R22", "10k", 213.36, 45.72, footprint=FP_R, **kw)
    stub_label(s, r22, "1", "IDEAL_G", kind="local")
    stub_power(s, r22, "2", "power:GND", **kw)
    # USB power switch: Q5 (P-FET, S = VBUS) in series ahead of the ideal diode; the right-angle
    # slide switch SW10 drives only its gate (GND = on; open = off, R26 pulls the gate to VBUS)
    q5 = add_symbol(s, "Transistor_FET:AO3401A", "Q5", "AP30P30Q", 76.2, 45.72,
                    footprint="Footprints:PDFN3333-8_PMOS_GSD", **kw)
    stub_label(s, q5, "2", "VBUS", kind="local")
    stub_label(s, q5, "3", "VBUS_SW", kind="local")
    stub_label(s, q5, "1", "PWR_EN", kind="local")
    r26 = add_symbol(s, "Device:R", "R26", "100k", 55.88, 45.72, footprint=FP_R, **kw)
    stub_label(s, r26, "1", "VBUS", kind="local")
    stub_label(s, r26, "2", "PWR_EN", kind="local")
    sw10 = add_symbol(s, "Switch:SW_SPDT", "SW10", "USB PWR", 45.72, 76.2,
                      footprint="Footprints:SW_SPDT_Shouhan_MSK12C02", **kw)
    stub_label(s, sw10, "2", "PWR_EN", kind="local")
    stub_power(s, sw10, "1", "power:GND", **kw)
    x3, y3, _ = sym_pins(s, sw10)["3"]
    no_connect(s, x3, y3)             # OFF throw left open: R26 holds Q5 off
    text(s, "USB power switch: SW10 (right-angle slide, left edge) -> Q5 gate.\n"
            "PWR_EN = GND: Q5 on, USB-C VBUS reaches the ideal diode.\n"
            "Switch OFF: PWR_EN open, R26 pulls it to VBUS, Q5 off. Only cuts HAT USB-C power.", 30, 20)
    text(s, "USB-C VBUS -> +5V (Pi 5V pins) through a PFET ideal diode:\n"
            "blocks back-feed into the USB host when the Pi has its own supply.\n"
            "A Pi 4 needs a 3 A Type-C source when powered from here.", 130, 20)
    return s


# ═════════════════════════════════════════════════════════════════════════════
# New sheet: BNC I/O + daughterboard sockets
# ═════════════════════════════════════════════════════════════════════════════
def build_io(template):
    s = Schematic.create_new()
    s.version = template.version
    s.generator = "eeschema"
    s.uuid = IO_SHEET_UUID
    s.paper = copy.deepcopy(template.paper)
    s.titleBlock = copy.deepcopy(template.titleBlock)
    s.titleBlock.title = "BNC I/O and daughterboard sockets"
    s.titleBlock.date = "2026-09-25"
    s.titleBlock.revision = "2.0"
    s.titleBlock.comments = {}
    kw = dict(project="LaserDriver", sheet_path=IO_PATH)

    # BNC trigger input: series R + pull-down into a 5 V-tolerant Schmitt buffer
    j6 = add_symbol(s, "Connector:Conn_Coaxial", "J6", "SMA TRIGGER IN", 45.72, 60.96,
                    footprint=FP_BNC, mirror="y", **kw)
    j6.dnp = True                   # shipped loose, soldered by hand
    stub_label(s, j6, "1", "BNC_IN", kind="local")
    stub_power(s, j6, "2", "power:GND", **kw)
    r23 = add_symbol(s, "Device:R", "R23", "1k", 76.2, 60.96, angle=90, footprint=FP_R, **kw)
    stub_label(s, r23, "2", "BNC_IN", kind="local")
    stub_label(s, r23, "1", "BUF_IN", kind="local")
    r24 = add_symbol(s, "Device:R", "R24", "100k", 91.44, 71.12, footprint=FP_R, **kw)
    stub_label(s, r24, "1", "BUF_IN", kind="local")
    stub_power(s, r24, "2", "power:GND", **kw)
    u8a = add_symbol(s, "74xGxx:74LVC2G17", "U8", "74LVC2G17", 121.92, 60.96, unit=1,
                     footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6", **kw)
    stub_label(s, u8a, "1", "BUF_IN", kind="local")
    stub_label(s, u8a, "6", "MCU_STIM_IN", kind="global", shape="output")

    # BNC stim-mirror output
    u8b = add_symbol(s, "74xGxx:74LVC2G17", "U8", "74LVC2G17", 121.92, 101.6, unit=2,
                     footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6", **kw)
    stub_label(s, u8b, "3", "MCU_STIM_OUT", kind="global", shape="input")
    stub_label(s, u8b, "4", "BUF_OUT", kind="local")
    r25 = add_symbol(s, "Device:R", "R25", "33", 157.48, 101.6, angle=90, footprint=FP_R, **kw)
    stub_label(s, r25, "2", "BUF_OUT", kind="local")
    stub_label(s, r25, "1", "BNC_OUT", kind="local")
    j7 = add_symbol(s, "Connector:Conn_Coaxial", "J7", "SMA STIM OUT", 185.42, 101.6,
                    footprint=FP_BNC, **kw)
    j7.dnp = True
    stub_label(s, j7, "1", "BNC_OUT", kind="local")
    stub_power(s, j7, "2", "power:GND", **kw)
    d9 = add_symbol(s, "Device:LED", "D9", "STIM", 157.48, 127, angle=90, footprint=FP_LED, **kw)
    stub_label(s, d9, "2", "BUF_OUT", kind="local")
    stub_label(s, d9, "1", "STIM_LED_K", kind="local")
    r18 = add_symbol(s, "Device:R", "R18", "2k", 157.48, 147.32, footprint=FP_R, **kw)
    stub_label(s, r18, "1", "STIM_LED_K", kind="local")
    stub_power(s, r18, "2", "power:GND", **kw)

    # Buffer supply
    u8c = add_symbol(s, "74xGxx:74LVC2G17", "U8", "74LVC2G17", 91.44, 139.7, unit=3,
                     footprint="Package_TO_SOT_SMD:SOT-363_SC-70-6", **kw)
    stub_label(s, u8c, "5", "MSPM0_3V3", kind="global", shape="input")
    stub_power(s, u8c, "2", "power:GND", **kw)
    c16 = add_symbol(s, "Device:C", "C16", "100nF", 106.68, 139.7, footprint=FP_C, **kw)
    stub_label(s, c16, "1", "MSPM0_3V3", kind="global", shape="input")
    stub_power(s, c16, "2", "power:GND", **kw)

    # Daughterboard sockets (female on the HAT, male pins on the daughterboard)
    j8 = add_symbol(s, "Connector_Generic:Conn_01x05", "J8", "DB_POWER_TIMING", 236.22, 60.96,
                    footprint=FP_SOCKET, **kw)
    stub_power(s, j8, "1", "power:GND", **kw)     # GND on the end pin: pour can always reach it
    stub_power(s, j8, "2", "power:+5V", **kw)
    stub_label(s, j8, "3", "DB_PWM_A", kind="global", shape="output")
    stub_label(s, j8, "4", "DB_PWM_B", kind="global", shape="output")
    stub_label(s, j8, "5", "DB_GPIO", kind="global")
    j9 = add_symbol(s, "Connector_Generic:Conn_01x05", "J9", "DB_ANALOG", 236.22, 101.6,
                    footprint=FP_SOCKET, **kw)
    stub_power(s, j9, "1", "power:GND", **kw)
    stub_label(s, j9, "2", "MSPM0_3V3", kind="global", shape="input")
    stub_label(s, j9, "3", "DB_DAC", kind="global", shape="output")
    stub_label(s, j9, "4", "DB_ADC_A", kind="global", shape="input")
    stub_label(s, j9, "5", "DB_ADC_B", kind="global", shape="input")

    text(s, "BNC IN: 5 V TTL tolerant (74LVC inputs), 100k pull-down, Schmitt trigger.\n"
            "BNC OUT: 3.3 V CMOS from U8 through 33R; STIM LED follows the output.", 30, 30)
    text(s, "Daughterboard interface (two 1x5, 2.54 mm)\n"
            "J8: 1 GND  2 +5V  3 PWM_A (PA21)  4 PWM_B (PA22, complement)  5 GPIO (PA26)\n"
            "J9: 1 GND  2 +3V3 (switched MCU rail)  3 DAC (PA15)  4 ADC_A (PA17)  5 ADC_B (PA16)\n"
            "Laser board: ADC_A = photodiode monitor, ADC_B = compliance-rail divider.",
         200, 130)
    return s


# ═════════════════════════════════════════════════════════════════════════════
# Root sheet
# ═════════════════════════════════════════════════════════════════════════════
def migrate_root(io_sheet_template):
    s = rev1("LaserDriver.kicad_sch")
    kw = dict(project="LaserDriver", sheet_path=f"/{ROOT_UUID}")

    # Remove the eink and laser-driver sheets
    for sh in list(s.sheets):
        if sh.fileName.value in ("eink.kicad_sch", "laser_driver_circuit.kicad_sch"):
            s.sheets.remove(sh)
    for lb in list(s.hierarchicalLabels):
        if lb.text.startswith("EINK_"):
            drop(s, lb)
    # MSPM0 sheet pins that no longer exist; USB sheet's unused 3v3_REG pin
    gone = {"PWM_LASER", "PWM_DUMMY", "MSPM0_DAC", "MSPM0_ADC", "STIM_TRIGGER", "STIM_MIRROR",
            "3v3_REG"}
    for sh in s.sheets:
        sh.pins = [p for p in sh.pins if p.name not in gone]
    for lb in labels_named(s, "STIM_TRIGGER", "STIM_MIRROR", "LASER_V"):
        drop(s, lb)
    # Parts that leave the root: 3V3 LED, RGB compliance LED, BNCs (-> new sheet)
    for ref in ("D6", "R14", "D10", "D11", "R16", "R17", "D9", "R18", "J6", "J7"):
        remove_symbol(s, ref)

    # Pi UART -> MCU UART1 (fixes TX<->TX)
    # (the J1-side labels are the ones left of x=110; the others feed the CH340N)
    for old, new in (("MCU_UART_TX", "PI_TXD"), ("MCU_UART_RX", "PI_RXD")):
        lb = next(l for l in s.hierarchicalLabels if l.text == old and l.position.X < 110)
        relabel(s, lb, new, kind="global")
    # Remaining root hierarchical labels are plain local nets
    for lb in list(s.hierarchicalLabels):
        relabel(s, lb, lb.text, kind="local")
    # SWD swapped at the header so the two traces don't cross (the MCU side is fixed: PA19 SWDIO
    # is pin 23, PA20 SWCLK pin 24): Pi GPIO24 (J1.18) -> SWCLK, GPIO25 (J1.22) -> SWDIO.
    # OpenOCD for Rev 2: make flash OPENOCD_SWCLK=24 OPENOCD_SWDIO=25 (Firmware/Makefile.gcc).
    swd = {lb.text: lb for lb in s.labels
           if lb.text in ("MSPM0_SWDIO", "MSPM0_SWCLK") and abs(lb.position.X - 100.33) < 0.01}
    swd["MSPM0_SWDIO"].text, swd["MSPM0_SWCLK"].text = "MSPM0_SWCLK", "MSPM0_SWDIO"
    # Likewise NRST <-> MCU power enable: Pi GPIO23 (J1.16, nearer the MCU) -> NRST,
    # GPIO18 (J1.12) -> MCU_POWER_EN.  Pi side: power_cycle.py and OPENOCD_SRST=23.
    ctl = {lb.text: lb for lb in s.labels
           if lb.text in ("MSPM0_NRST", "MCU_POWER_EN") and abs(lb.position.X - 100.33) < 0.01}
    ctl["MSPM0_NRST"].text, ctl["MCU_POWER_EN"].text = "MCU_POWER_EN", "MSPM0_NRST"
    # New Pi header nets: I2C1 to the MCU, GPIO26 trigger
    for text_, name in (("GPIO2{slash}SDA1", "I2C_SDA"), ("GPIO3{slash}SCL1", "I2C_SCL"),
                        ("GPIO26", "PI_TRIGGER")):
        lb = next(l for l in s.labels if l.text == text_)
        label(s, name, lb.position.X, lb.position.Y, 180, kind="global")

    # Status LED D7 now driven by PA7; dimmer LEDs (issue #3)
    relabel(s, next(lb for lb in s.globalLabels if lb.text == "MSPM0_3V3"), "LED_MCU",
            kind="global", shape="input")
    set_value(s, "R13", "3k")
    set_value(s, "R15", "2k")
    set_value(s, "D7", "MCU")
    set_value(s, "JP4", "RTS_NRST")
    # Rev 1 leftovers: display TODO (resolved: external OLED bonnet) and a dangling label
    s.texts = [t for t in s.texts if not t.text.startswith("TODO - Add in Rev 2")]
    for lb in list(s.labels):
        if lb.text == "MCU_POWER_EN" and abs(lb.position.X - 156.21) < 0.01:
            drop(s, lb)
    prune(s)

    # Stand-alone (no Pi) jumper + OLED I2C pull-ups
    jp5 = add_symbol(s, "Jumper:SolderJumper_2_Open", "JP5", "STANDALONE_3V3", 228.6, 185.42,
                     footprint=FP_SJ, **kw)
    stub_power(s, jp5, "1", "power:+3.3V", value="+3V3", **kw)
    stub_power(s, jp5, "2", "power:+3.3V", value="RPi +3V3", **kw)
    r19 = add_symbol(s, "Device:R", "R19", "4.7k", 256.54, 185.42, footprint=FP_R, **kw)
    stub_power(s, r19, "1", "power:+3.3V", value="RPi +3V3", **kw)
    stub_label(s, r19, "2", "I2C_SDA", kind="global")
    r20 = add_symbol(s, "Device:R", "R20", "4.7k", 271.78, 185.42, footprint=FP_R, **kw)
    stub_power(s, r20, "1", "power:+3.3V", value="RPi +3V3", **kw)
    stub_label(s, r20, "2", "I2C_SCL", kind="global")
    text(s, "STAND-ALONE MODE (no Pi): close JP5 to power the OLED bonnet from the HAT\n"
            "3.3 V regulator via header pins 1/17.  OPEN JP5 BEFORE PLUGGING INTO A PI.\n"
            "R19/R20: I2C pull-ups for stand-alone use (parallel the Pi's 1k8 otherwise).",
         205, 165)

    # New hierarchical sheet for BNC I/O + daughterboard sockets
    usb = next(sh for sh in s.sheets if sh.fileName.value == "usb_uart.kicad_sch")
    io = copy.deepcopy(usb)
    io.uuid = IO_SHEET_UUID
    io.sheetName.value = "BNC + Daughterboard I/O"
    io.fileName.value = IO_FILE
    io.position.X, io.position.Y = 293.37, 39.37
    io.width, io.height = 55.88, 30.48
    io.sheetName.position.X, io.sheetName.position.Y = 293.37, 38.66
    io.fileName.position.X, io.fileName.position.Y = 293.37, 70.45
    io.pins = []
    for inst in io.instances:
        for p in inst.paths:
            p.page = "5"
    s.sheets.append(io)
    return s


def main():
    mspm0 = migrate_mspm0()
    usb = migrate_usb()
    io = build_io(usb)
    root = migrate_root(io)
    for sch, name in ((mspm0, "mspm0_controller.kicad_sch"), (usb, "usb_uart.kicad_sch"),
                      (root, "LaserDriver.kicad_sch")):
        with open(os.path.join(HERE, name), "w") as f:
            f.write(patch(sch._orig_text, sch._orig, sch))
        print("patched", name)
    io.to_file(os.path.join(HERE, IO_FILE))
    print("wrote", IO_FILE)


if __name__ == "__main__":
    main()
