#!/bin/bash
# protect-files-bash.sh
# PreToolUse hook for Bash tool: block shell commands that read/write sensitive files
# Exit 2 = block the action; Exit 0 = allow

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# If no command found, allow
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Protected file patterns
PROTECTED_PATTERNS=(
  ".claude/settings.json"
  ".claude/settings.local.json"
  ".claude/index.json"
  ".env"
  ".env.local"
  ".env.production"
  ".env.development"
  ".git/"
  ".cursorrc"
  ".cursor/"
  "id_rsa"
  "id_ed25519"
  ".ssh/"
  ".npmrc"
  ".pypirc"
)

# Dangerous commands that can read file contents
# Covers: cat, less, more, head, tail, bat, vi/vim/nvim, nano, sed, awk, grep, 
#         od, xxd, hexdump, strings, file, open, cp, mv, source, xargs + cat, etc.
READ_COMMANDS='cat|less|more|head|tail|bat|batcat|vi|vim|nvim|nano|sed|awk|grep|egrep|fgrep|rg|ag|od|xxd|hexdump|strings|source|\.|open|code|subl|pbcopy'
WRITE_COMMANDS='cp|mv|rm|tee|chmod|chown'

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  # Check if the command references this protected pattern
  if echo "$COMMAND" | grep -qF "$pattern"; then
    # Check if it's a read/write command targeting the file
    if echo "$COMMAND" | grep -qE "(^|\s|/|;|\||&&|\`|\$\()($READ_COMMANDS|$WRITE_COMMANDS)(\s|$)" || \
       echo "$COMMAND" | grep -qE "(<|>|>>)\s*[^ ]*$pattern"; then
      echo "🚫 Blocked: command references protected pattern '$pattern'. Sensitive files cannot be read or modified via shell commands." >&2
      exit 2
    fi
    # Also block if the pattern appears as a direct argument (e.g., `python script.py .env`)
    # or redirection target
    if echo "$COMMAND" | grep -qE "(^|\s)([a-zA-Z0-9_./-]*$pattern)"; then
      echo "🚫 Blocked: command references protected file matching '$pattern'. Sensitive files cannot be accessed via shell commands." >&2
      exit 2
    fi
  fi
done

exit 0
