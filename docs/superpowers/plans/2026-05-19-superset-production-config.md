# Superset Production Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `superset-bphn` into a production Docker Compose stack with baked branding defaults, volume overrides, PostgreSQL metadata, Redis/Celery, Keycloak SSO + local admin fallback, and security settings for an external HTTPS proxy.

**Architecture:** Custom image extends `apache/superset:6.1.0`, copies `superset_config.py` and branding into the image, mounts `./superset/assets/branding` for runtime overrides. Compose runs postgres, redis, superset (web), worker, and beat on an internal network; Keycloak and TLS proxy stay external.

**Tech Stack:** Docker Compose, Apache Superset 6.1.0, PostgreSQL 16, Redis 7, Celery, Flask-AppBuilder OAuth (Keycloak OIDC), Python 3 (image venv via `uv pip`).

**Spec:** `docs/superpowers/specs/2026-05-19-superset-production-config-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `.gitignore` | Ignore `.env`, secrets, local overrides |
| `superset/branding.py` | Resolve branding paths (volume → default → env) |
| `superset/superset_config.py` | Production config: DB, Redis, Celery, OAuth, security, theme |
| `superset/security_manager.py` | Keycloak `oauth_user_info` + DB login alongside OAuth |
| `superset/assets/branding/*` | Build-time brand kit (logo, favicon, theme.json) |
| `Dockerfile` | Drivers + COPY config + branding-default |
| `docker-compose.yml` | Full stack + healthchecks + volumes |
| `.env.example` | Documented env template |
| `README.md` | Deploy, Keycloak, admin bootstrap, branding ops |

---

### Task 1: Repository scaffolding

**Files:**
- Create: `.gitignore`
- Create: `superset/assets/branding/.gitkeep`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
.env
.env.local
*.pyc
__pycache__/
.DS_Store
superset/assets/branding/logo.svg
superset/assets/branding/logo.png
superset/assets/branding/favicon.png
!superset/assets/branding/.gitkeep
!superset/assets/branding/theme.json.example
```

(Real logo/favicon committed only when you choose; `theme.json.example` is committed as template.)

- [ ] **Step 2: Create branding directory placeholder**

```bash
mkdir -p superset/assets/branding
touch superset/assets/branding/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore superset/assets/branding/.gitkeep
git commit -m "chore: add gitignore and branding directory scaffold"
```

---

### Task 2: Brand kit defaults (build input)

**Files:**
- Create: `superset/assets/branding/theme.json.example`
- Create: `superset/assets/branding/theme.json` (copy from example with BPHN placeholders)
- Create: `superset/assets/branding/logo.svg` (minimal placeholder SVG)
- Create: `superset/assets/branding/favicon.png` (or document user must add — use a 32×32 generated placeholder)

- [ ] **Step 1: Add `theme.json.example`**

```json
{
  "app_name": "BPHN Analytics",
  "primary_color": "#2893B3",
  "secondary_color": "#5AC189",
  "welcome_message": "Welcome to BPHN Analytics"
}
```

- [ ] **Step 2: Copy to `theme.json` for build defaults**

```bash
cp superset/assets/branding/theme.json.example superset/assets/branding/theme.json
```

Edit `app_name` / colors to match your brand kit before shipping.

- [ ] **Step 3: Add placeholder `logo.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="40" viewBox="0 0 200 40">
  <text x="0" y="28" font-family="system-ui,sans-serif" font-size="20" fill="#2893B3">BPHN</text>
</svg>
```

Replace with production logo before first real deploy.

- [ ] **Step 4: Add `favicon.png`**

Add a 32×32 PNG (brand team asset). If unavailable, copy any small PNG and replace later.

- [ ] **Step 5: Commit**

```bash
git add superset/assets/branding/
git commit -m "feat: add default branding assets for image build"
```

---

### Task 3: Branding resolver module

**Files:**
- Create: `superset/branding.py`

- [ ] **Step 1: Create `superset/branding.py`**

```python
"""Resolve branding files: env > volume mount > image defaults."""
from __future__ import annotations

import json
import os
from pathlib import Path

BRANDING_OVERRIDE_DIR = Path(
    "/app/superset/static/assets/branding"
)
BRANDING_DEFAULT_DIR = Path(
    "/app/superset/static/assets/branding-default"
)


def resolve_branding_file(name: str) -> Path | None:
    override = BRANDING_OVERRIDE_DIR / name
    if override.is_file():
        return override
    default = BRANDING_DEFAULT_DIR / name
    if default.is_file():
        return default
    return None


def load_theme_json() -> dict:
    path = resolve_branding_file("theme.json")
    if not path:
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def branding_path_preference(names: list[str]) -> Path | None:
    for name in names:
        resolved = resolve_branding_file(name)
        if resolved:
            return resolved
    return None


def get_app_name() -> str:
    return os.getenv("SUPERSET_APP_NAME") or load_theme_json().get(
        "app_name", "Superset"
    )


def get_theme_overrides() -> dict:
    theme = load_theme_json()
    overrides: dict = {}
    primary = os.getenv("SUPERSET_PRIMARY_COLOR") or theme.get("primary_color")
    secondary = os.getenv("SUPERSET_SECONDARY_COLOR") or theme.get(
        "secondary_color"
    )
    if primary:
        overrides.setdefault("colors", {})["primary"] = {
            "base": primary,
        }
    if secondary:
        overrides.setdefault("colors", {})["secondary"] = {
            "base": secondary,
        }
    return overrides
```

- [ ] **Step 2: Commit**

```bash
git add superset/branding.py
git commit -m "feat: add branding path resolver with volume fallback"
```

---

### Task 4: Custom security manager (Keycloak + DB login)

**Files:**
- Create: `superset/security_manager.py`

- [ ] **Step 1: Create `superset/security_manager.py`**

```python
"""Keycloak OAuth with local DB login for break-glass admin."""
from __future__ import annotations

import logging
import os
from typing import Any

from flask import redirect, request, url_for
from flask_appbuilder.security.views import AuthDBView, AuthOAuthView
from superset.security import SupersetSecurityManager

logger = logging.getLogger(__name__)


class DualAuthOAuthView(AuthOAuthView):
    """Login page: OAuth (Keycloak) + database form."""

    @expose("/login/", methods=["GET", "POST"])
    def login(self):
        if request.method == "POST" and os.getenv("AUTH_LOCAL_ENABLED", "true").lower() == "true":
            return super().login()
        return super().login()


class DualAuthDBView(AuthDBView):
    """Expose DB login at /login/db for break-glass."""

    route_base = "/login/db"
    default_view = "login"


class CustomSecurityManager(SupersetSecurityManager):
    authoauthview = DualAuthOAuthView

    def oauth_user_info(
        self, provider: str, response: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if provider != "keycloak":
            return {}
        me = self.appbuilder.sm.oauth_remotes[provider].get("userinfo").json()
        return {
            "username": me.get("preferred_username") or me.get("sub"),
            "first_name": me.get("given_name", ""),
            "last_name": me.get("family_name", ""),
            "email": me.get("email", ""),
        }


# FAB exposes DB view when authdbview is set
CustomSecurityManager.authdbview = DualAuthDBView
```

Add at top of file if missing:

```python
from flask_appbuilder.api import expose
```

**Note:** If `DualAuthOAuthView` import path differs in image, use `flask_appbuilder.security.views.AuthOAuthView` only and set `AUTH_TYPE = AUTH_OAUTH`; verify DB login at `/login/db` during Task 10.

- [ ] **Step 2: Commit**

```bash
git add superset/security_manager.py
git commit -m "feat: add Keycloak security manager with DB fallback route"
```

---

### Task 5: Production `superset_config.py`

**Files:**
- Create: `superset/superset_config.py`

- [ ] **Step 1: Create `superset/superset_config.py`**

```python
"""Production Superset configuration (env-driven)."""
from __future__ import annotations

import json
import os
from datetime import timedelta

from celery.schedules import crontab
from flask_appbuilder.security.manager import AUTH_OAUTH

from branding import (
    branding_path_preference,
    get_app_name,
    get_theme_overrides,
    load_theme_json,
)
from security_manager import CustomSecurityManager

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
APP_NAME = get_app_name()
theme = load_theme_json()

_logo = branding_path_preference(["logo.svg", "logo.png"])
if _logo:
    APP_ICON = str(_logo)
    LOGO_TARGET_PATH = None  # use APP_ICON for navbar

_favicon = branding_path_preference(["favicon.png", "favicon.ico"])
if _favicon:
    FAVICONS = [{"href": str(_favicon)}]

_theme_overrides = get_theme_overrides()
if _theme_overrides:
    THEME_DEFAULT = _theme_overrides
    THEME_OVERRIDES = _theme_overrides

# ---------------------------------------------------------------------------
# Security / proxy
# ---------------------------------------------------------------------------
ENABLE_PROXY_FIX = True
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
WTF_CSRF_ENABLED = True
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    "content_security_policy": {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        "style-src": ["'self'", "'unsafe-inline'"],
    },
    "force_https": False,  # TLS terminated at external proxy
}

PERMANENT_SESSION_LIFETIME = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8"))
)

ENABLE_TEMPLATE_PROCESSING = False
PUBLIC_ROLE_LIKE_GAMMA = False
AUTH_USER_REGISTRATION = False

# ---------------------------------------------------------------------------
# Auth: Keycloak OIDC + local DB
# ---------------------------------------------------------------------------
AUTH_TYPE = AUTH_OAUTH
CUSTOM_SECURITY_MANAGER = CustomSecurityManager

KEYCLOAK_BASE = os.environ["KEYCLOAK_BASE_URL"].rstrip("/")
KEYCLOAK_REALM = os.environ["KEYCLOAK_REALM"]
KEYCLOAK_CLIENT_ID = os.environ["KEYCLOAK_CLIENT_ID"]
KEYCLOAK_CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
KEYCLOAK_SERVER_METADATA = (
    f"{KEYCLOAK_BASE}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
)

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET,
            "server_metadata_url": KEYCLOAK_SERVER_METADATA,
            "client_kwargs": {"scope": "openid email profile"},
        },
    }
]

AUTH_ROLES_SYNC_AT_LOGIN = True
_mapping = os.getenv("AUTH_ROLES_MAPPING_JSON", "{}")
AUTH_ROLES_MAPPING = json.loads(_mapping)

# ---------------------------------------------------------------------------
# Redis / cache / Celery
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_CELERY_DB = int(os.getenv("REDIS_CELERY_DB", "0"))
REDIS_RESULTS_DB = int(os.getenv("REDIS_RESULTS_DB", "1"))
REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", "2"))

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_CACHE_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG

class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    imports = ("superset.sql_lab",)
    worker_prefetch_multiplier = 1
    task_acks_late = True
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=0, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
FEATURE_FLAGS = {
    "PLAYWRIGHT_REPORTS_AND_THUMBNAILS": True,
    "ENABLE_TEMPLATE_PROCESSING": False,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("SUPERSET_LOG_LEVEL", "INFO")
```

- [ ] **Step 2: Commit**

```bash
git add superset/superset_config.py
git commit -m "feat: add production superset_config with OAuth, redis, branding"
```

---

### Task 6: Update Dockerfile

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Append config COPY and env after existing RUN blocks**

Add before `USER superset`:

```dockerfile
# Production config and baked branding defaults
COPY superset/branding.py superset/security_manager.py /app/pythonpath/
COPY superset/superset_config.py /app/pythonpath/superset_config.py
COPY superset/assets/branding/ /app/superset/static/assets/branding-default/

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
ENV PYTHONPATH=/app/pythonpath:${PYTHONPATH}
```

- [ ] **Step 2: Build image locally**

```bash
docker build -t superset-bphn:local .
```

Expected: build succeeds without errors.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: bake superset_config and branding-default into image"
```

---

### Task 7: Docker Compose stack

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

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
    build: .
    image: superset-bphn:local
    restart: unless-stopped
    env_file: .env
    ports:
      - "127.0.0.1:8088:8088"
    volumes:
      - ./superset/assets/branding:/app/superset/static/assets/branding:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: ["/bin/sh", "-c", "superset db upgrade && /app/docker/entrypoints/run-server.sh"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8088/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  superset-worker:
    image: superset-bphn:local
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./superset/assets/branding:/app/superset/static/assets/branding:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      superset:
        condition: service_healthy
    command: ["celery", "--app=superset.tasks.celery_app:app", "worker", "-O", "fair", "-l", "INFO"]

  superset-beat:
    image: superset-bphn:local
    restart: unless-stopped
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy
      superset:
        condition: service_healthy
    command: ["celery", "--app=superset.tasks.celery_app:app", "beat", "-l", "INFO"]

volumes:
  postgres_data:
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add production docker-compose stack"
```

---

### Task 8: Environment template

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`**

```bash
# --- Core ---
SUPERSET_SECRET_KEY=change-me-to-a-long-random-string
SUPERSET_WEBSERVER_BASE_URL=https://superset.example.com
PREFERRED_URL_SCHEME=https
SESSION_COOKIE_SECURE=true
SESSION_LIFETIME_HOURS=8
SUPERSET_LOG_LEVEL=INFO

# --- Metadata DB (compose postgres service) ---
POSTGRES_USER=superset
POSTGRES_PASSWORD=change-me
POSTGRES_DB=superset
DATABASE_URL=postgresql+psycopg2://superset:change-me@postgres:5432/superset

# --- Redis ---
REDIS_HOST=redis
REDIS_PORT=6379

# --- Keycloak OIDC (external) ---
KEYCLOAK_BASE_URL=https://keycloak.example.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=superset
KEYCLOAK_CLIENT_SECRET=change-me
# Map Keycloak groups to Superset roles, e.g. {"superset_admins":["Admin"],"superset_users":["Gamma"]}
AUTH_ROLES_MAPPING_JSON={"superset_admins":["Admin"],"superset_users":["Gamma"]}

# --- Branding overrides (optional; volume/file takes precedence) ---
# SUPERSET_APP_NAME=BPHN Analytics
# SUPERSET_PRIMARY_COLOR=#2893B3

# --- Local DB login (break-glass) ---
AUTH_LOCAL_ENABLED=true
```

- [ ] **Step 2: Create local `.env` for testing**

```bash
cp .env.example .env
# Edit secrets before docker compose up
```

- [ ] **Step 3: Commit**

```bash
git add .env.example
git commit -m "docs: add environment variable template"
```

---

### Task 9: README and ops documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`** with sections:

1. **Prerequisites** — Docker, Docker Compose, external Keycloak + reverse proxy  
2. **Quick start** — `cp .env.example .env`, edit secrets, `docker compose build`, `docker compose up -d`  
3. **Bootstrap admin** — `docker compose exec superset superset fab create-admin` (break-glass; login at `/login/db`)  
4. **Keycloak client** — redirect URI `https://<host>/oauth-authorized/keycloak`, confidential client, groups for `AUTH_ROLES_MAPPING_JSON`  
5. **Proxy** — forward `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-For` to port 8088  
6. **Branding** — build defaults in image; override files in `./superset/assets/branding/`; restart `superset` + workers  
7. **Backups** — `docker compose exec postgres pg_dump ...` or volume snapshot  

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add deployment and operations README"
```

---

### Task 10: Integration verification

**Files:** none (manual verification)

- [ ] **Step 1: Build and start stack**

```bash
docker compose build
docker compose up -d
docker compose ps
```

Expected: `postgres`, `redis`, `superset`, `superset-worker`, `superset-beat` all healthy (superset may take ~2 min on first boot).

- [ ] **Step 2: Create break-glass admin**

```bash
docker compose exec superset superset fab create-admin
```

- [ ] **Step 3: Init roles/permissions**

```bash
docker compose exec superset superset init
```

- [ ] **Step 4: Verify branding defaults**

Open `http://127.0.0.1:8088` — navbar shows baked logo and `APP_NAME` from `theme.json`.

- [ ] **Step 5: Verify volume override**

Replace `superset/assets/branding/logo.svg` with a different file, then:

```bash
docker compose restart superset
```

Reload UI — logo should change; favicon unchanged if not overridden.

- [ ] **Step 6: Verify Keycloak login** (requires real Keycloak in `.env`)

Click “Sign in with keycloak” — completes OAuth redirect and lands in Superset.

- [ ] **Step 7: Verify DB fallback**

Visit `http://127.0.0.1:8088/login/db` — log in with break-glass admin credentials.

- [ ] **Step 8: Verify Celery**

Run an async chart query or check worker logs:

```bash
docker compose logs superset-worker --tail=50
```

Expected: worker connected to Redis, no import errors.

- [ ] **Step 9: Update spec status**

In `docs/superpowers/specs/2026-05-19-superset-production-config-design.md`, change status to **Approved — implemented**.

- [ ] **Step 10: Commit**

```bash
git add docs/superpowers/specs/2026-05-19-superset-production-config-design.md
git commit -m "docs: mark production config spec as implemented"
```

---

## Plan self-review

| Spec requirement | Task |
|------------------|------|
| Compose: postgres, redis, web, worker, beat | Task 7 |
| External proxy TLS settings | Task 5 (`ENABLE_PROXY_FIX`, cookies, Talisman) |
| Keycloak OIDC | Task 4, 5, 8 |
| Local admin fallback | Task 4 (`/login/db`), 9, 10 |
| PostgreSQL metadata | Task 7, 8 |
| Build-time branding defaults | Task 2, 6 |
| Volume overrides with per-file fallback | Task 3, 7 |
| Security baseline | Task 5 |
| `.env.example` | Task 8 |
| README / ops | Task 9 |
| Testing checklist | Task 10 |
| Drivers (existing Dockerfile) | Task 6 (preserved) |

**Fix applied during review:** `security_manager.py` needs `from flask_appbuilder.api import expose` on `DualAuthOAuthView` — add during Task 4 implementation if `expose` is undefined.

**Out of scope (unchanged):** Keycloak/proxy containers, automated backups, K8s, CI/CD.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-superset-production-config.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement tasks in this session with checkpoints  

Which approach do you want?
