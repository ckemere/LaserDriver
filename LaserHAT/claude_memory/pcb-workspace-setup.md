---
name: pcb-workspace-setup
description: "LaserHAT PCB work stays inside the one repo checkout Claude is launched in, on branch pcb-rev2, using the \"kicad\" micromamba env and KiCad from /Applications"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1e5b4086-f717-4b1c-9f99-2a4cfed7a528
  modified: 2026-09-28T21:43:50.119Z
---

The user keeps several copies of this repo on the machine. Work only inside the checkout the session was started in. That was `.../temp/LaserDriver-PCBWorking` until 2026-09-28; the user then planned to move it to a new directory. Do the work on the feature branch `pcb-rev2`, and commit only when the user asks.

**Tooling:**
- **Python:** run it with `micromamba run -n kicad`. That env has kiutils 1.4.8, but no pcbnew.
- **pcbnew scripts:** use KiCad's bundled Python, `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
- **kicad-cli:** `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (v9.0.8). It is not on PATH.
- **freerouting:** `/Applications/freerouting.app`.

**Why:** the user said so explicitly at the start of the Rev 2 session.

**How to apply:**
- Never touch sibling checkouts.
- Don't commit on main.
- Don't create a new venv.

Related: [[laserhat-rev2-goals]], [[hat-manual-routing-handoff]].
