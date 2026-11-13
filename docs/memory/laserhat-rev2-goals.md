---
name: laserhat-rev2-goals
description: "Rev 2 LaserHAT goals — fix GitHub issue #3 bugs (display stays an external OLED bonnet) and split the analog output stage onto swappable daughterboards (laser / isolated estim)"
metadata:
  node_type: memory
  type: project
  originSessionId: 1e5b4086-f717-4b1c-9f99-2a4cfed7a528
  modified: 2026-09-26T03:17:08.918Z
---

Rev 2 goals, set 2026-09-25:
1. Fix the Rev 1 bugs in GitHub issue #3. The exception is "use the screen directly": the display stays the external Adafruit 128x32 OLED bonnet.
2. The base HAT keeps the MCU, the two BNCs (trigger in, stim mirror out), LEDs, USB-C (powering the MCU and Pi, plus UART) and the Pi UART. The laser-diode power stage (boost, current sink, LD connector) moves to a plug-in daughterboard. An alternative isolated constant-current electrical-stimulation daughterboard will use the same header.

User decisions (2026-09-25):
- The 5 V/12 V laser-compliance indicator (currently the RGB LED) belongs on the laser daughterboard. A lower-BOM alternative is welcome.
- Standalone MCU+OLED mode is set in hardware with solder jumpers (e.g. HAT 3.3 V onto header pin 1/17). The user likes solder jumpers for configuration options like this.
- The "fan connector" comment in issue #3 actually meant the PoE header. Target is the Pi 4; be Pi 5 compatible if it costs little.
- Stay on the 32-pin MSPM0G3507: minimum BOM is a major goal.
- Do the bug fixes and the daughterboard split together. Add a keep-out on the HAT where the daughterboard sits: next to the OLED bonnet and beside the BNCs.

**Why:** BNC I/O on its own is useful, and the MCU drives both output types.
**How to apply:** treat the daughterboard header as a stable interface. Put module-specific power (boost, isolated HV) on the daughterboards, not on the HAT.

Related: [[pcb-workspace-setup]]
