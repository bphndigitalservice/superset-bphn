# Curl Installer — Design Spec

**Date:** 2026-05-19  
**Status:** Approved (brainstorming)  
**Image:** `ghcr.io/bphndigitalservice/superset-bphn:latest` (public)

## Goal

Provide a one-command curl installer that deploys the BPHN Superset stack on a host with Docker — without cloning the repo or building images locally. The installer:

- Downloads or materializes a production-ready `docker-compose.yml` pointing at the latest GHCR image
- Auto-generates secrets (`SUPERSET_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`)
- Runs an interactive first-admin setup
- Supports **simple** (local demo) and **production** (HTTPS URL, proxy-oriented) paths
- Exposes separate **`install`** and **`upgrade`** commands on the same script

## Decisions Summary

| Area | Decision |
|------|----------|
| Delivery | Approach 2: thin bootstrap `scripts/install.sh` + templates fetched from GitHub `main` |
| Audience | Both simple and production paths in one interactive installer |
| Install location | Current working directory |
| Image tag | Always `latest` on install and upgrade |
| GHCR auth | Public — no `docker login` step |
| Re-run behavior | `install` fails if `.env` exists; `upgrade` refreshes compose + pulls image, never touches `.env` |
| Admin user | Interactive prompts (username, email, password with confirmation) |
| Auth at install | `SUPERSET_AUTH_TYPE=db` for both paths; production prints Keycloak enablement checklist |
| Examples | Optional prompt on install; default off; uses `LOAD_EXAMPLES` in `.env` (no Compose profiles in v1) |

## Invocation

```bash
# First install (interactive; default subcommand = install)
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash

# Explicit subcommands
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash -s install
curl -fsSL https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/main/scripts/install.sh | bash -s upgrade
```

## Prerequisites

- `docker` and Docker Compose v2 (`docker compose`)
- Bash 4+
- Outbound HTTPS: GitHub (templates), GHCR (image pull)
- For optional examples after install: outbound HTTPS to GitHub (see example-dashboards spec)

## Install Flow

1. **Preflight** — verify Docker, compose; `install` aborts if `.env` already exists.
2. **Mode** — user chooses **Simple** or **Production**.
3. **Configuration**
   - **Simple:** `SUPERSET_WEBSERVER_BASE_URL=http://127.0.0.1:8088`, `PREFERRED_URL_SCHEME=http`, `SESSION_COOKIE_SECURE=false`, bind `127.0.0.1:8088`.
   - **Production:** prompt for public HTTPS URL; set `PREFERRED_URL_SCHEME=https`, `SESSION_COOKIE_SECURE=true`, `SUPERSET_WEBSERVER_BASE_URL` to user URL; bind `127.0.0.1:8088` (reverse proxy in front).
   - Both: `SUPERSET_AUTH_TYPE=db`.
4. **Secrets** — generate `SUPERSET_SECRET_KEY`, `POSTGRES_PASSWORD`; build matching `DATABASE_URL`; write `.env` from template (`chmod 600`). Do not log secret values.
5. **Admin** — interactive username, email, password (confirm); password not stored in `.env`.
6. **Examples** — optional yes/no → `LOAD_EXAMPLES=true|false` in `.env`.
7. **Artifacts** — fetch `docker/docker-compose.install.yml` → `docker-compose.yml`; create empty `branding/`; optional `.install-meta` (mode, date, installer ref).
8. **Deploy** — `docker compose pull && docker compose up -d`.
9. **Wait** — poll superset healthcheck (timeout ~5 minutes).
10. **Bootstrap** — `superset fab create-admin` (non-interactive) + `superset init`; skip gracefully if admin already exists.
11. **Summary** — URL, login path, `.env` path, upgrade command; production also prints Keycloak + reverse-proxy checklist.

## Upgrade Flow

1. Require `.env` and `docker-compose.yml` in cwd.
2. Re-download `docker/docker-compose.install.yml` → `docker-compose.yml` (image remains `:latest`).
3. `docker compose pull && docker compose up -d --force-recreate`.
4. Do not modify `.env` or recreate admin.
5. Print success (optionally show pulled image digest).

## Repository Artifacts

| File | Role |
|------|------|
| `scripts/install.sh` | Bootstrap: subcommands, prompts, secret generation, orchestration |
| `docker/docker-compose.install.yml` | Install compose: GHCR image, no `build:`, same service topology as dev stack |
| `install/.env.template` | Placeholders substituted by installer (`{{SUPERSET_SECRET_KEY}}`, etc.) |

### Template fetch URLs

```
https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/${INSTALLER_REF}/docker/docker-compose.install.yml
https://raw.githubusercontent.com/bphndigitalservice/superset-bphn/${INSTALLER_REF}/install/.env.template
```

`INSTALLER_REF` defaults to `main` (constant embedded in `install.sh`). Pinning installer behavior to a git tag is out of scope for v1.

## Install Directory Layout

After `install` in the chosen cwd:

```
./
├── docker-compose.yml
├── .env                    # mode 600
├── branding/               # optional runtime overrides (empty initially)
└── .install-meta           # optional: mode, install date, installer ref
```

## Compose Differences (install vs dev)

| Aspect | Dev `docker-compose.yml` | `docker-compose.install.yml` |
|--------|--------------------------|------------------------------|
| Image | `build: .` + `superset-bphn:local` | `ghcr.io/bphndigitalservice/superset-bphn:latest` |
| Branding mount | `./superset/assets/branding` | `./branding` |
| Examples profile | `docker/compose.examples.yaml` profile | `LOAD_EXAMPLES` env only (v1) |

Services unchanged: `postgres`, `redis`, `superset`, `superset-worker`, `superset-beat`.

## Environment: Simple vs Production

| Variable | Simple | Production |
|----------|--------|------------|
| `SUPERSET_WEBSERVER_BASE_URL` | `http://127.0.0.1:8088` | User HTTPS URL |
| `PREFERRED_URL_SCHEME` | `http` | `https` |
| `SESSION_COOKIE_SECURE` | `false` | `true` |
| `SUPERSET_AUTH_TYPE` | `db` | `db` |

Shared generated values: `SUPERSET_SECRET_KEY`, `POSTGRES_*`, `DATABASE_URL`, Redis defaults from `.env.example`.

## Admin Bootstrap

```bash
docker compose exec -T superset superset fab create-admin \
  --username "$ADMIN_USER" \
  --firstname Admin \
  --lastname User \
  --email "$ADMIN_EMAIL" \
  --password "$ADMIN_PASSWORD"
docker compose exec -T superset superset init
```

- Password collected with `read -s`; confirmation required; never echoed.
- If user already exists, log and continue (do not fail install).

## Production Post-Install Checklist (printed only)

1. Configure reverse proxy → `127.0.0.1:8088` with `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-For`.
2. Confirm `SUPERSET_WEBSERVER_BASE_URL` matches the public URL.
3. To enable Keycloak later:
   - Create OIDC client; redirect URI `https://<host>/oauth-authorized/keycloak`
   - Set `SUPERSET_AUTH_TYPE=oauth` and `KEYCLOAK_*` in `.env`
   - `docker compose up -d --force-recreate superset superset-worker superset-beat`
   - Break-glass login remains at `/login/db`

## Error Handling

| Check | On failure |
|-------|------------|
| `docker` / `docker compose` | Exit with install Docker guidance |
| `install` + existing `.env` | Exit: use `upgrade` or remove `.env` to reinstall |
| `upgrade` + missing `.env`/compose | Exit: run `install` first |
| Template fetch | Exit: network / GitHub availability |
| `docker compose pull` | Exit: GHCR reachability |
| Healthcheck timeout (~5 min) | Print last lines of `docker compose logs superset`, exit non-zero |

Script uses `set -euo pipefail`. Avoid `set -x` while handling passwords.

## Security

- `.env` created with `chmod 600`.
- Secrets generated on host only; not transmitted except into local files.
- Admin password stored only in Superset metadata DB, not in `.env`.
- Public GHCR image — no registry credentials in v1.

## Testing

| Level | Scope |
|-------|--------|
| CI (optional) | Shellcheck on `scripts/install.sh` |
| Manual smoke | Fresh Linux VM → simple install → `curl /health` → admin login |
| Manual upgrade | Install → `upgrade` → services healthy, `.env` unchanged |

## Out of Scope (v1)

- `uninstall` command
- Automatic Keycloak client registration
- Non-interactive flags (`--yes`, env-only install)
- Air-gapped / offline bundle
- Image version pinning (always `latest`)
- Installer ref pinning via env (future)
- Custom branding upload during install (empty `branding/` only)
- macOS guarantees beyond best effort

## README Addition

Add a **Quick install** section with the curl one-liner and link to this spec.

## Related Specs

- [Example dashboards design](./2026-05-19-example-dashboards-design.md) — `LOAD_EXAMPLES` behavior
- [Production config design](./2026-05-19-superset-production-config-design.md) — auth, Keycloak, env vars
