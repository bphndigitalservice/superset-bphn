"""Resolve branding files: env > volume mount > image defaults."""
from __future__ import annotations

import json
import os
from pathlib import Path

BRANDING_OVERRIDE_DIR = Path("/app/superset/static/assets/branding")
BRANDING_DEFAULT_DIR = Path("/app/superset/static/assets/branding-default")
STATIC_ROOT = Path("/app/superset/static")
# Bundled in the official image; avoids dev-only loading.svg path (base.py warning).
DEFAULT_SPINNER_URL = "/static/assets/images/loading.gif"


def resolve_branding_file(name: str) -> Path | None:
    override = BRANDING_OVERRIDE_DIR / name
    if override.is_file():
        return override
    default = BRANDING_DEFAULT_DIR / name
    if default.is_file():
        return default
    return None


def branding_web_path(path: Path) -> str:
    """Map filesystem path under static/ to a browser URL."""
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return f"/static/assets/branding-default/{path.name}"
    return f"/static/{relative.as_posix()}"


def load_theme_json() -> dict:
    path = resolve_branding_file("theme.json")
    if not path:
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def branding_path_preference(names: list[str]) -> Path | None:
    for name in names:
        resolved = resolve_branding_file(name)
        if resolved:
            return resolved
    return None


def get_app_name() -> str:
    return os.getenv("SUPERSET_APP_NAME") or load_theme_json().get(
        "app_name", "Superset"
    )


def get_color_tokens() -> dict[str, str]:
    """Ant Design v5 token keys for theme.json / env color overrides."""
    theme = load_theme_json()
    tokens: dict[str, str] = {}
    primary = os.getenv("SUPERSET_PRIMARY_COLOR") or theme.get("primary_color")
    secondary = os.getenv("SUPERSET_SECONDARY_COLOR") or theme.get("secondary_color")
    if primary:
        tokens["colorPrimary"] = primary
    if secondary:
        tokens["colorSuccess"] = secondary
    return tokens


def get_logo_urls() -> tuple[str | None, str | None]:
    """Return (light_mode_logo_url, dark_mode_logo_url)."""
    light_path = branding_path_preference(["logo.svg", "logo.png"])
    dark_path = branding_path_preference(
        ["logo-dark.svg", "logo-dark.png", "logo.svg", "logo.png"]
    )
    light_url = branding_web_path(light_path) if light_path else None
    dark_url = branding_web_path(dark_path) if dark_path else light_url
    return light_url, dark_url


def get_spinner_token() -> dict[str, str]:
    """Use bundled loading.gif so Superset skips missing frontend-source SVG."""
    return {"brandSpinnerUrl": os.getenv("SUPERSET_SPINNER_URL", DEFAULT_SPINNER_URL)}


def get_brand_tokens(logo_url: str | None) -> dict[str, str | int]:
    tokens: dict[str, str | int] = get_spinner_token()
    if not logo_url:
        return tokens
    tokens.update(
        {
            "brandLogoUrl": logo_url,
            # Required when brandLogoUrl is set — otherwise ensureAppRoot(undefined)
            # crashes with "Cannot read properties of undefined (reading 'startsWith')"
            # (apache/superset#39855).
            "brandLogoHref": os.getenv("SUPERSET_BRAND_LOGO_HREF", "/"),
            "brandLogoAlt": get_app_name(),
            "brandLogoHeight": "40px",
            "brandIconMaxWidth": 200,
        }
    )
    return tokens


def build_theme_config(*, dark: bool = False) -> dict:
    """Build THEME_DEFAULT or THEME_DARK with logo + colors in token format."""
    light_logo, dark_logo = get_logo_urls()
    logo_url = dark_logo if dark else light_logo

    token = {**get_color_tokens(), **get_brand_tokens(logo_url)}
    config: dict = {"token": token}
    if dark:
        config["algorithm"] = "dark"
    return config


def get_theme_overrides() -> dict:
    """Deprecated shape kept for callers; prefer build_theme_config()."""
    return build_theme_config(dark=False)
