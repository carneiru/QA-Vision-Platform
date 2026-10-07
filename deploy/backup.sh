#!/usr/bin/env bash
# Dumps every QEOS database into one compressed file and keeps the last 14 days.
# Run from cron (see deploy/README.md); safe to run while the platform serves traffic.
set -euo pipefail
cd "$(dirname "$0")/.."

# QAV_BACKUP_* are the names before the QEOS rename, still read when the new ones are unset
dir="${QEOS_BACKUP_DIR:-${QAV_BACKUP_DIR:-$PWD/backups}}"
keep_days="${QEOS_BACKUP_KEEP_DAYS:-${QAV_BACKUP_KEEP_DAYS:-14}}"
mkdir -p "$dir"

file="$dir/qeos-$(date -u +%Y%m%dT%H%MZ).sql.gz"
# pg_dumpall: all four service databases plus roles, consistent per database
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml \
  exec -T postgres pg_dumpall -U postgres | gzip > "$file.partial"
mv "$file.partial" "$file"  # a half-written dump never looks like a good one

# qav-*.sql.gz: dumps written before the QEOS rename age out the same way
find "$dir" \( -name 'qeos-*.sql.gz' -o -name 'qav-*.sql.gz' \) -mtime +"$keep_days" -delete
echo "backup written: $file ($(du -h "$file" | cut -f1))"
