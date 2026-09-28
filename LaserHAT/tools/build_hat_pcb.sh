#!/bin/sh
# Rebuild the Rev 2 HAT PCB from the schematic:
#   sh tools/build_hat_pcb.sh              placement + hand routes + ground vias only
#   sh tools/build_hat_pcb.sh --route      ... then freerouting (best of 3), import, stitching
#   sh tools/build_hat_pcb.sh --reuse-ses  ... reuse the last freerouting session
# Starts from the Rev 1 board in git, so every step here is reproducible.
set -e
cd "$(dirname "$0")/.."
KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
KICAD_PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
FREEROUTING=/Applications/freerouting.app/Contents/MacOS/freerouting
TMP=${TMPDIR:-/tmp}/laserhat_build
mkdir -p "$TMP"
quiet() { grep -v -E "Fontconfig|assert|memory leak|Debug:" || true; }

git show a722d88:LaserHAT/LaserDriver.kicad_pcb > LaserDriver.kicad_pcb
$KICAD_CLI sch export netlist --format kicadsexpr -o "$TMP/hat.net" LaserDriver.kicad_sch 2>&1 | quiet
$KICAD_PY tools/pcb_sync.py LaserDriver.kicad_pcb "$TMP/hat.net" > "$TMP/sync.log" 2>&1 || { cat "$TMP/sync.log"; exit 1; }
grep -E "saved" "$TMP/sync.log"
$KICAD_PY tools/hat_layout.py LaserDriver.kicad_pcb 2>&1 | quiet
$KICAD_PY tools/hat_preroute.py LaserDriver.kicad_pcb 2>&1 | quiet
$KICAD_PY tools/gnd_vias.py LaserDriver.kicad_pcb 2>&1 | quiet
$KICAD_PY tools/fill_zones.py LaserDriver.kicad_pcb 2>&1 | quiet
if [ "$1" = "--route" ] || [ "$1" = "--reuse-ses" ]; then
    if [ "$1" = "--route" ]; then
        # freerouting is run-to-run variable: try a few times and keep the best session
        $KICAD_PY tools/specctra.py export LaserDriver.kicad_pcb "$TMP/hat.dsn" 2>&1 | quiet
        best=999
        for attempt in 1 2 3; do
            (cd "$TMP" && $FREEROUTING -de hat.dsn -do try.ses -mp 300 -mt 8 --gui.enabled=false > fr$attempt.log 2>&1)
            n=$(grep "Auto-routing stage completed" "$TMP/fr$attempt.log" | sed -E 's/.*\(([0-9]+) unrouted.*/\1/')
            echo "attempt $attempt: ${n:-?} unrouted"
            if [ -n "$n" ] && [ "$n" -lt "$best" ]; then
                best=$n; cp "$TMP/try.ses" "$TMP/hat.ses"; cp "$TMP/fr$attempt.log" "$TMP/fr.log"
            fi
            [ "$best" -eq 0 ] && break
        done
    fi
    $KICAD_PY tools/specctra.py import LaserDriver.kicad_pcb "$TMP/hat.ses" 2>&1 | quiet
    $KICAD_PY tools/stitch.py LaserDriver.kicad_pcb 2.5 2>&1 | quiet
    $KICAD_PY tools/fill_zones.py LaserDriver.kicad_pcb 2>&1 | quiet
    # ground islands: prune floating stitching vias, route pad-bearing islands to the main pour;
    # plus any signal freerouting could not finish -> grid maze router (numpy, kicad env)
    $KICAD_PY tools/gnd_islands.py LaserDriver.kicad_pcb "$TMP/islands.json" 2>&1 | quiet
    $KICAD_CLI pcb drc -o "$TMP/drc.rpt" LaserDriver.kicad_pcb >/dev/null 2>&1
    $KICAD_PY tools/maze_io.py export LaserDriver.kicad_pcb "$TMP/drc.rpt" "$TMP/maze.json" "$TMP/islands.json" 2>&1 | quiet
    micromamba run -n kicad python tools/maze_route.py "$TMP/maze.json" "$TMP/maze_out.json"
    $KICAD_PY tools/maze_io.py import LaserDriver.kicad_pcb "$TMP/maze_out.json" 2>&1 | quiet
fi
$KICAD_PY tools/silk_tidy.py LaserDriver.kicad_pcb 2>&1 | quiet
$KICAD_CLI pcb drc -o "$TMP/drc.rpt" LaserDriver.kicad_pcb 2>&1 | grep Found
