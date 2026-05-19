# Example Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optionally load Apache Superset example dashboards/datasets via `superset load_examples`, gated by `LOAD_EXAMPLES` env and the Compose `examples` profile.

**Architecture:** Shell entrypoint runs `db upgrade`, conditionally `load_examples` (with metadata idempotency check), then `run-server.sh`. Compose `include` with `profiles: [examples]` sets `LOAD_EXAMPLES=true` for local dev; production defaults off via `.env`.

**Tech Stack:** Docker Compose 2.x (include + profiles), Apache Superset 6.1.0 CLI, shell.

**Spec:** `docs/superpowers/specs/2026-05-19-example-dashboards-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `docker/entrypoint-with-examples.sh` | `db upgrade` → optional `load_examples` → server |
| `docker/compose.examples.yaml` | Profile merge: `LOAD_EXAMPLES=true` on `superset` |
| `Dockerfile` | COPY + chmod entrypoint script |
| `docker-compose.yml` | `include` examples overlay; wire entrypoint command |
| `.env.example` | Document `LOAD_EXAMPLES=false` |
| `README.md` | Examples section + manual test checklist |

---

### Task 1: Entrypoint script

**Files:**
- Create: `docker/entrypoint-with-examples.sh`

- [ ] **Step 1: Create `docker/entrypoint-with-examples.sh`**

```sh
#!/bin/sh
set -e

load_examples_enabled() {
  case "$(printf '%s' "${LOAD_EXAMPLES:-false}" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes) return 0 ;;
    *) return 1 ;;
  esac
}

examples_already_loaded() {
  . /app/.venv/bin/activate
  python -c "
import os
os.environ.setdefault('SUPERSET_CONFIG_PATH', '/app/pythonpath/superset_config.py')
from superset.app import create_app
from superset.extensions import db
from superset.models.core import Database

app = create_app()
with app.app_context():
    found = (
        db.session.query(Database)
        .filter(Database.database_name == 'examples')
        .first()
        is not None
    )
raise SystemExit(0 if found else 1)
" >/dev/null 2>&1
}

superset db upgrade

if load_examples_enabled; then
  if examples_already_loaded; then
    echo "Examples already present, skipping."
  else
    echo "LOAD_EXAMPLES=true, loading Apache example data…"
    if superset load_examples; then
      echo "Example data loaded."
    else
      echo "Example load failed. Continuing without examples."
    fi
  fi
fi

exec /app/docker/entrypoints/run-server.sh
```

- [ ] **Step 2: Commit**

```bash
git add docker/entrypoint-with-examples.sh
git commit -m "feat: add entrypoint wrapper for optional load_examples"
```

---

### Task 2: Dockerfile + Compose

**Files:**
- Modify: `Dockerfile`
- Create: `docker/compose.examples.yaml`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update `Dockerfile` (before `USER superset`)**

```dockerfile
COPY docker/entrypoint-with-examples.sh /app/docker/entrypoints/entrypoint-with-examples.sh
RUN chmod +x /app/docker/entrypoints/entrypoint-with-examples.sh
```

- [ ] **Step 2: Create `docker/compose.examples.yaml`**

```yaml
services:
  superset:
    environment:
      LOAD_EXAMPLES: "true"
```

- [ ] **Step 3: Update `docker-compose.yml`**

Add at top:

```yaml
include:
  - path: docker/compose.examples.yaml
    profiles:
      - examples
```

On `superset` service, replace `command` with:

```yaml
    environment:
      LOAD_EXAMPLES: ${LOAD_EXAMPLES:-false}
    command: ["/app/docker/entrypoints/entrypoint-with-examples.sh"]
```

- [ ] **Step 4: Rebuild and smoke-test default (no examples)**

```bash
docker compose build superset
docker compose up -d
docker compose logs superset 2>&1 | tail -20
```

Expected: no "loading Apache example data" line; `/health` returns 200.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile docker/compose.examples.yaml docker-compose.yml
git commit -m "feat: wire LOAD_EXAMPLES entrypoint and examples compose profile"
```

---

### Task 3: Env template + README

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add to `.env.example`**

```bash
# Load Apache example dashboards/datasets on startup (requires outbound HTTPS to GitHub).
# Default: false. Local dev: use `docker compose --profile examples up` instead.
LOAD_EXAMPLES=false
```

- [ ] **Step 2: Add README section** (after Quick start)

Document local profile, prod opt-in, network requirement, manual `load_examples`, reset/volume warning, link to spec test checklist.

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: document optional example dashboards and LOAD_EXAMPLES"
```

---

### Task 4: Manual verification

- [ ] **Profile examples:** `docker compose --profile examples up -d --build` → logs show load or skip; Data → Databases has `examples`.
- [ ] **Idempotency:** `docker compose restart superset` → log "Examples already present, skipping."
- [ ] **Default off:** unset profile, `LOAD_EXAMPLES=false` → no examples DB on fresh volume (or skip if volume already has examples from prior test — note in log).

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Stock `load_examples` | Task 1 |
| `LOAD_EXAMPLES` env default off | Task 2, 3 |
| `examples` Compose profile | Task 2 |
| Idempotency (examples DB check) | Task 1 |
| Fail-open on load error | Task 1 |
| README + `.env.example` | Task 3 |
| Manual test checklist | Task 4 |
