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

The compose file binds host port `8088` using `SUPERSET_PORT_PUBLISH_HOST` from `.env` (`0.0.0.0` for simple mode, `127.0.0.1` when installed for production behind a reverse proxy on the same host).

See [curl installer design](docs/superpowers/specs/2026-05-19-curl-installer-design.md) for modes, Keycloak checklist, and troubleshooting.

For development (local image build), use **Quick start** below.

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

## Example dashboards & datasets

Optional stock Apache examples (World Bank, flights, etc.) for onboarding and demos. Data is downloaded from GitHub on first load and stored in a local `examples` database connection.

| Environment | How to enable |
|-------------|----------------|
| Local dev | `docker compose --profile examples up -d` |
| Production | Set `LOAD_EXAMPLES=true` in `.env`, then `docker compose up -d --force-recreate superset` |
| Default | Off — no examples loaded |

**Requirements:** Outbound HTTPS to GitHub on first load; can take several minutes and use significant CPU. Not suitable for air-gapped installs without a mirror (v1).

**Bootstrap unchanged:** create admin and run `superset init` as above, then open **Dashboards** to explore examples.

**Manual load** (if startup load was skipped or failed):

```bash
docker compose exec superset superset load_examples
```

**Reset examples:** remove the `examples` database in **Data → Databases**, or wipe metadata (`docker compose down -v` destroys `postgres_data` — back up first).

## Default landing dashboard

Skip the stock welcome page and send users to one dashboard after login.

1. Create or import the dashboard in Superset.
2. Set its **slug** (Dashboard → Settings).
3. In `.env`:

```bash
SUPERSET_DEFAULT_DASHBOARD_SLUG=your-dashboard-slug
```

4. Recreate the web container:

```bash
docker compose up -d --force-recreate superset
```

| `SUPERSET_DEFAULT_DASHBOARD_SLUG` | Behavior |
|-----------------------------------|----------|
| Unset or empty | Stock welcome page |
| Valid slug, user has access | Redirect to `/superset/dashboard/<slug>/` |
| Slug not in database | HTTP 404 with configuration hint |
| Slug exists, user denied | HTTP 403 with permission hint |

Celery worker/beat do not need this variable.

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

### Troubleshooting: `CSRF session token is missing` on login

**Feedback loop:** Open DevTools → Application → Cookies for your host. After loading `/login/`, there should be a session cookie (often `session`). If it is absent after a full page load, the browser dropped it.

**Ranked causes**

1. **`SESSION_COOKIE_SECURE=true` while you use plain `http://` (e.g. `http://172.27.11.28:8088`).** Browsers do not store or send `Secure` cookies on HTTP, so Flask has no session on `POST /login/` → CSRF token missing. **`superset_config.py` forces `SESSION_COOKIE_SECURE=false` and `PREFERRED_URL_SCHEME=http` whenever `SUPERSET_WEBSERVER_BASE_URL` starts with `http://`**, so mis-copied `.env` still works after image rebuild. For clarity you can still set those vars explicitly in `.env`. Real production should use `https://` in `SUPERSET_WEBSERVER_BASE_URL` and TLS in front of the app.
2. **Base URL mismatch** (`SUPERSET_WEBSERVER_BASE_URL` does not match how users reach Superset), causing redirects and odd `next=` chains. *Fix:* align `SUPERSET_WEBSERVER_BASE_URL` with the real origin (or put HTTPS + correct `X-Forwarded-*` behind a proxy and use the public HTTPS URL).
3. **Third-party cookie / ITP issues** (rare for first-party same-host login). *Fix:* try another browser; rule out (1) first.

On container start, `superset_config` logs **INFO** lines when it auto-aligns cookies/scheme for `http://` base URLs.

**Talisman override:** Flask-Talisman also sets `session_cookie_secure` (default `true`). If login works in curl but the browser still fails, check the response `Set-Cookie` for an unexpected `Secure` flag — `superset_config.py` mirrors `SESSION_COOKIE_SECURE` into Talisman.

### Troubleshooting: Scarf CSP warning or API `403` after login

**Scarf pixel (`apachesuperset.gateway.scarf.sh`):** Harmless telemetry. Upstream Superset 6 allows it in `img-src`; a too-minimal CSP blocks it in the console only.

**API `403` on `/api/v1/chart`, `dashboard`, `recent_activity`, etc.:** Usually **role permissions**, not login. Sync FAB permissions and confirm your user has the **Admin** role:

```bash
docker compose exec superset superset init
docker compose exec superset superset fab list-users
```

If the user has no roles or only `Public`, recreate admin or assign **Admin** in **Settings → List Users**. Then hard-refresh the browser.

After upgrading the image or `superset_config.py`, recreate containers:

```bash
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash -s upgrade
```

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
| Image `branding-default/` | Build-time defaults (from `superset/assets/branding/` when the image is **built**) |
| Volume (curl install) | `./branding/` next to `docker-compose.yml` → `/app/superset/static/assets/branding` (see `docker/docker-compose.install.yml`) |
| Volume (clone / dev compose) | `./superset/assets/branding/` → same container path (`docker-compose.yml` in repo) |

**Important:** The curl installer creates an empty `./branding/` directory. Override files go there; anything you omit is served from **`branding-default/` inside the image**, which is populated at build time from `superset/assets/branding/` (including committed `logo.png` / `favicon.png` / `theme.json`). To change defaults for everyone, update those files in the repo and publish a new image.

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

## Troubleshooting: `could not translate host name "postgres"`

That message means the **Superset container cannot resolve the Compose service name `postgres`** (embedded Docker DNS), not wrong password.

**What your diagnostics showed**

- A Compose **default** bridge sometimes gets **`172.17.0.0/16`** (same idea as `docker0`), which can confuse **embedded DNS** for other containers.
- Your `NetworkSettings` later showed **`Gateway":"172.17.0.1"`** and **`IPAddress":"172.17.0.4"`** on `superset_superset_backend` — that is still the **`docker0` / default-bridge range**. Even with a separate network name, **Docker’s IPAM sometimes hands out `172.17.0.0/16` to user-defined bridges**, which duplicates routing and breaks service-to-service DNS (e.g. `postgres` from Superset).

This repo **pins** `superset_backend` to **`172.28.0.0/16`** in Compose so containers never land on `172.17.x` for this stack.

**If `docker compose up` errors with “pool overlaps” or “subnet already in use”**

Another project may already use `172.28.0.0/16`. Edit both compose files and pick an unused `/16` (e.g. `172.29.0.0/16`).

**After pulling these compose changes, recreate the stack** (required so the bridge gets the new subnet):

```bash
docker compose down --remove-orphans
docker compose up -d
```

Confirm `docker inspect superset-superset-1` shows **`172.28.x.x`**, not `172.17.x`, then:

```bash
docker compose exec superset getent hosts postgres
```

**Checklist**

1. **Bring the whole stack up** from the directory that contains `docker-compose.yml` (do not run only the `superset` image with plain `docker run`):

   ```bash
   docker compose ps
   ```

   You should see `postgres`, `redis`, `superset`, `superset-worker`, and `superset-beat` (names may include a project prefix).

2. **Confirm DNS from inside the web container:**

   ```bash
   docker compose exec superset getent hosts postgres
   ```

   You should get an IP address. If this fails, the `superset` container is not on the same Compose network as `postgres` (e.g. stack started from the wrong directory, or a broken Docker DNS setup).

3. **Recreate the stack after pulling compose changes** (new `superset_backend` network):

   ```bash
   docker compose down --remove-orphans
   docker compose up -d
   ```

4. **Re-check the app network** — `docker network inspect <project>_superset_backend` should show subnet **`172.28.0.0/16`** (not `172.17.x`) and **all five** containers with non-empty `IPv4Address`.

5. **VPN / corporate DNS / Docker Desktop** sometimes breaks container DNS. Restart Docker or disconnect VPN and retry step 2.

6. On startup the image entrypoint **waits up to 90s** for `postgres:5432` before `superset db upgrade`, so transient DNS/TCP races are less likely.

`DATABASE_URL` should keep host **`postgres`** (the service name) when using this repository’s Compose files.

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
