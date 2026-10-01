# LaserHAT Rev 2 — output-module interface spec (for the isolated e-stim module)

This file is the contract between the **LaserHAT Rev 2 base board** (Raspberry Pi HAT with an MSPM0G3507 MCU) and the plug-in **output modules**.

- **Laser-diode module:** already designed; see `../LaserDaughter/`.
- **Isolated constant-current electrical-stimulation module:** what you are designing.

Questions and changes are coordinated between the HAT session and the module session directly (§8). The former `QUESTIONS.md` log (Q1–Q4, NOTICES 1–13, 2026-09-26 to 29) was retired on 2026-09-29; everything still binding from it is in §7.

Status: the HAT Rev 2 board is hand-routed and committed (2026-09-28). The pad positions below are frozen; the e-stim meaning of J9.3–5 is per §7 (rev M4).

---

## 1. Coordinate frame

All coordinates are in **mm, KiCad board coordinates of the HAT**: x to the right, y **down**.

- The HAT board spans x 100.0–165.0, y 43.12–100.0 (Raspberry Pi HAT template frame).
- The Pi 40-pin header runs along the top edge (y ≈ 44.6–50.4).
- Pi mounting holes are at (103.5, 47.5), (161.5, 47.5), (103.5, 96.5), (161.5, 96.5).

**Design your module PCB in this same coordinate frame** (a top view, looking down at the HAT). Then the header pads can be placed at the absolute positions below and alignment is guaranteed. `../LaserDaughter/LaserDaughter.kicad_pcb` does exactly this, and `../tools/daughter_layout.py` shows how.

## 2. Module outline and neighbours

| Item | Value |
|---|---|
| Module outline (max) | **x 101.0 – 127.5, y 76.0 – 112.5** (26.5 × 36.5 mm), rectangle. Changed 2026-09-28 (NOTICE 12): the module may extend **12.5 mm south past the HAT's edge (y = 100)**, over the Pi's port edge. The original 26.5 × 23.5 mm outline (y 76.0 – 99.5) is still valid for modules that don't need the room (the laser module keeps it). |
| North (y < 76) | Adafruit 128×32 OLED bonnet (covers HAT y 44–74.7). Do not extend north of y = 76. |
| East (x > 127.5) | BNC J6 (TRIG IN) starts at x ≈ 128. It is either right-angle (031-5540, ~13 mm tall, y ≈ 86–100, barrel out past the edge) or vertical (031-5539, ~14.5 mm tall, y ≈ 80–96). Do not extend east. |
| South (y > 99.5) | HAT bottom edge at y = 100; the module may overhang it to y = 112.5. Below the overhang, ≈ 24 mm under the module's surface, are the plugs of the Pi's USB-C power (x ≈ 103–112) and micro-HDMI0 (x ≈ 122–131) cables (overmoulds ≤ 9 mm above the Pi). Nothing may hang below the HAT plane there. Cables may exit south. |
| West (x < 101) | HAT left edge at x = 100. It is now a straight edge; the display flex-cable slot was removed on 2026-09-27. Cables or switches may exit here. |
| Accessible edges | **West and south edges only** (the south edge is now 12.5 mm beyond the HAT and clear of the BACK-button thumb zone), but see the HAT's UI thumb-access zones below. Put the electrode connector, any switches and the compliance/range selectors there. |
| **HAT UI thumb zones (keep clear)** | Updated 2026-09-26. The HAT's UI moved to edge-operated parts at HAT level, **below** your module: a **thumbwheel on the west edge, y ≈ 80–95**, with the wheel sticking out ~6 mm past x = 100; a **BACK button on the south edge, x ≈ 109–114** (SMD side-actuated EVQP7A since 2026-09-30), with its button ~0.4 mm past y = 100. Don't hang connectors, cables or switches over the HAT edge in those two spans. **Best electrode-connector spots: south edge x ≈ 117–127.5, or west edge y ≈ 95–99.5.** (The FIRE button is on the HAT's east edge, x ≈ 160–164, y ≈ 86–92, outside your outline.) |

**Stack height.** The HAT has **female 1×5 sockets** (KiCad `Connector_PinSocket_2.54mm:PinSocket_1x05_P2.54mm_Vertical`, 8.5 mm body). The module has **male 1×5 pin headers on its underside** (`Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical`, placed on B.Cu, 2.5 mm plastic). So the module's bottom surface sits **≈ 11 mm above the HAT top surface**.

**Under the module (on the HAT):**

- Thumbwheel SW7 (SHOUHAN BL-DT, 2.5 mm tall) at the west edge, x ≈ 100.7–107, y 81–93.5.
- Side-actuated SMD BACK button SW8 (Panasonic EVQP7A01P, 3.6 × 3.5 mm, ~2.5 mm tall) at the south edge, x ≈ 108.8–114.3, y 96.5–100 (was a C&K PTS645 right-angle THT until 2026-09-30).
- The two sockets.
- M2.5 mounting hole MH3 at (103.5, 96.5) with its screw head.
- Everything else under the module on the HAT is low SMD. Module underside components up to ~6 mm tall are fine, except over the sockets.
- Optional: a Ø2.7 mm hole in the module at (103.5, 96.5) would let an M2.5 standoff stack secure the module to MH3. The laser module does not do this yet.

## 3. Connectors (exact pad positions)

Pitch 2.54 mm, round THT pads.

**J8 — "power / timing" (row, pins run +x):**

| Pin | Position (x, y) | Net | MCU pin / function |
|---|---|---|---|
| 1 | (109.00, 78.50) | **GND** | HAT ground (= Pi ground, = USB ground) |
| 2 | (111.54, 78.50) | **+5V** | Pi 5 V rail (Pi supply or HAT USB-C through an ideal diode) |
| 3 | (114.08, 78.50) | **GPIO / FAULT** | PA6, general GPIO; also TIMA0_FAULT0 input (hardware PWM kill, latched, forces PWM_A and PWM_B low). **Pins 3 and 5 swapped on 2026-09-29 (evening)**; the HAT copper follows. |
| 4 | (116.62, 78.50) | **PWM_B** | PA12, TIMA0_CCP3 (an independent channel on the same timer as PWM_A; the laser module's firmware runs it as the complement of PWM_A, e-stim mode drives it independently) |
| 5 | (119.16, 78.50) | **PWM_A** | PA7, TIMA0_CCP1 (was pin 3 until 2026-09-29) |

**J9 — "analog" (column, pins run +y):**

| Pin | Position (x, y) | Net | MCU pin / function |
|---|---|---|---|
| 1 | (125.50, 82.00) | **GND** | HAT ground |
| 2 | (125.50, 84.54) | **+3V3** | MCU's switched 3.3 V rail (MSPM0_3V3). Off when the Pi powers the MCU down (GPIO23). |
| 3 | (125.50, 87.08) | **DAC** | PA15, DAC0_OUT, 12-bit, 0 – 3.3 V (VDD reference), unbuffered-ish; treat as ≥ 10 kΩ load |
| 4 | (125.50, 89.62) | **ADC_A** | PA17, ADC1 ch 2, 12-bit, 0 – 3.3 V |
| 5 | (125.50, 92.16) | **ADC_B** | PA22, ADC1 ch 8, 12-bit, 0 – 3.3 V |

The L arrangement keys the module: it can only be plugged in one way. Pin 1 of each connector is the GND end.

MCU pin numbers were last changed on 2026-09-28 (HAT routing); the pad positions are unchanged since the spec was frozen. `../REV2_NOTES.md` has the full MCU pin map.

## 4. Electrical budget and levels

| Rail / signal | Limit / level |
|---|---|
| +5V (J8.2) | Shared with the Pi. Budget **≤ 500 mA** for the module (the laser module draws ~0.4 A peak). Ask if you need more. |
| +3V3 (J9.2) | From a 250 mA LDO shared with the MCU, USB-UART and LEDs. Budget **≤ 50 mA**. Intended for the *non-isolated* side of digital isolators and similar logic. |
| Logic levels | 3.3 V CMOS, **not 5 V tolerant** (PWM_A/B, GPIO). |
| ADC inputs | 0 – 3.3 V. Keep the source impedance ≤ ~10 kΩ or buffer; add RC as needed. |
| Isolation | **All isolation must be on the module.** HAT GND is the Pi/USB ground. Put a digital isolator on PWM_A/PWM_B/GPIO, an isolated DC-DC from +5V, and isolated (or ratiometric/transformer-coupled) feedback for ADC_A/B if they measure the isolated side. |

## 5. Suggested channel use for a biphasic constant-current stimulator

This is a suggestion; the firmware is flexible, so tell us what you need.

| Channel | Suggested e-stim use |
|---|---|
| DAC (PA15) | Stimulus current amplitude setpoint (to a V-to-I / Howland stage, via the isolation barrier if needed) |
| PWM_A (PA7) | Phase 1 (e.g. cathodic) enable |
| PWM_B (PA12) | Phase 2 (anodic) enable. Normally the complement of PWM_A; the firmware can instead run independent, non-overlapping phases with dead time. |
| GPIO (PA6) | Output-stage enable / electrode shorting (charge balance) switch; or, as an input, a FAULT from the module (compliance limit, over-current) that hardware-kills the PWM via TIMA0_FAULT0 |
| ADC_A (PA17) | Delivered-current monitor (sense-resistor voltage) |
| ADC_B (PA22) | Compliance-voltage monitor. The laser module uses ADC_B for its compliance rail, so the GUI already shows it. |

What the e-stim module actually does with these lines (rev M4, §7): DAC = RELEASE (SHORT-switch control), ADC_A / ADC_B = SCL / SDA of a bit-banged I²C bus to an isolated DAC (M1–M3 used SPI CS_n / SCK / MOSI on the three), PWM_A = EN, PWM_B = CATH, and GPIO = FAULT_n from the module's LM393 compliance window.

Existing firmware already has an "EStim mode" (paired monophasic pulses on the STIM_MIRROR BNC). PWM_A/B-driven biphasic output on the module is the natural extension.

## 6. Reference material

- `../REV2_NOTES.md`: the whole Rev 2 change list, including the MCU pin map.
- `../LaserDaughter/`: the laser module (schematic and PCB) as a worked example of the interface.
- `../tools/daughter_layout.py`, `../tools/build_daughter_pcb.sh`: how the laser module PCB is built and aligned.
- `../bnc_daughter_io.kicad_sch`: the HAT-side sheet with J8/J9.

---

## 7. Agreed contract with the e-stim module (rev M4, 2026-09-29)

Everything below was negotiated between the two sessions in 2026-09-26 … 29 and is the binding state. The HAT's copper is unchanged by it. The J8.3/J8.5 FAULT/EN swap (2026-09-29 evening, user decision; HAT copper change, laser module re-route) and the J9.4/J9.5 SDA/SCL swap (2026-09-29, module layout session, user decision) were made while the HAT session was unreachable and are listed in `../EStimDaughter/LAYOUT_HANDOFF.md`; both were acknowledged and applied on the HAT side on 2026-09-30 (J8: HAT and laser-module copper re-routed; J9: firmware only, PA17 = SDA, PA22 = SCL).

| Line | HAT pin | Module meaning | Notes |
|---|---|---|---|
| J8.5 PWM_A | PA7 = TIMA0_CCP1 | **EN** — current flows while high | independent channel; edge precision ~0.1 µs. **On J8.5 since 2026-09-29 evening (was J8.3)** |
| J8.4 PWM_B | PA12 = TIMA0_CCP3 | **CATH** — 1 = cathodic, 0 = anodic | changes only while EN is low; leads EN by ≥ 1 µs |
| J8.3 GPIO | PA6 = TIMA0_FAULT0, active low, **latched**, forces CCP1 and CCP3 low | **FAULT_n** (**on J8.3 since 2026-09-29 evening, was J8.5**; HAT and laser-module copper re-routed to match on 2026-09-30) — low = compliance / open-electrode fault, isolated side unpowered, or (M4b) one battery pack missing | at start-up low means "module not ready": wait for high (≤ ~100 ms) before arming; clear only between trains; report faults to the Pi; keep the input glitch filter ≤ 1 µs (pulses at the window edge can be ~1 µs) |
| J9.3 "DAC" | PA15, push-pull GPIO | **RELEASE** — high = electrode SHORT switch open | high ≥ 1 µs before the first EN of a pair; low ~200 µs after the pair for ≥ 200 µs (electrode reset, also re-centres the output amplifier — do it at least every ~0.3 s during a train); also drop it in the fault handler |
| J9.4 "ADC_A" | PA17, open-drain GPIO | **SDA** | bit-banged I²C ≤ 400 kHz, between trains only; pull-ups on the module. **SDA/SCL swapped on 2026-09-29** (module layout; HAT firmware only, no HAT copper). Before that: J9.4 = SCL, J9.5 = SDA |
| J9.5 "ADC_B" | PA22, open-drain GPIO | **SCL** | " |
| J9.2 +3V3 | MSPM0_3V3 (off when the Pi powers the MCU down) | isolator input side | while the MCU pins are Hi-Z the module's pulls give EN = CATH = RELEASE = low: zero current, electrode shorted |

DAC (DAC60501Z, I²C address 0x48, frame 0x90 · command · MSB · LSB): after the isolated side is up (FAULT_n high + 250 µs) write GAIN register 0x04 = 0x0100 once (REF-DIV = 1, BUFF-GAIN = 0 → 0–1.25 V full scale; the power-on default is ×2 gain = 4× the intended current), then DAC register 0x08 = code << 4. I = code / 4096 × 1.25 V / 2.49 kΩ (0.123 µA/LSB, 502 µA full scale). The DAC powers up at zero code; its ACK doubles as "isolated side alive". Pulse pair: RELEASE high → CATH high → EN high t_pw → EN low, CATH low in the gap → EN high t_pw → EN low → RELEASE low ~200 µs later.

Module outline: x 101.0–127.5, y 76.0–112.5 (26.5 × 36.5 mm, 12.5 mm past the HAT's south edge over the Pi's port edge; the HAT's User.Drawings layer carries both the laser module outline (y 76–99.5) and the e-stim board's actual outline (y 76–109, M4c) since 2026-09-30; the `DAUGHTERBOARD` F.Cu keep-out under the module is unchanged). Everything else (BNCs, laser module, MCU pin map) is as in §1–6.

## 8. Coordination

There are usually two Claude Code sessions: one owning the HAT (`LaserHAT/`, session name `laserhat-87` on the Ubuntu machine as of 2026-09-29) and one owning the module layout. They coordinate by:

1. **Direct messages** between sessions (Claude Code's session messaging; both must be running with Remote Control enabled) for quick questions.
2. **Git** for anything that must survive: decisions go into this spec (§7), `EStimDaughter/DESIGN_NOTES.md` and `EStimDaughter/LAYOUT_HANDOFF.md`; a session that changes the contract edits §7 in the same commit.
3. **`LaserHAT/claude_memory/`** for session context (install per its README).

Don't edit the other session's board file (`LaserDriver.kicad_pcb` is the HAT's, `EStimDaughter/EStimDaughter.kicad_pcb` the module's); ask.
