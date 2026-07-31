#!/usr/bin/env bash
# deploy/google-cloud/sync-data.sh — Back up cloud SQLite data locally, optionally upload local backend/data/ to GCS, and restart backend.
# [Sync] 2026-06-12: preserve deploy-owned backend CORS env vars during restarts.
# [Sync] 2026-06-12: strip stale INK_CORS_* values from .cloud-env before Cloud Run env updates.
# [Sync] 2026-06-12: write fixed frontend public origin CORS defaults during data-sync restarts.
# [Sync] 2026-06-12: download cloud SQLite files to backend/data/bak_<date>/ before upload or shutdown-style maintenance.
# [Sync] 2026-06-12: move Google Cloud implementation from deploy/ to deploy/google-cloud/.
# [Sync] 2026-06-23: preserve production OAuth/cookie env vars during data-sync restarts.
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   ./deploy/google-cloud/deploy.sh sync-data
#   ./deploy/google-cloud/deploy.sh backup-data
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STORAGE_ENV="${REPO_ROOT}/.storage-env"
CLOUD_ENV="${REPO_ROOT}/.cloud-env"

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-asia-east1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-ink-backend}"
FRONTEND_PUBLIC_ORIGIN="${FRONTEND_PUBLIC_ORIGIN:-https://ink-frontend.suoxya.com}"
BACKEND_PUBLIC_ORIGIN="${BACKEND_PUBLIC_ORIGIN:-https://ink-backend.suoxya.com}"
BACKEND_CORS_ALLOW_ORIGINS="${BACKEND_CORS_ALLOW_ORIGINS:-${FRONTEND_PUBLIC_ORIGIN}}"
INK_CORS_ALLOW_CREDENTIALS="${INK_CORS_ALLOW_CREDENTIALS:-true}"
BACKEND_COOKIE_SECURE="${BACKEND_COOKIE_SECURE:-true}"
BACKEND_COOKIE_SAMESITE="${BACKEND_COOKIE_SAMESITE:-none}"
DATA_DIR="${REPO_ROOT}/backend/data"
COMMAND="${1:-upload}"
SYNC_DATA_SKIP_CLOUD_BACKUP="${SYNC_DATA_SKIP_CLOUD_BACKUP:-0}"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[sync]${NC} $*"; }
info() { echo -e "${CYAN}[info]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*" >&2; }
err()  { echo "ERROR: $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  ./deploy/google-cloud/sync-data.sh [upload]
  ./deploy/google-cloud/sync-data.sh backup-cloud
  ./deploy/google-cloud/sync-data.sh --help

Commands:
  upload        Default. Back up cloud SQLite files locally, upload local DB/WAL/SHM to GCS, and restart backend.
  backup-cloud  Download cloud SQLite files to backend/data/bak_<YYYYMMDD_HHMMSS>/ only. No upload or restart.

Environment:
  GCP_PROJECT_ID                 required
  GCP_REGION                     default: asia-east1
  BACKEND_SERVICE                default: ink-backend
  SYNC_DATA_SKIP_CLOUD_BACKUP=1  skip pre-upload cloud backup; not recommended
EOF
}

sanitize_cloud_env_vars() {
  local raw="$1"
  local result="" item key
  local -a entries
  IFS=',' read -ra entries <<< "${raw}"
  for item in "${entries[@]}"; do
    [[ -z "${item}" ]] && continue
    key="${item%%=*}"
    case "${key}" in
      WEBUI_URL|API_BASE_URL|COOKIE_SECURE|COOKIE_SAMESITE|INK_CORS_ALLOW_ORIGINS|INK_CORS_ALLOW_CREDENTIALS|INK_PUBLIC_BASE_URL|INK_BACKEND_PUBLIC_BASE_URL)
        warn "Ignoring ${key} from .cloud-env; deploy/google-cloud/deploy.sh owns public OAuth/CORS/cookie env."
        continue
        ;;
    esac
    if [[ -n "${result}" ]]; then
      result+=",${item}"
    else
      result="${item}"
    fi
  done
  printf '%s\n' "${result}"
}

env_vars_to_delimited() {
  local raw="$1"
  local result="" item
  local -a entries
  IFS=',' read -ra entries <<< "${raw}"
  for item in "${entries[@]}"; do
    [[ -z "${item}" ]] && continue
    if [[ -n "${result}" ]]; then
      result+="|${item}"
    else
      result="${item}"
    fi
  done
  printf '%s\n' "${result}"
}

normalize_origin_list() {
  local raw="$1"
  local result="" item trimmed
  local -a entries
  IFS=',' read -ra entries <<< "${raw}"
  for item in "${entries[@]}"; do
    trimmed="${item#"${item%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    trimmed="${trimmed%/}"
    [[ -z "${trimmed}" ]] && continue
    if [[ -n "${result}" ]]; then
      result+=",${trimmed}"
    else
      result="${trimmed}"
    fi
  done
  printf '%s\n' "${result}"
}

load_storage_env() {
  [[ -n "${PROJECT_ID}" ]] || err "GCP_PROJECT_ID is not set."
  [[ -f "${STORAGE_ENV}" ]] || err ".storage-env not found. Run ./deploy/google-cloud/deploy.sh setup-storage first."
  # shellcheck source=/dev/null
  source "${STORAGE_ENV}"
}

load_cloud_env() {
  [[ -f "${CLOUD_ENV}" ]] || err ".cloud-env not found. Run ./deploy/google-cloud/deploy.sh setup-env first."
  # shellcheck source=/dev/null
  source "${CLOUD_ENV}"
}

cloud_db_exists() {
  gsutil ls "gs://${GCS_BUCKET}/ink-and-memory.db" >/dev/null 2>&1
}

check_backup_integrity() {
  local db_path="$1"
  if ! command -v sqlite3 >/dev/null 2>&1; then
    warn "sqlite3 not found; skipped integrity check for ${db_path}."
    return 0
  fi

  local result
  result="$(sqlite3 "${db_path}" "PRAGMA integrity_check;" 2>&1 || true)"
  if [[ "${result}" == "ok" ]]; then
    info "  Integrity check: ok"
  else
    warn "Integrity check reported a problem for ${db_path}:"
    warn "${result}"
    warn "Backup is still preserved for recovery analysis."
  fi
}

download_cloud_backup() {
  local timestamp backup_dir
  timestamp="$(date +%Y%m%d_%H%M%S)"
  backup_dir="${DATA_DIR}/bak_${timestamp}"

  if ! cloud_db_exists; then
    warn "Cloud database not found at gs://${GCS_BUCKET}/ink-and-memory.db; skipping local backup."
    return 0
  fi

  mkdir -p "${backup_dir}"
  log "Downloading cloud SQLite files to ${backup_dir}..."
  gsutil -m cp "gs://${GCS_BUCKET}/ink-and-memory.db*" "${backup_dir}/"

  if [[ -f "${backup_dir}/ink-and-memory.db" ]]; then
    check_backup_integrity "${backup_dir}/ink-and-memory.db"
  else
    warn "Backup directory was created, but ink-and-memory.db was not downloaded."
  fi

  info "Cloud backup saved: ${backup_dir}"
}

upload_local_data() {
  load_cloud_env
  [[ -f "${DATA_DIR}/ink-and-memory.db" ]] || err "Local database not found: ${DATA_DIR}/ink-and-memory.db"

  if [[ "${SYNC_DATA_SKIP_CLOUD_BACKUP}" == "1" ]]; then
    warn "Skipping pre-upload cloud backup because SYNC_DATA_SKIP_CLOUD_BACKUP=1."
  else
    download_cloud_backup
  fi

  # ── Upload ──────────────────────────────────────────────────────────────────
  log "Uploading ink-and-memory.db..."
  gsutil cp "${DATA_DIR}/ink-and-memory.db" "gs://${GCS_BUCKET}/ink-and-memory.db"

  # Also sync WAL files if they exist (needed for consistent SQLite state).
  for wal_file in "${DATA_DIR}/ink-and-memory.db-wal" "${DATA_DIR}/ink-and-memory.db-shm"; do
    [[ -f "${wal_file}" ]] && gsutil cp "${wal_file}" "gs://${GCS_BUCKET}/$(basename "${wal_file}")"
  done


  # ── Restart backend while preserving deploy-owned values such as CORS ──────
  log "Restarting ${BACKEND_SERVICE} with full config..."
  SANITIZED_CLOUD_ENV_VARS="$(sanitize_cloud_env_vars "${CLOUD_ENV_VARS:-}")"
  SANITIZED_CLOUD_ENV_VARS_DELIMITED="$(env_vars_to_delimited "${SANITIZED_CLOUD_ENV_VARS}")"
  CORS_ORIGINS="$(normalize_origin_list "${BACKEND_CORS_ALLOW_ORIGINS}")"
  UPDATE_RUNTIME_ENV_VARS="FORCE_RESTART=$(date +%s)|WEBUI_URL=${FRONTEND_PUBLIC_ORIGIN}|API_BASE_URL=${BACKEND_PUBLIC_ORIGIN}|COOKIE_SECURE=${BACKEND_COOKIE_SECURE}|COOKIE_SAMESITE=${BACKEND_COOKIE_SAMESITE}|INK_PUBLIC_BASE_URL=${FRONTEND_PUBLIC_ORIGIN%/}/|INK_BACKEND_PUBLIC_BASE_URL=${BACKEND_PUBLIC_ORIGIN}|INK_CORS_ALLOW_ORIGINS=${CORS_ORIGINS}|INK_CORS_ALLOW_CREDENTIALS=${INK_CORS_ALLOW_CREDENTIALS}"
  if [[ -n "${SANITIZED_CLOUD_ENV_VARS_DELIMITED}" ]]; then
    UPDATE_ENV_VARS="${SANITIZED_CLOUD_ENV_VARS_DELIMITED}|${UPDATE_RUNTIME_ENV_VARS}"
  else
    UPDATE_ENV_VARS="${UPDATE_RUNTIME_ENV_VARS}"
  fi
  RESTART_FLAGS=(
    --region="${REGION}"
    --project="${PROJECT_ID}"
    --update-env-vars="^|^${UPDATE_ENV_VARS}"
    --quiet
  )
  [[ -n "${CLOUD_SECRET_REFS:-}" ]] && RESTART_FLAGS+=(--set-secrets="${CLOUD_SECRET_REFS}")
  gcloud run services update "${BACKEND_SERVICE}" "${RESTART_FLAGS[@]}"

  info "════════════════════════════════════════"
  info "  Sync complete. Backend is restarting."
  info "  Data: gs://${GCS_BUCKET}/"
  info "  CORS: ${CORS_ORIGINS}"
  info "════════════════════════════════════════"
}

case "${COMMAND}" in
  --help|-h|help)
    usage
    ;;
  upload|sync)
    load_storage_env
    upload_local_data
    ;;
  backup-cloud|backup|download|download-backup)
    load_storage_env
    download_cloud_backup
    ;;
  *)
    err "Unknown command: ${COMMAND}. Run ./deploy/google-cloud/sync-data.sh --help."
    ;;
esac
