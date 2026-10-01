---
name: estim-module-status
description: "E-stim daughterboard state on 2026-09-29: rev M4 (I2C DAC60501 via ISO1640, ISO7741F with a dedicated RELEASE line, fault detector, 26.5 x 36.5 mm single-sided) placed but not routed; the decisions behind it and what was rejected"
metadata:
  type: project
---

**Where it is (commit `ba12414`, branch pcb-rev2):** schematic final (netcheck OK, ERC 0), board placed only — the
user hand-routes it (done: rev M4c, 2026-09-29/30). Fab outputs are
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
6. **Rev M4b (2026-09-29): fault detector = TLV1702 on ±V** (E1 direct, one 10k/215k/10k string, R26 + BAT54WS level shift): 5 resistors instead of 9, faster, no load on E1; unequal packs give the average margin, a missing pack holds the fault on. The layout session (user) had meanwhile re-wired U1/U9 channels and swapped J9.4/J9.5 = SDA/SCL (firmware only) and made the barrier an L; the board was synced with `pcb_sync.py --keep-tracks`.
7. **Rev M4: dedicated SHORT-release line.** I²C DAC60501Z (internal 2.5 V ref ÷ 2, 0–1.25 V, addr 0x48) through an
   ISO1640, ISO7741F for EN/CATH/RELEASE + FAULT_n; J9.3/4/5 = RELEASE/SCL/SDA (no HAT copper change); hold timer and
   TL431 chain removed; R14 2.49 k (502 µA FS). Firmware: GAIN 0x04 = 0x0100 once, DAC 0x08 = code << 4.

7. **Layout session 2026-09-29 (uncommitted):** J9.4 = SDA, J9.5 = SCL (swap; HAT firmware only; `laserhat-87` was
   unreachable — open question 1 in LAYOUT_HANDOFF). U1 channels A/B/C = RELEASE/EN/CATH (B/C swapped 2026-09-29 evening), U9 channels swapped, so the
   headers feed the isolators straight; FAULT_H (J8.5 → U1.6) still needs one via (PA6 is the MCU's only TIMA0 fault
   pin). Barrier is now an L: y 83.58 to x 120, x 120 down to y 95.5, then east; HAT domain = y < 82.58 plus
   x > 121, y < 94.5. Zones on all four layers follow it; rule areas `ISOLATION_BARRIER_0/1/2`.
8. **M4c (2026-09-29, uncommitted):** 74HC4053 + the −5 V zener rail (R6, D1, C8) → one **ADG1436YCPZ** (LFCSP-16 4×4,
   LCSC C655227, $7.22, 1451 in stock; user's choice over cost). Built first with two ADG1219 (SOT-23-8) then replaced. Truth
   table: INx low = SxB. Switch 2 = phase (IN2 = CATH: S2B = VSET_P, S2A = VSET_N), switch 1 = gate (IN1 = EN: S1B = 0 V,
   S1A = SW_P → V_IN; swapped for the layout); EN pin and exposed pad (= VSS) netted. Footprint QFN-16-1EP_4x4mm_P0.65mm_EP2.5x2.5mm, rot −90 in the
   west column at x 104.05 with C14 above / C13 below; NC pads 5/7/13/14 carry the unconnected-(U6-NC-PadN) nets. Outline is now y 76–109. −V rail load (~1.5 mA) is below the Mornsun A0515S 10 % minimum: use the RECOM RB-0515D/HP
   or batteries. U8 comparator halves swapped (B = TH_P side). Rejected: TMUX7219/6219 WSON-8 (LCSC stock 4 / 0), TS5A22364
   (5 V part), DG636E (±8 V max, would keep the −5 V rail; 32 in stock), ADG6436 ($17.67, 13 in stock).

**How to apply:** don't redo the sims or the routing experiments (the autorouting scripts were deleted 2026-10-01); never rebuild a
hand-edited board; changes to the contract go into spec §7 in the same commit.

Related: [[laserhat-next-tasks]], [[hat-manual-routing-handoff]], [[laserhat-user-preferences]].
9. **Stable UUIDs (2026-09-29):** `sch_engine.U()` is uuid5-based (symbols hash their reference), regeneration is byte-identical,
   and all 48 footprints carry `(path "/<symbol uuid>")` (root-sheet form, verified against an F8 save), so F8 no longer swaps every part. C4/C20 dropped, C2 shared
   by U1.16/U9.5; ADG1436 channels: sw 1 = EN gate, sw 2 = CATH phase.
10. **2-layer, fully routed (2026-09-29 evening, uncommitted):** inner planes removed, GND pours on F+B, power/logic routed with
   `tools/fixroute.py` (scratch scripts relayout*.py; SWIG quirk: collect-then-remove and one board write per process). C10/C11/C12
   moved onto U4/U5/U7 pins, C13/C14 are +V/−V taps at (106.7, 97.4)/(103.6, 97.08) — no room within 2 mm of U6 without moving
   R10. V_IN on B.Cu, not under U5 on top. 0 unconnected, 0 electrical DRC errors; ~75 vias, bottom pour fragmented by the
   diagonal power runs (user may tidy). Outline stayed y 76–109.
11. **Connector standard change (2026-09-29 evening, user decision): J8.3 = FAULT_n (PA6), J8.5 = EN (PA7).** HAT copper and the
   laser module must follow — **done 2026-09-30** (HAT sheet + copper, laser module sheet + copper, LAYOUT_HANDOFF Q1/Q2 answered).
   U1 pins unchanged (6/5/4/3 = FAULT/CATH/EN/RELEASE). Hardware I2C1 cannot use PA17/PA22 (only bit-bang); the re-map that would
   allow it (J9.4 → PA16, J9.5 → PA17, BUTTON3 → PA22) is written up in REV2_NOTES, not applied.
12. C13/C14 both kept for now (2026-09-29 late, after going back and forth): ±V taps on the west feed, 45 SMT parts. Candidates to drop later; C17 too.
13. **Back to 4 layers (2026-09-29 late):** the user gave up on 2 layers. In1 = split GND planes (zones `PLANE_GND_H/ISO`), In2 =
   power, routed by the user; my router's power/I2C/EN/CATH/FAULT_H runs were all ripped earlier at the user's request.
14. U6 EN (pin 12) → +V_STIM instead of +5V_ISO (2026-09-29 late): datasheet allows inputs to VDD, IDD ~1 nA. Power widths: In2/B 0.5,
   F 0.4 mm (three −V segments 0.3). Labels moved back on board. User routed power on In2 (traces, not pours).
