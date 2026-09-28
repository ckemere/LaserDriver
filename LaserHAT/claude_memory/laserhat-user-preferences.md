---
name: laserhat-user-preferences
description: "How the LaserHAT user likes PCB work done — hand-routing with Claude as checker/tidier, pin choices verified against the pin mux, clean geometry, minimal silkscreen, Mouser-available parts"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1e5b4086-f717-4b1c-9f99-2a4cfed7a528
  modified: 2026-09-28T21:43:58.914Z
---

Preferences shown during the Rev 2 HAT work (2026-09-25 to 2026-09-28):

- **Routing:**
  - The user routes critical boards by hand. They rejected the freerouting result ("I can do better").
  - Claude's role is pin-map optimisation (fewest vias), checking, and geometric clean-up. Automatic re-routing is not wanted.
- **Geometry:**
  - Traces through the 0.1″ header run exactly on pad midlines.
  - Traces leave pads straight and hit vias head-on, with no tiny jags.
  - Straight 45°/90° segments only.
- **Silkscreen:**
  - Minimal: hide reference designators except the solder jumpers.
  - Descriptive labels at ≥ 1.0 mm (1.5 mm where there's room). JLC can't print 0.6 mm legibly.
- **Pin changes:**
  - The user proposes swaps; Claude checks them against the SysConfig pin mux (`rhb_pinmux` data) and timer/fault constraints.
  - Say plainly when a swap is impossible, and offer the nearest valid alternative. Don't silently skip it.
  - When the user asks for a change, make it; don't only describe it.
- **Parts:** good Mouser US availability and a good KiCad footprint. The user has stock of Amphenol 031-5539 BNCs. They like solder jumpers for configuration options.
- **Safety:** the hardware TIMA fault kill for the stim output is valued ("nice, easy to route"). Keep PWM_A/B + FAULT on one TIMA timer.

**Why:** stated or demonstrated repeatedly. The user was frustrated when requested schematic changes weren't actually applied, and when an F8 update moved parts.

**How to apply:**
- Verify every edit with DRC, against the project rules.
- Back up the board to `stash/` first.
- Report what changed and what was left for the user.

Related: [[hat-manual-routing-handoff]], [[pcb-workspace-setup]].
