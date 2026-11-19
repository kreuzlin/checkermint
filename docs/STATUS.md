# Project status

Current state of https://checkermint.ch and the next steps. **Every PR updates
this file** (at least "Last updated" and whatever the PR changes). Details
live in the linked docs; open work lives in GitHub issues.

Requirements and scope of version 1:
[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) (milestones in section 10).

_Last updated: 2026-11-19 (PR "Let coaches upload on behalf of participants")_

## Live

- **https://checkermint.ch** – not live yet. The apex does not point to a
  server of this project yet (certificate mismatch, 2026-11-18). Planned:
  apex only, `www` redirects to the apex (#2).
- Deployed commit: `curl -s https://checkermint.ch/version`, compare with
  `git rev-parse origin/main`. Last deploy: `—`. Docs- or CI-only changes
  need no deploy (the live commit then lags behind `main`).
- Search engines: never indexed (brief, section 4). Django sends
  `X-Robots-Tag: noindex, nofollow` on every response, `/robots.txt`
  disallows everything, `<meta name="robots">` in the layout, no sitemap,
  canonical or Open Graph tags. Caddy sets the same header, fixed (no
  `ROBOTS_TAG` variable any more).

## Infrastructure

| What | Where |
|---|---|
| Server | Not set up yet (#1). Planned: UpCloud, Ubuntu 26.04, 2 cores / 2 GB / 30 GB, time zone Europe/Zurich |
| Access | `ssh {{SSH_TARGET}}` (key only, no root login, passwordless sudo) – placeholder until #1 is done |
| App | `/srv/checkermint` (git checkout), `compose.prod.yaml`: `db` (PostgreSQL 18), `web` (GHCR image, Gunicorn), `caddy` (HTTPS) |
| Secrets | `/srv/checkermint/.env` on the server only |
| Deploy | `scripts/deploy.sh` on the server after CI has pushed the image for the merged commit |
| Backups | cron 02:00 `scripts/backup-db.sh` (14 days in `backups/`), UpCloud backup _daily at …_; must include the `media` volume (ADR 0009) |
| Cron | _scheduled jobs_ |
| Mail | Hostpoint SMTP, sender `coach@checkermint.ch` (#3) |
| DNS | Hostpoint; only apex and `www` of checkermint.ch are changed (#2) |
| CI | GitHub Actions: lint + tests, `linux/amd64` image to `ghcr.io/kreuzlin/checkermint` (`latest`, `sha-<commit>`) on `main`; runs on `main` are queued, never cancelled |
| GitHub | Squash merge only (PR title/body), auto-merge, head branches deleted; ruleset "protect main" active (PR, CI checks, no force push/deletion); labels `ops`, `content`, `bug`, `enhancement` |

Runbook: [`deployment.md`](deployment.md). Architecture:
[`architecture.md`](architecture.md). Decisions: [`decisions/`](decisions/)
(project-specific: 0009–0015).

## Done (version 1)

- Milestone 1 (setup), partly: GitHub settings, placeholders replaced
  (except `{{SSH_TARGET}}`), project brief added, ADRs 0009–0013 (private
  media, task versioning, submission requirements, avatars with Robohash
  set1, points and levels).
- #6: search engines blocked in the app (middleware, robots.txt, meta tag).
- #7: no public `/media/` route – Caddy has no access to the media volume,
  Django does not route `/media/` (not even with `DEBUG`).
- #8: `|markdown` filter (`markdown` + `nh3` allow-list; no images, no raw
  HTML, safe links). Milestone M1 complete.
- #9: app `accounts` with `Profile` (nickname, real name, avatar seed, about,
  visibility flags private by default, email notifications) and the group
  "Coach" (data migration; for now only view/change profiles).
- #10: login `/anmelden/` with "Angemeldet bleiben" (30 days, otherwise until
  the browser closes), logout (POST) in the header, minimum password length
  6 for participants and 8 for staff.
- #11: coaches create participant accounts with profile in one admin form,
  edit them, set new passwords and deactivate them; staff accounts and
  rights fields are out of their reach (migration `accounts/0003`).
- #12: password reset by email (`/passwort-vergessen/`, German pages and
  email, link valid 3 days) for accounts with an email address; otherwise a
  coach sets a new password. Emails go to the console until SMTP (#3, M9).
- #13: own profile `/profil/` (about text, optional email, visibility
  switches, notifications; nickname and real name only via coaches),
  internal directory and profiles `/teilnehmende/` for logged-in users
  (email only for the person and coaches).
- #14: robot avatars with Robohash set1, generated locally (no external
  requests), "Neuen Roboter würfeln" on `/profil/`, shown in the header,
  directory and profiles; CC-BY credits in the footer (to be repeated on
  the imprint page, #47).
- #15: apps `tasks` (topics, shared level table with level 1 at 0 points,
  validated: no gaps, strictly increasing) and `badges` (static artwork or
  placeholder until #4); admin for coaches (migrations `tasks/0001–0002`,
  `badges/0001`).
- #16: `Task`, `TaskVersion`, `TaskRequirement`, `Hint`; published versions
  and their requirements and hints are immutable in the model layer
  (`save`/`delete`/QuerySet guards, protected cascade), at most one draft
  per task (migrations `tasks/0003–0004`).
- #17: admin workflow for task versions: version list on the task,
  "Neue Version erstellen" (copy into a draft), draft editing with
  requirement and hint inlines, preview as participants see it, publish
  with confirmation; published versions read-only.
- #21 (ahead of #18, which needs it): private files only through
  `/dateien/<kind>/<pk>/` with per-object access checks, random storage
  names and safe headers.
- #18: images in task instructions: upload in the task admin (re-encoded
  without metadata), referenced as `![…](bild:<id>)`, served privately,
  immutable once a published version uses them (migrations
  `tasks/0005–0006`).
- #19: `TaskAttempt` pins the version per participant and task
  (`tasks.attempts.start_attempt`, `visible_version`); the version list on
  a task shows how many participants are pinned to each version
  (migration `tasks/0007`).
- #20: task catalogue `/aufgaben/` grouped by topic (status offen,
  begonnen, gesperrt with the required level; archived and unpublished
  tasks hidden) and task page `/aufgaben/<slug>/` with the pinned or latest
  version, requirements, number of hints and "Aufgabe starten". Levels are
  1 everywhere until points exist (#33); the statuses eingereicht,
  Überarbeitung nötig and gelöst follow with submissions and reviews
  (#22, #32).
- #22: app `submissions` with `Submission` (fixed published version,
  statuses Entwurf, Eingereicht, Überarbeitung nötig, Angenommen; one
  draft per participant and task; stars 1–3 only when approved, enforced
  by check constraints) and `SubmissionItem` (text, private file, original
  file name, thumbnail, data; locked once submitted). Read-only admin for
  coaches (migrations `submissions/0001–0002`).
- #23: submission form `/aufgaben/<slug>/loesung/` with requirement
  handlers for `text` and `code` (paste or text file, Pygments
  highlighting); draft, submit, resubmit after "needs revision" or
  approval (prefilled from the last submission). The task page lists the
  participant's submissions with status, stars, feedback and version; the
  catalogue now also shows eingereicht, Überarbeitung nötig and gelöst
  (with stars).
- #24: photo requirements (JPEG, PNG, HEIC, WebP; re-encoded without
  metadata, auto-rotated, 2000 px, thumbnail) and file requirements
  (optional allowed extensions); several per input, kept in the draft
  until removed, copied on resubmission; served privately to the
  participant and coaches. Size limits `UPLOAD_MAX_PHOTO_MB` /
  `UPLOAD_MAX_FILE_MB` (new in `.env.example`, defaults 15 and 20).
  ADR 0014: code uploads stored as text, every item owns its files,
  generated alt text for participant photos.
- #26: notice "Es gibt eine neuere Version dieser Aufgabe" with the change
  note, confirmation listing what of the draft is lost, switch to the
  confirmed version only; the draft is replaced by one on the new version
  with copies of the items matching by key and type (ADR 0015).
- #27: history `/verlauf/` ("Mein Verlauf" in the navigation): submitted
  and reviewed events newest first, with task, topic, version, status,
  stars, feedback and the solution; archived tasks stay without a link;
  30 events per page. Badges join with #34.
- #25: Caddy limits each request to `UPLOAD_MAX_REQUEST_MB` (default 100,
  new in `.env.example` and `compose.prod.yaml`) with a German 413 message;
  startup check `submissions.W001` keeps it consistent with the per-file
  limits. Tested locally with a Caddy container in front of the dev app.
  Milestone M4 complete.
- #28: QR code in the submission form (once a draft exists) with a signed
  link valid 30 minutes; the phone page `/hochladen/<token>/` adds photos
  and files to the draft without login (same image pipeline). The other
  device sees them without a reload since #29.
- #29: htmx 2.0.4 vendored (`core/static/core/js/`, provenance and SHA-512
  in `docs/vendored-assets.md`); the form polls the stored photos/files
  every 5 s while a draft exists (204 when unchanged).
- #30: coaches add photos and files to a participant's draft from the
  participant profile ("Fotos oder Dateien für … hochladen"); the draft is
  created if needed, the participant submits. Milestone M5 complete.
  Open point: items do not record whether a coach uploaded them (would
  need a migration; ask the maintainer if wanted).

## Open issues

Overview: `gh issue list`. At the time of writing:

| # | Topic | Who |
|---|---|---|
| 1 | Production server (UpCloud), SSH target, backups, GHCR visibility | Maintainer |
| 2 | DNS for checkermint.ch (apex and `www` only) | Maintainer |
| 3 | Outgoing mail `coach@checkermint.ch` (Hostpoint SMTP) | Maintainer |
| 4 | Logo, colours and badge artwork | Maintainer |
| 6–51 | Version 1, one issue per PR, grouped in milestones M1–M11 (brief, section 10); PRs with migrations or server changes are marked and merged by the maintainer | Claude Code |

## Next steps

1. Next: M6 review and progress: #31 coach queue, #32 review form, #33
   points and levels, #34 badges, #35 participant dashboard.
2. Libraries agreed: `markdown` + `nh3` (sanitised Markdown), `segno` (QR
   codes, added with #28), htmx served as a local static file, `robohash` (avatars),
   `pygments` (code highlighting, added with #23), `pillow` +
   `pillow-heif` (image processing incl. HEIC, explicit since #24).

## Working agreements (summary)

- Conversation with the maintainer in German; docs and code in English; site
  content German (Swiss spelling). See CLAUDE.md.
- Every change via branch + PR. Claude merges its own PRs with
  `gh pr merge <N> --squash --auto` once the checks are green, verifies with
  `gh pr view` and deploys. PRs with database migrations or server/deployment
  changes are merged by the maintainer. Never pipe `gh` output.
- Content on the live site lives only in the production database, not in
  git; local data is a playground.
- Privacy principles (brief, section 4) are hard rules.
