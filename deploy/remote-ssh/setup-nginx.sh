#!/usr/bin/env bash
# [Input] deploy/remote-ssh/nginx/ink-and-memory.conf, REMOTE_SSH_HOST env.
# [Output] Installs and configures host-level nginx reverse proxy on remote server.
# [Pos] nginx setup companion script in deploy/remote-ssh/
# [Sync] 2026-06-12: initial nginx setup script for ink-backend.suoxya.com / ink-frontend.suoxya.com.
# [Sync] 2026-06-12: use SCP-specific port args so REMOTE_SSH_PORT is not treated as a local file.
# [Sync] 2026-06-12: preflight host port 80 and reload unmanaged nginx listeners safely.
# [Sync] 2026-06-12: render upstream ports from Remote SSH deploy env instead of static defaults.
# [Sync] 2026-06-12: disable stale same-domain nginx configs before testing the deployed site.
# [Sync] 2026-07-06: also render/upload/enable the apex suoxya.com site (nginx/suoxya-root.conf).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_CONF_SRC="${SCRIPT_DIR}/nginx/ink-and-memory.conf"
NGINX_CONF_NAME="ink-and-memory"
APEX_CONF_SRC="${SCRIPT_DIR}/nginx/suoxya-root.conf"
APEX_CONF_NAME="suoxya-root"

REMOTE_SSH_HOST="${REMOTE_SSH_HOST:-}"
REMOTE_SSH_USER="${REMOTE_SSH_USER:-}"
REMOTE_SSH_PORT="${REMOTE_SSH_PORT:-22}"
REMOTE_SSH_KEY="${REMOTE_SSH_KEY:-}"
REMOTE_FRONTEND_BIND_HOST="${REMOTE_FRONTEND_BIND_HOST:-127.0.0.1}"
REMOTE_FRONTEND_PORT="${REMOTE_FRONTEND_PORT:-8080}"
REMOTE_FRONTEND_NGINX_HOST="${REMOTE_FRONTEND_NGINX_HOST:-}"
REMOTE_BACKEND_BIND_HOST="${REMOTE_BACKEND_BIND_HOST:-127.0.0.1}"
REMOTE_BACKEND_PORT="${REMOTE_BACKEND_PORT:-8765}"
REMOTE_BACKEND_NGINX_HOST="${REMOTE_BACKEND_NGINX_HOST:-}"
WITH_SSL="${WITH_SSL:-0}"
DRY_RUN="${DRY_RUN:-0}"

usage() {
  cat <<'EOF'
Usage:
  REMOTE_SSH_HOST=39.97.252.88 ./deploy/remote-ssh/setup-nginx.sh
  REMOTE_SSH_HOST=39.97.252.88 WITH_SSL=1 ./deploy/remote-ssh/setup-nginx.sh

Installs nginx on the remote server, deploys the Ink & Memory virtual host config,
and enables the site.  Optionally provisions Let's Encrypt SSL certificates.

Environment:
  REMOTE_SSH_HOST        required — remote server host or IP
  REMOTE_SSH_USER        SSH user; omitted means use your local SSH default
  REMOTE_SSH_PORT        SSH port (default: 22)
  REMOTE_SSH_KEY         optional private key path
  REMOTE_BACKEND_PORT    backend host port used by nginx upstream (default: 8765)
  REMOTE_FRONTEND_PORT   frontend host port used by nginx upstream (default: 8080)
  REMOTE_BACKEND_NGINX_HOST   optional backend upstream host override
  REMOTE_FRONTEND_NGINX_HOST  optional frontend upstream host override
  WITH_SSL               default: 0; set to 1 to run certbot after nginx setup
  DRY_RUN                default: 0; set to 1 to print commands without executing
EOF
}

log()  { printf '[setup-nginx] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*" >&2; }
err()  { printf '[error] %s\n' "$*" >&2; exit 1; }
print_cmd() {
  printf '[dry-run]'
  printf ' %q' "$@"
  printf '\n'
}

ssh_target() {
  local host="${REMOTE_SSH_HOST:-REMOTE_SSH_HOST}"
  if [[ -n "${REMOTE_SSH_USER}" ]]; then
    printf '%s@%s\n' "${REMOTE_SSH_USER}" "${host}"
  else
    printf '%s\n' "${host}"
  fi
}

nginx_upstream_host() {
  local bind_host="$1"
  case "${bind_host}" in
    ""|"0.0.0.0"|"::"|"[::]")
      bind_host="127.0.0.1"
      ;;
  esac
  if [[ "${bind_host}" == *:* && "${bind_host}" != \[*\] ]]; then
    printf '[%s]\n' "${bind_host}"
  else
    printf '%s\n' "${bind_host}"
  fi
}

validate_port() {
  local label="$1"
  local port="$2"
  if [[ ! "${port}" =~ ^[0-9]+$ ]]; then
    err "${label} must be a numeric TCP port, got: ${port}"
  fi
  local port_number=$((10#${port}))
  if (( port_number < 1 || port_number > 65535 )); then
    err "${label} must be between 1 and 65535, got: ${port}"
  fi
}

validate_nginx_host() {
  local label="$1"
  local host="$2"
  if [[ ! "${host}" =~ ^[A-Za-z0-9._-]+$ && ! "${host}" =~ ^\[[0-9A-Fa-f:]+\]$ ]]; then
    err "${label} contains unsupported characters for an nginx upstream host: ${host}"
  fi
}

render_nginx_conf() {
  local output="$1"
  local source="${2:-${NGINX_CONF_SRC}}"
  local backend_host="${REMOTE_BACKEND_NGINX_HOST:-}"
  local frontend_host="${REMOTE_FRONTEND_NGINX_HOST:-}"
  [[ -n "${backend_host}" ]] || backend_host="$(nginx_upstream_host "${REMOTE_BACKEND_BIND_HOST}")"
  [[ -n "${frontend_host}" ]] || frontend_host="$(nginx_upstream_host "${REMOTE_FRONTEND_BIND_HOST}")"

  validate_port "REMOTE_BACKEND_PORT" "${REMOTE_BACKEND_PORT}"
  validate_port "REMOTE_FRONTEND_PORT" "${REMOTE_FRONTEND_PORT}"
  validate_nginx_host "REMOTE_BACKEND_NGINX_HOST" "${backend_host}"
  validate_nginx_host "REMOTE_FRONTEND_NGINX_HOST" "${frontend_host}"

  log "Rendering nginx upstreams: backend=${backend_host}:${REMOTE_BACKEND_PORT}, frontend=${frontend_host}:${REMOTE_FRONTEND_PORT}"
  sed \
    -e "s|127\\.0\\.0\\.1:8765|${backend_host}:${REMOTE_BACKEND_PORT}|g" \
    -e "s|127\\.0\\.0\\.1:8080|${frontend_host}:${REMOTE_FRONTEND_PORT}|g" \
    "${source}" >"${output}"
}

# ── Prerequisites check ───────────────────────────────────────────────────────

check_prereqs() {
  local failed=0
  [[ -n "${REMOTE_SSH_HOST}" ]] || { warn "REMOTE_SSH_HOST is required."; failed=1; }
  [[ -f "${NGINX_CONF_SRC}" ]] || { warn "Missing nginx config: ${NGINX_CONF_SRC}"; failed=1; }
  [[ -f "${APEX_CONF_SRC}" ]] || { warn "Missing apex nginx config: ${APEX_CONF_SRC}"; failed=1; }
  command -v ssh >/dev/null 2>&1 || { warn "ssh not found."; failed=1; }
  command -v scp >/dev/null 2>&1 || { warn "scp not found."; failed=1; }
  [[ "${failed}" == "0" ]]
}

# ── Remote command helpers ────────────────────────────────────────────────────

remote_exec() {
  local cmd="$1"
  local target
  target="$(ssh_target)"
  local args=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && args+=(-i "${REMOTE_SSH_KEY}")
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd ssh "${args[@]}" "${target}" "${cmd}"
  else
    ssh "${args[@]}" "${target}" "${cmd}"
  fi
}

remote_script() {
  local target
  target="$(ssh_target)"
  local args=(-p "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && args+=(-i "${REMOTE_SSH_KEY}")
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd ssh "${args[@]}" "${target}" "bash -s <<REMOTE ... REMOTE"
  else
    ssh "${args[@]}" "${target}" 'bash -s'
  fi
}

# ── SCP helper ────────────────────────────────────────────────────────────────

scp_file() {
  local src="$1"
  local dst="$2"
  local target
  target="$(ssh_target)"
  local args=(-P "${REMOTE_SSH_PORT}")
  [[ -n "${REMOTE_SSH_KEY}" ]] && args+=(-i "${REMOTE_SSH_KEY}")
  if [[ "${DRY_RUN}" == "1" ]]; then
    print_cmd scp "${args[@]}" "${src}" "${target}:${dst}"
  else
    scp "${args[@]}" "${src}" "${target}:${dst}"
  fi
}

# ── Main setup ────────────────────────────────────────────────────────────────

setup_nginx() {
  log "Deploying nginx config to $(ssh_target)..."

  # 1) Render the nginx config from the same host ports used by remote Compose,
  # then copy it to the remote server /tmp.
  local rendered_conf
  rendered_conf="$(mktemp "${TMPDIR:-/tmp}/ink-and-memory-nginx.XXXXXX")"
  render_nginx_conf "${rendered_conf}"
  if ! scp_file "${rendered_conf}" "/tmp/${NGINX_CONF_NAME}.conf"; then
    rm -f "${rendered_conf}"
    return 1
  fi
  rm -f "${rendered_conf}"

  # 1b) Render and upload the apex (suoxya.com) site config the same way.
  local rendered_apex
  rendered_apex="$(mktemp "${TMPDIR:-/tmp}/suoxya-root-nginx.XXXXXX")"
  render_nginx_conf "${rendered_apex}" "${APEX_CONF_SRC}"
  if ! scp_file "${rendered_apex}" "/tmp/${APEX_CONF_NAME}.conf"; then
    rm -f "${rendered_apex}"
    return 1
  fi
  rm -f "${rendered_apex}"

  # 2) Install nginx, enable config, test, and reload via a single remote script
  remote_script <<'REMOTE'
set -euo pipefail

CONF_NAME="ink-and-memory"
TMP_CONF="/tmp/${CONF_NAME}.conf"
SITES_AVAILABLE="/etc/nginx/sites-available/${CONF_NAME}"
SITES_ENABLED="/etc/nginx/sites-enabled/${CONF_NAME}"
APEX_NAME="suoxya-root"
TMP_APEX_CONF="/tmp/${APEX_NAME}.conf"
APEX_AVAILABLE="/etc/nginx/sites-available/${APEX_NAME}"
APEX_ENABLED="/etc/nginx/sites-enabled/${APEX_NAME}"
DEFAULT_SITE="/etc/nginx/sites-enabled/default"
DOMAIN_PATTERN="ink-backend\.suoxya\.com|ink-frontend\.suoxya\.com"
POLICY_RC_D_CREATED=0

cleanup_policy_rc_d() {
  if [[ "${POLICY_RC_D_CREATED}" == "1" ]]; then
    rm -f /usr/sbin/policy-rc.d
  fi
}
trap cleanup_policy_rc_d EXIT

port_listeners() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltnp "sport = :${port}" 2>/dev/null || true
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  elif command -v netstat >/dev/null 2>&1; then
    netstat -ltnp 2>/dev/null | awk -v port=":${port}" '$4 ~ port "$" { print }' || true
  else
    echo "[warn] Cannot inspect port ${port}: ss, lsof, and netstat are unavailable." >&2
    return 0
  fi
}

port_has_listener() {
  [[ -n "$(port_listeners "$1")" ]]
}

port_owner_is_nginx() {
  port_listeners "$1" | grep -Eiq 'nginx'
}

check_proxy_port() {
  local port="$1"
  local listeners
  listeners="$(port_listeners "${port}")"
  if [[ -z "${listeners}" ]]; then
    echo "[setup-nginx] Port ${port} is available."
    return 0
  fi

  echo "[setup-nginx] Port ${port} is already in use:"
  printf '%s\n' "${listeners}" | sed 's/^/[setup-nginx]   /'
  if printf '%s\n' "${listeners}" | grep -Eiq 'nginx'; then
    echo "[setup-nginx] Existing nginx listener detected; setup will update config and reload it."
    return 0
  fi

  echo "[error] Port ${port} is occupied by a non-nginx process."
  echo "[error] Free port ${port}, or run deploy with REMOTE_SETUP_NGINX=0 if another reverse proxy manages these domains."
  exit 1
}

install_nginx_with_apt() {
  if [[ ! -e /usr/sbin/policy-rc.d ]]; then
    echo "[setup-nginx] Temporarily preventing apt from auto-starting nginx before config is ready."
    printf '#!/bin/sh\nexit 101\n' >/usr/sbin/policy-rc.d
    chmod +x /usr/sbin/policy-rc.d
    POLICY_RC_D_CREATED=1
  fi

  set +e
  apt-get update -qq
  local update_status=$?
  if [[ "${update_status}" == "0" ]]; then
    apt-get install -y -qq nginx
  fi
  local install_status=$?
  set -e
  cleanup_policy_rc_d
  POLICY_RC_D_CREATED=0

  if [[ "${update_status}" != "0" || "${install_status}" != "0" ]]; then
    echo "[error] Failed to install nginx via apt-get."
    exit 1
  fi
}

list_conflicting_domain_configs() {
  local available_target enabled_target
  available_target="$(readlink -f "${SITES_AVAILABLE}" 2>/dev/null || printf '%s' "${SITES_AVAILABLE}")"
  enabled_target="$(readlink -f "${SITES_ENABLED}" 2>/dev/null || printf '%s' "${SITES_ENABLED}")"

  local roots=()
  [[ -d /etc/nginx/conf.d ]] && roots+=("/etc/nginx/conf.d")
  [[ -d /etc/nginx/sites-enabled ]] && roots+=("/etc/nginx/sites-enabled")
  [[ "${#roots[@]}" == "0" ]] && return 0

  local path resolved
  while IFS= read -r -d '' path; do
    resolved="$(readlink -f "${path}" 2>/dev/null || printf '%s' "${path}")"
    if [[ "${path}" == "${SITES_AVAILABLE}" || "${path}" == "${SITES_ENABLED}" \
      || "${resolved}" == "${available_target}" || "${resolved}" == "${enabled_target}" ]]; then
      continue
    fi
    if [[ -r "${path}" ]] && grep -Eq "server_name[[:space:]][^;]*(${DOMAIN_PATTERN})" "${path}"; then
      printf '%s\n' "${path}"
    fi
  done < <(find "${roots[@]}" -maxdepth 1 \( -type f -o -type l \) -print0 2>/dev/null)
}

warn_conflicting_domain_configs() {
  local conflicts
  conflicts="$(list_conflicting_domain_configs || true)"
  if [[ -n "${conflicts}" ]]; then
    echo "[warn] Existing enabled nginx config files also define Ink & Memory domains:"
    printf '%s\n' "${conflicts}" | sed 's/^/[warn]   /'
    echo "[warn] If nginx reports conflicting server_name warnings, merge/remove those files or use REMOTE_SETUP_NGINX=0 when nginx is managed elsewhere."
  fi
}

disable_conflicting_domain_configs() {
  local conflicts
  conflicts="$(list_conflicting_domain_configs || true)"
  [[ -n "${conflicts}" ]] || return 0

  local backup_dir="/etc/nginx/disabled-ink-and-memory-$(date +%Y%m%d%H%M%S)"
  echo "[setup-nginx] Disabling stale Ink & Memory nginx configs into ${backup_dir}:"
  mkdir -p "${backup_dir}"

  local path
  while IFS= read -r path; do
    [[ -n "${path}" ]] || continue
    echo "[setup-nginx]   ${path}"
    mv "${path}" "${backup_dir}/$(basename "${path}")"
  done <<<"${conflicts}"
}

activate_nginx() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable nginx
    if systemctl is-active --quiet nginx; then
      echo "[setup-nginx] Reloading active nginx.service..."
      systemctl reload nginx
      return 0
    fi

    if port_has_listener 80; then
      if port_owner_is_nginx 80; then
        echo "[setup-nginx] nginx.service is inactive, but nginx already owns port 80; reloading via nginx -s reload."
        if ! nginx -s reload; then
          echo "[error] Existing nginx owns port 80, but nginx -s reload failed."
          echo "[error] Check whether this nginx process is managed outside /etc/nginx, or run deploy with REMOTE_SETUP_NGINX=0."
          exit 1
        fi
        return 0
      fi
      echo "[error] nginx.service is inactive and port 80 is owned by another process:"
      port_listeners 80 | sed 's/^/[error]   /'
      exit 1
    fi

    echo "[setup-nginx] Starting nginx.service..."
    if ! systemctl start nginx; then
      echo "[error] Failed to start nginx.service. Current port 80 listeners:"
      port_listeners 80 | sed 's/^/[error]   /'
      exit 1
    fi
  else
    if port_has_listener 80 && port_owner_is_nginx 80; then
      echo "[setup-nginx] Reloading existing nginx process via nginx -s reload..."
      if ! nginx -s reload; then
        echo "[error] Existing nginx owns port 80, but nginx -s reload failed."
        echo "[error] Check whether this nginx process is managed outside /etc/nginx, or run deploy with REMOTE_SETUP_NGINX=0."
        exit 1
      fi
    else
      service nginx reload || service nginx start
    fi
  fi
}

echo "[setup-nginx] Checking OS package manager..."
check_proxy_port 80

# Detect OS and install nginx
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  if ! dpkg -s nginx >/dev/null 2>&1; then
    echo "[setup-nginx] Installing nginx via apt-get..."
    install_nginx_with_apt
  else
    echo "[setup-nginx] nginx already installed."
  fi
elif command -v yum >/dev/null 2>&1; then
  if ! rpm -q nginx >/dev/null 2>&1; then
    echo "[setup-nginx] Installing nginx via yum..."
    yum install -y nginx
  else
    echo "[setup-nginx] nginx already installed."
  fi
elif command -v dnf >/dev/null 2>&1; then
  if ! rpm -q nginx >/dev/null 2>&1; then
    echo "[setup-nginx] Installing nginx via dnf..."
    dnf install -y nginx
  else
    echo "[setup-nginx] nginx already installed."
  fi
else
  echo "[error] Cannot detect package manager (apt/yum/dnf). Please install nginx manually."
  exit 1
fi

# Ensure sites-available / sites-enabled directories exist
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

# Remove default site if present to avoid conflicts
if [[ -f "${DEFAULT_SITE}" ]] || [[ -L "${DEFAULT_SITE}" ]]; then
  echo "[setup-nginx] Removing default site: ${DEFAULT_SITE}"
  rm -f "${DEFAULT_SITE}"
fi

# Deploy config
echo "[setup-nginx] Deploying ${SITES_AVAILABLE}..."
cp "${TMP_CONF}" "${SITES_AVAILABLE}"
rm -f "${TMP_CONF}"

# Create symlink if not already present
if [[ ! -L "${SITES_ENABLED}" ]] && [[ ! -f "${SITES_ENABLED}" ]]; then
  echo "[setup-nginx] Enabling site: ${SITES_ENABLED}"
  ln -s "${SITES_AVAILABLE}" "${SITES_ENABLED}"
else
  echo "[setup-nginx] Site already enabled: ${SITES_ENABLED}"
fi

# Deploy apex (suoxya.com) config if it was uploaded
if [[ -f "${TMP_APEX_CONF}" ]]; then
  echo "[setup-nginx] Deploying ${APEX_AVAILABLE}..."
  cp "${TMP_APEX_CONF}" "${APEX_AVAILABLE}"
  rm -f "${TMP_APEX_CONF}"
  if [[ ! -L "${APEX_ENABLED}" ]] && [[ ! -f "${APEX_ENABLED}" ]]; then
    echo "[setup-nginx] Enabling site: ${APEX_ENABLED}"
    ln -s "${APEX_AVAILABLE}" "${APEX_ENABLED}"
  else
    echo "[setup-nginx] Site already enabled: ${APEX_ENABLED}"
  fi
fi

# Ensure sites-enabled include is in nginx.conf
if ! grep -q 'include /etc/nginx/sites-enabled/\*' /etc/nginx/nginx.conf 2>/dev/null; then
  echo "[setup-nginx] Adding sites-enabled include to nginx.conf..."
  # Insert before the closing } of the http block
  sed -i '/^http {/,/^}/{
    /^}/i\    include /etc/nginx/sites-enabled/*;
  }' /etc/nginx/nginx.conf
fi

# Test configuration
echo "[setup-nginx] Testing nginx configuration..."
warn_conflicting_domain_configs
disable_conflicting_domain_configs
nginx -t

# Enable and start nginx
activate_nginx

echo "[setup-nginx] Nginx setup complete."
echo "[setup-nginx] Verify: curl -H 'Host: ink-backend.suoxya.com' http://127.0.0.1/api/health"
echo "[setup-nginx] Verify: curl -H 'Host: ink-frontend.suoxya.com' http://127.0.0.1/"
echo "[setup-nginx] Verify: curl -H 'Host: suoxya.com' http://127.0.0.1/"

REMOTE

  log "Nginx config deployed successfully."
}

setup_ssl() {
  log "Setting up Let's Encrypt SSL certificates..."

  remote_script <<'REMOTE'
set -euo pipefail

# Install certbot if not present
if command -v certbot >/dev/null 2>&1; then
  echo "[setup-ssl] certbot already installed."
else
  echo "[setup-ssl] Installing certbot..."
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx
  elif command -v yum >/dev/null 2>&1; then
    yum install -y certbot python3-certbot-nginx
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y certbot python3-certbot-nginx
  fi
fi

echo "[setup-ssl] Requesting certificates for all domains..."
certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email "${CERTBOT_EMAIL:-admin@suoxya.com}" \
  -d suoxya.com \
  -d ink-backend.suoxya.com \
  -d ink-frontend.suoxya.com

echo "[setup-ssl] Certificates installed. Nginx reloaded with SSL."
REMOTE

  log "SSL setup complete."
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
  check_prereqs

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "DRY RUN — commands will be printed but not executed."
  fi

  setup_nginx

  if [[ "${WITH_SSL}" == "1" ]]; then
    setup_ssl
    log "Next: uncomment the SSL server blocks in /etc/nginx/sites-available/ink-and-memory"
    log "      and the HTTP→HTTPS redirect block, then run: nginx -t && systemctl reload nginx"
  fi

  cat <<EOF

Done. The main deploy script now runs nginx setup automatically in auto mode.
For a complete install/deploy, run:

    export REMOTE_SSH_HOST=39.97.252.88
    export REMOTE_APP_DIR=/srv/ink-and-memory
    ./deploy/remote-ssh/deploy.sh deploy

EOF
}

main
