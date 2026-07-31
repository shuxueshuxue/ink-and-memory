#!/usr/bin/env bash
# [Input] Remote SSH connection env, rsync, deploy/remote-ssh/docker-compose.yml, backend/frontend Dockerfiles.
# [Output] Remote docker-compose deployment workflow over SSH.
# [Pos] platform release entry in deploy/remote-ssh/
# [Sync] 2026-06-12: add Remote SSH docker-compose deployment path for Docker-enabled servers.
# [Sync] 2026-06-12: align default container resources and filesystem paths with Cloud Run deployment.
# [Sync] 2026-06-12: propagate backend/frontend host ports into nginx setup and pin backend container port.
# [Sync] 2026-06-13: split deploy into explicit no-cache remote build and force-recreate up steps.
# [Sync] 2026-06-14: document Claude Code Docker nested sandbox behavior.
# [Sync] 2026-06-15: remove /ink-and-memory frontend path prefix from default verification URL.
# [Sync] 2026-06-16: align data maintenance wrappers with sync-data backup/upload/download commands.
# [Sync] 2026-06-23: add production OAuth/cookie defaults for split frontend/backend domains.
# [Sync] 2026-06-23: require Mihomo TUN config for the default backend proxy namespace.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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
REMOTE_FRONTEND_NGINX_HOST="${REMOTE_FRONTEND_NGINX_HOST:-}"
REMOTE_BACKEND_BIND_HOST="${REMOTE_BACKEND_BIND_HOST:-127.0.0.1}"
REMOTE_BACKEND_PORT="${REMOTE_BACKEND_PORT:-8765}"
REMOTE_BACKEND_CONTAINER_PORT="${REMOTE_BACKEND_CONTAINER_PORT:-8765}"
REMOTE_BACKEND_NGINX_HOST="${REMOTE_BACKEND_NGINX_HOST:-}"
REMOTE_BACKEND_IMAGE="${REMOTE_BACKEND_IMAGE:-ink-backend:remote}"
REMOTE_FRONTEND_IMAGE="${REMOTE_FRONTEND_IMAGE:-ink-frontend:remote}"
REMOTE_BACKEND_ROLLBACK_IMAGE="${REMOTE_BACKEND_ROLLBACK_IMAGE:-ink-backend:remote-rollback}"
REMOTE_FRONTEND_ROLLBACK_IMAGE="${REMOTE_FRONTEND_ROLLBACK_IMAGE:-ink-frontend:remote-rollback}"
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
REMOTE_SYNC_DATA="${REMOTE_SYNC_DATA:-0}"
REMOTE_SETUP_NGINX="${REMOTE_SETUP_NGINX:-auto}"
REMOTE_SETUP_STORAGE="${REMOTE_SETUP_STORAGE:-1}"
REMOTE_SETUP_SWAP="${REMOTE_SETUP_SWAP:-auto}"
REMOTE_SWAP_FILE="${REMOTE_SWAP_FILE:-/swapfile}"
REMOTE_SWAP_SIZE_MB="${REMOTE_SWAP_SIZE_MB:-2048}"
REMOTE_SETUP_SSL="${REMOTE_SETUP_SSL:-0}"
REMOTE_CLEAN_IMAGES="${REMOTE_CLEAN_IMAGES:-0}"
REMOTE_CLEAN_VOLUMES="${REMOTE_CLEAN_VOLUMES:-0}"
REMOTE_BUILD_PULL="${REMOTE_BUILD_PULL:-0}"
REMOTE_FRONTEND_SCHEME="${REMOTE_FRONTEND_SCHEME:-https}"
REMOTE_FRONTEND_PATH="${REMOTE_FRONTEND_PATH:-/}"
REMOTE_PUBLIC_HOST="${REMOTE_PUBLIC_HOST:-${REMOTE_SSH_HOST:-REMOTE_SSH_HOST}}"
REMOTE_VERIFY_FRONTEND_URL="${REMOTE_VERIFY_FRONTEND_URL:-http://127.0.0.1:${REMOTE_FRONTEND_PORT}${REMOTE_FRONTEND_PATH}}"
REMOTE_VERIFY_BACKEND_URL="${REMOTE_VERIFY_BACKEND_URL:-http://127.0.0.1:${REMOTE_BACKEND_PORT}/api/health}"

DRY_RUN="${DRY_RUN:-0}"
COMMAND=""

usage() {
  cat <<'EOF'
Usage:
  ./deploy/remote-ssh/deploy.sh [--dry-run] <command>
  ./deploy/remote-ssh/deploy.sh --check
  ./deploy/remote-ssh/deploy.sh --help

Commands:
  check     Validate local SSH/rsync, required files, remote docker-compose, and Docker daemon.
  plan      Print the remote deployment sequence and required env vars.
  sync      rsync repository files to REMOTE_APP_DIR without starting containers.
  config    Sync files, then run remote docker-compose config.
  build     Sync files, snapshot current images, then run remote docker-compose build --no-cache.
  deploy    One-command path: ensure nginx/storage when needed, sync files, build, start, and verify.
  install   Alias for deploy; kept for first-time one-command setup.
  start     Alias for deploy.
  verify    Run remote curl checks for backend health and frontend HTML.
  logs      Follow remote docker-compose logs.
  ps        Show remote docker-compose service status.
  rollback  Restart Compose with the previous image snapshot tags.
  stop      Stop and remove remote Compose containers/networks.
  clean     Stop and remove remote Compose containers/networks. Set REMOTE_CLEAN_IMAGES=1 or REMOTE_CLEAN_VOLUMES=1 for broader cleanup.
  setup-nginx    Install/update host nginx reverse proxy for the backend/frontend domains.
  setup-storage  Create/repair remote backend data, file-storage, agent-workspace, and backup directories.
  setup-swap     Ensure REMOTE_SWAP_SIZE_MB swap exists so the frontend build survives a 1G-RAM host.
  sync-data      Back up remote data locally, upload local backend/data, then force-recreate Compose services.
  backup-data    Download a timestamped remote backend/data backup without uploading local data.
  download-data  Back up current local backend/data, then download remote backend/data into local data.

Required environment:
  REMOTE_SSH_HOST       remote SSH host or IP
  REMOTE_APP_DIR        absolute directory on the remote server, e.g. /srv/ink-and-memory

Optional environment:
  REMOTE_SSH_USER       SSH user; omitted means use your local SSH default
  REMOTE_SSH_PORT       default: 22
  REMOTE_SSH_KEY        optional private key path
  REMOTE_DOCKER_COMPOSE_BIN  default: docker-compose
  REMOTE_FRONTEND_PORT  default: 8080, bound to localhost for host nginx
  REMOTE_FRONTEND_NGINX_HOST optional nginx upstream host override; defaults from REMOTE_FRONTEND_BIND_HOST
  REMOTE_BACKEND_PORT   default: 8765
  REMOTE_BACKEND_CONTAINER_PORT default: 8765, exported as backend PORT inside the container
  REMOTE_BACKEND_NGINX_HOST optional nginx upstream host override; defaults from REMOTE_BACKEND_BIND_HOST
  REMOTE_BACKEND_CPUS   default: 1.0, matching Cloud Run backend CPU
  REMOTE_BACKEND_MEMORY default: 1g, matching Cloud Run backend memory
  REMOTE_FRONTEND_CPUS  default: 1.0, matching Cloud Run frontend CPU
  REMOTE_FRONTEND_MEMORY default: 256m, matching Cloud Run frontend memory
  REMOTE_AGENT_CWD      default: /app/data/agent-workspace
  REMOTE_FILE_STORAGE_LOCAL_DIR default: /app/data/file-storage
  REMOTE_BACKEND_PUBLIC_ORIGIN default: https://ink-backend.suoxya.com
  REMOTE_FRONTEND_PUBLIC_ORIGIN default: https://ink-frontend.suoxya.com
  REMOTE_API_BASE_URL   browser-facing backend URL; default: REMOTE_BACKEND_PUBLIC_ORIGIN
  REMOTE_CORS_ALLOW_ORIGINS  default: REMOTE_FRONTEND_PUBLIC_ORIGIN
  REMOTE_CORS_ALLOW_CREDENTIALS default: true
  REMOTE_COOKIE_SECURE  default: true
  REMOTE_COOKIE_SAMESITE default: none
  REMOTE_CLASH_CONFIG_FILE default: ../../deploy/clash/config.yaml, resolved from deploy/remote-ssh/docker-compose.yml
  REMOTE_CLASH_IMAGE    default: metacubex/mihomo:latest
  REMOTE_SETUP_NGINX    default: auto; deploy installs/updates host nginx when localhost-bound ports need it
  REMOTE_SETUP_STORAGE  default: 1; deploy creates persistent backend/data directories before rsync
  REMOTE_SETUP_SSL      default: 0; set to 1 to let setup-nginx request certbot certificates
  REMOTE_SYNC_DATA      default: 0; when 1, sync backend/data to the remote server
  REMOTE_BUILD_PULL     default: 0; set to 1 to pull newer base images before build
EOF
}

log() { printf '[remote-ssh] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err() { printf '[error] %s\n' "$*" >&2; exit 1; }
quote() { printf '%q' "$1"; }

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

effective_remote_app_dir() {
  if [[ -n "${REMOTE_APP_DIR}" ]]; then
    printf '%s\n' "${REMOTE_APP_DIR}"
  else
    printf '%s\n' '${REMOTE_APP_DIR}'
  fi
}

ssh_target() {
  local host="${REMOTE_SSH_HOST:-REMOTE_SSH_HOST}"
  if [[ -n "${REMOTE_SSH_USER}" ]]; then
    printf '%s@%s\n' "${REMOTE_SSH_USER}" "${host}"
  else
    printf '%s\n' "${host}"
  fi
}

remote_frontend_url() {
  if [[ -n "${REMOTE_FRONTEND_URL:-}" ]]; then
    printf '%s\n' "${REMOTE_FRONTEND_URL}"
    return 0
  fi
  if [[ -n "${REMOTE_FRONTEND_PUBLIC_ORIGIN}" ]]; then
    printf '%s%s\n' "${REMOTE_FRONTEND_PUBLIC_ORIGIN%/}" "${REMOTE_FRONTEND_PATH}"
    return 0
  fi
  local port_suffix=""
  if [[ ! ( "${REMOTE_FRONTEND_SCHEME}" == "http" && "${REMOTE_FRONTEND_PORT}" == "80" ) \
        && ! ( "${REMOTE_FRONTEND_SCHEME}" == "https" && "${REMOTE_FRONTEND_PORT}" == "443" ) ]]; then
    port_suffix=":${REMOTE_FRONTEND_PORT}"
  fi
  printf '%s://%s%s%s\n' "${REMOTE_FRONTEND_SCHEME}" "${REMOTE_PUBLIC_HOST}" "${port_suffix}" "${REMOTE_FRONTEND_PATH}"
}

require_remote_config() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    [[ -n "${REMOTE_SSH_HOST}" ]] || log "Would require REMOTE_SSH_HOST."
    [[ -n "${REMOTE_APP_DIR}" ]] || log "Would require REMOTE_APP_DIR."
    return 0
  fi
  [[ -n "${REMOTE_SSH_HOST}" ]] || err "REMOTE_SSH_HOST is required."
  [[ -n "${REMOTE_APP_DIR}" ]] || err "REMOTE_APP_DIR is required."
  [[ "${REMOTE_APP_DIR}" == /* ]] || err "REMOTE_APP_DIR must be an absolute path."
}

require_remote_host_config() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    [[ -n "${REMOTE_SSH_HOST}" ]] || log "Would require REMOTE_SSH_HOST."
    return 0
  fi
  [[ -n "${REMOTE_SSH_HOST}" ]] || err "REMOTE_SSH_HOST is required."
}

ssh_run() {
  local cmd="$1"
  local target
  target="$(ssh_target)"
  local ssh_args=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && ssh_args+=(-i "${REMOTE_SSH_KEY}")
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd ssh "${ssh_args[@]}" "${target}" "${cmd}"
  else
    ssh "${ssh_args[@]}" "${target}" "${cmd}"
  fi
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
    REMOTE_SETUP_NGINX REMOTE_SETUP_STORAGE REMOTE_SETUP_SSL
    REMOTE_BUILD_PULL
  )
  local output="env" name
  for name in "${names[@]}"; do
    output+=" $(quote "${name}=${!name}")"
  done
  printf '%s\n' "${output}"
}

remote_compose() {
  require_remote_config
  local app_dir compose_cmd
  app_dir="$(effective_remote_app_dir)"
  compose_cmd="cd $(quote "${app_dir}") && $(remote_env_prefix) $(quote "${REMOTE_DOCKER_COMPOSE_BIN}") -p $(quote "${REMOTE_COMPOSE_PROJECT_NAME}") -f $(quote "${REMOTE_COMPOSE_FILE}")"
  local arg
  for arg in "$@"; do
    compose_cmd+=" $(quote "${arg}")"
  done
  ssh_run "${compose_cmd}"
}

check_local_prereqs() {
  local failed=0
  require_command ssh || { warn "ssh not found."; failed=1; }
  require_command rsync || { warn "rsync not found."; failed=1; }
  require_file "${REPO_ROOT}/deploy/remote-ssh/docker-compose.yml" || { warn "Missing remote compose file."; failed=1; }
  case "${REMOTE_CLASH_CONFIG_FILE}" in
    ../../deploy/clash/config.yaml|./deploy/clash/config.yaml|deploy/clash/config.yaml)
      require_file "${REPO_ROOT}/deploy/clash/config.yaml" || { warn "Missing Clash config: deploy/clash/config.yaml. Copy your profile there and merge deploy/clash/config.tun-snippet.yaml."; failed=1; }
      ;;
  esac
  require_file "${REPO_ROOT}/deploy/remote-ssh/setup-nginx.sh" || { warn "Missing remote nginx setup script."; failed=1; }
  require_file "${REPO_ROOT}/deploy/remote-ssh/setup-storage.sh" || { warn "Missing remote storage setup script."; failed=1; }
  require_file "${REPO_ROOT}/deploy/remote-ssh/sync-data.sh" || { warn "Missing remote data sync script."; failed=1; }
  require_file "${REPO_ROOT}/backend/.env" || { warn "Missing backend/.env. Remote Compose env_file requires it."; failed=1; }
  require_file "${REPO_ROOT}/backend/models.json" || { warn "Missing backend/models.json. Remote Compose mounts it read-only."; failed=1; }
  require_file "${REPO_ROOT}/backend/Dockerfile" || { warn "Missing backend/Dockerfile."; failed=1; }
  require_file "${REPO_ROOT}/frontend/Dockerfile" || { warn "Missing frontend/Dockerfile."; failed=1; }
  require_file "${REPO_ROOT}/frontend/docker-entrypoint.sh" || { warn "Missing frontend/docker-entrypoint.sh."; failed=1; }
  require_file "${REPO_ROOT}/frontend/nginx.conf.template" || { warn "Missing frontend/nginx.conf.template."; failed=1; }
  require_file "${REPO_ROOT}/frontend/public/runtime-config.template.js" || { warn "Missing frontend runtime-config template."; failed=1; }
  [[ "${failed}" == "0" ]]
}

check_remote_prereqs() {
  require_remote_config
  ssh_run "command -v $(quote "${REMOTE_DOCKER_COMPOSE_BIN}") >/dev/null && $(quote "${REMOTE_DOCKER_COMPOSE_BIN}") version >/dev/null && docker info >/dev/null && test -c /dev/net/tun"
}

check_prereqs() {
  check_local_prereqs
  check_remote_prereqs
  log "Remote SSH docker-compose prerequisites look usable."
}

command_plan() {
  cat <<EOF
Remote SSH docker-compose deploy:
  export REMOTE_SSH_HOST=<server-host-or-ip>
  export REMOTE_SSH_USER=<ssh-user>              # optional when your SSH config supplies it
  export REMOTE_APP_DIR=/srv/ink-and-memory      # required absolute remote path
  ./deploy/remote-ssh/deploy.sh deploy

Sequence:
  1. Check local ssh/rsync and required repository files.
  2. Check remote ${REMOTE_DOCKER_COMPOSE_BIN} and Docker daemon.
  3. Decide whether host nginx is needed; auto mode installs/updates it for localhost-bound frontend/backend ports.
  4. Create/repair remote backend/data, file-storage, agent-workspace, and backup directories.
  5. rsync repository files to REMOTE_APP_DIR, excluding backend/data by default.
  6. Tag current remote images as rollback images when they exist.
  7. Run remote docker-compose build, then docker-compose up -d --force-recreate.
  8. Verify backend and frontend from the remote server.

Resources:
  Backend defaults match Cloud Run backend: 1 CPU, 1g memory.
  Frontend defaults match Cloud Run frontend: 1 CPU, 256m memory.

Data:
  REMOTE_SETUP_STORAGE=1 by default, so deploy creates/repairs remote backend/data automatically.
  REMOTE_SYNC_DATA=0 by default, so remote backend/data contents are preserved during code deploys.
  Container /app/data is backed by REMOTE_APP_DIR/backend/data on the remote server.
  The backend auto-detects Linux container runtime and writes Claude Code's
  weaker nested Bash sandbox setting when the outer Docker container is the
  primary isolation boundary.
  Use sync-data only when you intentionally want local backend/data to overwrite/sync to the server.

API/nginx mode:
  REMOTE_SETUP_NGINX=auto by default; deploy installs/updates host nginx when the frontend is localhost-bound.
  Default REMOTE_API_BASE_URL is https://ink-backend.suoxya.com, so browser login/API calls never use the internal Docker hostname.
  Host-level nginx should route ink-backend.suoxya.com to 127.0.0.1:${REMOTE_BACKEND_PORT} and ink-frontend.suoxya.com to 127.0.0.1:${REMOTE_FRONTEND_PORT}.
  Override REMOTE_API_BASE_URL only when deploying to a different public backend origin.
  Backend egress routes through the default Mihomo TUN sidecar; backend remains reachable on REMOTE_BACKEND_PORT through the proxy container.

Rebuild controls:
  deploy always runs remote docker-compose build --no-cache before up.
  deploy always runs remote docker-compose up -d --force-recreate after build.
  Set REMOTE_BUILD_PULL=1 only when you also want to pull updated base images before build.
EOF
}

sync_files() {
  require_remote_config
  check_local_prereqs

  local app_dir
  app_dir="$(effective_remote_app_dir)"
  ssh_run "mkdir -p $(quote "${app_dir}") $(quote "${app_dir}/backend/data") $(quote "${app_dir}/backend/data/file-storage") $(quote "${app_dir}/backend/data/agent-workspace")"

  local ssh_transport="ssh -p $(quote "${REMOTE_SSH_PORT}")"
  [[ -n "${REMOTE_SSH_KEY}" ]] && ssh_transport+=" -i $(quote "${REMOTE_SSH_KEY}")"

  local target
  target="$(ssh_target):$(quote "${app_dir}")/"
  local rsync_args=(
    -az
    --delete
    --exclude '/.git/'
    --exclude '/.env'
    --exclude '/.cloud-env'
    --exclude '/.storage-env'
    --exclude '/logs/'
    --exclude '/frontend/node_modules/'
    --exclude '/frontend/dist/'
    --exclude '/node_modules/'
    --exclude '**/__pycache__/'
    --exclude '.DS_Store'
    -e "${ssh_transport}"
  )
  if [[ "${REMOTE_SYNC_DATA}" != "1" ]]; then
    rsync_args+=(--exclude '/backend/data/')
  fi

  log "Syncing repository to $(ssh_target):${app_dir}"
  run rsync "${rsync_args[@]}" "${REPO_ROOT}/" "${target}"
}

snapshot_images() {
  require_remote_config
  local cmd
  cmd="docker image inspect $(quote "${REMOTE_BACKEND_IMAGE}") >/dev/null 2>&1 && docker tag $(quote "${REMOTE_BACKEND_IMAGE}") $(quote "${REMOTE_BACKEND_ROLLBACK_IMAGE}") || true"
  cmd+="; docker image inspect $(quote "${REMOTE_FRONTEND_IMAGE}") >/dev/null 2>&1 && docker tag $(quote "${REMOTE_FRONTEND_IMAGE}") $(quote "${REMOTE_FRONTEND_ROLLBACK_IMAGE}") || true"
  ssh_run "${cmd}"
}

remote_build() {
  # local args=(build --no-cache)
  local args=(build )
  [[ "${REMOTE_BUILD_PULL}" == "1" ]] && args+=(--pull)
  log "Building remote Compose images with --no-cache. Pull base images: ${REMOTE_BUILD_PULL}."
  remote_compose "${args[@]}"
}

remote_up() {
  local args=(up -d --force-recreate)
  log "Starting remote Compose services with --force-recreate."
  remote_compose "${args[@]}"
}

should_setup_nginx() {
  case "${REMOTE_SETUP_NGINX}" in
    1|true|yes|on) return 0 ;;
    0|false|no|off) return 1 ;;
    auto)
      [[ "${REMOTE_FRONTEND_BIND_HOST}" == "127.0.0.1" || "${REMOTE_BACKEND_BIND_HOST}" == "127.0.0.1" ]]
      ;;
    *) err "REMOTE_SETUP_NGINX must be auto, 1, or 0." ;;
  esac
}

should_setup_storage() {
  case "${REMOTE_SETUP_STORAGE}" in
    1|true|yes|on|auto) return 0 ;;
    0|false|no|off) return 1 ;;
    *) err "REMOTE_SETUP_STORAGE must be 1, 0, or auto." ;;
  esac
}

should_setup_swap() {
  case "${REMOTE_SETUP_SWAP}" in
    1|true|yes|on|auto) return 0 ;;
    0|false|no|off) return 1 ;;
    *) err "REMOTE_SETUP_SWAP must be 1, 0, or auto." ;;
  esac
}

command_setup_nginx() {
  require_remote_host_config
  if should_setup_nginx; then
    log "Ensuring host nginx reverse proxy for ${REMOTE_BACKEND_PUBLIC_ORIGIN} and ${REMOTE_FRONTEND_PUBLIC_ORIGIN}."
    env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_FRONTEND_BIND_HOST="${REMOTE_FRONTEND_BIND_HOST}" \
      REMOTE_FRONTEND_PORT="${REMOTE_FRONTEND_PORT}" \
      REMOTE_FRONTEND_NGINX_HOST="${REMOTE_FRONTEND_NGINX_HOST}" \
      REMOTE_BACKEND_BIND_HOST="${REMOTE_BACKEND_BIND_HOST}" \
      REMOTE_BACKEND_PORT="${REMOTE_BACKEND_PORT}" \
      REMOTE_BACKEND_NGINX_HOST="${REMOTE_BACKEND_NGINX_HOST}" \
      WITH_SSL="${REMOTE_SETUP_SSL}" \
      "${SCRIPT_DIR}/setup-nginx.sh"
  else
    log "Skipping host nginx setup because REMOTE_SETUP_NGINX=${REMOTE_SETUP_NGINX}."
  fi
}

command_setup_storage() {
  require_remote_config
  if should_setup_storage; then
    log "Ensuring remote persistent storage under ${REMOTE_APP_DIR%/}/backend/data."
    env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_APP_DIR="${REMOTE_APP_DIR}" \
      "${SCRIPT_DIR}/setup-storage.sh"
  else
    log "Skipping remote storage setup because REMOTE_SETUP_STORAGE=${REMOTE_SETUP_STORAGE}."
  fi
}

command_setup_swap() {
  require_remote_host_config
  if should_setup_swap; then
    log "Ensuring at least ${REMOTE_SWAP_SIZE_MB}MB remote swap so the frontend build does not OOM."
    env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_SWAP_FILE="${REMOTE_SWAP_FILE}" \
      REMOTE_SWAP_SIZE_MB="${REMOTE_SWAP_SIZE_MB}" \
      "${SCRIPT_DIR}/setup-swap.sh"
  else
    log "Skipping remote swap setup because REMOTE_SETUP_SWAP=${REMOTE_SETUP_SWAP}."
  fi
}

command_deploy() {
  check_prereqs
  command_setup_nginx
  command_setup_storage
  command_setup_swap
  sync_files
  snapshot_images
  remote_build
  remote_up
  remote_compose ps
  command_verify
  log "Remote frontend: $(remote_frontend_url)"
}

command_verify() {
  require_remote_config
  local cmd
  cmd="curl -fsS --max-time 10 $(quote "${REMOTE_VERIFY_BACKEND_URL}") >/dev/null"
  cmd+=" && curl -fsS --max-time 10 $(quote "${REMOTE_VERIFY_FRONTEND_URL}") >/dev/null"
  ssh_run "${cmd}"
  log "Remote verification passed."
}

command_rollback() {
  require_remote_config
  local old_backend="${REMOTE_BACKEND_IMAGE}"
  local old_frontend="${REMOTE_FRONTEND_IMAGE}"
  REMOTE_BACKEND_IMAGE="${REMOTE_BACKEND_ROLLBACK_IMAGE}"
  REMOTE_FRONTEND_IMAGE="${REMOTE_FRONTEND_ROLLBACK_IMAGE}"
  remote_compose up -d --no-build
  remote_compose ps
  command_verify
  REMOTE_BACKEND_IMAGE="${old_backend}"
  REMOTE_FRONTEND_IMAGE="${old_frontend}"
  log "Rollback started from snapshot images. Data files were not rolled back."
}

command_clean() {
  local args=(down --remove-orphans)
  [[ "${REMOTE_CLEAN_IMAGES}" == "1" ]] && args+=(--rmi local)
  [[ "${REMOTE_CLEAN_VOLUMES}" == "1" ]] && args+=(--volumes)
  remote_compose "${args[@]}"
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
  plan) command_plan ;;
  sync) sync_files ;;
  config) check_prereqs; sync_files; remote_compose config ;;
  build) check_prereqs; sync_files; snapshot_images; remote_build ;;
  deploy|install|start|up) command_deploy ;;
  verify) command_verify ;;
  logs) remote_compose logs -f --tail=100 ;;
  ps) remote_compose ps ;;
  rollback) command_rollback ;;
  stop) remote_compose down ;;
  clean) command_clean ;;
  setup-nginx) command_setup_nginx ;;
  setup-storage)
    exec env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_APP_DIR="${REMOTE_APP_DIR}" \
      "${SCRIPT_DIR}/setup-storage.sh"
    ;;
  setup-swap) command_setup_swap ;;
  sync-data)
    exec env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_APP_DIR="${REMOTE_APP_DIR}" \
      REMOTE_DOCKER_COMPOSE_BIN="${REMOTE_DOCKER_COMPOSE_BIN}" \
      REMOTE_COMPOSE_FILE="${REMOTE_COMPOSE_FILE}" \
      REMOTE_COMPOSE_PROJECT_NAME="${REMOTE_COMPOSE_PROJECT_NAME}" \
      REMOTE_CLASH_CONFIG_FILE="${REMOTE_CLASH_CONFIG_FILE}" \
      REMOTE_CLASH_IMAGE="${REMOTE_CLASH_IMAGE}" \
      REMOTE_CLASH_CONTAINER="${REMOTE_CLASH_CONTAINER}" \
      REMOTE_CLASH_CONTROLLER_BIND_HOST="${REMOTE_CLASH_CONTROLLER_BIND_HOST}" \
      REMOTE_CLASH_CONTROLLER_PORT="${REMOTE_CLASH_CONTROLLER_PORT}" \
      REMOTE_CLASH_DASHBOARD_BIND_HOST="${REMOTE_CLASH_DASHBOARD_BIND_HOST}" \
      REMOTE_CLASH_DASHBOARD_PORT="${REMOTE_CLASH_DASHBOARD_PORT}" \
      "${SCRIPT_DIR}/sync-data.sh" upload
    ;;
  backup-data|backup)
    exec env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_APP_DIR="${REMOTE_APP_DIR}" \
      "${SCRIPT_DIR}/sync-data.sh" backup
    ;;
  download-data|download)
    exec env DRY_RUN="${DRY_RUN}" \
      REMOTE_SSH_HOST="${REMOTE_SSH_HOST}" \
      REMOTE_SSH_USER="${REMOTE_SSH_USER}" \
      REMOTE_SSH_PORT="${REMOTE_SSH_PORT}" \
      REMOTE_SSH_KEY="${REMOTE_SSH_KEY}" \
      REMOTE_APP_DIR="${REMOTE_APP_DIR}" \
      "${SCRIPT_DIR}/sync-data.sh" download
    ;;
  *) err "Unknown command: ${COMMAND}. Run --help." ;;
esac
