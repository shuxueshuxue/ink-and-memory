#!/usr/bin/env bash
# [Input] deploy/google-cloud/deploy.sh and legacy Cloud Run deploy CLI arguments.
# [Output] Backward-compatible Cloud Run deployment entrypoint.
# [Pos] legacy Cloud Run release compatibility script in deploy/
# [Sync] 2026-06-12: delegate to deploy/google-cloud/deploy.sh so the platform directory owns full env/deploy logic.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/google-cloud/deploy.sh" deploy "$@"
