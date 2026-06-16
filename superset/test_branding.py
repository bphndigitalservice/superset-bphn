"""Unit tests for branding theme config and color token resolvers."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from branding import (
    build_theme_config,
    get_color_tokens,
    load_theme_json,
)


class TestBrandingThemeColors(unittest.TestCase):
    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_light_defaults(self, mock_load_theme) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
            "primary_color_dark": "#3b82f6",
            "secondary_color_dark": "#FFC107",
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            tokens = get_color_tokens(dark=False)
            self.assertEqual(tokens.get("colorPrimary"), "#1A2B56")
            self.assertEqual(tokens.get("colorSuccess"), "#FFC107")

    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_light_env_override(self, mock_load_theme) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
        }
        env = {
            "SUPERSET_PRIMARY_COLOR": "#00FF00",
            "SUPERSET_SECONDARY_COLOR": "#0000FF",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            tokens = get_color_tokens(dark=False)
            self.assertEqual(tokens.get("colorPrimary"), "#00FF00")
            self.assertEqual(tokens.get("colorSuccess"), "#0000FF")

    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_dark_defaults(self, mock_load_theme) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
            "primary_color_dark": "#3b82f6",
            "secondary_color_dark": "#FFC107",
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            tokens = get_color_tokens(dark=True)
            self.assertEqual(tokens.get("colorPrimary"), "#3b82f6")
            self.assertEqual(tokens.get("colorSuccess"), "#FFC107")

    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_dark_fallback_to_light(self, mock_load_theme) -> None:
        # No dark properties in theme.json
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            tokens = get_color_tokens(dark=True)
            # Should fallback to light theme properties
            self.assertEqual(tokens.get("colorPrimary"), "#1A2B56")
            self.assertEqual(tokens.get("colorSuccess"), "#FFC107")

    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_dark_env_override(self, mock_load_theme) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
            "primary_color_dark": "#3b82f6",
            "secondary_color_dark": "#FFC107",
        }
        env = {
            "SUPERSET_PRIMARY_COLOR_DARK": "#FFFF00",
            "SUPERSET_SECONDARY_COLOR_DARK": "#00FFFF",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            tokens = get_color_tokens(dark=True)
            self.assertEqual(tokens.get("colorPrimary"), "#FFFF00")
            self.assertEqual(tokens.get("colorSuccess"), "#00FFFF")

    @mock.patch("branding.load_theme_json")
    def test_get_color_tokens_dark_env_fallback_to_light(self, mock_load_theme) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
        }
        env = {
            "SUPERSET_PRIMARY_COLOR": "#00FF00",
            "SUPERSET_SECONDARY_COLOR": "#0000FF",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            tokens = get_color_tokens(dark=True)
            # Should fallback to light environment overrides
            self.assertEqual(tokens.get("colorPrimary"), "#00FF00")
            self.assertEqual(tokens.get("colorSuccess"), "#0000FF")

    @mock.patch("branding.get_logo_urls")
    @mock.patch("branding.load_theme_json")
    def test_build_theme_config(self, mock_load_theme, mock_get_logos) -> None:
        mock_load_theme.return_value = {
            "primary_color": "#1A2B56",
            "secondary_color": "#FFC107",
            "primary_color_dark": "#3b82f6",
            "secondary_color_dark": "#FFC107",
        }
        mock_get_logos.return_value = ("/static/logo.png", "/static/logo-dark.png")

        with mock.patch.dict(os.environ, {}, clear=True):
            # Light theme config
            config_light = build_theme_config(dark=False)
            self.assertEqual(config_light["token"]["colorPrimary"], "#1A2B56")
            self.assertEqual(config_light["token"]["brandLogoUrl"], "/static/logo.png")
            self.assertNotIn("algorithm", config_light)

            # Dark theme config
            config_dark = build_theme_config(dark=True)
            self.assertEqual(config_dark["token"]["colorPrimary"], "#3b82f6")
            self.assertEqual(config_dark["token"]["brandLogoUrl"], "/static/logo-dark.png")
            self.assertEqual(config_dark["algorithm"], "dark")


if __name__ == "__main__":
    unittest.main()
