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
PREFERRED_URL_SCHEME = os.getenv("PREFERRED_URL_SCHEME", "https")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE_HTTPONLY = True
WTF_CSRF_ENABLED = True

_webserver_base = os.getenv("SUPERSET_WEBSERVER_BASE_URL", "").strip()
if _webserver_base.startswith("http://") and SESSION_COOKIE_SECURE:
    print(
        "[superset_config] WARNING: SUPERSET_WEBSERVER_BASE_URL uses http:// but "
        "SESSION_COOKIE_SECURE=true — browsers will not persist session cookies over "
        "plain HTTP, which breaks login (CSRF session token is missing). "
        "Set SESSION_COOKIE_SECURE=false and PREFERRED_URL_SCHEME=http for direct HTTP "
        "access, or use HTTPS (reverse proxy) and keep secure cookies.",
        flush=True,
    )
TALISMAN_ENABLED = True
TALISMAN_CONFIG = {
    "content_security_policy": {
        "default-src": ["'self'"],
        "img-src": ["'self'", "data:", "blob:"],
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        "style-src": ["'self'", "'unsafe-inline'"],
    },
    "force_https": False,
}

PERMANENT_SESSION_LIFETIME = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8"))
)

ENABLE_TEMPLATE_PROCESSING = False
PUBLIC_ROLE_LIKE_GAMMA = False
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
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("SUPERSET_LOG_LEVEL", "INFO")
