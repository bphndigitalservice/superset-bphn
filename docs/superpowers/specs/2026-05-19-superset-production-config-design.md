# Superset Production Image & Docker Compose — Design Spec

**Date:** 2026-05-19  
**Status:** Approved — implemented  
**Base image:** `apache/superset:6.1.0`

## Goal

Extend `superset-bphn` from a driver-only Dockerfile into a production-ready Docker Compose stack with:

- Baked-in branding defaults (logo, favicon, theme) at **build time**
- Optional **runtime volume** overrides per file
- Full production services: PostgreSQL metadata, Redis, Celery worker & beat
- Keycloak OIDC SSO plus local admin fallback
- Security baseline suitable for deployment behind an **external** HTTPS reverse proxy

## Decisions Summary

| Area | Decision |
|------|----------|
| Deployment | Docker Compose on single host / small stack |
| Scope | Full production: branding, security, Redis, Celery, health checks, logging |
| Auth | Keycloak OIDC (primary) + local DB auth (break-glass admin) |
| Metadata DB | PostgreSQL |
| Branding | Full brand kit; build-time defaults + volume overrides |
| TLS | External reverse proxy (not in this compose stack) |
| SSO provider | Keycloak (external) |

## Repository Layout

```
superset-bphn/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── superset/
│   ├── superset_config.py
│   └── assets/branding/          # build input → copied to branding-default/
│       ├── logo.svg
│       ├── favicon.png
│       └── theme.json
├── docs/superpowers/specs/
│   └── 2026-05-19-superset-production-config-design.md
└── README.md                     # ops: env vars, Keycloak setup, backups
```

Host mount directory (optional overrides, may start empty):

```
./superset/assets/branding/  →  /app/superset/static/assets/branding/
```

## Docker Compose Services

| Service | Image | Role |
|---------|-------|------|
| `postgres` | `postgres:16` (or pinned minor) | Metadata database |
| `redis` | `redis:7-alpine` | Cache + Celery broker |
| `superset` | Custom build | Web (Gunicorn :8088) |
| `superset-worker` | Same custom image | Celery worker |
| `superset-beat` | Same custom image | Celery beat scheduler |

**External dependencies (not in compose):**

- Reverse proxy — TLS termination, forwards to Superset
- Keycloak — OIDC issuer

**Networking:**

- Internal Compose network for all services
- Publish `superset` only (e.g. `127.0.0.1:8088:8088`) for same-host proxy
- Do not expose `postgres` or `redis` publicly

**Startup order:**

1. `postgres` + `redis` healthy
2. `superset` runs `superset db upgrade` then starts app
3. `superset-worker` and `superset-beat` after DB ready

**Health checks:**

- Postgres: `pg_isready`
- Redis: `redis-cli ping`
- Superset: HTTP health endpoint

## Branding: Build-Time Defaults + Volume Overrides

### Paths

| Path | Source |
|------|--------|
| `.../branding-default/` | `COPY` at image build (always present) |
| `.../branding/` | Optional Compose volume (overrides) |

### Resolution order (per file)

1. Environment variable overrides (highest)
2. `branding/<file>` if exists on volume
3. `branding-default/<file>` (baked at build)

Supported files: `logo.svg` (or `.png`), `favicon.png`, `theme.json`.

### `theme.json` (public tokens only)

Example fields:

- `app_name`
- `primary_color`, `secondary_color`
- `welcome_message` (optional)

No secrets in `theme.json`.

### Dockerfile changes

- `COPY superset/assets/branding/` → `branding-default/`
- Keep existing driver installs (MySQL/MariaDB, Elasticsearch/OpenSearch, MSSQL, Authlib, Playwright, etc.)
- Set `SUPERSET_CONFIG_PATH` to custom `superset_config.py`

### Operational behavior

- Empty volume mount → all UI uses baked defaults
- Partial volume (e.g. only `logo.svg`) → only logo overridden
- Branding change without rebuild → replace file on host, restart `superset` (and workers if needed)

## Authentication

### Primary: Keycloak OIDC

Configure via environment (documented in `.env.example`):

- `AUTH_TYPE = AUTH_OAUTH`
- OAuth provider pointing at Keycloak realm
- Client ID / secret from env
- Map roles: Keycloak groups → Superset roles (`Admin`, `Alpha`, `Gamma`) via `AUTH_ROLES_MAPPING` or sync

### Fallback: Local (database) auth

- Keep `AUTH_DB` enabled for break-glass admin account
- Bootstrap admin via `superset fab create-admin` on first deploy (documented)
- Do not enable public self-registration

### Keycloak setup (documented, not automated)

- Create OIDC client (confidential)
- Valid redirect URI: `https://<superset-public-url>/oauth-authorized/keycloak` (exact path per provider name in config)
- CORS/web origins aligned with public URL

## Security & Production Settings

Secrets via `.env` only (gitignored); `.env.example` has placeholders.

| Setting | Value / notes |
|---------|----------------|
| `SECRET_KEY` | Long random string from env |
| `SQLALCHEMY_DATABASE_URI` | PostgreSQL via env |
| `CACHE_CONFIG` / `CELERY_CONFIG` | Redis URLs from env |
| `ENABLE_PROXY_FIX` | `True` |
| `PREFERRED_URL_SCHEME` | `https` |
| `SESSION_COOKIE_SECURE` | `True` |
| `SESSION_COOKIE_HTTPONLY` | `True` |
| `WTF_CSRF_ENABLED` | `True` |
| `TALISMAN_ENABLED` | `True` (CSP compatible with Superset static assets) |
| `PERMANENT_SESSION_LIFETIME` | Configurable (e.g. 8h) |
| `ENABLE_TEMPLATE_PROCESSING` | `False` unless explicitly needed |
| `PLAYWRIGHT_REPORTS_AND_THUMBNAILS` | `True` |
| Public / anonymous access | Disabled |

Logging: stdout, level from `SUPERSET_LOG_LEVEL`.

Backups: operational note to snapshot Postgres volume on schedule (not implemented in code).

Further hardening (stricter CSP, IP allowlist) deferred per user request.

## Environment Variables (`.env.example`)

Required groups:

- **Core:** `SUPERSET_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, public `SUPERSET_WEBSERVER_BASE_URL`
- **Postgres:** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- **Keycloak:** issuer URL, client ID, client secret, optional role mapping JSON
- **Branding overrides:** optional `SUPERSET_APP_NAME`, color overrides
- **Admin bootstrap:** documented one-time commands, not stored in repo

## Data Flow

```text
User → External proxy (TLS) → superset:8088
                              ↓
                    superset_config.py
                              ↓
              postgres (metadata) + redis (cache/celery)
                              ↓
              superset-worker / beat (async jobs)

Login: User → Keycloak → OAuth callback → Superset session
Fallback: User → local DB auth → Superset session
```

## Error Handling & Operations

- Services `restart: unless-stopped`
- Failed DB migration blocks app start (fail fast)
- Health checks drive Compose `depends_on` conditions
- README covers: first-time init, admin creation, Keycloak client setup, volume branding updates

## Out of Scope (this iteration)

- Keycloak or reverse proxy containers in compose
- Automated Postgres backups
- Kubernetes / Helm manifests
- Stricter CSP tuning beyond Talisman defaults
- CI/CD pipeline (can follow in implementation plan)

## Testing Checklist (implementation verification)

- [ ] `docker compose up` — all services healthy
- [ ] Login via Keycloak succeeds; roles applied
- [ ] Local admin login works when SSO unavailable
- [ ] Empty branding volume shows baked logo/theme
- [ ] Volume override of `logo.svg` only changes logo
- [ ] HTTPS cookies/proxy headers work behind external proxy
- [ ] Celery worker processes async query
- [ ] Playwright thumbnail generation (if feature enabled)

## Implementation Approach

**Chosen:** Monorepo production bundle (Approach 1) — custom image + compose + env-driven config, with dual-path branding (baked default + volume override).

**Rejected for v1:**

- Config-only volume without build defaults (user required build-time defaults)
- Separate dev/prod compose files (unnecessary complexity for now)

---

*Next step after approval: invoke `writing-plans` skill for implementation plan.*
