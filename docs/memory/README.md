# Claude Code memory (LaserHAT Rev 2 → Glance out)

Portable copies of the Claude Code auto-memory from the Rev 2 sessions (2026-09-25 onwards): `MEMORY.md` is the
index, one fact per file. Refreshed 2026-09-29; moved from `LaserHAT/claude_memory/` to `docs/memory/` on 2026-11-13
(glance-out restructure: `LaserHAT/` is now `hardware/`, `Firmware/` `firmware/`, `Pi/` `pi/`; the Rev 2 HAT,
LaserDaughter, EStimDaughter and relay BatteryPack are archived at tag `archive/pre-glance-cleanup`).  Notes about
those boards are history; their paths are as they were.

Claude Code keeps memory per project directory under `~/.claude/projects/<encoded path>/memory/`, where the encoded
path is the checkout's absolute path with every `/` replaced by `-`. To install in a new checkout:

```bash
REPO=$(git rev-parse --show-toplevel)            # run inside the new checkout
MEM=~/.claude/projects/$(echo "$REPO" | sed 's|/|-|g')/memory
mkdir -p "$MEM" && cp docs/memory/*.md "$MEM"/ && rm "$MEM"/README.md
```

Then fix `pcb-workspace-setup.md` in the installed copy for the machine (tool paths). Or just tell the session
"read docs/memory/ first". The design facts themselves live in `hardware/CLAUDE.md`, `docs/history/REV2_NOTES.md`,
`hardware/estim_interface/ESTIM_MODULE_SPEC.md` and each board's README (`EStimDaughter/DESIGN_NOTES.md` is archived).
