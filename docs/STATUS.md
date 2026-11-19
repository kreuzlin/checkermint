# Project status

Current state of https://checkermint.ch and the next steps. **Every PR updates
this file** (at least "Last updated" and whatever the PR changes). Details
live in the linked docs; open work lives in GitHub issues.

Requirements and scope of version 1:
[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) (milestones in section 10).

_Last updated: 2026-11-19 (PR "Add progress matrix for coaches")_

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
(project-specific: 0009–0016).

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
  30 events per page. Badges joined with #34.
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
  Who uploaded an item is not recorded yet: #77 (migration; merged by
  Claude until the go-live).
- Manual test of phone upload and live update (#28, #29) with phone and
  laptop: [`manual-testing.md`](manual-testing.md). Not yet done by the
  maintainer; the htmx behaviour is so far only covered by Django tests.
- #31: coach queue `/warteschlange/` ("Warteschlange" in the navigation,
  coaches only): submitted solutions of active participants, oldest
  first, with participant, topic, task, version, waiting time and a
  resubmission marker; hint requests joined with #37.
- #32: review form `/warteschlange/<id>/` (linked from the queue): the
  solution, the exact version (admin preview), a note on newer versions,
  earlier submissions; "Annehmen" with 1–3 stars or "Überarbeitung nötig"
  with feedback (no stars). htmx replaces only the review block and links
  the next waiting submission; works without JavaScript. Reviews are
  visible to the participant on the task page and in the history.
  Notifications follow with #44.
- #33: points and levels computed from reviews (`submissions.progress`,
  ADR 0013): best approved `base points × stars` per task, sum per topic,
  level from the threshold table. Locked tasks now unlock for real. The
  catalogue shows level, points and the points missing to the next level
  per topic; the task page shows the points earned. In the demo data
  RoboAnna is level 2 in Code.
- #34: badges are awarded on approval (`UserBadge`, migrations
  `badges/0002–0003`, merged by Claude before go-live): once per user and
  badge, in the review transaction. "Neue Badges im Club" on the home page
  (logged-in users only), badges on the internal profile and in the
  history; coaches can revoke an award in the admin. Demo data: two
  badges, three awards.
- #35: the home page is the participant dashboard: open revisions with
  feedback, suggested next tasks, levels per topic, recently approved
  solutions with points, the badge feed. Coaches see the queue size and
  the feed; visitors the start page (landing page #45). Demo data: MaxMotor
  has an open revision. **Milestone M6 complete.**
- Demo data for local development: `manage.py seed_demo` (only with
  `DEBUG`; `--reset`, `--remove`, password given or generated, see README).
  Covers every submission state, a resubmission, a task with two versions,
  a locked task and an unpublished draft. Extended with each feature
  (badges #34, hint requests #36). ADR 0016: deleting demo data bypasses
  the version immutability of ADR 0010 for demo tasks only.
- Coach queue (#31): shows "Wartezeit: …" (was "wartet seit 2 Tage",
  wrong case).
- Dark mint theme (maintainer's wish, 2026-11-19: "hackathon style" like
  the RoboChallenge flyer, but mint): deep petrol background with a faint
  grid, glowing mint panels for topics, dashboard blocks, submissions and
  fieldsets, heavy italic headings, pill navigation and buttons; colours
  from the logo package (#4), system fonts only. All text colours checked
  for WCAG AA (at least 5.6:1). Code highlighting switched from Pygments
  `xcode` to `one-dark` on the dark code background (at least 5.2:1).
  The header is sticky on wide screens only.
- #51: logo package from the maintainer in `design/logo/` (sources and
  rights in `design/README.md`); `design/generate_assets.py` writes the
  header logo, SVG favicon, PNG favicon and Apple touch icon to
  `core/static/core/brand/`. Maintainer's decision 2026-11-19: artwork
  made by the maintainer with AI tools may be used; Claude Code still
  never generates artwork (brief, section 11).
- #36: app `hints` with `HintRequest` (migrations `hints/0001–0002`,
  merged by Claude before go-live). "Hinweis anfragen" on the task page
  for the next hint with an optional message; one open request per task;
  starts the task; "Anfrage wartet auf einen Coach", granted hints with
  the coach's reply, reply to a declined request. Granted is decided by
  the hint key, so it already carries over on a version switch (#38 adds
  the notice in the switch confirmation). Read-only admin for coaches.
  Demo data: one granted, one declined, one open request.
- #37: open hint requests join the coach queue (merged with submissions,
  oldest first) with the participant's message and the hint's text;
  "Freigeben" / "Ablehnen" with an optional reply via htmx (works
  without JavaScript); a request decided twice is refused. The coach
  home page counts solutions and hint requests separately.
- #38: the version switch confirmation lists the granted hints that stay
  granted (same key) and warns about granted hints the new version no
  longer has; an open hint request for such a hint blocks the switch
  until a coach decided it. **Milestone M7 complete.**
- #39: progress matrix `/fortschritt/` ("Fortschritt" in the navigation,
  coaches only, new app `overviews`): participants × tasks with the
  status in words and the best stars, filter by topic with the level per
  participant; same rules as the catalogue, fixed number of queries.
  `task_state` now takes a `coach` flag (the catalogue no longer asks
  the database once per task).
- 2026-11-19: on the maintainer's one-time instruction, Claude merged #73
  (Caddy upload limit, a server change) itself. The merge exceptions in
  CLAUDE.md stay in force: PRs with migrations or server/deployment
  changes are merged by the maintainer.
- 2026-11-19: maintainer's decision: until the go-live (first deploy to
  the production server, #1) Claude merges PRs with migrations itself –
  there is no production data yet. Server and deployment PRs stay with
  the maintainer. From the go-live on, migrations are merged by the
  maintainer again (CLAUDE.md, Workflow).

## Open issues

Overview: `gh issue list`. At the time of writing:

| # | Topic | Who |
|---|---|---|
| 1 | Production server (UpCloud), SSH target, backups, GHCR visibility | Maintainer |
| 2 | DNS for checkermint.ch (apex and `www` only) | Maintainer |
| 3 | Outgoing mail `coach@checkermint.ch` (Hostpoint SMTP) | Maintainer |
| 4 | Badge artwork (logo and colours delivered) | Maintainer |
| 36–50 | Version 1, one issue per PR, grouped in milestones M7–M11 (brief, section 10); PRs with server changes (and, from the go-live on, migrations) are marked and merged by the maintainer. #42 (SMTP), #49 (media backup/restore) and #50 (rollback, go-live) need the server (#1) and SMTP access (#3) first | Claude Code |
| 77 | Show who uploaded a submission item (follow-up to #30; migration) | Claude Code |

## Next steps

1. M8 coach overviews: #40 participant detail, #41 task detail.
2. Maintainer: manual test of phone upload and live update
   ([`manual-testing.md`](manual-testing.md)).
3. #77 show who uploaded a submission item (migration; M6 is done, so
   it can be picked up any time).
4. Libraries agreed: `markdown` + `nh3` (sanitised Markdown), `segno` (QR
   codes, added with #28), htmx served as a local static file, `robohash` (avatars),
   `pygments` (code highlighting, added with #23), `pillow` +
   `pillow-heif` (image processing incl. HEIC, explicit since #24).

## Working agreements (summary)

- Conversation with the maintainer in German; docs and code in English; site
  content German (Swiss spelling). See CLAUDE.md.
- Every change via branch + PR. Claude merges its own PRs with
  `gh pr merge <N> --squash --auto` once the checks are green, verifies with
  `gh pr view` and deploys. PRs with server/deployment changes are merged
  by the maintainer; PRs with database migrations too, but only from the
  go-live on (until then Claude merges them). Never pipe `gh` output.
- Content on the live site lives only in the production database, not in
  git; local data is a playground.
- Privacy principles (brief, section 4) are hard rules.
