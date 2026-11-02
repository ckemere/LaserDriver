"""Surgical write-back of kiutils edits into an original KiCad 9 schematic.

kiutils 1.4.8 predates KiCad 9's `(hide yes)` syntax, so a full kiutils
round-trip un-hides every hidden field of a hand-edited sheet.  Instead we
diff the edited kiutils object against the original (by UUID) and splice only
the changes into the original text:

  * top-level items removed      -> their text span is deleted
  * top-level items added        -> serialised by kiutils and appended
  * symbols whose property values changed -> value strings replaced in place
  * sheets that lost pins        -> those (pin ...) spans are deleted
  * wires that changed           -> re-serialised (wires carry no hidden fields)
  * new lib symbols              -> appended inside (lib_symbols ...)
"""
import re


# ── minimal s-expression span parser ───────────────────────────────────────
class Node:
    __slots__ = ("start", "end", "children", "tokens")

    def __init__(self, start):
        self.start, self.end, self.children, self.tokens = start, None, [], []

    @property
    def head(self):
        return self.tokens[0][2] if self.tokens else None

    def child(self, head):
        return next((c for c in self.children if c.head == head), None)

    def uuid(self, text):
        c = self.child("uuid")
        return c.tokens[1][2].strip('"') if c and len(c.tokens) > 1 else None


def parse(text):
    root = Node(0)
    stack = [root]
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "(":
            node = Node(i)
            stack[-1].children.append(node)
            stack.append(node)
            i += 1
        elif ch == ")":
            stack[-1].end = i + 1
            stack.pop()
            i += 1
        elif ch == '"':
            j = i + 1
            while text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            stack[-1].tokens.append((i, j + 1, text[i:j + 1]))
            i = j + 1
        elif ch.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            stack[-1].tokens.append((i, j, text[i:j]))
            i = j
    return root.children[0]


# ── kiutils side ───────────────────────────────────────────────────────────
def _items(sch):
    """uuid -> (kind, kiutils object) for all top-level items with a uuid."""
    out = {}
    for s in sch.schematicSymbols:
        out[s.uuid] = ("symbol", s)
    for w in sch.graphicalItems:
        out[w.uuid] = ("wire" if getattr(w, "type", "") in ("wire", "bus") else "graphic", w)
    for lb in sch.labels:
        out[lb.uuid] = ("label", lb)
    for lb in sch.globalLabels:
        out[lb.uuid] = ("global_label", lb)
    for lb in sch.hierarchicalLabels:
        out[lb.uuid] = ("hierarchical_label", lb)
    for j in sch.junctions:
        out[j.uuid] = ("junction", j)
    for nc in sch.noConnects:
        out[nc.uuid] = ("no_connect", nc)
    for t in sch.texts:
        out[t.uuid] = ("text", t)
    for sh in sch.sheets:
        out[sh.uuid] = ("sheet", sh)
    return out


def _props(sym):
    return {p.key: p.value for p in sym.properties}


def _qs(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def patch(orig_text, orig_sch, new_sch):
    """Return orig_text with the differences orig_sch -> new_sch applied."""
    root = parse(orig_text)
    spans = {}
    for c in root.children:
        u = c.uuid(orig_text)
        if u:
            spans[u] = c
    old, new = _items(orig_sch), _items(new_sch)
    edits = []            # (start, end, replacement)
    appended = []

    for u, (kind, obj) in old.items():
        node = spans.get(u)
        if u not in new:
            if node is None:
                raise RuntimeError(f"cannot find span for removed {kind} {u}")
            # swallow the preceding indentation/newline too
            s = node.start
            while s > 0 and orig_text[s - 1] in " \t":
                s -= 1
            if s > 0 and orig_text[s - 1] == "\n":
                s -= 1
            edits.append((s, node.end, ""))
            continue
        nobj = new[u][1]
        if kind == "symbol":
            op, np_ = _props(obj), _props(nobj)
            for key, val in np_.items():
                if op.get(key) != val:
                    pnode = next(c for c in node.children
                                 if c.head == "property" and c.tokens[1][2] == _qs(key))
                    a, b, _ = pnode.tokens[2]
                    edits.append((a, b, _qs(val)))
        elif kind == "wire":
            if obj.to_sexpr(indent=1) != nobj.to_sexpr(indent=1):
                edits.append((node.start, node.end, nobj.to_sexpr(indent=0).strip()))
        elif kind == "sheet":
            keep = {p.uuid for p in nobj.pins}
            for c in node.children:
                if c.head == "pin" and c.uuid(orig_text) not in keep:
                    s = c.start
                    while orig_text[s - 1] in " \t":
                        s -= 1
                    if orig_text[s - 1] == "\n":
                        s -= 1
                    edits.append((s, c.end, ""))
            if len(nobj.pins) > len(node.children):
                raise RuntimeError("adding sheet pins is not supported")

    for u, (kind, obj) in new.items():
        if u not in old:
            appended.append(obj.to_sexpr(indent=2))

    # new lib symbols
    have = {ls.libId for ls in orig_sch.libSymbols}
    new_libs = [ls for ls in new_sch.libSymbols if ls.libId not in have]
    libnode = root.child("lib_symbols")
    if new_libs:
        ins = libnode.end - 1
        edits.append((ins, ins, "".join(ls.to_sexpr(indent=4) for ls in new_libs) + "  "))

    # append new items before (sheet_instances ...) / (embedded_fonts ...) or at the end
    anchor = root.child("sheet_instances") or root.child("embedded_fonts")
    pos = anchor.start if anchor else root.end - 1
    if appended:
        edits.append((pos, pos, "".join(appended) + "\t"))

    out = orig_text
    for a, b, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        out = out[:a] + rep + out[b:]
    return out
