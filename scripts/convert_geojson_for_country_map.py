#!/usr/bin/env python3
"""Convert BPHN 38-province GeoJSON to legacy Country Map plugin format (ISO + NAME_1)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "superset/charts/geojson/indonesia-38-provinces.geojson"
MAPPING = ROOT / "superset/charts/geojson/kode-prov-to-iso.json"
OUTPUT = ROOT / "superset/charts/geojson/country-map-indonesia.geojson"


def main() -> None:
    kode_to_iso = json.loads(MAPPING.read_text(encoding="utf-8"))
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    out_features = []
    for feature in data["features"]:
        props = feature["properties"]
        kode = props["KODE_PROV"]
        iso = kode_to_iso.get(kode)
        if not iso:
            raise SystemExit(f"no ISO mapping for KODE_PROV={kode}")
        out_features.append(
            {
                "type": "Feature",
                "properties": {
                    "ISO": iso,
                    "NAME_1": props["PROVINSI"],
                    "KODE_PROV": kode,
                },
                "geometry": feature["geometry"],
            }
        )

    if len(out_features) != 38:
        raise SystemExit(f"expected 38 features, got {len(out_features)}")

    isos = {f["properties"]["ISO"] for f in out_features}
    if len(isos) != 38:
        raise SystemExit(f"duplicate ISO codes: {len(isos)} unique")

    out = {
        "type": "FeatureCollection",
        "features": out_features,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} ({len(out_features)} provinces)")


if __name__ == "__main__":
    main()
