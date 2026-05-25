"""Unit tests for home_menu bootstrap override."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from home_menu import build_home_menu_item, home_menu_bootstrap_override
from welcome_redirect import ENV_SLUG


class TestHomeMenu(unittest.TestCase):
    def test_build_home_menu_item(self) -> None:
        item = build_home_menu_item(application_root="/analytics", slug="bphn-overview")
        self.assertEqual(item["label"], "Home")
        self.assertEqual(item["url"], "/analytics/superset/dashboard/bphn-overview/")
        self.assertEqual(item["icon"], "fa-home")

    def test_override_no_slug(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = home_menu_bootstrap_override(
                {
                    "application_root": "",
                    "menu_data": {"menu": [{"name": "Dashboards", "label": "Dashboards"}]},
                }
            )
        self.assertEqual(result, {})

    def test_override_prepends_home(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "my-dash"}):
            result = home_menu_bootstrap_override(
                {
                    "application_root": "",
                    "menu_data": {
                        "menu": [
                            {
                                "name": "Dashboards",
                                "label": "Dashboards",
                                "url": "/dashboard/list/",
                            }
                        ],
                        "brand": {},
                        "navbar_right": {},
                        "settings": [],
                    },
                }
            )
        menu = result["menu_data"]["menu"]
        self.assertEqual(menu[0]["label"], "Home")
        self.assertEqual(menu[0]["url"], "/superset/dashboard/my-dash/")
        self.assertEqual(menu[1]["name"], "Dashboards")

    def test_override_missing_menu_data(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "x"}):
            self.assertEqual(home_menu_bootstrap_override({}), {})

    def test_override_skips_if_home_already_present(self) -> None:
        with mock.patch.dict(os.environ, {ENV_SLUG: "my-dash"}):
            result = home_menu_bootstrap_override(
                {
                    "application_root": "",
                    "menu_data": {
                        "menu": [{"name": "Home", "label": "Home", "url": "/x"}],
                    },
                }
            )
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
