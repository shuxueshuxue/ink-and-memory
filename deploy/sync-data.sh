#!/usr/bin/env bash
# [Input] deploy/google-cloud/sync-data.sh and legacy sync-data CLI arguments.
# [Output] Backward-compatible Google Cloud data sync entrypoint.
# [Pos] legacy Google Cloud data sync compatibility script in deploy/
# [Sync] 2026-06-12: delegate to deploy/google-cloud/sync-data.sh after moving implementation into the platform directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/google-cloud/sync-data.sh" "$@"
