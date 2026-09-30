"""
Small schematic-drawing engine for gen_schematic.py: places symbols from sch_parts on a 1.27 mm grid and draws
real wires between pins (Manhattan, optional channel x), power symbols, global labels, no-connects and PWR_FLAGs.
Wires are split wherever another connection point lands on them and junctions are added where >= 3 things meet, so
the file KiCad reads has explicit connectivity; tools/netcheck.py then proves the netlist equals sch_parts.
"""
import math
import uuid

import sch_symbols as S
from sch_parts import BY_REF

G = 1.27
# Deterministic UUIDs (2026-09-29): symbol instances hash their reference (unit 1) or "REF#uN", everything else a running
# counter, all in one fixed namespace.  Regenerating therefore keeps every UUID, so the board footprints, whose path is
# "/ROOT/<symbol uuid>", stay linked across F8 (Update PCB from Schematic) and git diffs stay small.
UUID_NS = uuid.UUID("6f1d3c2a-9b7e-4e5f-8a1c-0e2d4b6a8c10")
_uuid_counter = [0]


def U(key=None):
    if key is None:
        _uuid_counter[0] += 1
        key = f"item{_uuid_counter[0]}"
    return str(uuid.uuid5(UUID_NS, key))


def symbol_uuid(ref, unit=1):
    return U(ref if unit == 1 else f"{ref}#u{unit}")
F = S.F

# PWR_FLAG (power symbol with a power_out pin)
S.add_symbol("PWR_FLAG", "#FLG", S.poly([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)]),
             [("1", "pwr", 0, 0, 90, "power_out")], power=True, ref_pos=(0, 1.905), val_pos=(0, 3.81),
             hide_pin_numbers=True, hide_pin_names=True)

PROJ = "EStimDaughter"
ROOT = U()


def snap(v):
    return round(round(v / G) * G, 4)


class Sheet:
    def __init__(self):
        self.items = []
        self.pos = {}           # (ref, unit) -> (x, y, rot, mirror)
        self.segs = []          # ((x1, y1), (x2, y2))
        self.attach = []        # connection points of labels / power symbols / NC
        self.pwr_n = 0
        self.flg_n = 0
        self.wired = set()      # (ref, pin) handled explicitly

    # ------------------------------------------------------------------ symbols
    def put(self, ref, x, y, rot=0, mirror=False, ref_at=None, val_at=None, hide_val=False, unit=1):
        p = BY_REF[ref]
        x, y = snap(x), snap(y)
        self.pos[(ref, unit)] = (x, y, rot, mirror)
        stxt, pinmap = S.symbols[p["sym"]]
        umap = S.UNITS.get(p["sym"], {})
        pinmap = {n: v for n, v in pinmap.items() if umap.get(n, 1) == unit}
        pins_txt = "\n    ".join(f'(pin "{n}" (uuid "{U()}"))' for n in pinmap)
        small = p["sym"] in ("R", "C", "Polyfuse", "D", "D_Zener", "TestPoint", "TL431_SOT23") or p["sym"].startswith("Q_")
        if ref_at is None:
            if p["sym"] in ("R", "C", "Polyfuse"):
                ref_at, val_at = ((2.54, -1.27), (2.54, 1.27)) if rot in (0, 180) else ((0, -3.81), (0, 3.81))
            elif p["sym"] in ("D", "D_Zener"):
                ref_at, val_at = ((0, -3.81), (0, 3.81)) if rot in (0, 180) else ((2.54, -1.27), (2.54, 1.27))
            elif p["sym"].startswith("Q_"):
                ref_at, val_at = (5.08, -1.27), (5.08, 1.27)
            elif p["sym"] == "TL431_SOT23":
                ref_at, val_at = (2.54, -1.27), (2.54, 1.27)
            elif p["sym"] == "TestPoint":
                ref_at, val_at = (0, -5.08), (0, -3.3)
            else:
                h = max(abs(v[1]) for v in pinmap.values()) + 2.54
                ref_at, val_at = (0, -h), (0, h)
        side = "left" if ref_at[0] > 0 else "right" if ref_at[0] < 0 else ""
        if side and (rot == 180) != bool(mirror):     # KiCad mirrors field justification with the symbol
            side = {"left": "right", "right": "left"}[side]
        just = f"(justify {side})" if small and side else ""
        fa = 90 if rot in (90, 270) else 0     # KiCad draws field angle relative to the symbol: keep text horizontal
        props = [
            f'(property "Reference" "{ref}" (at {F(x + ref_at[0])} {F(y + ref_at[1])}  {fa}) (effects (font (size 1.27 1.27)) {just}))',
            f'(property "Value" "{p["value"]}" (at {F(x + val_at[0])} {F(y + val_at[1])}  {fa}) (effects (font (size 1.27 1.27)) {just}{" (hide yes)" if hide_val else ""}))',
            f'(property "Footprint" "{p["fp"]}" (at {F(x)} {F(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
            f'(property "Datasheet" "" (at {F(x)} {F(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))',
        ]
        if p["lcsc"]:
            props.append(f'(property "LCSC" "{p["lcsc"]}" (at {F(x)} {F(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))')
        is_tp = p["sym"] == "TestPoint"
        self.items.append(
            f'(symbol (lib_id "{S.LIB}:{p["sym"]}") (at {F(x)} {F(y)} {rot}){" (mirror y)" if mirror else ""} (unit {unit}) '
            f'(exclude_from_sim no) (in_bom {"no" if is_tp else "yes"}) (on_board yes) (dnp {"yes" if p.get("dnp") else "no"})\n    (uuid "{symbol_uuid(ref, unit)}")\n    '
            + "\n    ".join(props) + f"\n    {pins_txt}\n"
            f'    (instances (project "{PROJ}" (path "/{ROOT}" (reference "{ref}") (unit {unit}))))\n  )')

    def pin(self, ref, num):
        """absolute (x, y) of a pin end and its outward direction (dx, dy)"""
        sym = BY_REF[ref]["sym"]
        x, y, rot, mirror = self.pos[(ref, S.UNITS.get(sym, {}).get(num, 1))]
        px, py, pang = S.symbols[sym][1][num]
        if mirror:
            px, pang = -px, (180 - pang) % 360
        a = math.radians(rot)
        rx, ry = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
        out = math.radians((pang + 180 + rot) % 360)
        return (snap(x + rx), snap(y - ry)), (round(math.cos(out)), -round(math.sin(out)))

    def P(self, spec):
        if isinstance(spec, tuple):
            return (snap(spec[0]), snap(spec[1]))
        ref, num = spec.split(".")
        self.wired.add((ref, num))
        return self.pin(ref, num)[0]

    # ------------------------------------------------------------------ wires
    def seg(self, a, b):
        if a != b:
            self.segs.append((a, b))

    def W(self, *specs, first="h"):
        """Chain of points (pins 'REF.N' or (x, y)); non-aligned hops are L-shaped, horizontal-first by default.
        A spec ('x', value) or ('y', value) is a relative channel: jog to that x (or y) keeping the other coordinate."""
        pts, modes = [], []
        for s in specs:
            if isinstance(s, tuple) and s[0] in ("x", "y"):
                last = pts[-1]
                pts.append((snap(s[1]), last[1]) if s[0] == "x" else (last[0], snap(s[1])))
                modes.append("v" if s[0] == "x" else "h")     # after a channel jog, turn the other way
            else:
                pts.append(self.P(s))
                modes.append(first)
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            mode = modes[i]
            if a[0] == b[0] or a[1] == b[1]:
                self.seg(a, b)
            elif mode == "h":
                self.seg(a, (b[0], a[1])); self.seg((b[0], a[1]), b)
            else:
                self.seg(a, (a[0], b[1])); self.seg((a[0], b[1]), b)
        return pts[-1]

    def stub(self, spec, length=2.54):
        ref, num = spec.split(".")
        self.wired.add((ref, num))
        (x, y), (dx, dy) = self.pin(ref, num)
        e = (snap(x + dx * length), snap(y + dy * length))
        self.seg((x, y), e)
        return e, (dx, dy)

    # ------------------------------------------------------------------ power / labels / NC
    def PWR(self, spec, net=None, length=2.54, at=None, up=None):
        """power symbol on a pin (via a stub) or at a point; orientation from the stub direction."""
        if at is None:
            ref, num = spec.split(".")
            net = net or BY_REF[ref]["nets"][num]
            if length:
                e, (dx, dy) = self.stub(spec, length)
            else:
                self.wired.add((ref, num))
                e, (dx, dy) = self.pin(ref, num)
        else:
            e, (dx, dy) = (snap(at[0]), snap(at[1])), up
        gnd = S.POWER_NETS[net]
        if gnd:
            rot = {(0, 1): 0, (0, -1): 180, (1, 0): 270, (-1, 0): 90}[(dx, dy)]
        else:
            rot = {(0, -1): 0, (0, 1): 180, (1, 0): 90, (-1, 0): 270}[(dx, dy)]
        self.pwr_n += 1
        ref = f"#PWR{self.pwr_n:03d}"
        vpos = (e[0] + dx * 3.81 if dx else e[0], e[1] + dy * 3.81 if dy else e[1])
        if dx:
            vpos = (e[0] + dx * 4.5, e[1])
        self.items.append(self._power(net, ref, e, rot, vpos))
        self.attach.append(e)
        return e

    def _power(self, net, ref, e, rot, vpos):
        just = "" if rot in (0, 180) else (" (justify left)" if vpos[0] > e[0] else " (justify right)")
        return (f'(symbol (lib_id "{S.LIB}:{net}") (at {F(e[0])} {F(e[1])} {rot}) (unit 1) (exclude_from_sim no) '
                f'(in_bom no) (on_board no) (dnp no)\n    (uuid "{U()}")\n'
                f'    (property "Reference" "{ref}" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                f'    (property "Value" "{net}" (at {F(vpos[0])} {F(vpos[1])} {90 if rot in (90, 270) else 0}) (effects (font (size 1.27 1.27)){just}))\n'
                f'    (property "Footprint" "" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                f'    (property "Datasheet" "" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                f'    (pin "1" (uuid "{U()}"))\n'
                f'    (instances (project "{PROJ}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n  )')

    def FLAG(self, at, up=(0, -1)):
        """PWR_FLAG at a point that is already on the net (e.g. the end of a power stub)."""
        self.flg_n += 1
        ref = f"#FLG{self.flg_n:02d}"
        e = (snap(at[0]), snap(at[1]))
        rot = {(0, -1): 0, (0, 1): 180, (1, 0): 90, (-1, 0): 270}[up]
        self.items.append(
            f'(symbol (lib_id "{S.LIB}:PWR_FLAG") (at {F(e[0])} {F(e[1])} {rot}) (unit 1) (exclude_from_sim no) '
            f'(in_bom no) (on_board no) (dnp no)\n    (uuid "{U()}")\n'
            f'    (property "Reference" "{ref}" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'    (property "Value" "PWR_FLAG" (at {F(e[0])} {F(e[1] - 4.5)} 0) (effects (font (size 1.0 1.0)) (hide yes)))\n'
            f'    (property "Footprint" "" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'    (property "Datasheet" "" (at {F(e[0])} {F(e[1])} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'    (pin "1" (uuid "{U()}"))\n'
            f'    (instances (project "{PROJ}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n  )')
        self.attach.append(e)

    def LBL(self, spec, net=None, length=2.54, at=None, direction=None, shape="passive"):
        """global label on a pin (via stub) or at a point; direction = outward (dx, dy) the label points to."""
        if at is None:
            ref, num = spec.split(".")
            net = net or BY_REF[ref]["nets"][num]
            e, d = self.stub(spec, length)
        else:
            e, d = (snap(at[0]), snap(at[1])), direction
        ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[d]
        just = "left" if ang in (0, 90) else "right"
        self.items.append(
            f'(global_label "{net}" (shape {shape}) (at {F(e[0])} {F(e[1])} {ang}) (fields_autoplaced yes) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid "{U()}")\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {F(e[0])} {F(e[1])} 0) '
            f'(effects (font (size 1.27 1.27)) (hide yes))))')
        self.attach.append(e)
        return e

    def NET(self, spec, net=None, length=2.54):
        """local net label at the end of a short stub (for a loop inside one block)."""
        ref, num = spec.split(".")
        net = net or BY_REF[ref]["nets"][num]
        e, d = self.stub(spec, length)
        ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[d]
        self.items.append(f'(label "{net}" (at {F(e[0])} {F(e[1])} {ang}) (fields_autoplaced yes) '
                          f'(effects (font (size 1.27 1.27)) (justify {"left" if ang in (0, 90) else "right"} bottom)) (uuid "{U()}"))')
        self.attach.append(e)
        return e

    def LAB(self, net, at, direction=(1, 0)):
        """local net label placed on an existing wire point."""
        p = (snap(at[0]), snap(at[1]))
        ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[direction]
        self.items.append(f'(label "{net}" (at {F(p[0])} {F(p[1])} {ang}) (fields_autoplaced yes) '
                          f'(effects (font (size 1.27 1.27)) (justify {"left" if ang in (0, 90) else "right"} bottom)) (uuid "{U()}"))')
        self.attach.append(p)

    def NC(self, spec):
        ref, num = spec.split(".")
        self.wired.add((ref, num))
        (x, y), _ = self.pin(ref, num)
        self.items.append(f'(no_connect (at {F(x)} {F(y)}) (uuid "{U()}"))')

    # ------------------------------------------------------------------ text / boxes
    def text(self, s, x, y, size=1.27, bold=False):
        b = " (bold yes)" if bold else ""
        self.items.append(f'(text "{s}" (exclude_from_sim no) (at {F(x)} {F(y)} 0) '
                          f'(effects (font (size {size} {size}){b}) (justify left bottom)) (uuid "{U()}"))')

    def box(self, x1, y1, x2, y2, title=None):
        self.items.append(f'(rectangle (start {F(x1)} {F(y1)}) (end {F(x2)} {F(y2)}) '
                          f'(stroke (width 0.2) (type dash)) (fill (type none)) (uuid "{U()}"))')
        if title:
            self.text(title, x1 + 1.27, y1 + 3.81, 2.0, True)

    # ------------------------------------------------------------------ finish
    def finish(self):
        # every pin with a net must have been handled
        missing = []
        placed = {}
        for (ref, unit) in self.pos:
            placed.setdefault(ref, set()).add(unit)
        for ref, units in placed.items():
            umap = S.UNITS.get(BY_REF[ref]["sym"], {})
            for num, net in BY_REF[ref]["nets"].items():
                if umap.get(num, 1) in units and (ref, num) not in self.wired:
                    if net is None:
                        self.NC(f"{ref}.{num}")
                    else:
                        missing.append(f"{ref}.{num}={net}")
        unplaced = [r for r in BY_REF if r not in placed] + \
                   [f"{r} unit {k}" for r, us in placed.items() for k in set(S.UNITS.get(BY_REF[r]["sym"], {1: 1}).values()) - us]
        pins = set()
        for ref, units in placed.items():
            umap = S.UNITS.get(BY_REF[ref]["sym"], {})
            for num in S.symbols[BY_REF[ref]["sym"]][1]:
                if umap.get(num, 1) in units:
                    pins.add(self.pin(ref, num)[0])
        # split segments at interior connection points
        pts = set(pins) | set(self.attach)
        for a, b in self.segs:
            pts.add(a); pts.add(b)
        out = []
        for a, b in self.segs:
            inner = [p for p in pts if p != a and p != b and _on(p, a, b)]
            chain = [a] + sorted(inner, key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1])) + [b]
            out += list(zip(chain, chain[1:]))
        # merge exact duplicates and detect collinear overlaps (a drawing error)
        seen, segs = set(), []
        for a, b in out:
            k = tuple(sorted((a, b)))
            if k not in seen:
                seen.add(k); segs.append(k)
        overlaps = [(s, t) for i, s in enumerate(segs) for t in segs[i + 1:] if _overlap(s, t)]
        deg = {}
        for a, b in segs:
            deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
        for p in pins | set(self.attach):
            if p in deg:
                deg[p] += 1
        for a, b in segs:
            self.items.append(f'(wire (pts (xy {F(a[0])} {F(a[1])}) (xy {F(b[0])} {F(b[1])})) '
                              f'(stroke (width 0) (type default)) (uuid "{U()}"))')
        for p, d in deg.items():
            if d >= 3:
                self.items.append(f'(junction (at {F(p[0])} {F(p[1])}) (diameter 0) (color 0 0 0 0) (uuid "{U()}"))')
        return missing, unplaced, overlaps

    def write(self, path, title, rev, date, paper="A2"):
        lib_txt = "\n".join(s for s, _ in S.symbols.values())
        sch = (f'(kicad_sch (version 20231120) (generator "gen_schematic.py") (generator_version "9.0")\n'
               f'  (uuid "{ROOT}")\n  (paper "{paper}")\n'
               f'  (title_block (title "{title}") (date "{date}") (rev "{rev}") (company "Kemere lab (kbest)"))\n'
               f'  (lib_symbols\n{lib_txt}\n  )\n  ' + "\n  ".join(self.items) +
               f'\n  (sheet_instances (path "/" (page "1")))\n)\n')
        open(path, "w").write(sch)
        # project symbol library identical to the embedded copies, so ERC's library checks pass
        lib = "\n".join(s.replace(f'(symbol "{S.LIB}:', '(symbol "', 1) for s, _ in S.symbols.values())
        open(f"{S.LIB}.kicad_sym", "w").write(f'(kicad_symbol_lib (version 20231120) (generator "gen_schematic.py") '
                                              f'(generator_version "9.0")\n{lib}\n)\n')
        open("sym-lib-table", "w").write(f'(sym_lib_table\n  (version 7)\n  (lib (name "{S.LIB}")(type "KiCad")'
                                        f'(uri "${{KIPRJMOD}}/{S.LIB}.kicad_sym")(options "")(descr "kbest project symbols"))\n)\n')
        return len(sch)


def _on(p, a, b):
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) < p[1] < max(a[1], b[1])
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0])
    return False


def _overlap(s, t):
    (a, b), (c, d) = s, t
    if a[0] == b[0] == c[0] == d[0]:
        lo, hi = sorted((a[1], b[1])); lo2, hi2 = sorted((c[1], d[1]))
        return min(hi, hi2) - max(lo, lo2) > 1e-6
    if a[1] == b[1] == c[1] == d[1]:
        lo, hi = sorted((a[0], b[0])); lo2, hi2 = sorted((c[0], d[0]))
        return min(hi, hi2) - max(lo, lo2) > 1e-6
    return False
