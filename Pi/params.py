"""Adjustable LaserHat parameters — single source of truth.

Defines each knob's increment (step) size and range once, so the eink
GUI (eink_gui.py) and the web GUI (web_app.py / templates/index.html)
stay in sync instead of carrying their own copies.  Pure stdlib.

Per-surface *display formatting* (e.g. the eink's "ms" suffix) is kept
in the surface that renders it; only the numeric spec lives here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParamSpec:
    name: str        # firmware knob letter: 'i' / 'r' / 'h'
    label: str       # human-readable name
    step: int        # +/- increment applied by the GUIs
    minimum: int
    maximum: int


PARAMS: list[ParamSpec] = [
    ParamSpec("i", "intensity", step=8,   minimum=1, maximum=320),
    ParamSpec("r", "ramp",      step=200, minimum=1, maximum=10_000_000),
    ParamSpec("h", "hold",      step=500, minimum=1, maximum=10_000_000),
]

PARAMS_BY_NAME: dict[str, ParamSpec] = {p.name: p for p in PARAMS}
