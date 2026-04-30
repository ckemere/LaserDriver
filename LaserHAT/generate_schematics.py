#!/usr/bin/env python3
"""
Generate KiCad 9 schematics for the LaserDriver Raspberry Pi HAT.
Uses kiutils to produce correctly-formatted .kicad_sch files.

Run from the repo root:
    .venv/bin/python3 LaserHAT/generate_schematics.py

Rules encoded here:
  1. Passive components (R, C, L) hide pin names and pin numbers.
  2. Every signal connection has a wire stub ≥ WIRE_STUB mm before the label.
  3. The laser_driver_circuit sub-sheet is derived from PCB/laser_driver.kicad_sch
     (the hand-validated schematic) with minimal structural additions.
  4. If you add or rearrange a symbol, preserve all other symbol positions exactly.
"""

import math
import uuid as _uuid_mod
import os
import copy

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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR   = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_UUID = "212bfd25-f831-4b85-926b-437df65a6b12"

# Wire stub length (mm).  All pin→label connections use this length.
WIRE_STUB = 5.08   # 200 mil = 5.08 mm

# Passive lib_symbol entry names that should have pin names/numbers hidden.
PASSIVE_ENTRIES = {"R", "C", "L", "C_1", "C_2", "C_3", "Device:R",
                   "Device:C", "Device:L"}

# ── Core helpers ──────────────────────────────────────────────────────────────

def uid() -> str:
    return str(_uuid_mod.uuid4())

def pos(x, y, angle=0) -> Position:
    return Position(X=round(x, 3), Y=round(y, 3), angle=angle)

def default_effects() -> Effects:
    return Effects(font=Font(height=1.27, width=1.27))

def hidden_effects() -> Effects:
    """Effects with hide=True — used for Footprint, Datasheet, Description properties."""
    e = Effects(font=Font(height=1.27, width=1.27))
    e.hide = True
    return e

def pin_global(sx, sy, sa, px, py):
    """Global coords of a pin's wire-connection point.
    In KiCad the pin 'at' coordinates ARE the wire endpoint; apply symbol rotation."""
    rad = math.radians(sa)
    c, s = math.cos(rad), math.sin(rad)
    return (round(sx + c*px - s*py, 3),
            round(sy + s*px + c*py, 3))

def wire_end(px, py, pin_angle, length=WIRE_STUB):
    """Compute the far end of a wire stub leaving a pin.
    The stub goes OPPOSITE to the pin-body direction."""
    rad = math.radians(pin_angle)
    return (round(px - length * math.cos(rad), 3),
            round(py - length * math.sin(rad), 3))

def label_angle_for_pin(pin_angle) -> int:
    """Label angle so its tail faces the component (arrow points away)."""
    return int((pin_angle + 180) % 360)

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

# ── Lib-symbol helpers ────────────────────────────────────────────────────────

def _fix_lib_sym_angles(ls):
    """KiCad requires a number for pin angle.  Default None → 0."""
    for unit in ls.units:
        for pin in unit.pins:
            if pin.position.angle is None:
                pin.position.angle = 0
    for pin in ls.pins:
        if pin.position.angle is None:
            pin.position.angle = 0

def _hide_passive_pins(ls):
    """Rule 1: hide pin names and pin numbers on passive components."""
    ls.pinNames       = True   # must be True for (pin_names hide) to be serialized
    ls.pinNamesHide   = True
    ls.hidePinNumbers = True
    for unit in ls.units:
        for pin in unit.pins:
            if pin.nameEffects:
                pin.nameEffects.hide   = True
            if pin.numberEffects:
                pin.numberEffects.hide = True
    for pin in ls.pins:
        if pin.nameEffects:
            pin.nameEffects.hide   = True
        if pin.numberEffects:
            pin.numberEffects.hide = True

def copy_lib_syms(sch: Schematic, src_path: str):
    """Copy embedded lib symbols from an existing schematic.
    Applies angle fixes and passive-pin hiding automatically."""
    src  = Schematic.from_file(src_path)
    have = {ls.entryName for ls in sch.libSymbols}
    for ls in src.libSymbols:
        if ls.entryName not in have:
            _fix_lib_sym_angles(ls)
            if ls.entryName in PASSIVE_ENTRIES:
                _hide_passive_pins(ls)
            sch.libSymbols.append(ls)

def apply_passive_hiding(sch: Schematic):
    """Apply Rule 1 to all passive lib symbols already in a schematic."""
    for ls in sch.libSymbols:
        _fix_lib_sym_angles(ls)
        if ls.entryName in PASSIVE_ENTRIES:
            _hide_passive_pins(ls)

_SHOW_PROP_KEYS = {"Reference", "Value"}

def hide_extra_properties(sch: Schematic):
    """Hide all schematic symbol properties except Reference and Value (Rule 1 / user rule)."""
    for sym in sch.schematicSymbols:
        for prop in sym.properties:
            if prop.key not in _SHOW_PROP_KEYS:
                if prop.effects is None:
                    prop.effects = hidden_effects()
                else:
                    prop.effects.hide = True

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
                 effects=hidden_effects()),
        Property(key="Datasheet",  value="~",       position=pos(x, y),
                 effects=hidden_effects()),
    ]
    if extra_props:
        sym.properties.extend(extra_props)
    sym.pins = {}
    sch.schematicSymbols.append(sym)
    return sym

def wire(sch: Schematic, x1, y1, x2, y2):
    """Add a wire segment."""
    c = Connection()
    c.type   = "wire"
    c.points = [pos(x1, y1), pos(x2, y2)]
    c.stroke = Stroke(width=0, type="default")
    c.uuid   = uid()
    sch.graphicalItems.append(c)

def net_label(sch: Schematic, name: str, px, py, pin_angle: int):
    """Rule 2: Add a WIRE_STUB wire from the pin, then a local net label.

    px, py     — pin connection point (wire starts here)
    pin_angle  — the angle defined in the lib symbol pin's 'at' clause
                 (determines which way the wire stub runs)
    """
    wx, wy = wire_end(px, py, pin_angle)
    wire(sch, px, py, wx, wy)
    lbl = LocalLabel()
    lbl.text     = name
    lbl.position = pos(wx, wy, label_angle_for_pin(pin_angle))
    lbl.effects  = default_effects()
    lbl.uuid     = uid()
    sch.labels.append(lbl)

def pwr_symbol(sch: Schematic, lib_entry: str, x, y):
    """Place a power symbol (+3V3, GND, +LASER_V …) directly at a pin endpoint."""
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
        Property(key="Footprint", value="",     effects=hidden_effects()),
        Property(key="Datasheet", value="~",    effects=hidden_effects()),
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

def add_sym_instance(sch: Schematic, sym: SchematicSymbol, sheet_path: str):
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

def place_rc(sch, lib_entry, cx, cy, ref, val, fp, net_top, net_bot,
             sheet_path, angle=0):
    """Place a vertical passive (R or C) with 5mm wire stubs at both pins."""
    sym = add_sym(sch, f"Device:{lib_entry}", cx, cy, ref, val, fp, angle=angle)
    sym.pins = {"1": uid(), "2": uid()}
    add_sym_instance(sch, sym, sheet_path)
    # Device:R/C pin 1 at local (0, +3.81) angle=270; pin 2 at (0, -3.81) angle=90
    p1x, p1y = pin_global(cx, cy, angle, 0,  3.81)
    p2x, p2y = pin_global(cx, cy, angle, 0, -3.81)
    net_label(sch, net_top, p1x, p1y, 270)   # pin 1 angle=270 → wire goes down (+Y)
    net_label(sch, net_bot, p2x, p2y, 90)    # pin 2 angle=90  → wire goes up  (-Y)
    return sym

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET 2 — laser_driver_circuit.kicad_sch
# Derived from PCB/laser_driver.kicad_sch (preserves all existing placement).
# Changes made:
#   • Signal rename: DAC→VREF, PWM→PWM_LASER, PWM_INV→PWM_DUMMY
#   • Power rename: +5V→+LASER_V (laser supply rail)
#   • New UUID and sheet instance path
#   • Boost converter section added at x<50 (clear of existing circuit at x≥56)
#   • Hierarchical labels added for sheet ports
#   • Passive pin hiding applied
# ═══════════════════════════════════════════════════════════════════════════════

LASER_PATH = "/212bfd25-f831-4b85-926b-000000000002"
ORIG_LASER = os.path.join(REPO_ROOT, "PCB", "laser_driver.kicad_sch")

# Signal renames from original to HAT naming
_GLABEL_RENAME = {
    "DAC":     "VREF",
    "PWM":     "PWM_LASER",
    "PWM_INV": "PWM_DUMMY",
    "ADC":     "ADC",   # keep ADC if present (photodiode monitor - not used)
}

# Lib symbol entry that maps original +5V to new +LASER_V power net
_PWR_RENAME = {"+5V": "+LASER_V"}

def _make_laser_v_sym():
    """Create a power lib symbol for +LASER_V (12 V boost output).
    Derived from +5V symbol shape."""
    ls = Symbol()
    ls.libraryNickname = "power"
    ls.entryName       = "+LASER_V"
    ls.isPower         = True
    ls.inBom           = True
    ls.onBoard         = True
    # Borrow the graphical shape from an existing +5V instance via raw sexpr copy
    # We just need it to be a valid power symbol – kiutils will handle the rest
    from kiutils.items.common import Effects, Font
    from kiutils.symbol import SymbolPin
    # Properties
    ref_prop = Property(key="Reference", value="#PWR",
                        position=pos(0, -1), effects=default_effects())
    val_prop = Property(key="Value",     value="+LASER_V",
                        position=pos(0,  3.81), effects=default_effects())
    fp_prop  = Property(key="Footprint", value="",
                        effects=Effects(font=Font(height=1.27, width=1.27)))
    ds_prop  = Property(key="Datasheet", value="~",
                        effects=Effects(font=Font(height=1.27, width=1.27)))
    ls.properties = [ref_prop, val_prop, fp_prop, ds_prop]

    # Build two units: unit 0 = graphics, unit 1 = pin
    from kiutils.symbol import Symbol as Sym
    u0 = Sym(unitId=0, styleId=1)
    u0.entryName = "+LASER_V"   # prevents serialization as "None_0_1"
    from kiutils.items.schitems import PolyLine
    # Up-arrow shape (same as +5V)
    pl1 = PolyLine()
    pl1.points = [pos(-0.762, 0.762), pos(0, 1.524)]
    pl1.stroke = Stroke(width=0, type="default")
    u0.graphicItems.append(pl1)
    pl2 = PolyLine()
    pl2.points = [pos(0, 0), pos(0, 1.524)]
    pl2.stroke = Stroke(width=0, type="default")
    u0.graphicItems.append(pl2)
    pl3 = PolyLine()
    pl3.points = [pos(0, 1.524), pos(0.762, 0.762)]
    pl3.stroke = Stroke(width=0, type="default")
    u0.graphicItems.append(pl3)
    ls.units.append(u0)

    u1 = Sym(unitId=1, styleId=1)
    u1.entryName = "+LASER_V"   # prevents serialization as "None_1_1"
    pin = SymbolPin()
    pin.electricalType  = "power_in"
    pin.graphicalStyle  = "line"
    pin.position        = pos(0, 0, 270)
    pin.length          = 0
    pin.name            = "~"
    pin.number          = "1"
    from kiutils.items.common import Effects as Eff
    pin.nameEffects   = Eff(font=Font(height=1.27, width=1.27))
    pin.numberEffects = Eff(font=Font(height=1.27, width=1.27))
    u1.pins.append(pin)
    ls.units.append(u1)
    return ls

def build_laser_driver() -> Schematic:
    """Load the hand-validated PCB/laser_driver.kicad_sch and transform it
    into the laser_driver_circuit sub-sheet for the HAT design."""
    src = Schematic.from_file(ORIG_LASER)

    # ── Fix up lib symbols and symbol properties ──────────────────────────────
    apply_passive_hiding(src)
    hide_extra_properties(src)

    # Rename +5V lib symbol to +LASER_V
    have_laser_v = any(ls.entryName == "+LASER_V" for ls in src.libSymbols)
    if not have_laser_v:
        src.libSymbols.append(_make_laser_v_sym())
    for ls in src.libSymbols:
        _fix_lib_sym_angles(ls)

    # ── Rename global labels ──────────────────────────────────────────────────
    for gl in src.globalLabels:
        gl.text = _GLABEL_RENAME.get(gl.text, gl.text)

    # ── Rename +5V power symbols to +LASER_V ─────────────────────────────────
    for sym in src.schematicSymbols:
        if sym.entryName in _PWR_RENAME:
            new_entry = _PWR_RENAME[sym.entryName]
            sym.entryName = new_entry
            for prop in sym.properties:
                if prop.key == "Value":
                    prop.value = new_entry

    # ── Update UUID and title ─────────────────────────────────────────────────
    src.uuid = LASER_PATH[1:]   # strip leading /
    src.titleBlock = TitleBlock()
    src.titleBlock.title    = "Laser Driver Circuit"
    src.titleBlock.date     = "2026-04-30"
    src.titleBlock.revision = "0.1"
    src.titleBlock.company  = "Rice University"
    src.titleBlock.comments = {
        1: "Derived from PCB/laser_driver.kicad_sch — existing layout preserved",
        2: "+LASER_V = 12V from MT3608 boost (see boost section at left)",
        3: "Q2 must be Si1902DL (1.25A) for red laser; BSS138DW ok for blue",
    }
    src.paper = PageSettings(paperSize="A3")

    # ── Add hierarchical port labels (at left margin, clear of existing circuit) ─
    # Existing circuit occupies x≈56–245, y≈25–133
    # Place port labels at x=10 (left margin)
    PORT_X = 10
    ports = [
        ("VCC_5V_IN", "input",   PORT_X,  20, 180),
        ("VCC_3V3",   "input",   PORT_X,  25, 180),
        ("GND",       "input",   PORT_X,  30, 180),
        ("PWM_LASER", "input",   PORT_X,  35, 180),
        ("PWM_DUMMY", "input",   PORT_X,  40, 180),
        ("VREF",      "input",   PORT_X,  45, 180),
    ]
    for name, ctype, x, y, ang in ports:
        hlabel(src, name, x, y, ang, ctype)

    # ── Set sheet instance ────────────────────────────────────────────────────
    set_sheet_instance(src, LASER_PATH, "2")

    # ── Add boost converter section ───────────────────────────────────────────
    # Place entirely to the left of the existing circuit (x < 50)
    # Existing boost lib symbols come from /tmp/laser_driver_circuit.kicad_sch
    # We add them manually here.

    # We need Regulator_Switching:MT3608, Device:L, Diode:SS14 lib syms.
    # Copy from the round-tripped file which has them embedded.
    rt_laser = "/tmp/laser_driver_circuit.kicad_sch"
    if os.path.exists(rt_laser):
        rt = Schematic.from_file(rt_laser)
        have = {ls.entryName for ls in src.libSymbols}
        for ls in rt.libSymbols:
            if ls.entryName not in have:
                _fix_lib_sym_angles(ls)
                if ls.entryName in PASSIVE_ENTRIES:
                    _hide_passive_pins(ls)
                src.libSymbols.append(ls)

    # Boost component positions (all x < 50 so they don't overlap original circuit)
    # MT3608 pins: 1=IN(-7.62,2.54), 2=SW(-7.62,-2.54), 3=GND(0,-8.89),
    #              4=FB(7.62,-2.54), 5=EN(7.62,2.54), 6=NC(-7.62,0)
    B_X, B_Y = 30, 70
    mt = add_sym(src, "Regulator_Switching:MT3608", B_X, B_Y,
                 "U_BOOST", "MT3608",
                 "Package_TO_SOT_SMD:SOT-23-6_Handsoldering")
    add_sym_instance(src, mt, LASER_PATH)
    boost_pins = {
        "1": (-7.62,  2.54, "VCC_5V_IN",  0,   180),
        "2": (-7.62, -2.54, "BOOST_SW",   0,   180),
        "3": ( 0,    -8.89, "GND",        90,  270),
        "4": ( 7.62, -2.54, "BOOST_FB",   180,   0),
        "5": ( 7.62,  2.54, "BOOST_EN",   180,   0),
        "6": (-7.62,  0,    None,         0,   180),
    }
    for pnum, (px, py, net, pin_ang, _) in boost_pins.items():
        mt.pins[pnum] = uid()
        gx, gy = pin_global(B_X, B_Y, 0, px, py)
        if net is None:
            no_connect(src, gx, gy)
        else:
            net_label(src, net, gx, gy, pin_ang)

    # EN pull-up to VIN (100k, always enabled)
    place_rc(src, "R", 20, 55, "R_EN", "100k",
             "Resistor_SMD:R_0402_1005Metric",
             "VCC_5V_IN", "BOOST_EN", LASER_PATH)

    # L1 22µH — Device:L pin1=(0,3.81) angle=270, pin2=(0,-3.81) angle=90
    l1 = place_rc(src, "L", 42, 58, "L1", "22µH",
                  "Inductor_SMD:L_Bourns_SRR1260",
                  "BOOST_OUT_SW", "BOOST_SW", LASER_PATH)

    # D_BOOST SS14: A at (-3.81,0) angle=0, K at (3.81,0) angle=180
    d_boost = add_sym(src, "Diode:SS14", 42, 70, "D_BOOST", "SS14",
                      "Diode_SMD:D_SMA")
    add_sym_instance(src, d_boost, LASER_PATH)
    d_boost.pins = {"1": uid(), "2": uid()}
    net_label(src, "BOOST_OUT_SW", *pin_global(42, 70, 0, -3.81, 0), 0)
    net_label(src, "+LASER_V",     *pin_global(42, 70, 0,  3.81, 0), 180)

    # Feedback divider
    place_rc(src, "R", 30, 90, "R_FB1", "187k 1%",
             "Resistor_SMD:R_0402_1005Metric",
             "+LASER_V", "BOOST_FB", LASER_PATH)
    place_rc(src, "R", 30, 105, "R_FB2", "10k 1%",
             "Resistor_SMD:R_0402_1005Metric",
             "BOOST_FB", "GND", LASER_PATH)

    # Boost caps
    for ref, cx, cy, n_top, val, fp in [
        ("C_IN1",  20, 70, "VCC_5V_IN", "10µF 10V",  "Capacitor_SMD:C_0805_2012Metric"),
        ("C_IN2",  20, 80, "VCC_5V_IN", "100nF 10V", "Capacitor_SMD:C_0402_1005Metric"),
        ("C_OUT1", 42, 80, "+LASER_V",  "10µF 16V",  "Capacitor_SMD:C_0805_2012Metric"),
        ("C_OUT2", 42, 90, "+LASER_V",  "100nF 16V", "Capacitor_SMD:C_0402_1005Metric"),
    ]:
        place_rc(src, "C", cx, cy, ref, val, fp, n_top, "GND", LASER_PATH)

    return src


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

    # Hierarchical port declarations (sheet interface)
    for name, ctype, x, y, ang in [
        ("VCC_3V3_MCU", "input",          5,  20, 180),
        ("GND",          "input",          5,  30, 180),
        ("UART_TX",      "bidirectional",  5,  40, 180),
        ("UART_RX",      "bidirectional",  5,  50, 180),
        ("SWCLK",        "input",          5,  60, 180),
        ("SWDIO",        "bidirectional",  5,  70, 180),
        ("NRST",         "input",          5,  80, 180),
        ("TRIGGER",      "input",         200,  20,   0),
        ("PWM_LASER",    "output",        200,  30,   0),
        ("PWM_DUMMY",    "output",        200,  40,   0),
        ("VREF",         "output",        200,  50,   0),
    ]:
        hlabel(sch, name, x, y, ang, ctype)

    # ── MCU placed centrally on an A3 sheet ──────────────────────────────────
    MCU_X, MCU_Y = 100, 80
    # Symbol box ±20 wide, ±35 tall
    # Left pins at global x = 100 − 22.86 = 77.14
    # Right pins at global x = 100 + 22.86 = 122.86

    mcu = add_sym(sch, "MCU_TI_MSPM0:MSPM0G3507RGZR",
                  MCU_X, MCU_Y, "U_MCU", "MSPM0G3507RGZR",
                  "Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP6.45x6.45mm")
    add_sym_instance(sch, mcu, MSPM0_PATH)

    mcu_pin_map = [
        # pin,  local_x,  local_y,  net,         pin_angle
        ("1",  -22.86,  30.00, "+3V3",       0),
        ("2",  -22.86,  27.46, "+3V3",       0),
        ("3",  -22.86, -30.00, "GND",        0),
        ("4",  -22.86, -32.54, "GND",        0),
        ("5",  -22.86, -27.46, "NRST",       0),
        ("10", -22.86,   5.08, "UART_TX",    0),
        ("11", -22.86,   2.54, "UART_RX",    0),
        ("12", -22.86,  10.16, "VREF",       0),
        ("19", -22.86,  20.32, "SWCLK",      0),
        ("20", -22.86,  17.78, "SWDIO",      0),
        ("8",   22.86,  17.78, "PWM_LASER", 180),
        ("22",  22.86,  15.24, "PWM_DUMMY", 180),
        ("49",  22.86,  10.16, "TRIGGER",   180),
    ]
    for pnum, px, py, net, pin_ang in mcu_pin_map:
        mcu.pins[pnum] = uid()
        gx, gy = pin_global(MCU_X, MCU_Y, 0, px, py)
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), gx, gy)
        else:
            net_label(sch, net, gx, gy, pin_ang)

    # Decoupling caps — placed well clear of MCU box (box edge at x=80, x=120)
    # Spread vertically to the left of the MCU
    caps = [
        ("C_MCU1",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 60, 42),
        ("C_MCU2",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 60, 55),
        ("C_MCU3",  "10µF",  "Capacitor_SMD:C_0805_2012Metric", 60, 68),
        ("C_VDDA",  "100nF", "Capacitor_SMD:C_0402_1005Metric", 60, 100),
        ("C_VDDA2", "1µF",   "Capacitor_SMD:C_0402_1005Metric", 60, 113),
    ]
    for ref, val, fp, cx, cy in caps:
        place_rc(sch, "C", cx, cy, ref, val, fp, "+3V3", "GND", MSPM0_PATH)

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
        2: "SB1/SB2: solder bridges — installed=USB-C active, remove=Pi UART mode",
        3: "5.1kΩ CC resistors for USB-C UFP (device) detection",
    }
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, USB_PATH, "4")

    for name, ctype, x, y, ang in [
        ("VBUS_5V", "input",           5,  20, 180),
        ("GND",     "input",           5,  30, 180),
        ("UART_TX", "bidirectional",  200,  20,   0),
        ("UART_RX", "bidirectional",  200,  30,   0),
    ]:
        hlabel(sch, name, x, y, ang, ctype)

    # ── USB-C connector ──────────────────────────────────────────────────────
    J_X, J_Y = 45, 60
    jusb = add_sym(sch, "Connector_USB:USB_C_Receptacle_USB2.0", J_X, J_Y,
                   "J_USB", "USB_C_Receptacle",
                   "Connector_USB:USB_C_Receptacle_GCT_USB4125")
    add_sym_instance(sch, jusb, USB_PATH)
    # Confirmed pin positions: all pins point left (angle=0) or right (angle=180)
    usb_pins = {
        "A4": (-6.35,  10.16, "VBUS_5V",    0),
        "A5": (-6.35,   5.08, "CC1",         0),
        "A6": (-6.35,   2.54, "USB_DM",      0),
        "A7": (-6.35,   0,    "USB_DP",      0),
        "A8": (-6.35,  -2.54, None,          0),
        "A1": (-6.35, -10.16, "GND",         0),
        "B5": ( 6.35,   5.08, "CC2",        180),
        "B8": ( 6.35,  -2.54, None,         180),
        "S1": ( 6.35,  -7.62, "GND_SHIELD", 180),
    }
    for pnum, (px, py, net, pin_ang) in usb_pins.items():
        jusb.pins[pnum] = uid()
        gx, gy = pin_global(J_X, J_Y, 0, px, py)
        if net is None:
            no_connect(sch, gx, gy)
        else:
            net_label(sch, net, gx, gy, pin_ang)

    # CC pull-downs — spread out, not stacked
    place_rc(sch, "R", 65, 50, "R_CC1", "5k1",
             "Resistor_SMD:R_0402_1005Metric", "CC1", "GND", USB_PATH)
    place_rc(sch, "R", 80, 50, "R_CC2", "5k1",
             "Resistor_SMD:R_0402_1005Metric", "CC2", "GND", USB_PATH)

    # Shield isolation resistor
    place_rc(sch, "R", 65, 75, "R_SHIELD", "1M",
             "Resistor_SMD:R_0402_1005Metric", "GND_SHIELD", "GND", USB_PATH)

    # ── CH340N ───────────────────────────────────────────────────────────────
    U_X, U_Y = 115, 60
    ch = add_sym(sch, "Interface_USB:CH340N", U_X, U_Y,
                 "U_USB", "CH340N", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    add_sym_instance(sch, ch, USB_PATH)
    ch340_pins = {
        "1": (-7.62,  2.54, "VBUS_5V",   0),
        "2": (-7.62,  0,    "CH340_TXD", 0),
        "3": (-7.62, -2.54, "CH340_RXD", 0),
        "4": (-7.62, -5.08, "GND",       0),
        "5": ( 7.62, -5.08, "CH340_V3", 180),
        "6": ( 7.62, -2.54, "USB_DP",   180),
        "7": ( 7.62,  0,    "USB_DM",   180),
        "8": ( 7.62,  2.54, None,       180),
    }
    for pnum, (px, py, net, pin_ang) in ch340_pins.items():
        ch.pins[pnum] = uid()
        gx, gy = pin_global(U_X, U_Y, 0, px, py)
        if net is None:
            no_connect(sch, gx, gy)
        else:
            net_label(sch, net, gx, gy, pin_ang)

    # CH340N bypass caps
    place_rc(sch, "C", 100, 75, "C_USB1", "100nF",
             "Capacitor_SMD:C_0402_1005Metric", "VBUS_5V",  "GND", USB_PATH)
    place_rc(sch, "C", 115, 75, "C_USB2", "100nF",
             "Capacitor_SMD:C_0402_1005Metric", "CH340_V3", "GND", USB_PATH)

    # ── Solder bridges ───────────────────────────────────────────────────────
    # SolderJumper_2_Open: pin1 at (-3.81,0) angle=0, pin2 at (3.81,0) angle=180
    # Rotate 90° → pin1 at (0,-3.81) angle=90 (pointing up), pin2 at (0,3.81) angle=270
    for ref, cx, cy, net_ch, net_uart in [
        ("SB1", 145, 58, "CH340_TXD", "UART_TX"),
        ("SB2", 145, 68, "CH340_RXD", "UART_RX"),
    ]:
        sb = add_sym(sch, "Jumper:SolderJumper_2_Open", cx, cy, ref,
                     f"{ref}_bridge",
                     "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
                     angle=90)
        add_sym_instance(sch, sb, USB_PATH)
        sb.pins = {"1": uid(), "2": uid()}
        # With symbol rotated 90°: pin1 local(-3.81,0) → global(cx, cy-3.81)
        # pin angle in rotated symbol: original 0° + 90° symbol = 90° effective
        p1x, p1y = pin_global(cx, cy, 90, -3.81, 0)
        p2x, p2y = pin_global(cx, cy, 90,  3.81, 0)
        net_label(sch, net_ch,   p1x, p1y, 90)   # pin1 effective angle=90
        net_label(sch, net_uart, p2x, p2y, 270)  # pin2 effective angle=270

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# ROOT  LaserDriver.kicad_sch
# ═══════════════════════════════════════════════════════════════════════════════

ROOT_PATH = f"/{TEMPLATE_UUID}"

def _add_hsheet(sch, uuid, filename, name, x, y, w, h, pin_list):
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
    sh.instances = []
    sh.pins = []
    for pname, ctype, px, py, ang in pin_list:
        hp = HierarchicalPin()
        hp.name           = pname
        hp.connectionType = ctype
        hp.position       = pos(px, py, ang)
        hp.effects        = default_effects()
        hp.uuid           = uid()
        sh.pins.append(hp)
        # Wire stub + label on each sheet pin (Rule 2)
        # Sheet pins: angle 180 = pin points left (wire stub goes right)
        #             angle   0 = pin points right (wire stub goes left)
        pin_ang = ang
        wx, wy = wire_end(px, py, pin_ang)
        wire(sch, px, py, wx, wy)
        lbl = LocalLabel()
        lbl.text     = pname
        lbl.position = pos(wx, wy, label_angle_for_pin(pin_ang))
        lbl.effects  = default_effects()
        lbl.uuid     = uid()
        sch.labels.append(lbl)
    sch.sheets.append(sh)
    return sh

def build_root(lib_src: str) -> Schematic:
    sch = new_schematic(TEMPLATE_UUID, "LaserDriver Pi HAT")
    sch.titleBlock.comments = {
        1: "Pi HAT: MSPM0G3507 + MT3608 boost + laser driver + USB-C UART",
        2: "GPIO17=MCU power switch, GPIO14/15=UART, GPIO26=TRIGGER",
        3: "SWD 5-pin header for OpenOCD firmware updates (NRST/SWCLK/SWDIO/3V3/GND)",
    }
    copy_lib_syms(sch, lib_src)
    set_sheet_instance(sch, "/", "1")

    # ── P-MOSFET power switch for MSPM0 ──────────────────────────────────────
    # DMG2302U used as PMOS substitute (same package/footprint as DMG2305UX)
    # Pins: 1=G(-5.08,0), 2=S(2.54,-5.08), 3=D(2.54,5.08)
    Q_X, Q_Y = 60, 40
    q_pwr = add_sym(sch, "Transistor_FET:DMG2302U", Q_X, Q_Y,
                    "Q_PWR", "DMG2305UX",
                    "Package_TO_SOT_SMD:SOT-323_SC-70")
    add_sym_instance(sch, q_pwr, ROOT_PATH)
    q_pwr.pins = {"1": uid(), "2": uid(), "3": uid()}
    net_label(sch, "MCU_PWR_EN",  *pin_global(Q_X, Q_Y, 0, -5.08,  0),   0)
    pwr_symbol(sch, "+3V3",        *pin_global(Q_X, Q_Y, 0,  2.54, -5.08))
    net_label(sch, "VCC_3V3_MCU", *pin_global(Q_X, Q_Y, 0,  2.54,  5.08), 270)

    # R_GATE 1kΩ (Pi GPIO17 → Q_PWR gate)
    place_rc(sch, "R", 40, 40, "R_GATE", "1k",
             "Resistor_SMD:R_0402_1005Metric",
             "Pi_GPIO17", "MCU_PWR_EN", ROOT_PATH)

    # R_PD 10kΩ (gate to GND pull-down → MSPM0 ON by default when Pi is off)
    place_rc(sch, "R", 50, 40, "R_PD", "10k",
             "Resistor_SMD:R_0402_1005Metric",
             "MCU_PWR_EN", "GND", ROOT_PATH)

    # ── BNC trigger + 50R termination ────────────────────────────────────────
    j_bnc = add_sym(sch, "Connector_Coaxial:BNC", 90, 40,
                    "J_BNC", "BNC_Trigger",
                    "Connector_Coaxial:BNC_Amphenol_031-221-RFX_Horizontal")
    add_sym_instance(sch, j_bnc, ROOT_PATH)
    j_bnc.pins = {"1": uid(), "2": uid()}
    net_label(sch, "TRIGGER_SIG", 90 - 5, 40,    180)   # rough pin position
    net_label(sch, "GND",         90,     40 + 5,  270)

    place_rc(sch, "R", 105, 40, "R_TERM", "50R DNP",
             "Resistor_SMD:R_0402_1005Metric",
             "TRIGGER_SIG", "GND", ROOT_PATH)

    # ── SWD 5-pin header ─────────────────────────────────────────────────────
    # Conn_01x05: pins at (-3.81, (i-1)*-2.54) for i=1..5, angle=0
    J_SWD_X, J_SWD_Y = 130, 30
    j_swd = add_sym(sch, "Connector_Generic:Conn_01x05", J_SWD_X, J_SWD_Y,
                    "J_SWD", "SWD 5-pin 0.1\"",
                    "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical")
    add_sym_instance(sch, j_swd, ROOT_PATH)
    swd_nets = ["NRST", "SWCLK", "SWDIO", "+3V3", "GND"]
    j_swd.pins = {}
    for i, net in enumerate(swd_nets, 1):
        j_swd.pins[str(i)] = uid()
        py = (i - 1) * -2.54
        gx, gy = pin_global(J_SWD_X, J_SWD_Y, 0, -3.81, py)
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), gx, gy)
        else:
            net_label(sch, net, gx, gy, 0)   # pin angle=0 → wire goes left

    # ── HAT EEPROM AT24C256C ─────────────────────────────────────────────────
    U_EE_X, U_EE_Y = 160, 35
    u_ee = add_sym(sch, "Memory_EEPROM:AT24C256C", U_EE_X, U_EE_Y,
                   "U_EEPROM", "AT24C256C",
                   "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    add_sym_instance(sch, u_ee, ROOT_PATH)
    u_ee.pins = {str(i): uid() for i in range(1, 9)}
    # Approximate SOIC-8 pin positions: left pins i=1..4 at x≈-7.62, right i=5..8 at x≈7.62
    for i, net in enumerate(["GND","GND","GND","GND","ID_SDA","ID_SCL","GND","+3V3"], 1):
        px = -7.62 if i <= 4 else 7.62
        py = (i - 1 if i <= 4 else 8 - i) * 2.54 - 3.81
        gx, gy = pin_global(U_EE_X, U_EE_Y, 0, px, py)
        pin_ang = 0 if px < 0 else 180
        if net in ("+3V3", "GND"):
            pwr_symbol(sch, net.lstrip("+"), gx, gy)
        else:
            net_label(sch, net, gx, gy, pin_ang)

    # I2C pull-ups
    place_rc(sch, "R", 175, 25, "R_I2C_SDA", "4k7",
             "Resistor_SMD:R_0402_1005Metric", "+3V3", "ID_SDA", ROOT_PATH)
    place_rc(sch, "R", 188, 25, "R_I2C_SCL", "4k7",
             "Resistor_SMD:R_0402_1005Metric", "+3V3", "ID_SCL", ROOT_PATH)

    # ── Hierarchical sub-sheet boxes ─────────────────────────────────────────
    # Spread out horizontally with generous spacing
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000002",
        filename="laser_driver_circuit.kicad_sch",
        name="Laser Driver Circuit",
        x=20, y=80, w=60, h=40,
        pin_list=[
            ("VCC_5V_IN", "input",   20,  85, 180),
            ("VCC_3V3",   "input",   20,  90, 180),
            ("GND",       "input",   20,  95, 180),
            ("PWM_LASER", "input",   20, 100, 180),
            ("PWM_DUMMY", "input",   20, 105, 180),
            ("VREF",      "input",   20, 110, 180),
        ],
    )
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000003",
        filename="mspm0_controller.kicad_sch",
        name="MSPM0 Controller",
        x=100, y=80, w=70, h=50,
        pin_list=[
            ("VCC_3V3_MCU", "input",         100,  85, 180),
            ("GND",          "input",         100,  90, 180),
            ("UART_TX",      "bidirectional", 100,  95, 180),
            ("UART_RX",      "bidirectional", 100, 100, 180),
            ("SWCLK",        "input",         100, 105, 180),
            ("SWDIO",        "bidirectional", 100, 110, 180),
            ("NRST",         "input",         100, 115, 180),
            ("TRIGGER",      "input",         170,  85,   0),
            ("PWM_LASER",    "output",        170,  90,   0),
            ("PWM_DUMMY",    "output",        170,  95,   0),
            ("VREF",         "output",        170, 100,   0),
        ],
    )
    _add_hsheet(sch,
        uuid="212bfd25-f831-4b85-926b-000000000004",
        filename="usb_uart.kicad_sch",
        name="USB-C UART",
        x=190, y=80, w=50, h=30,
        pin_list=[
            ("VBUS_5V", "input",          190,  85, 180),
            ("GND",     "input",          190,  90, 180),
            ("UART_TX", "bidirectional",  240,  85,   0),
            ("UART_RX", "bidirectional",  240,  90,   0),
        ],
    )

    return sch


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    rt = {
        "mspm0": "/tmp/mspm0_controller.kicad_sch",
        "usb":   "/tmp/usb_uart.kicad_sch",
        "laser": "/tmp/laser_driver_circuit.kicad_sch",
        "root":  "/tmp/LaserDriver.kicad_sch",
    }
    # Refresh /tmp sources from git (in case they're stale/corrupt)
    import subprocess, sys
    for name, src in [
        ("mspm0_controller", "mspm0"),
        ("usb_uart",         "usb"),
        ("laser_driver_circuit", "laser"),
        ("LaserDriver",      "root"),
    ]:
        tmp = f"/tmp/{name}.kicad_sch"
        result = subprocess.run(
            ["git", "show", f"HEAD:{os.path.join('LaserHAT', name + '.kicad_sch')}"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        if result.returncode == 0 and result.stdout.strip():
            with open(tmp, "w") as f:
                f.write(result.stdout)
        # else leave existing /tmp file

    tasks = [
        ("Laser driver circuit",  lambda: build_laser_driver(),
         os.path.join(OUT_DIR, "laser_driver_circuit.kicad_sch")),
        ("MSPM0 controller",      lambda: build_mspm0(rt["mspm0"]),
         os.path.join(OUT_DIR, "mspm0_controller.kicad_sch")),
        ("USB-C UART",            lambda: build_usb_uart(rt["usb"]),
         os.path.join(OUT_DIR, "usb_uart.kicad_sch")),
        ("Root schematic",        lambda: build_root(rt["root"]),
         os.path.join(OUT_DIR, "LaserDriver.kicad_sch")),
    ]

    for desc, builder, out_path in tasks:
        print(f"Building {desc} …")
        try:
            sch = builder()
            sch.to_file(out_path)
            print(f"  → {out_path}  "
                  f"({len(sch.schematicSymbols)} symbols, "
                  f"{len(sch.labels)} labels, "
                  f"{len(getattr(sch,'hierarchicalLabels',[]))} hLabels)")
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            raise

    print("\nDone — open LaserHAT/LaserDriver.kicad_pro in KiCad to verify.")


if __name__ == "__main__":
    main()
