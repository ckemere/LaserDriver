# Repository map (glance-out)

| Path | What | Entry points |
|---|---|---|
| `hardware/` | KiCad 9 projects (rules: `hardware/CLAUDE.md`, overview: `hardware/README.md`) | per board below |
| `hardware/StimHAT/`, `hardware/LaserDriverHAT/` | the two HATs: shared MSPM0 core + stimulator / laser driver | `gen_schematic.py` (+ `sch_parts.py` = parts, LCSC codes, pin→net), `tools/drc_summary.py`, `tools/netcheck.py`, `tools/make_footprints.py`, `tools/stamp_fields.py`, `tools/make_bom.py`, `tools/make_fab.py`; README "MCU pin map" |
| `hardware/DCDCPod/` | isolated ±15 V pod for the StimHAT | same, plus `tools/check_isolation.py` |
| `hardware/SimpleBatteryPack/` | ±V battery board (two 4S packs) | same generator layout; `production/` = Fabrication Toolkit output |
| `hardware/tools/` | board-agnostic helpers | `pcb_sync.py` (headless F8), `sync_check.py` / `path_check.py` (read-only F8 checks), `fill_zones.py`, `track_tidy.py`, `gnd_islands.py`, `maze_io.py` + `maze_route.py`, `netcheck.py`, `overlaps.py`, `make_bnc_fp.py`; `lcsc_parts.py` / `lcsc_catalog.json` = Rev 2 part data |
| `hardware/Footprints.pretty`, `Footprints.3dshapes`, `LaserHAT.kicad_sym` | shared footprints, models, owl symbol | referenced as `${KIPRJMOD}/../Footprints.pretty` |
| `hardware/ref/` | `LaserHAT_Rev2_ref.kicad_pcb`: archived Rev 2 HAT's footprints + outline, read by some generators | — |
| `hardware/estim_interface/` | `ESTIM_MODULE_SPEC.md`: stimulator contract (§7 firmware/pins) | — |
| `hardware/fab/` | JLC outputs per board, `fab/orders/` = archives actually ordered (2026-11-01) | `<board>/tools/make_fab.py` |
| `firmware/` | MSPM0 firmware, one source tree for three boards | `make -f Makefile.gcc BOARD=stim\|laser\|rev2` (`make flash` on a Pi); `protocol.h` (wire protocol, mirror of `pi/protocol.py`); `host_tools/proto_crosscheck.py`; `openocd/pi-swd.cfg`; `CLAUDE.md`, `README.md`, `TESTING.md` |
| `pi/` | Raspberry Pi software, Debian package `laserhat` | `brokerd/` (C broker: UART, GPIO trigger, UDP triggers), `oledd.c` + `oled_gui.py`, `web_app.py`, `laserhat-flash` (SWD flash), `laserhat-eeprom` (HAT ID EEPROM read/make/write), `laserhat-power`, `systemd/laserhat-*`, `packaging/build-deb.sh`, `packaging/inject-laserhat.sh`, `tests/`; `README.md`, `PROVISIONING.md` |
| `.github/workflows/pi-deploy.yml` | CI: oledd render test, Pi test suite, protocol cross-check, debs (arm64/armhf); a `v*` tag (or dispatch with `release_tag`) builds the release + golden Pi OS images | ignores `hardware/**`, `docs/**` |
| `docs/images/` | board renders (kicad-cli, 2026-11-13) | — |
| `docs/memory/` | Claude Code session memory (`MEMORY.md` index; install per `README.md`) | — |
| `docs/history/REV2_NOTES.md` | Rev 2 design history + appendix "Rev 2 MCU pin map" (`firmware/board_rev2.h`) | — |
| `docs/DONE.md` | 2026-06 firmware/software audit, item status | — |
| `docs/datasheets/` | laser diode datasheets | — |
| `requirements.txt` | `kiutils` for the hardware scripts | — |

Software identifiers keep their LaserHAT names on purpose (package `laserhat`, `laserhat-*` commands and services,
`/usr/lib/laserhat`, `LASERHAT_*` variables, EEPROM vendor "KemereLab"): v0.3.0 was verified on hardware with them; a
rename would be a separate, deliberate change.

**Archived** (deleted from this branch, kept at tag `archive/pre-glance-cleanup`, all under `LaserHAT/`): the Rev 2 HAT
(`LaserDriver.kicad_pro/.kicad_sch/.kicad_pcb`, sheets `mspm0_controller`, `usb_uart`, `bnc_daughter_io`, its
`fp-lib-table` / `sym-lib-table`), `LaserDaughter/` (laser module), `EStimDaughter/` (e-stim module), `BatteryPack/`
(rev D relay pack), `fab/LaserHAT`, `fab/LaserDaughter`, `fab/EStimDaughter`, `fab/BatteryPack`, the 2026-10-01 order
archives, and `tools/jlc_fab.py`, `tools/stamp_lcsc.py`, `tools/silk_declutter.py`, `tools/lcsc_verify.py`.
`git show archive/pre-glance-cleanup:LaserHAT/<path>` or `git checkout archive/pre-glance-cleanup -- LaserHAT/<path>`.
