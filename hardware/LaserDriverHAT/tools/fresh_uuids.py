#!/usr/bin/env python3
"""Give every duplicated (uuid "...") in LaserDriverHAT.kicad_pcb a fresh value (the first occurrence keeps its own).
Footprints copied in by pcb_sync.py share their pads' and graphics' UUIDs with the library footprint they were copied
from; KiCad's DRC then confuses items of different footprints (it reported courtyard overlaps between parts 40 mm
apart, 2026-10-29).  Schematic links use the symbol path, not these UUIDs, so this is safe.   python tools/fresh_uuids.py"""
import os
import re
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BOARD = os.path.join(ROOT, "LaserDriverHAT.kicad_pcb")
t = open(BOARD).read()
seen = set()
n = 0


def fresh(m):
    global n
    u = m.group(1)
    if u in seen:
        n += 1
        return f'(uuid "{uuid.uuid4()}")'
    seen.add(u)
    return m.group(0)


t = re.sub(r'\(uuid "([0-9a-f-]+)"\)', fresh, t)
open(BOARD, "w").write(t)
print(f"replaced {n} duplicated uuids")
