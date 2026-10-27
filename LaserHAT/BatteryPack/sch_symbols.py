#!/usr/bin/env python3
"""
Symbol library for the 4S 18650 battery pack board (copied from EStimDaughter/sch_symbols.py, 2026-10-26).  All symbols are embedded (no external libraries needed).
Connectivity is by net label on every pin; blocks are grouped and titled so it reads
as a functional schematic.  Open in KiCad 8 -> Schematic Editor and run ERC.
"""
import uuid, math

U = lambda: str(uuid.uuid4())
F = lambda v: f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)

# ----------------------------------------------------------------------------- symbol library
LIB = "battpack"
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

box_symbol("TL431_SOT23", "U", [("1", "REF", "input"), ("3", "A", "passive")], [("2", "K", "passive")], width=12.7)   # Hottech C181103: 1 REF, 2 K, 3 A
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
POWER_NETS = {"+BAT": False, "+SW": False, "+OUT": False, "+RUN": False, "+CHGB": False, "+G": False, "+GB": False,
              "+BATB": False, "VBUS": False, "VCHG": False, "GND": True, "0V": True}      # rev C: 0V = pack B's negative
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


add_symbol("TL431_SOT23", "U",
           poly([(-1.27, 0.635), (1.27, 0.635), (0, -0.635), (-1.27, 0.635)]) + "\n    " +
           poly([(-1.27, -0.635), (1.27, -0.635), (1.27, -0.3)], w=0.254) + "\n    " + poly([(0, 2.54), (0, -2.54)]) + "\n    " +
           poly([(-2.54, 0), (-0.635, 0)]),
           [("2", "K", 0, 5.08, 270, "passive"), ("3", "A", 0, -5.08, 90, "passive"), ("1", "REF", -5.08, 0, 0, "input")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_names=True)
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


dual_amp("LM393", "open_collector")


# ----------------------------------------------------------------------------- pack-specific symbols
# LED: pin 1 = K (left), 2 = A (right), like D; the KiCad LED_0603/0805 footprints put the cathode on pad 1
add_symbol("LED", "D", diode_gfx + "\n    " + poly([(0.3, 1.6), (1.3, 2.6)], w=0.254) + "\n    " + poly([(1.1, 1.6), (2.1, 2.6)], w=0.254),
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
# (rev A SPDT slide switch kept for reference; rev B uses SW_DPDT_CO below)
add_symbol("SW_SPDT", "SW", poly([(-2.54, 0), (-1.27, 0)]) + "\n    " + poly([(-1.27, 0), (1.6, 1.4)], w=0.381) + "\n    " +
           poly([(1.27, 1.27), (2.54, 1.27)]) + "\n    " + poly([(1.27, -1.27), (2.54, -1.27)]) + "\n    " +
           circ(-1.27, 0, 0.3) + "\n    " + circ(1.27, 1.27, 0.3) + "\n    " + circ(1.27, -1.27, 0.3),
           [("2", "C", -5.08, 0, 0, "passive"), ("1", "A", 5.08, 1.27, 180, "passive"), ("3", "B", 5.08, -1.27, 180, "passive")],
           ref_pos=(0, 3.81), val_pos=(0, -3.81), hide_pin_names=True)
# one 18650 contact clip (MYOUNG MY-18650-01): a single terminal, three PCB pins on one pad net
add_symbol("Clip18650", "BC", poly([(-1.27, 2.54), (-1.27, -2.54)], w=0.508) + "\n    " + poly([(-1.27, 2.54), (0.5, 2.54), (1.27, 1.9)]) + "\n    " +
           poly([(-1.27, -2.54), (0.5, -2.54), (1.27, -1.9)]) + "\n    " + circ(-0.4, 0, 0.5),
           [("1", "~", -3.81, 0, 0, "passive")],
           ref_pos=(0, 4.45), val_pos=(0, -4.45), hide_pin_numbers=True, hide_pin_names=True)
box_symbol("Conn_01x02", "J", [("1", "Pin_1", "passive"), ("2", "Pin_2", "passive")], [], width=7.62, hide_pin_names=True)
box_symbol("Conn_01x03", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 4)], [], width=7.62, hide_pin_names=True)
box_symbol("Conn_01x05", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 6)], [], width=7.62, hide_pin_names=True)
# mounting hole: no pins
add_symbol("MountingHole", "H", circ(0, 0, 1.27) + "\n    " + circ(0, 0, 0.6), [], ref_pos=(0, 3.81), val_pos=(0, -3.81))


# ----------------------------------------------------------------------------- rev B (2026-10-26): charger, balancers, toggle
# DPDT centre-off toggle (MTS-203): pole 1 = pins 1 (throw) 2 (common) 3 (throw), pole 2 = 4 5 6.  Drawn commons left.
def _spdt(y):
    return (poly([(-2.54, y), (-1.27, y)]) + "\n    " + poly([(-1.27, y), (1.6, y + 1.4)], w=0.381) + "\n    " +
            poly([(1.27, y + 1.27), (2.54, y + 1.27)]) + "\n    " + poly([(1.27, y - 1.27), (2.54, y - 1.27)]) + "\n    " +
            circ(-1.27, y, 0.3) + "\n    " + circ(1.27, y + 1.27, 0.3) + "\n    " + circ(1.27, y - 1.27, 0.3))
add_symbol("SW_DPDT_CO", "SW", _spdt(3.81) + "\n    " + _spdt(-3.81) + "\n    " +
           poly([(0.2, 2.9), (0.2, -4.7)], w=0.127),
           [("2", "C1", -5.08, 3.81, 0, "passive"), ("1", "A1", 5.08, 5.08, 180, "passive"), ("3", "B1", 5.08, 2.54, 180, "passive"),
            ("5", "C2", -5.08, -3.81, 0, "passive"), ("4", "A2", 5.08, -2.54, 180, "passive"), ("6", "B2", 5.08, -5.08, 180, "passive")],
           ref_pos=(0, 8.89), val_pos=(0, -8.89), hide_pin_names=True)
# Schottky diode: pin 1 = K, 2 = A (D_SMA pad 1 = cathode)
schottky_gfx = diode_gfx + "\n    " + poly([(-1.27, 1.27), (-1.905, 1.27), (-1.905, 0.9)], w=0.508) + "\n    " + \
               poly([(-1.27, -1.27), (-0.635, -1.27), (-0.635, -0.9)], w=0.508)
add_symbol("D_Schottky", "D", schottky_gfx,
           [("1", "K", -3.81, 0, 0, "passive"), ("2", "A", 3.81, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
# inductor, horizontal: pin 1 left, 2 right
_coil = "\n    ".join(poly([(x - 1.27 + 0.3175 * k, 0.0 + 1.2 * math.sin(math.pi * k / 8)) for k in range(9)], w=0.254)
                      for x in (-2.54, 0, 2.54))
add_symbol("L", "L", _coil + "\n    " + poly([(-3.81, 0), (-3.81, 0)]),
           [("1", "~", -5.08, 0, 0, "passive"), ("2", "~", 5.08, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)
# polarised capacitor: pin 1 = + (top), 2 = - (CP_Elec pad 1 = +)
add_symbol("CP", "C", poly([(-2.032, 0.762), (2.032, 0.762)], w=0.508) + "\n    " + rect(-2.032, -0.508, 2.032, -1.016, fill="outline") +
           "\n    " + poly([(-1.8, 2.2), (-1.0, 2.2)], w=0.254) + "\n    " + poly([(-1.4, 2.6), (-1.4, 1.8)], w=0.254),
           [("1", "+", 0, 3.81, 270, "passive"), ("2", "-", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
# NTC thermistor, drawn like R with a bar
add_symbol("Thermistor", "RT", rect(-1.016, -2.54, 1.016, 2.54) + "\n    " + poly([(-2.0, -2.2), (-1.2, -2.2), (1.6, 2.2)], w=0.254),
           [("1", "~", 0, 3.81, 270, "passive"), ("2", "~", 0, -3.81, 90, "passive")],
           ref_pos=(2.54, 1.27), val_pos=(2.54, -1.27), hide_pin_numbers=True, hide_pin_names=True)
box_symbol("Conn_01x04", "J", [(str(i), f"Pin_{i}", "passive") for i in range(1, 5)], [], width=7.62, hide_pin_names=True)
# CN3704 4-cell buck charger, TSSOP-16
ic_symbol("CN3704", "U", 20.32, 27.94,
          left=[("15", "VCC", 12.7, "power_in"), ("1", "VG", 10.16, "passive"), ("16", "DRV", 7.62, "output"),
                ("4", "CHRG", 2.54, "open_collector"), ("5", "DONE", 0, "open_collector"), ("6", "TEMP", -5.08, "input"),
                ("7", "EOC", -7.62, "input"), ("10", "test", -10.16, "input"), ("12", "NC", -12.7, "no_connect")],
          right=[("13", "CSP", 10.16, "input"), ("14", "BAT", 7.62, "input"), ("8", "COM1", 0, "passive"),
                 ("9", "COM2", -2.54, "passive"), ("11", "COM3", -5.08, "passive")],
          bottom=[("3", "GND", -2.54, "power_in"), ("2", "PGND", 2.54, "power_in")])
# CH224A USB PD sink controller, ESSOP-10 (pin 11 = exposed pad = GND)
ic_symbol("CH224A", "U", 15.24, 20.32,
          left=[("1", "VHV", 7.62, "power_in"), ("8", "VBUS", 5.08, "input"), ("7", "CC1", 0, "bidirectional"),
                ("6", "CC2", -2.54, "bidirectional"), ("4", "DP", -5.08, "bidirectional"), ("5", "DM", -7.62, "bidirectional")],
          right=[("9", "CFG1", 5.08, "input"), ("2", "CFG2", 2.54, "input"), ("3", "CFG3", 0, "bidirectional"),
                 ("10", "PG", -5.08, "open_collector")],
          bottom=[("11", "GND", 0, "power_in")])
# HY2213-BB3A single-cell balance IC, SOT-23-6: 2 VDD, 3 VSS, 6 OUT, 1/4/5 NC
ic_symbol("HY2213", "U", 12.7, 15.24,
          left=[("2", "VDD", 5.08, "passive"), ("3", "VSS", -5.08, "passive")],
          right=[("6", "OUT", 5.08, "output"), ("1", "NC", 0, "no_connect"), ("4", "NC", -2.54, "no_connect"), ("5", "NC", -5.08, "no_connect")])
# USB-C receptacle (HRO TYPE-C-31-M-12, USB 2.0): pad names as in the KiCad footprint
ic_symbol("USB_C_16P", "J", 15.24, 25.4,
          left=[("A4", "VBUS", 10.16, "passive"), ("B4", "VBUS", 7.62, "passive"), ("A9", "VBUS", 5.08, "passive"), ("B9", "VBUS", 2.54, "passive")],
          right=[("A5", "CC1", 7.62, "passive"), ("B5", "CC2", 5.08, "passive"), ("A6", "D+", 2.54, "passive"), ("B6", "D+", 0, "passive"),
                 ("A7", "D-", -2.54, "passive"), ("B7", "D-", -5.08, "passive"), ("A8", "SBU1", -7.62, "passive"), ("B8", "SBU2", -10.16, "passive")],
          bottom=[("A1", "GND", -5.08, "passive"), ("B1", "GND", -2.54, "passive"), ("A12", "GND", 0, "passive"), ("B12", "GND", 2.54, "passive"),
                  ("S1", "SH", 5.08, "passive")])
