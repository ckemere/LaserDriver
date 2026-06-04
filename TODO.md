# LaserDriver TODO

Derived from the 2026-06-04 firmware/SW audit. Items are grouped by priority;
the open design questions at the bottom should be scoped on their own and must
not block the concrete fixes above them.

## High priority

- [ ] **B1 / A1 — Per-pulse trigger attribution.**
  Replace the shared `g_pulse_via_uart` flag plus `g_pulse_start_evt` /
  `g_pulse_end_evt` with a single atomic event record `{kind, tick, via_uart}`
  written by the ISR and drained by main. A concurrent BNC/Pi-GPIO trigger can
  currently stomp `g_pulse_via_uart` and silently suppress a UART pulse's
  start/end ACK pair, so the `t` client times out. Folding the via-uart bit into
  the per-event record kills the race and localizes the ordering contract (this
  is also the A1 architecture cleanup).
  Files: `laser_driver.c:130, 205-207, 531-540`.

- [ ] **B2 — `trigger()` honest failure.**
  `LaserHat.trigger()` returns `True` when `reply == ""` (readline timeout), so a
  powered-off/wedged MCU makes the web "TRIGGER (UART)" button report success.
  Treat empty/`None` reply as failure, matching `get_state()`.
  Files: `laser_hat.py:139`.

- [ ] **B4 — PA14 (BNC) pulldown.**
  Add `IOMUX_PINCM_PIPD_ENABLE` to the BNC trigger input so a released/unterminated
  line can't look like a rising edge and fire the laser. Active-high, matching the
  Pi-trigger input PA19.
  Files: `laser_gpio.c:77-78` (cf. `laser_gpio.c:108-110`).

- [ ] **C5 — Rewrite Firmware CLAUDE.md.**
  The first doc a contributor reads describes a prior architecture. Fix: it claims
  "no state-machine logic inside ISRs" (the whole SM runs in `TIMG0_IRQHandler`);
  references nonexistent `get_next_state`/`set_output`; names the ack helper wrong
  (it's `laser_timerg_tick_ack()`); and calls the UART "9600 baud placeholder echo"
  when it's 115200 with a full parser.
  Files: `Firmware/laserHatFirmware/CLAUDE.md`.

## Medium / near-term

- [ ] **B3 — Overflow guard in `parse_decimal`.**
  `v = v*10 + digit` has no overflow guard, so e.g. `i 4294967297` wraps to 1,
  passes the 1..320 range check, and silently sets a wrong setpoint. Reject when
  the value exceeds the field max (or `UINT32_MAX/10`). Cheap and independent of
  the protocol redesign (item 11) — do it regardless.
  Files: `laser_driver.c:362-378`.

- [ ] **S1 — Drop the needless IRQ guards.**
  Remove `__disable_irq()`/`__enable_irq()` around the single-field config writes;
  each is one aligned store (atomic on Cortex-M0+) and the latch is the consistency
  point. Replace the misleading "prevents a torn copy" comment with a note that the
  aligned store is atomic.
  Files: `laser_driver.c:444-447, 455-458, 466-469`.

- [ ] **S2 — Delete dead code.**
  Remove `laser_gpio_read_button1()` (and its declaration); `poll_buttons()` uses
  `laser_gpio_read_buttons_raw()` exclusively.
  Files: `laser_gpio.h:38-41`.

- [ ] **S4 — Hot-path change-guard in `set_output_from_state()`.**
  Stop re-muxing the IOMUX (two registers + duty) every 10 µs during HOLD_HIGH when
  nothing changed. Compare the desired output config against a `static` RAM shadow of
  what was last applied (do NOT read the IOMUX back) and skip the writes when
  unchanged. Preserves the locked-GPIO-vs-PWM safety property and the idempotent-set
  design.
  Files: `laser_driver.c:288-291`.

- [ ] **C1–C4 — Comment fixes.**
  - C1: `eink_panel._image_to_buffer` comment claims an SSD1680 inversion the code
    never performs; rewrite to explain why no inversion is needed (PIL "1" packing and
    SSD1680 BW RAM agree, 1 = white). `eink_panel.py:192-195`.
  - C2: remove the stale "echo placeholder" reference in `laser_uart.c`; keep the real
    FEN/one-byte-interrupt rationale. `laser_uart.c:111-113`.
  - C3: the architecture header's "(wired in a later commit)" parenthetical is stale —
    `GROUP1_IRQHandler` and `laser_gpio_arm_pi_trigger()` are present now.
    `laser_driver.c:26-28`.
  - C4: reword the double-negative invariant comment positively (read flag first, then
    the matching tick is guaranteed valid). `laser_driver.c:526-527`.

- [ ] **A2 (part 1) — Pointer comment for the PA19 duality / g-arming dance.**
  Add a one-line pointer comment at the PA19 SWDIO↔GPIO / arming code sites to the
  canonical prose explanation (board.h / README). (Part 2 — the single-UART-owner
  rule — folds into item 12.)

## Refactor

- [ ] **R1 — Rename source files by function, drop the `laser_` prefix.**
  Use history-preserving `git mv`; then update `#include` directives, header guards
  (`LASER_TIMERA_H` → `PWM_TIMER_H`, etc.), the Makefile object list, and doc
  references in CLAUDE.md / README.

  | Current | New |
  |---|---|
  | `laser_driver.c` | `main.c` |
  | `laser_timera.{c,h}` | `pwm_timer.{c,h}` |
  | `laser_timerg.{c,h}` | `tick_timers.{c,h}` |
  | `laser_pwm_control.{c,h}` | `output_mux.{c,h}` |
  | `laser_dac.{c,h}` | `dac.{c,h}` |
  | `laser_uart.{c,h}` | `uart.{c,h}` |
  | `laser_gpio.{c,h}` | `gpio.{c,h}` |
  | `laser_sysctl.{c,h}` | `sysctl.{c,h}` |

  Out of scope for now: renaming the `laser_` prefix on function *symbols*
  (e.g. `laser_timerg_tick_ack()`). Revisit separately if desired.

## Open design questions (scope separately — do not block the above)

- [ ] **11 — Comms layer redesign.**
  Bundles three converging concerns:
  - **B3 (broader)** — is TEXT the right transmission form, or should we move to a
    binary protocol? A binary framing with an optional text fallback for interactive
    debugging is a common pattern.
  - **B5** — the firmware emits unsolicited `OK pulse start/end` lines (button/BNC/GPIO
    events) that desync the Pi's one-reply-per-command model; a pulse line arriving
    between `write()` and `readline()` is mistaken for the command reply, causing
    intermittent phantom "no response" (esp. with the eink GUI polling at 20 Hz next to
    button use). Framing solves this; otherwise a read-until-matching-prefix loop in
    `_send_line`. `laser_hat.py:87-95`.
  - **A2 (part 2) — UART ownership.** Today eink-GUI and web both want exclusive
    `/dev/ttyS0`, guarded only by a systemd `Conflicts=`; nothing in code enforces it.
    Consider a single broker daemon that owns the port and exposes a local socket to
    both clients — removes the "pick one" constraint, serializes access, and is the
    natural home for framing + filtering the async pulse lines.

- [ ] **12 — Re-evaluate the arming mechanism.**
  Do we still need the one-way `g` arming at all? `web_app` re-sends `g` (a blocking
  UART round-trip) before every GPIO trigger (`web_app.py:127`), adding ms-class
  jitter — though the web path is not the low-latency path (network/BNC triggers are).
  If we keep arming: add a GUI arm/disarm control that also reflects the current state.
  (Separately: GitHub issue to reflect arm state via an LED — owned by Caleb.)
