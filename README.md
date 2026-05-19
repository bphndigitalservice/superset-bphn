# superset-bphn

Production Apache Superset image and Docker Compose stack for BPHN.

## Features

- Custom branding (baked defaults + runtime volume overrides)
- PostgreSQL metadata database
- Redis cache and Celery worker/beat
- Keycloak OIDC SSO with break-glass local admin at `/login/db`
- Database drivers: PostgreSQL, MySQL/MariaDB, Elasticsearch, OpenSearch, MSSQL

## Prerequisites

- Docker and Docker Compose
- External HTTPS reverse proxy (TLS termination)
- External Keycloak realm and OIDC client

## Quick start

1. Copy environment template and set secrets:

```bash
cp .env.example .env
# Edit .env — set SUPERSET_SECRET_KEY, POSTGRES_PASSWORD, Keycloak values
```

2. Add your brand assets (or keep placeholders):

```
superset/assets/branding/
├── logo.svg
├── favicon.png
└── theme.json
```

3. Build and start:

```bash
docker compose build
docker compose up -d
docker compose ps
```

4. Bootstrap admin (break-glass):

```bash
docker compose exec superset superset fab create-admin
docker compose exec superset superset init
```

5. Open Superset (via proxy or locally):

```
http://127.0.0.1:8088
```

## Authentication

Controlled by `SUPERSET_AUTH_TYPE` in `.env`:

| Value | Behavior |
|-------|----------|
| `db` | Local username/password only (standard `/login/`) |
| `oauth` | Keycloak SSO on `/login/`; break-glass admin at `/login/db` |

### Local DB only (disable Keycloak)

In `.env`:

```bash
SUPERSET_AUTH_TYPE=db
```

Keycloak variables are ignored in `db` mode. **Recreate** containers so env is picked up (restart alone is not always enough):

```bash
docker compose build superset
docker compose up -d --force-recreate superset superset-worker superset-beat
```

Confirm in logs:

```bash
docker compose logs superset 2>&1 | grep superset_config
# Expected: SUPERSET_AUTH_TYPE='db' -> database
```

Login at `/login/` (username/password form). No “Sign in with keycloak” button.

Create users with `superset fab create-admin` (first admin) or FAB user management after login.

### Keycloak SSO (default)

Set `SUPERSET_AUTH_TYPE=oauth` and configure Keycloak below.

## Keycloak client setup

Create a confidential OIDC client in Keycloak:

| Setting | Value |
|---------|--------|
| Valid redirect URI | `https://<your-superset-host>/oauth-authorized/keycloak` |
| Web origins | `https://<your-superset-host>` |
| Client authentication | On |

Set `KEYCLOAK_*` variables in `.env`. Map Keycloak groups to Superset roles via `AUTH_ROLES_MAPPING_JSON`.

## Reverse proxy

Terminate TLS at your proxy and forward to `127.0.0.1:8088` with headers:

- `X-Forwarded-Proto: https`
- `X-Forwarded-Host: <public-host>`
- `X-Forwarded-For: <client-ip>`

Set `SUPERSET_WEBSERVER_BASE_URL` to your public HTTPS URL.

## Branding

| Location | Purpose |
|----------|---------|
| Image `branding-default/` | Build-time defaults (from `superset/assets/branding/` at build) |
| Volume `branding/` | Runtime overrides (`./superset/assets/branding` mounted read-only) |

Per-file override: place only the files you want to change on the host mount. Missing files fall back to image defaults.

**Dark mode logo:** Superset 6 reads `brandLogoUrl` from `THEME_DARK`. Add `logo-dark.svg` (or `logo-dark.png`) for a logo tuned for dark backgrounds; otherwise the light logo is reused.

**Loading spinner:** Theme config sets `brandSpinnerUrl` to the bundled `loading.gif` so the app does not look for dev-only frontend source paths. Override with `SUPERSET_SPINNER_URL` in `.env` if needed.

After changing branding files:

```bash
docker compose restart superset superset-worker
```

## Break-glass login (oauth mode only)

When `SUPERSET_AUTH_TYPE=oauth` and Keycloak is unavailable:

```
https://<host>/login/db
```

## Backups

Dump metadata database:

```bash
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > superset-metadata-backup.sql
```

Or snapshot the `postgres_data` Docker volume on your backup schedule.

## Services

| Service | Port | Description |
|---------|------|-------------|
| superset | 8088 | Web UI |
| postgres | internal | Metadata DB |
| redis | internal | Cache + Celery broker |
| superset-worker | — | Async queries and reports |
| superset-beat | — | Scheduled reports |
