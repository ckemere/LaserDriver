---
name: laserhat-fault-detector-handoff
description: "State of the e-stim fault-detector restore and the SMA-vs-BNC study when the session paused on 2026-09-28 (moving machines); what was read, decided and changed"
metadata:
  type: project
---

Paused 2026-09-28 while moving to another computer. Repo: branch `pcb-rev2` at `af9df99`, nothing committed since.

**Only repo change so far:** `EStimDaughter/sim/models/LM393_LM2903B.lib` copied from `kbest/models/` (TI LM2903B PSpice model, SLCJ016; subckt `LM2903B IN+ IN- Vcc GND OUT`). Not yet listed in `sim/models/README.md`.

**Task 1 plan (fault detector), decided from the history in `kbest` (commit 9d8db45 removed it):**
- Restore the rev E / M1 LM393 window exactly as it was: E1 -> 100k / 12k-to-GND / 27k-to-+5V_ISO (+100p) = 0.0767*E1 + 1.42 V; TH_P from +V via 110k/12k/27k, TH_N from -V likewise; LM393 open-collector outputs wired-OR onto FAULT_n with the existing R19 4.7k pull-up. Trips at |E1| ~ 0.915*V (13.9 V at +/-15 V), 7-11 us before U5A saturates; open electrode trips within ~5 us of the first phase. New refs planned: U8 LM393 (VSSOP-8, C34440), R20-R28, C18 100p, C19 100n.
- Board-space argument: the window was dropped in the same commit that replaced the 8-part MOSFET SHORT with the DG419 (net -25 mm2); isolated-domain courtyard fill today is ~51 % top / ~41 % bottom, so ~39 mm2 more should fit. Rebuild the e-stim PCB with `tools/route_pcb.py` (SEEDS env, Freerouting) after backing up to `LaserHAT/stash/`.
- Sim: add `monitor()` to `sim/spice.py` + new `sim/fault.py` (thresholds vs rail 12/15/16.8/18 V; pw sweep across saturation at 250 uA; open electrode; no false trip on in-compliance trains incl. DG419 injection; 10 uA ISO7761 input load). ngspice 47 is at /opt/homebrew/bin/ngspice.
- Docs to fix: `EStimDaughter/README.md`, `DESIGN_NOTES.md` and `estim_interface/ESTIM_MODULE_SPEC.md` still list PA21/PA22/PA26/PA16; current map is EN PA7 (TIMA0_CCP1), CATH PA12 (CCP3), FAULT_n PA6 (FAULT0), CS_n PA15, SCK PA17, MOSI PA22. Also update REV2_NOTES e-stim summary, `fab/README.md`, bom via `tools/make_bom.py`, and add NOTICE 11 in QUESTIONS.md.

**Task 2 numbers gathered (SMA vs BNC), HAT coordinates:**
- BNC J6/J7 footprints: x 127.48-143.12 and 142.78-158.41, on-board depth y 79.56-100. Centre pins at (135.30, 87.55) and (150.60, 87.55); BNC_IN/BNC_OUT tracks are short B.Cu runs from vias near U8 at y ~68-70.
- East of x 127.5 in y 76-100 only: SW6 BSL (y 73.2-76.8, x 136-142), LEDs D7/D9 + R15/R18 (x 158.7-164, y 76-82), FIRE SW9 (x 160.5-164, y 86-92), MH4 (161.5, 96.5), logo (x 151-162.6, y 60-74).
- KiCad SMA footprints: edge-mount Amphenol 132289 courtyard 17.6 x 11.2 (about 3.1 mm on-board, 11.2 wide incl. courtyard; body 6.35); Samtec SMA-J-P-H-ST-EM1 edge mount 8.1 wide, 2.65 on-board; vertical 132134 8.4 x 8.4; right-angle 901-143 8.7 wide x 4.3 on-board.
- E-stim module today: 623 mm2, top SMD courtyard 153 mm2 (15 parts), bottom 141 mm2 (27); isolated-domain usable top area ~220 mm2. Single-sided with the fault detector needs roughly 450-540 mm2 of isolated top area (2.1-2.5x), i.e. module east edge near x 146-151, which needs one SMA moved to the east edge (y ~ 62-72, logo moves) and the module's barrier/domain layout redrawn. Both SMAs on the south edge east of x ~141 gives only ~1.5x.

**How to apply:** continue from here; don't redo the reading. User wants numbers + recommendation for task 2 before either board changes.

Related: [[laserhat-next-tasks]], [[hat-manual-routing-handoff]], [[laserhat-user-preferences]].
