#!/usr/bin/env python3
"""
Symbol library for the StimHAT (LaserHAT Rev 2 core + the e-stim module's isolated stimulator on one HAT, 2026-10-29).
All symbols are embedded (no external libraries needed); the engine writes them into the schematic and into
stimhat.kicad_sym.  Copied from EStimDaughter/sch_symbols.py and BatteryPack/sch_symbols.py, plus the HAT core parts.
"""
import math
import uuid

U = lambda: str(uuid.uuid4())  # noqa: E731
F = lambda v: f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)  # noqa: E731

LIB = "stimhat"
symbols = {}          # name -> (sexpr text, {pin_number: (x, y, angle)}) in symbol coords (y up)


def font(size=1.27, hide=False):
    return f"(effects (font (size {size} {size})){' (hide yes)' if hide else ''})"


def prop(name, value, x=0, y=0, hide=False, size=1.27):
    return f'(property "{name}" "{value}" (at {F(x)} {F(y)} 0) {font(size, hide)})'


def pin(num, name, x, y, angle, length=2.54, etype="passive", hide_name=False):
    return (f'(pin {etype} line (at {F(x)} {F(y)} {angle}) (length {F(length)}) '
            f'(name "{name}" {font(1.27, hide_name)}) (number "{num}" {font(1.27)}))')


def add_symbol(name, ref_prefix, graphics, pins, power=False, ref_pos=(0, 5), val_pos=(0, -5),
               hide_pin_numbers=False, hide_pin_names=False):
    """pins: list of (num, name, x, y, angle, etype)"""
    pinmap = {p[0]: (p[2], p[3], p[4]) for p in pins}
    pin_txt = "\n    ".join(pin(p[0], p[1], p[2], p[3], p[4], 2.54, p[5], hide_pin_names) for p in pins)
    s = (f'(symbol "{LIB}:{name}"{" (power)" if power else ""}'
         f'{" (pin_numbers (hide yes))" if hide_pin_numbers else ""} (pin_names (offset 0.6){" (hide yes)" if hide_pin_names else ""})'
         f' (exclude_from_sim no) (in_bom {"no" if power else "yes"}) (on_board {"no" if power else "yes"})\n'
         f'  {prop("Reference", ref_prefix, *ref_pos, hide=power)}\n'
         f'  {prop("Value", name, *val_pos)}\n'
         f'  {prop("Footprint", "", 0, 0, True)}\n'
         f'  {prop("Datasheet", "", 0, 0, True)}\n'
         f'  (symbol "{name}_0_1"\n    {graphics}\n  )\n'
         f'  (symbol "{name}_1_1"\n    {pin_txt}\n  )\n)')
    symbols[name] = (s, pinmap)


def rect(x1, y1, x2, y2, fill="none"):
    return f'(rectangle (start {F(x1)} {F(y1)}) (end {F(x2)} {F(y2)}) (stroke (width 0.254) (type default)) (fill (type {fill})))'


def poly(pts, fill="none", w=0.254):
    p = " ".join(f"(xy {F(x)} {F(y)})" for x, y in pts)
    return f'(polyline (pts {p}) (stroke (width {w}) (type default)) (fill (type {fill})))'


def circ(x, y, r):
    return f'(circle (center {F(x)} {F(y)}) (radius {F(r)}) (stroke (width 0.254) (type default)) (fill (type none)))'


# --- passives (pin 1 top, pin 2 bottom)
add_symbol("R", "R", rect(-1.016, -2.54, 1.016, 2.54),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("C", "C", poly([(-2.032, 0.762), (2.032, 0.762)], w=0.508) + "\n    " + poly([(-2.032, -0.762), (2.032, -0.762)], w=0.508),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
diode_gfx = poly([(1.27, 1.27), (1.27, -1.27), (-1.27, 0), (1.27, 1.27)]) + "\n    " + poly([(-1.27, 1.27), (-1.27, -1.27)], w=0.508)
# diodes, horizontal: pin 1 = K (left), 2 = A (right); the KiCad SOD / LED footprints put the cathode on pad 1
add_symbol("D", "D", diode_gfx,
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("D_Zener", "D", diode_gfx + "\n    " + poly([(-1.27, 1.27), (-1.905, 1.27)], w=0.508) + "\n    " + poly([(-1.27, -1.27), (-0.635, -1.27)], w=0.508),
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("LED", "D", diode_gfx + "\n    " + poly([(0.3, 1.6), (1.3, 2.6)], w=0.254) + "\n    " + poly([(1.1, 1.6), (2.1, 2.6)], w=0.254),
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
_coil = "\n    ".join(poly([(x - 1.27 + 0.3175 * k, 0.0 + 1.2 * math.sin(math.pi * k / 8)) for k in range(9)], w=0.254)
                      for x in (-2.54, 0, 2.54))
add_symbol("L", "L", _coil,
           [("1", "~", -5.08, 0, 0, "passive"), ("2", "~", 5.08, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)


# --- MOSFETs (KiCad Q_xMOS_GSD pin layout: 1 G left, 2 S bottom, 3 D top)
def mos_gfx(pmos):
    g = [poly([(-2.54, 0), (-1.27, 0)], w=0.254), poly([(-1.27, 2.0), (-1.27, -2.0)], w=0.508),
         poly([(-0.508, 2.2), (-0.508, 1.2)], w=0.508), poly([(-0.508, 0.5), (-0.508, -0.5)], w=0.508),
         poly([(-0.508, -1.2), (-0.508, -2.2)], w=0.508),
         poly([(-0.508, 1.7), (2.54, 1.7), (2.54, 2.54)]), poly([(-0.508, -1.7), (2.54, -1.7), (2.54, -2.54)]),
         poly([(-0.508, 0), (2.54, 0), (2.54, -1.7)]), circ(0.762, 0, 3.0)]
    if pmos:
        g.append(poly([(0.2, 0), (1.3, 0.6), (1.3, -0.6), (0.2, 0)], fill="outline"))
    else:
        g.append(poly([(1.5, 0), (0.4, 0.6), (0.4, -0.6), (1.5, 0)], fill="outline"))
    return "\n    ".join(g)


mos_pins = [("1", "G", -5.08, 0, 0, "input"), ("2", "S", 2.54, -5.08, 90, "passive"), ("3", "D", 2.54, 5.08, 270, "passive")]
add_symbol("Q_NMOS_GSD", "Q", mos_gfx(False), mos_pins, ref_pos=(5.08, 2.54), val_pos=(5.08, 0), hide_pin_names=True)
add_symbol("Q_PMOS_GSD", "Q", mos_gfx(True), mos_pins, ref_pos=(5.08, 2.54), val_pos=(5.08, 0), hide_pin_names=True)


# --- bipolar transistors, SOT-23 (KiCad Q_NPN_BEC / Q_PNP_BEC: 1 B left, 2 E bottom, 3 C top)
def bjt_gfx(pnp):
    g = [poly([(-2.54, 0), (-0.635, 0)], w=0.254), poly([(-0.635, 1.905), (-0.635, -1.905)], w=0.508),
         poly([(-0.635, 0.635), (2.54, 2.54)]), poly([(-0.635, -0.635), (2.54, -2.54)]), circ(0.762, 0, 2.8)]
    if pnp:
        g.append(poly([(0.9, -1.1), (1.9, -0.6), (1.6, -1.6), (0.9, -1.1)], fill="outline"))
    else:
        g.append(poly([(2.3, -2.3), (1.3, -2.0), (2.0, -1.3), (2.3, -2.3)], fill="outline"))
    return "\n    ".join(g)


bjt_pins = [("1", "B", -5.08, 0, 0, "input"), ("2", "E", 2.54, -5.08, 90, "passive"), ("3", "C", 2.54, 5.08, 270, "passive")]
add_symbol("Q_NPN_BEC", "Q", bjt_gfx(False), bjt_pins, ref_pos=(5.08, 2.54), val_pos=(5.08, 0), hide_pin_names=True)
add_symbol("Q_PNP_BEC", "Q", bjt_gfx(True), bjt_pins, ref_pos=(5.08, 2.54), val_pos=(5.08, 0), hide_pin_names=True)


# --- IC boxes: pins listed as (num, name, side, slot, etype); side L/R, slot from top
def box_symbol(name, ref, left, right, width=15.24, hide_pin_names=False):
    n = max(len(left), len(right))
    h = (n + 1) * 2.54
    top = h / 2
    pins = []
    for i, (num, pname, et) in enumerate(left):
        pins.append((num, pname, -width / 2 - 2.54, top - (i + 1) * 2.54, 0, et))
    for i, (num, pname, et) in enumerate(right):
        pins.append((num, pname, width / 2 + 2.54, top - (i + 1) * 2.54, 180, et))
    add_symbol(name, ref, rect(-width / 2, top, width / 2, -top), pins, ref_pos=(0, top + 1.27), val_pos=(0, -top - 1.27), hide_pin_names=hide_pin_names)


box_symbol("Conn_01x02", "J", [("1", "Pin_1", "passive"), ("2", "Pin_2", "passive")], [], width=7.62, hide_pin_names=True)
box_symbol("Conn_01x04", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 5)], [], width=7.62, hide_pin_names=True)
box_symbol("Conn_01x05", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 6)], [], width=7.62, hide_pin_names=True)
box_symbol("BNC", "J", [("1", "In", "passive"), ("2", "Ext", "passive")], [], width=7.62)
box_symbol("Jumper2", "JP", [("1", "A", "passive"), ("2", "B", "passive")], [], width=7.62, hide_pin_names=True)
add_symbol("TestPoint", "TP", circ(0, 1.27, 0.762), [("1", "~", 0, 0, 90, "passive")], ref_pos=(0, 3.81), val_pos=(0, -2.54),
           hide_pin_numbers=True, hide_pin_names=True)
add_symbol("MountingHole", "H", circ(0, 0, 1.27) + "\n    " + circ(0, 0, 0.6), [], ref_pos=(0, 3.81), val_pos=(0, -3.81))
add_symbol("Logo", "G", rect(-2.54, 2.54, 2.54, -2.54) + "\n    " + circ(0, 0, 1.5), [("1", "GND", 0, -5.08, 90, "passive")],
           ref_pos=(0, 3.81), val_pos=(0, -7.62), hide_pin_numbers=True, hide_pin_names=True)
# momentary push button, horizontal: pin 1 left, 2 right
add_symbol("SW_Push", "SW", poly([(-2.54, 0), (-1.27, 0)]) + "\n    " + poly([(1.27, 0), (2.54, 0)]) + "\n    " +
           poly([(-1.6, 1.6), (1.6, 1.6)], w=0.381) + "\n    " + poly([(0, 1.6), (0, 2.8)], w=0.381) + "\n    " +
           circ(-1.27, 0, 0.3) + "\n    " + circ(1.27, 0, 0.3),
           [("1", "1", -5.08, 0, 0, "passive"), ("2", "2", 5.08, 0, 180, "passive")],
           ref_pos=(0, 4.45), val_pos=(0, -2.54), hide_pin_names=True)
# SPDT slide switch (MSK12C02): 2 = common (left), 1 = A, 3 = B
add_symbol("SW_SPDT", "SW", poly([(-2.54, 0), (-1.27, 0)]) + "\n    " + poly([(-1.27, 0), (1.6, 1.4)], w=0.381) + "\n    " +
           poly([(1.27, 1.27), (2.54, 1.27)]) + "\n    " + poly([(1.27, -1.27), (2.54, -1.27)]) + "\n    " +
           circ(-1.27, 0, 0.3) + "\n    " + circ(1.27, 1.27, 0.3) + "\n    " + circ(1.27, -1.27, 0.3),
           [("2", "C", -5.08, 0, 0, "passive"), ("1", "A", 5.08, 1.27, 180, "passive"), ("3", "B", 5.08, -1.27, 180, "passive")],
           ref_pos=(0, 3.81), val_pos=(0, -3.81), hide_pin_names=True)
# ALPS SKRHADE010 five-way: 1 A (up), 2 centre push, 3 C (left), 4 B (right), 5 common, 6 D (down); directions with the
# package mounted at 45 degrees (the stem moves along the package diagonals)
box_symbol("Joystick5", "SW",
           [("1", "A/DOWN", "passive"), ("3", "C/RIGHT", "passive"), ("6", "D/UP", "passive"), ("4", "B/LEFT", "passive"),
            ("2", "CENTRE", "passive")],
           [("5", "COM", "passive")], width=15.24)


# --- power symbols
def power_symbol(name, gnd=False):
    if gnd:
        gfx = poly([(0, 0), (0, -1.27)]) + "\n    " + poly([(-1.27, -1.27), (1.27, -1.27)], w=0.508) + "\n    " + \
              poly([(-0.635, -1.905), (0.635, -1.905)], w=0.508)
        add_symbol(name, "#PWR", gfx, [("1", name, 0, 0, 90, "power_in")], power=True, ref_pos=(0, -6.35), val_pos=(0, -3.81),
                   hide_pin_numbers=True, hide_pin_names=True)
    else:
        gfx = poly([(0, 0), (0, 1.27)]) + "\n    " + poly([(-1.27, 1.27), (1.27, 1.27)], w=0.508)
        add_symbol(name, "#PWR", gfx, [("1", name, 0, 0, 270, "power_in")], power=True, ref_pos=(0, -3.81), val_pos=(0, 3.175),
                   hide_pin_numbers=True, hide_pin_names=True)


POWER_NETS = {"+5V": False, "+3V3": False, "+3V3_PI": False, "MSPM0_3V3": False, "VBUS": False,
              "+V_RAW": False, "+V_F": False, "+V_STIM": False, "+5V_ISO": False,
              "GND": True, "GND_ISO": True, "-V_RAW": True, "-V_F": True, "-V_STIM": True, "-5V_ISO": True}
for n, g in POWER_NETS.items():
    power_symbol(n, g)


# --- IC symbols: power pins top/bottom
def ic_symbol(name, ref, w, h, left=(), right=(), top=(), bottom=(), gfx_extra=""):
    """left/right: (num, pin_name, y, etype); top/bottom: (num, pin_name, x, etype).  Body is +-w/2 x +-h/2; pins 2.54 long."""
    pins = [(n, nm, -w / 2 - 2.54, y, 0, et) for n, nm, y, et in left]
    pins += [(n, nm, w / 2 + 2.54, y, 180, et) for n, nm, y, et in right]
    pins += [(n, nm, x, h / 2 + 2.54, 270, et) for n, nm, x, et in top]
    pins += [(n, nm, x, -h / 2 - 2.54, 90, et) for n, nm, x, et in bottom]
    add_symbol(name, ref, rect(-w / 2, h / 2, w / 2, -h / 2, fill="background") + gfx_extra, pins,
               ref_pos=(0, h / 2 + 3.81), val_pos=(0, -h / 2 - 3.81))


# ----------------------------------------------------------------------------- multi-unit symbols (dual op-amps / comparators)
UNITS = {}      # symbol name -> {pin number: unit}


def add_units_symbol(name, ref_prefix, units, ref_pos=(2.54, 5.08), val_pos=(2.54, -5.08)):
    """units: list of (graphics, pins) for unit 1..n; pins as in add_symbol."""
    pinmap, umap, body = {}, {}, []
    for k, (gfx, pins) in enumerate(units, start=1):
        for p in pins:
            pinmap[p[0]] = (p[2], p[3], p[4]); umap[p[0]] = k
        pin_txt = "\n    ".join(pin(p[0], p[1], p[2], p[3], p[4], 2.54, p[5]) for p in pins)
        body.append(f'  (symbol "{name}_{k}_1"\n    {gfx}\n    {pin_txt}\n  )')
    s = (f'(symbol "{LIB}:{name}" (pin_names (offset 0.254)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
         f'  {prop("Reference", ref_prefix, *ref_pos)}\n  {prop("Value", name, *val_pos)}\n'
         f'  {prop("Footprint", "", 0, 0, True)}\n  {prop("Datasheet", "", 0, 0, True)}\n' + "\n".join(body) + "\n)")
    symbols[name] = (s, pinmap)
    UNITS[name] = umap


def dual_amp(name, out_type):
    tri = poly([(-5.08, 5.08), (5.08, 0), (-5.08, -5.08), (-5.08, 5.08)], fill="background")
    unit = lambda p, m, o: (tri, [(p, "+", -7.62, 2.54, 0, "input"), (m, "-", -7.62, -2.54, 0, "input"),  # noqa: E731
                                  (o, "~", 7.62, 0, 180, out_type)])
    pwr = (rect(-1.27, 2.54, 1.27, -2.54, fill="background"),
           [("8", "V+", 0, 5.08, 270, "power_in"), ("4", "V-", 0, -5.08, 90, "power_in")])
    add_units_symbol(name, "U", [unit("3", "2", "1"), unit("5", "6", "7"), pwr])


dual_amp("OPA2192", "output")
dual_amp("TLV1702", "open_collector")      # 1 OUTA, 2 INA-, 3 INA+, 4 V-, 5 INB+, 6 INB-, 7 OUTB, 8 V+


# ----------------------------------------------------------------------------- stimulator ICs
ic_symbol("ISO7741", "U", 30.48, 17.78,
          left=[("3", "INA", 5.08, "input"), ("4", "INB", 2.54, "input"), ("5", "INC", 0, "input"), ("6", "OUTD", -2.54, "output"),
                ("7", "EN1", -5.08, "input")],
          right=[("14", "OUTA", 5.08, "output"), ("13", "OUTB", 2.54, "output"), ("12", "OUTC", 0, "output"),
                 ("11", "IND", -2.54, "input"), ("10", "EN2", -5.08, "input")],
          top=[("1", "VCC1", -7.62, "power_in"), ("16", "VCC2", 7.62, "power_in")],
          bottom=[("2", "GND1", -7.62, "power_in"), ("8", "GND1", -5.08, "passive"), ("9", "GND2", 5.08, "power_in"), ("15", "GND2", 7.62, "passive")],
          gfx_extra="\n    " + poly([(0, 8.89), (0, -8.89)], w=0.254))
# ISO1640 SOIC-8 (TI datasheet, D package): 1 VCC1, 2 SDA1, 3 SCL1, 4 GND1 | 5 GND2, 6 SCL2, 7 SDA2, 8 VCC2.
# (The e-stim module's symbol had VCC1/GND1 and VCC2/GND2 swapped, 2026-10-20.)  Side 1 = the master (MCU) side.
ic_symbol("ISO1640", "U", 20.32, 12.7,
          left=[("2", "SDA1", 2.54, "bidirectional"), ("3", "SCL1", -2.54, "bidirectional")],
          right=[("7", "SDA2", 2.54, "bidirectional"), ("6", "SCL2", -2.54, "bidirectional")],
          top=[("1", "VCC1", -5.08, "power_in"), ("8", "VCC2", 5.08, "power_in")],
          bottom=[("4", "GND1", -5.08, "power_in"), ("5", "GND2", 5.08, "power_in")],
          gfx_extra="\n    " + poly([(0, 6.35), (0, -6.35)], w=0.254))
ic_symbol("DAC60501", "U", 15.24, 17.78,
          left=[("6", "SCL", 5.08, "input"), ("8", "SDA", 2.54, "bidirectional"), ("5", "SPI2C", 0, "input"), ("7", "A0", -2.54, "input"),
                ("3", "NC", -5.08, "no_connect")],
          right=[("2", "VOUT", 0, "output"), ("10", "VREFIO", -2.54, "passive"), ("9", "NC", -5.08, "no_connect")],
          top=[("1", "VDD", 0, "power_in")], bottom=[("4", "AGND", 0, "power_in")])
ic_symbol("A0515S", "PS", 20.32, 10.16,
          left=[("1", "+VIN", 2.54, "power_in"), ("2", "-VIN", -2.54, "power_in")],
          right=[("6", "+VO", 2.54, "power_out"), ("5", "COM", 0, "power_out"), ("4", "-VO", -2.54, "power_out")],
          gfx_extra="\n    " + poly([(0, 5.08), (0, -5.08)], w=0.254))
ic_symbol("TLV760", "U", 12.7, 7.62,
          left=[("2", "IN", 0, "power_in")], right=[("1", "OUT", 0, "power_out")], bottom=[("3", "GND", 0, "power_in")])
ic_symbol("74HC4053", "U", 20.32, 25.4,
          left=[("12", "1Y0", 10.16, "passive"), ("13", "1Y1", 7.62, "passive"), ("2", "2Y0", 2.54, "passive"), ("1", "2Y1", 0, "passive"),
                ("5", "3Y0", -5.08, "passive"), ("3", "3Y1", -7.62, "passive")],
          right=[("14", "1Z", 8.89, "passive"), ("15", "2Z", 1.27, "passive"), ("4", "3Z", -6.35, "passive")],
          top=[("16", "VCC", 0, "power_in")],
          bottom=[("11", "S1", -7.62, "input"), ("10", "S2", -5.08, "input"), ("9", "S3", -2.54, "input"), ("6", "~{E}", 0, "input"),
                  ("8", "GND", 5.08, "power_in"), ("7", "VEE", 7.62, "power_in")])
# DG418 SPST normally open (IN high = on), SOIC-8: 1 S, 2 NC, 3 GND, 4 V+, 5 VL, 6 IN, 7 V-, 8 D
ic_symbol("DG418", "U", 12.7, 10.16,
          left=[("6", "IN", 0, "input"), ("2", "NC", -2.54, "no_connect")],
          right=[("8", "D", 2.54, "passive"), ("1", "S", -2.54, "passive")],
          top=[("4", "V+", -2.54, "power_in"), ("5", "VL", 2.54, "power_in")],
          bottom=[("3", "GND", -2.54, "power_in"), ("7", "V-", 2.54, "power_in")])


# ----------------------------------------------------------------------------- HAT core ICs
# MSPM0G3507 VQFN-32 (RHB): the Rev 2 HAT's pin usage; pad 33 = exposed pad
ic_symbol("MSPM0G3507", "U", 33.02, 40.64,
          left=[("1", "PA0/SDA", 17.78, "bidirectional"), ("2", "PA1/SCL", 15.24, "bidirectional"), ("3", "NRST", 12.7, "input"),
                ("6", "PA2/ROSC", 10.16, "bidirectional"), ("7", "PA3", 7.62, "bidirectional"), ("8", "PA4", 5.08, "bidirectional"),
                ("9", "PA5", 2.54, "bidirectional"), ("10", "PA6", 0, "bidirectional"), ("11", "PA7", -2.54, "bidirectional"),
                ("12", "PA8", -5.08, "bidirectional"), ("13", "PA9", -7.62, "bidirectional"), ("14", "PA10", -10.16, "bidirectional"),
                ("15", "PA11", -12.7, "bidirectional"), ("16", "PA12", -15.24, "bidirectional")],
          right=[("17", "PA13", 17.78, "bidirectional"), ("18", "PA14", 15.24, "bidirectional"), ("19", "PA15/DAC", 12.7, "bidirectional"),
                 ("20", "PA16", 10.16, "bidirectional"), ("21", "PA17", 7.62, "bidirectional"), ("22", "PA18", 5.08, "bidirectional"),
                 ("23", "PA19/SWDIO", 2.54, "bidirectional"), ("24", "PA20/SWCLK", 0, "bidirectional"), ("25", "PA21", -2.54, "bidirectional"),
                 ("26", "PA22", -5.08, "bidirectional"), ("27", "PA23", -7.62, "bidirectional"), ("28", "PA24", -10.16, "bidirectional"),
                 ("29", "PA25", -12.7, "bidirectional"), ("30", "PA26", -15.24, "bidirectional"), ("31", "PA27", -17.78, "bidirectional")],
          top=[("4", "VDD", -5.08, "power_in"), ("32", "VCORE", 5.08, "passive")],
          bottom=[("5", "VSS", -5.08, "power_in"), ("33", "EPAD", 5.08, "passive")])
ic_symbol("CH340N", "U", 17.78, 15.24,
          left=[("1", "UD+", 5.08, "bidirectional"), ("2", "UD-", 2.54, "bidirectional"), ("4", "~{RTS}", -2.54, "output")],
          right=[("6", "TXD", 2.54, "output"), ("7", "RXD", -2.54, "input")],
          top=[("5", "VCC", -2.54, "power_in"), ("8", "V3", 2.54, "passive")], bottom=[("3", "GND", 0, "power_in")])
ic_symbol("AP2171W", "U", 15.24, 10.16,
          left=[("5", "IN", 2.54, "power_in"), ("4", "EN", -2.54, "input")],
          right=[("1", "OUT", 2.54, "power_out"), ("3", "~{FLG}", -2.54, "open_collector")],
          bottom=[("2", "GND", 0, "power_in")])
ic_symbol("MCP1700", "U", 12.7, 7.62,
          left=[("2", "VI", 0, "power_in")], right=[("3", "VO", 0, "power_out")], bottom=[("1", "GND", 0, "power_in")])
ic_symbol("M24C32", "U", 15.24, 15.24,
          left=[("1", "A0", 5.08, "input"), ("2", "A1", 2.54, "input"), ("3", "A2", 0, "input"), ("7", "WP", -5.08, "input")],
          right=[("5", "SDA", 2.54, "bidirectional"), ("6", "SCL", -2.54, "input")],
          top=[("8", "VCC", 0, "power_in")], bottom=[("4", "GND", 0, "power_in")])
ic_symbol("74LVC2G17", "U", 12.7, 12.7,
          left=[("1", "1A", 2.54, "input"), ("3", "2A", -2.54, "input")],
          right=[("6", "1Y", 2.54, "output"), ("4", "2Y", -2.54, "output")],
          top=[("5", "VCC", 0, "power_in")], bottom=[("2", "GND", 0, "power_in")])
# DMMT5401 dual PNP, SOT-23-6: 1 C1, 2 B1, 3 B2, 4 C2, 5 E2, 6 E1
ic_symbol("DMMT5401", "Q", 12.7, 17.78,
          left=[("2", "B1", 5.08, "input"), ("3", "B2", -5.08, "input")],
          right=[("1", "C1", 7.62, "passive"), ("6", "E1", 2.54, "passive"), ("4", "C2", -2.54, "passive"), ("5", "E2", -7.62, "passive")])
# USB-C receptacle (G-Switch GT-USB-7010ASV, USB 2.0): pad names as in the KiCad footprint
ic_symbol("USB_C_16P", "J", 15.24, 25.4,
          left=[("A4", "VBUS", 10.16, "passive"), ("B4", "VBUS", 7.62, "passive"), ("A9", "VBUS", 5.08, "passive"), ("B9", "VBUS", 2.54, "passive")],
          right=[("A5", "CC1", 7.62, "passive"), ("B5", "CC2", 5.08, "passive"), ("A6", "D+", 2.54, "passive"), ("B6", "D+", 0, "passive"),
                 ("A7", "D-", -2.54, "passive"), ("B7", "D-", -5.08, "passive"), ("A8", "SBU1", -7.62, "passive"), ("B8", "SBU2", -10.16, "passive")],
          bottom=[("A1", "GND", -5.08, "passive"), ("B1", "GND", -2.54, "passive"), ("A12", "GND", 0, "passive"), ("B12", "GND", 2.54, "passive"),
                  ("S1", "SH", 5.08, "passive")])
# Raspberry Pi 40-pin header: odd pins left, even pins right, in physical order
_PI = {1: "3V3", 2: "5V", 3: "GPIO2/SDA", 4: "5V", 5: "GPIO3/SCL", 6: "GND", 7: "GPIO4", 8: "GPIO14/TXD", 9: "GND", 10: "GPIO15/RXD",
       11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22", 16: "GPIO23", 17: "3V3", 18: "GPIO24", 19: "GPIO10",
       20: "GND", 21: "GPIO9", 22: "GPIO25", 23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7", 27: "ID_SD", 28: "ID_SC",
       29: "GPIO5", 30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND", 35: "GPIO19", 36: "GPIO16", 37: "GPIO26",
       38: "GPIO20", 39: "GND", 40: "GPIO21"}
ic_symbol("GPIO_2x20", "J", 20.32, 55.88,
          left=[(str(n), _PI[n], 25.4 - 2.54 * (n // 2), "passive") for n in range(1, 40, 2)],
          right=[(str(n), _PI[n], 25.4 - 2.54 * (n // 2 - 1), "passive") for n in range(2, 41, 2)])
