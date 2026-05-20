#!/usr/bin/env bash
set -euo pipefail

INSTALLER_REF="${INSTALLER_REF:-main}"
GITHUB_REPO="bphndigitalservice/superset-bphn"
RAW_BASE="https://raw.githubusercontent.com/${GITHUB_REPO}/${INSTALLER_REF}"
IMAGE="ghcr.io/bphndigitalservice/superset-bphn:latest"
HEALTH_TIMEOUT_SEC=300

die() { echo "error: $*" >&2; exit 1; }
info() { echo "==> $*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

preflight_docker() {
  require_cmd docker
  docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin required"
}

random_secret() {
  # hex only — safe for sed substitution and DATABASE_URL (no / + =)
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

fetch_template() {
  local remote_path="$1" dest="$2"
  curl -fsSL "${RAW_BASE}/${remote_path}" -o "$dest" || die "failed to download ${remote_path} from GitHub"
}

superset_port_bind() {
  case "${INSTALL_MODE:-simple}" in
    production) echo "127.0.0.1:8088:8088" ;;
    *) echo "0.0.0.0:8088:8088" ;;
  esac
}

read_install_mode() {
  if [ -f .install-meta ] && grep -q '^mode=production$' .install-meta 2>/dev/null; then
    INSTALL_MODE=production
  else
    INSTALL_MODE=simple
  fi
}

substitute_compose_template() {
  local template="$1" dest="$2"
  sed -e "s|{{SUPERSET_PORT_BIND}}|$(superset_port_bind)|g" "$template" >"$dest"
}

substitute_env_template() {
  local template="$1" dest="$2"
  sed \
    -e "s|{{SUPERSET_SECRET_KEY}}|${SUPERSET_SECRET_KEY}|g" \
    -e "s|{{POSTGRES_PASSWORD}}|${POSTGRES_PASSWORD}|g" \
    -e "s|{{DATABASE_URL}}|${DATABASE_URL}|g" \
    -e "s|{{SUPERSET_WEBSERVER_BASE_URL}}|${SUPERSET_WEBSERVER_BASE_URL}|g" \
    -e "s|{{PREFERRED_URL_SCHEME}}|${PREFERRED_URL_SCHEME}|g" \
    -e "s|{{SESSION_COOKIE_SECURE}}|${SESSION_COOKIE_SECURE}|g" \
    -e "s|{{SUPERSET_AUTH_TYPE}}|${SUPERSET_AUTH_TYPE}|g" \
    -e "s|{{LOAD_EXAMPLES}}|${LOAD_EXAMPLES}|g" \
    "$template" >"$dest"
  chmod 600 "$dest"
}

wait_for_superset_health() {
  local elapsed=0 interval=5
  info "waiting for superset health (up to ${HEALTH_TIMEOUT_SEC}s)…"
  while [ "$elapsed" -lt "$HEALTH_TIMEOUT_SEC" ]; do
    if docker compose ps superset 2>/dev/null | grep -q healthy; then
      info "superset is healthy"
      return 0
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  echo "--- last 40 lines of superset logs ---" >&2
  docker compose logs --tail=40 superset >&2 || true
  die "superset did not become healthy within ${HEALTH_TIMEOUT_SEC}s"
}

prompt_admin() {
  read -r -p "Admin username [admin]: " ADMIN_USER
  ADMIN_USER="${ADMIN_USER:-admin}"
  read -r -p "Admin email: " ADMIN_EMAIL
  [ -n "$ADMIN_EMAIL" ] || die "email is required"
  while true; do
    read -r -s -p "Admin password: " ADMIN_PASSWORD
    echo
    read -r -s -p "Confirm password: " ADMIN_PASSWORD_CONFIRM
    echo
    [ "$ADMIN_PASSWORD" = "$ADMIN_PASSWORD_CONFIRM" ] || { echo "passwords do not match"; continue; }
    [ -n "$ADMIN_PASSWORD" ] || { echo "password cannot be empty"; continue; }
    break
  done
}

create_admin() {
  set +e
  docker compose exec -T superset superset fab create-admin \
    --username "$ADMIN_USER" \
    --firstname Admin \
    --lastname User \
    --email "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" 2>&1 | tee /tmp/superset-create-admin.log
  local rc="${PIPESTATUS[0]}"
  set -e
  if [ "$rc" -ne 0 ]; then
    if grep -qi "already exists" /tmp/superset-create-admin.log 2>/dev/null; then
      info "admin user already exists, skipping create-admin"
    else
      die "fab create-admin failed (see log above)"
    fi
  fi
  docker compose exec -T superset superset init
}

print_production_checklist() {
  local host
  host="$(echo "$SUPERSET_WEBSERVER_BASE_URL" | sed -E 's#https?://##; s#/.*##')"
  cat <<EOF

--- Production next steps ---
1. Point your reverse proxy at 127.0.0.1:8088 with headers:
   X-Forwarded-Proto, X-Forwarded-Host, X-Forwarded-For
2. Confirm SUPERSET_WEBSERVER_BASE_URL in .env matches your public URL.
3. To enable Keycloak later:
   - Redirect URI: https://${host}/oauth-authorized/keycloak
   - Set SUPERSET_AUTH_TYPE=oauth and KEYCLOAK_* in .env
   - Run: docker compose up -d --force-recreate superset superset-worker superset-beat
   - Break-glass login: https://${host}/login/db

EOF
}

usage() {
  cat <<EOF
Usage: install.sh [install|upgrade]

  install   First-time setup in the current directory
  upgrade   Pull latest image and recreate containers (keeps .env)

Examples:
  curl -fsSL .../install.sh | bash
  curl -fsSL .../install.sh | bash -s upgrade
EOF
}

cmd_install() {
  preflight_docker
  [ -f .env ] && die ".env already exists — run 'upgrade' or remove .env to reinstall"

  echo "Select install mode:"
  echo "  1) Simple   — demo on port 8088 (all interfaces; use this host's IP from other machines)"
  echo "  2) Production — public HTTPS URL (reverse proxy)"
  read -r -p "Choice [1]: " MODE_CHOICE
  MODE_CHOICE="${MODE_CHOICE:-1}"

  SUPERSET_AUTH_TYPE=db
  case "$MODE_CHOICE" in
    1|"simple"|"Simple")
      INSTALL_MODE=simple
      SUPERSET_WEBSERVER_BASE_URL="http://127.0.0.1:8088"
      PREFERRED_URL_SCHEME=http
      SESSION_COOKIE_SECURE=false
      ;;
    2|"production"|"Production")
      INSTALL_MODE=production
      read -r -p "Public HTTPS URL (e.g. https://analytics.example.com): " SUPERSET_WEBSERVER_BASE_URL
      [ -n "$SUPERSET_WEBSERVER_BASE_URL" ] || die "URL is required"
      case "$SUPERSET_WEBSERVER_BASE_URL" in
        https://*) ;;
        *) die "production URL must start with https://" ;;
      esac
      PREFERRED_URL_SCHEME=https
      SESSION_COOKIE_SECURE=true
      ;;
    *) die "invalid choice" ;;
  esac

  read -r -p "Load example dashboards on first start? [y/N]: " EXAMPLES_CHOICE
  case "${EXAMPLES_CHOICE:-N}" in
    y|Y|yes|Yes) LOAD_EXAMPLES=true ;;
    *) LOAD_EXAMPLES=false ;;
  esac

  SUPERSET_SECRET_KEY="$(random_secret)"
  POSTGRES_PASSWORD="$(random_secret)"
  DATABASE_URL="postgresql+psycopg2://superset:${POSTGRES_PASSWORD}@postgres:5432/superset"

  prompt_admin

  mkdir -p branding
  local tmpdir
  tmpdir="$(mktemp -d)"
  fetch_template "docker/docker-compose.install.yml" "${tmpdir}/compose.template.yml"
  fetch_template "install/.env.template" "${tmpdir}/env.template"
  substitute_compose_template "${tmpdir}/compose.template.yml" docker-compose.yml
  substitute_env_template "${tmpdir}/env.template" .env
  rm -rf "$tmpdir"

  {
    date -Iseconds 2>/dev/null || date
    echo "mode=${INSTALL_MODE}"
    echo "installer_ref=${INSTALLER_REF}"
  } >.install-meta

  info "pulling images (${IMAGE})…"
  docker compose pull
  info "starting stack…"
  docker compose up -d

  wait_for_superset_health
  info "creating admin user…"
  create_admin

  cat <<EOF

--- Install complete ---
URL:      ${SUPERSET_WEBSERVER_BASE_URL}
Login:    ${SUPERSET_WEBSERVER_BASE_URL}/login/
Secrets:  .env (mode 600)
Upgrade:  curl -fsSL ${RAW_BASE}/scripts/install.sh | bash -s upgrade

EOF
  [ "$INSTALL_MODE" = production ] && print_production_checklist
}

cmd_upgrade() {
  preflight_docker
  [ -f .env ] || die "missing .env — run install first"
  [ -f docker-compose.yml ] || die "missing docker-compose.yml — run install first"

  read_install_mode

  local tmpdir
  tmpdir="$(mktemp -d)"
  fetch_template "docker/docker-compose.install.yml" "${tmpdir}/compose.template.yml"
  substitute_compose_template "${tmpdir}/compose.template.yml" docker-compose.yml
  rm -rf "$tmpdir"

  info "pulling images (${IMAGE})…"
  docker compose pull
  info "recreating containers…"
  docker compose up -d --force-recreate

  wait_for_superset_health

  cat <<EOF

--- Upgrade complete ---
Image:    ${IMAGE}
.env:     unchanged
URL:      check SUPERSET_WEBSERVER_BASE_URL in .env

EOF
}

main() {
  local cmd="${1:-install}"
  case "$cmd" in
    install) cmd_install ;;
    upgrade) cmd_upgrade ;;
    -h|--help|help) usage ;;
    *) usage; die "unknown command: $cmd" ;;
  esac
}

main "${1:-install}"
