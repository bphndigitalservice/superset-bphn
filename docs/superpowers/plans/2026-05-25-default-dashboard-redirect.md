# Default Dashboard Redirect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After login, redirect authenticated users from `/superset/welcome/` to a dashboard identified by `SUPERSET_DEFAULT_DASHBOARD_SLUG`, with loud 404/403 errors when misconfigured.

**Architecture:** New `welcome_redirect.py` module resolves slug via SQLAlchemy, checks `security_manager.can_access_dashboard()`, and returns redirect or HTML error. `superset_config.py` registers the handler through `FLASK_APP_MUTATOR` + `before_request` (Superset 6–safe; no `FAB_INDEX_VIEW` override).

**Tech Stack:** Apache Superset 6.1.0, Flask, Flask-AppBuilder, SQLAlchemy, Python `unittest` (stdlib).

**Spec:** `docs/superpowers/specs/2026-05-25-default-dashboard-redirect-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `superset/welcome_redirect.py` | Slug env read, welcome path match, DB lookup, RBAC, redirect/error responses |
| `superset/test_welcome_redirect.py` | Unit tests for env/path/HTML helpers (no live DB) |
| `superset/superset_config.py` | `FLASK_APP_MUTATOR` → `register_welcome_redirect(app)` |
| `Dockerfile` | `COPY` `welcome_redirect.py` into `/app/pythonpath/` |
| `.env.example` | Document `SUPERSET_DEFAULT_DASHBOARD_SLUG` |
| `README.md` | Ops section: create dashboard, set slug, env, smoke checklist |

---

### Task 1: Pure helpers + unit tests

**Files:**
- Create: `superset/welcome_redirect.py` (helpers only first)
- Create: `superset/test_welcome_redirect.py`

- [ ] **Step 1: Create `superset/welcome_redirect.py` (helpers)**

```python
"""Post-login redirect from /superset/welcome/ to a configured dashboard slug."""
from __future__ import annotations

import logging
import os
from html import escape

logger = logging.getLogger(__name__)

ENV_SLUG = "SUPERSET_DEFAULT_DASHBOARD_SLUG"

WELCOME_PATHS = frozenset(
    {
        "/superset/welcome/",
        "/superset/welcome",
    }
)


def get_configured_slug() -> str | None:
    slug = os.getenv(ENV_SLUG, "").strip()
    return slug or None


def is_welcome_path(path: str) -> bool:
    return path in WELCOME_PATHS


def build_dashboard_path(dashboard_slug: str) -> str:
    """Browser path for Superset 6 dashboard view (slug in URL)."""
    return f"/superset/dashboard/{dashboard_slug}/"


def render_error_html(*, status: int, slug: str, detail: str) -> str:
    title = "Default dashboard not available" if status == 404 else "Access denied"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #333; }}
    h1 {{ font-size: 1.25rem; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.35rem; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>{escape(detail)}</p>
  <p>Configured slug: <code>{escape(slug)}</code></p>
  <p>Check <code>{ENV_SLUG}</code> in <code>.env</code>, the dashboard slug in Superset
     (Dashboard → Settings), and that your user role can open that dashboard.</p>
</body>
</html>"""
```

- [ ] **Step 2: Create `superset/test_welcome_redirect.py`**

```python
"""Unit tests for welcome_redirect helpers (no Superset app required)."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from welcome_redirect import (
    ENV_SLUG,
    build_dashboard_path,
    get_configured_slug,
    is_welcome_path,
    render_error_html,
)


class TestWelcomeRedirectHelpers(unittest.TestCase):
    def test_get_configured_slug_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(get_configured_slug())

    def test_get_configured_slug_strips(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "  my-dash  "}):
            self.assertEqual(get_configured_slug(), "my-dash")

    def test_get_configured_slug_empty(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "   "}):
            self.assertIsNone(get_configured_slug())

    def test_is_welcome_path(self) -> None:
        self.assertTrue(is_welcome_path("/superset/welcome/"))
        self.assertTrue(is_welcome_path("/superset/welcome"))
        self.assertFalse(is_welcome_path("/dashboard/list/"))

    def test_build_dashboard_path(self) -> None:
        self.assertEqual(
            build_dashboard_path("bphn-overview"),
            "/superset/dashboard/bphn-overview/",
        )

    def test_render_error_html_404(self) -> None:
        html = render_error_html(
            status=404, slug="missing", detail="No dashboard with this slug."
        )
        self.assertIn("Default dashboard not available", html)
        self.assertIn("missing", html)
        self.assertIn(ENV_SLUG, html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run unit tests locally**

From repo root (Python 3.11+):

```bash
cd superset && python -m unittest test_welcome_redirect.py -v
```

Expected: `OK` (6 tests).

- [ ] **Step 4: Commit**

```bash
git add superset/welcome_redirect.py superset/test_welcome_redirect.py
git commit -m "feat: add welcome redirect helpers and unit tests"
```

---

### Task 2: Flask handler (DB lookup, RBAC, redirect)

**Files:**
- Modify: `superset/welcome_redirect.py` (append handler + registration)

- [ ] **Step 1: Append handler and registration to `welcome_redirect.py`**

Add after `render_error_html`:

```python
from typing import TYPE_CHECKING

from flask import g, redirect, request
from flask import make_response
from flask_login import current_user

if TYPE_CHECKING:
    from flask import Flask


def _dashboard_for_slug(slug: str):
    from superset.extensions import db
    from superset.models.dashboard import Dashboard

    return (
        db.session.query(Dashboard)
        .filter(Dashboard.slug == slug)
        .one_or_none()
    )


def handle_welcome_redirect():
    """before_request hook: redirect welcome → default dashboard when configured."""
    if not is_welcome_path(request.path):
        return None

    slug = get_configured_slug()
    if not slug:
        return None

    if not current_user or not getattr(current_user, "is_authenticated", False):
        return None

    dashboard = _dashboard_for_slug(slug)
    if dashboard is None:
        logger.warning(
            "Default dashboard slug %r not found (%s unset in DB)",
            slug,
            ENV_SLUG,
        )
        body = render_error_html(
            status=404,
            slug=slug,
            detail="No dashboard with this slug exists in the metadata database.",
        )
        return make_response(body, 404)

    from superset import security_manager

    if not security_manager.can_access_dashboard(dashboard):
        username = getattr(g.user, "username", None) or "unknown"
        logger.warning(
            "User %r denied access to default dashboard slug %r",
            username,
            slug,
        )
        body = render_error_html(
            status=403,
            slug=slug,
            detail="Your account does not have permission to view the configured default dashboard.",
        )
        return make_response(body, 403)

    username = getattr(g.user, "username", None) or "unknown"
    target = request.script_root + build_dashboard_path(slug)
    logger.info(
        "Redirecting user %r from welcome to default dashboard %r → %s",
        username,
        slug,
        target,
    )
    return redirect(target)


def register_welcome_redirect(app: "Flask") -> None:
    app.before_request(handle_welcome_redirect)
```

- [ ] **Step 2: Commit**

```bash
git add superset/welcome_redirect.py
git commit -m "feat: add welcome before_request redirect handler"
```

---

### Task 3: Wire `FLASK_APP_MUTATOR` in config

**Files:**
- Modify: `superset/superset_config.py` (end of file)

- [ ] **Step 1: Append to `superset/superset_config.py`**

```python
# ---------------------------------------------------------------------------
# Default dashboard redirect (optional)
# ---------------------------------------------------------------------------
def FLASK_APP_MUTATOR(app):  # noqa: N802
    from welcome_redirect import register_welcome_redirect

    register_welcome_redirect(app)
    return app
```

- [ ] **Step 2: Commit**

```bash
git add superset/superset_config.py
git commit -m "feat: register welcome redirect via FLASK_APP_MUTATOR"
```

---

### Task 4: Dockerfile COPY

**Files:**
- Modify: `Dockerfile` (line ~44)

- [ ] **Step 1: Add `welcome_redirect.py` to COPY**

Change:

```dockerfile
COPY --chown=superset:superset superset/branding.py superset/security_manager.py /app/pythonpath/
```

To:

```dockerfile
COPY --chown=superset:superset \
  superset/branding.py \
  superset/security_manager.py \
  superset/welcome_redirect.py \
  /app/pythonpath/
```

Optional: also copy `test_welcome_redirect.py` for in-container unittest during smoke test (not required for runtime).

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "build: copy welcome_redirect into pythonpath"
```

---

### Task 5: Documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add to `.env.example` after branding block**

```bash
# --- Default landing dashboard (optional) ---
# When set, authenticated users hitting /superset/welcome/ redirect here.
# Slug must match Dashboard → Settings in Superset UI.
# SUPERSET_DEFAULT_DASHBOARD_SLUG=bphn-overview
```

- [ ] **Step 2: Add README section after “Example dashboards & datasets”**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: document SUPERSET_DEFAULT_DASHBOARD_SLUG"
```

---

### Task 6: Build image and manual smoke test

**Files:** none (verification only)

Prerequisites: running stack, admin user, at least one dashboard with a known slug (e.g. from `LOAD_EXAMPLES=true` use slug `world_health` or create `bphn-overview`).

- [ ] **Step 1: Rebuild and recreate superset**

```bash
docker compose build superset
docker compose up -d --force-recreate superset
docker compose ps
```

Expected: `superset` healthy.

- [ ] **Step 2: Env unset — stock welcome**

Ensure `SUPERSET_DEFAULT_DASHBOARD_SLUG` is **not** in `.env`. Recreate if you removed it.

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8088/health
```

Log in via browser → should land on **welcome** (recents / favorites), not a forced dashboard.

- [ ] **Step 3: Valid slug — redirect**

Add to `.env`:

```bash
SUPERSET_DEFAULT_DASHBOARD_SLUG=world_health
```

(Or your test dashboard slug.)

```bash
docker compose up -d --force-recreate superset
```

Log in → browser should open `/superset/dashboard/world_health/` (or your slug), not welcome.

Direct hit while logged in:

```bash
# Session cookie required — easiest check is browser: open /superset/welcome/
```

- [ ] **Step 4: Invalid slug — 404**

```bash
SUPERSET_DEFAULT_DASHBOARD_SLUG=does-not-exist-xyz
```

Recreate `superset`, log in → **404** HTML page mentioning `SUPERSET_DEFAULT_DASHBOARD_SLUG`, not welcome.

- [ ] **Step 5: Forbidden slug — 403 (if reproducible)**

Use a dashboard slug the test user cannot access (e.g. Admin-only dashboard while logged in as Gamma). Expect **403** HTML, not welcome or list.

- [ ] **Step 6: In-container unit tests (optional)**

```bash
docker compose exec superset bash -c \
  'cd /app/pythonpath && python -m unittest test_welcome_redirect.py -v'
```

Expected: `OK` if test file was copied; skip if not copied (helpers already validated locally).

- [ ] **Step 7: Check logs**

```bash
docker compose logs superset --tail=50 | grep -i welcome
```

Expected on success: `Redirecting user ... from welcome to default dashboard`.

- [ ] **Step 8: Record results**

Note slug used, auth mode (`db` / `oauth`), and whether `/` after login needed an extra welcome path (if yes, add `/` to `WELCOME_PATHS` in a follow-up commit).

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Env slug `SUPERSET_DEFAULT_DASHBOARD_SLUG` | Task 1, 5 |
| Unset → no hook | `get_configured_slug()` returns None |
| Valid slug + access → redirect | Task 2 |
| Missing slug → 404 | Task 2 |
| No access → 403 | Task 2 |
| `FLASK_APP_MUTATOR` + `before_request` | Task 2, 3 |
| `security_manager.can_access_dashboard` | Task 2 |
| `script_root` for proxy paths | Task 2 `request.script_root` |
| `.env.example` + README | Task 5 |
| Manual test checklist | Task 6 |
| Dockerfile pythonpath | Task 4 |
| Out of scope (roles, custom welcome UI) | Not in plan |

## Out of scope (do not implement in this plan)

- Role-based redirects
- `SUPERSET_BRAND_LOGO_HREF` change
- Bundling/creating default dashboard
- Curl installer prompt for slug (optional future)
