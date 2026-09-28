# Claude Code memory for the LaserHAT Rev 2 work

These are portable copies of the Claude Code auto-memory from the Rev 2 HAT sessions
(2026-09-25 to 2026-09-28). The files are:
- `MEMORY.md`, the index;
- one fact per file (workspace setup, Rev 2 goals, HAT board status, user preferences, next tasks).

Claude Code keeps memory per project directory, under
`~/.claude/projects/<encoded path>/memory/`. The encoded path is the checkout's absolute path with
every `/` replaced by `-`. To install these in a new checkout:

```bash
REPO=$(git rev-parse --show-toplevel)            # run inside the new checkout
MEM=~/.claude/projects/$(echo "$REPO" | sed 's|/|-|g')/memory
mkdir -p "$MEM" && cp LaserHAT/claude_memory/*.md "$MEM"/ && rm "$MEM"/README.md
```

Or just point the new session at this folder ("read LaserHAT/claude_memory/ first"). The same
facts are in `LaserHAT/CLAUDE.md` (Rev 2 section) and `LaserHAT/REV2_NOTES.md`, which Claude
reads anyway.
