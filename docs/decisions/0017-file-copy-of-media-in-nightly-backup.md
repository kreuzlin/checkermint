# 0017: File copy of the media volume in the nightly backup

- Status: accepted
- Date: 2026-11-20

## Context

ADR 0008 relies on UpCloud's disk backups plus a nightly `pg_dump`. The
uploaded photos and files live in the Docker volume `checkermint_media`
(ADR 0009). The disk backup contains that volume, but only as part of a
whole-disk snapshot: getting back a few files, or moving the data to a new
server, means restoring or mounting the whole disk and finding the volume
inside Docker's data directory. The brief (section 8.3, milestone 11)
asks for a tested restore of database **and** media.

## Decision

- `scripts/backup.sh` (was `scripts/backup-db.sh`) writes the database
  dump as before and also streams the media volume out of the `web`
  container into `backups/media.tar`. The media copy is a plain,
  uncompressed tar (photos are already compressed) and only the latest one
  is kept; older states are in the UpCloud backups. Daily copies would cost
  the full media size per day.
- `scripts/test-restore.sh` restores the latest dump into a throwaway
  PostgreSQL container and extracts `media.tar` into a temporary directory,
  then compares rows per table and SHA-256 sums of every file with the
  running site. It never writes to the live database or volume, so it can
  be repeated at any time (e.g. after changes to the backup).

## Consequences

- Database and media can be restored from `backups/` with two commands
  (`docs/deployment.md`, section 6), independent of how Docker lays out
  its volumes. The UpCloud snapshot then holds both in a portable form.
- The disk needs room for one extra copy of the media (a few GB per year
  for about 10 participants, see the sizing in `docs/STATUS.md`).
- Still the same provider for all copies (ADR 0008 unchanged on that).
