#!/usr/bin/env python3
"""Project footprints into dcdcpod.pretty (plain text edits, no pcbnew needed):
  * DCDC_SIP6_A0515S_BodyN: the StimHAT's A0515S SIP footprint (body 0.9 mm behind / 5.1 mm in front of the pin row,
    1.6 mm pads, pins 1 2 4 5 6 on 2.54 mm), its VRML model pointed at dcdcpod.3dshapes
  * PinHeader_1x02_P2.54mm_Horizontal_Pod, PinHeader_1x04_P2.00mm_Horizontal_Pod: KiCad's right-angle pin headers with
    the silk / fab drawing of the pins beyond the body removed (on the pod they hang over the bottom edge into the HAT,
    and silk crossing Edge.Cuts is a DRC warning) and the silk pin-1 corner mark removed (the square pad marks pin 1;
    the pod's pin-name silk sits where the mark was); pads, body and 3D model unchanged
    python tools/make_footprints.py"""
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = os.path.join(ROOT, "dcdcpod.pretty")
STIMHAT = os.path.join(ROOT, "..", "StimHAT", "stimhat.pretty")
KICAD_FP = next(d for d in ("/usr/share/kicad/footprints", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
                if os.path.isdir(d))
os.makedirs(LIB, exist_ok=True)

# ---- A0515S SIP
src = open(os.path.join(STIMHAT, "DCDC_SIP6_A0515S_BodyN.kicad_mod")).read()
src = src.replace("${KIPRJMOD}/stimhat.3dshapes/", "${KIPRJMOD}/dcdcpod.3dshapes/")
open(os.path.join(LIB, "DCDC_SIP6_A0515S_BodyN.kicad_mod"), "w").write(src)
print("wrote DCDC_SIP6_A0515S_BodyN")


def blocks(text):
    """split a footprint file into its top-level (...) items (after the header line)"""
    items, depth, start, q = [], 0, None, False
    for i, c in enumerate(text):
        if c == '"' and text[i - 1] != "\\":
            q = not q
        elif not q:
            if c == "(":
                if depth == 1:
                    start = i
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 1 and start is not None:
                    items.append(text[start:i + 1]); start = None
    return items


def strip_pins(lib, name, body_end):
    """drop F.SilkS / F.Fab lines and rects that lie entirely beyond the body end (the pins)"""
    text = open(os.path.join(KICAD_FP, lib + ".pretty", name + ".kicad_mod")).read()
    head = text[:text.index("\n") + 1]
    keep, dropped = [], 0
    for it in blocks(text):
        if it.startswith(("(fp_line", "(fp_rect")) and ('"F.SilkS"' in it or '"F.Fab"' in it):
            xs = [float(m.group(1)) for m in re.finditer(r"\((?:start|end)\s+(-?[\d.]+)\s+-?[\d.]+\)", it)]
            if min(xs) >= body_end - 0.01 or ('"F.SilkS"' in it and max(xs) <= 0.01):   # pins, and the pin-1 corner mark
                dropped += 1
                continue
        if it.startswith("(footprint "):
            continue
        it = it.replace(f'"{name}"', f'"{name}_Pod"')
        keep.append(it)
    out = head.replace(f'"{name}"', f'"{name}_Pod"') + "\n".join("\t" + k for k in keep) + "\n)\n"
    out = out.replace('(descr "', '(descr "DC-DC pod copy, pin drawing beyond the body removed; ')
    open(os.path.join(LIB, name + "_Pod.kicad_mod"), "w").write(out)
    print(f"wrote {name}_Pod: dropped {dropped} pin graphics")


strip_pins("Connector_PinHeader_2.54mm", "PinHeader_1x02_P2.54mm_Horizontal", 4.15)
strip_pins("Connector_PinHeader_2.00mm", "PinHeader_1x04_P2.00mm_Horizontal", 3.11)
