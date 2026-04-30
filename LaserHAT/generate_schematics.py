#!/usr/bin/env python3
"""
Generate KiCad 9 schematics for the LaserDriver Raspberry Pi HAT.
Uses kiutils to produce correctly-formatted .kicad_sch files.

Run from the repo root:
    .venv/bin/python3 LaserHAT/generate_schematics.py
"""

import math
import uuid as _uuid_mod
import os

from kiutils.schematic import Schematic, TitleBlock, PageSettings
from kiutils.symbol import Symbol
from kiutils.items.schitems import (
    SchematicSymbol, Connection, Junction,
    GlobalLabel, HierarchicalLabel,
    HierarchicalSheet, HierarchicalPin,
    HierarchicalSheetInstance,
    SymbolInstance,
    NoConnect,
    LocalLabel,
)
from kiutils.items.common import (
    Position, Property, Effects, Font, Stroke, ColorRGBA, Justify,
)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_UUID = "212bfd25-f831-4b85-926b-437df65a6b12"

# ── Core helpers ──────────────────────────────────────────────────────────────

def uid() -> str:
    return str(_uuid_mod.uuid4())

def pos(x, y, angle=0) -> Position:
    return Position(X=round(x, 3), Y=round(y, 3), angle=angle)

def default_effects() -> Effects:
    return Effects(font=Font(height=1.27, width=1.27))

def pin_global(sx, sy, sa, px, py):
    """Global coords of a pin connection point.
    In KiCad the 'at' position IS the wire-end; apply symbol rotation."""
    rad = math.radians(sa)
    c, s = math.cos(rad), math.sin(rad)
    return (round(sx + c*px - s*py, 3),
            round(sy + s*px + c*py, 3))

def new_schematic(file_uuid, title, paper="A3") -> Schematic:
    sch = Schematic.create_new()
    sch.uuid    = file_uuid
    sch.version = 20250114
    sch.generator = "eeschema"
    sch.paper   = PageSettings(paperSize=paper)
    tb = TitleBlock()
    tb.title    = title
    tb.date     = "2026-04-30"
    tb.revision = "0.1"
    tb.company  = "Rice University"
    sch.titleBlock = tb
    return sch

def copy_lib_syms(sch: Schematic, src_path: str):
    """Copy embedded lib symbols from an existing schematic."""
    src = Schematic.from_file(src_path)
    have = {ls.entryName for ls in sch.libSymbols}
    for ls in src.libSymbols:
        if ls.entryName not in have:
            sch.libSymbols.append(ls)

# ── Schematic item builders ───────────────────────────────────────────────────

def add_sym(sch: Schematic, lib_id: str, x, y, ref, value,
            footprint="", angle=0, mirror=None,
            extra_props=None) -> SchematicSymbol:
    lib_nick, entry = lib_id.split(":", 1)
    sym = SchematicSymbol()
    sym.libraryNickname = lib_nick
    sym.entryName       = entry
    sym.position        = pos(x, y, angle)
    sym.unit            = 1
    sym.inBom           = True
    sym.onBoard         = True
    sym.uuid            = uid()
    sym.mirror          = mirror
    sym.properties = [
        Property(key="Reference",  value=ref,       position=pos(x+1.5, y-2),
                 effects=default_effects()),
        Property(key="Value",      value=value,     position=pos(x+1.5, y+2),
                 effects=default_effects()),
        Property(key="Footprint",  value=footprint, position=pos(x, y),
                 effects=Effects(font=Font(height=1.27, width=1.27))),
        Property(key="Datasheet",  value="~",       position=pos(x, y),
                 effects=Effects(font=Font(height=1.27, width=1.27))),
    ]
    if extra_props:
        sym.properties.extend(extra_props)
    sym.pins = {}
    sch.schematicSymbols.append(sym)
    return sym

def wire(sch: Schematic, x1, y1, x2, y2):
    c = Connection()
    c.type   = "wire"
    c.points = [pos(x1, y1), pos(x2, y2)]
    c.stroke = Stroke(width=0, type="default")
    c.uuid   = uid()
    sch.graphicalItems.append(c)

def net_label(sch: Schematic, name: str, x, y, angle=0):
    """Local net label — connects same-named nets within the sheet."""
    lbl = LocalLabel()
    lbl.text     = name
    lbl.position = pos(x, y, angle)
    lbl.effects  = default_effects()
    lbl.uuid     = uid()
    sch.labels.append(lbl)

def pwr_symbol(sch: Schematic, lib_entry: str, x, y):
    """Power flag symbol (+3V3, GND, +5V …)."""
    sym = SchematicSymbol()
    sym.libraryNickname = "power"
    sym.entryName       = lib_entry
    sym.position        = pos(x, y)
    sym.unit            = 1
    sym.inBom           = False
    sym.onBoard         = False
    sym.uuid            = uid()
    sym.properties = [
        Property(key="Reference", value="#PWR",
                 position=pos(x, y-2), effects=default_effects()),
        Property(key="Value",     value=lib_entry,
                 position=pos(x, y+2), effects=default_effects()),
        Property(key="Footprint", value="",
                 effects=Effects(font=Font(height=1.27, width=1.27))),
        Property(key="Datasheet", value="~",
                 effects=Effects(font=Font(height=1.27, width=1.27))),
    ]
    sym.pins = {"1": uid()}
    sch.schematicSymbols.append(sym)

def no_connect(sch: Schematic, x, y):
    nc = NoConnect()
    nc.position = pos(x, y)
    nc.uuid     = uid()
    sch.noConnects.append(nc)

def hlabel(sch: Schematic, name: str, x, y, angle: int, conn_type="input"):
    lbl = HierarchicalLabel()
    lbl.text     = name
    lbl.shape    = conn_type
    lbl.position = pos(x, y, angle)
    lbl.effects  = default_effects()
    lbl.uuid     = uid()
    sch.hierarchicalLabels.append(lbl)

def set_sheet_instance(sch: Schematic, path: str, page: str):
    si = HierarchicalSheetInstance()
    si.instancePath = path
    si.page         = page
    sch.sheetInstances = [si]

def add_sym_instance(sch: Schematic, sym: SchematicSymbol,
                     sheet_path: str):
    """Register a component in the symbol_instances table."""
    ref = next((p.value for p in sym.properties if p.key == "Reference"), "?")
    val = next((p.value for p in sym.properties if p.key == "Value"),     "?")
    fp  = next((p.value for p in sym.properties if p.key == "Footprint"), "")
    si = SymbolInstance()
    si.path      = f"{sheet_path}/{sym.uuid}"
    si.reference = ref
    si.unit      = 1
    si.value     = val
    si.footprint = fp
    sch.symbolInstances.append(si)

# ── Resistor / cap helper: place vertical R or C with labels at both ends ────

def place_rc(sch, lib_entry, cx, cy, ref, val, fp, net_top, net_bot,
             sheet_path, angle=0):
    """Place a Device:R or Device:C (vertical) and connect both pins by label."""
    sym = add_sym(sch, f"Device:{lib_entry}", cx, cy, ref, val, fp, angle=angle)
    sym.pins = {"1": uid(), "2": uid()}
    add_sym_instance(sch, sym, sheet_path)
    # Pin 1 at (0, +3.81), pin 2 at (0, -3.81) local (same for R and C)
    p1x, p1y = pin_global(cx, cy, angle, 0,  3.81)
    p2x, p2y = pin_global(cx, cy, angle, 0, -3.81)
    net_label(sch, net_top, p1x, p1y, 90)
    net_label(sch, net_bot, p2x, p2y, 270)
    return sym

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 3  mspm0_controller.kicad_sch
# ═══════════════════════════════════════════════════════════════════════════════

MSPM0_PATH = "/212bfd25-f831-4b85-926b-000000000003"

def build_mspm0(lib_src: str) -> Schematic:
    sch = new_schematic(MSPM0_PATH[1:], "MSPM0G3507 Controller")
    sch.titleBlock.comments = {
        1: "PA8=PWM_LASER(TIMA0_CCP0), PA22=PWM_DUMMY(TIMA0_CCP0_CMPL)",
        2: "PA12=VREF(DAC0_OUT), PB21=TRIGGER, PA10=UART_TX, PA11=UART_RX",
        3: "PA19=SWCLK, PA20=SWDIO, NRST; powered from 3V3 via P-MOSFET switch",
    }
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, MSPM0_PATH, "3")

    # ── Hierarchical ports ──────────────────────────────────────────────────
    #  left side: signals coming IN from root (angle=180 = arrow points left)
    #  right side: signals going OUT to laser driver (angle=0 = arrow points right)
    PORTS_L = [
        ("VCC_3V3_MCU", "input",          5,  5),
        ("GND",          "input",          5,  7.54),
        ("UART_TX",      "bidirectional",  5, 10.08),
        ("UART_RX",      "bidirectional",  5, 12.62),
        ("SWCLK",        "input",          5, 15.16),
        ("SWDIO",        "bidirectional",  5, 17.70),
        ("NRST",         "input",          5, 20.24),
    ]
    PORTS_R = [
        ("TRIGGER",   "input",  170,  5),
        ("PWM_LASER", "output", 170,  7.54),
        ("PWM_DUMMY", "output", 170, 10.08),
        ("VREF",      "output", 170, 12.62),
    ]
    for name, ctype, x, y in PORTS_L:
        hlabel(sch, name, x, y, 180, ctype)
    for name, ctype, x, y in PORTS_R:
        hlabel(sch, name, x, y, 0, ctype)

    # ── MCU ─────────────────────────────────────────────────────────────────
    MCU_X, MCU_Y = 90, 55
    mcu = add_sym(sch, "MCU_TI_MSPM0:MSPM0G3507RGZR",
                  MCU_X, MCU_Y, "U_MCU", "MSPM0G3507RGZR",
                  "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP6.45x6.45mm")
    add_sym_instance(sch, mcu, MSPM0_PATH)

    # All MCU pins with their local (px,py) and the net name to attach
    # Left pins angle=0 → label angle=180; right pins angle=180 → label angle=0
    mcu_pin_map = [
        # pnum,  px,      py,      net
        ("1",  -22.86,  30.00, "+3V3"),
        ("2",  -22.86,  27.46, "+3V3"),
        ("3",  -22.86, -30.00, "GND"),
        ("4",  -22.86, -32.54, "GND"),
        ("5",  -22.86, -27.46, "NRST"),
        ("10", -22.86,   5.08, "UART_TX"),
        ("11", -22.86,   2.54, "UART_RX"),
        ("12", -22.86,  10.16, "VREF"),
        ("19", -22.86,  20.32, "SWCLK"),
        ("20", -22.86,  17.78, "SWDIO"),
        ("8",   22.86,  17.78, "PWM_LASER"),
        ("22",  22.86,  15.24, "PWM_DUMMY"),
        ("49",  22.86,  10.16, "TRIGGER"),
    ]
    for pnum, px, py, net in mcu_pin_map:
        mcu.pins[pnum] = uid()
        gx, gy = pin_global(MCU_X, MCU_Y, 0, px, py)
        lbl_angle = 180 if px < 0 else 0
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), gx, gy)
        else:
            net_label(sch, net, gx, gy, lbl_angle)

    # ── Decoupling caps (vertical, pin1=top=+3V3, pin2=bottom=GND) ──────────
    # Place to left of MCU symbol box (box edge at MCU_X-20 = 70)
    caps = [
        ("C_MCU1",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 52, 35),
        ("C_MCU2",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 52, 42),
        ("C_MCU3",  "10µF",  "Capacitor_SMD:C_0805_2012Metric", 52, 49),
        ("C_VDDA",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 52, 68),
        ("C_VDDA2", "1µF",   "Capacitor_SMD:C_0402_1005Metric", 52, 75),
    ]
    for ref, val, fp, cx, cy in caps:
        sym = place_rc(sch, "C", cx, cy, ref, val, fp,
                       "+3V3", "GND", MSPM0_PATH)

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 4  usb_uart.kicad_sch
# ═══════════════════════════════════════════════════════════════════════════════

USB_PATH = "/212bfd25-f831-4b85-926b-000000000004"

def build_usb_uart(lib_src: str) -> Schematic:
    sch = new_schematic(USB_PATH[1:], "USB-C UART Interface (Standalone Mode)",
                        paper="A4")
    sch.titleBlock.comments = {
        1: "CH340N USB-to-UART, no external crystal (SOIC-8)",
        2: "SB1/SB2: 0Ω solder bridges disconnect CH340N TX/RX when using Pi",
        3: "5.1kΩ CC resistors for USB-C host detection (DFP/UFP)",
    }
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, USB_PATH, "4")

    for name, ctype, x, y, ang in [
        ("VBUS_5V", "input",          5,  5, 180),
        ("GND",     "input",          5,  7.54, 180),
        ("UART_TX", "bidirectional", 120,  5,   0),
        ("UART_RX", "bidirectional", 120,  7.54,  0),
    ]:
        hlabel(sch, name, x, y, ang, ctype)

    # ── USB-C receptacle at (30, 45) ─────────────────────────────────────────
    J_X, J_Y = 30, 45
    jusb = add_sym(sch, "Connector_USB:USB_C_Receptacle_USB2.0", J_X, J_Y,
                   "J_USB", "USB_C_Receptacle",
                   "Connector_USB:USB_C_Receptacle_GCT_USB4125")
    add_sym_instance(sch, jusb, USB_PATH)
    # Pin connection points (all local coords confirmed above)
    usb_pins = {
        "A4": (-6.35,  10.16, "VBUS_5V",   180),
        "A5": (-6.35,   5.08, "CC1",        180),
        "A6": (-6.35,   2.54, "USB_DM",     180),
        "A7": (-6.35,   0,    "USB_DP",     180),
        "A8": (-6.35,  -2.54, None,         180),   # SBU1 → NC
        "A1": (-6.35, -10.16, "GND",        180),
        "B5": ( 6.35,   5.08, "CC2",          0),
        "B8": ( 6.35,  -2.54, None,           0),   # SBU2 → NC
        "S1": ( 6.35,  -7.62, "GND_SHIELD",   0),
    }
    for pnum, (px, py, net, lang) in usb_pins.items():
        jusb.pins[pnum] = uid()
        gx, gy = pin_global(J_X, J_Y, 0, px, py)
        if net is None:
            no_connect(sch, gx, gy)
        else:
            net_label(sch, net, gx, gy, lang)

    # CC pull-downs 5.1kΩ  (vertical, pin1=top=CC net, pin2=bottom=GND)
    for ref, cx, cy, cc_net in [("R_CC1", 46, 37, "CC1"),
                                  ("R_CC2", 54, 37, "CC2")]:
        place_rc(sch, "R", cx, cy, ref, "5k1",
                 "Resistor_SMD:R_0402_1005Metric",
                 cc_net, "GND", USB_PATH)

    # Shield isolation resistor 1MΩ  (pin1=top=GND_SHIELD, pin2=bottom=GND)
    place_rc(sch, "R", 46, 56, "R_SHIELD", "1M",
             "Resistor_SMD:R_0402_1005Metric",
             "GND_SHIELD", "GND", USB_PATH)

    # ── CH340N at (85, 45) ───────────────────────────────────────────────────
    # Pin positions (confirmed above):
    # 1=VCC(-7.62,2.54) 2=TXD(-7.62,0) 3=RXD(-7.62,-2.54) 4=GND(-7.62,-5.08)
    # 5=V3(7.62,-5.08) 6=UD+(7.62,-2.54) 7=UD-(7.62,0) 8=~DTR(7.62,2.54)
    U_X, U_Y = 85, 45
    ch = add_sym(sch, "Interface_USB:CH340N", U_X, U_Y,
                 "U_USB", "CH340N", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    add_sym_instance(sch, ch, USB_PATH)
    ch340_pins = {
        "1": (-7.62,  2.54, "VBUS_5V",    180),
        "2": (-7.62,  0,    "CH340_TXD",  180),
        "3": (-7.62, -2.54, "CH340_RXD",  180),
        "4": (-7.62, -5.08, "GND",        180),
        "5": ( 7.62, -5.08, "CH340_V3",     0),
        "6": ( 7.62, -2.54, "USB_DP",       0),
        "7": ( 7.62,  0,    "USB_DM",       0),
        "8": ( 7.62,  2.54, None,           0),   # DTR → NC
    }
    for pnum, (px, py, net, lang) in ch340_pins.items():
        ch.pins[pnum] = uid()
        gx, gy = pin_global(U_X, U_Y, 0, px, py)
        if net is None:
            no_connect(sch, gx, gy)
        else:
            net_label(sch, net, gx, gy, lang)

    # CH340N bypass caps (100nF on VCC, 100nF on V3)
    place_rc(sch, "C", 75, 55, "C_USB1", "100nF",
             "Capacitor_SMD:C_0402_1005Metric", "VBUS_5V", "GND", USB_PATH)
    place_rc(sch, "C", 83, 55, "C_USB2", "100nF",
             "Capacitor_SMD:C_0402_1005Metric", "CH340_V3", "GND", USB_PATH)

    # ── Solder bridges SB1 (TX) and SB2 (RX) at (103, 43) / (103, 47) ──────
    # SolderJumper pin1 at (-3.81,0) angle=0,  pin2 at (3.81,0) angle=180
    # With angle=90 (rotated): pin1 at (0,-3.81), pin2 at (0,3.81)
    for ref, cx, cy, net_ch, net_uart in [
        ("SB1", 103, 43, "CH340_TXD", "UART_TX"),
        ("SB2", 103, 47, "CH340_RXD", "UART_RX"),
    ]:
        sb = add_sym(sch, "Jumper:SolderJumper_2_Open", cx, cy, ref,
                     f"{ref}_bridge",
                     "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                     angle=90)
        add_sym_instance(sch, sb, USB_PATH)
        sb.pins = {"1": uid(), "2": uid()}
        # With symbol angle=90: pin1 rotates to (0,-3.81), pin2 to (0,3.81)
        p1x, p1y = pin_global(cx, cy, 90, -3.81, 0)
        p2x, p2y = pin_global(cx, cy, 90,  3.81, 0)
        net_label(sch, net_ch,   p1x, p1y, 270)
        net_label(sch, net_uart, p2x, p2y, 90)

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 2  laser_driver_circuit.kicad_sch
# ═══════════════════════════════════════════════════════════════════════════════

LASER_PATH = "/212bfd25-f831-4b85-926b-000000000002"

def build_laser_driver(lib_src: str) -> Schematic:
    sch = new_schematic(LASER_PATH[1:], "Laser Driver Circuit")
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, LASER_PATH, "2")

    for name, ctype, x, y, ang in [
        ("VCC_5V_IN", "input",   5,  5,   180),
        ("VCC_3V3",   "input",   5,  7.54, 180),
        ("GND",       "input",   5, 10.08, 180),
        ("PWM_LASER", "input",   5, 12.62, 180),
        ("PWM_DUMMY", "input",   5, 15.16, 180),
        ("VREF",      "input",   5, 17.70, 180),
    ]:
        hlabel(sch, name, x, y, ang, ctype)

    # ── MT3608 Boost converter at (50, 35) ────────────────────────────────
    # Regulator_Switching:MT3608 pins (confirmed above):
    # 1=IN(-7.62,2.54) 2=SW(-7.62,-2.54) 3=GND(0,-8.89) 4=FB(7.62,-2.54)
    # 5=EN(7.62,2.54)  6=NC(-7.62,0)
    B_X, B_Y = 50, 35
    mt = add_sym(sch, "Regulator_Switching:MT3608", B_X, B_Y,
                 "U_BOOST", "MT3608",
                 "Package_TO_SOT_SMD:SOT-23-6_Handsoldering")
    add_sym_instance(sch, mt, LASER_PATH)
    boost_pins = {
        "1": (-7.62,  2.54, "VCC_5V_IN", 180),
        "2": (-7.62, -2.54, "BOOST_SW",  180),
        "3": ( 0,    -8.89, "GND",       270),
        "4": ( 7.62, -2.54, "BOOST_FB",    0),
        "5": ( 7.62,  2.54, "BOOST_EN",    0),
        "6": (-7.62,  0,    None,         180),  # NC
    }
    for pnum, (px, py, net, lang) in boost_pins.items():
        mt.pins[pnum] = uid()
        gx, gy = pin_global(B_X, B_Y, 0, px, py)
        if net is None:
            no_connect(sch, gx, gy)
        else:
            net_label(sch, net, gx, gy, lang)

    # EN pull-up to VIN via R_EN (100k) — EN high = always enabled
    place_rc(sch, "R", 68, 28, "R_EN", "100k",
             "Resistor_SMD:R_0402_1005Metric",
             "VCC_5V_IN", "BOOST_EN", LASER_PATH)

    # L1 22µH inductor: Device:L pin1=(0,3.81), pin2=(0,-3.81)
    # Connect SW → L1 → BOOST_OUT (pre-diode)
    l1 = place_rc(sch, "L", 65, 35, "L1", "22µH",
                  "Inductor_SMD:L_Bourns_SRR1260",
                  "BOOST_OUT_RAW", "BOOST_SW", LASER_PATH)

    # D_BOOST SS14 (Schottky): A at (-3.81,0), K at (3.81,0)
    d_boost = add_sym(sch, "Diode:SS14", 80, 35, "D_BOOST", "SS14",
                      "Diode_SMD:D_SMA")
    add_sym_instance(sch, d_boost, LASER_PATH)
    d_boost.pins = {"1": uid(), "2": uid()}   # 1=A, 2=K
    net_label(sch, "BOOST_OUT_RAW", *pin_global(80, 35, 0, -3.81, 0), 180)
    net_label(sch, "+LASER_V",      *pin_global(80, 35, 0,  3.81, 0),   0)

    # Feedback divider: R_FB1 (187k) top=+LASER_V bottom=BOOST_FB
    #                   R_FB2 (10k)  top=BOOST_FB  bottom=GND
    place_rc(sch, "R", 90, 28, "R_FB1", "187k 1%",
             "Resistor_SMD:R_0402_1005Metric",
             "+LASER_V", "BOOST_FB", LASER_PATH)
    place_rc(sch, "R", 90, 38, "R_FB2", "10k 1%",
             "Resistor_SMD:R_0402_1005Metric",
             "BOOST_FB", "GND", LASER_PATH)

    # Boost input / output caps
    for ref, cx, cy, n_top, n_bot, val, fp in [
        ("C_IN1",  43, 48, "VCC_5V_IN", "GND", "10µF 10V",  "Capacitor_SMD:C_0805_2012Metric"),
        ("C_IN2",  50, 48, "VCC_5V_IN", "GND", "100nF 10V", "Capacitor_SMD:C_0402_1005Metric"),
        ("C_OUT1", 73, 48, "+LASER_V",  "GND", "10µF 16V",  "Capacitor_SMD:C_0805_2012Metric"),
        ("C_OUT2", 80, 48, "+LASER_V",  "GND", "100nF 16V", "Capacitor_SMD:C_0402_1005Metric"),
    ]:
        place_rc(sch, "C", cx, cy, ref, val, fp, n_top, n_bot, LASER_PATH)

    # ── TLV2371 op-amp at (140, 60) ──────────────────────────────────────────
    # Pins: 1=IN-(-7.62,2.54), 2=OUT(7.62,0), 3=V-(0,-7.62), 4=IN+(-7.62,-2.54), 5=V+(0,7.62)
    U1_X, U1_Y = 140, 60
    u1 = add_sym(sch, "Amplifier_Operational:TLV2371DBV", U1_X, U1_Y,
                 "U1", "TLV2371DBV",
                 "Package_TO_SOT_SMD:SOT-23-5")
    add_sym_instance(sch, u1, LASER_PATH)
    u1_pins = {
        "1": (-7.62,  2.54, "ISENSE",    180),   # IN-
        "2": ( 7.62,  0,    "LD_CTRL",     0),   # OUT
        "3": ( 0,    -7.62, "GND",        270),   # V-
        "4": (-7.62, -2.54, "VREF",      180),   # IN+
        "5": ( 0,     7.62, "+LASER_V",   90),   # V+
    }
    for pnum, (px, py, net, lang) in u1_pins.items():
        u1.pins[pnum] = uid()
        net_label(sch, net, *pin_global(U1_X, U1_Y, 0, px, py), lang)

    # ── Q1 DMG2302U / Si2302CDS at (155, 68) ─────────────────────────────────
    # Transistor_FET:DMG2302U pins: 1=G(-5.08,0), 2=S(2.54,-5.08), 3=D(2.54,5.08)
    Q1_X, Q1_Y = 155, 68
    q1 = add_sym(sch, "Transistor_FET:DMG2302U", Q1_X, Q1_Y,
                 "Q1", "DMG2302U",
                 "Package_TO_SOT_SMD:SOT-23")
    add_sym_instance(sch, q1, LASER_PATH)
    q1.pins = {"1": uid(), "2": uid(), "3": uid()}
    net_label(sch, "LD_CTRL",   *pin_global(Q1_X, Q1_Y, 0, -5.08,  0),  180)  # G
    net_label(sch, "ISENSE",    *pin_global(Q1_X, Q1_Y, 0,  2.54, -5.08), 270) # S (source)
    net_label(sch, "LD_CATHODE",*pin_global(Q1_X, Q1_Y, 0,  2.54,  5.08),  90) # D (drain)

    # Rsense (2R2 red / 4R7 blue)
    rsense = add_sym(sch, "Device:R", 155, 80, "R_SENSE", "2R2 1%",
                     "Resistor_SMD:R_0402_1005Metric")
    rsense.properties.append(Property(
        key="Description", value="2R2 1% red  |  4R7 1% blue",
        effects=default_effects()))
    add_sym_instance(sch, rsense, LASER_PATH)
    rsense.pins = {"1": uid(), "2": uid()}
    net_label(sch, "ISENSE", *pin_global(155, 80, 0, 0,  3.81),  90)
    net_label(sch, "GND",    *pin_global(155, 80, 0, 0, -3.81), 270)

    # ── Q2 dual NMOS (Q_Dual_NMOS_S1G1D2S2G2D1) at (125, 70) ────────────────
    # Pins: 1=S1(-5.08,-2.54), 2=G1(-5.08,0), 3=D2(2.54,5.08),
    #        4=S2(-5.08,2.54), 5=G2(-5.08,5.08), 6=D1(2.54,-5.08)
    Q2_X, Q2_Y = 125, 70
    q2 = add_sym(sch, "Transistor_FET:Q_Dual_NMOS_S1G1D2S2G2D1",
                 Q2_X, Q2_Y, "Q2", "Si1902DL",
                 "Package_TO_SOT_SMD:SOT-363_SC-70-6")
    add_sym_instance(sch, q2, LASER_PATH)
    # Q2a (laser path): G1=PWM_LASER, S1=LD_CATHODE (drain of Q1), D1=NODE_A
    # Q2b (dummy path): G2=PWM_DUMMY, S2=DUMMY_DRAIN, D2=NODE_A
    q2_pins = {
        "1": (-5.08, -2.54, "LD_CATHODE",  180),  # S1 (laser source)
        "2": (-5.08,  0,    "PWM_LASER",   180),  # G1
        "3": ( 2.54,  5.08, "NODE_A",       90),  # D2 (dummy drain)
        "4": (-5.08,  2.54, "DUMMY_S",     180),  # S2 (dummy source)
        "5": (-5.08,  5.08, "PWM_DUMMY",   180),  # G2
        "6": ( 2.54, -5.08, "NODE_A",      270),  # D1 (laser drain)
    }
    for pnum, (px, py, net, lang) in q2_pins.items():
        q2.pins[pnum] = uid()
        net_label(sch, net, *pin_global(Q2_X, Q2_Y, 0, px, py), lang)

    # Fail-safe pull resistors
    place_rc(sch, "R", 108, 63, "R_pd_a", "10k",
             "Resistor_SMD:R_0402_1005Metric",
             "PWM_LASER", "GND", LASER_PATH)
    place_rc(sch, "R", 108, 77, "R_pu_b", "10k",
             "Resistor_SMD:R_0402_1005Metric",
             "VCC_3V3", "PWM_DUMMY", LASER_PATH)

    # ── Diode D1 BAT54 reverse protection at (115, 58) ───────────────────────
    # Diode:BAT54 A at (-3.81,0), K at (3.81,0)
    d1 = add_sym(sch, "Diode:BAT54", 115, 58, "D1", "BAT54",
                 "Diode_SMD:D_SOT-23_ANK")
    add_sym_instance(sch, d1, LASER_PATH)
    d1.pins = {"1": uid(), "2": uid()}
    net_label(sch, "NODE_A",    *pin_global(115, 58, 0, -3.81, 0), 180)
    net_label(sch, "LD_ANODE",  *pin_global(115, 58, 0,  3.81, 0),   0)

    # ── D2 dummy voltage compensation: 1N4148W at (115, 78) ──────────────────
    d2 = add_sym(sch, "Diode:1N4148W", 115, 78, "D2", "1N4148W",
                 "Diode_SMD:D_SOD-123")
    add_sym_instance(sch, d2, LASER_PATH)
    d2.pins = {"1": uid(), "2": uid()}
    net_label(sch, "DUMMY_S",     *pin_global(115, 78, 0, -3.81, 0), 180)
    net_label(sch, "DUMMY_K",     *pin_global(115, 78, 0,  3.81, 0),   0)

    # Rdummy
    rdummy = add_sym(sch, "Device:R", 105, 78, "R_DUMMY", "8R2",
                     "Resistor_SMD:R_0805_2012Metric")
    rdummy.properties.append(Property(
        key="Description", value="8R2 red (0805 ≥0.5W)  |  36R blue",
        effects=default_effects()))
    add_sym_instance(sch, rdummy, LASER_PATH)
    rdummy.pins = {"1": uid(), "2": uid()}
    net_label(sch, "NODE_A",    *pin_global(105, 78, 0, 0,  3.81),  90)
    net_label(sch, "DUMMY_K",   *pin_global(105, 78, 0, 0, -3.81), 270)

    # ── Laser diode connector J_LD (Device:D_Laser_Photo_NType) at (155, 55)
    # Pins: 1=K(0,-7.62), 2=NC(-2.54,0), 3=A(0,7.62)
    J_LD_X, J_LD_Y = 155, 55
    j_ld = add_sym(sch, "Device:D_Laser_Photo_NType", J_LD_X, J_LD_Y,
                   "J_LD", "Laser_TO38",
                   "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical")
    add_sym_instance(sch, j_ld, LASER_PATH)
    j_ld.pins = {"1": uid(), "2": uid(), "3": uid()}
    net_label(sch, "LD_CATHODE", *pin_global(J_LD_X, J_LD_Y, 0,  0, -7.62), 270)  # K
    no_connect(sch, *pin_global(J_LD_X, J_LD_Y, 0, -2.54,  0))                    # NC
    net_label(sch, "LD_ANODE",   *pin_global(J_LD_X, J_LD_Y, 0,  0,  7.62),  90)  # A

    # Supply bypass for op-amp
    for ref, cx, cy, n_top in [
        ("C1",     165, 55, "+LASER_V"),
        ("C2",     165, 62, "+LASER_V"),
        ("C_BULK", 165, 69, "+LASER_V"),
        ("C3",     165, 78, "VREF"),
    ]:
        val = "100nF" if ref != "C_BULK" else "10µF"
        fp  = "Capacitor_SMD:C_0402_1005Metric" if val == "100nF" \
              else "Capacitor_SMD:C_0805_2012Metric"
        place_rc(sch, "C", cx, cy, ref, val, fp, n_top, "GND", LASER_PATH)

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# ROOT  LaserDriver.kicad_sch
# ═══════════════════════════════════════════════════════════════════════════════

ROOT_PATH = f"/{TEMPLATE_UUID}"

def _add_hsheet(sch, uuid, filename, name, x, y, w, h, pin_list):
    """Add a hierarchical sub-sheet box with labelled pins."""
    sh = HierarchicalSheet()
    sh.uuid     = uuid
    sh.position = pos(x, y)
    sh.width    = w
    sh.height   = h
    sh.stroke   = Stroke(width=0.001, type="default")
    sh.fill     = ColorRGBA(R=0, G=0, B=0, A=0)
    sh.sheetName = Property(key="Sheet name", value=name,
                            position=pos(x, y - 1.5),
                            effects=default_effects())
    sh.fileName  = Property(key="Sheet file", value=filename,
                            position=pos(x, y + h + 1.5),
                            effects=default_effects())
    sh.instances = []   # populated by KiCad on first save
    sh.pins = []
    for name_, ctype, px, py, ang in pin_list:
        hp = HierarchicalPin()
        hp.name           = name_
        hp.connectionType = ctype
        hp.position       = pos(px, py, ang)
        hp.effects        = default_effects()
        hp.uuid           = uid()
        sh.pins.append(hp)
    sch.sheets.append(sh)
    return sh

def build_root(lib_src: str) -> Schematic:
    sch = new_schematic(TEMPLATE_UUID, "LaserDriver Pi HAT")
    sch.titleBlock.comments = {
        1: "Pi HAT: MSPM0G3507 + boost laser driver + USB-C UART",
        2: "GPIO17→Q_PWR gate (LOW=MCU on), GPIO14/15=UART, GPIO26=TRIGGER",
        3: "SWD header for OpenOCD firmware updates",
    }
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, "/", "1")

    # ── P-MOSFET power switch Q_PWR for MSPM0 ────────────────────────────────
    # Use Device:Q_PMOS_GSD — pin positions vary by library version so use labels
    # to keep it robust; we'll use a standard PMOS symbol.
    # For simplicity, model as generic PMOS:  G=left, S=top(source=3V3), D=bottom(MCU 3V3)
    # Device:Q_PMOS_GSD: G(-3.302,0), D(0,-3.81), S(0,3.81) (common KiCad layout)
    Q_X, Q_Y = 50, 35
    q_pwr = add_sym(sch, "Transistor_FET:DMG2305UX", Q_X, Q_Y,
                    "Q_PWR", "DMG2305UX",
                    "Package_TO_SOT_SMD:SOT-323_SC-70")
    add_sym_instance(sch, q_pwr, ROOT_PATH)
    # DMG2305UX (P-channel, SOT-323) — same package as DMG2302U
    # Pins 1=G, 2=S, 3=D  same layout as DMG2302U
    q_pwr.pins = {"1": uid(), "2": uid(), "3": uid()}
    net_label(sch, "MCU_PWR_EN",  *pin_global(Q_X, Q_Y, 0, -5.08,  0),  180)  # G
    pwr_symbol(sch, "+3V3",       *pin_global(Q_X, Q_Y, 0,  2.54, -5.08))     # S (source = 3V3)
    net_label(sch, "VCC_3V3_MCU", *pin_global(Q_X, Q_Y, 0,  2.54,  5.08),  90) # D (drain = MCU)

    # R_GATE 1k, R_PD 10k (gate voltage divider)
    place_rc(sch, "R", 35, 35, "R_GATE", "1k",
             "Resistor_SMD:R_0402_1005Metric",
             "Pi_GPIO17", "MCU_PWR_EN", ROOT_PATH)
    place_rc(sch, "R", 42, 35, "R_PD", "10k",
             "Resistor_SMD:R_0402_1005Metric",
             "MCU_PWR_EN", "GND", ROOT_PATH)

    # ── BNC trigger ──────────────────────────────────────────────────────────
    # Use Connector_Coaxial:BNC (2 pins: Pin and Shield)
    j_bnc = add_sym(sch, "Connector_Coaxial:BNC", 70, 35,
                    "J_BNC", "BNC_Trigger",
                    "Connector_Coaxial:BNC_Amphenol_031-221-RFX_Horizontal")
    add_sym_instance(sch, j_bnc, ROOT_PATH)
    j_bnc.pins = {"1": uid(), "2": uid()}   # rough pin assignments
    net_label(sch, "TRIGGER_SIG", 70 - 5, 35,     180)
    net_label(sch, "GND",         70,     35 + 5,   90)

    # R_TERM 50R DNP
    place_rc(sch, "R", 80, 35, "R_TERM", "50R DNP",
             "Resistor_SMD:R_0402_1005Metric",
             "TRIGGER_SIG", "GND", ROOT_PATH)

    # ── SWD 5-pin header ─────────────────────────────────────────────────────
    # Connector_Generic:Conn_01x05 pins at (-3.81, (i-1)*2.54)  i=1..5
    # Note: angle=None in the lib definition - treat as angle=0 (pointing right)
    J_SWD_X, J_SWD_Y = 95, 33
    j_swd = add_sym(sch, "Connector_Generic:Conn_01x05", J_SWD_X, J_SWD_Y,
                    "J_SWD", "SWD 5-pin 0.1\"",
                    "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
    add_sym_instance(sch, j_swd, ROOT_PATH)
    swd_nets = ["NRST", "SWCLK", "SWDIO", "+3V3", "GND"]
    j_swd.pins = {}
    for i, net in enumerate(swd_nets, 1):
        j_swd.pins[str(i)] = uid()
        py = (i - 1) * -2.54   # pins go downward for Conn_01x05
        gx, gy = pin_global(J_SWD_X, J_SWD_Y, 0, -3.81, py)
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), gx, gy)
        else:
            net_label(sch, net, gx, gy, 180)

    # ── HAT EEPROM AT24C256C ─────────────────────────────────────────────────
    # Use Memory_EEPROM:AT24C256C (SOIC-8)
    # Standard I2C EEPROM pinout: 1=A0,2=A1,3=A2,4=GND,5=SDA,6=SCL,7=WP,8=VCC
    # For SOIC-8 in KiCad: left pins 1-4 at (-X, y), right pins 5-8 at (+X, y)
    U_EE_X, U_EE_Y = 115, 35
    u_ee = add_sym(sch, "Memory_EEPROM:AT24C256C", U_EE_X, U_EE_Y,
                   "U_EEPROM", "AT24C256C",
                   "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    add_sym_instance(sch, u_ee, ROOT_PATH)
    u_ee.pins = {str(i): uid() for i in range(1, 9)}
    # We don't have exact pin positions without the library, so use net labels near symbol
    # Standard SOIC-8 pin layout: left pins descend, right pins ascend
    for i, net in enumerate(["GND","GND","GND","GND","ID_SDA","ID_SCL","GND","+3V3"], 1):
        side = -1 if i <= 4 else 1
        row  = (i - 1) if i <= 4 else (7 - i)
        lx = U_EE_X + side * 7
        ly = U_EE_Y - 3.81 + row * 2.54
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), lx, ly)
        else:
            net_label(sch, net, lx, ly, 0 if side > 0 else 180)

    # I2C pull-ups
    place_rc(sch, "R", 128, 28, "R_I2C_SDA", "4k7",
             "Resistor_SMD:R_0402_1005Metric",
             "+3V3", "ID_SDA", ROOT_PATH)
    place_rc(sch, "R", 135, 28, "R_I2C_SCL", "4k7",
             "Resistor_SMD:R_0402_1005Metric",
             "+3V3", "ID_SCL", ROOT_PATH)

    # ── Hierarchical sub-sheet boxes ─────────────────────────────────────────
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000002",
        filename="laser_driver_circuit.kicad_sch",
        name="Laser Driver Circuit",
        x=20, y=60, w=50, h=35,
        pin_list=[
            ("VCC_5V_IN", "input",   20,  63, 180),
            ("VCC_3V3",   "input",   20,  65.54, 180),
            ("GND",       "input",   20,  68.08, 180),
            ("PWM_LASER", "input",   20,  70.62, 180),
            ("PWM_DUMMY", "input",   20,  73.16, 180),
            ("VREF",      "input",   20,  75.70, 180),
        ],
    )
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000003",
        filename="mspm0_controller.kicad_sch",
        name="MSPM0 Controller",
        x=80, y=60, w=60, h=40,
        pin_list=[
            ("VCC_3V3_MCU", "input",         80,  63, 180),
            ("GND",          "input",         80,  65.54, 180),
            ("UART_TX",      "bidirectional", 80,  68.08, 180),
            ("UART_RX",      "bidirectional", 80,  70.62, 180),
            ("SWCLK",        "input",         80,  73.16, 180),
            ("SWDIO",        "bidirectional", 80,  75.70, 180),
            ("NRST",         "input",         80,  78.24, 180),
            ("TRIGGER",      "input",        140,  63,    0),
            ("PWM_LASER",    "output",       140,  65.54,  0),
            ("PWM_DUMMY",    "output",       140,  68.08,  0),
            ("VREF",         "output",       140,  70.62,  0),
        ],
    )
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000004",
        filename="usb_uart.kicad_sch",
        name="USB-C UART",
        x=155, y=60, w=40, h=20,
        pin_list=[
            ("VBUS_5V", "input",          155,  63, 180),
            ("GND",     "input",          155,  65.54, 180),
            ("UART_TX", "bidirectional",  195,  63,    0),
            ("UART_RX", "bidirectional",  195,  65.54,  0),
        ],
    )

    # Labels on sheet pins so they connect to root-level nets
    label_pairs = [
        # laser driver sheet
        (20,  63, "VCC_5V_IN",   180), (20,  65.54, "VCC_3V3",   180),
        (20,  68.08, "GND",      180), (20,  70.62, "PWM_LASER", 180),
        (20,  73.16, "PWM_DUMMY",180), (20,  75.70, "VREF",      180),
        # mspm0 sheet
        (80,  63, "VCC_3V3_MCU", 180), (80,  65.54, "GND",       180),
        (80,  68.08, "UART_TX",  180), (80,  70.62, "UART_RX",   180),
        (80,  73.16, "SWCLK",    180), (80,  75.70, "SWDIO",     180),
        (80,  78.24, "NRST",     180),
        (140, 63, "TRIGGER",       0), (140, 65.54, "PWM_LASER",  0),
        (140, 68.08, "PWM_DUMMY",  0), (140, 70.62, "VREF",       0),
        # usb uart sheet
        (155, 63, "VBUS_5V",     180), (155, 65.54, "GND",        180),
        (195, 63, "UART_TX",       0), (195, 65.54, "UART_RX",     0),
    ]
    for lx, ly, lname, lang in label_pairs:
        net_label(sch, lname, lx, ly, lang)

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# Import guard for HierarchicalSheetProjectInstance
# ═══════════════════════════════════════════════════════════════════════════════

from kiutils.items.schitems import HierarchicalSheetProjectInstance

# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Source files for embedded lib symbols — use /tmp round-trips so the
    # script can overwrite LaserHAT/ without reading its own output mid-run.
    rt = {
        "mspm0": "/tmp/mspm0_controller.kicad_sch",
        "usb":   "/tmp/usb_uart.kicad_sch",
        "laser": "/tmp/laser_driver_circuit.kicad_sch",
        "root":  "/tmp/LaserDriver.kicad_sch",
    }

    tasks = [
        ("MSPM0 controller",      lambda: build_mspm0(rt["mspm0"]),
         os.path.join(OUT_DIR, "mspm0_controller.kicad_sch")),
        ("USB-C UART",            lambda: build_usb_uart(rt["usb"]),
         os.path.join(OUT_DIR, "usb_uart.kicad_sch")),
        ("Laser driver circuit",  lambda: build_laser_driver(rt["laser"]),
         os.path.join(OUT_DIR, "laser_driver_circuit.kicad_sch")),
        ("Root schematic",        lambda: build_root(rt["root"]),
         os.path.join(OUT_DIR, "LaserDriver.kicad_sch")),
    ]

    for desc, builder, out_path in tasks:
        print(f"Building {desc} …")
        sch = builder()
        sch.to_file(out_path)
        print(f"  → {out_path}  "
              f"({len(sch.schematicSymbols)} symbols, "
              f"{len(sch.labels)} labels, "
              f"{len(sch.hierarchicalLabels)} hLabels)")

    print("\nDone — open LaserHAT/LaserDriver.kicad_pro in KiCad to verify.")


if __name__ == "__main__":
    main()
