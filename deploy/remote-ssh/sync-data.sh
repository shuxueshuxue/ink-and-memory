#!/usr/bin/env bash
# [Input] Local backend/data, Remote SSH connection env, and REMOTE_APP_DIR.
# [Output] Backs up, uploads, or downloads Remote SSH backend data files over rsync.
# [Pos] data sync companion script in deploy/remote-ssh/
# [Sync] 2026-06-12: add Remote SSH data backup/upload/download workflow for Docker Compose deployments.
# [Sync] 2026-06-16: restrict commands to backup/upload/download and force-recreate Compose services after upload.
# [Sync] 2026-06-23: preserve production OAuth/cookie env vars during data-sync restarts.
# [Sync] 2026-06-23: preserve Mihomo TUN env during data-sync restarts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOCAL_DATA_DIR="${LOCAL_DATA_DIR:-${REPO_ROOT}/backend/data}"

REMOTE_SSH_HOST="${REMOTE_SSH_HOST:-}"
REMOTE_SSH_USER="${REMOTE_SSH_USER:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_SSH_KEY="${REMOTE_SSH_KEY:-}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-}"
REMOTE_DOCKER_COMPOSE_BIN="${REMOTE_DOCKER_COMPOSE_BIN:-docker-compose}"
REMOTE_COMPOSE_FILE="${REMOTE_COMPOSE_FILE:-deploy/remote-ssh/docker-compose.yml}"
REMOTE_COMPOSE_PROJECT_NAME="${REMOTE_COMPOSE_PROJECT_NAME:-ink-and-memory}"
REMOTE_FRONTEND_BIND_HOST="${REMOTE_FRONTEND_BIND_HOST:-127.0.0.1}"
REMOTE_FRONTEND_PORT="${REMOTE_FRONTEND_PORT:-8080}"
REMOTE_BACKEND_BIND_HOST="${REMOTE_BACKEND_BIND_HOST:-127.0.0.1}"
REMOTE_BACKEND_PORT="${REMOTE_BACKEND_PORT:-8765}"
REMOTE_BACKEND_CONTAINER_PORT="${REMOTE_BACKEND_CONTAINER_PORT:-8765}"
REMOTE_BACKEND_IMAGE="${REMOTE_BACKEND_IMAGE:-ink-backend:remote}"
REMOTE_FRONTEND_IMAGE="${REMOTE_FRONTEND_IMAGE:-ink-frontend:remote}"
REMOTE_BACKEND_CONTAINER="${REMOTE_BACKEND_CONTAINER:-ink-backend}"
REMOTE_FRONTEND_CONTAINER="${REMOTE_FRONTEND_CONTAINER:-ink-frontend}"
REMOTE_BACKEND_CPUS="${REMOTE_BACKEND_CPUS:-1.0}"
REMOTE_BACKEND_MEMORY="${REMOTE_BACKEND_MEMORY:-1g}"
REMOTE_FRONTEND_CPUS="${REMOTE_FRONTEND_CPUS:-1.0}"
REMOTE_FRONTEND_MEMORY="${REMOTE_FRONTEND_MEMORY:-256m}"
REMOTE_TZ="${REMOTE_TZ:-UTC}"
REMOTE_AGENT_CWD="${REMOTE_AGENT_CWD:-/app/data/agent-workspace}"
REMOTE_FILE_STORAGE_TYPE="${REMOTE_FILE_STORAGE_TYPE:-local}"
REMOTE_FILE_STORAGE_LOCAL_DIR="${REMOTE_FILE_STORAGE_LOCAL_DIR:-/app/data/file-storage}"
REMOTE_FILE_STORAGE_PREFIX="${REMOTE_FILE_STORAGE_PREFIX:-uploads}"
REMOTE_BACKEND_PUBLIC_ORIGIN="${REMOTE_BACKEND_PUBLIC_ORIGIN:-https://ink-backend.suoxya.com}"
REMOTE_FRONTEND_PUBLIC_ORIGIN="${REMOTE_FRONTEND_PUBLIC_ORIGIN:-https://ink-frontend.suoxya.com}"
REMOTE_API_BASE_URL="${REMOTE_API_BASE_URL:-${REMOTE_BACKEND_PUBLIC_ORIGIN}}"
REMOTE_WS_BASE_URL="${REMOTE_WS_BASE_URL:-}"
REMOTE_CORS_ALLOW_ORIGINS="${REMOTE_CORS_ALLOW_ORIGINS:-${REMOTE_FRONTEND_PUBLIC_ORIGIN}}"
REMOTE_CORS_ALLOW_CREDENTIALS="${REMOTE_CORS_ALLOW_CREDENTIALS:-true}"
REMOTE_COOKIE_SECURE="${REMOTE_COOKIE_SECURE:-true}"
REMOTE_COOKIE_SAMESITE="${REMOTE_COOKIE_SAMESITE:-none}"
REMOTE_CLASH_CONFIG_FILE="${REMOTE_CLASH_CONFIG_FILE:-../../deploy/clash/config.yaml}"
REMOTE_CLASH_IMAGE="${REMOTE_CLASH_IMAGE:-metacubex/mihomo:latest}"
REMOTE_CLASH_CONTAINER="${REMOTE_CLASH_CONTAINER:-tun-proxy}"
REMOTE_CLASH_CONTROLLER_BIND_HOST="${REMOTE_CLASH_CONTROLLER_BIND_HOST:-127.0.0.1}"
REMOTE_CLASH_CONTROLLER_PORT="${REMOTE_CLASH_CONTROLLER_PORT:-9090}"
REMOTE_CLASH_DASHBOARD_BIND_HOST="${REMOTE_CLASH_DASHBOARD_BIND_HOST:-127.0.0.1}"
REMOTE_CLASH_DASHBOARD_PORT="${REMOTE_CLASH_DASHBOARD_PORT:-3000}"
REMOTE_SYNC_DELETE="${REMOTE_SYNC_DELETE:-0}"
DRY_RUN="${DRY_RUN:-0}"
COMMAND="${1:-upload}"

usage() {
  cat <<'USAGE'
Usage:
  ./deploy/remote-ssh/sync-data.sh [upload]
  ./deploy/remote-ssh/sync-data.sh backup
  ./deploy/remote-ssh/sync-data.sh download
  ./deploy/remote-ssh/sync-data.sh --help

Commands:
  backup    Download remote backend/data to backend/data/bak_remote_<YYYYMMDD_HHMMSS>/ only.
  upload    Default. Back up remote data locally, upload local backend/data, then restart Compose with --force-recreate.
  download  Back up current local backend/data, then download remote backend/data into LOCAL_DATA_DIR.

Required environment:
  REMOTE_SSH_HOST       remote SSH host or IP
  REMOTE_APP_DIR        absolute remote deployment directory, e.g. /srv/ink-and-memory

Optional environment:
  REMOTE_SSH_USER       SSH user; omitted means use your local SSH default
  REMOTE_SSH_PORT       default: 22
  REMOTE_SSH_KEY        optional private key path
  LOCAL_DATA_DIR        default: <repo>/backend/data
  REMOTE_DOCKER_COMPOSE_BIN default: docker-compose
  REMOTE_COMPOSE_FILE   default: deploy/remote-ssh/docker-compose.yml
  REMOTE_COMPOSE_PROJECT_NAME default: ink-and-memory
  REMOTE_CLASH_CONFIG_FILE default: ../../deploy/clash/config.yaml, resolved from deploy/remote-ssh/docker-compose.yml
  REMOTE_SYNC_DELETE    default: 0; set to 1 to pass --delete during upload/download
  DRY_RUN               set to 1 to print commands without executing
USAGE
}

log() { printf '[remote-sync] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err() { printf '[error] %s\n' "$*" >&2; exit 1; }
quote() { printf '%q' "$1"; }

ssh_target() {
  if [[ -n "${REMOTE_SSH_USER}" ]]; then
    printf '%s@%s\n' "${REMOTE_SSH_USER}" "${REMOTE_SSH_HOST:-REMOTE_SSH_HOST}"
  else
    printf '%s\n' "${REMOTE_SSH_HOST:-REMOTE_SSH_HOST}"
  fi
}

ssh_transport() {
  local transport="ssh -p $(quote "${REMOTE_SSH_PORT}")"
  [[ -n "${REMOTE_SSH_KEY}" ]] && transport+=" -i $(quote "${REMOTE_SSH_KEY}")"
  printf '%s\n' "${transport}"
}

ssh_args_array() {
  SSH_ARGS=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && SSH_ARGS+=(-i "${REMOTE_SSH_KEY}")
  return 0
}

remote_data_dir() {
  printf '%s/backend/data\n' "${REMOTE_APP_DIR%/}"
}

remote_env_prefix() {
  local names=(
    REMOTE_FRONTEND_BIND_HOST REMOTE_FRONTEND_PORT
    REMOTE_BACKEND_BIND_HOST REMOTE_BACKEND_PORT REMOTE_BACKEND_CONTAINER_PORT
    REMOTE_BACKEND_IMAGE REMOTE_FRONTEND_IMAGE
    REMOTE_BACKEND_CONTAINER REMOTE_FRONTEND_CONTAINER
    REMOTE_BACKEND_CPUS REMOTE_BACKEND_MEMORY
    REMOTE_FRONTEND_CPUS REMOTE_FRONTEND_MEMORY
    REMOTE_TZ REMOTE_BACKEND_PUBLIC_ORIGIN REMOTE_FRONTEND_PUBLIC_ORIGIN
    REMOTE_API_BASE_URL REMOTE_WS_BASE_URL
    REMOTE_AGENT_CWD REMOTE_FILE_STORAGE_TYPE
    REMOTE_FILE_STORAGE_LOCAL_DIR REMOTE_FILE_STORAGE_PREFIX
    REMOTE_CORS_ALLOW_ORIGINS REMOTE_CORS_ALLOW_CREDENTIALS
    REMOTE_COOKIE_SECURE REMOTE_COOKIE_SAMESITE
    REMOTE_CLASH_CONFIG_FILE REMOTE_CLASH_IMAGE
    REMOTE_CLASH_CONTAINER REMOTE_CLASH_CONTROLLER_BIND_HOST
    REMOTE_CLASH_CONTROLLER_PORT REMOTE_CLASH_DASHBOARD_BIND_HOST
    REMOTE_CLASH_DASHBOARD_PORT
  )
  local output="env" name
  for name in "${names[@]}"; do
    output+=" $(quote "${name}=${!name}")"
  done
  printf '%s\n' "${output}"
}

remote_compose() {
  local compose_cmd arg
  compose_cmd="cd $(quote "${REMOTE_APP_DIR%/}") && $(remote_env_prefix) $(quote "${REMOTE_DOCKER_COMPOSE_BIN}") -p $(quote "${REMOTE_COMPOSE_PROJECT_NAME}") -f $(quote "${REMOTE_COMPOSE_FILE}")"
  for arg in "$@"; do
    compose_cmd+=" $(quote "${arg}")"
  done
  ssh_run "${compose_cmd}"
}

check_prereqs() {
  [[ -n "${REMOTE_SSH_HOST}" ]] || err "REMOTE_SSH_HOST is required."
  [[ -n "${REMOTE_APP_DIR}" ]] || err "REMOTE_APP_DIR is required."
  [[ "${REMOTE_APP_DIR}" == /* ]] || err "REMOTE_APP_DIR must be an absolute path."
  command -v ssh >/dev/null 2>&1 || err "ssh not found."
  command -v rsync >/dev/null 2>&1 || err "rsync not found."
  if [[ "${DRY_RUN}" != "1" ]]; then
    mkdir -p "${LOCAL_DATA_DIR}"
  fi
}

ssh_run() {
  local cmd="$1" target
  target="$(ssh_target)"
  ssh_args_array
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] ssh'
    printf ' %q' "${SSH_ARGS[@]}" "${target}" "${cmd}"
    printf '\n'
  else
    ssh "${SSH_ARGS[@]}" "${target}" "${cmd}"
  fi
}

run_cmd() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

ensure_remote_storage() {
  ssh_run "mkdir -p $(quote "$(remote_data_dir)") $(quote "$(remote_data_dir)/file-storage") $(quote "$(remote_data_dir)/agent-workspace") $(quote "$(remote_data_dir)/backups")"
}

restart_remote_services() {
  log "Restarting remote Compose services with --force-recreate so the backend reloads uploaded data."
  remote_compose up -d --force-recreate
}

backup_remote() {
  local timestamp backup_dir remote_path target
  timestamp="$(date +%Y%m%d_%H%M%S)"
  backup_dir="${LOCAL_DATA_DIR}/bak_remote_${timestamp}"
  remote_path="$(remote_data_dir)/"
  target="$(ssh_target):${remote_path}"

  ensure_remote_storage
  run_cmd mkdir -p "${backup_dir}"
  log "Downloading remote backend/data backup to ${backup_dir}"
  run_cmd rsync -az \
    --exclude '/bak_*/' \
    --exclude '/bak_remote_*/' \
    --exclude '/backups/' \
    -e "$(ssh_transport)" \
    "${target}" "${backup_dir}/"

  log "Remote backup complete: ${backup_dir}"
}

backup_local() {
  local timestamp backup_dir
  timestamp="$(date +%Y%m%d_%H%M%S)"
  backup_dir="${LOCAL_DATA_DIR}/bak_local_${timestamp}"

  run_cmd mkdir -p "${backup_dir}"
  log "Backing up current local backend/data to ${backup_dir}"
  run_cmd rsync -az \
    --exclude '/bak_*/' \
    --exclude '/bak_remote_*/' \
    --exclude '/bak_local_*/' \
    --exclude '/backups/' \
    "${LOCAL_DATA_DIR}/" "${backup_dir}/"

  log "Local backup complete: ${backup_dir}"
}

upload_local() {
  local target remote_path rsync_args
  [[ -f "${LOCAL_DATA_DIR}/ink-and-memory.db" ]] || warn "Local SQLite DB not found at ${LOCAL_DATA_DIR}/ink-and-memory.db; syncing directory contents anyway."
  backup_remote

  remote_path="$(remote_data_dir)/"
  target="$(ssh_target):${remote_path}"
  rsync_args=(-az
    --exclude '/bak_*/'
    --exclude '/bak_remote_*/'
    --exclude '/backups/'
    -e "$(ssh_transport)")
  [[ "${REMOTE_SYNC_DELETE}" == "1" ]] && rsync_args+=(--delete)

  log "Uploading ${LOCAL_DATA_DIR}/ to $(ssh_target):${remote_path}"
  run_cmd rsync "${rsync_args[@]}" "${LOCAL_DATA_DIR}/" "${target}"
  restart_remote_services
  log "Remote data upload complete."
}

download_remote() {
  local target remote_path rsync_args
  ensure_remote_storage
  backup_local

  remote_path="$(remote_data_dir)/"
  target="$(ssh_target):${remote_path}"
  rsync_args=(-az
    --exclude '/bak_*/'
    --exclude '/bak_remote_*/'
    --exclude '/backups/'
    -e "$(ssh_transport)")
  [[ "${REMOTE_SYNC_DELETE}" == "1" ]] && rsync_args+=(--delete)

  log "Downloading $(ssh_target):${remote_path} to ${LOCAL_DATA_DIR}/"
  run_cmd rsync "${rsync_args[@]}" "${target}" "${LOCAL_DATA_DIR}/"
  log "Remote data download complete."
}

case "${COMMAND}" in
  --help|-h|help) usage ;;
  upload) check_prereqs; upload_local ;;
  backup) check_prereqs; backup_remote ;;
  download) check_prereqs; download_remote ;;
  *) err "Unknown command: ${COMMAND}. Run --help." ;;
esac
