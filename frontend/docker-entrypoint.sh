#!/bin/sh
# [Input] BACKEND_URL, API_BASE_URL, WS_BASE_URL env vars and nginx/runtime config templates.
# [Output] Render nginx config plus frontend runtime config before starting nginx.
# [Pos] frontend container entrypoint
# [Sync] 2026-06-12: generate runtime-config.js so deployed frontend can call backend by cross-origin URL.
# [Sync] 2026-06-15: render runtime-config.js at frontend root after removing /ink-and-memory/ prefix.
set -eu

# BACKEND_URL remains the nginx proxy fallback; API_BASE_URL is the browser-facing
# backend origin. Default API_BASE_URL to BACKEND_URL for cross-origin deployments.
API_BASE_URL="${API_BASE_URL:-${BACKEND_URL:-}}"
WS_BASE_URL="${WS_BASE_URL:-}"
export API_BASE_URL WS_BASE_URL BACKEND_URL

# Only substitute ${BACKEND_URL}; leave all nginx runtime variables ($host,
# $proxy_host, $remote_addr, $scheme, etc.) untouched.
envsubst '${BACKEND_URL}' \
  < /etc/nginx/templates/ink.conf.template \
  > /etc/nginx/conf.d/ink.conf

if [ -f /usr/share/nginx/html/runtime-config.template.js ]; then
  envsubst '${API_BASE_URL} ${WS_BASE_URL}' \
    < /usr/share/nginx/html/runtime-config.template.js \
    > /usr/share/nginx/html/runtime-config.js
fi

exec nginx -g 'daemon off;'
