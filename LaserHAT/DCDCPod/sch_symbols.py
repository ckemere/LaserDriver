#!/usr/bin/env python3
"""
Symbol library for the DC-DC pod (2026-10-29): the subset of StimHAT/sch_symbols.py the pod needs.  All symbols are
embedded; the engine writes them into the schematic and into dcdcpod.kicad_sym.
"""
import math
import uuid

U = lambda: str(uuid.uuid4())  # noqa: E731
F = lambda v: f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)  # noqa: E731

LIB = "dcdcpod"
symbols = {}          # name -> (sexpr text, {pin_number: (x, y, angle)}) in symbol coords (y up)
UNITS = {}            # multi-unit symbols: none here


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
_coil = "\n    ".join(poly([(x - 1.27 + 0.3175 * k, 0.0 + 1.2 * math.sin(math.pi * k / 8)) for k in range(9)], w=0.254)
                      for x in (-2.54, 0, 2.54))
add_symbol("L", "L", _coil,
           [("1", "~", -5.08, 0, 0, "passive"), ("2", "~", 5.08, 0, 180, "passive")],
           ref_pos=(0, 2.54), val_pos=(0, -2.54), hide_pin_numbers=True, hide_pin_names=True)


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


# True = drawn as a ground-style symbol (points down); 0V is the isolated output reference
POWER_NETS = {"+5V": False, "GND": True, "0V": True}
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


# Mornsun A0515S-1WR3 (SIP-7 with pins 1 2 4 5 6): 1 +Vin, 2 -Vin (GND), 4 -Vo, 5 0V (COM), 6 +Vo
ic_symbol("A0515S", "PS", 20.32, 10.16,
          left=[("1", "+VIN", 2.54, "power_in"), ("2", "-VIN", -2.54, "power_in")],
          right=[("6", "+VO", 2.54, "power_out"), ("5", "COM", 0, "power_out"), ("4", "-VO", -2.54, "power_out")],
          gfx_extra="\n    " + poly([(0, 5.08), (0, -5.08)], w=0.254))
