#!/usr/bin/env python3
"""
Symbol library for the kbest e-stim module (LaserHAT plug-in).  All symbols are embedded (no external libraries needed).
Connectivity is by net label on every pin; blocks are grouped and titled so it reads
as a functional schematic.  Open in KiCad 8 -> Schematic Editor and run ERC.
"""
import uuid, math

U = lambda: str(uuid.uuid4())
F = lambda v: f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)

# ----------------------------------------------------------------------------- symbol library
LIB = "estim"
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

# --- passives
add_symbol("R", "R", rect(-1.016, -2.54, 1.016, 2.54),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("C", "C", poly([(-2.032, 0.762), (2.032, 0.762)], w=0.508) + "\n    " + poly([(-2.032, -0.762), (2.032, -0.762)], w=0.508),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("Polyfuse", "F", rect(-1.016, -2.54, 1.016, 2.54) + "\n    " + poly([(-1.016, 2.54), (1.016, -2.54)]),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
diode_gfx = poly([(1.27, 1.27), (1.27, -1.27), (-1.27, 0), (1.27, 1.27)]) + "\n    " + poly([(-1.27, 1.27), (-1.27, -1.27)], w=0.508)
add_symbol("D", "D", diode_gfx,
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
add_symbol("D_Zener", "D", diode_gfx + "\n    " + poly([(-1.27, 1.27), (-1.905, 1.27)], w=0.508) + "\n    " + poly([(-1.27, -1.27), (-0.635, -1.27)], w=0.508),
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
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

box_symbol("CA-IS3741LN", "U",
           [("1", "VDD1", "power_in"), ("2", "GND1", "power_in"), ("3", "INA", "input"), ("4", "INB", "input"),
            ("5", "INC", "input"), ("6", "OUTD", "output"), ("7", "EN1", "input"), ("8", "GND1", "power_in")],
           [("16", "VDD2", "power_in"), ("15", "GND2", "power_in"), ("14", "OUTA", "output"), ("13", "OUTB", "output"),
            ("12", "OUTC", "output"), ("11", "IND", "input"), ("10", "EN2", "input"), ("9", "GND2", "power_in")], width=20.32)
box_symbol("MCP4921", "U",
           [("1", "VDD", "power_in"), ("2", "~{CS}", "input"), ("3", "SCK", "input"), ("4", "SDI", "input")],
           [("8", "VOUT", "output"), ("7", "VSS", "power_in"), ("6", "VREF", "input"), ("5", "~{LDAC}", "input")], width=17.78)
box_symbol("TLV9062", "U",
           [("3", "+INA", "input"), ("2", "-INA", "input"), ("8", "V+", "power_in"), ("5", "+INB", "input"), ("6", "-INB", "input")],
           [("1", "OUTA", "output"), ("4", "V-", "power_in"), ("7", "OUTB", "output")], width=15.24)
box_symbol("LM393", "U",
           [("3", "+IN1", "input"), ("2", "-IN1", "input"), ("8", "VCC", "power_in"), ("5", "+IN2", "input"), ("6", "-IN2", "input")],
           [("1", "OUT1", "open_collector"), ("4", "GND", "power_in"), ("7", "OUT2", "open_collector")], width=15.24)
box_symbol("TL431_SOT23", "U", [("1", "REF", "input"), ("3", "A", "passive")], [("2", "K", "passive")], width=12.7)   # Hottech C181103: 1 REF, 2 K, 3 A
box_symbol("L78L05_SOT89", "U", [("3", "IN", "power_in"), ("2", "GND", "power_in")], [("1", "OUT", "power_out")], width=12.7)
box_symbol("Conn_01x10", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 11)], [], width=7.62, hide_pin_names=True)
box_symbol("Conn_01x02", "J", [("1", "Pin_1", "passive"), ("2", "Pin_2", "passive")], [], width=7.62, hide_pin_names=True)
add_symbol("TestPoint", "TP", circ(0, 1.27, 0.762), [("1", "~", 0, 0, 90, "passive")], ref_pos=(0, 3.81), val_pos=(0, -2.54),
           hide_pin_numbers=True, hide_pin_names=True)

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
box_symbol("OPA2192", "U",
           [("3", "+INA", "input"), ("2", "-INA", "input"), ("8", "V+", "power_in"), ("5", "+INB", "input"), ("6", "-INB", "input")],
           [("1", "OUTA", "output"), ("4", "V-", "power_in"), ("7", "OUTB", "output")], width=15.24)
box_symbol("74HC4053", "U",
           [("12", "1Y0", "passive"), ("13", "1Y1", "passive"), ("11", "S1", "input"), ("2", "2Y0", "passive"), ("1", "2Y1", "passive"),
            ("10", "S2", "input"), ("5", "3Y0", "passive"), ("3", "3Y1", "passive"), ("9", "S3", "input")],
           [("16", "VCC", "power_in"), ("14", "1Z", "passive"), ("15", "2Z", "passive"), ("4", "3Z", "passive"),
            ("6", "~{E}", "input"), ("7", "VEE", "power_in"), ("8", "GND", "power_in")], width=20.32)
add_symbol("R_Potentiometer", "RV", rect(-1.016, -2.54, 1.016, 2.54) + "\n    " + poly([(2.54, 0), (1.27, 0)]) + "\n    " + poly([(1.27, 0), (1.9, 0.5), (1.9, -0.5), (1.27, 0)], fill="outline"),
           [("1", "1", 0, 3.81, 270, "passive"), ("2", "2", 3.81, 0, 180, "passive"), ("3", "3", 0, -3.81, 90, "passive")],
           ref_pos=(-3.81, 1.27), val_pos=(-3.81, -1.27), hide_pin_numbers=True, hide_pin_names=True)
POWER_NETS = {"+V_STIM": False, "-V_STIM": True, "+5V_ISO": False, "-5V_ISO": True, "GND_ISO": True,
              "+3V3_H": False, "+5V_H": False, "GND_H": True}
for n, g in POWER_NETS.items():
    power_symbol(n, g)



# ----------------------------------------------------------------------------- rev D IC symbols: power pins top/bottom
def ic_symbol(name, ref, w, h, left=(), right=(), top=(), bottom=(), gfx_extra=""):
    """left/right: (num, pin_name, y, etype); top/bottom: (num, pin_name, x, etype).  Body is +-w/2 x +-h/2; pins 2.54 long."""
    pins = [(n, nm, -w / 2 - 2.54, y, 0, et) for n, nm, y, et in left]
    pins += [(n, nm, w / 2 + 2.54, y, 180, et) for n, nm, y, et in right]
    pins += [(n, nm, x, h / 2 + 2.54, 270, et) for n, nm, x, et in top]
    pins += [(n, nm, x, -h / 2 - 2.54, 90, et) for n, nm, x, et in bottom]
    add_symbol(name, ref, rect(-w / 2, h / 2, w / 2, -h / 2, fill="background") + gfx_extra, pins,
               ref_pos=(0, h / 2 + 3.81), val_pos=(0, -h / 2 - 3.81))


ic_symbol("CA-IS3741LN", "U", 30.48, 20.32,
          left=[("3", "INA", 5.08, "input"), ("4", "INB", 2.54, "input"), ("5", "INC", 0, "input"), ("6", "OUTD", -2.54, "output")],
          right=[("14", "OUTA", 5.08, "output"), ("13", "OUTB", 2.54, "output"), ("12", "OUTC", 0, "output"), ("11", "IND", -2.54, "input")],
          top=[("1", "VDD1", -7.62, "power_in"), ("7", "EN1", -5.08, "input"), ("10", "EN2", 5.08, "input"), ("16", "VDD2", 7.62, "power_in")],
          bottom=[("2", "GND1", -7.62, "power_in"), ("8", "GND1", -5.08, "passive"), ("9", "GND2", 5.08, "passive"), ("15", "GND2", 7.62, "power_in")],
          gfx_extra="\n    " + poly([(0, 10.16), (0, -10.16)], w=0.254))
for _n, _out in (("OPA2192", "output"), ("TLV9062", "output"), ("LM393", "open_collector")):
    ic_symbol(_n, "U", 15.24, 15.24,
              left=[("3", "+INA", 5.08, "input"), ("2", "-INA", 2.54, "input"), ("5", "+INB", -2.54, "input"), ("6", "-INB", -5.08, "input")],
              right=[("1", "OUTA", 3.81, _out), ("7", "OUTB", -3.81, _out)],
              top=[("8", "V+", 0, "power_in")], bottom=[("4", "V-", 0, "power_in")])
ic_symbol("MCP4921", "U", 15.24, 15.24,
          left=[("6", "VREF", 5.08, "input"), ("2", "~{CS}", 2.54, "input"), ("3", "SCK", 0, "input"), ("4", "SDI", -2.54, "input"),
                ("5", "~{LDAC}", -5.08, "input")],
          right=[("8", "VOUT", 0, "output")], top=[("1", "VDD", 0, "power_in")], bottom=[("7", "VSS", 0, "power_in")])
ic_symbol("74HC4053", "U", 20.32, 25.4,
          left=[("12", "1Y0", 10.16, "passive"), ("13", "1Y1", 7.62, "passive"), ("2", "2Y0", 2.54, "passive"), ("1", "2Y1", 0, "passive"),
                ("5", "3Y0", -5.08, "passive"), ("3", "3Y1", -7.62, "passive")],
          right=[("14", "1Z", 8.89, "passive"), ("15", "2Z", 1.27, "passive"), ("4", "3Z", -6.35, "passive")],
          top=[("16", "VCC", 0, "power_in")],
          bottom=[("11", "S1", -7.62, "input"), ("10", "S2", -5.08, "input"), ("9", "S3", -2.54, "input"), ("6", "~{E}", 0, "input"),
                  ("8", "GND", 5.08, "power_in"), ("7", "VEE", 7.62, "power_in")])
ic_symbol("L78L05_SOT89", "U", 12.7, 7.62,
          left=[("3", "IN", 0, "power_in")], right=[("1", "OUT", 0, "power_out")], bottom=[("2", "GND", 0, "power_in")])
add_symbol("TL431_SOT23", "U",
           poly([(-1.27, 0.635), (1.27, 0.635), (0, -0.635), (-1.27, 0.635)]) + "\n    " +
           poly([(-1.27, -0.635), (1.27, -0.635), (1.27, -0.3)], w=0.254) + "\n    " + poly([(0, 2.54), (0, -2.54)]) + "\n    " +
           poly([(-2.54, 0), (-0.635, 0)]),
           [("2", "K", 0, 5.08, 270, "passive"), ("3", "A", 0, -5.08, 90, "passive"), ("1", "REF", -5.08, 0, 0, "input")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_names=True)
symbols.pop("R_Potentiometer", None)


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
    unit = lambda p, m, o: (tri, [(p, "+", -7.62, 2.54, 0, "input"), (m, "-", -7.62, -2.54, 0, "input"),
                                  (o, "~", 7.62, 0, 180, out_type)])
    pwr = (rect(-1.27, 2.54, 1.27, -2.54, fill="background"),
           [("8", "V+", 0, 5.08, 270, "power_in"), ("4", "V-", 0, -5.08, 90, "power_in")])
    add_units_symbol(name, "U", [unit("3", "2", "1"), unit("5", "6", "7"), pwr])


dual_amp("OPA2192", "output")
dual_amp("TLV9062", "output")
dual_amp("LM393", "open_collector")


# ----------------------------------------------------------------------------- module-specific symbols
ic_symbol("ISO7761", "U", 30.48, 17.78,
          left=[("2", "INA", 5.08, "input"), ("3", "INB", 2.54, "input"), ("4", "INC", 0, "input"), ("5", "IND", -2.54, "input"),
                ("6", "INE", -5.08, "input"), ("7", "OUTF", -7.62, "output")],
          right=[("15", "OUTA", 5.08, "output"), ("14", "OUTB", 2.54, "output"), ("13", "OUTC", 0, "output"),
                 ("12", "OUTD", -2.54, "output"), ("11", "OUTE", -5.08, "output"), ("10", "INF", -7.62, "input")],
          top=[("1", "VCC1", -7.62, "power_in"), ("16", "VCC2", 7.62, "power_in")],
          bottom=[("8", "GND1", -7.62, "power_in"), ("9", "GND2", 7.62, "power_in")],
          gfx_extra="\n    " + poly([(0, 8.89), (0, -8.89)], w=0.254))
ic_symbol("A0515S", "PS", 20.32, 10.16,
          left=[("1", "+VIN", 2.54, "power_in"), ("2", "-VIN", -2.54, "power_in")],
          right=[("6", "+VO", 2.54, "power_out"), ("5", "COM", 0, "power_out"), ("4", "-VO", -2.54, "power_out")],
          gfx_extra="\n    " + poly([(0, 5.08), (0, -5.08)], w=0.254))
ic_symbol("TLV760", "U", 12.7, 7.62,
          left=[("2", "IN", 0, "power_in")], right=[("1", "OUT", 0, "power_out")], bottom=[("3", "GND", 0, "power_in")])
ic_symbol("74LVC1G14", "U", 10.16, 7.62,
          left=[("2", "A", 0, "input"), ("1", "NC", -2.54, "no_connect")], right=[("4", "Y", 0, "output")],
          top=[("5", "VCC", 0, "power_in")], bottom=[("3", "GND", 0, "power_in")])
ic_symbol("DG419", "U", 12.7, 10.16,
          left=[("6", "IN", 0, "input")],
          right=[("1", "D", 2.54, "passive"), ("2", "S1", 0, "passive"), ("8", "S2", -2.54, "passive")],
          top=[("4", "V+", -2.54, "power_in"), ("5", "VL", 2.54, "power_in")],
          bottom=[("3", "GND", -2.54, "power_in"), ("7", "V-", 2.54, "power_in")])
ic_symbol("BAT54C", "D", 7.62, 7.62,
          left=[("1", "A1", 2.54, "passive"), ("2", "A2", -2.54, "passive")], right=[("3", "K", 0, "passive")])
box_symbol("Conn_01x05", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 6)], [], width=7.62, hide_pin_names=True)
