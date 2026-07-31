#!/usr/bin/env bash
# [Input] Remote SSH connection env and REMOTE_SWAP_SIZE_MB/REMOTE_SWAP_FILE.
# [Output] Ensures a swap file exists on the remote server so memory-heavy
#          builds (frontend `docker-compose build`, which needs a Node/Vite
#          heap well above what a 1G-RAM host provides) survive transient
#          memory pressure instead of being OOM-killed.
# [Pos] swap setup companion script in deploy/remote-ssh/
# [Sync] 2026-07-20: created — frontend Vite/Rollup build (mermaid + tiptap +
#                    ai sdk dependency graph) needs a builder heap around 1G,
#                    which saturates a 1G-RAM remote host with zero headroom
#                    for the OS/Docker daemon/other containers; provision swap
#                    so `deploy/remote-ssh/deploy.sh deploy` no longer OOMs.
set -euo pipefail

REMOTE_SSH_HOST="${REMOTE_SSH_HOST:-}"
REMOTE_SSH_USER="${REMOTE_SSH_USER:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_SSH_KEY="${REMOTE_SSH_KEY:-}"
REMOTE_SWAP_FILE="${REMOTE_SWAP_FILE:-/swapfile}"
REMOTE_SWAP_SIZE_MB="${REMOTE_SWAP_SIZE_MB:-2048}"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'USAGE'
Usage:
  REMOTE_SSH_HOST=<host> ./deploy/remote-ssh/setup-swap.sh

Ensures the remote server has at least REMOTE_SWAP_SIZE_MB of swap by
creating/enabling REMOTE_SWAP_FILE when current total swap is smaller.
Idempotent: does nothing when sufficient swap already exists. Persists the
swap file across reboots via /etc/fstab (added only if missing).

Required environment:
  REMOTE_SSH_HOST       remote SSH host or IP

Optional environment:
  REMOTE_SSH_USER       SSH user; omitted means use your local SSH default
  REMOTE_SSH_PORT       default: 22
  REMOTE_SSH_KEY        optional private key path
  REMOTE_SWAP_FILE      swap file path on the remote host, default: /swapfile
  REMOTE_SWAP_SIZE_MB   minimum total swap to ensure, in MB, default: 2048
  DRY_RUN               set to 1 to print commands without executing
USAGE
}

log() { printf '[setup-swap] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err() { printf '[error] %s\n' "$*" >&2; exit 1; }
quote() { printf '%q' "$1"; }

check_prereqs() {
  [[ -n "${REMOTE_SSH_HOST}" ]] || err "REMOTE_SSH_HOST is required."
  [[ "${REMOTE_SWAP_SIZE_MB}" =~ ^[0-9]+$ ]] || err "REMOTE_SWAP_SIZE_MB must be a positive integer."
  command -v ssh >/dev/null 2>&1 || err "ssh not found."
}

ssh_target() {
  if [[ -n "${REMOTE_SSH_USER}" ]]; then
    printf '%s@%s\n' "${REMOTE_SSH_USER}" "${REMOTE_SSH_HOST}"
  else
    printf '%s\n' "${REMOTE_SSH_HOST}"
  fi
}

ssh_run() {
  local cmd="$1" target ssh_args=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && ssh_args+=(-i "${REMOTE_SSH_KEY}")
  target="$(ssh_target)"
  if [[ "${DRY_RUN}" == "1" ]]; then
    printf '[dry-run] ssh'
    printf ' %q' "${ssh_args[@]}" "${target}" "${cmd}"
    printf '\n'
  else
    ssh "${ssh_args[@]}" "${target}" "${cmd}"
  fi
}

setup_swap() {
  local swap_file swap_size_mb remote_script
  swap_file="${REMOTE_SWAP_FILE}"
  swap_size_mb="${REMOTE_SWAP_SIZE_MB}"

  # Runs on the remote host: prefer running as-is (already root on most small
  # VPS deployments used here), fall back to non-interactive sudo, otherwise
  # skip without failing the overall deploy.
  remote_script=$(cat <<'REMOTE_EOF'
set -e
SWAP_FILE="__SWAP_FILE__"
SWAP_SIZE_MB="__SWAP_SIZE_MB__"

as_root() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
  else
    echo "[setup-swap] no root/passwordless-sudo access; skipping swap setup." >&2
    exit 78
  fi
}

current_swap_kb=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
current_swap_mb=$((current_swap_kb / 1024))
if [ "${current_swap_mb}" -ge "${SWAP_SIZE_MB}" ]; then
  echo "[setup-swap] existing swap ${current_swap_mb}MB already >= ${SWAP_SIZE_MB}MB, skipping."
  exit 0
fi

if swapon --show=NAME --noheadings 2>/dev/null | grep -qx "${SWAP_FILE}"; then
  echo "[setup-swap] ${SWAP_FILE} already active but total swap is below target; leaving as-is."
  exit 0
fi

echo "[setup-swap] creating ${SWAP_SIZE_MB}MB swap file at ${SWAP_FILE}."
if ! as_root fallocate -l "${SWAP_SIZE_MB}M" "${SWAP_FILE}" 2>/dev/null; then
  as_root dd if=/dev/zero of="${SWAP_FILE}" bs=1M count="${SWAP_SIZE_MB}"
fi
as_root chmod 600 "${SWAP_FILE}"
as_root mkswap "${SWAP_FILE}"
as_root swapon "${SWAP_FILE}"

if ! grep -qsF "${SWAP_FILE} " /etc/fstab; then
  as_root sh -c "printf '%s\n' '${SWAP_FILE} none swap sw 0 0' >> /etc/fstab"
fi

echo "[setup-swap] swap ready: $(awk '/^SwapTotal:/ {print $2/1024\"MB\"}' /proc/meminfo)"
REMOTE_EOF
)
  remote_script="${remote_script//__SWAP_FILE__/${swap_file}}"
  remote_script="${remote_script//__SWAP_SIZE_MB__/${swap_size_mb}}"

  log "Ensuring at least ${swap_size_mb}MB swap on $(ssh_target) (file: ${swap_file})."
  if ssh_run "${remote_script}"; then
    return 0
  fi
  local exit_code=$?
  if [[ "${exit_code}" == "78" ]]; then
    warn "Skipped remote swap setup (no root access). Provision swap manually if frontend builds OOM."
    return 0
  fi
  err "Remote swap setup failed (exit ${exit_code})."
}

case "${1:-setup}" in
  --help|-h|help) usage ;;
  setup) check_prereqs; setup_swap ;;
  *) err "Unknown command: $1. Run --help." ;;
esac
