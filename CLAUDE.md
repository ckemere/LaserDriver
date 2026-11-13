# Glance out — working guide for agents

This repository is the **output side of Glance**: two Raspberry Pi HATs that deliver stimulation (laser or electrical),
their two power boards, the MCU firmware and the Pi software and OS images.  Read this file first; it tells you where
everything lives and which rules apply where.  `README.md` is the human overview with pictures; `docs/REPO_MAP.md`
is the directory-by-directory index.

## The four boards

| Board | Directory | Role | Status |
|---|---|---|---|
| **StimHAT** | `hardware/StimHAT/` | HAT core (MSPM0G1507 MCU, USB-C, HAT ID EEPROM, BNC trigger in / sync out, joystick, OLED) + galvanically isolated constant-current stimulator (±13.5 V rails, 502 µA full scale) | rev 3 ordered 2026-11-01; stimulator bench-tested 2026-11-12 |
| **LaserDriverHAT** | `hardware/LaserDriverHAT/` | the same HAT core + the laser-diode driver block (12 V boost, current servo, photodiode monitor) | rev 3 ordered 2026-11-01; laser verified 2026-11-11 |
| **DCDCPod** | `hardware/DCDCPod/` | isolated ±15 V supply pod (RECOM RB-0515D/HP + LC filters + capacitance multipliers) that plugs into the StimHAT | rev 3 ordered 2026-11-01 |
| **SimpleBatteryPack** | `hardware/SimpleBatteryPack/` | two 4S packs in series → ±V for the stimulator, with ON/OFF | rev 3 ordered 2026-11-01 |

Earlier generations (the Rev 2 LaserHAT with plug-in laser / e-stim modules, the relay BatteryPack) are archived at
tag `archive/pre-glance-cleanup`; `docs/history/REV2_NOTES.md` keeps their story and the Rev 2 pin map, which the
firmware still builds (`BOARD=rev2`).

## Where the rules are

- **Hardware** (`hardware/`): `hardware/CLAUDE.md` — generated schematics (`sch_parts.py` is the source of truth for
  parts, LCSC codes and pin→net), hand-finished boards, never rebuild a board, the F8-safety checks, pcbnew gotchas.
  Each project README has its MCU pin map, layout history and pre-order audit record.  **The production boards were
  hand-edited after generation: when a pin map matters, read it from the board (`.kicad_pcb` pad nets) or the
  project's `sch_parts.py`, which is kept in step with it — not from an older README.**
- **Firmware** (`firmware/`): `firmware/CLAUDE.md` — one source tree, three boards (`BOARD=rev2|stim|laser`,
  `board_<board>.h` pin maps), hand-written register code, the wire protocol in `protocol.h` mirrored by
  `pi/protocol.py` (`firmware/host_tools/proto_crosscheck.py` must pass), `TESTING.md` for bring-up.
- **Pi software** (`pi/`): `pi/README.md` (architecture: broker, OLED daemon, web GUI, triggers) and
  `pi/PROVISIONING.md` (images, services, the HAT ID EEPROM, flashing).  Debian package `laserhat`; the identifiers
  (`laserhat-*` commands and services, `/usr/lib/laserhat`, `LASERHAT_*` variables, EEPROM vendor "KemereLab") keep
  their historical names on purpose — a rename is a separate, deliberate change.
- **Session memory** (`docs/memory/`): the project's Claude Code memory notes (`MEMORY.md` index, one fact per file:
  user preferences, decisions, open items).  Install them as the user's auto-memory per `docs/memory/README.md`, and
  keep them updated when you learn something durable.

## How the pieces identify each other

- The **HAT ID EEPROM** (U1 on both HATs) is the board identity: vendor `KemereLab`, products `StimHAT` 0x0003 and
  `LaserDriverHAT` 0x0004 (`LaserHAT Rev 2` 0x0002).  `laserhat-eeprom write <board> --yes` programs it once with
  JP1 **open** (closed = write-protected); the Pi reads it at boot into `/proc/device-tree/hat/`.
- The **firmware** reports its board type in `RSP_VERSION` (byte 2: 1 rev2, 2 stim, 3 laser; 0 = firmware older
  than v0.3.0).  The brokers publish `board` (EEPROM) and `fw_board` (MCU) and set `fw_ok` false when they differ.
- **Pi GPIOs** per board (BCM): Rev 2 NRST 23 / power 18 / trigger 26; StimHAT and LaserDriverHAT NRST 9 / power 10 /
  trigger 18; SWD 24/25 on all.  `pi/hat_id.py` resolves board and pins: EEPROM, then `--board`, then
  `LASERHAT_BOARD` (environment or `/etc/default/laserhat`), then Rev 2; `LASERHAT_*_PIN` overrides single pins.
- **Displays**: the Adafruit SSD1305 bonnet or a 0.91" SSD1306 module on J10; `laserhat-oledd` detects which at start
  (bonnet reset on GPIO 4) and `LASERHAT_OLED_PANEL` overrides.

## Build, test, release

- Nothing is built or tested on the user's own machine: **GitHub CI** (`.github/workflows/pi-deploy.yml`) runs the
  Pi tests, the protocol cross-check, cross-builds the three firmware images and the `laserhat` debs (arm64, armhf),
  and on a `v*` tag publishes a release with golden Raspberry Pi OS images.  Delivery = commit, tag `vX.Y.Z[-rcN]`,
  push the tag; the user flashes the image and runs `sudo laserhat-flash` (picks the firmware for the EEPROM's board).
  Put a tag on its own commit: two tags on one commit make `git describe` pick either for the version string.
- Run state is readable without credentials from `https://api.github.com/repos/<org>/<repo>/actions/runs`; job logs
  need a token with Actions read.
- Hardware checks run locally with KiCad 9's Python (`pcbnew`) and `kicad-cli`: each project's `tools/drc_summary.py`,
  `tools/netcheck.py` (schematic vs `sch_parts.py`), `hardware/tools/path_check.py` / `sync_check.py` (read-only F8).
  DRC must be 0 errors / 0 unconnected before a fab claim; `tools/make_fab.py` regenerates `hardware/fab/<board>/`.

## Conventions

- Commit messages end with the attribution trailers given in the session; never push to `main` directly or force-push;
  the user merges.  The user also edits boards and generators by hand and pushes: pull / rebase before committing and
  compare the regenerated netlist with the pushed schematic rather than overwriting hand edits.
- Prose over numbers in reports; name a file only when the reader has to go there.
- Open items and decisions live in `docs/memory/` (durable) and in each README's audit sections (per board).
