#!/usr/bin/env python3
"""Place reference designators where they do not collide (KiCad bundled Python).

    $KICAD_PY tools/silk_tidy.py board.kicad_pcb [--keep REF,REF]

Every visible silkscreen reference is shrunk to the board's minimum silk text
height and tried at a ring of spots around its courtyard (above, below, left,
right, on the body, corners; horizontal, then vertical).  The first spot that
stays on the board, clears every pad, every other silk item and every
reference already placed, and sits clearly nearer its own part than any other
wins.  A reference with no free spot is hidden; the assembly (Fab) layer still
carries it.  --keep leaves hand-placed references untouched.
"""
import sys

import pcbnew

MM, TO = pcbnew.FromMM, pcbnew.ToMM
GAP = MM(0.15)


def ink(text):
    """bounding box of the stroked glyphs (GetBoundingBox adds ~0.2 mm margins)"""
    return text.GetEffectiveTextShape().BBox()


def main(path, keep=()):
    board = pcbnew.LoadBoard(path)
    ds = board.GetDesignSettings()
    h = max(ds.m_MinSilkTextHeight, MM(0.8))
    thick = max(ds.m_MinSilkTextThickness, MM(0.12))
    edge = board.GetBoardEdgesBoundingBox()
    edge.Inflate(-MM(0.3))
    fps = list(board.GetFootprints())

    def silk_of(f):
        return pcbnew.B_SilkS if f.IsFlipped() else pcbnew.F_SilkS

    # fixed obstacles per silk side: pads on that copper side, footprint art, board text
    obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    for f in fps:
        for p in f.Pads():
            for silk, cu in ((pcbnew.F_SilkS, pcbnew.F_Cu), (pcbnew.B_SilkS, pcbnew.B_Cu)):
                if p.IsOnLayer(cu):
                    obst[silk].append(p)
        for g in f.GraphicalItems():
            if g.GetLayer() in obst:
                obst[g.GetLayer()].append(g)
    for d in board.GetDrawings():
        if d.GetLayer() in obst:
            obst[d.GetLayer()].append(d)
    placed = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
    crt = {f.GetReference(): f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
           for f in fps}

    def box_dist(b, p):
        dx = max(b.GetX() - p.x, 0, p.x - b.GetRight())
        dy = max(b.GetY() - p.y, 0, p.y - b.GetBottom())
        return (dx * dx + dy * dy) ** 0.5

    def own(ref, box, layer):
        """the label must read as belonging to its own part: no other part on the
        same side is closer to the label's centre"""
        c = box.GetCenter()
        mine = box_dist(crt[ref], c)
        return all(box_dist(crt[f.GetReference()], c) >= 1.2 * mine for f in fps
                   if f.GetReference() != ref and silk_of(f) == layer and crt[f.GetReference()].GetWidth())

    def clear(box, layer):
        if not edge.Contains(box.GetOrigin()) or not edge.Contains(box.GetEnd()):
            return False
        big = pcbnew.BOX2I(box.GetOrigin(), box.GetSize())
        big.Inflate(GAP)
        for o in obst[layer]:
            if o.HitTest(big, False, 0):
                return False
        return not any(big.Intersects(b) for b in placed[layer])

    hidden, moved = [], 0
    # big parts first: they have the most room around them
    for f in sorted(fps, key=lambda f: -f.GetCourtyard(pcbnew.F_CrtYd if not f.IsFlipped()
                                                        else pcbnew.B_CrtYd).Area()):
        ref = f.Reference()
        layer = silk_of(f)
        if not ref.IsVisible() or ref.GetLayer() != layer:
            continue
        if f.GetReference() in keep:
            placed[layer].append(ink(ref))
            continue
        ref.SetTextSize(pcbnew.VECTOR2I(h, h))
        ref.SetTextThickness(thick)
        ref.SetKeepUpright(True)
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox()
        if cy.GetWidth() == 0:
            cy = f.GetBoundingBox(False)
        cx, cyy = cy.GetCenter().x, cy.GetCenter().y
        ok = False
        for angle in (0, 90):
            ref.SetTextAngleDegrees(angle)
            ref.SetPosition(pcbnew.VECTOR2I(cx, cyy))
            tb = ink(ref)
            w2, h2 = tb.GetWidth() // 2, tb.GetHeight() // 2
            top, bot = cy.GetY() - h2 - GAP, cy.GetBottom() + h2 + GAP
            lft, rgt = cy.GetX() - w2 - GAP, cy.GetRight() + w2 + GAP
            spots = [(cx, top), (cx, bot), (lft, cyy), (rgt, cyy), (cx, cyy),
                     (lft, top), (rgt, top), (lft, bot), (rgt, bot)]
            for x, y in spots:
                ref.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                box = ink(ref)
                if clear(box, layer) and own(f.GetReference(), box, layer):
                    placed[layer].append(box)
                    ok = True
                    break
            if ok:
                break
        if ok:
            moved += 1
        else:
            ref.SetVisible(False)
            hidden.append(f.GetReference())
    pcbnew.SaveBoard(path, board)
    print(f"silk: placed {moved} references, hid {len(hidden)}: {sorted(hidden)}")


if __name__ == "__main__":
    keep = ()
    if "--keep" in sys.argv:
        keep = set(sys.argv[sys.argv.index("--keep") + 1].split(","))
    main(sys.argv[1], keep)
