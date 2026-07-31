#!/usr/bin/env bash
# deploy/setup-env.sh — Initialize Cloud Run environment variables for the backend.
# [Sync] 2026-06-12: point follow-up release guidance to deploy/google-cloud/deploy.sh.
# [Sync] 2026-06-23: store Google OAuth, JWT, and session secrets in Secret Manager.
#
# Behavior:
#   - Prompts to confirm selected Secret Manager keys
#   - All other keys in backend/.env are passed through as plain env vars silently
#   - Writes .cloud-env before any gcloud calls
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   ./deploy/setup-env.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOTENV="${REPO_ROOT}/backend/.env"
CLOUD_ENV="${REPO_ROOT}/.cloud-env"

PROJECT_ID="${GCP_PROJECT_ID:?ERROR: GCP_PROJECT_ID is not set. Run: export GCP_PROJECT_ID=your-project-id}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[setup-env]${NC} $*"; }
info()  { echo -e "${CYAN}[info]${NC}      $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}      $*"; }
err()   { echo -e "${RED}[error]${NC}     $*" >&2; exit 1; }
prompt(){ echo -en "${CYAN}  ? ${1}${NC} [${2}]: " >&2; }

command -v gcloud >/dev/null 2>&1 || err "gcloud CLI not found."
gcloud config set project "${PROJECT_ID}" --quiet

# ── Keys that require confirmation and go to Secret Manager ──────────────────
# secret_name is the corresponding Secret Manager resource name.
#
#  ENV_KEY                        SECRET_NAME
SECRET_KEYS="
ANTHROPIC_BASE_URL             ink-anthropic-base-url
ANTHROPIC_AUTH_TOKEN           ink-anthropic-auth-token
ANTHROPIC_MODEL                ink-anthropic-model
ANTHROPIC_DEFAULT_HAIKU_MODEL  ink-anthropic-haiku-model
ANTHROPIC_DEFAULT_SONNET_MODEL ink-anthropic-sonnet-model
ANTHROPIC_DEFAULT_OPUS_MODEL   ink-anthropic-opus-model
AGENT_CWD                      ink-agent-cwd
FILE_STORAGE_LOCAL_DIR         ink-file-storage-dir
GOOGLE_CLIENT_SECRET           ink-google-client-secret
JWT_SECRET                     ink-jwt-secret
SESSION_SECRET_KEY             ink-session-secret-key
OAUTH_TOKEN_ENCRYPTION_KEY     ink-oauth-token-encryption-key
"

# Cloud Run defaults for path keys (ignore local .env values)
_DEFAULT_AGENT_CWD="/app/data/agent-workspace"
_DEFAULT_FILE_STORAGE="/app/data/file-storage"

# ── Load backend/.env ─────────────────────────────────────────────────────────
DEFAULTS_FILE="$(mktemp)"
trap 'rm -f "${DEFAULTS_FILE}"' EXIT

if [[ -f "${DOTENV}" ]]; then
  log "Reading backend/.env..."
  while IFS= read -r line; do
    [[ "${line}" =~ ^[[:space:]]*# || -z "${line// /}" ]] && continue
    key="${line%%=*}" ; value="${line#*=}"
    key="${key// /}"
    value="${value%\"}" ; value="${value#\"}"
    value="${value%\'}" ; value="${value#\'}"
    [[ -n "${key}" ]] && printf '%s=%s\n' "${key}" "${value}" >> "${DEFAULTS_FILE}"
  done < "${DOTENV}"
else
  warn "backend/.env not found — only prompted keys will be set."
fi

get_default() { grep "^${1}=" "${DEFAULTS_FILE}" 2>/dev/null | head -1 | cut -d= -f2-; }

# ── Build the set of keys that will go to Secret Manager ─────────────────────
# (used to exclude them from plain ENV_VARS)
secret_key_list() {
  echo "${SECRET_KEYS}" | awk 'NF>=1{print $1}'
}

is_secret_key() {
  secret_key_list | grep -qx "${1}"
}

# ════════════════════════════════════════════════════════
# PHASE 1 — Confirm secret keys interactively
# ════════════════════════════════════════════════════════
echo ""
info "════════════════════════════════════════════════════════"
info "  Confirm keys for Secret Manager"
info "  Press Enter to accept the value shown in [brackets]."
info "════════════════════════════════════════════════════════"
echo ""

# Temp file to store confirmed secret values: KEY=VALUE
CONFIRMED_FILE="$(mktemp)"
trap 'rm -f "${DEFAULTS_FILE}" "${CONFIRMED_FILE}"' EXIT

while read -r env_key secret_name; do
  [[ -z "${env_key}" ]] && continue

  # Choose display default
  case "${env_key}" in
    AGENT_CWD)             default="${_DEFAULT_AGENT_CWD}" ;;
    FILE_STORAGE_LOCAL_DIR) default="${_DEFAULT_FILE_STORAGE}" ;;
    ANTHROPIC_AUTH_TOKEN|GOOGLE_CLIENT_SECRET|JWT_SECRET|SESSION_SECRET_KEY|OAUTH_TOKEN_ENCRYPTION_KEY)
                           default="$(get_default "${env_key}")"
                           display="${default:+(set)}" ;;
    *)                     default="$(get_default "${env_key}")"
                           display="${default:-empty}" ;;
  esac

  # For auth token use masked display, others show actual value
  case "${env_key}" in
    ANTHROPIC_AUTH_TOKEN|GOOGLE_CLIENT_SECRET|JWT_SECRET|SESSION_SECRET_KEY|OAUTH_TOKEN_ENCRYPTION_KEY)
                         display="${default:+(set)}" ;;
    *)                    display="${default:-empty}" ;;
  esac

  prompt "${env_key}" "${display}"
  read -r input </dev/tty
  value="${input:-${default}}"
  printf '%s=%s\n' "${env_key}" "${value}" >> "${CONFIRMED_FILE}"

done < <(echo "${SECRET_KEYS}" | awk 'NF>=2{print $1, $2}')

# ════════════════════════════════════════════════════════
# PHASE 2 — Build ENV_VARS from remaining .env keys + write .cloud-env
# ════════════════════════════════════════════════════════
ENV_VARS="TZ=UTC"
SECRET_REFS=""

# Pass through all .env keys not in the secret list
while IFS='=' read -r key value; do
  is_secret_key "${key}" && continue
  case "${key}" in
    TZ) continue ;; # already set
    # Owned by deploy/google-cloud/deploy.sh so localhost values from
    # backend/.env never leak into the production Cloud Run revision.
    WEBUI_URL|API_BASE_URL|COOKIE_SECURE|COOKIE_SAMESITE|INK_CORS_ALLOW_ORIGINS|INK_CORS_ALLOW_CREDENTIALS|INK_PUBLIC_BASE_URL|INK_BACKEND_PUBLIC_BASE_URL) continue ;;
  esac
  ENV_VARS+=",${key}=${value}"
done < "${DEFAULTS_FILE}"

# Build SECRET_REFS from confirmed values
while read -r env_key secret_name; do
  [[ -z "${env_key}" ]] && continue
  confirmed_val="$(grep "^${env_key}=" "${CONFIRMED_FILE}" | head -1 | cut -d= -f2-)"
  [[ -n "${confirmed_val}" ]] && SECRET_REFS+="${env_key}=${secret_name}:latest,"
done < <(echo "${SECRET_KEYS}" | awk 'NF>=2{print $1, $2}')
SECRET_REFS="${SECRET_REFS%,}"

cat > "${CLOUD_ENV}" <<EOF
# Auto-generated by deploy/setup-env.sh — do NOT commit this file.
CLOUD_ENV_VARS=${ENV_VARS}
CLOUD_SECRET_REFS=${SECRET_REFS}
EOF
log "Saved ${CLOUD_ENV}"

# ════════════════════════════════════════════════════════
# PHASE 3 — gcloud: enable API, upsert secrets, grant IAM
# ════════════════════════════════════════════════════════
log "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="${PROJECT_ID}"

upsert_secret() {
  local secret_name="$1" secret_value="$2"
  [[ -z "${secret_value}" ]] && { warn "Skipping empty secret: ${secret_name}"; return; }
  if gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" &>/dev/null; then
    printf '%s' "${secret_value}" | gcloud secrets versions add "${secret_name}" \
      --data-file=- --project="${PROJECT_ID}" --quiet
    log "Updated: ${secret_name}"
  else
    printf '%s' "${secret_value}" | gcloud secrets create "${secret_name}" \
      --data-file=- --replication-policy=automatic --project="${PROJECT_ID}"
    log "Created: ${secret_name}"
  fi
}

log "Storing secrets..."
while read -r env_key secret_name; do
  [[ -z "${env_key}" ]] && continue
  val="$(grep "^${env_key}=" "${CONFIRMED_FILE}" | head -1 | cut -d= -f2-)"
  upsert_secret "${secret_name}" "${val}"
done < <(echo "${SECRET_KEYS}" | awk 'NF>=2{print $1, $2}')

STORAGE_ENV="${REPO_ROOT}/.storage-env"
if [[ -f "${STORAGE_ENV}" ]]; then
  # shellcheck source=/dev/null
  source "${STORAGE_ENV}"
  if [[ -n "${SA_EMAIL:-}" && -n "${SECRET_REFS}" ]]; then
    log "Granting Secret Manager Secret Accessor to ${SA_EMAIL}..."
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="roles/secretmanager.secretAccessor" \
      --condition=None \
      --quiet
  fi
fi

echo ""
info "════════════════════════════════════════════════════════"
info "  Done. Next step: ./deploy/google-cloud/deploy.sh deploy"
info "════════════════════════════════════════════════════════"
