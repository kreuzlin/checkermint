# Project status

Current state of https://checkermint.ch and the next steps. **Every PR updates
this file** (at least "Last updated" and whatever the PR changes). Details
live in the linked docs; open work lives in GitHub issues.

Requirements and scope of version 1:
[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) (milestones in section 10).
Next project, approved by the maintainer 2026-11-21:
[`GEARSBOT_BRIEF.md`](GEARSBOT_BRIEF.md) (GearsBot simulator; see
"GearsBot" below).

_Last updated: 2026-11-21 (PR "Add the monthly GearsBot update workflow", #143)_

## Live

- **https://checkermint.ch** – deployed since 2026-11-20, **not productive
  yet** (no real participants or data; the maintainer declares it
  productive). Apex
  and `www` (A and AAAA) point to the server; Let's Encrypt certificate via
  Caddy; `http://` and `www` redirect to `https://checkermint.ch/`; IPv4 and
  IPv6 answer. The maintainer's admin account exists (2026-11-20).
  **Demo data** is loaded for testing (accounts `demo-coach`,
  `demo-anna` … `demo-luna`; must be removed before the go-live). Email
  goes out via Hostpoint SMTP since 2026-11-20 (#42).
- Deployed commit: `curl -s https://checkermint.ch/version`, compare with
  `git rev-parse origin/main`. Last deploy: 2026-11-21, `0a72d51`
  (checked at the session start on 2026-11-21). Docs- or CI-only changes need no deploy (the live
  commit then lags behind `main`).
- Search engines: never indexed (brief, section 4). Django sends
  `X-Robots-Tag: noindex, nofollow` on every response, `/robots.txt`
  disallows everything, `<meta name="robots">` in the layout, no sitemap,
  canonical or Open Graph tags. Caddy sets the same header, fixed (no
  `ROBOTS_TAG` variable any more).

## Infrastructure

| What | Where |
|---|---|
| Server | UpCloud `de-fra1` (Frankfurt), `85.9.202.23` / `2a04:3542:1000:910:9010:e8ff:fe50:74f8`, Ubuntu 26.04.1, 2 cores / 2 GB / 30 GB, 2 GB swap, time zone Europe/Zurich, `ufw` (22, 80, 443 tcp/udp), unattended upgrades. Set up 2026-11-20 by Claude (deployment.md, section 1) |
| Access | `ssh deploy@85.9.202.23` (key only, root login and passwords disabled, passwordless sudo, member of `docker`) |
| Docker | Docker Engine 29.10 with Compose 5.8 from Docker's apt repository; `/etc/docker/daemon.json` limits container logs to 5 × 10 MB = 50 MB per container (maintainer's decision 2026-11-20, #97); logs also go when a container is recreated |
| App | `/srv/checkermint` (git checkout), `compose.prod.yaml`: `db` (PostgreSQL 18), `web` (GHCR image, Gunicorn), `caddy` (HTTPS), `sim` (GearsBot, own GHCR image, since #142) |
| Secrets | `/srv/checkermint/.env` on the server only |
| Deploy | `scripts/deploy.sh` on the server after CI has pushed the image for the merged commit |
| Backups | cron 02:00 `scripts/backup.sh`: database dump (14 days) and `media.tar` (latest only) in `backups/` (ADR 0017); restore test `scripts/test-restore.sh`; first nightly run 2026-11-21 02:00 OK (dump and `media.tar`); UpCloud backup daily at 02:15 (set by the maintainer 2026-11-20, after the dump); must include the `media` volume (ADR 0009) |
| Cron | `deploy`'s crontab: `0 2 * * * cd /srv/checkermint && scripts/backup.sh` (switched from `backup-db.sh` after #107, 2026-11-20) |
| Mail | Hostpoint SMTP `asmtp.mail.hostpoint.ch:465` (SSL), login and sender `mail@checkermint.ch` (mailbox created by the maintainer 2026-11-19). Outbound 465/587 not blocked by UpCloud. SPF `redirect=spf-permissive.mail.hostpoint.ch`, DKIM (three keys, selectors `20261121-{rsa1024,rsa2048,ed25519}-2051a403`) and DMARC `p=quarantine` enabled by the maintainer at Hostpoint 2026-11-21; sender policy "only with the mailbox's own user" fits (login, `DEFAULT_FROM_EMAIL` and `SERVER_EMAIL` are all `mail@checkermint.ch`) |
| DNS | Hostpoint; only apex, `www` and `sim` of checkermint.ch are changed (#2, GearsBot brief). Both point to the server (A and AAAA) since 2026-11-20; `sim` (A and AAAA, GearsBot simulator) added by the maintainer 2026-11-21; MX records unchanged |
| GearsBot | pinned upstream commit `c0549600a26f` (`sim/gears/UPSTREAM`), set 2026-11-21; monthly update PRs by the workflow "GearsBot update" (ADR 0020) |
| CI | GitHub Actions: on pull requests lint + tests and, in parallel, an image build (no push); on `main` only the `linux/amd64` image build and push to `ghcr.io/kreuzlin/checkermint` (`latest`, `sha-<commit>`), no second test run (#118, #119); runs on `main` are queued, never cancelled |
| GitHub | Squash merge only (PR title/body), auto-merge, head branches deleted; ruleset "protect main" active (PR, CI checks, branch up to date with `main` since #119, no force push/deletion); labels `ops`, `content`, `bug`, `enhancement` |

Runbook: [`deployment.md`](deployment.md). Architecture:
[`architecture.md`](architecture.md). Decisions: [`decisions/`](decisions/)
(project-specific: 0009–0016).

## Done (version 1)

- Milestone 1 (setup), partly: GitHub settings, placeholders replaced
  (`{{SSH_TARGET}}` last, 2026-11-20), project brief added, ADRs 0009–0013 (private
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
  directory and profiles; CC-BY credits in the footer and on the imprint
  page (#47).
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
  Since #77 every item records who added it (see below).
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
- #40: participant detail `/fortschritt/teilnehmende/<nickname>/` for
  coaches (linked from the progress matrix and the internal profile): real
  name, level per topic, suggested next tasks (same rules as the
  dashboard), all submissions with status, stars, points and feedback
  (linked to the review page) and all hint requests with their outcome.
- #41: task detail `/fortschritt/aufgaben/<slug>/` for coaches (linked
  from the matrix column headers and the task page): who solved it with
  the best stars and the version, average stars, hint statistics per key
  (requested, granted, declined, open) and the versions with change notes
  and pinned participants. **Milestone M8 complete.**
- #45: landing page for visitors on `/` (what Checkermint is, how it
  works, who can take part with a link to vrobot.ch, a note for parents);
  no images, no participant data. Wording to be reviewed by the
  maintainer.
- #46: public profiles `/p/<nickname>/` without login: nickname, avatar,
  level and points per topic; about text, badges and titles of solved
  tasks only when switched on. Never real name, email, username, feedback
  or submission content (tested). Linked from `/profil/` and the internal
  profile only, not from any public page.
- #48: ranking per topic `/rangliste/` for logged-in users, linked only
  at the bottom of the catalogue: rank (ties share), avatar, nickname,
  level and points; participants without points only counted.
- #47: privacy page `/datenschutz/` and imprint `/impressum/`, linked in
  the footer of every page (and from the landing page). Operator:
  "Verein Robotik Talente (VRoboT)" (name as on vrobot.ch), contact
  `privacy@checkermint.ch` (maintainer's decision, 2026-11-19; mailbox
  created by the maintainer the same day), server at
  UpCloud in Germany, mail via Hostpoint. Both live in `settings.py`
  (`CLUB_NAME`, `PRIVACY_EMAIL`); the "Stand" date in
  `core.views.PRIVACY_UPDATED`. The imprint has no postal address yet.
  Texts approved by the maintainer (2026-11-19). **Milestone M10
  complete.**
- #43: new app `notifications`: email to coaches on every submission,
  resubmission and hint request (link to the review page or the queue),
  one message per coach, after commit, errors only logged; coaches turn
  it off on `/profil/`. Goes to the console until SMTP is set up (#3,
  #42).
- #44: email to participants (only with an address and the switch on)
  when a solution is approved (stars, points, badge, feedback) or needs
  revision, and when a hint request is granted or declined (with the
  coach's reply).
- #77: `SubmissionItem.uploaded_by` and `via_phone` (migration
  `submissions/0003`, merged by Claude before go-live): set by the form
  (participant), the coach upload page (coach) and the phone page ("per
  Handy", no login); copies on resubmission and version switch keep them.
  Shown as "hochgeladen von Coach …" / "per Handy hochgeladen" in the
  form, on the task page, in the history and the review; never public.
- 2026-11-19: on the maintainer's one-time instruction, Claude merged #73
  (Caddy upload limit, a server change) itself. The merge exceptions in
  CLAUDE.md stay in force: PRs with migrations or server/deployment
  changes are merged by the maintainer.
- 2026-11-19: maintainer's decision: until the go-live (first deploy to
  the production server, #1) Claude merges PRs with migrations itself –
  there is no production data yet. Server and deployment PRs stay with
  the maintainer. From the go-live on, migrations are merged by the
  maintainer again (CLAUDE.md, Workflow).
- 2026-11-20: production server set up by Claude on the maintainer's
  instruction (#1, deployment.md section 1): updates and reboot, time
  zone, swap, firewall, user `deploy`, root login disabled, Docker with log
  limits. Repo cloned to `/srv/checkermint` (`main` at `3380288`), cron
  restarted after the time zone change. `.env` created from `.env.example`
  with the non-secret production values (`DEBUG=false`, `ALLOWED_HOSTS`,
  `CSRF_TRUSTED_ORIGINS`, `SITE_ADDRESS=checkermint.ch`,
  `REDIRECT_ADDRESSES=www.checkermint.ch`,
  `DEFAULT_FROM_EMAIL=mail@checkermint.ch`); `SECRET_KEY` and the database
  password were generated on the server (never shown) on the maintainer's
  instruction to do as much as possible. The GHCR image is public
  (anonymous pull works).
- 2026-11-20: **first production deploy** (`scripts/deploy.sh`, image
  `3380288`, all migrations applied). Checked from outside: `/`,
  `/anmelden/`, `/admin/login/`, `/datenschutz/`, `/robots.txt` 200;
  `/media/…` 404; `X-Robots-Tag: noindex, nofollow`, HSTS (Caddy); HTTP and
  `www` redirect to the apex; IPv4 and IPv6. `check --deploy` only warns
  about `SECURE_HSTS_SECONDS` and `SECURE_SSL_REDIRECT`, both handled by
  Caddy. Backup cron set up, first dump OK. Memory after start: about
  770 MB used of 1.8 GB, swap unused. Scanners (leakix etc.) probed the
  site within a minute of the certificate being issued; all got 404.
- 2026-11-20: maintainer's decision: the deploy is not the go-live. Until
  the maintainer declares the app productive (real participants and data),
  Claude keeps merging PRs with migrations itself. Server and deployment
  PRs stay with the maintainer.

- #50: rollback tested on the server 2026-11-20: `IMAGE_TAG=sha-f0adf44…`
  and `scripts/deploy.sh` (7 s), `/version` showed `f0adf44`, pages 200;
  back to `latest` (`22a0f91`). Finding: the old image does not know
  `submissions/0003`, and `via_phone` is `NOT NULL` without a database
  default, so the old code could not save uploads – rollbacks across
  migrations need a check first (deployment.md, section 4). Go-live
  checklist in deployment.md, section 9 (section 8 renamed "Domain
  switch").
- #49: `scripts/backup.sh` (renamed from `backup-db.sh`) also copies the
  media volume to `backups/media.tar`; `scripts/test-restore.sh` restores
  the latest backup into throwaway containers and compares rows per table
  and file checksums with the live site (ADR 0017). Tested on the server
  2026-11-20 with sample files: restore test passes, detects an added row
  and an added file; a real restore of database and media (runbook section
  6) brought the files back identical. Sample data removed afterwards.

- #42: SMTP live on 2026-11-20: Hostpoint credentials in the server
  `.env` (`EMAIL_BACKEND` smtp, `asmtp.mail.hostpoint.ch`, 465, SSL),
  `web` recreated, `sendtestemail mail@checkermint.ch` accepted by
  Hostpoint. No code change was needed: the settings and `.env.example`
  came with the notifications PRs. The maintainer passed the mailbox
  password through the chat; it should be changed at Hostpoint and
  entered on the server without echo (deployment.md, section 3).
  Maintainer's decision 2026-11-20: the password stays as it is.
- 2026-11-20, maintainer's decisions: container logs stay limited by size,
  50 MB per container (#97; "regelmässig gelöscht" on the privacy page
  holds); the imprint gets no postal address, the contact is
  `privacy@checkermint.ch` (already shown).

- 2026-11-20: on the maintainer's request, demo data (`seed_demo`) loaded
  on the server for testing, in a one-off container with `DEBUG=true`
  (the site itself keeps `DEBUG=false`):
  `docker compose -f compose.prod.yaml run --rm -e DEBUG=true web python manage.py seed_demo`.
  ADR 0016 meant the command for local development; this is a temporary
  exception while the app is not productive. The demo accounts have no
  email address, so no emails were sent. The password was generated and
  given to the maintainer in the chat, not stored anywhere. Checked: demo
  coach login, home, catalogue, queue, progress, ranking, directory and
  admin answer 200; 11 files in the media volume.

- 2026-11-21 (#3): after the maintainer enabled DKIM and DMARC at
  Hostpoint, a test email to `mail@checkermint.ch` showed `spf=pass`,
  `dkim=pass` (all three signatures) and `dmarc=pass`, spam score −0.3
  (limit 4.0), delivered to the inbox (headers read via IMAP, only that
  message). The DKIM selectors from the signatures resolve at `ns` and
  `ns2.hostpoint.ch`. A test email to the maintainer's external (iCloud)
  address arrived in the inbox, not in spam. The first test on
  2026-11-20, before DKIM/DMARC, had landed in spam.
- 2026-11-21: first nightly `scripts/backup.sh` by cron at 02:00 wrote
  the dump and `media.tar`. Disk 25 % used.

- #4: badge artwork from the maintainer, made with ChatGPT (prompt and
  file list in `design/badges/PROMPT.md`, rights in `design/README.md`):
  six badges (Erste LED, Code-Starter, Greifarm, Sensor-Profi,
  Konstrukteur/in, Durchhalter/in) as 1024 px originals in
  `design/badges/`; `design/generate_assets.py` now also writes 160 px web
  versions to `badges/static/badges/img/`, which the badge admin offers.
  Checked at 40 px on the dark background. Coaches create the badges in
  the admin and pick the image there.
- 2026-11-21: on the maintainer's request, Claude created the six badges
  in the production database (name, one-sentence description, image), not
  attached to any task yet – there are only demo tasks so far. Real
  content, not demo data: `seed_demo --remove` does not touch them.
  Descriptions can be changed in the admin.
- 2026-11-21, on the maintainer's request (to see the look and feel), on
  the server: badges attached to the demo tasks (Blinklicht → Code-Starter,
  Sensor auslesen → Sensor-Profi, LED-Schaltung → Erste LED, Greifarm →
  Greifarm, Gehäuse → Konstrukteur/in; Linienfolger → Linienfolger and
  Motor ansteuern → Motor after this PR). The two image-less demo badges
  were revoked and deleted. For approved demo submissions the awards were
  given afterwards with `award_for` (same rule as a review, dated with the
  review) – normally badges are not retroactive. Tested locally that
  `seed_demo --remove` then still removes all demo tasks and awards and
  keeps the real badges. The attachments go with the demo tasks.
- Two more badges from the maintainer (Linienfolger, Motor, made with
  ChatGPT from a follow-up prompt in `design/badges/PROMPT.md`).
  `design/generate_assets.py` now crops each badge to its motif and centres
  it at 85 % of the height, because the new originals were larger with less
  margin; all eight web versions are regenerated and look the same size.

- #117: tests use the MD5 password hasher through
  `config.test_runner.FastPasswordHasherRunner` (`TEST_RUNNER`); the live
  site keeps PBKDF2, checked by `config/tests/test_password_hashers.py`.
  Locally 505 tests in 16.5 s instead of 114 s (hashing was about 85 % of
  the test time, analysis 2026-11-21).

- #118: the image job no longer waits for the test job; on pull requests
  both run at the same time (both stay required checks). Until #119 is
  merged, `main` also runs both in parallel, so `latest` can be pushed
  before the tests on `main` finish; the deploy still waits for the whole
  run to be green.

- #119: `Lint and test` runs only on pull requests; on `main` CI only
  builds and pushes the image. Needs the ruleset setting "Require branches
  to be up to date before merging" (set by the maintainer); CLAUDE.md
  describes `gh pr update-branch` for PRs that fall behind.
- ADR 0018 accepted (2026-11-21): coaches upload badge images in the admin
  (PNG/WebP only, re-encoded without metadata, cropped and centred at
  512 px, served by a dedicated public view) – a narrow exception from ADR
  0009. The eight shipped images move into the upload. Implemented in two
  PRs (#120). (Since the merge rule of 2026-11-21: part 1 adds a field
  and fills it – merged by Claude; part 2 removes the old field and needs
  the maintainer's OK.)
- Maintainer's rules 2026-11-21: never stack PRs (each from `main`, one
  after another); `git` output is not filtered either (CLAUDE.md,
  Workflow).

- #120, part 1: `Badge.image_file` (migration `badges/0004`) and
  `badges.images.process_badge_image` (PNG/WebP only, max 2 MB and
  4096 px, re-encoded as a 512 px PNG without metadata, motif cropped and
  centred). Data migration `badges/0005` moves the eight shipped images
  into `image_file`; the shipped files are generated at 512 px for that
  (about 190 KB each, until part 2 removes them). No visible change yet;
  merged by the maintainer (migration).

- #120, part 2: coaches (and superusers) upload badge images in the admin
  ("Bild hochladen", notice "Keine Fotos von Personen hochladen – nur
  Grafiken …", PNG/WebP only) or remove them; staff outside the coach group
  cannot. Public view `/badges/<id>/bild/<file name>.png` (no login,
  `nosniff`, inline, cached a year; the URL changes with every upload).
  Migration `badges/0006` removes the old field `image`; the shipped images
  and the badge part of `design/generate_assets.py` are gone. Merged after
  the maintainer's OK (field removal).

- #128: the phone upload failed on the maintainer's iPhone with 403 (CSRF):
  the page's `no-referrer` policy makes browsers send `Origin: null` on the
  POST. Now `strict-origin` (only the origin, never the token, as
  referrer); a test posts with CSRF enforcement and an `Origin` header.
  The manual test of the phone upload is to be repeated.

- #130: the QR code for the phone upload appeared only after "Entwurf
  speichern" – after "Aufgabe starten" the maintainer saw only the file
  inputs. Now the QR code is shown right away; the link is bound to
  participant and task, and the first phone upload creates the draft
  (`ensure_draft`). Live update keeps polling until the draft exists.

- #132: iPhone photos (`IMG_….jpeg`) were rejected with "Erlaubt sind
  JPEG, PNG, HEIC und WebP": they contain an HDR gain map, so Pillow opens
  them as "MPO". Now accepted; only the photo itself is kept, re-encoded
  as JPEG without metadata. The maintainer's attempt also showed that the
  CSRF fix (#128) works (`Origin: https://checkermint.ch`, 200).

- #134: the phone upload page ("Fotos hochladen") also showed file fields
  (e.g. "3D-Modell (.stl)"); the maintainer picked a photo in the wrong
  field. Now the phone page shows photo requirements only, and the QR code
  appears only for tasks with photos (brief 5.7). The coach upload keeps
  photos and files. Videos stay out of scope for version 1 (brief,
  section 6). The maintainer's phone upload works (2026-11-21).

- Database dumps are named `db-YYYY-MM-DD-HHMMSS.dump`: the manual
  backup before #127 had replaced the nightly dump of the same day
  (`db-YYYY-MM-DD.dump`). `scripts/test-restore.sh` picks the newest dump
  by modification time.
- The maintainer's phone upload works (2026-11-21, after #128–#134);
  checked off in the go-live checklist.

- Email tests by the maintainer (2026-11-21): the coach notification on a
  submission arrives in the inbox (sent to the superuser `linard`, the
  only account with an address); the password reset works, but its email
  lands in spam. Maintainer's decision: accepted, common for reset emails
  (possible later: sender name "Checkermint", calmer wording). The email
  to a participant after a review is still to be tried (needs an address
  on a demo account).

- #138: coaches reach the admin without typing `/admin/`: "Verwaltung"
  in the main navigation, "Neue Aufgabe erstellen" on the catalogue and
  "In der Verwaltung bearbeiten" on each task page (coaches only).

## GearsBot (brief approved 2026-11-21)

- Brief: [`GEARSBOT_BRIEF.md`](GEARSBOT_BRIEF.md). Spike done 2026-11-21
  against upstream `c0549600` (still `master`):
  [`gearsbot-spike.md`](gearsbot-spike.md). All facts of brief section 2
  confirmed; new findings: 61 challenges with 61 codes, the default robot
  and other worlds also load from `files.aposteriori.com.sg` (33 files,
  0.8 MB, plus one on GitHub), the challenge file name must stay in the
  world URL, the block filter uses English ids (works in German), the
  brief's first block filter lacks the turns that "Move and Turn" needs.
- ADRs 0019–0022 **accepted** by the maintainer (2026-11-21): hosting on
  `sim.checkermint.ch` with its own image, pin and monthly update PRs,
  simulator configuration on task versions and the code check, GPLv3 and
  attribution.
- Maintainer's decisions 2026-11-21: merging follows CLAUDE.md as for
  everything else; only the scheduled GearsBot update PRs are merged by the
  maintainer. "Grundlagen" shows turn blocks (ADR 0021). All 34 external
  files are mirrored and the simulator's CSP blocks third-party hosts. The
  challenge rules live in GearsBot and can change with an update; update
  PRs report it (ADR 0020).
- Issues #141–#147 created 2026-11-21 (image, server, update workflow,
  task configuration, submissions, import, coach guide).
- #141: `sim/gears/` builds `ghcr.io/kreuzlin/checkermint-sim` (workflow
  "Simulator", only when `sim/` changes): upstream at the pinned commit,
  34 mirrored files (553 URLs rewritten), start page with German default,
  Caddy with caching and CSP. Checked locally with Chrome: challenge deep
  link with world and filter from another origin works, German UI, filter
  applies, no CSP violations, no third-party requests. The GHCR package
  `checkermint-sim` is public (anonymous pull checked 2026-11-21). The hidden
  beginner category is labelled "Movement" in English (no translation in
  GearsBot).
- #142: `sim` service in `compose.prod.yaml`, Caddy site `{$SIM_ADDRESS}`
  → `sim:8080`, `deploy.sh` pulls `sim`, new variables `SIM_ADDRESS`,
  `SIMULATOR_URL`, `SIM_IMAGE_TAG`; imprint names GearsBot with the pinned
  commit (ADR 0022), privacy page has a "Simulator" paragraph when
  `SIMULATOR_URL` is set ("Stand" 21 November 2026). DNS `sim` A and AAAA
  added by the maintainer 2026-11-21; the maintainer allowed Claude to set
  the `.env` values on the server.
- 2026-11-21: #142 deployed (`75e5e97`): `.env` values `SIM_ADDRESS`,
  `SIMULATOR_URL`, `SIM_IMAGE_TAG` added by Claude (maintainer's OK),
  `scripts/deploy.sh` started `sim`; `https://sim.checkermint.ch` live with a
  Let's Encrypt certificate (IPv4 and IPv6), headers checked; in Chrome the
  live simulator starts in German and makes requests only to
  `sim.checkermint.ch`.
- #143: `sim/gears/check.py` parses the Basic Challenges (61, each with a
  completion code, block limit and English mission text) and writes the
  committed bundle `sim/gears/challenges_basic/` (`challenges.json` + world
  files with mirror URLs, about 1 MB). CI job "GearsBot" on every PR: parser
  tests and "bundle matches the pin" (fetches only the challenge files).
  Workflow "GearsBot update" (monthly and manual): bumps the pin, mirrors
  new third-party files, regenerates the bundle, opens or updates the PR
  `chore/gearsbot-update` with commit log and change report. Needs the
  repository setting "Allow GitHub Actions to create and approve pull
  requests" (maintainer); GitHub runs no checks on PRs opened by a
  workflow, so the PR is closed and reopened to start them. The "GearsBot"
  check is to be added to the ruleset by the maintainer.
- Next: the issues in the brief's order (hosting
  and build, update workflow, simulator configuration, submissions and
  review, import command, coach guide), one PR each, never stacked.
- Needs the maintainer later: DNS record `sim` (A and AAAA, only added),
  `.env` values `SIM_ADDRESS` and `SIMULATOR_URL` on the server, OKs for
  the server/Caddy/deploy PR, merging the GearsBot update PRs, the
  "GearsBot" check in the ruleset, testing the simulator on the club's
  devices before the first tasks are published.

## Open issues

Overview: `gh issue list`. At the time of writing:

| # | Topic | Who |
|---|---|---|
| 1 | Production server (UpCloud): set up, deployed, backups running, maintainer's admin account created (2026-11-20) – nothing left, can be closed (still open on 2026-11-21) | Maintainer |

## Next steps

1. The go-live checklist (deployment.md, section 9) until the
   maintainer declares the app productive.
2. Maintainer: manual test of phone upload and live update
   ([`manual-testing.md`](manual-testing.md)).
3. GearsBot: issues one after another, starting with the `sim` image
   (see "GearsBot" above).
4. Libraries agreed: `markdown` + `nh3` (sanitised Markdown), `segno` (QR
   codes, added with #28), htmx served as a local static file, `robohash` (avatars),
   `pygments` (code highlighting, added with #23), `pillow` +
   `pillow-heif` (image processing incl. HEIC, explicit since #24).

## Working agreements (summary)

- Merging (maintainer's rule, 2026-11-21): Claude merges every PR itself
  once the checks are green. It asks in the chat first, and merges after
  the OK, for migrations that delete data or fields or rework existing
  data, for changes to the server, DNS, Caddy, secrets or
  `scripts/deploy.sh`, and for CI changes that weaken or remove checks
  (CLAUDE.md, Workflow). The earlier "maintainer merges migration and
  server PRs" rule is replaced.
- On the server Claude runs only read-only commands without the
  maintainer's explicit OK; executing or changing anything (also
  `scripts/deploy.sh`) needs the OK first, except the normal deployment
  after a merged PR (CLAUDE.md, Workflow; rule since 2026-11-21).
- Conversation with the maintainer in German; docs and code in English; site
  content German (Swiss spelling). See CLAUDE.md.
- Every change via branch + PR from `main` (never stacked). Claude merges
  with `gh pr merge <N> --squash --auto` once the checks are green,
  verifies with `gh pr view` and deploys (exceptions that need an OK:
  above). Never pipe `gh` or `git` output.
- Content on the live site lives only in the production database, not in
  git; local data is a playground.
- Privacy principles (brief, section 4) are hard rules.
