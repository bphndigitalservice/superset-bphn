"""Unit tests for BPHN dashboard color metadata helpers."""
from __future__ import annotations

import unittest

from chart_colors import BPHN_LABEL_COLORS
from sync_dashboard_colors import merge_dashboard_color_metadata


class TestMergeDashboardColorMetadata(unittest.TestCase):
    def test_merges_known_labels_and_sets_scheme(self) -> None:
        result = merge_dashboard_color_metadata(
            {"label_colors": {"Custom": "#111111"}},
            label_colors=BPHN_LABEL_COLORS,
        )

        self.assertEqual(result["color_scheme"], "bphn_brand")
        self.assertEqual(result["label_colors"]["Perdata"], "#192C70")
        self.assertEqual(result["label_colors"]["Pidana"], "#FFCB05")
        self.assertEqual(result["label_colors"]["TUN"], "#4A6BC7")
        self.assertEqual(result["label_colors"]["Custom"], "#111111")
        self.assertEqual(result["shared_label_colors"]["Perdata"], "#192C70")

    def test_bphn_labels_override_existing_pins(self) -> None:
        result = merge_dashboard_color_metadata(
            {"label_colors": {"Perdata": "#000000"}},
            label_colors=BPHN_LABEL_COLORS,
        )

        self.assertEqual(result["label_colors"]["Perdata"], "#192C70")

    def test_handles_empty_metadata(self) -> None:
        result = merge_dashboard_color_metadata(None, label_colors={"A": "#192C70"})
        self.assertEqual(result["label_colors"], {"A": "#192C70"})
        self.assertEqual(result["color_scheme"], "bphn_brand")


if __name__ == "__main__":
    unittest.main()
