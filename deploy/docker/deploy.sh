#!/usr/bin/env bash
# [Input] docker-compose.yml, backend/Dockerfile, frontend/Dockerfile, frontend/nginx.conf.template.
# [Output] Docker Compose check/build/start/verify/stop/clean workflow for Ink & Memory.
# [Pos] platform release entry in deploy/docker/
# [Sync] 2026-06-12: add platform-scoped Docker release helper with help, dry-run, and check modes.
# [Sync] 2026-06-15: remove /ink-and-memory frontend path prefix from verification URL.
# [Sync] 2026-06-23: require Mihomo TUN config for the default backend proxy namespace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMPOSE_FILE="${DOCKER_COMPOSE_FILE:-${REPO_ROOT}/docker-compose.yml}"
CLASH_CONFIG_FILE="${CLASH_CONFIG_FILE:-${REPO_ROOT}/deploy/clash/config.yaml}"
DOCKER_FRONTEND_URL="${DOCKER_FRONTEND_URL:-http://localhost/}"
DOCKER_BACKEND_HEALTH_URL="${DOCKER_BACKEND_HEALTH_URL:-http://127.0.0.1:8765/api/health}"
export CLASH_CONFIG_FILE

DRY_RUN="${DRY_RUN:-0}"
COMMAND=""

usage() {
  cat <<'EOF'
Usage:
  ./deploy/docker/deploy.sh [--dry-run] <command>
  ./deploy/docker/deploy.sh --check
  ./deploy/docker/deploy.sh --help

Commands:
  check    Validate Docker, Compose, docker-compose.yml, and mounted config files.
  config   Render and validate the Compose configuration.
  build    Build frontend and backend images.
  start    Build and start the Compose stack in detached mode.
  deploy   Alias for start.
  verify   Check frontend and backend URLs.
  stop     Stop and remove Compose containers/networks.
  clean    Stop and remove Compose containers/networks. Set CLEAN_IMAGES=1 or CLEAN_VOLUMES=1 for broader cleanup.
  logs     Follow Compose logs.

Environment overrides:
  DOCKER_COMPOSE_FILE         default: docker-compose.yml
  CLASH_CONFIG_FILE           default: deploy/clash/config.yaml
  DOCKER_FRONTEND_URL         default: http://localhost/
  DOCKER_BACKEND_HEALTH_URL   default: http://127.0.0.1:8765/api/health
  CLEAN_IMAGES                default: 0; when 1, add --rmi local to clean
  CLEAN_VOLUMES               default: 0; when 1, add --volumes to clean
EOF
}

log() { printf '[docker] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err() { printf '[error] %s\n' "$*" >&2; exit 1; }

print_cmd() {
  printf '[dry-run]'
  printf ' %q' "$@"
  printf '\n'
}

run() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd "$@"
  else
    "$@"
  fi
}

require_command() {
  local name="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Would check command: ${name}"
    return 0
  fi
  command -v "${name}" >/dev/null 2>&1 || return 1
}

require_file() {
  local file="$1"
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Would check file: ${file}"
    return 0
  fi
  [[ -f "${file}" ]] || return 1
}

has_compose() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Would check Docker Compose plugin or docker-compose binary."
    return 0
  fi
  docker compose version >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    run docker compose -f "${COMPOSE_FILE}" "$@"
  else
    run docker-compose -f "${COMPOSE_FILE}" "$@"
  fi
}

check_prereqs() {
  local failed=0
  require_command docker || { warn "docker not found."; failed=1; }
  has_compose || { warn "Docker Compose not found."; failed=1; }
  require_file "${COMPOSE_FILE}" || { warn "Missing Compose file: ${COMPOSE_FILE}"; failed=1; }
  require_file "${CLASH_CONFIG_FILE}" || { warn "Missing Clash config: ${CLASH_CONFIG_FILE}. Copy your profile to deploy/clash/config.yaml and merge deploy/clash/config.tun-snippet.yaml."; failed=1; }
  require_file "${REPO_ROOT}/backend/.env" || { warn "Missing backend/.env. Compose env_file requires it."; failed=1; }
  require_file "${REPO_ROOT}/backend/models.json" || { warn "Missing backend/models.json. Compose mounts it read-only."; failed=1; }
  require_file "${REPO_ROOT}/backend/Dockerfile" || { warn "Missing backend/Dockerfile."; failed=1; }
  require_file "${REPO_ROOT}/frontend/Dockerfile" || { warn "Missing frontend/Dockerfile."; failed=1; }
  require_file "${REPO_ROOT}/frontend/nginx.conf.template" || { warn "Missing frontend/nginx.conf.template."; failed=1; }
  if [[ "${DRY_RUN}" != "1" ]]; then
    docker info >/dev/null 2>&1 || { warn "Docker daemon is not running."; failed=1; }
    [[ -c /dev/net/tun ]] || warn "/dev/net/tun not found on this host; Docker TUN may only work on a Linux host or a Docker environment that exposes the TUN device."
  else
    log "Would check Docker daemon with docker info."
    log "Would check /dev/net/tun for Mihomo TUN."
  fi
  if [[ "${failed}" == "1" ]]; then
    return 1
  fi
  log "Docker prerequisites look usable."
}

command_verify() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd curl -fsS --max-time 5 "${DOCKER_BACKEND_HEALTH_URL}"
    print_cmd curl -fsS --max-time 5 "${DOCKER_FRONTEND_URL}"
    return 0
  fi
  require_command curl || err "curl not found."
  curl -fsS --max-time 5 "${DOCKER_BACKEND_HEALTH_URL}" >/dev/null
  curl -fsS --max-time 5 "${DOCKER_FRONTEND_URL}" >/dev/null
  log "Docker verification passed."
}

command_clean() {
  local args=(down --remove-orphans)
  [[ "${CLEAN_IMAGES:-0}" == "1" ]] && args+=(--rmi local)
  [[ "${CLEAN_VOLUMES:-0}" == "1" ]] && args+=(--volumes)
  compose "${args[@]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --check)
      COMMAND="check"
      shift
      ;;
    *)
      if [[ -z "${COMMAND}" ]]; then
        COMMAND="$1"
        shift
      else
        err "Unexpected argument: $1"
      fi
      ;;
  esac
done

case "${COMMAND:-help}" in
  help) usage ;;
  check) check_prereqs ;;
  config) check_prereqs; compose config ;;
  build) check_prereqs; compose build ;;
  start|deploy|up) check_prereqs; compose up --build -d ;;
  verify) command_verify ;;
  stop) compose down ;;
  clean) command_clean ;;
  logs) compose logs -f --tail=100 ;;
  *) err "Unknown command: ${COMMAND}. Run --help." ;;
esac
