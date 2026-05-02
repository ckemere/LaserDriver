#!/usr/bin/env python3
"""
Fix floating hierarchical_labels in child schematics.

Rule: every label must be connected to a component pin via a net (wire).
The generated schematics had hierarchical_labels placed at sheet-edge
coordinates (5, 20-80) and (200, 20-50) with no wire connections, and used
local labels at the actual pin wire stubs.

Fix:
  1. Remove all floating hierarchical_labels.
  2. Replace each connected local label at a wire stub with a
     hierarchical_label of the same name, position, and direction.
  3. For VCC_3V3_MCU/GND in the MSPM0 sheet: add short wires + junctions +
     hierarchical_labels branching off the MCU VDD/VSS pin connections
     (which already have power symbols placed there).

Run from repo root:
    .venv/bin/python3 LaserHAT/fix_labels.py
"""

import os, uuid as _uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSPM0 = os.path.join(REPO, "LaserHAT", "mspm0_controller.kicad_sch")
USBUART = os.path.join(REPO, "LaserHAT", "usb_uart.kicad_sch")

def uid():
    return str(_uuid.uuid4())

# ── helpers ──────────────────────────────────────────────────────────────────

def remove_block(text, start_tag):
    """Remove a top-level S-expr block that begins with start_tag."""
    idx = text.find(start_tag)
    while idx >= 0:
        depth = 0
        end = idx
        for i, ch in enumerate(text[idx:]):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    end = idx + i + 1
                    break
        # consume trailing newline
        if end < len(text) and text[end] == '\n':
            end += 1
        text = text[:idx] + text[end:]
        idx = text.find(start_tag)
    return text

def replace_label_with_hlabel(text, label_name, x, y, angle, shape):
    """Replace one (label "name" (at x y angle) ...) with a hierarchical_label."""
    # Build the exact at-string to find the specific label
    at_str = f'(at {x} {y} {angle})'
    search = f'  (label "{label_name}" {at_str}'
    idx = text.find(search)
    if idx < 0:
        print(f"  WARNING: could not find label '{label_name}' at {x},{y},{angle}")
        return text
    # Find the end of this block
    depth = 0
    end = idx
    for i, ch in enumerate(text[idx:]):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                end = idx + i + 1
                break
    if end < len(text) and text[end] == '\n':
        end += 1
    # Build replacement hierarchical_label
    new_uuid = uid()
    new_block = (
        f'  (hierarchical_label "{label_name}" (shape {shape}) {at_str}\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'    (uuid "{new_uuid}")\n'
        f'  )\n'
    )
    return text[:idx] + new_block + text[end:]

def add_before(text, anchor, new_content):
    """Insert new_content immediately before the first occurrence of anchor."""
    idx = text.find(anchor)
    if idx < 0:
        raise RuntimeError(f"anchor not found: {anchor!r}")
    return text[:idx] + new_content + text[idx:]

def wire_block(x1, y1, x2, y2):
    return (
        f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2}))\n'
        f'    (stroke (width 0) (type default))\n'
        f'    (uuid "{uid()}")\n'
        f'  )\n'
    )

def junction_block(x, y):
    return (
        f'  (junction\n'
        f'    (at {x} {y})\n'
        f'    (diameter 0)\n'
        f'    (color 0 0 0 0)\n'
        f'    (uuid "{uid()}")\n'
        f'  )\n'
    )

def hlabel_block(name, shape, x, y, angle):
    return (
        f'  (hierarchical_label "{name}" (shape {shape}) (at {x} {y} {angle})\n'
        f'    (effects (font (size 1.27 1.27)))\n'
        f'    (uuid "{uid()}")\n'
        f'  )\n'
    )

# ── MSPM0 fix ─────────────────────────────────────────────────────────────────

def fix_mspm0():
    with open(MSPM0) as f:
        text = f.read()

    # 1. Remove all floating hierarchical_labels (all at x=5 or x=200)
    for tag in [
        '  (hierarchical_label "VCC_3V3_MCU"',
        '  (hierarchical_label "GND" (shape input) (at 5',
        '  (hierarchical_label "UART_TX" (shape bidirectional) (at 5',
        '  (hierarchical_label "UART_RX" (shape bidirectional) (at 5',
        '  (hierarchical_label "SWCLK"',
        '  (hierarchical_label "SWDIO"',
        '  (hierarchical_label "NRST"',
        '  (hierarchical_label "TRIGGER"',
        '  (hierarchical_label "PWM_LASER"',
        '  (hierarchical_label "PWM_DUMMY"',
        '  (hierarchical_label "VREF"',
    ]:
        text = remove_block(text, tag)

    # 2. Replace connected local labels with hierarchical_labels
    #    (position, angle, shape derived from the parent sheet's pin definitions)
    signal_labels = [
        # (name, x, y, angle, shape)
        ("NRST",      72.06, 52.54,  180, "input"),
        ("UART_TX",   72.06, 85.08,  180, "bidirectional"),
        ("UART_RX",   72.06, 82.54,  180, "bidirectional"),
        ("VREF",      72.06, 90.16,  180, "output"),
        ("SWCLK",     72.06, 100.32, 180, "input"),
        ("SWDIO",     72.06, 97.78,  180, "bidirectional"),
        ("PWM_LASER", 127.94, 97.78,   0, "output"),
        ("PWM_DUMMY", 127.94, 95.24,   0, "output"),
        ("TRIGGER",   127.94, 90.16,   0, "input"),
    ]
    for name, x, y, angle, shape in signal_labels:
        text = replace_label_with_hlabel(text, name, x, y, angle, shape)

    # 3. Add VCC_3V3_MCU and GND hierarchical_labels connected via short wire
    #    stubs branching off the MCU VDD (77.14, 110.0) and VSS (77.14, 50.0)
    #    pin connection points (where +3V3 / GND power symbols already sit).
    #    Wire goes 5.08 mm to the left so the label sits at x=72.06.
    new_elements = (
        # VCC_3V3_MCU: branch left from MCU VDD at (77.14, 110.0)
        junction_block(77.14, 110.0) +
        wire_block(77.14, 110.0, 72.06, 110.0) +
        hlabel_block("VCC_3V3_MCU", "input", 72.06, 110.0, 180) +
        # GND: branch left from MCU VSS at (77.14, 50.0)
        junction_block(77.14, 50.0) +
        wire_block(77.14, 50.0, 72.06, 50.0) +
        hlabel_block("GND", "input", 72.06, 50.0, 180)
    )
    # Insert before sheet_instances
    text = add_before(text, "  (sheet_instances", new_elements)

    with open(MSPM0, 'w') as f:
        f.write(text)
    print(f"  Wrote {MSPM0}")

# ── USB-UART fix ──────────────────────────────────────────────────────────────

def fix_usbuart():
    with open(USBUART) as f:
        text = f.read()

    # 1. Remove all floating hierarchical_labels
    for tag in [
        '  (hierarchical_label "VBUS_5V"',
        '  (hierarchical_label "GND"',
        '  (hierarchical_label "UART_TX"',
        '  (hierarchical_label "UART_RX"',
    ]:
        text = remove_block(text, tag)

    # 2. Replace connected local labels with hierarchical_labels
    #    UART_TX and UART_RX: at the far ends of the SB1/SB2 solder bridge stubs
    #    VBUS_5V: at the USB connector VBUS pin wire stub end
    #    GND: at the USB connector GND pin wire stub end
    signal_labels = [
        # (name, x, y, angle, shape)
        ("UART_TX",  145.0, 66.89,  90, "bidirectional"),
        ("UART_RX",  145.0, 76.89,  90, "bidirectional"),
        ("VBUS_5V",   33.57, 70.16, 180, "input"),
        ("GND",       33.57, 49.84, 180, "input"),
    ]
    for name, x, y, angle, shape in signal_labels:
        text = replace_label_with_hlabel(text, name, x, y, angle, shape)

    with open(USBUART, 'w') as f:
        f.write(text)
    print(f"  Wrote {USBUART}")

if __name__ == "__main__":
    fix_mspm0()
    fix_usbuart()
    print("Done.")
