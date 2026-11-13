#!/usr/bin/env python3
"""Drop duplicated silkscreen texts (same text, position and layer) from footprint blocks: TI's VQFN32_RHB footprint
carries its pin-1 '*' twice on F.SilkS, which prints as '**'.  Works on a .kicad_mod or on named footprints of a
.kicad_pcb (text edit; pcbnew segfaults on FOOTPRINT.Remove(graphic) in this build).
    python tools/silk_dedupe.py FILE [REF ...]"""
import re
import sys


def close(text, i):
    depth, q = 0, False
    while True:
        c = text[i]
        if c == '"' and text[i - 1] != "\\":
            q = not q
        elif not q:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1


def dedupe_block(block):
    out, seen, n, i = [], set(), 0, 0
    pat = re.compile(r"\n\t+\(fp_text\b")
    while True:
        m = pat.search(block, i)
        if not m:
            out.append(block[i:]); return "".join(out), n
        k = close(block, block.index("(", m.start()))
        item = block[m.start():k]
        out.append(block[i:m.start()])
        key = (re.search(r'\(fp_text user "([^"]*)"', item), re.search(r"\(at [^)]*\)", item), re.search(r'\(layer "[^"]*"\)', item))
        key = tuple(x.group(0) if x else None for x in key)
        if key[0] is not None and key in seen:
            n += 1
        else:
            seen.add(key); out.append(item)
        i = k


def run(path, refs):
    text = open(path).read()
    if path.endswith(".kicad_mod"):
        text, n = dedupe_block(text)
    else:
        out, n, i = [], 0, 0
        while True:
            j = text.find("\n\t(footprint ", i)
            if j < 0:
                out.append(text[i:]); break
            k = close(text, text.index("(", j))
            block = text[j:k]
            out.append(text[i:j])
            m = re.search(r'\(property "Reference" "([^"]+)"', block)
            if m and (not refs or m.group(1) in refs):
                block, d = dedupe_block(block); n += d
            out.append(block); i = k
        text = "".join(out)
    open(path, "w").write(text)
    print("removed", n, "duplicated silk texts from", path)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2:])
