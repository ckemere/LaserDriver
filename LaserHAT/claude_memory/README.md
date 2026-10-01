# Claude Code memory for the LaserHAT Rev 2 work

Portable copies of the Claude Code auto-memory from the Rev 2 sessions (2026-09-25 onwards): `MEMORY.md` is the
index, one fact per file. Refreshed 2026-09-29.

Claude Code keeps memory per project directory under `~/.claude/projects/<encoded path>/memory/`, where the encoded
path is the checkout's absolute path with every `/` replaced by `-`. To install in a new checkout:

```bash
REPO=$(git rev-parse --show-toplevel)            # run inside the new checkout
MEM=~/.claude/projects/$(echo "$REPO" | sed 's|/|-|g')/memory
mkdir -p "$MEM" && cp LaserHAT/claude_memory/*.md "$MEM"/ && rm "$MEM"/README.md
```

Then fix `pcb-workspace-setup.md` in the installed copy for the machine (tool paths). Or just tell the session
"read LaserHAT/claude_memory/ first". The design facts themselves live in `LaserHAT/CLAUDE.md`, `REV2_NOTES.md`,
`EStimDaughter/DESIGN_NOTES.md` and `estim_interface/ESTIM_MODULE_SPEC.md`.
