---
name: laserhat-next-tasks
description: "Next LaserHAT tasks as of 2026-09-28 — bring back the e-stim module's fault-detector circuit, and test whether SMA instead of BNC on the HAT lets the e-stim daughterboard become single-sided assembly"
metadata:
  node_type: memory
  type: project
  originSessionId: 1e5b4086-f717-4b1c-9f99-2a4cfed7a528
  modified: 2026-09-28T21:44:06.107Z
---

Planned next (the user, 2026-09-28):

1. **Bring back the e-stim module's fault detector.**
   - `LaserHAT/EStimDaughter` dropped its LM393 compliance/over-current window (U8, 9 R, 2 C) on 2026-09-26 because it wouldn't route. See `EStimDaughter/DESIGN_NOTES.md`.
   - FAULT_n now only means "isolated side powered", via R19 4.7k and ISO7761F reverse channel → J8.5.
   - The HAT side is ready: J8.5 → PA6 = TIMA0_FAULT0, a latched hardware kill of PWM_A (PA7, CCP1) and PWM_B (PA12, CCP3).
   - The e-stim docs still say PA26 for FAULT: out of date.
2. **SMA vs BNC experiment.**
   - The e-stim module outline is capped at x = 127.5 because HAT BNC J6 (TRIG IN) starts at x ≈ 128. See `estim_interface/ESTIM_MODULE_SPEC.md`.
   - The module is 26.5 × 23.5 mm, 4 layers, double-sided (15 SMT top, 27 bottom). Its README says single-sided needs about 1.7× the usable top area.
   - Question: would smaller SMA jacks on the HAT (J6/J7) free enough room to enlarge the module to single-sided assembly?

**Why:** single-sided assembly is cheaper at JLC (Economic tier). Restoring on-board compliance/open-electrode detection is a safety improvement.

**How to apply:**
- Any HAT outline or connector change must respect the hand layout (see [[hat-manual-routing-handoff]]).
- Any J8/J9 contract change goes to `estim_interface/QUESTIONS.md` as a NOTICE.

Related: [[laserhat-rev2-goals]], [[laserhat-user-preferences]].
