---
name: stim-hat-board
description: "2026-10-29: StimHAT rev A = the LaserHAT Rev 2 core + the e-stim stimulator on one HAT (LaserHAT/StimHAT/, generated like the pack board), decided in the 2026-10-28 brainstorm: 74HC4053 + DG418 instead of ADG1436 + DG419, I2C DAC kept (no SPI readback on the DAC60501), bonnet kept (NRST moved to GPIO16: the bonnet's joystick-right is GPIO23), five-way joystick, DC-DC PS1 under the tab or the pack on J102; branch worktree-stim-hat, not ordered"
metadata:
  type: project
  originSessionId: 3d2bbd2f-69c2-4c9f-abdd-a97d90e88da4
  modified: 2026-10-29T05:13:43.721Z
---

**StimHAT** (`LaserHAT/StimHAT/`, branch `worktree-stim-hat` off `battery-pack`, a git worktree at
`.claude/worktrees/stim-hat`): one 65 x 57 mm HAT + 12.5 mm south-east tab carrying the Rev 2 core (MSPM0G3507, CH340N,
USB-C path, EEPROM, BNCs, FIRE, joystick) and the kbest stimulator isolated by ISO7741F + ISO1640, powered by the A0515S
(PS1, hand-fitted on the back of the tab) or the battery pack (J102 B4B-PH-K-S).  Full record of the decisions and
rejected options in `LaserHAT/claude_memory/stim-hat-plan.md`; build details and checks in `StimHAT/README.md`.

Key facts not obvious from the code:
- The user wants the **bonnet (Adafruit 4567) kept** and a 0.91 in 128 x 32 module as the fallback (J10, unpopulated);
  no 128 x 64 panel (Pi software change).  Latency is sacred (no photoMOS SHORT switch); readback of the DAC matters.
- Pi side must use **GPIO16 for the MCU reset** on this board (`LASERHAT_RESET_PIN=16`); firmware adds BUTTON6 (PA3,
  joystick right); joystick is mounted at 45 degrees.
- pcb_sync-copied footprints share UUIDs -> run `tools/fresh_uuids.py` or KiCad's DRC pairs the wrong parts.
- Hand-fit: J1, J6, J7, J101, J102, PS1 (DNP in the BOM; never with the pack at the same time), J10 optional; MH4 nylon.

**Why:** the module + HAT + pack chain had become more complex and costlier than two dedicated HATs; see the plan note.
**How to apply:** treat StimHAT as a generated project (edit `sch_parts.py` / `gen_schematic.py` / `tools/place.py`, never
the .kicad files by hand); the laser HAT would reuse the same core block.

Related: [[battery-pack-board]], [[laserhat-next-tasks]], [[laserhat-user-preferences]].
