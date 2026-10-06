#!/bin/sh
# Creates each service database that does not exist yet. The root docker-compose stack runs this
# on EVERY `up` (job `db-init`): Postgres's own /docker-entrypoint-initdb.d scripts run only on an
# empty volume, so a database added for a new service would otherwise never be created on an
# existing one. Connection comes from PGHOST / PGUSER / PGPASSWORD.
set -eu

for db in auth_db organization_db project_db ingestion_db testmgmt_db; do
  if psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
    echo "database $db exists"
  else
    psql -c "CREATE DATABASE \"$db\""
    echo "database $db created"
  fi
done
