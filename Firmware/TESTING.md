# LaserHAT Rev 2 bring-up checklist

For the Rev 2 HAT **with no module plugged into J8/J9** (laser and e-stim
modules come later).  Everything below is validated off-hardware
(`Pi/tests/`, `host_tools/proto_crosscheck.py`); this list is the on-board
confirmation.  Work top-down — a failure then tells you which layer broke.

What the bring-up firmware does: five edge buttons → `EVT_BUTTON`, FIRE
fires a pulse; D7 boot-blinks, heartbeats at 1 Hz when idle and is solid
during a pulse; the pulse envelope is mirrored on STIM OUT (J7 + D9); TRIG IN
(J6) and Pi GPIO 26 fire a pulse; the binary protocol runs on both UARTs
(Pi GPIO 14/15 and the USB-C CH340N).

Protocol summary (frame = `SYNC(DE AD) | TYPE | payload`, no CRC):
`CMD_CONFIG{i,r,h}` / `CMD_TRIGGER` / `CMD_QUERY` → every command is
answered with `RSP_STATUS`; async `EVT_PULSE_START/END`, `EVT_BUTTON`.

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
- [ ] ~4 s D7 boot blink right after the command (= flash landed), then a
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
