#!/bin/sh
# Renders /tmp/thresholds.yml from POSTGRES_DB_SIZE_ALERT_GB (rule files cannot read the environment,
# Ruling 9), then runs Prometheus with the given arguments.
set -eu
gb="${POSTGRES_DB_SIZE_ALERT_GB:-20}"
case "$gb" in
  ''|*[!0-9.]*|*.*.*) echo "prometheus: POSTGRES_DB_SIZE_ALERT_GB must be a number of GB, got '$gb'" >&2; exit 1 ;;
esac
cat > /tmp/thresholds.yml <<EOT
groups:
  - name: qeos-thresholds
    rules:
      - record: postgresql_database_size_alert_bytes
        expr: vector($gb * 1e9)
EOT
exec /bin/prometheus "$@"
