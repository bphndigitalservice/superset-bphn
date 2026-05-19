# Curl Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a curl-invoked bash installer that deploys the BPHN Superset stack from public GHCR, generates secrets, prompts for admin credentials, and supports `install` / `upgrade` subcommands.

**Architecture:** Thin `scripts/install.sh` fetches `docker/docker-compose.install.yml` and `install/.env.template` from GitHub `main`, substitutes placeholders, runs `docker compose`. Dev `docker-compose.yml` unchanged.

**Tech Stack:** Bash 4+, Docker Compose v2, GHCR, curl.

**Spec:** `docs/superpowers/specs/2026-05-19-curl-installer-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `docker/docker-compose.install.yml` | GHCR image, `./branding` mount, no `build:` |
| `install/.env.template` | Placeholder-based env for installer substitution |
| `scripts/install.sh` | Preflight, prompts, fetch, deploy, admin bootstrap |
| `.github/workflows/lint-installer.yml` | Shellcheck on `scripts/install.sh` |
| `README.md` | Quick install one-liner + link to spec |

---

### Task 1: Install Compose template

**Files:**
- Create: `docker/docker-compose.install.yml`

- [ ] **Step 1: Create `docker/docker-compose.install.yml`**

Copy `docker-compose.yml` with these edits:
- Remove top `include:` block (examples profile not used by installer v1).
- Remove `build: .` from `superset`.
- Set image on all three Superset services to `ghcr.io/bphndigitalservice/superset-bphn:latest`.
- Change branding volume on `superset` and `superset-worker` to `./branding:/app/superset/static/assets/branding:ro`.
- Keep `command: ["/app/docker/entrypoints/entrypoint-with-examples.sh"]` on `superset`.
- Keep `LOAD_EXAMPLES: ${LOAD_EXAMPLES:-false}` on `superset`.

Full file:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  superset:
    image: ghcr.io/bphndigitalservice/superset-bphn:latest
    restart: unless-stopped
    env_file: .env
    environment:
      LOAD_EXAMPLES: ${LOAD_EXAMPLES:-false}
    ports:
      - "127.0.0.1:8088:8088"
    volumes:
      - ./branding:/app/superset/static/assets/branding:ro
      - superset_home:/app/superset_home
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: ["/app/docker/entrypoints/entrypoint-with-examples.sh"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  superset-worker:
    image: ghcr.io/bphndigitalservice/superset-bphn:latest
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./branding:/app/superset/static/assets/branding:ro
      - superset_home:/app/superset_home
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      superset:
        condition: service_healthy
    command:
      [
        "celery",
        "--app=superset.tasks.celery_app:app",
        "worker",
        "-O",
        "fair",
        "-l",
        "INFO",
      ]

  superset-beat:
    image: ghcr.io/bphndigitalservice/superset-bphn:latest
    restart: unless-stopped
    env_file: .env
    volumes:
      - superset_home:/app/superset_home
    depends_on:
      redis:
        condition: service_healthy
      superset:
        condition: service_healthy
    command:
      [
        "celery",
        "--app=superset.tasks.celery_app:app",
        "beat",
        "--pidfile",
        "/tmp/celerybeat.pid",
        "-l",
        "INFO",
        "-s",
        "/app/superset_home/celerybeat-schedule",
      ]

volumes:
  postgres_data:
  superset_home:
```

- [ ] **Step 2: Commit**

```bash
git add docker/docker-compose.install.yml
git commit -m "feat: add compose template for curl installer"
```

---

### Task 2: Environment template

**Files:**
- Create: `install/.env.template`

- [ ] **Step 1: Create `install/.env.template`**

Use `{{PLACEHOLDER}}` tokens the installer replaces via `sed` (see Task 3). Keycloak vars stay as static placeholders for later manual edit.

```bash
# --- Core ---
SUPERSET_HOME=/app/superset_home
SUPERSET_SECRET_KEY={{SUPERSET_SECRET_KEY}}
SUPERSET_WEBSERVER_BASE_URL={{SUPERSET_WEBSERVER_BASE_URL}}
PREFERRED_URL_SCHEME={{PREFERRED_URL_SCHEME}}
SESSION_COOKIE_SECURE={{SESSION_COOKIE_SECURE}}
SESSION_LIFETIME_HOURS=8
SUPERSET_LOG_LEVEL=INFO

# --- Metadata DB (compose postgres service) ---
POSTGRES_USER=superset
POSTGRES_PASSWORD={{POSTGRES_PASSWORD}}
POSTGRES_DB=superset
DATABASE_URL={{DATABASE_URL}}

# --- Redis ---
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_CELERY_DB=0
REDIS_RESULTS_DB=1
REDIS_CACHE_DB=2

# --- Auth: db (local only) | oauth (Keycloak + break-glass /login/db) ---
SUPERSET_AUTH_TYPE={{SUPERSET_AUTH_TYPE}}

# Keycloak (only when SUPERSET_AUTH_TYPE=oauth)
KEYCLOAK_BASE_URL=https://keycloak.example.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=superset
KEYCLOAK_CLIENT_SECRET=change-me
AUTH_ROLES_MAPPING_JSON={"superset_admins":["Admin"],"superset_users":["Gamma"]}

# --- Examples (optional) ---
LOAD_EXAMPLES={{LOAD_EXAMPLES}}
```

- [ ] **Step 2: Commit**

```bash
git add install/.env.template
git commit -m "feat: add env template for curl installer"
```

---

### Task 3: Installer script — skeleton and helpers

**Files:**
- Create: `scripts/install.sh`

- [ ] **Step 1: Create `scripts/install.sh` with header, constants, and helpers**

```bash
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
  if docker compose exec -T superset superset fab create-admin \
    --username "$ADMIN_USER" \
    --firstname Admin \
    --lastname User \
    --email "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" 2>&1 | tee /tmp/superset-create-admin.log; then
    :
  else
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
```

- [ ] **Step 2: Commit**

```bash
chmod +x scripts/install.sh
git add scripts/install.sh
git commit -m "feat: add installer script skeleton and helpers"
```

---

### Task 4: Installer script — `cmd_install`

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: Append `cmd_install` and mode prompts to `scripts/install.sh`**

```bash
cmd_install() {
  preflight_docker
  [ -f .env ] && die ".env already exists — run 'upgrade' or remove .env to reinstall"

  echo "Select install mode:"
  echo "  1) Simple   — local demo at http://127.0.0.1:8088"
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
  fetch_template "docker/docker-compose.install.yml" "${tmpdir}/compose.yml"
  fetch_template "install/.env.template" "${tmpdir}/env.template"
  cp "${tmpdir}/compose.yml" docker-compose.yml
  substitute_env_template "${tmpdir}/env.template" .env
  rm -rf "$tmpdir"

  date -Iseconds > .install-meta 2>/dev/null || date > .install-meta
  echo "mode=${INSTALL_MODE}" >> .install-meta
  echo "installer_ref=${INSTALLER_REF}" >> .install-meta

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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add install subcommand to curl installer"
```

---

### Task 5: Installer script — `cmd_upgrade` and main

**Files:**
- Modify: `scripts/install.sh`

- [ ] **Step 1: Append `cmd_upgrade` and `main` to `scripts/install.sh`**

```bash
cmd_upgrade() {
  preflight_docker
  [ -f .env ] || die "missing .env — run install first"
  [ -f docker-compose.yml ] || die "missing docker-compose.yml — run install first"

  local tmpdir
  tmpdir="$(mktemp -d)"
  fetch_template "docker/docker-compose.install.yml" "${tmpdir}/compose.yml"
  cp "${tmpdir}/compose.yml" docker-compose.yml
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
```

- [ ] **Step 2: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add upgrade subcommand and main entry to installer"
```

---

### Task 6: Shellcheck CI

**Files:**
- Create: `.github/workflows/lint-installer.yml`

- [ ] **Step 1: Create `.github/workflows/lint-installer.yml`**

```yaml
name: Lint installer

on:
  push:
    branches: [main]
    paths:
      - "scripts/install.sh"
      - ".github/workflows/lint-installer.yml"
  pull_request:
    branches: [main]
    paths:
      - "scripts/install.sh"
      - ".github/workflows/lint-installer.yml"

jobs:
  shellcheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run ShellCheck
        uses: koalaman/shellcheck-action@v0.9
        with:
          scandir: scripts
```

- [ ] **Step 2: Run ShellCheck locally**

```bash
# if shellcheck installed:
shellcheck scripts/install.sh
# Expected: no errors (fix any SC2086 etc. reported)
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/lint-installer.yml
git commit -m "ci: shellcheck curl installer script"
```

---

### Task 7: README Quick install

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add section after `## Prerequisites` in `README.md`**

```markdown
## Quick install (curl)

Deploy with the published GHCR image (no clone or local build):

```bash
mkdir superset && cd superset
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash
```

Upgrade an existing install in the same directory:

```bash
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash -s upgrade
```

See [curl installer design](docs/superpowers/specs/2026-05-19-curl-installer-design.md) for modes, Keycloak checklist, and troubleshooting.

For development (local image build), use **Quick start** below.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add curl quick install to README"
```

---

### Task 8: Manual smoke test

**Files:** none (verification only)

- [ ] **Step 1: Ensure GHCR image exists**

Push `main` so `.github/workflows/build-image.yml` has published `ghcr.io/bphndigitalservice/superset-bphn:latest`. Package must be **public**.

- [ ] **Step 2: Simple install smoke test**

```bash
mkdir /tmp/superset-install-test && cd /tmp/superset-install-test
bash /path/to/repo/scripts/install.sh install
# Choose 1 (simple), skip examples, set admin credentials
curl -sf http://127.0.0.1:8088/health
# Expected: HTTP 200
```

- [ ] **Step 3: Upgrade smoke test**

```bash
bash /path/to/repo/scripts/install.sh upgrade
docker compose ps
# Expected: all services running/healthy
grep SUPERSET_SECRET_KEY .env | wc -l
# Expected: 1 (unchanged value vs before upgrade — note first line manually)
```

- [ ] **Step 4: Cleanup**

```bash
cd /tmp/superset-install-test && docker compose down -v
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Bootstrap + templates from GitHub | Task 1–2, 3 `fetch_template` |
| `install` / `upgrade` subcommands | Task 4–5 |
| Simple vs production env | Task 4 `cmd_install` |
| Auto-generated secrets | Task 4 |
| Interactive admin | Task 3–4 `prompt_admin`, `create_admin` |
| `db` auth + production Keycloak checklist | Task 4, `print_production_checklist` |
| Public GHCR, no login | Task 1 image ref |
| `.env` 600, install fails if exists | Task 3 `substitute_env_template`, Task 4 |
| Upgrade keeps `.env` | Task 5 |
| Optional examples | Task 4 `LOAD_EXAMPLES` |
| `branding/` dir | Task 4 `mkdir -p branding` |
| Health wait + log tail on failure | Task 3 `wait_for_superset_health` |
| README quick install | Task 7 |
| Shellcheck CI | Task 6 |
