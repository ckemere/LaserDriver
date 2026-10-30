---
name: laser-driver-hat
description: "2026-10-30: LaserDriverHAT = the StimHAT's HAT core + the LaserDaughter laser driver block on one HAT (LaserHAT/LaserDriverHAT/, generated like the StimHAT); e-stim half removed, one GND; module layout imported as a block at (-62.5, -57.25); 7 connections left for hand routing; branch worktree-stim-hat, not committed / not ordered"
metadata:
  type: project
---

**LaserDriverHAT** (`LaserHAT/LaserDriverHAT/`, project name LaserDriverHAT, library nickname `laserdriverhat`, fab
`LaserHAT/fab/LaserDriverHAT/`): copy of the StimHAT with the isolated stimulator (U101-U110, R101-R121, C101-C127,
D101-D104, J101-J103, TP101/102, GND_ISO and the barrier rules / rule areas) removed and the LaserDaughter module's 26
parts added in `sch_parts.py` (refs kept where free - D1-D4, J2, J4, L1, Q1, Q2, Rs1, SW5 - else +200: R201-R206,
R211/R212, C208/C209/C211/C212, U202/U203, J205; mapping in `sch_parts.MODULE_REFS`; module headers J1/J3 dropped).

Key facts not obvious from the code:
- Pin map: PA22 DB_PWM_A = TIMA0_C1 (firmware CCP1, laser switch), PA23 DB_PWM_B = TIMA0_C3 (CCP3, dummy), PA15 DB_DAC
  (DAC0, only pin), so BUTTON3 moved PA15 -> PA6 (pin 10); PA26/PA27 DB_ADC_A/B = ADC0 ch1/ch0; PA3/PA24/PA25 spare; no
  fault line (the laser module never had one).  Firmware edits are only drafted in the README, Firmware/ untouched.
- Board: HAT core footprints and 450 StimHAT tracks unchanged; the module layout (all tracks/vias/footprints, its F+B GND
  pour as "Laser GND pour") translated by (-62.5, -57.25), not rotated -> x 38.5-65, y 18.75-42.25 against the east edge;
  In1 one GND plane, F/B full GND pours.  `place.py` table holds exact module positions (Rs1 y 38.4125, U203 x 56.9875:
  rounding to 0.01 shifted pads off the module copper once).
- Open (user hand-routes): +5V to the block (~0.85 A for the boost - StimHAT +5V path has 0.3 mm outer segments), DB_PWM_A/B,
  DB_DAC, DB_ADC_A/B from U7 to the dangling stubs where the module headers were, BUTTON3 PA6 -> SW7.1.
- Checks at creation: ERC 0, netcheck OK, path 0, sync 0, DRC 0 errors / 7 unconnected; `laser_r202_one_spoke` DRU rule
  covers the module's own starved_thermal on R2 (= R202) pad 2.
- Session scripts (derive_board.py, prune/trim, synctable.py, pipeline.sh, verify_block.py) live in
  `~/.claude/jobs/3d2bbd2f/tmp/laserhat/`, not in the repo.

Related: [[stim-hat-board]], [[laserhat-user-preferences]].
