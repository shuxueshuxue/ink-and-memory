#!/usr/bin/env bash
# [Input] deploy/google-cloud/setup-storage.sh and legacy setup-storage CLI arguments.
# [Output] Backward-compatible Google Cloud storage setup entrypoint.
# [Pos] legacy Google Cloud storage setup compatibility script in deploy/
# [Sync] 2026-06-12: delegate to deploy/google-cloud/setup-storage.sh after moving implementation into the platform directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/google-cloud/setup-storage.sh" "$@"
