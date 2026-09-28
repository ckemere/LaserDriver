# LaserHAT Rev 2 — output-module interface spec (for the isolated e-stim module)

This file is the contract between the **LaserHAT Rev 2 base board** (Raspberry Pi HAT with an MSPM0G3507 MCU) and the plug-in **output modules**.

- **Laser-diode module:** already designed; see `../LaserDaughter/`.
- **Isolated constant-current electrical-stimulation module:** what you are designing.

If anything here is unclear or you need a change on the HAT side, ask in `QUESTIONS.md` in this folder (protocol at the bottom). The HAT designer's session watches that file.

Status: HAT Rev 2 schematic is final and the PCB is in final routing (2026-09-26). The pinout below is frozen unless we agree otherwise in `QUESTIONS.md`.

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
| Module outline (max) | **x 101.0 – 127.5, y 76.0 – 99.5** (26.5 × 23.5 mm), rectangle |
| North (y < 76) | Adafruit 128×32 OLED bonnet (covers HAT y 44–74.7). Do not extend north of y = 76. |
| East (x > 127.5) | BNC J6 (TRIG IN) starts at x ≈ 128. It is either right-angle (031-5540, ~13 mm tall, y ≈ 86–100, barrel out past the edge) or vertical (031-5539, ~14.5 mm tall, y ≈ 80–96). Do not extend east. |
| South (y > 99.5) | HAT bottom edge at y = 100. Cables may exit here. |
| West (x < 101) | HAT left edge at x = 100. It is now a straight edge; the display flex-cable slot was removed on 2026-09-27. Cables or switches may exit here. |
| Accessible edges | **West and south edges only**, but see the HAT's UI thumb-access zones below. Put the electrode connector, any switches and the compliance/range selectors there. |
| **HAT UI thumb zones (keep clear)** | Updated 2026-09-26. The HAT's UI moved to edge-operated parts at HAT level, **below** your module: a **thumbwheel on the west edge, y ≈ 80–95**, with the wheel sticking out ~6 mm past x = 100; a **BACK button on the south edge, x ≈ 107–116**, with its plunger ~1.3 mm past y = 100. Don't hang connectors, cables or switches over the HAT edge in those two spans. **Best electrode-connector spots: south edge x ≈ 117–127.5, or west edge y ≈ 95–99.5.** (The FIRE button is on the HAT's east edge, x ≈ 160–164, y ≈ 86–92, outside your outline.) |

**Stack height.** The HAT has **female 1×5 sockets** (KiCad `Connector_PinSocket_2.54mm:PinSocket_1x05_P2.54mm_Vertical`, 8.5 mm body). The module has **male 1×5 pin headers on its underside** (`Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical`, placed on B.Cu, 2.5 mm plastic). So the module's bottom surface sits **≈ 11 mm above the HAT top surface**.

**Under the module (on the HAT):**

- Thumbwheel SW7 (SHOUHAN BL-DT, 2.5 mm tall) at the west edge, x ≈ 100.7–107, y 81–93.5.
- Right-angle BACK button SW8 (C&K PTS645, ~3.5 mm tall) at the south edge, x ≈ 106.7–116.3, y 93–100.
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
| 3 | (114.08, 78.50) | **PWM_A** | PA21, TIMA0_CCP0 |
| 4 | (116.62, 78.50) | **PWM_B** | PA22, TIMA0_CCP0_CMPL (hardware complement of PWM_A, dead-band capable) |
| 5 | (119.16, 78.50) | **GPIO** | PA26, general GPIO; also TIMA0_FAULT0 input (hardware PWM kill) |

**J9 — "analog" (column, pins run +y):**

| Pin | Position (x, y) | Net | MCU pin / function |
|---|---|---|---|
| 1 | (125.50, 82.00) | **GND** | HAT ground |
| 2 | (125.50, 84.54) | **+3V3** | MCU's switched 3.3 V rail (MSPM0_3V3). Off when the Pi powers the MCU down (GPIO23). |
| 3 | (125.50, 87.08) | **DAC** | PA15, DAC0_OUT, 12-bit, 0 – 3.3 V (VDD reference), unbuffered-ish; treat as ≥ 10 kΩ load |
| 4 | (125.50, 89.62) | **ADC_A** | PA17, ADC1 ch 2, 12-bit, 0 – 3.3 V |
| 5 | (125.50, 92.16) | **ADC_B** | PA16, ADC1 ch 1, 12-bit, 0 – 3.3 V |

The L arrangement keys the module: it can only be plugged in one way. Pin 1 of each connector is the GND end.

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
| PWM_A (PA21) | Phase 1 (e.g. cathodic) enable |
| PWM_B (PA22) | Phase 2 (anodic) enable. Normally the complement of PWM_A; the firmware can instead run independent, non-overlapping phases with dead time. |
| GPIO (PA26) | Output-stage enable / electrode shorting (charge balance) switch; or, as an input, a FAULT from the module (compliance limit, over-current) that hardware-kills the PWM via TIMA0_FAULT0 |
| ADC_A (PA17) | Delivered-current monitor (sense-resistor voltage) |
| ADC_B (PA16) | Compliance-voltage monitor. The laser module uses ADC_B for its compliance rail, so the GUI already shows it. |

Existing firmware already has an "EStim mode" (paired monophasic pulses on the STIM_MIRROR BNC). PWM_A/B-driven biphasic output on the module is the natural extension.

## 6. Reference material

- `../REV2_NOTES.md`: the whole Rev 2 change list, including the MCU pin map.
- `../LaserDaughter/`: the laser module (schematic and PCB) as a worked example of the interface.
- `../tools/daughter_layout.py`, `../tools/build_daughter_pcb.sh`: how the laser module PCB is built and aligned.
- `../bnc_daughter_io.kicad_sch`: the HAT-side sheet with J8/J9.

---

## Communication protocol

Use `QUESTIONS.md` in this folder:

1. Append a question at the end as `### Q<n> — <short title>` followed by `Status: OPEN` and your question text.
2. The HAT session sees the change, relays the question to the user, and writes an answer under it (`**A:** …`), changing the status to `ANSWERED`. If it needs the user's decision, the status becomes `WAITING-ON-USER`.
3. Don't edit existing answers. Add a follow-up question instead.
