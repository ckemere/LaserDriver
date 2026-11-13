#!/usr/bin/env python3
"""Geometric clean-up of hand-routed tracks (KiCad bundled Python).

    $KICAD_PY tools/track_tidy.py board.kicad_pcb [--dry-run]

0. Tiny dead-end spurs (< 0.12 mm) are deleted.
1. Header crossings: B.Cu verticals that pass between two pads of a J1 row are moved onto the
   exact 2.54 mm midline.  The run from the adjacent outer-row pad becomes one 45-degree segment
   from the pad centre; the far end slides along its neighbouring segment so no angle changes.
2. Via jags: a short end segment that turns just before a via is removed, and the via moves onto
   the incoming track's line (and, when the other layer also arrives at it, onto that line too).
3. Pad jags: a short end segment that enters a pad at an angle is removed when the incoming
   track's own line already passes through the pad; the track then ends straight in the pad.
   Straight stubs out of a pad (along its long axis) are left alone.
4. Tiny segments (< 0.12 mm) are collapsed onto the intersection of their neighbours' lines.

Every edit keeps each surviving segment's direction, and is a transaction: the touched copper is
checked against all other-net copper (board clearance) and drilled holes (hole clearance); an edit
that would violate either is rolled back and reported.  Run DRC afterwards all the same.
"""
import math
import sys

import pcbnew

T, MM = pcbnew.ToMM, pcbnew.FromMM
TOL = 1e-3
SHORT, TINY, MAX_VIA_MOVE = 0.6, 0.12, 0.8
CLEAR, HOLE_CLEAR = 0.15, 0.25


def pt(v):
    return (T(v.x), T(v.y))


def vec(p):
    return pcbnew.VECTOR2I(MM(p[0]), MM(p[1]))


def same(a, b, tol=TOL):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def uid(t):
    return t.m_Uuid.AsString()


def intersect(p1, p2, q1, q2):
    """Intersection of infinite lines p1p2 and q1q2 (None when parallel)."""
    d = (p2[0] - p1[0]) * (q2[1] - q1[1]) - (p2[1] - p1[1]) * (q2[0] - q1[0])
    if abs(d) < 1e-9:
        return None
    t = ((q1[0] - p1[0]) * (q2[1] - q1[1]) - (q1[1] - p1[1]) * (q2[0] - q1[0])) / d
    return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))


def project(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)
    return (ax + t * dx, ay + t * dy), t


def direction(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360


class Board:
    def __init__(self, path):
        self.path = path
        self.b = pcbnew.LoadBoard(path)
        self.dead = {}
        self.log = []
        self.pads = [p for f in self.b.GetFootprints() for p in f.Pads()]
        self.undo = None

    # ── queries ──
    def tracks(self):
        return [t for t in self.b.GetTracks() if t.GetClass() == 'PCB_TRACK' and uid(t) not in self.dead]

    def vias(self):
        return [t for t in self.b.GetTracks() if t.GetClass() == 'PCB_VIA']

    def at(self, layer, p, net=None):
        """[(track, end)] with an endpoint at p on layer; end is 0 (start) or 1 (end)."""
        out = []
        for t in self.tracks():
            if t.GetLayer() != layer or (net and t.GetNetname() != net):
                continue
            if same(pt(t.GetStart()), p):
                out.append((t, 0))
            elif same(pt(t.GetEnd()), p):
                out.append((t, 1))
        return out

    def via_at(self, p):
        return next((v for v in self.vias() if same(pt(v.GetPosition()), p)), None)

    def pad_at(self, t, p):
        for pad in self.pads:
            if pad.GetNetname() == t.GetNetname() and pad.IsOnLayer(t.GetLayer()) and pad.HitTest(vec(p)):
                return pad
        return None

    @staticmethod
    def ends(t):
        return pt(t.GetStart()), pt(t.GetEnd())

    @staticmethod
    def far(t, e):
        return pt(t.GetEnd()) if e == 0 else pt(t.GetStart())

    # ── transactional edits ──
    def begin(self):
        self.undo, self.touched = [], {}

    def set_end(self, t, e, p):
        cur = t.GetStart() if e == 0 else t.GetEnd()
        old = pcbnew.VECTOR2I(cur.x, cur.y)                  # a copy: GetStart() is a live reference
        self.undo.append(lambda t=t, e=e, old=old: (t.SetStart if e == 0 else t.SetEnd)(old))
        (t.SetStart if e == 0 else t.SetEnd)(vec(p))
        self.touched[uid(t)] = t

    def move_via(self, v, p):
        cur = v.GetPosition()
        old = pcbnew.VECTOR2I(cur.x, cur.y)
        self.undo.append(lambda v=v, old=old: v.SetPosition(old))
        v.SetPosition(vec(p))
        self.touched[uid(v)] = v

    def kill(self, t):
        self.dead[uid(t)] = t
        self.undo.append(lambda k=uid(t): self.dead.pop(k, None))

    def add_track(self, like, a, b):
        seg = pcbnew.PCB_TRACK(self.b)
        seg.SetStart(vec(a))
        seg.SetEnd(vec(b))
        seg.SetWidth(like.GetWidth())
        seg.SetLayer(like.GetLayer())
        seg.SetNet(like.GetNet())
        self.b.Add(seg)
        self.undo.append(lambda s=seg: self.b.Remove(s))
        self.touched[uid(seg)] = seg
        return seg

    def violations(self):
        others = [t for t in self.b.GetTracks() if uid(t) not in self.dead] + self.pads
        holes = [o for o in self.pads + self.vias() if o.HasHole()] if hasattr(self.pads[0], 'HasHole') else \
            [o for o in self.pads if T(o.GetDrillSize().x) > 0] + self.vias()
        bad = []
        for t in self.touched.values():
            if uid(t) in self.dead:
                continue
            layers = [pcbnew.F_Cu, pcbnew.B_Cu] if t.GetClass() == 'PCB_VIA' else [t.GetLayer()]
            for layer in layers:
                s = t.GetEffectiveShape(layer)
                for o in others:
                    if o.GetNetCode() == t.GetNetCode() or uid(o) == uid(t) or not o.IsOnLayer(layer):
                        continue
                    if s.Collide(o.GetEffectiveShape(layer), MM(CLEAR) - 1):
                        bad.append(o)
                for o in holes:
                    if uid(o) == uid(t) or (o.GetNetCode() == t.GetNetCode() and o.GetNetCode() > 0):
                        continue
                    if s.Collide(o.GetEffectiveHoleShape(), MM(HOLE_CLEAR) - 1):
                        bad.append(o)
        return bad

    def commit(self, msg):
        bad = self.violations()
        if bad:
            for f in reversed(self.undo):
                f()
            o = bad[0]
            who = (o.GetParentFootprint().GetReference() + '.' + o.GetNumber()) if o.GetClass() == 'PAD' \
                else f'{o.GetClass().lower()} {o.GetNetname()}'
            self.log.append(f'SKIPPED {msg}: would crowd {who}')
            self.undo = None
            return False
        self.log.append(msg)
        self.undo = None
        return True

    def save(self):
        for t in list(self.b.GetTracks()):
            if uid(t) in self.dead:
                self.b.Remove(t)
        pcbnew.ZONE_FILLER(self.b).Fill(self.b.Zones())
        pcbnew.SaveBoard(self.path, self.b)


# ── 0. tiny dead-end spurs ───────────────────────────────────────────────────
def spurs(B):
    for t in B.tracks():
        a, b = B.ends(t)
        if math.dist(a, b) >= TINY:
            continue
        for p in (a, b):
            if not [u for u, _ in B.at(t.GetLayer(), p) if uid(u) != uid(t)] and not B.via_at(p) \
                    and not B.pad_at(t, p):
                B.begin()
                B.kill(t)
                B.commit(f'spur {t.GetNetname()}: removed dangling {math.dist(a, b):.3f} mm stub at {p}')
                break


# ── 1. header crossings ──────────────────────────────────────────────────────
def header(B):
    j1 = next(f for f in B.b.GetFootprints() if f.GetReference() == 'J1')
    pads = [p for p in j1.Pads() if p.GetNumber().isdigit()]
    xs = sorted({round(pt(p.GetPosition())[0], 4) for p in pads})
    rows = sorted({round(pt(p.GetPosition())[1], 4) for p in pads})
    pitch = xs[1] - xs[0]
    mids = [(a + b) / 2 for a, b in zip(xs, xs[1:])]
    inner = rows[1]
    for t in B.tracks():
        if t.GetLayer() != pcbnew.B_Cu or uid(t) in B.dead:
            continue
        a, b = B.ends(t)
        if abs(a[0] - b[0]) > TOL or not (min(a[1], b[1]) < inner < max(a[1], b[1])):
            continue
        xm = min(mids, key=lambda m: abs(m - a[0]))
        if abs(xm - a[0]) > 0.3:
            B.log.append(f'header: {t.GetNetname()} at x {a[0]:.3f} is too far from a midline, skipped')
            continue
        net, x0 = t.GetNetname(), a[0]
        top, bot = (a, b) if a[1] < b[1] else (b, a)
        B.begin()
        # top: the chain back to an outer-row pad
        chain, cur, prev, pad = [], top, t, None
        for _ in range(4):
            nb = [(u, e) for u, e in B.at(pcbnew.B_Cu, cur, net) if uid(u) != uid(prev)]
            if len(nb) != 1:
                break
            u, e = nb[0]
            chain.append(u)
            cur, prev = B.far(u, e), u
            pad = next((p for p in pads if p.GetNetname() == net and same(pt(p.GetPosition()), cur, 0.01)), None)
            if pad:
                break
        if not pad or abs(abs(xm - pt(pad.GetPosition())[0]) - pitch / 2) > 0.01:
            B.log.append(f'header: {net} vertical at x {x0:.3f}: no adjacent outer-row pad above, skipped')
            continue
        pc = pt(pad.GetPosition())
        new_top = (xm, pc[1] + abs(xm - pc[0]))
        # bottom: absorb collinear vertical pieces, then slide along the next segment (or move the via)
        while True:
            nb = [(u, e) for u, e in B.at(pcbnew.B_Cu, bot, net) if uid(u) != uid(t)]
            if len(nb) == 1 and not B.via_at(bot) and abs(B.far(*nb[0])[0] - x0) < TOL:
                B.kill(nb[0][0])
                bot = B.far(*nb[0])
                continue
            break
        via = B.via_at(bot)
        if via:
            fb = B.at(pcbnew.F_Cu, bot, net)
            new_bot = (xm, bot[1])
            if len(fb) == 1:
                new_bot = intersect(bot, B.far(*fb[0]), (xm, 0), (xm, 1)) or new_bot
                B.set_end(fb[0][0], fb[0][1], new_bot)
            B.move_via(via, new_bot)
        elif len(nb) == 1:
            new_bot = intersect(bot, B.far(*nb[0]), (xm, 0), (xm, 1))
        else:
            new_bot = None
        if new_bot is None:
            for f in reversed(B.undo):
                f()
            B.log.append(f'header: {net}: no clean way to slide the bottom end, skipped')
            continue
        for u, e in nb:
            B.set_end(u, e, new_bot)
        like = chain[0]
        for u in chain:
            B.kill(u)
        B.add_track(like, pc, new_top)
        B.set_end(t, 0, new_top)
        B.set_end(t, 1, new_bot)
        B.commit(f'header: {net} x {x0:.3f} -> {xm:.3f} (J1.{pad.GetNumber()} 45 deg to y {new_top[1]:.2f})')


# ── 2./3. jags at vias and pads ─────────────────────────────────────────────
def jags(B):
    for t in list(B.tracks()):
        if uid(t) in B.dead:
            continue
        a, b = B.ends(t)
        L = math.dist(a, b)
        if L >= SHORT or L < TINY:
            continue
        for e, p in ((0, a), (1, b)):
            o = b if e == 0 else a                                   # inner joint
            nb = [(u, k) for u, k in B.at(t.GetLayer(), o, t.GetNetname()) if uid(u) != uid(t)]
            if len(nb) != 1:
                continue
            u, k = nb[0]
            q = B.far(u, k)
            turn = (direction(q, o) - direction(o, p) + 540) % 360 - 180
            if abs(turn) < 1:
                continue
            via = B.via_at(p)
            if via:
                if len(B.at(t.GetLayer(), p)) != 1:
                    continue
                other = pcbnew.B_Cu if t.GetLayer() == pcbnew.F_Cu else pcbnew.F_Cu
                ob = B.at(other, p, t.GetNetname())
                if len(ob) > 1:
                    B.log.append(f'via jag {t.GetNetname()} at {p}: {len(ob)} tracks on the other layer, left as is')
                    break
                np_ = None
                if ob:
                    np_ = intersect(q, o, p, B.far(*ob[0]))
                np_ = np_ or project(p, q, o)[0]
                if math.dist(np_, p) > MAX_VIA_MOVE or project(np_, q, o)[1] < 0.2:
                    B.log.append(f'via jag {t.GetNetname()} at {p}: fix would move the via '
                                 f'{math.dist(np_, p):.2f} mm, left as is')
                    break
                B.begin()
                B.move_via(via, np_)
                if ob:
                    B.set_end(ob[0][0], ob[0][1], np_)
                B.set_end(u, k, np_)
                B.kill(t)
                B.commit(f'via jag {t.GetNetname()}: via ({p[0]:.3f}, {p[1]:.3f}) -> ({np_[0]:.3f}, {np_[1]:.3f})')
                break
            pad = B.pad_at(t, p)
            if pad:
                sz = pad.GetSize()
                sx, sy = T(sz.x), T(sz.y)
                ang = pad.GetOrientation().AsDegrees() % 180
                long_axis = 0 if (sx >= sy) == (abs(ang - 90) > 45) else 90
                d = direction(o, p) % 180
                if min(abs(d - long_axis), 180 - abs(d - long_axis)) < 1:
                    continue                                          # a straight stub out of the pad
                name = f'{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}'
                np_, s = project(pt(pad.GetPosition()), q, o)
                if s < 0.2 or not pad.HitTest(vec(np_)):
                    B.log.append(f'pad jag {t.GetNetname()} at {name}: incoming line misses the pad, left as is')
                    break
                B.begin()
                B.set_end(u, k, np_)
                B.kill(t)
                B.commit(f'pad jag {t.GetNetname()}: now enters {name} straight')
                break


# ── 4. tiny segments ─────────────────────────────────────────────────────────
def tiny(B):
    for t in list(B.tracks()):
        if uid(t) in B.dead:
            continue
        a, b = B.ends(t)
        if math.dist(a, b) >= TINY:
            continue
        na = [(u, k) for u, k in B.at(t.GetLayer(), a, t.GetNetname()) if uid(u) != uid(t)]
        nb = [(u, k) for u, k in B.at(t.GetLayer(), b, t.GetNetname()) if uid(u) != uid(t)]
        fixed = [p for p in (a, b) if B.via_at(p) or B.pad_at(t, p)]
        if fixed:
            p = fixed[0]
            movers = nb if p == a else na
            other = b if p == a else a
            if all(abs(((direction(B.far(u, k), other) - direction(B.far(u, k), p) + 540) % 360) - 180) < 3
                   for u, k in movers):
                B.begin()
                for u, k in movers:
                    B.set_end(u, k, p)
                B.kill(t)
                B.commit(f'tiny {t.GetNetname()}: merged into ({p[0]:.3f}, {p[1]:.3f})')
            else:
                B.log.append(f'tiny {t.GetNetname()} at {a}: would bend a neighbour, left as is')
            continue
        if len(na) != 1 or len(nb) != 1:
            B.log.append(f'tiny {t.GetNetname()} at {a}: branch point, left as is')
            continue
        c = intersect(B.far(*na[0]), a, B.far(*nb[0]), b)
        if c is None or math.dist(c, a) > 0.3:
            B.log.append(f'tiny {t.GetNetname()} at {a}: neighbours are parallel (a 0.05 mm jog), left as is')
            continue
        B.begin()
        B.set_end(na[0][0], na[0][1], c)
        B.set_end(nb[0][0], nb[0][1], c)
        B.kill(t)
        B.commit(f'tiny {t.GetNetname()}: collapsed at ({c[0]:.3f}, {c[1]:.3f})')


if __name__ == '__main__':
    B = Board(sys.argv[1])
    spurs(B)
    header(B)
    jags(B)
    tiny(B)
    print('\n'.join(B.log))
    print(f'{len(B.dead)} segments removed; {sum(l.startswith("SKIPPED") for l in B.log)} edits rolled back')
    if '--dry-run' not in sys.argv:
        B.save()
        print('saved', sys.argv[1])
