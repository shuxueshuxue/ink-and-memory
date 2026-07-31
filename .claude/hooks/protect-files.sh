#!/bin/bash
# protect-files.sh
# PreToolUse hook: block reading/editing sensitive files
# Exit 2 = block the action; Exit 0 = allow

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')

# If no file path found, allow the action
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Protected patterns: add more as needed
PROTECTED_PATTERNS=(
  ".claude/"
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

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "🚫 Blocked: '$FILE_PATH' matches protected pattern '$pattern'. This file is sensitive and cannot be read or modified." >&2
    exit 2
  fi
done

exit 0
