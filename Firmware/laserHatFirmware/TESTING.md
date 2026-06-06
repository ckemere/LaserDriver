# LaserHAT bring-up & test checklist

Hardware bring-up for the magic-framed binary protocol + broker stack
(branch `comms-binary-broker`). Everything below is validated off-hardware
(see `Pi/tests/` and `host_tools/proto_crosscheck.py`); this list is the
on-board confirmation.

Work top-down — a failure then tells you which layer broke. Do steps 1–8
with the **laser physically unplugged**: `STIM_MIRROR` (PA13) mirrors
laser-on, so you can validate everything short of actual light with no
risk. Plug the laser in only at the end.

> **Flashing rule:** flash with the laser unplugged, and **stop the broker
> first** — PA19 doubles as SWDIO and the trigger pin, and the broker holds
> Pi GPIO 24 (= SWDIO). See the firmware `README.md` "Flashing" section.

Protocol summary (frame = `SYNC(DE AD) | TYPE | payload`, no CRC):
`CMD_CONFIG{i,r,h}` / `CMD_TRIGGER` / `CMD_QUERY` → every command is
answered with `RSP_STATUS`; async `EVT_PULSE_START/END`, `EVT_BUTTON`.

---

## 1. Build the gcc firmware
```bash
make -C Firmware/laserHatFirmware -f Makefile.gcc clean all
```
- [ ] Builds to `build_gcc/main.elf` with **no errors and no `-Wall -Wextra`
      warnings** (this toolchain has flags the TI one doesn't — first place a
      real warning would surface).

## 2. Flash (laser unplugged)
```bash
sudo systemctl stop laserhat-broker.service     # frees GPIO 24 (= SWDIO)
make -C Firmware/laserHatFirmware -f Makefile.gcc flash   # +OPENOCD_GPIOCHIP=4 on Pi 5
```
- [ ] ~4 s `STIM_MIRROR` boot blink right after the command (= flash landed).

## 3. Raw link — the protocol's first real hardware test (broker stopped)
```bash
cd Firmware/laserHatFirmware
python3 host_tools/smoke_test.py                # broker must be stopped
```
- [ ] `query` prints a `State(...)`.
- [ ] After `config`, the echo `State` matches `i=100 r=2000 h=500`.
- [ ] `trigger` reports `EVT_PULSE_START / EVT_PULSE_END` (LED blinks).
- [ ] `python3 ../../Pi/laser_hat.py watch`, then press **B1** → `EVT_BUTTON`
      frames appear; B2/B3/B4 likewise.

> This validates magic framing, CONFIG, status-as-ack, and field layout
> against the real MCU. If it hangs or prints garbage, suspect a C↔Python
> field-layout mismatch (`emit_status` / `apply_config` vs the Python structs).

## 4. Pulse shape (ramp-down removal)
With a long pulse for visibility:
```bash
python3 ../../Pi/laser_hat.py config 320 200000 200000
python3 ../../Pi/laser_hat.py trigger
```
- [ ] Envelope on `PWM_LASER` (PA21) / the LED is **ramp up → hold → off**,
      with **no ramp-down tail**.

## 5. Broker + both GUIs together (the headline feature)
```bash
sudo systemctl restart laserhat-broker.service
journalctl -u laserhat-broker.service -f        # "serving …", NO "UART read error"
```
- [ ] `sudo fuser -v /dev/ttyS0` shows **only the broker**.
- [ ] eink GUI shows live state; web GUI loads and shows the same state.
- [ ] Physical buttons drive the eink UI **and** the change appears in the
      web page (pub/sub).
- [ ] A config change in the web UI reflects on the eink.

## 6. All three trigger paths (broker up)
- [ ] Web **TRIGGER (UART)** button → pulse; `phase` flips W→T→W in both GUIs.
- [ ] Web **TRIGGER (GPIO)** button (PA19) → pulse.
- [ ] External **BNC** edge (PA14) → pulse.

## 7. Resync robustness (what the framing is for)
- [ ] `sudo systemctl restart laserhat-broker.service` several times while the
      MCU runs — each reconnect is clean (`mcu_alive` returns, no stuck
      "UART read error"). Exercises mid-stream-restart resync.

## 8. Reflash still works (arming was removed)
- [ ] After PA19 has been a live trigger for a while, repeat step 2 — flash
      succeeds during the boot blink. Confirms the boot-window flash approach
      replaced arming.

## 9. Laser connected
- [ ] Plug the laser in; trigger one pulse at low intensity (`config 20 …`)
      and confirm light + the expected envelope.

---

### If something fails
- **Step 5 "UART read error":** `sudo fuser -v /dev/ttyS0` — a second process
  (stale GUI, getty) is on the port.
- **Step 3 hang/garbage:** field-layout mismatch — capture the raw bytes
  (`laser_hat.py watch`) and compare against `protocol.py`.
- **`make flash` "Error requesting gpio line swdio":** the broker still holds
  GPIO 24 — `sudo systemctl stop laserhat-broker.service` first.
