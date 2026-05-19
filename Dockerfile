# change this to apache/superset:5.0.0 or whatever version you want to build from;
# otherwise the default is the latest commit on GitHub master branch
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
    # install psycopg2 for using PostgreSQL metadata store - could be a MySQL package if using that backend:
    psycopg2-binary \
    # MySQL & MariaDB: mysql://user:pass@host:3306/db (use mysql-connector-python if auth uses caching_sha2_password)
    mysqlclient \
    # Elasticsearch & OpenSearch (SQL): elasticsearch+https://... or opendistro+https://...
    "elasticsearch-dbapi[opendistro]" \
    # add the driver(s) for your data warehouse(s), in this example we're showing for Microsoft SQL Server:
    pymssql \
    # package needed for using single-sign on authentication:
    Authlib \
    # openpyxl to be able to upload Excel files
    openpyxl \
    # Pillow for Alerts & Reports to generate PDFs of dashboards
    Pillow \
    # install Playwright for taking screenshots for Alerts & Reports. This assumes the feature flag PLAYWRIGHT_REPORTS_AND_THUMBNAILS is enabled
    # That feature flag will default to True starting in 6.0.0
    # Playwright works only with Chrome.
    # If you are still using Selenium instead of Playwright, you would instead install here the selenium package and a headless browser & webdriver
    playwright \
    && playwright install-deps \
    && PLAYWRIGHT_BROWSERS_PATH=/usr/local/share/playwright-browsers playwright install chromium

# Production config and baked branding defaults
COPY --chown=superset:superset superset/branding.py superset/security_manager.py /app/pythonpath/
COPY --chown=superset:superset superset/superset_config.py /app/pythonpath/superset_config.py
COPY --chown=superset:superset superset/assets/branding/ /app/superset/static/assets/branding-default/

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
ENV PYTHONPATH=/app/pythonpath:${PYTHONPATH}
ENV SUPERSET_HOME=/app/superset_home

# Writable home for Celery beat schedule and other runtime state
RUN mkdir -p /app/superset_home && chown -R superset:superset /app/superset_home

# apache/superset lean image omits service-worker.js (https://github.com/apache/superset/issues/39431)
RUN if [ ! -f /app/superset/static/service-worker.js ]; then \
      printf '%s\n' "'use strict';self.addEventListener('install',function(){self.skipWaiting();});" \
        > /app/superset/static/service-worker.js; \
    fi && chown superset:superset /app/superset/static/service-worker.js

# Switch back to the superset user
USER superset

CMD ["/app/docker/entrypoints/run-server.sh"]