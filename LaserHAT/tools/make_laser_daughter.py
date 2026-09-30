#!/usr/bin/env python3
"""Create the laser-diode daughterboard schematic from the Rev 1 laser sheet.

The Rev 1 `laser_driver_circuit.kicad_sch` sub-sheet becomes the root sheet of
LaserHAT/LaserDaughter/LaserDaughter.kicad_sch with these changes:
  * hierarchical inputs -> daughterboard header nets (DB_PWM_A/B, DB_DAC, DB_ADC_A)
  * boost input and op-amp supply come from +5V on the header
    (U3 on +5V keeps Q2's gate below its +/-8 V V_GS rating)
  * R1/R2 divider reports the 5 V / 12 V compliance rail on DB_ADC_B
    (replaces the Rev 1 RGB indicator; shown on the OLED / web GUI instead)
  * J1/J3: 1x5 male headers mating with HAT J8/J9
"""
import os
import sys
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schlib import *  # noqa: E402,F401
from sexpr_patch import patch, parse  # noqa: E402
from rev2_migrate import rev1, text, drop  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(HERE, "LaserDaughter")
SHEET_UUID = "212bfd25-f831-4b85-926b-000000000002"
PROJECT = "LaserDaughter"
PATH = f"/{SHEET_UUID}"
FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_HDR = "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"


def build():
    s = rev1("laser_driver_circuit.kicad_sch")
    kw = dict(project=PROJECT, sheet_path=PATH)

    for lb in list(s.hierarchicalLabels):
        if lb.text == "V_LASER_BOOST_IN":
            x, y = lb.position.X, lb.position.Y
            drop(s, lb)
            power_symbol(s, "power:+5V", x, y, **kw)
    names = {"PWM_LASER": "DB_PWM_A", "PWM_DUMMY": "DB_PWM_B", "DIODE_ADC": "DB_ADC_A"}
    for lb in list(s.hierarchicalLabels):
        if lb.text == "LASER_VREF":        # op-amp setpoint now comes via the DAC divider
            relabel(s, lb, "IREF", kind="local")
        else:
            relabel(s, lb, names[lb.text], kind="global")

    # Op-amp supply: LASER_V (up to 12 V) -> +5V
    u3 = find_sym(s, "U3")
    x, y, _ = sym_pins(s, u3)["5"]
    lb = next(l for l in trace(s, x, y)[1] if l.text == "LASER_V")
    lx, ly = lb.position.X, lb.position.Y
    drop(s, lb)
    power_symbol(s, "power:+5V", lx, ly, **kw)

    # ---- 300 mA design point (red SLD1255VFR 280 mA max; blue PLT3-450GB 120 mA) ----
    # Sense resistor 10R -> 2R: 0.16 W at 280 mA (was 0.9 W at 300 mA in a 1206).
    set_value(s, "Rs1", "2R 1% 0.5W (ESR18EZPF2R00)")
    # DAC divider: full-scale DAC 3.3 V -> IREF 0.673 V -> ~335 mA (hardware ceiling).
    r3 = add_symbol(s, "Device:R", "R3", "39k 1%", 88.9, 185.42, footprint=FP_R, **kw)
    stub_label(s, r3, "1", "DB_DAC", kind="global")
    stub_label(s, r3, "2", "IREF", kind="local")
    r4 = add_symbol(s, "Device:R", "R4", "10k 1%", 99.06, 185.42, footprint=FP_R, **kw)
    stub_label(s, r4, "1", "IREF", kind="local")
    stub_power(s, r4, "2", "power:GND", **kw)
    # Q2 linear current sink: SOT-23 -> SOT-223 NDT3055L (logic level, ~3 W on copper);
    # worst case is a blue LD on 12 V: (12 - 5.2) V x 120 mA ~ 0.8 W continuous.
    q2 = find_sym(s, "Q2")
    x, y, a_, m = q2.position.X, q2.position.Y, q2.position.angle, q2.mirror
    s.schematicSymbols.remove(q2)
    add_symbol(s, "Transistor_FET:NDT3055L", "Q2", "NDT3055L", x, y, angle=a_, mirror=m,
               footprint="Package_TO_SOT_SMD:SOT-223-3_TabPin2", **kw)
    # 4-terminal photodiode strap: DNP 2.54 mm header -> solder jumper (much smaller)
    set_value(s, "J4", "PD_K-LASER_V (solder jumper)",
              footprint="Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm")
    # Op-amp supply bypass (missing in Rev 1)
    c12 = add_symbol(s, "Device:C", "C12", "100nF", 109.22, 185.42, footprint="Capacitor_SMD:C_0402_1005Metric", **kw)
    stub_power(s, c12, "1", "power:+5V", **kw)
    stub_power(s, c12, "2", "power:GND", **kw)
    # Boost inductor: 4x4 mm, 10 uH, Isat >= 1.5 A (input peaks ~1.1 A at 12 V / 300 mA out)
    set_value(s, "L1", "10uH Isat>=1.5A (SRN4018-100M)", footprint="Inductor_SMD:L_Bourns-SRN4018")
    # Dummy-load diode carries the full current while the LD is off: 1N4148W -> SS14
    set_value(s, "D3", "SS14", footprint="Diode_SMD:D_SOD-123F")
    # Dummy-load zener: Rev 1 drew it with a plain-diode symbol, forward biased (only ~0.7 V).
    # Now a correctly oriented 2.4 V + 2.7 V stack; the RED shunt (J5) shorts the 2.7 V one:
    #   shunt ON  (red,  Vf 2.6-3.0 V): ~0.4 + 2.4       = 2.8 V
    #   shunt OFF (blue, Vf 5.2-6.5 V): ~0.4 + 2.4 + 2.7 = 5.5 V
    d2 = find_sym(s, "D2")
    for n, (px, py, _d) in sym_pins(s, d2).items():
        wl, labs = trace(s, px, py)
        for w in wl:
            s.graphicalItems.remove(w)
    s.schematicSymbols.remove(d2)
    stub_label(s, find_sym(s, "D3"), "1", "DUMMY_TOP", kind="local")
    q1a = next(q for q in s.schematicSymbols if ref_of(q) == "Q1" and "6" in sym_pins(s, q))
    stub_label(s, q1a, "6", "DUMMY_BOT", kind="local")
    d2 = add_symbol(s, "Device:D_Zener", "D2", "2.4V 1W (KDZVTR2.4B)", 139.7, 110.49, angle=90,
                    footprint="Diode_SMD:D_SOD-123F", **kw)
    stub_label(s, d2, "1", "DUMMY_TOP", kind="local")
    stub_label(s, d2, "2", "DUMMY_MID", kind="local")
    d4 = add_symbol(s, "Device:D_Zener", "D4", "2.7V 1W (KDZVTR2.7B)", 154.94, 110.49, angle=90,
                    footprint="Diode_SMD:D_SOD-123F", **kw)
    stub_label(s, d4, "1", "DUMMY_MID", kind="local")
    stub_label(s, d4, "2", "DUMMY_BOT", kind="local")
    j5 = add_symbol(s, "Connector_Generic:Conn_01x02", "J5", "RED_SHUNT", 170.18, 110.49,
                    footprint="Connector_PinHeader_2.00mm:PinHeader_1x02_P2.00mm_Vertical", **kw)
    stub_label(s, j5, "1", "DUMMY_MID", kind="local")
    stub_label(s, j5, "2", "DUMMY_BOT", kind="local")
    s.texts = [tx for tx in s.texts
               if not tx.text.startswith(("Rsense sets", "At Vref", "Dummy load", "4.7V Zener", "User a 1.8V"))]
    text(s, "Current setpoint: I_LD = V(IREF) / Rs1 = DAC x (10k / 49k) / 2R  (full scale ~335 mA)\n"
            "Dummy load: D3 + D2 (+ D4 unless J5 shunted). J5 ON = red LD (~2.8 V), OFF = blue LD (~5.5 V).\n"
            "Q2 dissipation: red on 5 V ~0.5 W, blue on 12 V ~0.8 W -> SOT-223 on copper.\n"
            "Use the 5 V setting for a single red LD (12 V would put ~2.5 W into Q2).",
         60.0, 236.22)

    # Compliance-rail monitor: 12 V -> 2.98 V, 5 V -> 1.24 V at DB_ADC_B
    r1 = add_symbol(s, "Device:R", "R1", "100k 1%", 254.0, 71.12, footprint=FP_R, **kw)
    stub_label(s, r1, "1", "LASER_V", kind="global")
    stub_label(s, r1, "2", "DB_ADC_B", kind="global")
    r2 = add_symbol(s, "Device:R", "R2", "33k 1%", 254.0, 91.44, footprint=FP_R, **kw)
    stub_label(s, r2, "1", "DB_ADC_B", kind="global")
    stub_power(s, r2, "2", "power:GND", **kw)
    text(s, "Compliance monitor: V(ADC_B) = LASER_V x 33/133\n"
            "(12 V -> 2.98 V, 5 V -> 1.24 V). Firmware reports 5 V / 12 V to the OLED + web GUI.",
         238.76, 55.88)

    # Mating headers (male, on the underside of the daughterboard)
    j1 = add_symbol(s, "Connector_Generic:Conn_01x05", "J1", "HAT_J8", 330.2, 116.84,
                    footprint=FP_HDR, **kw)
    stub_power(s, j1, "1", "power:GND", **kw)
    stub_power(s, j1, "2", "power:+5V", **kw)
    x, y, _ = sym_pins(s, j1)["3"]
    no_connect(s, x, y)                     # J8.3 = GPIO / FAULT_n since 2026-09-29: unused on the laser board
    stub_label(s, j1, "4", "DB_PWM_B", kind="global")
    stub_label(s, j1, "5", "DB_PWM_A", kind="global")   # J8.5 = PWM_A (PA7) since 2026-09-29 (was pin 3)
    j3 = add_symbol(s, "Connector_Generic:Conn_01x05", "J3", "HAT_J9", 330.2, 147.32,
                    footprint=FP_HDR, **kw)
    stub_power(s, j3, "1", "power:GND", **kw)
    x, y, _ = sym_pins(s, j3)["2"]
    no_connect(s, x, y)                     # switched 3V3 unused on the laser board
    stub_label(s, j3, "3", "DB_DAC", kind="global")
    stub_label(s, j3, "4", "DB_ADC_A", kind="global")
    stub_label(s, j3, "5", "DB_ADC_B", kind="global")
    text(s, "HAT interface (two 1x5, 2.54 mm)\n"
            "J1 (HAT J8): 1 GND  2 +5V  3 GPIO/FAULT (n/c)  4 PWM_B = dummy  5 PWM_A = laser\n"
            "J3 (HAT J9): 1 GND  2 +3V3 (n/c)  3 DAC = current setpoint  4 ADC_A = PD  5 ADC_B = compliance",
         292.1, 101.6)
    prune(s)

    s.titleBlock.title = "Laser Diode Daughterboard"
    s.titleBlock.revision = "2.0"
    s.titleBlock.date = "2026-09-25"
    return s


def retarget_instances(txt):
    """Every symbol instance -> (project "LaserDaughter" (path "/<sheet uuid>" ...))."""
    root = parse(txt)
    edits = []
    for c in root.children:
        if c.head != "symbol":
            continue
        inst = c.child("instances")
        if inst is None:
            continue
        # Prefer the LaserDriver (HAT) instance; the Rev 1 sheet also carries stale
        # instances from the old stand-alone PCB/laser_driver project.
        found = []
        for proj in inst.children:
            pname = proj.tokens[1][2].strip('"')
            for p in proj.children:
                ref = next((q.tokens[1][2] for q in p.children if q.head == "reference"), None)
                unit = next((q.tokens[1][2] for q in p.children if q.head == "unit"), "1")
                found.append((pname in ("LaserDriver", PROJECT), ref, unit))
        found.sort(key=lambda f: not f[0])
        _, ref, unit = found[0]
        new = (f'(instances (project "{PROJECT}" (path "{PATH}" '
               f'(reference {ref}) (unit {unit}))))')
        edits.append((inst.start, inst.end, new))
    for a, b, rep in sorted(edits, reverse=True):
        txt = txt[:a] + rep + txt[b:]
    if "(sheet_instances" not in txt:
        end = txt.rstrip().rfind(")")
        txt = txt[:end] + '\t(sheet_instances (path "/" (page "1")))\n' + txt[end:]
    return txt


def main():
    s = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    txt = retarget_instances(patch(s._orig_text, s._orig, s))
    out = os.path.join(OUT_DIR, "LaserDaughter.kicad_sch")
    with open(out, "w") as f:
        f.write(txt)
    print("wrote", out)


if __name__ == "__main__":
    main()
