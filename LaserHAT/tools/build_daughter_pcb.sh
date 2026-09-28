#!/bin/sh
# Rebuild the laser daughterboard PCB:  sh tools/build_daughter_pcb.sh [--route]
set -e
cd "$(dirname "$0")/.."
KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
KICAD_PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
FREEROUTING=/Applications/freerouting.app/Contents/MacOS/freerouting
TMP=${TMPDIR:-/tmp}/laserdaughter_build
mkdir -p "$TMP"
quiet() { grep -v -E "Fontconfig|assert|memory leak|Debug:" || true; }
B=LaserDaughter/LaserDaughter.kicad_pcb

git show a722d88:LaserHAT/LaserDriver.kicad_pcb > "$TMP/rev1.kicad_pcb"   # footprint source
$KICAD_PY tools/blank_board.py "$TMP/rev1.kicad_pcb" $B 2>&1 | quiet
micromamba run -n kicad python tools/make_daughter_pro.py
$KICAD_CLI sch export netlist --format kicadsexpr -o "$TMP/d.net" LaserDaughter/LaserDaughter.kicad_sch 2>&1 | quiet
$KICAD_PY tools/pcb_sync.py $B "$TMP/d.net" --src "$TMP/rev1.kicad_pcb" 2>&1 | quiet
$KICAD_PY tools/daughter_layout.py $B 2>&1 | quiet
$KICAD_PY tools/add_gnd_pour.py $B 2>&1 | quiet
$KICAD_PY tools/gnd_vias.py $B 2>&1 | quiet
$KICAD_PY tools/fill_zones.py $B 2>&1 | quiet
if [ "$1" = "--route" ]; then
    # deliberate routing: tools/grid_router.py with LaserDaughter/route_plan.json
    # (net order, widths, thin late branches, turn/via/bottom-layer costs; failed nets
    # are ripped up and promoted automatically).  Ground comes from the pours.
    : > "$TMP/empty.rpt"
    $KICAD_PY tools/maze_io.py export $B "$TMP/empty.rpt" "$TMP/board.json" 2>&1 | quiet
    micromamba run -n kicad python tools/grid_router.py "$TMP/board.json" LaserDaughter/route_plan.json "$TMP/routes.json"
    $KICAD_PY tools/maze_io.py import $B "$TMP/routes.json" 2>&1 | quiet
    $KICAD_PY tools/fill_zones.py $B 2>&1 | quiet
    # ground pads cut off from the main pour (none expected) get a maze-routed tie
    $KICAD_PY tools/gnd_islands.py $B "$TMP/islands.json" 2>&1 | quiet
    if [ "$(cat "$TMP/islands.json")" != "[]" ]; then
        $KICAD_PY tools/maze_io.py export $B "$TMP/empty.rpt" "$TMP/maze.json" "$TMP/islands.json" 2>&1 | quiet
        micromamba run -n kicad python tools/maze_route.py "$TMP/maze.json" "$TMP/maze_out.json"
        $KICAD_PY tools/maze_io.py import $B "$TMP/maze_out.json" 2>&1 | quiet
    fi
    $KICAD_PY tools/netcheck.py $B --skip GND 2>&1 | quiet | tail -1
fi
$KICAD_PY tools/silk_tidy.py $B 2>&1 | quiet
$KICAD_CLI pcb drc -o "$TMP/drc.rpt" $B 2>&1 | grep Found
