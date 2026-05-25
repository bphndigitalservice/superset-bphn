# Indonesia Province GeoJSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bake a validated 38-province Indonesia GeoJSON into the BPHN image with unique Kemendagri `KODE_PROV` values (91–96 for Papua splits) for Country Map charts.

**Architecture:** Canonical file in `superset/charts/geojson/`; `Dockerfile` copies it to `/app/superset/static/assets/geojson-default/`; stdlib `unittest` guards schema and codes in CI/local runs. No Python serving layer in v1.

**Tech Stack:** GeoJSON, Docker `COPY`, Python 3 `unittest`, Apache Superset 6.1.0 Country Map chart.

**Spec:** `docs/superpowers/specs/2026-05-25-indonesia-geojson-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `superset/charts/geojson/indonesia-38-provinces.geojson` | Canonical boundaries; Papua codes normalized |
| `superset/test_indonesia_geojson.py` | Assert 38 features, unique codes, required properties |
| `Dockerfile` | `COPY` GeoJSON into `geojson-default/` |
| `README.md` | Analyst + ops documentation |

---

### Task 1: GeoJSON validation tests (TDD)

**Files:**
- Create: `superset/test_indonesia_geojson.py`

- [ ] **Step 1: Create `superset/test_indonesia_geojson.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL (duplicate Papua codes)**

Run:

```bash
cd /Users/finnarc/Repo/superset-bphn/superset && python3 -m unittest test_indonesia_geojson.py -v
```

Expected: `test_unique_kode_prov_matches_official_set` and `test_papua_codes` **FAIL** (only 34 unique codes today).

- [ ] **Step 3: Commit test file**

```bash
git add superset/test_indonesia_geojson.py
git commit -m "test: add Indonesia province GeoJSON validation"
```

---

### Task 2: Normalize Papua `KODE_PROV` and `id`

**Files:**
- Modify: `superset/charts/geojson/indonesia-38-provinces.geojson`

- [ ] **Step 1: Apply code fix with a one-off script**

Run from repo root:

```bash
python3 <<'PY'
import json
from pathlib import Path

path = Path("superset/charts/geojson/indonesia-38-provinces.geojson")
PAPUA = {
    "Papua": "91",
    "Papua Barat": "92",
    "Papua Selatan": "93",
    "Papua Tengah": "94",
    "Papua Pegunungan": "95",
    "Papua Barat Daya": "96",
}
data = json.loads(path.read_text(encoding="utf-8"))
for feature in data["features"]:
    name = feature["properties"]["PROVINSI"]
    if name in PAPUA:
        code = PAPUA[name]
        feature["properties"]["KODE_PROV"] = code
        feature["properties"]["id"] = code
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("updated", path)
PY
```

Note: re-serializing reformats the ~12k-line file (acceptable; keeps JSON valid and pretty-printed).

- [ ] **Step 2: Run tests — expect PASS**

```bash
cd superset && python3 -m unittest test_indonesia_geojson.py -v
```

Expected: **OK** (4 tests).

- [ ] **Step 3: Commit GeoJSON fix**

```bash
git add superset/charts/geojson/indonesia-38-provinces.geojson
git commit -m "fix: assign Kemendagri codes 91-96 to Papua province features"
```

---

### Task 3: Bake GeoJSON into Docker image

**Files:**
- Modify: `Dockerfile` (after branding `COPY`, ~line 51)

- [ ] **Step 1: Add `COPY` for geojson-default**

Insert after the branding `COPY` line:

```dockerfile
COPY --chown=superset:superset \
  superset/charts/geojson/indonesia-38-provinces.geojson \
  /app/superset/static/assets/geojson-default/
```

- [ ] **Step 2: Build image and verify file in container**

```bash
cd /Users/finnarc/Repo/superset-bphn
docker compose build superset
docker compose run --rm superset test -f /app/superset/static/assets/geojson-default/indonesia-38-provinces.geojson
```

Expected: exit code `0`.

- [ ] **Step 3: Verify HTTP serving (stack running)**

```bash
docker compose up -d superset
curl -sI http://127.0.0.1:8088/static/assets/geojson-default/indonesia-38-provinces.geojson | head -5
```

Expected: `HTTP/1.1 200` (or `304` on repeat).

Optional in-container unittest (if `test_indonesia_geojson.py` is not copied into image, run from mounted dev context only):

```bash
docker compose exec superset python3 -c "
import json
p='/app/superset/static/assets/geojson-default/indonesia-38-provinces.geojson'
d=json.load(open(p))
assert len(d['features'])==38
codes={f['properties']['KODE_PROV'] for f in d['features']}
assert len(codes)==38
print('ok', len(codes), 'provinces')
"
```

- [ ] **Step 4: Commit Dockerfile**

```bash
git add Dockerfile
git commit -m "feat: bake Indonesia province GeoJSON into image static assets"
```

---

### Task 4: README — Indonesia province map

**Files:**
- Modify: `README.md` (new section after **Branding**, before **Break-glass login**)

- [ ] **Step 1: Add section**

```markdown
## Indonesia province map (Country Map)

Baked GeoJSON for all **38** provinces (including Papua Selatan, Tengah, Pegunungan, Barat Daya).

| Item | Value |
|------|--------|
| URL | `{your-origin}/static/assets/geojson-default/indonesia-38-provinces.geojson` |
| Join on code | GeoJSON property `KODE_PROV` — Country Field Type **code** |
| Join on name | GeoJSON property `PROVINSI` — Country Field Type **name** |

**Papua province codes (Kemendagri):** 91 Papua, 92 Papua Barat, 93 Papua Selatan, 94 Papua Tengah, 95 Papua Pegunungan, 96 Papua Barat Daya.

**Create a chart:** Chart type **Country Map** → set **GeoJSON URL** to the table URL → set **Properties key** to `KODE_PROV` or `PROVINSI` to match your dataset → pick **Country** dimension and matching **Country Field Type**.

**Update boundaries:** edit `superset/charts/geojson/indonesia-38-provinces.geojson`, rebuild the image, redeploy. Verify:

```bash
curl -sI https://<host>/static/assets/geojson-default/indonesia-38-provinces.geojson
```

Source file in repo: `superset/charts/geojson/indonesia-38-provinces.geojson`. Validation: `cd superset && python3 -m unittest test_indonesia_geojson.py -v`.
```

- [ ] **Step 2: Commit README**

```bash
git add README.md
git commit -m "docs: document Indonesia province GeoJSON for Country Map charts"
```

---

### Task 5: Manual smoke checklist

- [ ] **Step 1: Run full unit test suite for pythonpath modules**

```bash
cd superset && python3 -m unittest test_indonesia_geojson.py test_home_menu.py test_welcome_redirect.py -v
```

Expected: all **PASS**.

- [ ] **Step 2: Superset UI (manual)**

1. Log in as admin.
2. **Charts → + Chart → Country Map**.
3. GeoJSON URL: `http://127.0.0.1:8088/static/assets/geojson-default/indonesia-38-provinces.geojson` (adjust host if behind proxy).
4. Properties key: `KODE_PROV`.
5. Use a dataset with a 2-digit province code column (or create a small SQL Lab query with a few codes, e.g. `32`, `33`, `91`, `93`).
6. Confirm map renders multiple provinces; Papua sub-provinces are distinct (not merged incorrectly).

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| 38 provinces, Papua 91–96 | Task 1–2 |
| Baked static at `geojson-default/` | Task 3 |
| Country Map / join docs | Task 4 |
| Automated validation | Task 1, 5 |
| Manual smoke | Task 3, 5 |
| No volume override / no CSP change | N/A (documented out of scope in spec) |
| Kab/kota deferred | N/A |

## Acceptance checklist

- [ ] `test_indonesia_geojson.py` passes locally
- [ ] GeoJSON returns HTTP 200 from `/static/assets/geojson-default/...`
- [ ] README section added
- [ ] Country Map smoke test completed (optional but recommended before release)
