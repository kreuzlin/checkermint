#!/bin/sh
# Restore test (ADR 0017): restores the latest backup into throwaway
# containers and compares it with the running site. Changes nothing on the
# live database or the media volume. Run right after scripts/backup.sh –
# anything changed on the site in between shows up as a difference.
# APP_DIR overrides the checkout directory (default: the script's parent).
set -eu
cd "${APP_DIR:-$(dirname "$0")/..}"

compose() { docker compose -f compose.prod.yaml "$@"; }
dump=$(ls backups/db-*.dump 2>/dev/null | sort | tail -n 1)
[ -n "$dump" ] || { echo "No database dump in backups/" >&2; exit 1; }
[ -f backups/media.tar ] || { echo "No backups/media.tar" >&2; exit 1; }

name="restore-test-$$"
tmp=$(mktemp -d)
cleanup() {
    docker rm -f "$name" >/dev/null 2>&1 || true
    rm -rf "$tmp"
}
trap cleanup EXIT

# Rows per table, in the database the given command connects to.
COUNT_SQL="SELECT table_name || ' ' || (xpath('/row/c/text()',
  query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name),
  false, true, '')))[1]::text FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1"

echo "Database: restoring $dump into a temporary PostgreSQL container"
docker run -d --rm --name "$name" -e POSTGRES_PASSWORD=restore-test \
    postgres:18 >/dev/null
until docker exec "$name" pg_isready -U postgres -q 2>/dev/null; do sleep 1; done
sleep 2  # the image restarts the server once after initialising
until docker exec "$name" pg_isready -U postgres -q 2>/dev/null; do sleep 1; done
docker exec "$name" createdb -U postgres restored
docker exec -i "$name" pg_restore -U postgres -d restored --no-owner \
    --no-privileges --exit-on-error < "$dump"
docker exec "$name" psql -U postgres -d restored -At -c "$COUNT_SQL" \
    > "$tmp/db-restored.txt"
compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$0"' \
    "$COUNT_SQL" > "$tmp/db-live.txt"
db_ok=yes
diff "$tmp/db-live.txt" "$tmp/db-restored.txt" || db_ok=no
echo "  $(wc -l < "$tmp/db-restored.txt") tables, $(awk '{s += $2} END {print s}' "$tmp/db-restored.txt") rows"

echo "Media: extracting backups/media.tar"
mkdir "$tmp/media"
tar -C "$tmp/media" -xf backups/media.tar
(cd "$tmp/media" && find . -type f -exec sha256sum {} + | sort -k 2) \
    > "$tmp/media-restored.txt"
compose exec -T web sh -c 'cd /app/media && find . -type f -exec sha256sum {} + | sort -k 2' \
    > "$tmp/media-live.txt"
media_ok=yes
diff "$tmp/media-live.txt" "$tmp/media-restored.txt" || media_ok=no
echo "  $(wc -l < "$tmp/media-restored.txt") files"

echo "Database matches the live site: $db_ok"
echo "Media matches the live site: $media_ok"
[ "$db_ok" = yes ] && [ "$media_ok" = yes ]
