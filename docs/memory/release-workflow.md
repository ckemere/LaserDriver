---
name: release-workflow
description: How test firmware reaches the user - push a v* tag; GitHub Actions (.github/workflows/pi-deploy.yml) builds debs + golden Raspberry Pi OS images with the MCU firmware baked in; the user flashes an SD card and runs sudo laserhat-flash
metadata:
  type: feedback
---

The user does **not** build firmware on the Pi by hand. Delivery is: commit, then `git tag v<ver>` (rc tags like
`v0.2.0-rc1` are normal) and `git push origin <branch> <tag>`. The workflow in `.github/workflows/pi-deploy.yml`
(brought to `pcb-rev2` from `main` on 2026-10-14) runs the Pi tests, cross-builds `laserhat_<ver>_{arm64,armhf}.deb`
(C broker `Pi/brokerd`, `oledd.c`, MCU firmware via `Firmware/Makefile.gcc`, `laserhat-flash`), publishes a GitHub
Release, and bakes golden Raspberry Pi OS Lite images (`laserhat-raspios-lite-<arch>.img.xz` + `imager.json`).
On the Pi: flash the image, then `sudo laserhat-flash` programs the MCU over SWD using
`Firmware/openocd/pi-swd.cfg` (so that file must carry the board's real pins) and `Pi/power_cycle.py`.

**Three boards since v0.3.0 (2026-11-09):** one firmware tree, `make -f Makefile.gcc BOARD=rev2|stim|laser` -> `Firmware/build_gcc/<board>/main.elf` (board_rev2.h / board_stim.h / board_laser.h); RSP_VERSION byte 2 = board type (0 unknown/old fw, 1 rev2, 2 stim, 3 laser), PROTO_VERSION still 2.  The HAT ID EEPROM (vendor KemereLab; pids 0x0002 LaserHAT Rev 2, 0x0003 StimHAT, 0x0004 LaserDriverHAT) is the board identity: program once with `sudo laserhat-eeprom write <board> --yes` with JP1 OPEN (closed = write-protected), close JP1, reboot.  Pi tools resolve board EEPROM > --board > LASERHAT_BOARD (/etc/default/laserhat) > Rev 2; pins Rev 2 NRST 23 / POWER 18 / TRIGGER 26, new boards 9 / 10 / 18, SWD 24/25; LASERHAT_*_PIN override single pins.  `laserhat-flash` picks /usr/lib/laserhat/firmware/laserhat-mcu-<board>.elf and refuses a mismatching board without --force; brokers publish board / board_source / fw_board and fw_ok goes false on a mismatch.  v0.3.0-rc1 = same software tagged on a pre-rebase commit; rc2 = rebased onto the user's 2026-11-01 production commits.  First CI build of the three-board firmware = rc1/rc2.

**CI runner images (2026-11-10):** ubuntu-latest became Ubuntu 26.04 (gcc 15, no qemu-user-static package: it is qemu-user + qemu-user-binfmt there).  The workflow registers QEMU binfmt handlers with docker/setup-qemu-action (image-independent) since v0.3.0-rc6; v0.3.0-rc5 was pinned to ubuntu-24.04 and is the known-good fallback (full release with golden images).  CI runs/jobs are readable without auth from the public API (api.github.com/repos/ckemere/LaserDriver/actions/runs); job logs need a GH_TOKEN (Actions: read).  The remote is an SSH alias (github-laserhat), so derive the API path as ckemere/LaserDriver directly.

**Pin maps are per production board (lesson 2026-11-10):** the firmware's board headers must be derived from the ordered board's `sch_parts.py` U7/SW7 nets (not from an older README).  LaserDriverHAT (ordered 2026-11-01): PWM_A PA26 TIMG7_C0, PWM_B PA27 TIMG7_C1 (PF 7), ADC_A PA25 ADC0 ch 2, ADC_B PA24 ADC0 ch 3, DAC PA15, BUTTON1 PA6 / BUTTON6 PA12 / BUTTON2 PA13 / BUTTON3 PA14 — v0.3.0-rc7 (board_laser.h); rc6 and earlier laser images drove PA22/PA23 and gave no light.  StimHAT map unchanged since 2026-10-30 (board_stim.h verified against sch_parts 2026-11-10).

**Why:** user (2026-10-14): "I thought our work flow was for you to push a tag to github so I could pull the test
firmware as a raspbian image?"
**How to apply:** after any firmware/Pi change meant for testing, tag and push; keep `pi-swd.cfg`, `power_cycle.py`,
brokerd `--gpio-pin` default and `laserhat-flash` consistent with the HAT revision. Pi tests run in CI only
([[no-local-testing]]). Related: [[laserhat-next-tasks]].
