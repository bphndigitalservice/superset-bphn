# Home Nav Menu Item Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepend a **Home** top-nav item linking to the default dashboard when `SUPERSET_DEFAULT_DASHBOARD_SLUG` is set, without changing the logo href.

**Architecture:** `home_menu.py` implements `home_menu_bootstrap_override()` registered as `COMMON_BOOTSTRAP_OVERRIDES_FUNC`. It reuses slug/path helpers from `welcome_redirect.py` and prepends a FAB-shaped menu dict to `menu_data.menu`.

**Tech Stack:** Apache Superset 6.1.0, Python 3, `COMMON_BOOTSTRAP_OVERRIDES_FUNC`, stdlib `unittest`.

**Spec:** `docs/superpowers/specs/2026-05-25-home-nav-menu-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `superset/home_menu.py` | Bootstrap override + `build_home_menu_item()` helper |
| `superset/test_home_menu.py` | Unit tests for menu injection logic |
| `superset/superset_config.py` | `COMMON_BOOTSTRAP_OVERRIDES_FUNC` assignment |
| `Dockerfile` | `COPY home_menu.py` into pythonpath |
| `.env.example` | Note that slug also enables Home nav |
| `README.md` | Extend “Default landing dashboard” section |

---

### Task 1: `home_menu` module + unit tests

**Files:**
- Create: `superset/home_menu.py`
- Create: `superset/test_home_menu.py`

- [ ] **Step 1: Create `superset/home_menu.py`**

```python
"""Inject a Home nav item when SUPERSET_DEFAULT_DASHBOARD_SLUG is configured."""
from __future__ import annotations

from typing import Any

from welcome_redirect import build_dashboard_path, get_configured_slug


def build_home_menu_item(*, application_root: str, slug: str) -> dict[str, str]:
    root = application_root or ""
    return {
        "name": "Home",
        "label": "Home",
        "icon": "fa-home",
        "url": root + build_dashboard_path(slug),
    }


def home_menu_bootstrap_override(bootstrap_data: dict[str, Any]) -> dict[str, Any]:
    """COMMON_BOOTSTRAP_OVERRIDES_FUNC: prepend Home to menu_data.menu."""
    slug = get_configured_slug()
    if not slug:
        return {}

    menu_data = bootstrap_data.get("menu_data")
    if not menu_data or "menu" not in menu_data:
        return {}

    application_root = bootstrap_data.get("application_root", "") or ""
    home_item = build_home_menu_item(application_root=application_root, slug=slug)

    return {
        "menu_data": {
            **menu_data,
            "menu": [home_item, *menu_data["menu"]],
        }
    }
```

- [ ] **Step 2: Create `superset/test_home_menu.py`**

```python
"""Unit tests for home_menu bootstrap override."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from home_menu import build_home_menu_item, home_menu_bootstrap_override
from welcome_redirect import ENV_SLUG


class TestHomeMenu(unittest.TestCase):
    def test_build_home_menu_item(self) -> None:
        item = build_home_menu_item(application_root="/analytics", slug="bphn-overview")
        self.assertEqual(item["label"], "Home")
        self.assertEqual(item["url"], "/analytics/superset/dashboard/bphn-overview/")
        self.assertEqual(item["icon"], "fa-home")

    def test_override_no_slug(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = home_menu_bootstrap_override(
                {
                    "application_root": "",
                    "menu_data": {"menu": [{"name": "Dashboards", "label": "Dashboards"}]},
                }
            )
        self.assertEqual(result, {})

    def test_override_prepends_home(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "my-dash"}):
            result = home_menu_bootstrap_override(
                {
                    "application_root": "",
                    "menu_data": {
                        "menu": [{"name": "Dashboards", "label": "Dashboards", "url": "/dashboard/list/"}],
                        "brand": {},
                        "navbar_right": {},
                        "settings": [],
                    },
                }
            )
        menu = result["menu_data"]["menu"]
        self.assertEqual(menu[0]["label"], "Home")
        self.assertEqual(menu[0]["url"], "/superset/dashboard/my-dash/")
        self.assertEqual(menu[1]["name"], "Dashboards")

    def test_override_missing_menu_data(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "x"}):
            self.assertEqual(home_menu_bootstrap_override({}), {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run unit tests**

```bash
cd superset && python3 -m unittest test_home_menu.py test_welcome_redirect.py -v
```

Expected: all tests OK.

- [ ] **Step 4: Commit**

```bash
git add superset/home_menu.py superset/test_home_menu.py
git commit -m "feat: add Home nav bootstrap override and tests"
```

---

### Task 2: Wire `superset_config.py`

**Files:**
- Modify: `superset/superset_config.py`

- [ ] **Step 1: Add import and config after logging block (before `FLASK_APP_MUTATOR`)**

```python
# ---------------------------------------------------------------------------
# Home nav menu (optional; uses SUPERSET_DEFAULT_DASHBOARD_SLUG)
# ---------------------------------------------------------------------------
from home_menu import home_menu_bootstrap_override

COMMON_BOOTSTRAP_OVERRIDES_FUNC = home_menu_bootstrap_override
```

Place this block **after** `LOG_LEVEL = ...` and **before** the `FLASK_APP_MUTATOR` section so both features are grouped at the end of the file.

- [ ] **Step 2: Commit**

```bash
git add superset/superset_config.py
git commit -m "feat: register Home nav via COMMON_BOOTSTRAP_OVERRIDES_FUNC"
```

---

### Task 3: Dockerfile COPY

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Add `home_menu.py` to pythonpath COPY**

```dockerfile
COPY --chown=superset:superset \
  superset/branding.py \
  superset/security_manager.py \
  superset/welcome_redirect.py \
  superset/home_menu.py \
  /app/pythonpath/
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "build: copy home_menu into pythonpath"
```

---

### Task 4: Documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update `.env.example` comment under default dashboard block**

```bash
# When set, also adds a "Home" item to the top nav (logo link unchanged).
```

- [ ] **Step 2: Extend README “Default landing dashboard” table**

Add row after existing table:

```markdown
| Valid slug, user has access | **Home** nav item (first in menu) + welcome redirect |
```

Add short paragraph:

```markdown
The **Home** link in the top navigation opens the same dashboard as the post-login redirect. The logo (top left) is not changed — configure `SUPERSET_BRAND_LOGO_HREF` separately if needed.
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: document Home nav menu with default dashboard slug"
```

---

### Task 5: Build and manual smoke test

**Files:** none (verification)

- [ ] **Step 1: Rebuild and recreate superset**

```bash
docker compose build superset
docker compose up -d --force-recreate superset
```

- [ ] **Step 2: Slug unset — no Home**

Remove `SUPERSET_DEFAULT_DASHBOARD_SLUG` from `.env`, recreate `superset`. Log in → top nav has **no Home** before Dashboards.

- [ ] **Step 3: Slug set — Home visible**

```bash
SUPERSET_DEFAULT_DASHBOARD_SLUG=world_health
```

Recreate, log in → **Home** is first nav item; click → `/superset/dashboard/world_health/`.

- [ ] **Step 4: Logo unchanged**

Click logo (top left) → still goes to `/` or welcome (not forced to dashboard).

- [ ] **Step 5: Welcome redirect still works**

With slug set, visit `/superset/welcome/` while logged in → still redirects to default dashboard (existing feature).

- [ ] **Step 6: Optional bootstrap inspection**

In browser devtools, inspect page bootstrap JSON (`menu_data.menu[0]`) or call an authenticated page source search for `"label":"Home"` to confirm server injection.

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Home → default dashboard URL | Task 1 `build_home_menu_item` |
| Logo unchanged | No code changes to `branding.py` |
| Slug unset → no Home | `get_configured_slug()` returns `{}` |
| Prepend first in menu | Task 1 `[home_item, *menu]` |
| `application_root` prefix | Task 1 |
| Reuse welcome_redirect helpers | Task 1 imports |
| `COMMON_BOOTSTRAP_OVERRIDES_FUNC` | Task 2 |
| Dockerfile pythonpath | Task 3 |
| README + `.env.example` | Task 4 |
| Manual tests | Task 5 |

## Out of scope (do not implement)

- Logo href sync with slug
- Frontend extension / Menu.tsx patch
- i18n / role-based Home
