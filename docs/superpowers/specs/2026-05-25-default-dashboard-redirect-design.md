# Default Dashboard Redirect — Design Spec

**Date:** 2026-05-25  
**Status:** Approved (brainstorming)  
**Base image:** `apache/superset:6.1.0`

## Goal

After login, send every authenticated user to a **single default dashboard** instead of the stock Superset welcome page (`/superset/welcome/`), when configured via environment variable.

Operators choose the dashboard by **slug** in `.env`. Misconfiguration must **fail loudly** (no silent fallback to welcome or dashboard list).

## Decisions Summary

| Area | Decision |
|------|----------|
| Post-login UX | Option **A**: skip welcome UI; redirect to one dashboard |
| Dashboard identity | `SUPERSET_DEFAULT_DASHBOARD_SLUG` in `.env` |
| Identifier | **Slug** only (not numeric ID) |
| Env unset / empty | Stock welcome page (no redirect hook) |
| Slug set, not found | **Error page** (404) with clear ops message |
| Slug set, no user access | **Error page** (403) with clear permission message |
| Implementation | `FLASK_APP_MUTATOR` + `before_request` on welcome paths |
| Code layout | `superset/welcome_redirect.py` + thin registration in `superset_config.py` |

## Context

- **superset-bphn** ships custom branding and production config; post-login flow in Superset 6 is: auth → `SupersetIndexView.index` → `/superset/welcome/`.
- `theme.json` includes `welcome_message` but it is **not** wired into theme tokens and is **out of scope** for this feature.
- Example-dashboards spec listed a custom BPHN welcome dashboard as a future item; this spec covers **redirect-only** landing, not a curated export or custom welcome UI.

## Behavior

| Condition | Result |
|-----------|--------|
| `SUPERSET_DEFAULT_DASHBOARD_SLUG` unset or whitespace-only | No interception; default Superset welcome |
| Slug set, dashboard exists, user has access | HTTP redirect to dashboard view URL |
| Slug set, no matching dashboard in metadata DB | Error response (404): misconfigured slug |
| Slug set, dashboard exists, user lacks permission | Error response (403): no access to default dashboard |

**Logging:**

- **INFO** on successful redirect (slug, username).
- **WARNING** when slug is configured but dashboard row is missing (ops typo).

Do **not** fall back to `/dashboard/list/` or welcome when the slug is set but invalid or inaccessible (explicit **F3** requirement).

## Configuration

### Environment variable

```bash
# Optional. When set, authenticated visits to /superset/welcome/ redirect here.
# Dashboard slug must match Superset UI (Dashboard → Settings → slug).
SUPERSET_DEFAULT_DASHBOARD_SLUG=bphn-overview
```

Document in:

- `.env.example`
- `README.md` (ops: create dashboard, set slug, set env, recreate `superset`)
- Curl installer / install docs if they reference post-login behavior

### Operational notes

1. Create or import the target dashboard in Superset.
2. Set a stable **slug** on the dashboard (required for env-based targeting).
3. Ensure roles (e.g. Gamma via Keycloak mapping) include permission to view that dashboard.
4. Set `SUPERSET_DEFAULT_DASHBOARD_SLUG` and restart the `superset` service (workers do not need this hook).

## Architecture

### Approach (recommended)

Use **`FLASK_APP_MUTATOR`** in `superset_config.py` to register a **`before_request`** handler. Do **not** monkey-patch `Superset.welcome()` or override `FAB_INDEX_VIEW` (unreliable or ignored in Superset 6).

### Components

| Piece | Role |
|-------|------|
| `SUPERSET_DEFAULT_DASHBOARD_SLUG` | Master switch; unset disables feature |
| `welcome_redirect.py` | Slug resolution, RBAC check, redirect or error response |
| `FLASK_APP_MUTATOR` | Registers handler after app init |
| `Dashboard` model | Lookup by `slug` in metadata database |
| `security_manager` | Same access rules as opening dashboard in UI |

### Request paths intercepted

Minimum (v1):

- `/superset/welcome/`
- `/superset/welcome`

Handler runs only when:

- Request path matches one of the above, and
- User is authenticated (`current_user` / `g.user`).

**Smoke test during implementation:** If authenticated users still see welcome after login via `/` only, add `/` to the path list; do not add preemptively without evidence.

### Redirect target URL

Build with Flask **`url_for`** or AppBuilder helpers so **`APPLICATION_ROOT`** and reverse-proxy deployments (`SUPERSET_WEBSERVER_BASE_URL`) produce correct absolute/relative URLs.

Prefer canonical Superset 6 dashboard route (verify in 6.1.0 smoke test), typically:

- `/superset/dashboard/<slug>/` or
- `/superset/dashboard/<id>/`

Use slug in URL when supported; otherwise resolve slug to id for redirect.

### Error responses (F3)

Return a minimal HTML page (or Superset-consistent error template) with:

- HTTP status **404** — slug configured but no dashboard row
- HTTP status **403** — dashboard exists but `security_manager` denies access

Message body should tell operators to check `SUPERSET_DEFAULT_DASHBOARD_SLUG`, dashboard slug in UI, and user role permissions. No redirect to welcome or list.

### Repository layout (additions)

```
superset-bphn/
├── superset/
│   ├── superset_config.py       # FLASK_APP_MUTATOR → register_welcome_redirect(app)
│   └── welcome_redirect.py      # core logic
├── .env.example                 # SUPERSET_DEFAULT_DASHBOARD_SLUG
└── README.md                    # Default landing dashboard section
```

## Security

- Run access check through **`security_manager`** (or equivalent `can_access_dashboard`) — never redirect to a dashboard id/slug the user cannot open in the UI.
- Handler must no-op for unauthenticated requests (login flow unchanged).
- Do not leak existence of dashboards to anonymous users on welcome paths; only authenticated users hit this logic after login.

## Out of Scope (v1)

- Role-based landing URLs
- Custom welcome page content, banners, or `welcome.message` frontend plugin
- Auto-creating or bundling the default dashboard
- Numeric dashboard ID env var
- Changing `SUPERSET_BRAND_LOGO_HREF` (remains `/` unless changed separately)
- Wiring `theme.json` `welcome_message` into theme tokens

## Testing

Manual verification checklist:

1. Env unset → login (DB and OAuth) → stock welcome page.
2. Valid slug, user with access → lands on target dashboard.
3. Invalid slug → error page (404), not welcome.
4. Valid slug, user without dashboard access → error page (403).
5. Direct navigation to `/superset/welcome/` when env set → redirect (bookmark behavior).
6. Deployment behind reverse proxy with `SUPERSET_WEBSERVER_BASE_URL` → redirect URL correct.

## Future Enhancements (not planned)

- Optional `SUPERSET_BRAND_LOGO_HREF` pointing at default dashboard when redirect enabled
- Role-based default dashboards
- Curated BPHN onboarding dashboard export bundled with image
- Client-side welcome customization via frontend plugin
