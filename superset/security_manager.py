"""Keycloak OAuth with local DB login for break-glass admin."""
from __future__ import annotations

import logging
from typing import Any

from flask_appbuilder.security.views import AuthDBView
from superset.security import SupersetSecurityManager

logger = logging.getLogger(__name__)


class DualAuthDBView(AuthDBView):
    """Expose DB login at /login/db for break-glass."""

    route_base = "/login/db"
    default_view = "login"


class CustomSecurityManager(SupersetSecurityManager):
    authdbview = DualAuthDBView

    def oauth_user_info(
        self, provider: str, response: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if provider != "keycloak":
            return {}
        remote = self.appbuilder.sm.oauth_remotes[provider]
        me = remote.get("userinfo").json()
        return {
            "username": me.get("preferred_username") or me.get("sub"),
            "first_name": me.get("given_name", ""),
            "last_name": me.get("family_name", ""),
            "email": me.get("email", ""),
        }
