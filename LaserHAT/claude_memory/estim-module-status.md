---
name: estim-module-status
description: "E-stim daughterboard state on 2026-09-29: rev M4 (I2C DAC60501 via ISO1640, ISO7741F with a dedicated RELEASE line, fault detector, 26.5 x 36.5 mm single-sided) placed but not routed; the decisions behind it and what was rejected"
metadata:
  type: project
---

**Where it is (commit `ba12414`, branch pcb-rev2):** schematic final (netcheck OK, ERC 0), board placed only — the
user hand-routes it (possibly in another Claude session; see `EStimDaughter/LAYOUT_HANDOFF.md`). Fab outputs are
the older M3 set. Contract with the HAT: `estim_interface/ESTIM_MODULE_SPEC.md` §7 (the old QUESTIONS.md log is gone).

**Decisions (2026-09-28/29), in order:**
1. Fault detector restored (rev E LM393 window, U8 + R20–R28 + C18/C19). Simulated: fires 7–12 µs before the current
   collapses, open electrode in 3.8 µs, no false trips.
2. Packages shrunk: 74HC4053BQ (DHVQFN-16), DG419BDQ (MSOP-8: 15 Ω, 38 pC, 12 pF — sims re-run, PM 67°/46°).
3. The 26.5 × 23.5 mm outline would not autoroute even so (best 4–6 nets open over 27 seeds). Rejected: SMA jacks
   instead of the HAT's BNCs (schematic change made then reverted, `b6c5e68`/`e20dc60`; study in `SMA_VS_BNC_STUDY.md`),
   a 2×5 header at one end. **Chosen: extend 12.5 mm south over the Pi's port edge** → 26.5 × 36.5 mm, single-sided
   (JLC economic). Rev M3 (`bbd4e76`) is that board autorouted DRC-clean.
4. **Batteries instead of the DC-DC** (PS1 stays DNP; ±V/0V pads). Offered but not yet added: keyed JST-PH pack
   connector, reverse-polarity Schottkys, a power switch.
5. Noise (µV recording) is the concern, not safety: no bleed resistor across the barrier; bond the Pi's ground to the
   recording ground; keep the ISO77xx (1 pF) rather than optos (3–5 pF).
6. **Rev M4: dedicated SHORT-release line.** I²C DAC60501Z (internal 2.5 V ref ÷ 2, 0–1.25 V, addr 0x48) through an
   ISO1640, ISO7741F for EN/CATH/RELEASE + FAULT_n; J9.3/4/5 = RELEASE/SCL/SDA (no HAT copper change); hold timer and
   TL431 chain removed; R14 2.49 k (502 µA FS). Firmware: GAIN 0x04 = 0x0100 once, DAC 0x08 = code << 4.

**How to apply:** don't redo the sims or the routing experiments; don't run `build_pcb.py`/`route_pcb.py` on a
hand-edited board; changes to the contract go into spec §7 in the same commit.

Related: [[laserhat-next-tasks]], [[hat-manual-routing-handoff]], [[laserhat-user-preferences]].
