# Glance out — hardware

Raspberry Pi HATs for optogenetic laser and electrical stimulation in neuroscience experiments, plus their supplies.
KiCad 9 projects; schematics generated from Python, boards finished by hand.  Working rules and tool list:
`CLAUDE.md`.

| Board | Directory | What | Status |
|---|---|---|---|
| **StimHAT** | `StimHAT/` | HAT core + isolated constant-current stimulator (4-layer, 65 × 57 mm) | production files 2026-11-01 (`fab/orders/2026-11-01_StimHAT_rev3_production.zip`) |
| **LaserDriverHAT** | `LaserDriverHAT/` | HAT core + laser-diode driver (4-layer, 65 × 57 mm) | production files 2026-11-01; v0.3.0 firmware verified on hardware |
| **DCDCPod** | `DCDCPod/` | isolated ±15 V supply pod that plugs into the StimHAT | production files 2026-11-01 |
| **SimpleBatteryPack** | `SimpleBatteryPack/` | two 4S hobby packs in series → ±V for the stimulator, ON/OFF | production files in `SimpleBatteryPack/production/` |

Each board's README has its circuit, MCU pin map (HATs), checks and assembly notes.  Shared parts:

- `Footprints.pretty/`, `Footprints.3dshapes/`, `LaserHAT.kicad_sym` — shared footprints / 3D models / owl symbol art
- `tools/` — board-agnostic helpers (`pcb_sync.py`, `sync_check.py`, `path_check.py`, `netcheck.py`, `fill_zones.py`,
  `track_tidy.py`, `maze_route.py`, ...)
- `ref/LaserHAT_Rev2_ref.kicad_pcb` — footprints and outline of the archived Rev 2 HAT, read by some generators
- `estim_interface/ESTIM_MODULE_SPEC.md` — the stimulator contract (§7: firmware sequencing and pins)
- `fab/` — JLC outputs per board and `fab/orders/` (the archives actually ordered)

Firmware: `../firmware/` (`make -f Makefile.gcc BOARD=stim|laser|rev2`).  Pi software: `../pi/`.  History: `../docs/history/`.  The Rev 2
HAT, the LaserDaughter / EStimDaughter modules and the relay BatteryPack are archived at tag `archive/pre-glance-cleanup`.

---

## Big Picture

The central challenge in optogenetics and fiber-photometry experiments is
getting clean, fast, digitally-controlled laser pulses synchronized to
behavior or electrophysiology acquisition. USB-connected laser drivers
introduce latency and jitter through the OS scheduler; GPIO-connected drivers
are faster but require dedicated single-board computers or FPGAs.

These boards solve the problem with a two-layer approach:

1. **A remote experiment machine** (Python / Bonsai / Open Ephys, …) runs
   the high-level logic and decides when a pulse should start. It sends a
   UDP trigger datagram to the Pi.
2. **The Raspberry Pi** runs the broker (`../pi/brokerd/`), whose real-time
   trigger thread turns each datagram into a single GPIO edge as fast as
   possible and ACKs it. The Pi also hosts the OLED and web GUIs for
   setting parameters.
3. **The MSPM0 MCU** on the HAT (MSPM0G1507; MSPM0G3507 on the archived Rev 2)
   responds to that edge in hardware, generates the waveform with
   sub-microsecond jitter, and drives the laser driver or the stimulator directly.

The remote machine handles "what and when."
The Pi gets the trigger from the network to the HAT with minimal, measured latency.
The MCU handles "how precisely" at the microsecond timescale.
