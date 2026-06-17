# Rebuild frontend so Country Map "Indonesia" uses 38-province boundaries (ISO 3166-2).
FROM node:20-bookworm-slim AS superset-frontend

ARG SUPERSET_GIT_REF=6.1.0
ENV NODE_OPTIONS="--max-old-space-size=4096"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    python3 \
    build-essential \
    zstd && \
    rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${SUPERSET_GIT_REF}" \
    https://github.com/apache/superset.git /src

COPY superset/charts/geojson/country-map-indonesia.geojson \
  /src/superset-frontend/plugins/legacy-plugin-chart-country-map/src/countries/indonesia.geojson

WORKDIR /src/superset-frontend
RUN npm ci && npm run build

# Runtime image: extend official Superset with BPHN config, branding, and patched frontend assets.
FROM apache/superset:6.1.0

USER root

# Build deps for mysqlclient (MySQL & MariaDB data sources / metadata store)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libmariadb-dev \
    build-essential \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Set environment variable for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/playwright-browsers

# Install packages using uv into the virtual environment
RUN . /app/.venv/bin/activate && \
    uv pip install \
    psycopg2-binary \
    mysqlclient \
    "elasticsearch-dbapi[opendistro]" \
    pymssql \
    Authlib \
    openpyxl \
    Pillow \
    playwright \
    && playwright install-deps \
    && PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/playwright-browsers playwright install chromium

# Frontend assets from superset-frontend stage (includes updated Indonesia Country Map)
COPY --from=superset-frontend --chown=superset:superset \
  /src/superset/static/assets /app/superset/static/assets

# Production config and baked branding defaults
COPY --chown=superset:superset \
  superset/branding.py \
  superset/security_manager.py \
  superset/welcome_redirect.py \
  superset/home_menu.py \
  superset/sync_public_role.py \
  /app/pythonpath/
COPY --chown=superset:superset superset/superset_config.py /app/pythonpath/superset_config.py
COPY --chown=superset:superset superset/assets/branding/ /app/superset/static/assets/branding-default/
COPY --chown=superset:superset \
  superset/charts/geojson/indonesia-38-provinces.geojson \
  /app/superset/static/assets/geojson-default/
COPY --chown=superset:superset superset/templates/ /app/superset/templates/

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
ENV PYTHONPATH=/app/pythonpath:${PYTHONPATH}
ENV SUPERSET_HOME=/app/superset_home

RUN mkdir -p /app/superset_home && chown -R superset:superset /app/superset_home

COPY docker/entrypoint-with-examples.sh /app/docker/entrypoints/entrypoint-with-examples.sh
RUN chmod +x /app/docker/entrypoints/entrypoint-with-examples.sh

RUN if [ ! -f /app/superset/static/service-worker.js ]; then \
      printf '%s\n' "'use strict';self.addEventListener('install',function(){self.skipWaiting();});" \
        > /app/superset/static/service-worker.js; \
    fi && chown superset:superset /app/superset/static/service-worker.js

USER superset

CMD ["/app/docker/entrypoints/run-server.sh"]
