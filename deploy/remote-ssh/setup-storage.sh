#!/usr/bin/env bash
# [Input] Remote SSH connection env and REMOTE_APP_DIR.
# [Output] Creates the Remote SSH persistent backend storage directories on the server.
# [Pos] storage setup companion script in deploy/remote-ssh/
# [Sync] 2026-06-12: add Remote SSH filesystem storage bootstrap for Docker Compose deployments.
set -euo pipefail

REMOTE_SSH_HOST="${REMOTE_SSH_HOST:-}"
REMOTE_SSH_USER="${REMOTE_SSH_USER:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_SSH_KEY="${REMOTE_SSH_KEY:-}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-}"
REMOTE_STORAGE_OWNER="${REMOTE_STORAGE_OWNER:-}"
REMOTE_STORAGE_GROUP="${REMOTE_STORAGE_GROUP:-}"
REMOTE_STORAGE_MODE="${REMOTE_STORAGE_MODE:-775}"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'USAGE'
Usage:
  REMOTE_SSH_HOST=<host> REMOTE_APP_DIR=/srv/ink-and-memory ./deploy/remote-ssh/setup-storage.sh

Creates or repairs the remote filesystem layout used by deploy/remote-ssh/docker-compose.yml:
  ${REMOTE_APP_DIR}/backend/data/
  ${REMOTE_APP_DIR}/backend/data/file-storage/
  ${REMOTE_APP_DIR}/backend/data/agent-workspace/
  ${REMOTE_APP_DIR}/backend/data/backups/

Required environment:
  REMOTE_SSH_HOST       remote SSH host or IP
  REMOTE_APP_DIR        absolute remote deployment directory, e.g. /srv/ink-and-memory

Optional environment:
  REMOTE_SSH_USER       SSH user; omitted means use your local SSH default
  REMOTE_SSH_PORT       default: 22
  REMOTE_SSH_KEY        optional private key path
  REMOTE_STORAGE_OWNER  optional chown owner for created directories
  REMOTE_STORAGE_GROUP  optional chown group for created directories
  REMOTE_STORAGE_MODE   chmod mode for directories, default: 775
  DRY_RUN               set to 1 to print commands without executing
USAGE
}

log() { printf '[remote-storage] %s\n' "$*"; }
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

ssh_args_array() {
  SSH_ARGS=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && SSH_ARGS+=(-i "${REMOTE_SSH_KEY}")
  return 0
}

check_prereqs() {
  [[ -n "${REMOTE_SSH_HOST}" ]] || err "REMOTE_SSH_HOST is required."
  [[ -n "${REMOTE_APP_DIR}" ]] || err "REMOTE_APP_DIR is required."
  [[ "${REMOTE_APP_DIR}" == /* ]] || err "REMOTE_APP_DIR must be an absolute path."
  command -v ssh >/dev/null 2>&1 || err "ssh not found."
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

setup_storage() {
  local app_dir data_dir owner_spec chown_cmd
  app_dir="${REMOTE_APP_DIR%/}"
  data_dir="${app_dir}/backend/data"

  owner_spec=""
  if [[ -n "${REMOTE_STORAGE_OWNER}" || -n "${REMOTE_STORAGE_GROUP}" ]]; then
    owner_spec="${REMOTE_STORAGE_OWNER}:${REMOTE_STORAGE_GROUP}"
  fi

  chown_cmd=""
  if [[ -n "${owner_spec}" ]]; then
    chown_cmd="chown -R $(quote "${owner_spec}") $(quote "${data_dir}") &&"
  fi

  log "Creating Remote SSH storage under $(ssh_target):${data_dir}"
  ssh_run "mkdir -p $(quote "${data_dir}") $(quote "${data_dir}/file-storage") $(quote "${data_dir}/agent-workspace") $(quote "${data_dir}/backups") && ${chown_cmd} chmod -R $(quote "${REMOTE_STORAGE_MODE}") $(quote "${data_dir}") && printf '%s\\n' 'Remote storage ready: ${data_dir}'"

  log "Storage setup complete. Compose mounts ${data_dir} to /app/data."
}

case "${1:-setup}" in
  --help|-h|help) usage ;;
  setup) check_prereqs; setup_storage ;;
  *) err "Unknown command: $1. Run --help." ;;
esac
