"""Helpers for scripted, minimal edits of hand-drawn KiCad 9 schematics (kiutils 1.4.8).

Coordinates: library symbols are Y-up, schematics are Y-down.  A symbol placed
at (sx, sy, rot) with optional mirror maps a lib pin at (px, py) to
    v = (px, -py) -> mirror -> rotate(-rot)  -> + (sx, sy)
which matches eeschema's transform (rotation is counter-clockwise on screen).
"""
import copy
import math
import os
import uuid as _uuid

from kiutils.schematic import Schematic
from kiutils.symbol import SymbolLib
from kiutils.items.schitems import (
    SchematicSymbol, Connection, Junction, GlobalLabel, LocalLabel,
    NoConnect, SymbolProjectInstance, SymbolProjectPath,
)
from kiutils.items.common import Position, Property, Effects, Font, Justify

KICAD_SYM_DIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
STUB = 5.08
PASSIVES = {"Device:R", "Device:C", "Device:L", "Device:R_Small", "Device:C_Small"}


def uid():
    return str(_uuid.uuid4())


def eff(hide=False, justify=None):
    e = Effects(font=Font(height=1.27, width=1.27))
    e.hide = hide
    if justify:
        e.justify = Justify(horizontally=justify)
    return e


# ── library symbols ─────────────────────────────────────────────────────────
_libcache = {}


PROJECT_LIBS = {   # project symbol libraries (sym-lib-table nickname -> file)
    "LaserHAT": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "LaserHAT.kicad_sym"),
}


def _load_lib(nick):
    if nick not in _libcache:
        path = PROJECT_LIBS.get(nick) or os.path.join(KICAD_SYM_DIR, nick + ".kicad_sym")
        _libcache[nick] = SymbolLib.from_file(path)
    return _libcache[nick]


def lib_symbol(lib_id):
    """Return a flattened copy of a library symbol, named lib_id (Nick:Name)."""
    nick, name = lib_id.split(":")
    lib = _load_lib(nick)
    sym = next(s for s in lib.symbols if s.entryName == name)
    sym = copy.deepcopy(sym)
    if sym.extends:
        parent = copy.deepcopy(next(s for s in lib.symbols if s.entryName == sym.extends))
        props = {p.key: p for p in sym.properties}
        for p in parent.properties:
            if p.key in props:
                p.value = props[p.key].value
        parent.properties = [p for p in parent.properties]
        for u in parent.units:
            u.entryName = name
        parent.entryName = name
        sym = parent
        sym.extends = None
    sym.libraryNickname = nick
    for u in sym.units:
        u.entryName = name
    for u in sym.units:
        for pin in u.pins:
            if pin.position.angle is None:
                pin.position.angle = 0
    if lib_id in PASSIVES:
        sym.pinNames = True
        sym.pinNamesHide = True
        sym.hidePinNumbers = True
    return sym


def ensure_lib_symbol(sch, lib_id):
    for ls in sch.libSymbols:
        if ls.libId == lib_id:
            return ls
    ls = lib_symbol(lib_id)
    sch.libSymbols.append(ls)
    return ls


def get_lib_symbol(sch, lib_id):
    return next(ls for ls in sch.libSymbols if ls.libId == lib_id)


# ── geometry ────────────────────────────────────────────────────────────────
def _xform(sym, px, py):
    x, y = px, -py
    if sym.mirror == "x":
        y = -y
    elif sym.mirror == "y":
        x = -x
    a = math.radians(sym.position.angle or 0)
    c, s = math.cos(a), math.sin(a)
    gx = sym.position.X + x * c + y * s
    gy = sym.position.Y - x * s + y * c
    return round(gx, 3), round(gy, 3)


def _pin_dir(sym, pin_angle):
    """Unit vector (screen coords) pointing from the pin tip into the body."""
    a = math.radians(pin_angle)
    return _xform_vec(sym, math.cos(a), math.sin(a))


def _xform_vec(sym, vx, vy):
    x, y = vx, -vy
    if sym.mirror == "x":
        y = -y
    elif sym.mirror == "y":
        x = -x
    a = math.radians(sym.position.angle or 0)
    c, s = math.cos(a), math.sin(a)
    return round(x * c + y * s, 6), round(-x * s + y * c, 6)


def sym_pins(sch, sym):
    """{pin_number: (x, y, (dx, dy))} where (dx,dy) points from tip into body."""
    ls = get_lib_symbol(sch, getattr(sym, "libName", None) or sym.libId)
    out = {}
    for u in ls.units:
        if u.unitId not in (0, sym.unit):
            continue
        for p in u.pins:
            x, y = _xform(sym, p.position.X, p.position.Y)
            out[p.number] = (x, y, _pin_dir(sym, p.position.angle or 0))
    return out


def find_sym(sch, ref):
    for s in sch.schematicSymbols:
        for p in s.properties:
            if p.key == "Reference" and p.value == ref:
                return s
    raise KeyError(ref)


def ref_of(sym):
    return next(p.value for p in sym.properties if p.key == "Reference")


# ── adding things ───────────────────────────────────────────────────────────
def add_symbol(sch, lib_id, ref, value, x, y, angle=0, footprint="", mirror=None,
               project="LaserDriver", sheet_path="/", unit=1, fields=None):
    ls = ensure_lib_symbol(sch, lib_id)
    s = SchematicSymbol()
    s.libraryNickname, s.entryName = lib_id.split(":")
    s.position = Position(X=x, Y=y, angle=angle)
    s.unit = unit
    s.inBom = True
    s.onBoard = True
    # Stable across re-runs: KiCad links each PCB footprint to its symbol by this UUID, so a
    # fresh random one on every run makes "Update PCB from Schematic" replace the footprint.
    s.uuid = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"laserhat:{sheet_path}:{ref}:{unit}"))
    s.mirror = mirror
    s.fieldsAutoplaced = True
    rp = Property(key="Reference", value=ref, id=0, effects=eff(),
                  position=Position(X=round(x + 2.54, 3), Y=round(y - 2.54, 3), angle=0))
    vp = Property(key="Value", value=value, id=1, effects=eff(),
                  position=Position(X=round(x + 2.54, 3), Y=round(y + 2.54, 3), angle=0))
    fp = Property(key="Footprint", value=footprint, id=2, effects=eff(hide=True),
                  position=Position(X=x, Y=y, angle=0))
    ds = Property(key="Datasheet", value="", id=3, effects=eff(hide=True),
                  position=Position(X=x, Y=y, angle=0))
    s.properties = [rp, vp, fp, ds]
    for k, v in (fields or {}).items():
        s.properties.append(Property(key=k, value=v, effects=eff(hide=True),
                                     position=Position(X=x, Y=y, angle=0)))
    s.pins = {}
    for u in ls.units:
        for p in u.pins:
            if u.unitId in (0, unit):
                s.pins[p.number] = uid()
    s.instances = [SymbolProjectInstance(name=project, paths=[
        SymbolProjectPath(sheetInstancePath=sheet_path, reference=ref, unit=unit)])]
    sch.schematicSymbols.append(s)
    return s


def wire(sch, x1, y1, x2, y2):
    c = Connection(type="wire", points=[Position(X=round(x1, 3), Y=round(y1, 3)),
                                        Position(X=round(x2, 3), Y=round(y2, 3))], uuid=uid())
    sch.graphicalItems.append(c)
    return c


def junction(sch, x, y):
    sch.junctions.append(Junction(position=Position(X=x, Y=y), diameter=0, uuid=uid()))


def no_connect(sch, x, y):
    sch.noConnects.append(NoConnect(position=Position(X=x, Y=y), uuid=uid()))


def _label_angle(dx, dy):
    # label points away from body: body direction is (dx,dy); away = -(dx,dy)
    ax, ay = -dx, -dy
    if abs(ax) > abs(ay):
        return 0 if ax > 0 else 180
    return 270 if ay > 0 else 90


def label(sch, name, x, y, angle, kind="global", shape="bidirectional"):
    just = "right" if angle in (180, 270) else "left"
    if kind == "global":
        lb = GlobalLabel(text=name, shape=shape, position=Position(X=x, Y=y, angle=angle),
                         effects=eff(justify=just), uuid=uid(), fieldsAutoplaced=True)
        lb.properties = [Property(key="Intersheetrefs", value="${INTERSHEET_REFS}", id=0,
                                  effects=eff(hide=True), position=Position(X=x, Y=y, angle=0))]
        sch.globalLabels.append(lb)
    else:
        lb = LocalLabel(text=name, position=Position(X=x, Y=y, angle=angle),
                        effects=eff(justify=just), uuid=uid(), fieldsAutoplaced=True)
        sch.labels.append(lb)
    return lb


def stub_label(sch, sym, pin, name, kind="global", shape="bidirectional", length=STUB):
    """Rule 2: wire stub of `length` leaving the pin, then a label at the far end."""
    x, y, (dx, dy) = sym_pins(sch, sym)[pin]
    ex, ey = round(x - length * dx, 3), round(y - length * dy, 3)
    wire(sch, x, y, ex, ey)
    return label(sch, name, ex, ey, _label_angle(dx, dy), kind=kind, shape=shape)


def stub_power(sch, sym, pin, power_id, value=None, length=STUB, project="LaserDriver",
               sheet_path="/"):
    """Wire stub from pin to a power symbol (power:GND / power:+5V ...), body pointing away."""
    x, y, (dx, dy) = sym_pins(sch, sym)[pin]
    ex, ey = round(x - length * dx, 3), round(y - length * dy, 3)
    wire(sch, x, y, ex, ey)
    return power_symbol(sch, power_id, ex, ey, value=value, away=(-dx, -dy),
                        project=project, sheet_path=sheet_path)


_pwr_n = [900]


def power_symbol(sch, power_id, x, y, value=None, away=None, project="LaserDriver",
                 sheet_path="/"):
    """Place a power symbol.  `away` = screen direction the symbol body should extend."""
    value = value or power_id.split(":")[1]
    gnd = "GND" in power_id
    angle = 0
    if away is not None:
        body = (0, -1) if gnd else (0, 1)     # lib (y-up) body direction
        for a in (0, 90, 180, 270):
            class _S:  # minimal stand-in for _xform_vec
                mirror = None
                position = Position(X=0, Y=0, angle=a)
            v = _xform_vec(_S, *body)
            if round(v[0]) == round(away[0]) and round(v[1]) == round(away[1]):
                angle = a
                break
    _pwr_n[0] += 1
    s = add_symbol(sch, power_id, "#PWR%04d" % _pwr_n[0], value, x, y, angle=angle,
                   project=project, sheet_path=sheet_path)
    s.inBom = False
    s.properties[0].effects.hide = True
    return s


def remove_symbol(sch, ref):
    s = find_sym(sch, ref)
    sch.schematicSymbols.remove(s)
    return s


# ── connectivity tracing (wires + labels, single sheet) ────────────────────
def _on_seg(p, a, b, tol=1e-3):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > tol:
        return False
    return min(ax, bx) - tol <= px <= max(ax, bx) + tol and min(ay, by) - tol <= py <= max(ay, by) + tol


def wires(sch):
    return [w for w in sch.graphicalItems if getattr(w, "type", "") == "wire"]


def trace(sch, x, y):
    """Return (wire_list, label_list) electrically reachable from point (x,y) through wires."""
    ws = wires(sch)
    segs = [((w.points[0].X, w.points[0].Y), (w.points[1].X, w.points[1].Y)) for w in ws]
    seen, todo = set(), [(x, y)]
    pts_seen = set()
    while todo:
        p = todo.pop()
        key = (round(p[0], 3), round(p[1], 3))
        if key in pts_seen:
            continue
        pts_seen.add(key)
        for i, (a, b) in enumerate(segs):
            if i in seen:
                continue
            if _on_seg(p, a, b) or _on_seg(a, p, p) or _on_seg(b, p, p):
                seen.add(i)
                todo += [a, b]
    wl = [ws[i] for i in seen]
    labs = []
    for lb in sch.labels + sch.globalLabels + sch.hierarchicalLabels:
        lp = (lb.position.X, lb.position.Y)
        if (abs(lp[0] - x) < 1e-3 and abs(lp[1] - y) < 1e-3) or any(_on_seg(lp, *segs[i]) for i in seen):
            labs.append(lb)
    return wl, labs


# ── cleanup ────────────────────────────────────────────────────────────────
def _anchor_points(sch):
    """Points that terminate a wire legitimately: pins, labels, sheet pins, no-connects."""
    pts = set()
    for s in sch.schematicSymbols:
        try:
            for (x, y, _d) in sym_pins(sch, s).values():
                pts.add((round(x, 2), round(y, 2)))
        except StopIteration:
            pass
    for lb in sch.labels + sch.globalLabels + sch.hierarchicalLabels:
        pts.add((round(lb.position.X, 2), round(lb.position.Y, 2)))
    for sh in sch.sheets:
        for p in sh.pins:
            pts.add((round(p.position.X, 2), round(p.position.Y, 2)))
    for nc in sch.noConnects:
        pts.add((round(nc.position.X, 2), round(nc.position.Y, 2)))
    return pts


def prune(sch, remove_power=True):
    """Iteratively remove dangling wires, orphan power symbols and useless junctions."""
    while True:
        changed = False
        anchors = _anchor_points(sch)
        ws = wires(sch)
        for w in list(ws):
            others = [o for o in ws if o is not w]
            for p in w.points:
                key = (round(p.X, 2), round(p.Y, 2))
                if key in anchors:
                    continue
                if any(_on_seg((p.X, p.Y), (o.points[0].X, o.points[0].Y),
                               (o.points[1].X, o.points[1].Y)) for o in others):
                    continue
                # A label part-way along the wire keeps it: shorten to the nearest one.
                a, b = w.points[0], w.points[1]
                on = [lb for lb in sch.labels + sch.globalLabels + sch.hierarchicalLabels
                      if _on_seg((lb.position.X, lb.position.Y), (a.X, a.Y), (b.X, b.Y))]
                if on:
                    lb = min(on, key=lambda l: (l.position.X - p.X) ** 2 + (l.position.Y - p.Y) ** 2)
                    p.X, p.Y = lb.position.X, lb.position.Y
                    changed = True
                    break
                sch.graphicalItems.remove(w)
                ws.remove(w)
                changed = True
                break
        if remove_power:
            ends = []
            for w in wires(sch):
                ends += [(w.points[0].X, w.points[0].Y), (w.points[1].X, w.points[1].Y)]
            segs = [((w.points[0].X, w.points[0].Y), (w.points[1].X, w.points[1].Y)) for w in wires(sch)]
            pinpts = {}
            for s in sch.schematicSymbols:
                if s.libId.startswith("power:"):
                    continue
                for (x, y, _d) in sym_pins(sch, s).values():
                    pinpts[(round(x, 2), round(y, 2))] = True
            for s in list(sch.schematicSymbols):
                if not s.libId.startswith("power:"):
                    continue
                (x, y, _d), = sym_pins(sch, s).values()
                if (round(x, 2), round(y, 2)) in pinpts:
                    continue
                if any(_on_seg((x, y), a, b) for a, b in segs):
                    continue
                sch.schematicSymbols.remove(s)
                changed = True
        if not changed:
            break
    # junctions need >=3 wire ends / pass-throughs
    segs = [((w.points[0].X, w.points[0].Y), (w.points[1].X, w.points[1].Y)) for w in wires(sch)]
    for j in list(sch.junctions):
        p = (j.position.X, j.position.Y)
        n = 0
        for a, b in segs:
            if _on_seg(p, a, a) or _on_seg(p, b, b):
                n += 1
            elif _on_seg(p, a, b):
                n += 2
        if n < 3:
            sch.junctions.remove(j)


def relabel(sch, old_label, new_text, kind="global", shape="bidirectional"):
    """Replace a label object with one of a (possibly) different kind/name at the same spot."""
    x, y, a = old_label.position.X, old_label.position.Y, old_label.position.angle
    for coll in (sch.labels, sch.globalLabels, sch.hierarchicalLabels):
        if old_label in coll:
            coll.remove(old_label)
    return label(sch, new_text, x, y, a, kind=kind, shape=shape)


def set_value(sch, ref, value, footprint=None):
    s = find_sym(sch, ref)
    for p in s.properties:
        if p.key == "Value":
            p.value = value
        if footprint is not None and p.key == "Footprint":
            p.value = footprint
    return s
