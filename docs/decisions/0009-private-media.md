# 0009: Private media served by Django

- Status: accepted
- Date: 2026-11-18

## Context

Participants are children aged 7 to 16. Their submissions contain photos,
often of themselves, their hands or their robots at home, and files. The
brief (section 4) makes it a hard rule that no uploaded photo or file is ever
public, that EXIF metadata is removed, and that media is never served from a
public `/media/` URL.

The template does the opposite: Caddy mounts the `media` volume read-only and
serves `/media/*` to anyone (`deploy/Caddyfile`, `compose.prod.yaml`).

## Decision

1. **No public media path.** The `media` volume is mounted only into the
   `web` container. The `handle_path /media/*` block in the Caddyfile and the
   volume mount in the `caddy` service are removed. `MEDIA_URL` is not
   routed by Django's static handling either.
2. **Authenticated view.** Every file is delivered by a Django view
   (`/dateien/<id>/…`), which loads the database object the file belongs to
   and checks access per object before streaming it with `FileResponse`:
   - submission items (photos, files, code files) and their thumbnails: the
     owning participant and coaches;
   - images in task instructions: any logged-in user who may see that task
     version (published, or coach for drafts);
   - avatars are SVG generated on the fly (ADR 0012) and are not media.
   The view never maps a URL path to a file system path; it only serves the
   path stored on the object.
3. **Unguessable storage names.** Files are stored under random names
   (UUID4) in per-model directories; the original file name is kept in the
   database for display and download.
4. **Response headers.** `Cache-Control: private, no-store` for submission
   content, `X-Content-Type-Options: nosniff`, and
   `Content-Disposition: attachment` for everything except images we have
   re-encoded ourselves (no browser rendering of uploaded HTML or SVG).
5. **Image processing on upload** (Pillow, HEIC via `pillow-heif`): decode,
   apply EXIF orientation, re-encode without any metadata (EXIF, GPS, XMP,
   ICC kept only if needed for colour), resize to at most 2000 px on the long
   edge, store a thumbnail. Re-encoding is the guarantee that metadata is
   gone; uploads that cannot be decoded as images are rejected.
6. **Size limits** in both places: Django
   (`DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE`, and a
   per-file check in the form) and Caddy (`request_body { max_size … }`),
   configured through `.env`.
7. **Backups** cover the `media` volume as well as the database (brief,
   section 8). Restoring both is tested before go-live.

## Consequences

- Photos cannot leak through a guessed or shared URL; a link only works for
  a logged-in user with access to the object.
- Every file request goes through Gunicorn. With about 15 users this is
  negligible. If it ever matters, Caddy's `intercept` handler can serve the
  file after Django has authorised the request (X-Accel-Redirect pattern)
  without making the path public.
- Removing the public media route changes `deploy/Caddyfile` and
  `compose.prod.yaml`; that PR is merged by the maintainer.
- Uploaded files are not cacheable by browsers; thumbnails keep list views
  light.
