# LaserHAT Pi-side

Pi-side Python code that talks to the LaserHAT. Currently the only thing
in here is an eink MVP that paints the Pi's primary IP address onto the
SSD1680Z display so you can see where to point your browser / SSH client.

```
Pi/
  eink_ip.py             one-shot: render IP + hostname, exit
  requirements.txt       Python deps
  systemd/
    eink-ip.service      runs eink_ip.py once on boot + each timer fire
    eink-ip.timer        re-render every 5 min so DHCP changes show up
```

---

## One-time install

```bash
sudo apt install python3-venv python3-pil

python3 -m venv ~/.venvs/laserhat
~/.venvs/laserhat/bin/pip install -r ~/Code/LaserDriver/Pi/requirements.txt
```

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
