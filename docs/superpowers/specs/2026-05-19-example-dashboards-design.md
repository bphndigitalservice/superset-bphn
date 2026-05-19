# Example Dashboards & Datasets — Design Spec

**Date:** 2026-05-19  
**Status:** Approved (brainstorming)  
**Base image:** `apache/superset:6.1.0`

## Goal

Add optional Apache Superset example dashboards and datasets to `superset-bphn` for:

- **Onboarding** — analysts can explore SQL Lab, datasets, charts, and dashboards without connecting a warehouse first.
- **Demo** — stakeholders see a populated instance with BPHN branding on the app shell.

Uses stock `superset load_examples` (no custom BPHN export in v1).

## Decisions Summary

| Area | Decision |
|------|----------|
| Content | Stock `superset load_examples` (Apache bundle) |
| Data source | Runtime download from [apache-superset/examples-data](https://github.com/apache-superset/examples-data); loaded into local `examples` database in the container |
| Production | Opt-in via `LOAD_EXAMPLES=true` in `.env`; default **off** |
| Local dev | `docker compose --profile examples up` sets `LOAD_EXAMPLES=true` automatically |
| Implementation | Env-gated entrypoint wrapper after `db upgrade` (no new Compose services) |
| Failed load | Log error, continue startup — examples are optional |

## How `load_examples` Works

`superset load_examples` is **not** a persistent connection to a remote warehouse. On first run it:

1. Downloads dataset files from GitHub (`examples-data`) over HTTPS.
2. Creates a local **`examples`** database connection and loads data.
3. Registers datasets, charts, and dashboards in the metadata database.

After load, charts query the local `examples` DB. Ongoing GitHub access is not required until metadata/volumes are reset.

**Implications:**

- First load needs outbound HTTPS to GitHub (1–3+ minutes, CPU-heavy).
- Air-gapped production cannot load examples in v1 without an internal mirror (out of scope).

## Architecture

### Components

| Piece | Role |
|-------|------|
| `LOAD_EXAMPLES` env | Master switch (`true` / `false` / unset). Default off. |
| `examples` Compose profile | Injects `LOAD_EXAMPLES=true` on `superset` for local dev. |
| Entrypoint wrapper | After `superset db upgrade`, optionally runs `superset load_examples`, then `run-server.sh`. |
| Idempotency guard | Skip if `examples` database connection already exists in metadata. |
| `superset load_examples` | Stock CLI from Apache Superset 6.1.0 image. |

### Repository Layout (additions)

```
superset-bphn/
├── docker/
│   └── entrypoint-with-examples.sh
├── docker-compose.yml          # profile + env passthrough
├── .env.example                # LOAD_EXAMPLES documented
└── README.md                   # Examples section
```

No changes to `superset_config.py` required for v1.

### Entrypoint Flow

```
superset db upgrade
  → if LOAD_EXAMPLES=true AND examples not already loaded:
       superset load_examples
  → /app/docker/entrypoints/run-server.sh
```

### Compose

**Default:** `LOAD_EXAMPLES` unset or `false` — no examples, current behavior.

**Local with examples:**

```bash
docker compose --profile examples up -d
```

**Production opt-in:**

```bash
# .env
LOAD_EXAMPLES=true
docker compose up -d --force-recreate superset
```

The `examples` profile only affects services that declare `profiles: [examples]`; production stacks that never enable the profile rely on `.env` alone.

### Idempotency

Before calling `load_examples`, check metadata for an existing database connection named `examples`. If present, log and skip.

Avoid running on every restart when examples already exist (prevents duplicate errors and slow startup).

### Admin Bootstrap

Examples do **not** replace existing bootstrap:

1. `docker compose up` (optionally `--profile examples`)
2. `docker compose exec superset superset fab create-admin` (first admin)
3. `docker compose exec superset superset init`
4. Log in; open example dashboards

SSO users need appropriate roles (e.g. Gamma) to view dashboards, same as any content.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `LOAD_EXAMPLES` false / unset | Skip loader; normal startup. |
| Examples already in metadata | Log info, skip, continue. |
| `load_examples` fails (network, GitHub, disk) | Log error; **continue startup** — do not block the web app. |
| `db upgrade` fails | Fail startup (unchanged). |
| Partial failure | Document manual recovery: `docker compose exec superset superset load_examples`, or reset metadata volume (with backup warning). |

**Log messages:**

- Start: `LOAD_EXAMPLES=true, loading Apache example data…`
- Success: `Example data loaded.`
- Skip: `Examples already present, skipping.`
- Failure: `Example load failed: <reason>. Continuing without examples.`

## Security

- Default off in production — no surprise external fetch or demo data in metadata.
- Example data is non-production; do not use for real KPIs or scheduled reports.
- No new exposed ports or services.

## Testing (manual checklist)

1. **Default up** — `docker compose up -d` → no `examples` database in Data → Databases; normal startup time.
2. **Profile examples** — `docker compose --profile examples up -d` → `examples` DB exists; dashboards visible; charts render.
3. **Idempotency** — restart `superset` with profile on → logs show skip; no duplicate connections.
4. **Prod opt-in** — `LOAD_EXAMPLES=true` in `.env`, recreate → examples load once.
5. **Failure path** — `LOAD_EXAMPLES=true` without GitHub access → `/health` OK; logs show failure + continue.

## Documentation

README section **“Example dashboards & datasets”** covering:

- What loads (stock Apache examples, local `examples` DB).
- Local: `docker compose --profile examples up -d`
- Prod: `LOAD_EXAMPLES=true`, recreate `superset`; default off.
- Network and timing requirements.
- Air-gapped limitation (v1).
- Reset options (UI or volume wipe with backup warning).

`.env.example` addition:

```bash
# Load Apache example dashboards/datasets on startup (requires outbound HTTPS to GitHub).
# Default: false. Local dev: use `docker compose --profile examples up` instead.
LOAD_EXAMPLES=false
```

## Out of Scope (v1)

- Custom BPHN welcome dashboard or curated export
- Bundled sample Postgres service in Compose
- CI automation for example loading
- Internal mirror for air-gapped `examples-data`
- Auto-run `superset init` or `fab create-admin`

## Future Enhancements (not planned)

- Curated BPHN onboarding dashboard atop stock examples
- `examples-data` mirror for air-gapped environments
- One-shot init container instead of entrypoint hook
