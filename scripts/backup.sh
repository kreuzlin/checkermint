#!/bin/sh
# Nightly backup before the UpCloud disk backup (ADR 0008, ADR 0017). Run by
# cron on the production server from the repo checkout:
#   - database dump backups/db-YYYY-MM-DD.dump, the last KEEP_DAYS days
#   - copy of the uploaded files (media volume) backups/media.tar, only the
#     latest; older states are in the UpCloud backups
# APP_DIR overrides the checkout directory (default: the script's parent).
set -eu
cd "${APP_DIR:-$(dirname "$0")/..}"

KEEP_DAYS="${KEEP_DAYS:-14}"
compose() { docker compose -f compose.prod.yaml "$@"; }
umask 077
mkdir -p backups

# Database. Custom format: compressed, restorable with pg_restore.
file="backups/db-$(date +%Y-%m-%d).dump"
compose exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
    > "$file.tmp"
mv "$file.tmp" "$file"
find backups -name 'db-*.dump' -mtime +"$KEEP_DAYS" -delete

# Uploaded files. Read from the web container, which is the only one that
# mounts the private media volume (ADR 0009). Photos are already
# compressed, so the archive is not.
compose exec -T web tar -C /app/media -cf - . > backups/media.tar.tmp
mv backups/media.tar.tmp backups/media.tar
