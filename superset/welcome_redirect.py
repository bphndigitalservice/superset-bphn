"""Post-login redirect from /superset/welcome/ to a configured dashboard slug."""
from __future__ import annotations

import logging
import os
from html import escape

logger = logging.getLogger(__name__)

ENV_SLUG = "SUPERSET_DEFAULT_DASHBOARD_SLUG"
WEBSERVER_BASE_ENV = "SUPERSET_WEBSERVER_BASE_URL"

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


def build_default_dashboard_url(
    *,
    slug: str | None = None,
    app=None,
    application_root: str | None = None,
) -> str | None:
    """Full or root-prefixed dashboard URL for nav links and bookmarks.

    Uses SUPERSET_WEBSERVER_BASE_URL when set (e.g. https://host/superset/dashboard/slug/).
    Otherwise prefixes APPLICATION_ROOT / bootstrap application_root.
    """
    resolved_slug = slug or get_configured_slug()
    if not resolved_slug:
        return None

    path = build_dashboard_path(resolved_slug)

    webserver_base = os.getenv(WEBSERVER_BASE_ENV, "").strip().rstrip("/")
    if webserver_base:
        return f"{webserver_base}{path}"

    root = application_root
    if root is None and app is not None:
        root = app.config.get("APPLICATION_ROOT") or ""
    return f"{(root or '').rstrip('/')}{path}"


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


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def _dashboard_for_slug(slug: str):
    from superset.extensions import db
    from superset.models.dashboard import Dashboard

    return (
        db.session.query(Dashboard).filter(Dashboard.slug == slug).one_or_none()
    )


def handle_welcome_redirect():
    """before_request hook: redirect welcome → default dashboard when configured."""
    from flask import g, make_response, redirect, request
    from flask_login import current_user

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
            "Default dashboard slug %r not found (%s not in metadata DB)",
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
            detail=(
                "Your account does not have permission to view the configured "
                "default dashboard."
            ),
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
