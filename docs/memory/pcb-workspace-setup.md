---
name: pcb-workspace-setup
description: "LaserHAT PCB work stays inside the one checkout the session was launched in, on branch pcb-rev2; commit only when asked; tool paths differ per machine"
metadata:
  type: feedback
---

The user keeps several copies of this repo and works from several machines. Work only inside the checkout the session
was started in, on branch `pcb-rev2`, and commit/push only when the user asks (they do ask, e.g. "commit and push").

**Tooling by machine** (fix this file for the machine you are on):
- Ubuntu box (2026-09-28, checkout `~/Code/LaserDriver`): Python for everything = `~/.venvs/kicad/bin/python` (sees the
  system `pcbnew`, kiutils 1.4.8, numpy, matplotlib); `kicad-cli` 9.0.8 and `ngspice` 45 on PATH; Freerouting jar
  `~/Tools/freerouting-2.4.1.jar` run with the Java 25 in `~/Tools/jdk-25*/bin/java`; kbest repo (e-stim history) at
  `~/Code/kbest`. Git identity not configured: commits used `-c user.name="Caleb Kemere" -c user.email="ckemere@gmail.com"`.
- macOS (2026-09-25..28): `micromamba run -n kicad` for kiutils scripts, KiCad's bundled Python for `pcbnew`,
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`, `/Applications/freerouting.app`.
- The e-stim tools take `FREEROUTING`, `KICAD_CLI`, `KICAD_FOOTPRINTS` from the environment; the HAT tools still have
  the macOS paths hard-coded.

**Repository moved (2026-11-13):** the project now lives at github.com/glanceneuro/glance-out (public; branch main = the restructured tree: hardware/, firmware/, pi/, docs/; archived boards at tag archive/pre-glance-cleanup).  Push with the SSH alias `github-glance-out-repo` (deploy key ~/.ssh/glance_out, write access); remote name `glance` in the stim-hat worktree, whose `origin` is still the old ckemere/LaserDriver.  CI run state via api.github.com/repos/glanceneuro/glance-out/actions/runs (tmp helpers ci_status.py / watch_ci.sh take REPO=...).

**Why:** said explicitly at the start of the Rev 2 session and again when moving machines.
**How to apply:** never touch sibling checkouts; don't commit on main; don't create a new venv.

Related: [[laserhat-rev2-goals]], [[hat-manual-routing-handoff]], [[estim-module-status]].
