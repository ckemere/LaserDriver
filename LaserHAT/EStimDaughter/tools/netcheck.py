"""
Connectivity check: the schematic's exported netlist must partition the component pins exactly as sch_parts.PARTS says.
Run:  python tools/netcheck.py   (exports the netlist with kicad-cli first: $KICAD_CLI, PATH, or the macOS bundle)
Exit code 0 = identical connectivity.
"""
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
from sch_parts import PARTS  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def expected():
    nets = {}
    for p in PARTS:
        for pin, net in p["nets"].items():
            if net is not None:
                nets.setdefault(net, set()).add((p["ref"], pin))
    return nets


def actual(sch):
    out = os.path.join(ROOT, "tools", "ref", "netlist_current.xml")
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadxml", "-o", out, sch],
                   check=True, capture_output=True)
    nets = {}
    for n in ET.parse(out).getroot().iter("net"):
        pins = {(nd.get("ref"), nd.get("pin")) for nd in n.iter("node") if not nd.get("ref").startswith("#")}
        if pins:
            nets[n.get("name")] = pins
    return nets


def compare(exp, act):
    ok = True
    exp_sets = {frozenset(v): k for k, v in exp.items()}
    act_sets = {frozenset(v): k for k, v in act.items()}
    # single-pin 'nets' in the actual netlist are unconnected pins (NC or forgotten)
    for s, name in exp_sets.items():
        if s not in act_sets:
            ok = False
            owners = {}
            for pin in s:
                for an, ap in act.items():
                    if pin in ap:
                        owners.setdefault(an, set()).add(pin)
            print(f"MISMATCH expected net {name}: {sorted(s)}\n    found split/merged as: " +
                  "; ".join(f"{an} {sorted(p)} (+{len(act[an]) - len(p)} other)" for an, p in owners.items()))
        elif not act_sets[s].lstrip("/").endswith(name.lstrip("/")) and not name.startswith(("+", "-", "GND")):
            print(f"note: net {name} is named {act_sets[s]}")
    extra = [s for s in act_sets if s not in exp_sets and len(s) > 1]
    for s in extra:
        ok = False
        print(f"UNEXPECTED net {act_sets[s]}: {sorted(s)}")
    return ok


if __name__ == "__main__":
    sch = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "EStimDaughter.kicad_sch")
    ok = compare(expected(), actual(sch))
    print("CONNECTIVITY OK" if ok else "CONNECTIVITY MISMATCH")
    sys.exit(0 if ok else 1)
