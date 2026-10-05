#!/usr/bin/env bash
# Dumps every QA Vision database into one compressed file and keeps the last 14 days.
# Run from cron (see deploy/README.md); safe to run while the platform serves traffic.
set -euo pipefail
cd "$(dirname "$0")/.."

dir="${QAV_BACKUP_DIR:-$PWD/backups}"
keep_days="${QAV_BACKUP_KEEP_DAYS:-14}"
mkdir -p "$dir"

file="$dir/qav-$(date -u +%Y%m%dT%H%MZ).sql.gz"
# pg_dumpall: all four service databases plus roles, consistent per database
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml \
  exec -T postgres pg_dumpall -U postgres | gzip > "$file.partial"
mv "$file.partial" "$file"  # a half-written dump never looks like a good one

find "$dir" -name 'qav-*.sql.gz' -mtime +"$keep_days" -delete
echo "backup written: $file ($(du -h "$file" | cut -f1))"
