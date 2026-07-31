#!/usr/bin/env bash
# =============================================================================
# Ink & Memory — Remote Server Nginx Setup
# =============================================================================
# Run this script ON THE REMOTE SERVER (root@39.97.252.88) to install and
# configure nginx as a reverse proxy for the Docker containers.
#
# Usage:
#   chmod +x setup-nginx.sh
#   sudo ./setup-nginx.sh
#   # After SSL certs are provisioned:
#   sudo ./setup-nginx.sh --enable-ssl
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_CONF_SRC="${SCRIPT_DIR}/ink-and-memory.conf"
NGINX_SITE_NAME="ink-and-memory"
NGINX_AVAILABLE="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"

# Apex domain (suoxya.com) site — serves the same content as the frontend
# subdomain by proxying to the real service behind it. Depends on the map and
# upstream blocks defined in ink-and-memory.conf.
APEX_CONF_SRC="${SCRIPT_DIR}/suoxya-root.conf"
APEX_SITE_NAME="suoxya-root"
APEX_AVAILABLE="/etc/nginx/sites-available/${APEX_SITE_NAME}"
APEX_ENABLED="/etc/nginx/sites-enabled/${APEX_SITE_NAME}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { printf "${GREEN}[setup-nginx]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC} %s\n" "$*" >&2; }
err()  { printf "${RED}[error]${NC} %s\n" "$*" >&2; exit 1; }

# ── Check root ──────────────────────────────────────────────────────────
if [[ "$(id -u)" != "0" ]]; then
    err "This script must be run as root. Use: sudo $0"
fi

# ── Detect OS ───────────────────────────────────────────────────────────
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID}"
    elif [ -f /etc/redhat-release ]; then
        OS_ID="rhel"
    else
        OS_ID="unknown"
    fi
    log "Detected OS: ${OS_ID}"
}

# ── Install nginx ───────────────────────────────────────────────────────
install_nginx() {
    if command -v nginx &>/dev/null; then
        log "nginx is already installed: $(nginx -v 2>&1)"
        return 0
    fi

    log "Installing nginx..."

    case "${OS_ID}" in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq nginx
            ;;
        centos|rhel|fedora|almalinux|rocky)
            if command -v dnf &>/dev/null; then
                dnf install -y nginx
            else
                yum install -y nginx
            fi
            ;;
        *)
            err "Unsupported OS: ${OS_ID}. Please install nginx manually."
            ;;
    esac

    log "nginx installed successfully."
}

# ── Configure nginx ─────────────────────────────────────────────────────
configure_nginx() {
    if [[ ! -f "${NGINX_CONF_SRC}" ]]; then
        err "nginx config not found at ${NGINX_CONF_SRC}"
    fi

    # Create sites-available / sites-enabled directories if not exist
    # (CentOS/RHEL sometimes don't have this structure by default)
    mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

    # Ensure main nginx.conf includes sites-enabled
    if ! grep -q "sites-enabled" /etc/nginx/nginx.conf; then
        log "Adding sites-enabled include to nginx.conf..."
        # Insert before the last closing brace
        if grep -q "include /etc/nginx/sites-enabled" /etc/nginx/nginx.conf; then
            : # Already configured
        elif grep -q "include /etc/nginx/conf.d" /etc/nginx/nginx.conf; then
            sed -i '/include \/etc\/nginx\/conf.d/i\    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
        else
            # Add inside the http block
            sed -i '/^http {/a\    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
        fi
    fi

    # Copy the config
    cp "${NGINX_CONF_SRC}" "${NGINX_AVAILABLE}"
    log "Copied nginx config to ${NGINX_AVAILABLE}"

    # Copy the apex domain config (if present)
    if [[ -f "${APEX_CONF_SRC}" ]]; then
        cp "${APEX_CONF_SRC}" "${APEX_AVAILABLE}"
        log "Copied apex nginx config to ${APEX_AVAILABLE}"
    else
        warn "Apex config not found at ${APEX_CONF_SRC}; skipping suoxya.com site"
    fi

    # Remove default site
    if [ -f /etc/nginx/sites-enabled/default ]; then
        rm -f /etc/nginx/sites-enabled/default
        log "Removed default site"
    fi
    if [ -f /etc/nginx/conf.d/default.conf ]; then
        rm -f /etc/nginx/conf.d/default.conf
        log "Removed default.conf"
    fi

    # Enable our site
    ln -sf "${NGINX_AVAILABLE}" "${NGINX_ENABLED}"
    log "Enabled site: ${NGINX_SITE_NAME}"

    # Enable the apex domain site (if it was copied)
    if [[ -f "${APEX_AVAILABLE}" ]]; then
        ln -sf "${APEX_AVAILABLE}" "${APEX_ENABLED}"
        log "Enabled site: ${APEX_SITE_NAME}"
    fi
}

# ── Open firewall ───────────────────────────────────────────────────────
open_firewall() {
    log "Checking firewall..."

    # ufw (Ubuntu/Debian)
    if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
        log "Opening ports 80 and 443 in ufw..."
        ufw allow 80/tcp
        ufw allow 443/tcp
        log "ufw rules added."
    fi

    # firewalld (CentOS/RHEL)
    if command -v firewall-cmd &>/dev/null && systemctl is-active --quiet firewalld 2>/dev/null; then
        log "Opening ports 80 and 443 in firewalld..."
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
        log "firewalld rules added."
    fi

    # iptables (fallback check — just warn)
    if command -v iptables &>/dev/null; then
        local has_80
        has_80=$(iptables -L INPUT -n 2>/dev/null | grep -c "dpt:80" || true)
        local has_443
        has_443=$(iptables -L INPUT -n 2>/dev/null | grep -c "dpt:443" || true)
        if [[ "${has_80}" == "0" ]] && [[ "${has_443}" == "0" ]]; then
            warn "No iptables rules found for ports 80/443."
            warn "If you use iptables directly, add rules manually:"
            warn "  iptables -A INPUT -p tcp --dport 80 -j ACCEPT"
            warn "  iptables -A INPUT -p tcp --dport 443 -j ACCEPT"
        fi
    fi

    # Cloud provider firewall reminder
    warn "REMINDER: If your server is behind a cloud firewall (Alibaba Cloud /"
    warn "  Tencent Cloud security group), make sure ports 80 and 443 are open"
    warn "  in the cloud console as well."
}

# ── Test & reload ───────────────────────────────────────────────────────
reload_nginx() {
    log "Testing nginx configuration..."
    if nginx -t; then
        log "Configuration OK. Reloading nginx..."
        systemctl reload nginx || systemctl restart nginx
        systemctl enable nginx
        log "nginx is running and enabled on boot."
    else
        err "nginx configuration test failed. Check the error output above."
    fi
}

# ── Verify ──────────────────────────────────────────────────────────────
verify_setup() {
    log "Verifying nginx is listening..."
    if ss -tlnp | grep -q ":80 "; then
        log "nginx is listening on port 80 ✓"
    else
        warn "nginx does not appear to be listening on port 80"
    fi

    log "Checking nginx status..."
    systemctl status nginx --no-pager || true
}

# ── SSL instructions ────────────────────────────────────────────────────
print_ssl_instructions() {
    echo ""
    echo "============================================================================"
    echo "  Next: Enable HTTPS with Let's Encrypt (Certbot)"
    echo "============================================================================"
    echo ""
    echo "  1. Install certbot:"
    if [[ "${OS_ID}" == "ubuntu" || "${OS_ID}" == "debian" ]]; then
    echo "     apt-get install -y certbot python3-certbot-nginx"
    else
    echo "     dnf install -y certbot python3-certbot-nginx"
    echo "     # or: yum install -y certbot python3-certbot-nginx"
    fi
    echo ""
    echo "  2. Obtain certificates (ensure DNS points to this server first):"
    echo "     certbot --nginx -d suoxya.com -d ink-backend.suoxya.com -d ink-frontend.suoxya.com"
    echo ""
    echo "  3. Or obtain separately:"
    echo "     certbot --nginx -d suoxya.com"
    echo "     certbot --nginx -d ink-backend.suoxya.com"
    echo "     certbot --nginx -d ink-frontend.suoxya.com"
    echo ""
    echo "  4. After certs are provisioned, re-run this script:"
    echo "     sudo ./setup-nginx.sh --enable-ssl"
    echo ""
    echo "  5. Set up auto-renewal (certbot adds a systemd timer automatically,"
    echo "     but verify it's active):"
    echo "     systemctl status certbot.timer"
    echo ""
    echo "============================================================================"
}

# ── Enable SSL in nginx config (after certbot has provisioned certs) ────
enable_ssl() {
    log "Enabling SSL configuration..."

    # Check if certs exist
    local certs_ok=1
    for domain in suoxya.com ink-backend.suoxya.com ink-frontend.suoxya.com; do
        if [ ! -f "/etc/letsencrypt/live/${domain}/fullchain.pem" ]; then
            warn "Certificate not found for ${domain}"
            certs_ok=0
        fi
    done

    if [[ "${certs_ok}" == "0" ]]; then
        err "SSL certificates not found. Run certbot first (see instructions above)."
    fi

    # Uncomment the SSL server blocks and HTTP→HTTPS redirect
    # Strategy: replace the commented SSL template with active config
    log "SSL certificates found. Please manually edit ${NGINX_AVAILABLE} to:"
    log "  1. Uncomment the SSL server blocks for both domains"
    log "  2. Uncomment the HTTP→HTTPS redirect server block"
    log "  3. Comment out the HTTP-only listen directives"
    log ""
    log "Or use certbot's automatic nginx integration:"
    log "  certbot --nginx -d ink-backend.suoxya.com -d ink-frontend.suoxya.com"
    log ""
    log "Then reload: systemctl reload nginx"
}

# ── Print Docker Compose env configuration ───────────────────────────────
print_docker_env() {
    echo ""
    echo "============================================================================"
    echo "  Docker Compose Environment Variables"
    echo "============================================================================"
    echo ""
    echo "  Add these to your deployment environment (or export before deploy):"
    echo ""
    echo "  # Frontend: move to a non-standard port (host nginx uses 80)"
    echo "  export REMOTE_FRONTEND_PORT=8080"
    echo "  export REMOTE_FRONTEND_BIND_HOST=127.0.0.1"
    echo ""
    echo "  # Backend: keep on localhost-only"
    echo "  export REMOTE_BACKEND_BIND_HOST=127.0.0.1"
    echo "  export REMOTE_BACKEND_PORT=8765"
    echo ""
    echo "  # CORS: allow the frontend domain for cross-origin requests"
    echo "  export REMOTE_CORS_ALLOW_ORIGINS=https://ink-frontend.suoxya.com,https://ink-backend.suoxya.com"
    echo ""
    echo "  # Optional: direct browser-to-backend API URL"
    echo "  # export REMOTE_API_BASE_URL=https://ink-backend.suoxya.com"
    echo ""
    echo "============================================================================"
}

# ── Main ────────────────────────────────────────────────────────────────
main() {
    local enable_ssl_flag=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --enable-ssl)
                enable_ssl_flag=1
                shift
                ;;
            --help|-h)
                echo "Usage: sudo $0 [--enable-ssl]"
                echo ""
                echo "  --enable-ssl   Enable HTTPS after certbot certificates are provisioned"
                exit 0
                ;;
            *)
                err "Unknown option: $1"
                ;;
        esac
    done

    detect_os

    if [[ "${enable_ssl_flag}" == "1" ]]; then
        enable_ssl
        exit 0
    fi

    install_nginx
    configure_nginx
    open_firewall
    reload_nginx
    verify_setup
    print_docker_env
    print_ssl_instructions

    echo ""
    log "Nginx setup complete!"
    log "Apex:     http://suoxya.com               → Docker frontend container"
    log "Frontend: http://ink-frontend.suoxya.com → Docker frontend container"
    log "Backend:  http://ink-backend.suoxya.com  → Docker backend container"
}

main "$@"
