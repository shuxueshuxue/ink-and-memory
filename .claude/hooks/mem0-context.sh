#!/usr/bin/env bash
# [Input] Consume Claude Code SessionStart hook stdin and project PAWKEYLAND_MEM0_* env.
# [Output] Execute mem0_hooks.context_main to inject cross-session additionalContext.
# [Pos] Claude Code SessionStart hook shim under .claude/hooks
# [Sync] 2026-05-10: restore Mem0 context hook from origin/claude-runner.
set -euo pipefail

PYTHON_BIN="${CLAUDE_PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" \
  -c "import sys; sys.path.insert(0, '${CLAUDE_PROJECT_DIR}/.claude/hooks'); from mem0_hooks import context_main; context_main()"
