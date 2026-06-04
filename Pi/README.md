# LaserHAT Pi-side

Pi-side Python code that talks to the LaserHAT. Five pieces:

- `eink_panel.py` — slim self-contained SSD1680 / GDEY0213B74 driver
  on `spidev` + `gpiozero` + Pillow. Full refresh (~3 s) and partial
  refresh (~300 ms) modes.
- `laser_hat.py` — thread-safe UART client class wrapping the
  firmware's line protocol (`?`, `i N`, `r N`, `h N`, `t`). Shared by
  every front-end.
- `pi_trigger.py` — `PiTrigger` class + CLI. Drives Pi GPIO 24 high
  briefly so the MCU's PA19 edge ISR fires a pulse directly,
  bypassing UART entirely (~50–100 µs end-to-end vs ~300–700 µs for
  a UART `t` command — and far less jitter).
- `eink_gui.py` — long-running daemon that polls the MCU at 20 Hz,
  runs the button-driven UI, pushes config changes back, and repaints
  the panel.
- `web_app.py` — Flask web GUI; same controls plus *two* trigger
  buttons (UART path and GPIO path), so you can compare the two.

```
Pi/
  eink_panel.py          SSD1680 driver (full + partial refresh)
  laser_hat.py           LaserHat class + CLI smoke tool
  pi_trigger.py          PiTrigger class + CLI (GPIO-path trigger)
  eink_ip.py             one-shot: render IP + hostname, exit
  eink_gui.py            long-running eink GUI daemon
  web_app.py             Flask web GUI
  templates/
    index.html           single-page browser UI (vanilla JS)
  requirements.txt       Python deps
  systemd/
    eink-ip.service      runs eink_ip.py once on boot + each timer fire
    eink-ip.timer        re-render every 5 min so DHCP changes show up
    eink-gui.service     runs eink_gui.py until killed
    laserhat-web.service runs web_app.py until killed
```

**One UART, one client.** `eink-gui.service` and `laserhat-web.service`
both want exclusive access to `/dev/ttyS0`. Pick one at a time. A
unified daemon that owns the UART and serves both surfaces is the
right answer once we've stabilised the two pieces separately.

`eink-ip.timer` and `eink-gui.service` both drive the panel — enable
one or the other, not both.

---

## One-time install

```bash
sudo apt install python3-venv python3-pil python3-spidev \
                 python3-gpiozero python3-lgpio

python3 -m venv --system-site-packages ~/.venvs/laserhat
~/.venvs/laserhat/bin/pip install -r ~/Code/LaserDriver/Pi/requirements.txt
```

`--system-site-packages` lets the venv see Pi OS's pre-installed
`gpiozero` / Pillow / spidev / lgpio. Pip only installs what's
missing (Flask and pyserial, typically). **`python3-lgpio` matters:**
without it `gpiozero` falls back to `RPi.GPIO`, which is broken on
recent Pi OS kernels. Installing it via pip needs `swig` and a C
build — don't bother, the apt package is prebuilt and fine.

Make sure SPI is enabled (it has to be, for both the eink and any future
sensor work):

```bash
sudo raspi-config nonint do_spi 0    # or via the menu: Interface → SPI → Enable
```

User needs to be in the `spi` and `gpio` groups (default on Pi OS):

```bash
groups | tr ' ' '\n' | grep -E '^(spi|gpio)$'
# If either is missing:
#   sudo usermod -aG spi,gpio $USER && newgrp spi
```

---

## Manual run (sanity check)

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python eink_ip.py
```

The display should clear to white, then show `LaserHAT` at the top,
`IP: 192.168.x.x` below it, the hostname underneath, and a thin red
rule across the bottom. Full refresh takes ~3 seconds.

If the script raises a SPI-busy or device-not-found error, double-check
`/dev/spidev0.0` exists (`ls /dev/spi*`) and that nothing else is
holding it.

---

## Deploy as a service

```bash
sudo cp ~/Code/LaserDriver/Pi/systemd/eink-ip.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eink-ip.timer
```

The timer starts the service 30 seconds after boot and re-runs it
every 5 minutes — short enough that DHCP changes show up promptly,
long enough that the panel sees only a few hundred refreshes per day.

**Edit the two paths in `eink-ip.service` before installing if your
account name isn't `kemerelab`** — `User=`, `Group=`, `WorkingDirectory=`,
and the `ExecStart=` python prefix all point at the default home.

### Operating it

```bash
# Force a refresh now:
sudo systemctl start eink-ip.service

# See the last few runs:
journalctl -u eink-ip.service --since '10 minutes ago'

# Stop the periodic refresh:
sudo systemctl disable --now eink-ip.timer

# Watch live (useful when debugging):
journalctl -u eink-ip.service -f
```

---

## The eink GUI

`eink_gui.py` is a long-running daemon. Run it manually first to
confirm it works:

```bash
cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python eink_gui.py
# Ctrl-C to stop.
```

### Button mapping

Per the LaserHAT mechanical layout — B1 / B2 on the left edge of the
display, B3 / B4 below it:

```
+--------+
|   B1   |  trigger pulse  (firmware fires on release, no UART needed)
+--------+
|        |
|  EINK  |
|        |
+--------+
|   B2   |  cycle selected parameter (i → r → h → i …)
+--------+
+---+----+
|B3 | B4 |  decrement / increment the selected parameter
+---+----+
```

Step sizes are coarse for usability (`i`: 8, `r`: 200 ticks, `h`: 500
ticks). Edit `PARAMS` in `eink_gui.py` to tune them.

Refresh: routine UI updates use the panel's partial-refresh mode
(~300 ms). Every 30th update we silently do a full refresh to clear
ghosting; the first paint after boot is always full. After a button
press, the GUI waits `SETTLE_GAP` (default 300 ms) of quiet before
repainting, so a burst of B4 presses coalesces to a single refresh
at the final value.

### LaserHat CLI

`laser_hat.py` doubles as a quick CLI when you want to poke the
firmware without the panel:

```bash
~/.venvs/laserhat/bin/python laser_hat.py query
~/.venvs/laserhat/bin/python laser_hat.py set i 100
~/.venvs/laserhat/bin/python laser_hat.py trigger
~/.venvs/laserhat/bin/python laser_hat.py watch     # live poll, Ctrl-C
```

### Deploy as a service

If `eink-ip.timer` is currently enabled, disable it first — both
services drive the same panel:

```bash
sudo systemctl disable --now eink-ip.timer

sudo cp ~/Code/LaserDriver/Pi/systemd/eink-gui.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eink-gui.service
journalctl -u eink-gui.service -f
```

Same paths-to-edit caveat as `eink-ip.service`: `User=`, `Group=`,
`WorkingDirectory=`, and the python prefix in `ExecStart=` assume
the user's `kemerelab` account.

---

## The web GUI

`web_app.py` is a Flask app that serves the same controls as the eink
GUI from a browser, plus a big trigger button. Single-page, vanilla
JS, ~500 ms state polling.

```bash
# (stop the eink GUI first if it's running)
sudo systemctl stop eink-gui.service

cd ~/Code/LaserDriver/Pi
~/.venvs/laserhat/bin/python web_app.py
# → serving on 0.0.0.0:8080 (http://<pi-ip>:8080/)
```

Open `http://<pi-ip>:8080/` from any device on the LAN. Each parameter
has a step input (preset to 8 / 200 / 500 ticks; edit freely) and ±
buttons. Trigger button is disabled while a pulse is running so you
can't fire `t` and get back `ERR busy`.

### Deploy as a service

```bash
sudo systemctl disable --now eink-gui.service     # if it's enabled
sudo cp ~/Code/LaserDriver/Pi/systemd/laserhat-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now laserhat-web.service
journalctl -u laserhat-web.service -f
```

The unit's `Conflicts=eink-gui.service` line stops eink-gui
automatically if you start the web service while eink-gui is running.

### Port override

`PORT` env var picks the bind port; the service unit sets 8080. To
run on 5000:

```bash
PORT=5000 ~/.venvs/laserhat/bin/python web_app.py
```

---

## Wiring (for reference)

Per the LaserHAT schematic (`LaserHAT/gpio_design.md`), the SSD1680Z is
connected to the Pi only — the MSPM0 does not have access:

| Pi GPIO       | HAT signal     | adafruit_epd pin     |
| ------------- | -------------- | -------------------- |
| GPIO 8 (CE0)  | `EINK_CS`      | `board.CE0`          |
| GPIO 9 (MISO) | `EINK_CIPO`    | `board.MISO`         |
| GPIO 10 (MOSI)| `EINK_COPI`    | `board.MOSI`         |
| GPIO 11 (SCLK)| `EINK_SCK`     | `board.SCK`          |
| GPIO 17       | `EINK_BUSY`    | `board.D17`          |
| GPIO 22       | `EINK_DC`      | `board.D22`          |
| GPIO 27       | `EINK_RESET`   | `board.D27`          |
