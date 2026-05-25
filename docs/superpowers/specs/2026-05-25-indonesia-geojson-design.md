# Indonesia Province GeoJSON — Design Spec

**Date:** 2026-05-25  
**Status:** Approved (brainstorming)  
**Base image:** `apache/superset:6.1.0`

## Goal

Ship a **38-province** Indonesia boundary GeoJSON baked into the BPHN Superset image so analysts can build **Country Map** charts with correct joins on official province codes or names, including the 2022 Papua administrative splits (Papua Selatan, Tengah, Pegunungan, Barat Daya).

## Decisions Summary

| Area | Decision |
|------|----------|
| Admin level | Province only (`provinsi`); kab/kota deferred to a future sibling file |
| Province set | **38** current official provinces (not legacy 34) |
| Chart type | Superset **Country Map** (GeoJSON URL + single join property) |
| Delivery | **Baked static asset** in Docker image (no runtime volume override in v1) |
| Join properties | `KODE_PROV` (BPS/Kemendagri code) and `PROVINSI` (name); `id` aligned with code |
| Source file (repo) | `superset/charts/geojson/indonesia-38-provinces.geojson` |
| Image path | `/app/superset/static/assets/geojson-default/indonesia-38-provinces.geojson` |
| Public URL | `{origin}/static/assets/geojson-default/indonesia-38-provinces.geojson` |
| Approach | Static `COPY` in Dockerfile (mirrors `branding-default/` pattern) |

## Context

- **superset-bphn** has no GeoJSON assets in the image today; map tile CSP entries already exist in `superset_config.py`.
- A draft GeoJSON file exists in the repo with **38** features and correct province **names**, including new Papua provinces.
- **Data fix required:** six Papua-related features currently share only codes `91` and `92`; Kemendagri assigns **91–96**. Country Map joins on one property — duplicate `KODE_PROV` breaks code-based joins.
- Analysts are greenfield on maps (no existing Superset upload or external URL).

## Property Schema

Every feature must include:

| Property | Purpose | Example |
|----------|---------|---------|
| `KODE_PROV` | Primary join key for BPS-style datasets | `"32"` |
| `PROVINSI` | Join on province name | `"Jawa Barat"` |
| `id` | Stable unique feature id | `"32"` (same as `KODE_PROV` after normalization) |

### Papua code normalization

| Province | Current `KODE_PROV` | Target `KODE_PROV` |
|----------|---------------------|---------------------|
| Papua | `91` | `91` |
| Papua Barat | `92` | `92` |
| Papua Selatan | `91` | `93` |
| Papua Tengah | `91` | `94` |
| Papua Pegunungan | `91` | `95` |
| Papua Barat Daya | `92` | `96` |

After fix: **38** unique `KODE_PROV` values. Official set:

`11`–`19`, `21`, `31`–`36`, `51`–`53`, `61`–`65`, `71`–`76`, `81`–`82`, `91`–`96`.

### Country Map join guidance

| Dataset column style | Country Field Type | GeoJSON property |
|---------------------|-------------------|------------------|
| 2-digit province code | `code` | `KODE_PROV` |
| Province name (exact spelling) | `name` | `PROVINSI` |

SQL tip for code joins: zero-pad to 2 digits when source stores integers (`LPAD(CAST(kode AS TEXT), 2, '0')`).

Do **not** use legacy 34-province codes for the four new Papua provinces.

## Architecture

### Approach (chosen)

**Baked static asset** — `COPY` GeoJSON into `geojson-default/` under Superset static. No Python resolver module in v1 (YAGNI vs branding volume pattern).

### Rejected alternatives

| Approach | Why not v1 |
|----------|------------|
| Runtime volume override (`./geo/`) | User chose bake-only; adds ops surface |
| `superset_config.py` URL constant only | Documentation suffices; file path is stable |
| Superset UI upload | Not versioned with BPHN releases |

### File layout

```
superset/charts/geojson/indonesia-38-provinces.geojson   # canonical source in repo
    ↓ Dockerfile COPY
/app/superset/static/assets/geojson-default/indonesia-38-provinces.geojson
```

### Dockerfile change

Add alongside branding `COPY`:

```dockerfile
COPY --chown=superset:superset \
  superset/charts/geojson/indonesia-38-provinces.geojson \
  /app/superset/static/assets/geojson-default/
```

### Future kab/kota

Add `indonesia-kabkota.geojson` (or similar) as a **separate** file in the same directory. Use consistent property names (`KODE_PROV`, `PROVINSI`, plus `KODE_KAB`, `KABUPATEN` when implemented). No change to v1 serving mechanism.

## Chart Setup (analyst)

1. Chart type: **Country Map**
2. **Country**: dimension with province code or name
3. **Country Field Type**: `code` or `name` per table above
4. **GeoJSON URL**: full Superset origin + `/static/assets/geojson-default/indonesia-38-provinces.geojson`
5. **Properties key**: `KODE_PROV` or `PROVINSI` (must match dataset values exactly)

**CSP:** GeoJSON is same-origin; no Talisman change expected.

## Operations

| Action | Steps |
|--------|--------|
| Ship updated boundaries | Edit GeoJSON in repo → rebuild image → redeploy |
| Verify after deploy | `curl -sI https://<host>/static/assets/geojson-default/indonesia-38-provinces.geojson` → HTTP 200 |
| Analyst smoke test | Open URL in browser (valid JSON) → Country Map renders 38 regions |

## Testing

### Automated (`pytest`)

New test module (e.g. `superset/test_indonesia_geojson.py`) loads the repo GeoJSON and asserts:

- Valid `FeatureCollection`
- Exactly **38** features
- **38** unique `KODE_PROV` values
- `KODE_PROV` set equals official 38-province code list
- Every feature has `KODE_PROV`, `PROVINSI`, `id`
- Geometry type is `Polygon` or `MultiPolygon`

### Manual smoke (post-build)

1. Static URL returns `200` and JSON content type
2. Country Map with `KODE_PROV` join colors all 38 provinces (no ambiguous Papua tiles)
3. Optional: `PROVINSI` name join with small test dataset

## Acceptance Criteria

- [ ] Papua provinces use distinct codes **91–96**
- [ ] GeoJSON copied into image at `geojson-default/`
- [ ] README section: URL, join fields, Papua code table, Country Map steps
- [ ] Automated validation test passes locally / in CI

## Out of Scope (v1)

- Runtime volume override for GeoJSON
- deck.gl choropleth
- Legacy 34-province alias layer or mapping file
- Pre-built example dashboard with Indonesia map chart
- Kabupaten/kota boundaries

## Implementation Files (planned)

| File | Change |
|------|--------|
| `superset/charts/geojson/indonesia-38-provinces.geojson` | Fix Papua `KODE_PROV` / `id` |
| `Dockerfile` | `COPY` to `geojson-default/` |
| `superset/test_indonesia_geojson.py` | Validation tests |
| `README.md` | “Indonesia province map” section |

## Related

- Branding static pattern: `superset/assets/branding/` → `branding-default/` (same bake model, different path)
