# LaserHAT Rev 2 bring-up checklist

Steps 0–9 are for the Rev 2 HAT **with no module plugged into J8/J9**; steps
10–11 add the laser and e-stim modules.  Everything below is validated
off-hardware (`Pi/tests/`, `host_tools/proto_crosscheck.py`); this list is the
on-board confirmation.  Work top-down — a failure then tells you which layer
broke.

What the firmware does: five edge buttons → `EVT_BUTTON`, FIRE fires a
pulse; D7 boot-blinks (~2 s), heartbeats at 1 Hz when idle, is solid during a
pulse and blinks at 5 Hz while a module fault is latched; the pulse envelope
is mirrored on STIM OUT (J7 + D9); TRIG IN (J6) and Pi GPIO 26 fire a pulse;
the binary protocol runs on both UARTs (Pi GPIO 14/15 and the USB-C CH340N).
LASER mode drives J8 with TIMA0 PWM and J9.3 with the DAC0 current setpoint
and reads J9.4/J9.5 back; ESTIM mode sequences EN/CATH/RELEASE per spec §7
and programs the module's DAC over I²C.

Protocol summary (frame = `SYNC(DE AD) | TYPE | payload`, no CRC):
`CMD_CONFIG{i,r,h}` / `CMD_TRIGGER` / `CMD_QUERY` / `CMD_SET_MODE` /
`CMD_ESTIM_CONFIG` / `CMD_LASER_CURRENT` / `CMD_ESTIM_CURRENT` /
`CMD_CLEAR_FAULT` → every command is answered with `RSP_STATUS`; async
`EVT_PULSE_START/END`, `EVT_BUTTON`, `EVT_FAULT`.

---

## 0. Power and USB (nothing flashed yet)
- [ ] USB-C (J5) alone: D5 (5 V) lights.  On the Pi: `lsusb` shows the CH340
      and `/dev/ttyUSB0` appears (or on a laptop: the CH340 COM port).
- [ ] On the Pi: `pinctrl set 18 op dh` → MSPM0_3V3 is 3.3 V at J9.2 (U5 on);
      `pinctrl set 18 op dl` → 0 V.  (GPIO 18 = MCU_POWER_EN in Rev 2.)

## 1. Build
```bash
make -C Firmware -f Makefile.gcc clean all
```
- [ ] Builds to `build_gcc/main.elf` with no errors and no `-Wall -Wextra` warnings.

## 2. Flash (Rev 2 is the default; `HAT_REV=1` for the old board)
```bash
sudo systemctl stop laserhat-broker.service     # frees GPIO 26 and the UART
make -C Firmware -f Makefile.gcc flash          # +OPENOCD_GPIOCHIP=4 on Pi 5
```
- [ ] ~2 s D7 boot blink right after the command (= flash landed), then a
      short D7 blip once a second (heartbeat).
- [ ] If OpenOCD cannot connect: check SWCLK = GPIO 24, SWDIO = GPIO 25,
      NRST = GPIO 23 (swapped vs Rev 1) and that nothing else holds them.

## 3. Raw link over the Pi UART (broker stopped)
```bash
cd Firmware
python3 host_tools/smoke_test.py                # /dev/ttyS0 = Pi GPIO 14/15 = MCU UART1
```
- [ ] `query` prints a `State(...)`.
- [ ] After `config`, the echo `State` matches `i=100 r=2000 h=500`.
- [ ] `trigger` reports `EVT_PULSE_START / EVT_PULSE_END`; D7 goes solid and
      D9 (STIM) lights for the pulse.

## 4. Same link over USB-C (no Pi needed)
```bash
python3 host_tools/smoke_test.py /dev/ttyUSB0   # or COMx on a laptop
```
- [ ] Same results as step 3.  Both ports are live at the same time; events
      (`EVT_*`) go to both, a command's `RSP_STATUS` returns on its own port.

## 5. Buttons
```bash
python3 ../Pi/laser_hat.py watch
```
- [ ] SW8 BACK (south edge) → `EVT_BUTTON` with bit 0 set (mask 0x01).
- [ ] SW7 wheel push → bit 1 (0x02); wheel roll one way → bit 2 (0x04),
      the other way → bit 3 (0x08).  Note which direction is which: the OLED
      GUI maps B3 = −, B4 = + (swap in `Pi/oled_gui.py` if it feels wrong).
- [ ] SW9 FIRE (east edge) → bit 4 (0x10) **and** a pulse (D7 solid, D9).
- [ ] SW6 BSL → bit 5 (0x20) while held (no other effect while running).
- [ ] Mask returns to 0 on release; no chatter (debounce is 10 ms).

## 6. Pulse shape on J8 (scope)
```bash
python3 ../Pi/laser_hat.py config 320 200000 200000
python3 ../Pi/laser_hat.py trigger
```
- [ ] J8.5 (PWM_A, PA7): 100 kHz PWM whose duty ramps up over 2 s, holds 2 s,
      then returns LOW.  J8.4 (PWM_B, PA12): the complement, HIGH when idle.
- [ ] J7 STIM OUT: HIGH for the whole 4 s envelope (buffered by U8).

## 7. Hardware triggers
- [ ] TTL rising edge into J6 TRIG IN → pulse (`EVT_PULSE_START` appears).
- [ ] `python3 ../Pi/pi_trigger.py fire` (GPIO 26 → PA27) → pulse.

## 8. Broker + GUIs
```bash
sudo systemctl restart laserhat-broker.service
journalctl -u laserhat-broker.service -f        # "serving …", no "UART read error"
```
- [ ] `sudo fuser -v /dev/ttyS0` shows only the broker.
- [ ] OLED bonnet shows live state (the MCU shares the Pi's I2C bus on
      PA0/PA1 and must not disturb it — `i2cdetect -y 1` still shows 0x3C).
- [ ] Wheel push cycles the row, wheel roll changes the value, BACK returns to
      the first row, FIRE pulses; the web page mirrors all of it.
- [ ] Web TRIGGER (UART) and TRIGGER (GPIO) both pulse.

## 9. Reset and power paths from the Pi
- [ ] `make -C Firmware -f Makefile.gcc reset` → boot blink again (NRST = GPIO 23).
- [ ] `python3 Pi/power_cycle.py` → MCU off (D7 dark) then boot blink.
- [ ] Optional: run `sudo laserhat-flash` a second time with the firmware
      already running.  If it still flashes, SWD attaches fine outside the
      boot blink and the blink can be shortened further (`BOOT_BLINK_FLASHES`
      in `main.c`).

## 10. Laser module (MCU powered down while plugging it in; laser diode last)
With the broker stopped, HAT powered, **no diode in J2 yet** (the dummy
load takes the current):
- [ ] J9.3 (DB_DAC) reads ≈ 0.98 V with the default `current` (DAC code
      1216 ≈ 100 mA): `python3 Pi/laser_hat.py query` shows `laser_dac=1216`;
      `python3 Pi/laser_hat.py current 2432` doubles the voltage (≈ 1.96 V);
      `current 4000` is refused (echo keeps the old code; max 3650 ≈ 300 mA).
- [ ] `adc_comp` tracks the module's LASER_V: ≈ 1540 at 5 V, ≈ 3700 at 12 V
      (SW5); the web page shows it as "compliance … V".  `adc_pd` moves when
      light hits the photodiode.
- [ ] Trigger with a scope on Rs1 (2 Ω sense): the current follows the PWM
      duty ramp and reaches ≈ `laser_dac × 0.082 mA` at full intensity,
      i.e. ≈ 100 mA at the default.  `python3 Pi/laser_hat.py config 320 200000 200000`
      makes the ramp/hold 2 s each for easy viewing.
- [ ] Then the diode: start with `current 600` (≈ 50 mA), raise in steps;
      the OLED `ld:` row and the web "current" row show mA.
- [ ] FAULT_n is open on this module → `module` flags stay 0, D7 never
      blinks at 5 Hz.

## 11. E-stim module (no electrodes connected; load = 10 kΩ across the output)
- [ ] Plug the module in with the HAT unpowered, power the HAT, start the
      broker: `module` shows `FAULT_n low` (0x01) until the isolated side is
      powered (packs / converter), then 0x00.
- [ ] Switch to e-stim: web "ESTIM" button or `laser_hat.py mode estim`.
      Within ~100 ms `module` shows `ESTIM_READY` (0x04): the DAC60501 ACKed
      its GAIN init over the bit-banged I²C on J9.4/J9.5.  If instead
      `I2C_ERROR` (0x08) appears, check the module's pull-ups and the J9.4 =
      SDA / J9.5 = SCL assignment (swapped 2026-09-29; `module.c` follows the
      spec).
- [ ] `estim-current 820` (≈ 100 µA): the status echoes `estim_dac=820`, the
      OLED `sd:` row loses its `!`, and the module output shows ≈ 1 V across
      10 kΩ during a pulse.
- [ ] Scope J8.5 (EN), J8.4 (CATH), J9.3 (RELEASE) and trigger: RELEASE and
      CATH rise together, EN 10 µs later for `pulse dur`; EN low and CATH low
      for `IPI`; EN again for `pulse dur`; RELEASE stays high 200 µs, then low
      for 200 µs.  Both pulses show on STIM OUT (J7 / D9).
- [ ] Fault: with a train running, pull J8.3 low (or open the output to
      trigger the module's detector): EN/CATH/RELEASE drop within a few µs,
      D7 blinks at 5 Hz, the web header shows FAULT, `EVT_FAULT` appears in
      `laser_hat.py watch`.  Triggers are refused until "clear fault" (web),
      a wheel push (OLED) or `laser_hat.py clear-fault`.
- [ ] Power the isolated side down: `FAULT_n low` returns, `ESTIM_READY`
      clears; power it back: ready again (GAIN re-written) and the amplitude
      re-programmed without a new command.

---

### If something fails
- **No boot blink after flash:** check MSPM0_3V3 (step 0), then NRST
  (GPIO 23 must idle high: R3 47 k pull-up to MSPM0_3V3, JP4 open).
- **Garbage on the UART, blink OK:** the SYSOSC frequency-correction loop
  uses R4 (100 k 0.1 %) on PA2.  To rule it out, delete the `SYSOSCFCLCTL`
  write in `sysctl.c` and rebuild (the free-running oscillator is ±2.5 %).
- **OLED dead after the MCU boots:** PA0/PA1 are being driven — they must
  stay at their IOMUX reset default (see `gpio.c`).
- **`make flash` "Error requesting gpio line":** the broker still holds a
  pin — `sudo systemctl stop laserhat-broker.service` first.
- **Spurious pulses with nothing connected:** PA27 (Pi trigger) and PA26
  (TRIG IN) have internal pull-downs; check that GPIO 26 is not left
  floating high by another process.
- **E-stim triggers do nothing:** `module` has `FAULT_n low` set (isolated
  side unpowered) or `FAULT_LATCHED`; a latched fault also shows on D7 (5 Hz).
- **`I2C_ERROR` in e-stim mode:** no ACK from the DAC60501 — module not
  seated, isolated side down, or SDA/SCL swapped.  The firmware retries the
  GAIN init every 100 ms.
- **Laser current is 2.5× too low across the board:** the DAC reference is
  VDDA (3.3 V) by design; if `dac.c` was changed back to the internal 2.5 V
  VREF the scaling in `Pi/protocol.py` no longer matches.
