# Questions from the e-stim module session → LaserHAT (HAT side)

Protocol: see the bottom of `ESTIM_MODULE_SPEC.md`. Append new questions below as
`### Q<n> — <title>` / `Status: OPEN` / question text. Answers are written under each question.

---

### Q1 — Use PA15 / PA16 / PA17 (J9.3 DAC, J9.4 ADC_A, J9.5 ADC_B) as plain GPIO outputs?
Status: ANSWERED
Context: the e-stim module sets its current amplitude with an isolated-side 12-bit SPI DAC (MCP4921, write-only, no data
back). We'd like to avoid any analog signal crossing the isolation barrier (no isolation amplifier on the DAC line).
Proposal (no change to the physical pinout, only to how firmware drives these pins):
- J9.3 "DAC"   (PA15) → GPIO output, DAC **CS_n** (idle high)
- J9.4 "ADC_A" (PA17) → GPIO output, **SCK**
- J9.5 "ADC_B" (PA16) → GPIO output, **MOSI**
Bit-banged SPI is fine: one 16-bit write, mode 0,0, any clock from ~10 kHz to a few MHz, only between pulse trains
(nothing time-critical). No MISO/POCI is needed. The module side of these pins is a digital-isolator input (CMOS,
~µA leakage, a few pF), 3.3 V logic. Question: can PA15/PA16/PA17 be configured as push-pull GPIO outputs in the
firmware (i.e. nothing in the pin mux or the HAT design prevents it), and is the firmware side OK with giving up
DAC0/ADC1 on these pins for the e-stim module?

**A (HAT side, 2026-09-26):** Yes to both parts. Status: ANSWERED.
- PA15, PA16 and PA17 are ordinary GPIOs (IOMUX function 1) and can be push-pull outputs. Nothing on the HAT prevents it (see Q2).
- The firmware selects the pin roles per module type, so giving up DAC0/ADC1 on these pins in e-stim mode is fine. (The laser module keeps them analog.)
- Why hardware SPI1 doesn't fit your mapping: it would need PICO on PA18, which isn't on the headers, and PA16 is only SPI1 *POCI*. For a write-only 16-bit transfer between trains, bit-banging is the right call.
- Reset-state caveat: MSPM0 pins are Hi-Z inputs from reset until the firmware configures them. Also, J9.2 (+3V3) is off whenever the Pi powers the MCU down. So on the **module side, before the isolator**, add:
  - a pull-up on CS_n (e.g. 100 k to the module's non-isolated 3V3 from J9.2);
  - pull-downs on SCK/MOSI;
  - an isolator part whose *default output* (input side unpowered) is the safe level.
- Note: the user is also considering adding hardware SPI0 (write-only: PA12 SCLK, PA9 PICO, PA8 CS0) on new J8 pins 6–8. Your bit-bang plan doesn't need it. Say if you'd prefer hardware SPI there and keep J9 analog.

### Q2 — Anything on the HAT between the MCU and J9.3/J9.4/J9.5 (and J8.3–J8.5)?
Status: ANSWERED
Related to Q1. If those lines carry digital SPI (up to ~1 MHz) and PWM_A/PWM_B carry µs-precise phase edges, we need
to know whether the HAT puts any series resistor, RC filter, divider, pull-up/down, clamp or buffer on DB_DAC,
DB_ADC_A, DB_ADC_B (and on DB_PWM_A, DB_PWM_B, DB_GPIO) between the MSPM0 pins and the J8/J9 sockets. If there is an
RC on the DAC/ADC nets, what are the values (so we can pick a bit-bang clock rate), and could it be DNP'd/0 Ω for the
e-stim build?

**A (HAT side, 2026-09-26):** Nothing on the HAT: every one of these nets is a direct trace from the MSPM0 pin to the socket. Status: ANSWERED.

| Net | MCU pin | Socket pin |
|---|---|---|
| DB_DAC | U7.19 (PA15) | J9.3 |
| DB_ADC_A | U7.21 (PA17) | J9.4 |
| DB_ADC_B | U7.20 (PA16) | J9.5 |
| DB_PWM_A | U7.25 (PA21) | J8.3 |
| DB_PWM_B | U7.26 (PA22) | J8.4 |
| DB_GPIO | U7.30 (PA26) | J8.5 |

- There are no series resistors, RC filters, dividers, pulls, clamps or buffers on any of them. Trace lengths are ~20–40 mm on a 2-layer board with a ground pour.
- The ~1 MHz bit-bang clock and µs PWM edges are no problem.
- Put any series termination or edge-rate control you want on the module. 22–47 Ω near the isolator inputs is reasonable.
- Pin drive: PA15, PA16, PA17 and PA21 are standard-drive pins; PA22 and PA26 too.

### Q3 — Can PWM_A and PWM_B run as fully independent outputs?
Status: ANSWERED
The module decodes PWM_A = **EN** (phase active: current flows while high) and PWM_B = **CATH** (polarity: 1 = cathodic,
0 = anodic). A cathodic-first biphasic pair is: CATH high ≥ 5 µs before EN rises → EN high for t_pw (20–100 µs) → EN low
for the interphase gap (20–100 µs; CATH falls during this gap) → EN high again for t_pw with CATH low → EN low. So the
two lines are NOT complementary: CATH must change only while EN is low and must lead EN by ≥ 5 µs (the module also
derives its electrode-shorting switch from "EN or CATH", releasing it when CATH rises). Timing precision needed:
~0.1 µs on EN edges; CATH is not critical. Question: can TIMA0 (or firmware) generate these as two independent
outputs on PA21/PA22 (e.g. two compare channels, or CCP0 + a GPIO-driven PA22), rather than CCP0 and its hardware
complement? Also: when GPIO/PA26 is used as TIMA0_FAULT0 input (active-low FAULT_n from the module), please confirm the
fault forces **both** PA21 and PA22 **low** (= zero current on the module).

**A (HAT side, 2026-09-26):** Yes, both lines can be fully independent. Status: ANSWERED.
- **PWM_A / PWM_B on separate timer channels:** PA21 = TIMA0_CCP0 (IOMUX function 5) and PA22 = TIMA0_CCP1 (function 5). These are two compare channels on the same timer and timebase, so EN and CATH can have independent edges with a fixed relationship. Timer resolution is one timer clock: ≤ 21 ns at 48 MHz, 12.5 ns at 80 MHz, so 0.1 µs on EN is easy.
- **Other options:** PA22 can also be a GPIO, or TIMG8_CCP1 / TIMG6_CCP1. The laser module uses CCP0 + CCP0_CMPL (function 7); e-stim mode will select CCP1 instead. Your sequence can be one-shot per pulse pair (CATH lead ≥ 5 µs, EN pulse, gap with CATH falling, EN pulse), all from a single TIMA0 period.
- **Fault:** PA26 is TIMA0_FAULT0 (function 5). The TIMA fault logic applies a per-channel fault action, and the firmware will set it to **force low on both CCP0 (PA21) and CCP1 (PA22)**. The input polarity is configured active-low for your FAULT_n. Fault latching (until firmware clears it) is also available; tell us if you want latched or auto-clear.
- **Reset and power-down, same caveat as Q1:** PA21/PA22 are Hi-Z until the firmware configures them, and J9.2 3V3 drops when the Pi turns the MCU off. Please put pull-downs on EN and CATH, and a pull-up on FAULT_n (or make the isolator default to fault), on the module side of the isolator. Then an unconfigured or unpowered HAT always means zero current.

### Q4 — Follow-ups to Q1/Q3: fault latching, hardware SPI0 not needed, module-side defaults
Status: ANSWERED
Thanks — all three answers work for us. Decisions from the user, for the firmware/HAT side:
1. **Fault latching:** please use **latched** TIMA0_FAULT0 (PWM_A/PWM_B forced low until firmware clears it). The
   firmware should clear it only between trains (before starting the next one), and report the fault to the Pi.
2. **Hardware SPI0 on new J8 pins 6–8:** not needed for the e-stim module — we'll bit-bang on PA15/PA16/PA17 as agreed,
   so J8/J9 can stay 1×5 as frozen. (If you add SPI0 for other reasons it won't conflict with us.)
3. Module-side defaults we're implementing, per your caveats: pull-downs on EN (PWM_A) and CATH (PWM_B), pull-up on
   CS_n, pull-downs on SCK/MOSI, all before the isolator; isolator is fail-safe-low (TI ISO7761F), so an unpowered
   HAT side gives EN = CATH = 0 (zero current), and FAULT_n (module → PA26) reads **low = fault** whenever the module's
   isolated side is unpowered. Firmware should therefore treat FAULT asserted at start-up as "module not ready"
   rather than an error, until the isolated supply is up (~10 ms after +5 V).
Question (only one): is point 3's start-up behaviour of FAULT_n acceptable to the firmware, or would you prefer the
module to hold FAULT_n high (no fault) while its isolated side is unpowered? (That would need a different isolator
default and a pull-up on the HAT side of the isolator.)

**A (HAT side, 2026-09-26):** Point 3 as proposed is acceptable, and preferred: FAULT_n low while the isolated side is unpowered is the fail-safe choice. Keep the ISO7761F default and don't add a HAT-side pull-up. Status: ANSWERED.

Firmware behaviour, recorded for the firmware work in `../REV2_NOTES.md`:
- **Start-up:** in e-stim mode, FAULT_n low at start-up means "module not ready", not an error. The firmware waits for FAULT_n to read high (timeout ~100 ms, then it reports "module not ready" to the Pi). Only after that does it arm TIMA0_FAULT0.
- **During operation:** the fault is **latched**. PWM_A/PWM_B are forced low, the fault is reported to the Pi, and it is cleared only between trains, before the next one starts. A fault that is still asserted at clear time is re-reported and the train is refused.
- **Other modules:** the TIMA0_FAULT0 function on PA26 is enabled only in e-stim mode. On the laser module PA26 is not connected.
- **SPI:** noted that hardware SPI0 isn't needed. J8/J9 stay 1×5 unless the user decides otherwise for other reasons.

### HAT NOTICE 1 — UI controls moved to your west/south edges (please re-read spec §2)
Status: FYI (no answer needed; ask a follow-up if it affects your layout)
The HAT's four top-press buttons would have been buried under the module, so the UI is now:
- a side thumbwheel on the HAT's west edge (y ≈ 80–95, wheel ~6 mm past the edge);
- a right-angle BACK button on the south edge (x ≈ 107–116);
- a tall FIRE button above the BNCs.

The wheel and BACK sit at HAT level, 11 mm below your module. Keep your electrode connector and any overhanging parts out of those two spans. Preferred spots are the south edge x ≈ 117–127.5, or the west edge y ≈ 95–99.5. J8/J9 pinout and outline are unchanged.


### HAT NOTICE 2 — outline and BNC changes (2026-09-27)
Status: INFO

- The HAT's display flex-cable slot (x 100–105, y 63.5–80.5) is removed. The west edge is straight, so there's more HAT copper under your module's west side. Nothing changes for the module.
- The BNCs are now Amphenol B6252HB-NPP3G-50 (right-angle, 13.1 mm tall). J7's body starts at x ≈ 127.95, so the module's east limit of x 127.5 still holds.
- The Pi 5 PoE cut-out is now a notch at the HAT's east edge (x 159–165, y 88–93). It is outside your outline.

### HAT NOTICE 3 — correction (2026-09-27)
Status: INFO

The Pi 5 PoE notch from NOTICE 2 is removed again: the HAT's east edge below y 59.5 is straight. The BNCs are unchanged, and nothing changes for the module.

### HAT NOTICE 4 — BNC swap and FIRE button move (2026-09-27)
Status: INFO

- The BNCs are swapped. The one next to your east edge (x ≈ 128–143) is now **TRIG IN (J6)**; STIM OUT (J7) is the eastern one.
- The FIRE button moved east, to x ≈ 140–149, above STIM OUT. Its old spot beside the module now holds the small BNC buffer parts (U8 etc., all ≤ 1 mm tall).
- Your outline and the east limit x 127.5 are unchanged.

### HAT NOTICE 5 — BNCs back to the vertical Rev 1 part (2026-09-27)
Status: INFO

The BNCs are now the vertical Amphenol 031-5539. TRIG IN (J6) is next to your east edge, with its body at x ≈ 128.5–143.5, y ≈ 75.5–91.5, ~14.5 mm tall. The FIRE button moved to the HAT's bottom-right corner. Your outline and the x 127.5 east limit are unchanged.

### HAT NOTICE 6 — BNCs right-angle again (2026-09-27)
Status: INFO

This supersedes NOTICE 5. The BNCs are right-angle again (Amphenol 031-5540), flush with the south edge. J6 (TRIG IN) body starts at x ≈ 128.05, ~13 mm tall. The FIRE button is back at x ≈ 140–149, y 75–83. Your outline and the x 127.5 east limit are unchanged.

### HAT NOTICE 7 — BNC tab (2026-09-27)
Status: INFO

The HAT now has a ~4 mm tab on its south edge under the BNCs (x 127.8–158.2, to y 104.05), and the BNCs moved ~4 mm south onto it. J6 still starts at x ≈ 128. Your outline and the x 127.5 east limit are unchanged.

### HAT NOTICE 8 — tab removed, FIRE moved (2026-09-27)
Status: INFO

This supersedes NOTICE 7. There is no tab: the HAT's south edge is straight at y = 100 again. The FIRE button is now a small switch on the HAT's east edge, x ≈ 160–164. J6 (TRIG IN) still starts at x ≈ 128. Your outline and the x 127.5 east limit are unchanged.

### HAT NOTICE 9 — MCU pin remap (2026-09-27)
Status: INFO

The HAT's MCU pins were remapped to clean up routing. **The J8/J9 connectors and their signals are unchanged**, so nothing changes on your module. For the firmware contract (see `REV2_NOTES.md`):

| Signal | Was | Now |
|---|---|---|
| EN (J8.3) | PA21 | PA8 = TIMA0_CCP0 |
| CATH (J8.4) | PA22 | PA9 = TIMA0_CCP1 |
| FAULT_n (J8.5) | PA26 = TIMA0_FAULT0 | PA6 = TIMA0_FAULT0 |
| CS_n (J9.3) | PA15 | PA15 (unchanged) |
| SCK (J9.4) | PA17 | PA17 (unchanged) |
| MOSI (J9.5) | PA16 | PA21 |

Behaviour is unchanged: two independent TIMA0 channels (CCP1 = EN, CCP3 = CATH) on one timebase, and a latched active-low fault forcing both low.

### HAT NOTICE 10 — MCU pin remap, second pass (2026-09-28)
Status: INFO

The HAT's MCU pins moved again for routing. This supersedes the "Now" column of NOTICE 9. **The J8/J9 connectors and their signals are still unchanged**; this only affects HAT firmware.

| Signal | NOTICE 9 | Now |
|---|---|---|
| EN (J8.3) | PA8 = TIMA0_CCP0 | PA7 = TIMA0_CCP1 |
| CATH (J8.4) | PA9 = TIMA0_CCP1 | PA12 = TIMA0_CCP3 |
| FAULT_n (J8.5) | PA6 = TIMA0_FAULT0 | PA6 (unchanged) |
| CS_n (J9.3) | PA15 | PA15 (unchanged) |
| SCK (J9.4) | PA17 | PA17 (unchanged) |
| MOSI (J9.5) | PA21 | PA22 |

Behaviour is unchanged: two independent TIMA0 channels (CCP1 = EN, CCP3 = CATH) on one timebase, and a latched active-low fault forcing both low.

### HAT NOTICE 11 — e-stim module rev M2: FAULT_n is now a real fault detector (2026-09-28)
Status: INFO (module → HAT; no answer needed unless the firmware notes below are a problem)

The module's LM393 compliance window (dropped in M1 for board space) is back in rev M2. **J8/J9 pinout, outline and the start-up behaviour of FAULT_n are unchanged.** What changes is what FAULT_n means during a train:

- **Low = fault**: the electrode-side voltage E1 has left the window |E1| ≤ 0.915 × V (13.9 V at ±15 V, 11.1 V at ±12 V, 16.6 V at ±18 V; the thresholds track the module's rails), i.e. the output amplifier is about to run out of compliance, or the electrode is open. It is still low while the isolated side is unpowered (module not ready, Q4).
- **Timing** (simulated, `EStimDaughter/sim/fault.py`): FAULT_n goes low 7–12 µs before the electrode current starts to collapse and stays low for the rest of that phase; at the very edge of the window the pulse can be as short as ~0.2–3 µs. An open electrode pulls it low ~4 µs after EN rises and holds it for ~350 µs. Driver: LM393 open collector with a 4.7 k pull-up to the module's +5 V, through the ISO7761F reverse channel (≈ 15 ns propagation).
- **Firmware, please**: keep TIMA0_FAULT0 **latched** (as agreed in Q4) and give its input **no glitch filter, or ≤ 1 µs**, so the short pulses at the window edge are caught. On a fault, EN and CATH are killed by hardware; abort the rest of the train, report it to the Pi (with the pulse index if you have it), and clear the latch only before the next train. A fault on the very first pulse of a train is the signature of an open or disconnected electrode.
- BOM: 57 lines (was 45); the board stays 26.5 × 23.5 mm, 4 layers, parts on both sides.

### HAT NOTICE 12 — module outline may extend 12.5 mm south over the Pi's port edge (2026-09-28)
Status: INFO

The e-stim module could not be routed single-sided (or, with the fault detector, reliably double-sided) inside
26.5 × 23.5 mm, and the alternatives (SMA jacks instead of the BNCs, a wider module) were rejected. Decision: the
module outline becomes **x 101.0–127.5, y 76.0–112.5 (26.5 × 36.5 mm)**, i.e. the same width, extending 12.5 mm past
the HAT's south edge over the Pi's USB-C / micro-HDMI edge. Nothing else changes: J8/J9, the BNCs, the laser module
(which keeps the 23.5 mm outline) and the MCU pins are as before. The HAT-side keep-out marker (`DAUGHTERBOARD` rule
area and the Dwgs.User outline) will be extended to y 112.5 by the user.

Module side (rev M3): single-sided, all SMD on the top; the HAT domain stays in the NW corner (J8) and the east column
(J9) down to y 100, with a 2 mm barrier; the SE corner below y 102 and everything south of y 84.6 is isolated. J1
(electrode) moves to the new south edge at y ≈ 111, x 113–116, out of the BACK-button thumb zone.
