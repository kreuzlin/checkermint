# 0018: Badge images uploaded in the admin (exception from ADR 0009)

- Status: accepted (maintainer, 2026-11-21)
- Date: 2026-11-21

## Context

Badge images are static files today: the originals go to `design/badges/`,
`design/generate_assets.py` writes the web versions to
`badges/static/badges/img/`, and the badge admin only offers images that
ship with the app. A new badge image therefore needs a PR, a CI run and a
deploy (about 8 minutes on 2026-11-21, plus Claude's time), and coaches
cannot do it themselves.

The reason was ADR 0009: uploads are private, but badges appear on public
profiles (`/p/<nickname>/`), so their images had to be static.

The maintainer wants coaches to upload badge images in the admin, with
these conditions (2026-11-21): only coaches upload; only PNG or WebP, no
SVG; the image is re-encoded on upload, without metadata and with a
limited size.

## Decision

A deliberate, narrow exception from ADR 0009 for **badge images only**.
Everything else in ADR 0009 stays as it is: no public `/media/` route, no
other upload becomes public.

1. **Storage.** `Badge.image` becomes an image file in the private media
   volume, under a random name in `badges/` (`core.private_files`
   `RandomUploadPath`), like other uploads. The shipped set is no longer
   needed (see 7).
2. **Who uploads.** Only in the badge admin. The upload field is shown and
   accepted only for staff users in the group "Coach" and for superusers.
   Participants have no upload path for badges.
3. **What is accepted.** The format is detected by decoding the file with
   Pillow, not by the file name: **only PNG and WebP**. SVG, GIF, JPEG,
   HEIC and everything else are rejected with a German error message. Limits:
   at most 2 MB per upload and at most 4096 × 4096 px, checked before
   decoding the pixels (decompression bombs, as in `core.images`).
4. **Re-encoding.** Every upload is decoded and saved again as PNG with
   transparency, containing pixels only (no EXIF, XMP, text chunks or ICC
   profile), using the same code as photos (`core.images`). Size: the
   visible motif is cropped and centred at 85 % of the height on a square
   of **512 × 512 px**, as `design/generate_assets.py` does today, so all
   badges look equally large. If an image cannot be decoded, it is rejected.
   The original upload is never stored.
5. **Public delivery.** A dedicated Django view, `/badges/<id>/bild/<hash>.png`,
   delivers **only** the processed image of that badge, without login:
   - it loads the `Badge` by id and serves the path stored on it, never a
     path taken from the URL;
   - `Content-Type: image/png`, `X-Content-Type-Options: nosniff`,
     `Content-Disposition: inline` (our own re-encoded PNG);
   - `<hash>` is a hash of the file content, so the URL changes when the
     image changes; responses may be cached publicly for a year
     (`Cache-Control: public, max-age=31536000, immutable`);
   - Caddy does not change: it still has no access to the media volume.
6. **Replacing and deleting.** When an image is replaced or a badge is
   deleted, the old file is removed after the database commit.
7. **The shipped set.** A data migration copies the eight shipped images
   (`badges/static/badges/img/`) into the new field for the badges that use
   them, through the same processing. After that, the static folder, the
   choice list in the admin and the badge part of
   `design/generate_assets.py` are removed. `design/badges/` stays as the
   archive of the originals and their prompts (rights in
   `design/README.md`).
8. **Responsibility.** The badge admin shows a notice next to the upload
   field (maintainer's requirement): "Keine Fotos von Personen hochladen –
   nur Grafiken. Das Bild ist öffentlich sichtbar (öffentliche Profile)."
   Coaches remain responsible for the usage rights; the source is noted in
   the badge's description field if needed (no extra field).

## Consequences

- Coaches add or change a badge image in about a minute, without PR,
  CI or deploy.
- One more public URL pattern. It can only return images that a coach
  uploaded and that we re-encoded, never participant uploads or other files.
  A test checks that the view refuses anything that is not a badge image.
- The risk moves to the content: a coach could upload a photo of a child
  as a badge, and it would be public. Mitigated by the help text and by
  coaches being trained adults; technically we cannot tell artwork from a
  photo.
- Badge images are now part of the media backups (ADR 0017) instead of the
  image; restoring the database without media would leave badges without
  images (shown as the placeholder).
- No SVG: no scripts in images, at the price of less sharp scaling. At
  512 px this does not matter for 40–48 px display.
- Implementation in two PRs, one after the other from `main`, both merged
  by the maintainer because both contain a migration:
  1. the new image field, the processing and a data migration that fills it
     from the eight shipped images (no visible change yet);
  2. the public view, the upload in the admin with the notice, switching
     the templates to the new image, and the cleanup: removing the old
     choice field (migration), the shipped images and the badge part of
     `design/generate_assets.py`.

## Maintainer's answers (2026-11-21)

- The eight existing images are moved into the upload: there is only one
  way to set a badge image.
- Uploaded images are cropped and centred automatically, like the shipped
  ones.
