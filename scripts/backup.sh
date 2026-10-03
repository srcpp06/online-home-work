#!/usr/bin/env bash
# Production backups into backups/ (SPEC §8; docs/deploy.md sets up cron).
#
#   scripts/backup.sh db      the database (pg_dump, gzipped); the last 14 are kept
#   scripts/backup.sh media   uploaded packages and solutions (tar.gz); the last 4 are kept
set -euo pipefail
cd "$(dirname "$0")/.."

compose=(docker compose -f compose.prod.yml)
stamp=$(date +%Y%m%d-%H%M)
mkdir -p backups

case "${1:-}" in
    db)
        file="backups/db-$stamp.sql.gz"
        keep=14
        "${compose[@]}" exec -T db pg_dump -U ohw ohw | gzip > "$file.part"
        ;;
    media)
        file="backups/media-$stamp.tar.gz"
        keep=4
        "${compose[@]}" exec -T web tar -C /data -czf - media > "$file.part"
        ;;
    *)
        echo "usage: $0 db|media" >&2
        exit 1
        ;;
esac

# Renamed only when complete, so a failed run never looks like a backup.
mv "$file.part" "$file"
kind="${file#backups/}"
kind="${kind%%-*}"
ls -1t backups/"$kind"-* | tail -n +"$((keep + 1))" | xargs -r rm --
echo "saved $file ($(du -h "$file" | cut -f1))"
