"""Inject a Home nav item when SUPERSET_DEFAULT_DASHBOARD_SLUG is configured."""
from __future__ import annotations

import logging
from typing import Any

from welcome_redirect import (
    build_default_dashboard_url,
    build_home_nav_active_path,
    get_configured_slug,
)

logger = logging.getLogger(__name__)


def build_home_menu_item(*, application_root: str, slug: str) -> dict[str, str]:
    url = build_default_dashboard_url(slug=slug, application_root=application_root)
    if url is None:
        raise ValueError("slug is required to build Home menu item")
    return {
        "name": "Home",
        "label": "Home",
        "icon": "fa-home",
        "url": url,
    }


def _home_href(app) -> str | None:
    return build_default_dashboard_url(app=app)


def _sync_home_menu_permissions() -> None:
    """Grant menu_access on Home to roles that already have Dashboards menu access."""
    from superset import security_manager

    permission = "menu_access"
    view_menu = "Home"

    try:
        if not security_manager.exist_permission_on_views({permission}, {view_menu}):
            security_manager.add_permission_view_menu(permission, view_menu)

        for role in security_manager.get_all_roles():
            if not security_manager.exist_permission_on_roles(
                role, {permission}, {"Dashboards"}
            ):
                continue
            if security_manager.exist_permission_on_roles(
                role, {permission}, {view_menu}
            ):
                continue
            security_manager.add_permission_role(role, permission, view_menu)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Home menu permission sync skipped: %s", exc)


def register_home_nav(app) -> None:
    """Register Home in FAB menu (survives get_data permission filtering when synced)."""
    href = _home_href(app)
    if not href:
        print(
            "[home_menu] SUPERSET_DEFAULT_DASHBOARD_SLUG unset — Home nav disabled",
            flush=True,
        )
        return

    from flask_appbuilder.menu import MenuItem
    from superset.extensions import appbuilder

    if appbuilder.menu.find("Home"):
        return

    appbuilder.menu.menu.insert(
        0,
        MenuItem(name="Home", href=href, icon="fa-home", label="Home"),
    )
    _sync_home_menu_permissions()
    print(f"[home_menu] Registered Home nav → {href}", flush=True)


def home_menu_bootstrap_override(bootstrap_data: dict[str, Any]) -> dict[str, Any]:
    """COMMON_BOOTSTRAP_OVERRIDES_FUNC: prepend Home if not already in menu."""
    slug = get_configured_slug()
    if not slug:
        return {}

    menu_data = bootstrap_data.get("menu_data")
    if not menu_data or "menu" not in menu_data:
        return {}

    menu = menu_data["menu"]
    if any(item.get("name") == "Home" for item in menu):
        return {}

    application_root = bootstrap_data.get("application_root", "") or ""
    home_item = build_home_menu_item(application_root=application_root, slug=slug)
    active_path = build_home_nav_active_path(
        slug=slug, application_root=application_root
    )

    return {
        "home_nav_active_path": active_path,
        "menu_data": {
            **menu_data,
            "menu": [home_item, *menu],
        }
    }
