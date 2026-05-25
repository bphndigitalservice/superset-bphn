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
