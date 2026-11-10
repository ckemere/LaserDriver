# LaserDriver DONE

Status of the 2026-06-04 firmware/SW audit items. The concrete fixes
(High priority, Medium / near-term, and Refactor) are **complete** and
merged; the open design questions at the bottom remain **deferred** and
should be scoped on their own.

Commits live on the `audit-fixes` branch (merged to `main`). Build was
confirmed clean after every firmware change (`make -C
Firmware`, output `build/main.out`), and the changes
were bench-tested on hardware.

## High priority — DONE

- [x] **B1 / A1 — Per-pulse trigger attribution.** (`225a4cb`)
  Replaced the shared `g_pulse_via_uart` flag plus the separate
  `g_pulse_start_evt` / `g_pulse_end_evt` (+ tick) flags with two
  `PulseEvent {tick, via_uart, pending}` records, each stamping its own
  via_uart bit at the instant the event is generated. This kills the
  dropped-ACK race where a concurrent BNC/Pi-GPIO trigger starting the
  next pulse could stomp `g_pulse_via_uart` and suppress a UART pulse's
  start/end ACK pair. `g_pulse_via_uart` is retained but is now ISR-only.
  Assumption (minimal-change): kept separate start/end slots rather than
  a single kind-tagged slot + queue — start and end are >150 ms apart
  while main drains at 1 kHz, so neither slot can be overrun.

- [x] **B2 — `trigger()` honest failure.** (`218255d`)
  `LaserHat.trigger()` now treats an empty / timed-out reply as failure
  (`bool(reply) and not reply.startswith("ERR")`), matching `get_state()`.

- [x] **B4 — PA14 (BNC) pulldown.** (`23d0cf2`)
  Added `IOMUX_PINCM_PIPD_ENABLE` to the BNC trigger input so a
  released/unterminated line idles LOW. Active-high, matching PA19.

- [x] **C5 — Rewrite Firmware CLAUDE.md.** (`35b6b39`)
  Fixed the four inaccuracies: the "no state-machine logic inside ISRs"
  claim, the nonexistent `get_next_state`/`set_output`, the wrong ack
  helper name (now `laser_timerg_tick_ack()`), and the "9600 baud
  placeholder echo" (now 115200 8N1 with a real line parser).

## Medium / near-term — DONE

- [x] **B3 — Overflow guard in `parse_decimal`.** (`5a3f947`)
  Reject before `v*10 + digit` can wrap past `UINT32_MAX`, so an
  over-long value can't alias a small in-range one. Callers still
  range-check the result.

- [x] **S1 — Drop the needless IRQ guards.** (`5a3f947`)
  Removed `__disable_irq()`/`__enable_irq()` around the single-field
  config writes (each is one aligned store, atomic on M0+; the latch is
  the consistency point). Updated the comments to state the real invariant.

- [x] **S2 — Delete dead code.** (`3aa2d25`)
  Removed `laser_gpio_read_button1()` and its declaration.

- [x] **S4 — Hot-path change-guard in `set_output_from_state()`.** (`5a3f947`)
  Added a `static` RAM shadow of the last-applied `{mux, duty, mirror}`;
  skips the IOMUX/duty writes when unchanged so a steady HOLD_HIGH no
  longer re-muxes the bridge every 10 µs. Never reads the IOMUX back, so
  the locked-GPIO-vs-PWM safety property and idempotent-set design hold.

- [x] **C1–C4 — Comment fixes.**
  - C1: eink `_image_to_buffer` comment rewritten to explain why no
    inversion is needed. (`864a86f`)
  - C2: stale "echo placeholder" reference removed; real FEN rationale
    kept. (`864a86f`)
  - C3: stale "(wired in a later commit)" parenthetical removed. (`225a4cb`)
  - C4: double-negative invariant comment reworded positively. (`225a4cb`)

- [x] **A2 (part 1) — Pointer comment for the PA19 duality / g-arming dance.**
  (`864a86f`) Added one-line pointers from the PA19 SWDIO↔GPIO / arming
  code sites to the canonical prose in board.h / README.
  (Part 2 — the single-UART-owner rule — folds into item 12, below.)

## Refactor — DONE

- [x] **R1 — Rename source files by function, drop the `laser_` prefix.**
  (`bfe62d5`) History-preserving `git mv` of all 8 modules, plus the
  matching `#include` / header-guard / Makefile (object list + artifact
  names) / doc updates.

  | Old | New |
  |---|---|
  | `laser_driver.c` | `main.c` |
  | `laser_timera.{c,h}` | `pwm_timer.{c,h}` |
  | `laser_timerg.{c,h}` | `tick_timers.{c,h}` |
  | `laser_pwm_control.{c,h}` | `output_mux.{c,h}` |
  | `laser_dac.{c,h}` | `dac.{c,h}` |
  | `laser_uart.{c,h}` | `uart.{c,h}` |
  | `laser_gpio.{c,h}` | `gpio.{c,h}` |
  | `laser_sysctl.{c,h}` | `sysctl.{c,h}` |

  Out of scope (unchanged): the `laser_` prefix on function *symbols*
  (e.g. `laser_timerg_tick_ack()`) and the `LASER_*` state-machine enum
  values. Revisit separately if desired.

## Three-board Pi software (2026-11-09) — DONE on the Pi side, CI to confirm

The Pi stack now serves the LaserHAT Rev 2, the StimHAT and the
LaserDriverHAT (branch `worktree-stim-hat`, not committed at the time of
writing).

- [x] **Board identity from the HAT ID EEPROM.** `Pi/hat_id.py` reads
  `/proc/device-tree/hat` (vendor `KemereLab`; product ids 0x0002 / 0x0003 /
  0x0004) and resolves board + Pi GPIOs: EEPROM, else `--board`, else
  `LASERHAT_BOARD`, else Rev 2; `LASERHAT_*_PIN` override single pins.
  `brokerd/hatid.c` is the C mirror.  `laserhat-eeprom read | make | write`
  builds the HAT EEPROM image itself (header, vendor atom, minimal GPIO map,
  CRC-16) and programs U1 over a temporary i2c-gpio bus on GPIO 0/1.
- [x] **Board-aware pins.** `power_cycle.py`, `laserhat-flash` (OpenOCD
  `adapter gpio` overrides after `pi-swd.cfg`), `pi_trigger.py`, `broker.py`
  and `laserhat-brokerd` (`--gpio-pin` default) use the board's pins and say
  which board they resolved.
- [x] **Firmware per board.** The package carries
  `laserhat-mcu-{rev2,stim,laser}.elf` (+ `laserhat-mcu.elf` → Rev 2);
  `laserhat-flash` picks the EEPROM's and refuses a contradicting `--board`
  without `--force`.  Both brokers publish `board` / `board_source` /
  `fw_board` (RSP_VERSION's board byte) and fail `fw_ok` on a mismatch; the
  web page and OLED show the board (and hide the mode switch on the
  single-mode boards); the StimHAT's 6th button (bit 6) is accepted.
- [ ] Not yet run in CI or on hardware: the deb build of the three images,
  the EEPROM write on a real board, the flash on a StimHAT.

## Open design questions — STILL OPEN (scope separately)

These were intentionally **not** addressed in the audit-fixes pass.

- [ ] **11 — Comms layer redesign.**
  Bundles three converging concerns:
  - **B3 (broader)** — is TEXT the right transmission form, or should we
    move to a binary protocol (binary framing + optional text fallback for
    interactive debugging)?
  - **B5** — the firmware emits unsolicited `OK pulse start/end` lines
    (button/BNC/GPIO events) that desync the Pi's one-reply-per-command
    model; a pulse line arriving between `write()` and `readline()` is
    mistaken for the command reply (intermittent phantom "no response",
    esp. with the eink GUI polling at 20 Hz next to button use). Framing
    solves this; otherwise a read-until-matching-prefix loop in
    `_send_line`. `laser_hat.py:87-95`.
  - **A2 (part 2) — UART ownership.** Today eink-GUI and web both want
    exclusive `/dev/ttyS0`, guarded only by a systemd `Conflicts=`;
    nothing in code enforces it. Consider a single broker daemon that owns
    the port and exposes a local socket to both clients.

- [ ] **12 — Re-evaluate the arming mechanism.**
  Do we still need the one-way `g` arming at all? `web_app` re-sends `g`
  (a blocking UART round-trip) before every GPIO trigger
  (`web_app.py:127`), adding ms-class jitter. If we keep arming: add a GUI
  arm/disarm control that also reflects the current state. (Separately:
  GitHub issue to reflect arm state via an LED — owned by Caleb.)
