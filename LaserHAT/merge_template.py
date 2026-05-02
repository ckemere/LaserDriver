#!/usr/bin/env python3
"""
Merge PiHatTemplate into LaserHAT project files.

Strategy:
  Schematic: take template as base (preserving all symbols/wiring exactly),
             change paper to A3, add our three sub-sheet boxes at x≥230
             (clear of the template GPIO content at x=15–200), update title.
  PCB:       take template PCB as base, update sheetfile reference and title.

Run from repo root:
    .venv/bin/python3 LaserHAT/merge_template.py
"""

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_SCH = os.path.join(REPO, "PiHatTemplate", "PiHatTemplate.kicad_sch")
TEMPLATE_PCB = os.path.join(REPO, "PiHatTemplate", "PiHatTemplate.kicad_pcb")
OUT_SCH = os.path.join(REPO, "LaserHAT", "LaserDriver.kicad_sch")
OUT_PCB = os.path.join(REPO, "LaserHAT", "LaserDriver.kicad_pcb")

# ── Sub-sheet blocks to inject ────────────────────────────────────────────────
# Placed at x=230+ to avoid overlap with template GPIO content (x=15-200).
# Positions: Laser Driver (230,15), MSPM0 (230,65), USB-UART (230,125).
# Pin UUIDs and sheet UUIDs preserved from existing LaserDriver.kicad_sch.

SHEETS = """\
\t(sheet (at 230 15) (size 60 40)
\t\t(stroke (width 0.001) (type default))
\t\t(fill (color 0 0 0 0))
\t\t(uuid "212bfd25-f831-4b85-926b-000000000002")
\t\t(property "Sheet name" "Laser Driver Circuit"
\t\t\t(at 230 13.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Sheet file" "laser_driver_circuit.kicad_sch"
\t\t\t(at 230 56.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(pin "VCC_5V_IN" input (at 230 20 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "63e4b422-a2be-4159-8705-61812fad550c")
\t\t)
\t\t(pin "VCC_3V3" input (at 230 25 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "94d99303-80f2-46f7-9271-6a8a8db42ecb")
\t\t)
\t\t(pin "GND" input (at 230 30 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "fb3b18b2-61d5-41db-b136-4f4f43cfda0f")
\t\t)
\t\t(pin "PWM_LASER" input (at 230 35 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "d92fd3fe-e6fb-445a-aac5-164c02a2d5d3")
\t\t)
\t\t(pin "PWM_DUMMY" input (at 230 40 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "5658b652-1969-48d2-8b97-cd5093db4eda")
\t\t)
\t\t(pin "VREF" input (at 230 45 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "5a3bac91-5c60-4697-a9c3-7165eb5b7145")
\t\t)
\t)
\t(sheet (at 230 65) (size 70 50)
\t\t(stroke (width 0.001) (type default))
\t\t(fill (color 0 0 0 0))
\t\t(uuid "212bfd25-f831-4b85-926b-000000000003")
\t\t(property "Sheet name" "MSPM0 Controller"
\t\t\t(at 230 63.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Sheet file" "mspm0_controller.kicad_sch"
\t\t\t(at 230 116.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(pin "VCC_3V3_MCU" input (at 230 70 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "9dde647b-7d38-47de-bbdc-73a23765f5eb")
\t\t)
\t\t(pin "GND" input (at 230 75 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "801ea249-0063-4aeb-94cc-3151c897c741")
\t\t)
\t\t(pin "UART_TX" bidirectional (at 230 80 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "f7d7c50f-d2e8-4086-a11c-4355003dc42e")
\t\t)
\t\t(pin "UART_RX" bidirectional (at 230 85 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "2adaff01-3c83-4b81-ac67-dc4c032ebd10")
\t\t)
\t\t(pin "SWCLK" input (at 230 90 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "ac33a1a1-499b-4793-8394-9427fa4e49c5")
\t\t)
\t\t(pin "SWDIO" bidirectional (at 230 95 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "01234590-25c0-4007-9133-b2a32c0933fd")
\t\t)
\t\t(pin "NRST" input (at 230 100 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "df025f0e-9c65-48f6-8f72-0abb2d664d5a")
\t\t)
\t\t(pin "TRIGGER" input (at 300 70 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "1cc1be4d-56f1-487e-b211-303250f9e2d7")
\t\t)
\t\t(pin "PWM_LASER" output (at 300 75 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "3b9d3203-a8f2-4c50-ba86-3f7628bc7199")
\t\t)
\t\t(pin "PWM_DUMMY" output (at 300 80 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "26f17cb3-0284-4283-b0b1-a3d08089d02a")
\t\t)
\t\t(pin "VREF" output (at 300 85 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "33e88771-99cc-4d58-90df-b431aad981aa")
\t\t)
\t)
\t(sheet (at 230 125) (size 50 30)
\t\t(stroke (width 0.001) (type default))
\t\t(fill (color 0 0 0 0))
\t\t(uuid "212bfd25-f831-4b85-926b-000000000004")
\t\t(property "Sheet name" "USB-C UART"
\t\t\t(at 230 123.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(property "Sheet file" "usb_uart.kicad_sch"
\t\t\t(at 230 156.5 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t)
\t\t(pin "VBUS_5V" input (at 230 130 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "91f0ee2a-223b-43a2-800d-f134c2703291")
\t\t)
\t\t(pin "GND" input (at 230 135 180)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "45e1ac44-1c17-4743-90c2-e8fa6990d983")
\t\t)
\t\t(pin "UART_TX" bidirectional (at 280 130 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "2dca76ac-d718-4d4e-a64c-b6018b519225")
\t\t)
\t\t(pin "UART_RX" bidirectional (at 280 135 0)
\t\t\t(effects (font (size 1.27 1.27)))
\t\t\t(uuid "bc27ba62-5ee5-4a41-9cfe-c26fcac08c95")
\t\t)
\t)
"""

# ── Title block replacement ────────────────────────────────────────────────────

SCH_TITLE_BLOCK_OLD = '\t(title_block\n\t\t(date "15 nov 2012")\n\t)'
SCH_TITLE_BLOCK_NEW = (
    '\t(title_block\n'
    '\t\t(title "LaserDriver Pi HAT")\n'
    '\t\t(date "2026-05-01")\n'
    '\t\t(rev "0.1")\n'
    '\t\t(company "Rice University")\n'
    '\t\t(comment 1 "Pi HAT: MSPM0G3507 + MT3608 boost + laser driver + USB-C UART")\n'
    '\t\t(comment 2 "GPIO17=MCU power switch, GPIO14/15=UART, GPIO26=TRIGGER")\n'
    '\t\t(comment 3 "SWD 5-pin header for OpenOCD firmware updates (NRST/SWCLK/SWDIO/3V3/GND)")\n'
    '\t)'
)

PCB_TITLE_BLOCK_OLD = '\t(title_block\n\t\t(date "15 nov 2012")\n\t)'
PCB_TITLE_BLOCK_NEW = (
    '\t(title_block\n'
    '\t\t(title "Laser Diode Driver - Raspberry Pi HAT")\n'
    '\t\t(date "2026-05-01")\n'
    '\t\t(rev "0.1")\n'
    '\t\t(company "Rice University")\n'
    '\t\t(comment 1 "65x56.5 mm HAT - run Update PCB from Schematic before layout")\n'
    '\t)'
)


def merge_schematic():
    with open(TEMPLATE_SCH) as f:
        text = f.read()

    # 1. Change paper A4 → A3
    text = text.replace('(paper "A4")', '(paper "A3")', 1)

    # 2. Replace the title_block section (exact string match)
    if SCH_TITLE_BLOCK_OLD not in text:
        raise RuntimeError("Could not find expected title_block in template schematic")
    text = text.replace(SCH_TITLE_BLOCK_OLD, SCH_TITLE_BLOCK_NEW, 1)

    # 3. Insert our sub-sheet blocks just before (sheet_instances
    insert_before = "\t(sheet_instances"
    idx = text.rfind(insert_before)
    if idx < 0:
        raise RuntimeError("Could not find (sheet_instances in template schematic")
    text = text[:idx] + SHEETS + text[idx:]

    with open(OUT_SCH, "w") as f:
        f.write(text)
    print(f"  Wrote {OUT_SCH}")


def merge_pcb():
    with open(TEMPLATE_PCB) as f:
        text = f.read()

    # 1. Update sheetfile reference from template project to ours
    text = text.replace(
        '(sheetfile "RaspberryPi-HAT.kicad_sch")',
        '(sheetfile "LaserDriver.kicad_sch")',
    )

    # 2. Update title block (exact string match)
    if PCB_TITLE_BLOCK_OLD not in text:
        raise RuntimeError("Could not find expected title_block in template PCB")
    text = text.replace(PCB_TITLE_BLOCK_OLD, PCB_TITLE_BLOCK_NEW, 1)

    with open(OUT_PCB, "w") as f:
        f.write(text)
    print(f"  Wrote {OUT_PCB}")


if __name__ == "__main__":
    merge_schematic()
    merge_pcb()
    print("Done.")
