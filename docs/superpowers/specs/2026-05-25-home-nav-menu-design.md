# Home Nav Menu Item — Design Spec

**Date:** 2026-05-25  
**Status:** Approved (brainstorming)  
**Base image:** `apache/superset:6.1.0`  
**Related:** [Default dashboard redirect](./2026-05-25-default-dashboard-redirect-design.md) (implemented)

## Goal

Add a labeled **Home** item to the Superset top navigation that opens the **default dashboard** (same target as `SUPERSET_DEFAULT_DASHBOARD_SLUG`), while leaving the **logo link unchanged** (M3).

## Decisions Summary

| Area | Decision |
|------|----------|
| Home target | **H1:** `/superset/dashboard/<slug>/` from `SUPERSET_DEFAULT_DASHBOARD_SLUG` |
| Logo | **M3:** unchanged — `SUPERSET_BRAND_LOGO_HREF` / stock brand path stays as today |
| Nav presentation | **Home** as first top-level item before Dashboards, Charts, etc. |
| Slug unset | No **Home** item in menu |
| Implementation | **`COMMON_BOOTSTRAP_OVERRIDES_FUNC`** — prepend item to `menu_data.menu` |
| URL helpers | Reuse `get_configured_slug()` and `build_dashboard_path()` from `welcome_redirect.py` |

## Context

- **superset-bphn** already redirects authenticated users from `/superset/welcome/` to the default dashboard when the slug env var is set (`welcome_redirect.py`).
- Stock Superset 6 has no **Home** nav label; the welcome experience is separate from the main menu.
- Superset exposes `COMMON_BOOTSTRAP_OVERRIDES_FUNC` in `superset_config.py` to merge into `common` bootstrap payload, including `menu_data` (see upstream `common_bootstrap_payload()` in `superset/views/base.py`).

## Behavior

| Condition | Top nav | Logo click |
|-----------|---------|------------|
| `SUPERSET_DEFAULT_DASHBOARD_SLUG` unset or empty | Stock menu only (no **Home**) | Unchanged |
| Slug set | **Home** prepended → dashboard URL for that slug | Unchanged (not slug-aware) |

**Home** click navigates to:

```
{application_root}/superset/dashboard/{slug}/
```

where `application_root` comes from bootstrap `common.application_root` (reverse-proxy / `APP_ROOT` safe).

**Access errors:** If the user cannot open the dashboard, Superset’s normal dashboard security UI applies. This spec does **not** reuse the custom 404/403 HTML pages used on `/superset/welcome/` (those remain welcome-only per redirect spec).

**Coexistence with welcome redirect:** Both features share the same env var. Enabling the slug enables redirect + **Home**; disabling it removes both.

## Architecture

### Approach (recommended)

Use **`COMMON_BOOTSTRAP_OVERRIDES_FUNC`** to return an updated `menu_data` dict with **Home** inserted at index 0. Do **not** fork the frontend or require `.supx` extensions for v1.

### Components

| Piece | Role |
|-------|------|
| `SUPERSET_DEFAULT_DASHBOARD_SLUG` | Master switch (shared with welcome redirect) |
| `welcome_redirect.py` | `get_configured_slug()`, `build_dashboard_path()` |
| `home_menu.py` (new) | `home_menu_bootstrap_override(bootstrap_data) -> dict` |
| `superset_config.py` | `COMMON_BOOTSTRAP_OVERRIDES_FUNC = home_menu_bootstrap_override` |
| Dockerfile | `COPY home_menu.py` into `/app/pythonpath/` |

### Menu item shape

Injected item (FAB-compatible dict):

```python
{
    "name": "Home",
    "label": "Home",
    "icon": "fa-home",
    "url": f"{application_root}/superset/dashboard/{slug}/",
}
```

Prepended to `bootstrap_data["menu_data"]["menu"]` before return.

### Override function

```python
def home_menu_bootstrap_override(bootstrap_data: dict) -> dict:
    slug = get_configured_slug()
    if not slug:
        return {}
    root = bootstrap_data.get("application_root", "") or ""
    home_item = {
        "name": "Home",
        "label": "Home",
        "icon": "fa-home",
        "url": root + build_dashboard_path(slug),
    }
    menu_data = bootstrap_data["menu_data"]
    return {
        "menu_data": {
            **menu_data,
            "menu": [home_item, *menu_data["menu"]],
        }
    }
```

Register in `superset_config.py`:

```python
COMMON_BOOTSTRAP_OVERRIDES_FUNC = home_menu_bootstrap_override
```

(Import from `home_menu` module.)

### Repository layout (additions)

```
superset-bphn/
├── superset/
│   ├── home_menu.py           # bootstrap override
│   ├── welcome_redirect.py    # shared slug helpers (existing)
│   └── superset_config.py     # COMMON_BOOTSTRAP_OVERRIDES_FUNC
├── Dockerfile                 # COPY home_menu.py
├── .env.example               # cross-reference slug + Home nav
└── README.md                  # document Home nav behavior
```

## UX notes

- **Active tab highlighting:** Stock `Menu.tsx` maps active state to paths like `/dashboard`, not `/superset/dashboard/`. **Home** may not show as “selected” while viewing the default dashboard. Accept for v1; optional frontend tweak is out of scope.
- **Mobile:** **Home** should appear in the main menu list built from the same `menu_data` (verify in smoke test).

## Security

- **Home** URL is only injected when slug is configured; no extra information leaked when feature is off.
- No bypass of `security_manager` — dashboard view enforces access on navigation.

## Out of Scope (v1)

- Changing `SUPERSET_BRAND_LOGO_HREF` or `LOGO_TARGET_PATH` when slug is set
- **Home** visible when slug env is unset
- Role-based Home URLs
- Frontend extension (`.supx`) or patched `Menu.tsx`
- Translated label via Flask-Babel (English `"Home"` only in v1)
- Custom 404/403 on Home navigation (welcome redirect keeps its own errors)

## Testing

Manual checklist:

1. Slug unset → no **Home** in nav; welcome redirect disabled (existing behavior).
2. Slug set → **Home** appears first; click opens correct dashboard.
3. Logo still goes to prior target (e.g. `/`), not the dashboard.
4. Post-login still redirects from welcome when slug set (existing redirect).
5. Behind reverse proxy / `application_root` → **Home** URL is correct.

## Future Enhancements (not planned)

- Sync logo to default dashboard (M1/M2 style)
- Highlight **Home** when viewing default dashboard (frontend)
- i18n for **Home** label
- `appbuilder.add_link` registration instead of bootstrap override
