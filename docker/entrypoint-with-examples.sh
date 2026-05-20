#!/bin/sh
set -e

# Compose `depends_on: healthy` does not guarantee embedded DNS is ready on all hosts.
# Also avoids racing `superset db upgrade` before Postgres accepts TCP.
wait_for_postgres_tcp() {
  echo "Waiting for postgres:5432 (Compose DNS + TCP)…"
  i=0
  while [ "$i" -lt 90 ]; do
    if /app/.venv/bin/python -c 'import socket; s=socket.create_connection(("postgres", 5432), 3); s.close()' 2>/dev/null; then
      echo "postgres is reachable."
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  echo "error: postgres:5432 not reachable after 90s (DNS or routing)."
  echo "hint: docker compose exec superset getent hosts postgres  # should print an IP"
  exit 1
}

wait_for_postgres_tcp

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
