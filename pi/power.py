"""Safe shutdown / reboot requests from the (unprivileged) GUIs.

The daemons run as the `laserhat` system user, which may not halt the
machine.  Instead of sudo or a polkit rule, the GUIs drop a flag file in
the broker's runtime directory and a root-owned systemd *path* unit
(`laserhat-power.path`) reacts to it by running `laserhat-power`, which
calls `systemctl poweroff` / `systemctl reboot`.  No daemon needs any
privilege; the only thing the user account can do is ask.

Why this exists: cutting 5 V while Raspberry Pi OS is writing corrupts
the SD card.  A HAT powered through its USB-C switch takes the Pi down
with it, so both GUIs offer an orderly halt first.

    request("poweroff")   -> creates <run_dir>/poweroff.request
    request("reboot")     -> creates <run_dir>/reboot.request

`run_dir` defaults to /run/laserhat (the broker's RuntimeDirectory, owned
by `laserhat`); LASERHAT_RUN_DIR overrides it for tests.
"""

from __future__ import annotations

import os
import time

DEFAULT_RUN_DIR = "/run/laserhat"
ACTIONS = ("poweroff", "reboot")


def run_dir() -> str:
    return os.environ.get("LASERHAT_RUN_DIR", DEFAULT_RUN_DIR)


def request_path(action: str, directory: str | None = None) -> str:
    if action not in ACTIONS:
        raise ValueError(f"unknown power action {action!r}")
    return os.path.join(directory or run_dir(), f"{action}.request")


def request(action: str, directory: str | None = None) -> bool:
    """Ask the system to power off or reboot.  Returns True once the
    request file exists (the path unit does the rest within a second)."""
    path = request_path(action, directory)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(f"{action} requested by pid {os.getpid()} at {time.time():.0f}\n")
        return True
    except OSError:
        return False
