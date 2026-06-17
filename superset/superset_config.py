"""Production Superset configuration (env-driven)."""
from __future__ import annotations

import json
import os
from datetime import timedelta

from celery.schedules import crontab
from flask_appbuilder.security.manager import AUTH_DB, AUTH_OAUTH

from branding import (
    branding_path_preference,
    branding_web_path,
    build_theme_config,
    get_app_name,
    get_logo_urls,
)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Connection pool tuning — defaults (pool_size=5, max_overflow=10) cause
# "QueuePool limit reached" errors under concurrent dashboard loads.
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": int(os.getenv("SQLALCHEMY_POOL_SIZE", "20")),
    "max_overflow": int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "20")),
    "pool_timeout": int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "30")),
    "pool_recycle": int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "1800")),
    "pool_pre_ping": True,
}

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
APP_NAME = get_app_name()

# Superset 6: logos live in theme tokens (APP_ICON alone is ignored when themes apply).
_light_logo, _dark_logo = get_logo_urls()
if _light_logo or _dark_logo:
    THEME_DEFAULT = build_theme_config(dark=False)
    THEME_DARK = build_theme_config(dark=True)
    THEME_OVERRIDES = THEME_DEFAULT

_favicon = branding_path_preference(["favicon.png", "favicon.ico"])
if _favicon:
    FAVICONS = [{"href": branding_web_path(_favicon)}]

# ---------------------------------------------------------------------------
# Security / proxy
# ---------------------------------------------------------------------------
ENABLE_PROXY_FIX = True
_webserver_base = os.getenv("SUPERSET_WEBSERVER_BASE_URL", "").strip()
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https").strip().lower()
if PREFERRED_URL_SCHEME not in ("http", "https"):
    PREFERRED_URL_SCHEME = "https"

SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

# Root cause of "CSRF session token is missing" on plain HTTP: browsers never store
# or send Secure session cookies on http://. Align flags with SUPERSET_WEBSERVER_BASE_URL.
if _webserver_base.startswith("http://"):
    if SESSION_COOKIE_SECURE:
        print(
            "[superset_config] INFO: SUPERSET_WEBSERVER_BASE_URL uses http:// — forcing "
            "SESSION_COOKIE_SECURE=false (Secure cookies are not applied on HTTP; without "
            "this, login and CSRF refresh fail).",
            flush=True,
        )
    SESSION_COOKIE_SECURE = False
    if PREFERRED_URL_SCHEME == "https":
        print(
            "[superset_config] INFO: SUPERSET_WEBSERVER_BASE_URL is http:// — setting "
            "PREFERRED_URL_SCHEME=http so redirects match how users reach the app.",
            flush=True,
        )
        PREFERRED_URL_SCHEME = "http"

SESSION_COOKIE_HTTPONLY = True
WTF_CSRF_ENABLED = True

TALISMAN_ENABLED = True
# Flask-Talisman has its OWN session_cookie_secure (default True). It stamps
# `Secure` onto the session cookie regardless of Flask's SESSION_COOKIE_SECURE.
# Over plain HTTP browsers (and curl) silently drop Secure cookies, so the
# Flask session vanishes on POST /login/ and CSRF validation fails with
# "The CSRF session token is missing". Mirror the Flask flag here so the two
# stay in lockstep. HSTS is also meaningless on http://, so disable it together.
#
# CSP is aligned with apache/superset 6.1.0 defaults. A minimal policy (only
# default-src/img-src) blocks Scarf telemetry pixels and can break map tiles
# and other connect-src targets the UI expects.
_THEME_FONT_DOMAINS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "use.typekit.net",
    "use.typekit.com",
)
TALISMAN_CONFIG = {
    "content_security_policy": {
        "base-uri": ["'self'"],
        "default-src": ["'self'"],
        "img-src": [
            "'self'",
            "blob:",
            "data:",
            "https://apachesuperset.gateway.scarf.sh",
            "https://static.scarf.sh/",
            "ows.terrestris.de",
            "https://cdn.document360.io",
        ],
        "worker-src": ["'self'", "blob:"],
        "connect-src": [
            "'self'",
            "https://api.mapbox.com",
            "https://events.mapbox.com",
            "https://tile.openstreetmap.org",
            "https://tile.osm.ch",
            "https://a.basemaps.cartocdn.com",
        ],
        "object-src": "'none'",
        "frame-src": ["'self'", "https://laporan.bphn.go.id", "https://fliphtml5.com"],
        "style-src": [
            "'self'",
            "'unsafe-inline'",
            *[f"https://{d}" for d in _THEME_FONT_DOMAINS],
        ],
        "font-src": [
            "'self'",
            *[f"https://{d}" for d in _THEME_FONT_DOMAINS],
        ],
        # unsafe-inline/eval: Superset 6 SPA bundles expect this in production
        # images (upstream dev config). strict-dynamic+nonce is upstream default
        # but needs nonce wiring through the app bootstrap.
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    },
    # TLS terminates at the reverse proxy; do not redirect http->https inside
    # the container or you race with the proxy and break ProxyFix.
    "force_https": False,
    "session_cookie_secure": SESSION_COOKIE_SECURE,
    "strict_transport_security": SESSION_COOKIE_SECURE,
}

PERMANENT_SESSION_LIFETIME = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8"))
)

ENABLE_TEMPLATE_PROCESSING = False
PUBLIC_ROLE_LIKE = "Gamma"
PUBLIC_ROLE_LIKE_GAMMA = True
AUTH_ROLE_PUBLIC = "Public"
AUTH_USER_REGISTRATION = False

# Avoid LanguagePicker crash when locale has no entry (apache/superset#39855).
LANGUAGES = {
    "en": {"flag": "us", "name": "English"},
}
BABEL_DEFAULT_LOCALE = "en"

# ---------------------------------------------------------------------------
# Auth: local DB only, or Keycloak OIDC + local break-glass (/login/db)
# Set SUPERSET_AUTH_TYPE=db | oauth in .env (must recreate containers after change)
# ---------------------------------------------------------------------------
_SUPERSET_AUTH_TYPE = os.getenv("SUPERSET_AUTH_TYPE", "db").strip().lower()

_USE_DB_AUTH = _SUPERSET_AUTH_TYPE in ("db", "database", "local", "auth_db")

if _USE_DB_AUTH:
    AUTH_TYPE = AUTH_DB
    OAUTH_PROVIDERS = []
else:
    from security_manager import CustomSecurityManager

    AUTH_TYPE = AUTH_OAUTH
    CUSTOM_SECURITY_MANAGER = CustomSecurityManager

    KEYCLOAK_BASE = os.environ["KEYCLOAK_BASE_URL"].rstrip("/")
    KEYCLOAK_REALM = os.environ["KEYCLOAK_REALM"]
    KEYCLOAK_CLIENT_ID = os.environ["KEYCLOAK_CLIENT_ID"]
    KEYCLOAK_CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
    KEYCLOAK_SERVER_METADATA = (
        f"{KEYCLOAK_BASE}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
    )

    OAUTH_PROVIDERS = [
        {
            "name": "keycloak",
            "icon": "fa-key",
            "token_key": "access_token",
            "remote_app": {
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "server_metadata_url": KEYCLOAK_SERVER_METADATA,
                "client_kwargs": {"scope": "openid email profile"},
            },
        }
    ]

    AUTH_ROLES_SYNC_AT_LOGIN = True
    AUTH_ROLES_MAPPING = json.loads(os.getenv("AUTH_ROLES_MAPPING_JSON", "{}"))

print(
    f"[superset_config] SUPERSET_AUTH_TYPE={_SUPERSET_AUTH_TYPE!r} "
    f"-> {'database' if _USE_DB_AUTH else 'oauth (Keycloak)'}",
    flush=True,
)

# ---------------------------------------------------------------------------
# Redis / cache / Celery
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_CELERY_DB = int(os.getenv("REDIS_CELERY_DB", "0"))
REDIS_RESULTS_DB = int(os.getenv("REDIS_RESULTS_DB", "1"))
REDIS_CACHE_DB = int(os.getenv("REDIS_CACHE_DB", "2"))

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_CACHE_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG


SUPERSET_HOME = os.getenv("SUPERSET_HOME", "/app/superset_home")


class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    imports = ("superset.sql_lab",)
    worker_prefetch_multiplier = 1
    task_acks_late = True
    beat_schedule_filename = os.path.join(SUPERSET_HOME, "celerybeat-schedule")
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=0, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
FEATURE_FLAGS = {
    "PLAYWRIGHT_REPORTS_AND_THUMBNAILS": True,
    "ENABLE_TEMPLATE_PROCESSING": False,
    "DASHBOARD_RBAC": True,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("SUPERSET_LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Currency Formatting (IDR locale)
# ---------------------------------------------------------------------------
D3_FORMAT = {
    "decimal": ",",
    "thousands": ".",
    "grouping": [3],
    "currency": ["Rp. ", ""]
}

# ---------------------------------------------------------------------------
# HTML Sanitization (Allow iframes)
# ---------------------------------------------------------------------------
HTML_SANITIZATION_SCHEMA_EXTENSIONS = {
    "tagNames": ["iframe"],
    "attributes": {
        "iframe": [
            "src",
            "width",
            "height",
            "frameborder",
            "allow",
            "allowfullscreen",
            "style",
        ]
    },
}

# ---------------------------------------------------------------------------
# Home nav menu (optional; uses SUPERSET_DEFAULT_DASHBOARD_SLUG)
# ---------------------------------------------------------------------------
from home_menu import home_menu_bootstrap_override

COMMON_BOOTSTRAP_OVERRIDES_FUNC = home_menu_bootstrap_override

# ---------------------------------------------------------------------------
# Default dashboard redirect (optional)
# ---------------------------------------------------------------------------
def FLASK_APP_MUTATOR(app):  # noqa: N802
    from home_menu import register_home_nav
    from welcome_redirect import register_welcome_redirect
    from sync_public_role import sync_public_role_permissions, auto_grant_public_to_default_dashboard

    register_home_nav(app)
    register_welcome_redirect(app)
    sync_public_role_permissions(app)
    auto_grant_public_to_default_dashboard(app)
    return app
