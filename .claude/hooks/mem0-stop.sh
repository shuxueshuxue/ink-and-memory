#!/usr/bin/env bash
# [Input] Consume Claude Code Stop hook stdin, transcript path, and project PAWKEYLAND_MEM0_* env.
# [Output] Execute mem0_hooks.stop_main to summarize the session into Mem0.
# [Pos] Claude Code Stop hook shim under .claude/hooks
# [Sync] 2026-05-10: restore Mem0 stop hook from origin/claude-runner.
set -euo pipefail

PYTHON_BIN="${CLAUDE_PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" \
  -c "import sys; sys.path.insert(0, '${CLAUDE_PROJECT_DIR}/.claude/hooks'); from mem0_hooks import stop_main; stop_main()"
