"""Merge BPHN label_colors into dashboard JSON metadata on startup."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from chart_colors import BPHN_LABEL_COLORS, DEFAULT_COLOR_SCHEME

logger = logging.getLogger(__name__)


def _load_extra_label_colors() -> dict[str, str]:
    raw = os.getenv("BPHN_EXTRA_LABEL_COLORS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid BPHN_EXTRA_LABEL_COLORS_JSON: %s", exc)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("BPHN_EXTRA_LABEL_COLORS_JSON must be a JSON object")
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def merge_dashboard_color_metadata(
    metadata: dict[str, Any] | None,
    *,
    label_colors: dict[str, str],
    color_scheme: str = DEFAULT_COLOR_SCHEME,
) -> dict[str, Any]:
    """Return metadata with BPHN label colors and default categorical scheme."""
    merged: dict[str, Any] = dict(metadata or {})

    existing_label_colors = merged.get("label_colors")
    if not isinstance(existing_label_colors, dict):
        existing_label_colors = {}

    merged["label_colors"] = {**existing_label_colors, **label_colors}
    merged["color_scheme"] = color_scheme

    # Keep shared label map aligned so dashboard-wide color sync picks up pins.
    shared = merged.get("shared_label_colors")
    if not isinstance(shared, dict):
        shared = {}
    merged["shared_label_colors"] = {**shared, **label_colors}

    return merged


def sync_dashboard_label_colors(app) -> None:
    """Apply BPHN label_colors to configured dashboard(s)."""
    if os.getenv("BPHN_SYNC_DASHBOARD_COLORS", "true").lower() == "false":
        return

    sync_all = os.getenv("BPHN_SYNC_ALL_DASHBOARDS", "false").lower() == "true"
    slug = os.getenv("SUPERSET_DEFAULT_DASHBOARD_SLUG", "").strip()

    if not sync_all and not slug:
        return

    label_colors = {**BPHN_LABEL_COLORS, **_load_extra_label_colors()}

    with app.app_context():
        from superset.extensions import db
        from superset.models.dashboard import Dashboard

        try:
            query = db.session.query(Dashboard)
            if not sync_all:
                query = query.filter(Dashboard.slug == slug)

            dashboards = query.all()
            if not dashboards:
                logger.warning(
                    "BPHN color sync: no dashboard found (slug=%r, sync_all=%s)",
                    slug or None,
                    sync_all,
                )
                return

            updated = 0
            for dashboard in dashboards:
                try:
                    metadata = json.loads(dashboard.json_metadata or "{}")
                except json.JSONDecodeError:
                    metadata = {}

                new_metadata = merge_dashboard_color_metadata(
                    metadata, label_colors=label_colors
                )
                if new_metadata == metadata:
                    continue

                dashboard.json_metadata = json.dumps(new_metadata)
                updated += 1

            if updated:
                db.session.commit()
                logger.info(
                    "BPHN color sync: updated label_colors on %d dashboard(s)",
                    updated,
                )
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            logger.error("BPHN color sync failed: %s", exc)
