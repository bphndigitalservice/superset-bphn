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
