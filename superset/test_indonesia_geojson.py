"""Validate Indonesia 38-province GeoJSON for Country Map joins."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

GEOJSON_PATH = (
    Path(__file__).resolve().parent / "charts/geojson/indonesia-38-provinces.geojson"
)

OFFICIAL_KODE_PROV = {
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "21",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "51",
    "52",
    "53",
    "61",
    "62",
    "63",
    "64",
    "65",
    "71",
    "72",
    "73",
    "74",
    "75",
    "76",
    "81",
    "82",
    "91",
    "92",
    "93",
    "94",
    "95",
    "96",
}

PAPUA_KODE_BY_NAME = {
    "Papua": "91",
    "Papua Barat": "92",
    "Papua Selatan": "93",
    "Papua Tengah": "94",
    "Papua Pegunungan": "95",
    "Papua Barat Daya": "96",
}


def load_geojson() -> dict:
    with GEOJSON_PATH.open(encoding="utf-8") as f:
        return json.load(f)


class TestIndonesiaGeojson(unittest.TestCase):
    def test_feature_collection_with_38_provinces(self) -> None:
        data = load_geojson()
        self.assertEqual(data["type"], "FeatureCollection")
        features = data["features"]
        self.assertEqual(len(features), 38)

    def test_unique_kode_prov_matches_official_set(self) -> None:
        features = load_geojson()["features"]
        codes = {f["properties"]["KODE_PROV"] for f in features}
        self.assertEqual(len(codes), 38)
        self.assertEqual(codes, OFFICIAL_KODE_PROV)

    def test_required_properties_and_geometry(self) -> None:
        for feature in load_geojson()["features"]:
            props = feature["properties"]
            self.assertIn("KODE_PROV", props)
            self.assertIn("PROVINSI", props)
            self.assertIn("id", props)
            self.assertEqual(props["id"], props["KODE_PROV"])
            self.assertIn(feature["geometry"]["type"], ("Polygon", "MultiPolygon"))

    def test_papua_codes(self) -> None:
        by_name = {
            f["properties"]["PROVINSI"]: f["properties"]["KODE_PROV"]
            for f in load_geojson()["features"]
            if f["properties"]["PROVINSI"] in PAPUA_KODE_BY_NAME
        }
        self.assertEqual(by_name, PAPUA_KODE_BY_NAME)


if __name__ == "__main__":
    unittest.main()
