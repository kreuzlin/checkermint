# Architecture

Overview of how the project is built and run. Decisions and their rationale:
[`decisions/`](decisions/). Operations: [`deployment.md`](deployment.md).

## Code

| Path | Purpose |
|---|---|
| `config/` | Settings (one module, configured via environment), URLs, WSGI |
| `core/` | Base layout, home page, private file view (`core/private_files.py`, `/dateien/…`), SEO (`core/seo.py`), noindex middleware, Markdown rendering (`core/markdown.py`, `markdown` template filter), navigation, `/version`, `/robots.txt`, error pages |
| `accounts/` | Profiles, roles (`is_coach`, group "Coach"), login/logout (`/anmelden/`, `/abmelden/`), password reset by email (`/passwort-vergessen/`), own profile (`/profil/`), internal profiles (`/teilnehmende/`), public profiles (`/p/<nickname>/`, `accounts.public`), robot avatars (`accounts/avatars.py`, `/avatar/<seed>-<size>.png`), password rules |
| `tasks/` | Topics, shared level table (`LevelThreshold`, `tasks.levels.level_for_points`; points from `submissions.progress`), tasks with immutable versions, requirements and hints (guards in the model layer, ADR 0010/0011), task attempts (`tasks.attempts`), catalogue `/aufgaben/` and task page `/aufgaben/<slug>/` (`tasks.catalogue`) |
| `hints/` | Hint requests (`HintRequest`, `hints.services`): "Hinweis anfragen" on the task page (POST `/aufgaben/<slug>/hinweis-anfragen/`), granted hints with replies; grant or decline in the coach queue (POST `/warteschlange/hinweis/<id>/`); read-only admin for coaches |
| `overviews/` | Coach overviews (no models): progress matrix `/fortschritt/` (`overviews.matrix.progress_matrix`, "Fortschritt" in the navigation, coaches only), participant detail `/fortschritt/teilnehmende/<nickname>/` (`overviews.participant`), task detail `/fortschritt/aufgaben/<slug>/` (`overviews.task`) |
| `notifications/` | Email notifications (no models): `notifications.emails` with templates in `notifications/templates/notifications/email/` |
| `badges/` | Badges with static artwork (`badges/static/badges/img/`) or a placeholder; awards (`UserBadge`, `badges.awards`: `award_for`, `recent_badges`, `badges_of`) |
| `submissions/` | Submissions against a pinned task version and their items (ADR 0010/0011); items locked once submitted; requirement handlers (`submissions/handlers.py`), submission form `/aufgaben/<slug>/loesung/`, version switch `/aufgaben/<slug>/wechseln/`, history `/verlauf/` (`submissions.history`), coach queue `/warteschlange/` (`submissions.queue`), review form `/warteschlange/<id>/`, phone upload `/hochladen/<token>/` (`submissions.upload_links`); read-only admin for coaches |
| `<app>/` | One small Django app per topic (added per project) |

- Every public view sets title and meta description via `core.seo.SeoMixin`;
  `base.html` renders `<title>` and description. Nothing is indexed:
  `core.middleware.NoIndexMiddleware` sends `X-Robots-Tag: noindex, nofollow`
  on every response, `/robots.txt` disallows everything, `base.html` adds
  `<meta name="robots" content="noindex, nofollow">`; no canonical, Open
  Graph or sitemap.
- Sessions: "Angemeldet bleiben" keeps the session for 30 days
  (`SESSION_COOKIE_AGE`); without it the session ends when the browser
  closes (shared devices in the club). Logout is POST only.
- Passwords: `accounts.password_validation.RoleMinimumLengthValidator`
  (participants 6, staff 8 characters) plus Django's similarity, common and
  numeric validators.
- Profiles: participants edit their about text, optional email address,
  visibility switches and notifications on `/profil/`; nickname and real
  name are changed by coaches in the admin. Logged-in users see the
  internal directory `/teilnehmende/` and internal profiles (real name and
  about text, regardless of the switches, which only control the public
  page `/p/<nickname>/`, #46). The email address is shown only to the
  participant and to coaches. Inactive and staff accounts are not listed.
- Public profiles (#46, brief 4.6, 5.12): `/p/<nickname>/` without login
  (active participants only, otherwise 404). `accounts.public` builds a
  `PublicProfile` with nickname, avatar seed and level/points per topic
  (topics with visible tasks; points as everywhere, ADR 0013); about text,
  badges (name, description, date – not the task) and titles of solved
  visible tasks are loaded only when the matching switch is on, so the
  template cannot show a private part by mistake. Never the real name,
  email, username, feedback or submission content. Not linked from any
  public page: participants share the link themselves ("So sieht dein
  öffentliches Profil aus" on `/profil/`, also on the internal profile).
- Avatars (ADR 0012): Robohash set1 rendered locally as PNG in 64, 128 or
  256 px, only for seeds of existing profiles, kept in an in-process LRU
  cache and sent with `Cache-Control: public, max-age=1 year, immutable`
  (a new seed is a new URL). "Neuen Roboter würfeln" (POST
  `/profil/roboter-wuerfeln/`) sets a new seed. The footer credits the
  CC-BY artwork; a snapshot test of a few seeds guards package upgrades.
- Task versions in the admin (ADR 0010): the task page lists all versions
  and has "Neue Version erstellen" (`Task.create_draft`: copies the latest
  published version with requirements and hints, keys kept; at most one
  draft). Drafts are edited with requirement and hint inlines, checked with
  "Vorschau" (site layout, `tasks/_version_content.html`, shared with the
  task page) and published after a confirmation step. Published
  versions are view-only; versions are not listed on the admin index.
  The pinned count per version follows with task attempts (#19).
- Task catalogue (#20, logged-in users only): `tasks.catalogue.catalogue`
  groups visible tasks (published, not archived) by topic with a status per
  task: `eingereicht` (latest submission waits for a coach), `geloest`
  (any approved submission, with the best stars), `ueberarbeiten` (needs
  revision), `begonnen` (attempt exists), `offen` or `gesperrt`
  (participant's level in the topic below `min_level`; coaches see no
  locks; a started task stays unlocked). Levels come from
  `submissions.progress` (see "Points and levels"). Locked tasks
  are listed without a link; their page shows only the title and the
  required level. The task page shows the version from
  `tasks.attempts.visible_version` and the number of hints (not their
  text; participants see the hints granted to them and can request the
  next one, see `docs/data-model.md`, hints); "Aufgabe starten" (POST `/aufgaben/<slug>/starten/`) calls
  `start_attempt`. Coaches see the latest version and cannot start tasks.
  Below the instructions the participant sees their own submissions with
  status, stars, feedback and "Version N".
- Submissions (#23, ADR 0011): every requirement type has a handler in
  `submissions.handlers` (form fields, validation into item dicts,
  completeness, display template); `SubmissionForm` builds its fields from
  the version's requirements, `submissions.services` saves the draft
  (starting the task, at most one draft) and submits it. "Entwurf
  speichern" stores without completeness checks, "Einreichen" saves and
  then submits only if every required part is there. While a submission
  waits for a coach there is no new draft; after a review the next draft
  starts from the last submission's content. `text` is plain text
  (escaped, line breaks kept); `code` is pasted or uploaded as a UTF-8
  text file (max. 200 KB, stored as text with the original file name, no
  file kept) and highlighted with Pygments (style `one-dark` on the site's dark
  code background, all colours WCAG AA; CSS generated into `submissions/static/submissions/css/code.css`,
  the command is in the file). Requirement `options` for code:
  `language` (Pygments name) and `extensions` (allowed endings). A type
  without a handler is shown as "Kommt bald"; a version that requires one
  can only be saved as a draft.
- Photos and files (#24): several per input up to `max_count`; stored
  items stay in the draft until "Entfernen" is ticked, and a resubmission
  starts with copies of the last submission's items. Photos go through
  `core.images.process_photo` (JPEG, PNG, WebP, HEIC via `pillow-heif`;
  auto-rotate, metadata dropped, 2000 px plus a 400 px thumbnail). Files
  are kept as uploaded, optionally limited by `options.extensions`. Size
  limits per file: `UPLOAD_MAX_PHOTO_MB` (15) and `UPLOAD_MAX_FILE_MB`
  (20) from `.env`. Caddy limits the whole request
  (`UPLOAD_MAX_REQUEST_MB`, default 100, `request_body` in
  `deploy/Caddyfile`, German 413 message); the startup check
  `submissions.W001` warns if it is smaller than a file limit.
- Version switch (#26, ADR 0015): if the attempt pins an older version than
  the latest published one, the task page and the form show "Es gibt eine
  neuere Version dieser Aufgabe" with the change note.
  `/aufgaben/<slug>/wechseln/` shows the change notes of all newer versions
  and what of the draft is carried over or lost
  (`submissions.switching.plan_switch`); the POST switches only to the
  confirmed version (`switch_version`), replacing the draft with one on the
  new version. The confirmation also lists granted hints that stay
  granted and those the new version no longer has
  (`hints.services.plan_carry_over`, #38); an open hint request for a hint
  the new version no longer has blocks the switch until a coach decided
  it.
- Phone upload (#28, brief 5.7): with a draft and photo or file
  requirements, the form shows a QR code (`segno`, inline SVG, generated
  locally) for `/hochladen/<token>/`. The token is signed with Django's
  signing (`submissions.upload_links`, salt `submissions.upload-link`),
  holds submission and user id, is valid 30 minutes and only while that
  submission is still the participant's draft. The page needs no login,
  shows only the task title and requirement labels (no names, no
  thumbnails), sends `no-referrer`, and only adds photos/files (same
  handlers and image pipeline, `max_count` respected); invalid or expired
  links answer 410.
- Live update (#29): with a draft, the form loads htmx (vendored, see
  [`vendored-assets.md`](vendored-assets.md)) and every stored-items block
  of a photo/file requirement polls
  `/aufgaben/<slug>/loesung/gespeichert/<key>/?stand=<ids>` every 5 s. The
  server answers 204 if the item ids are unchanged, the new block (keeping
  ticked "Entfernen" boxes) if not, and 286 (htmx stops polling) when
  there is no draft any more or the user may not see it.
- Coach uploads (#30): the participant profile links coaches to
  `/teilnehmende/<nickname>/hochladen/` (tasks with photo/file
  requirements and the participant's status) and
  `/teilnehmende/<nickname>/hochladen/<slug>/` (same upload fields as the
  phone page). The first upload creates the participant's draft
  (`submissions.services.ensure_draft`: starts the task, starts from the
  last submission like the form); locked tasks and waiting submissions are
  refused. The participant submits. Coach views use
  `accounts.mixins.CoachRequiredMixin` (login, then 403 for non-coaches).
  Items do not record who uploaded them.
- Coach queue (#31): `/warteschlange/` ("Warteschlange" in the
  navigation, coaches only: `NavItem(coaches_only=True)`) lists
  `submissions.queue.queue_entries()`: two kinds of entries of active
  participants, merged and sorted by waiting time, oldest first, each
  with participant (nickname and real name), topic, task, version and
  waiting time:
  - submitted, unreviewed submissions with an "erneut eingereicht"
    marker, linking to the review form (`submission_entries()`; "Nächste
    Lösung" in the review form only looks at these);
  - open hint requests (#37, `hint_request_entries()`) with the
    participant's message, the requested hint's text, an optional reply
    and "Freigeben" / "Ablehnen" (POST `/warteschlange/hinweis/<id>/`,
    `hints.views.DecideHintView`). With htmx only the entry is replaced
    (`hints/_queue_entry.html`); without JavaScript the page redirects to
    the queue with a message. A request decided by another coach in the
    meantime shows that decision and an error.
  The coach home page counts both kinds.
- Progress matrix (#39, brief 5.10.2): `/fortschritt/` for coaches,
  active participants (rows, by nickname, with real name) × visible tasks
  (columns, by topic and order, with minimum level), filter `?thema=<slug>`
  (then also the level in that topic). Cells use the participant's own
  catalogue rules (`tasks.catalogue.task_state`) and say the status in
  words; solved shows the best stars. A fixed number of queries
  (attempts, non-draft submissions and points per user and topic are
  each loaded once). The table scrolls sideways inside its box; the first
  column stays visible.
- Participant detail (#40, brief 5.10.3):
  `/fortschritt/teilnehmende/<nickname>/` for coaches, linked from the
  matrix rows and the internal profile. Real name, level per topic and
  suggested next tasks come from the participant's own catalogue
  (`tasks.catalogue.catalogue`, `submissions.dashboard.suggested_tasks`:
  started first, then open by minimum level, at most 5). All non-draft
  submissions (also of archived tasks) newest first with status, stars,
  points, feedback and a link to the review page; all hint requests with
  message, outcome, reply and the requested hint. Participants get 403;
  staff, inactive or unknown nicknames 404.
- Task detail (#41, brief 5.10.4): `/fortschritt/aufgaben/<slug>/` for
  coaches, linked from the matrix column headers and the task page (also
  for archived and unpublished tasks). Solvers: the best approved
  submission per active participant (most stars, then earliest), with its
  version and a link to the review page; the average is taken over these
  best stars. Hint statistics per hint key over all versions (requested,
  granted, declined, open), labelled with the newest version that has the
  key. Versions newest first with status, publish date, change note and
  pinned participants (all attempts, like the admin).
- Ranking per topic (#48, brief 5.9): `/rangliste/?thema=<slug>`, logged-in
  users only, linked only at the bottom of the catalogue (not from the
  navigation, dashboard or landing page). `submissions.ranking`: active
  participants with points in the topic, most points first, equal points
  share a rank; nicknames only, the own row is marked "(du)"; others
  without points are only counted. Default topic: the first one.
- Points and levels (#33, ADR 0013): `submissions.progress` computes
  everything from approved submissions, nothing is stored.
  `points_by_task` / `task_points`: the best `base_points × stars` per
  task (base points of the submission's own version), so resubmissions
  never lower points; archived or hidden tasks keep their points.
  `points_by_topic` (one query), `levels_by_topic` (plus the threshold
  table: `tasks.levels.LevelInfo` with level, points and points missing),
  `topic_progress` (every topic, for the dashboard #35). The catalogue
  shows level, points and a progress bar per topic
  (`tasks/_topic_level.html`, text first, the bar only repeats it); the
  task page shows the participant's points for the task.
- Privacy page `/datenschutz/` and imprint `/impressum/` (#47, brief
  4.8): static templates in `core`, linked in the footer. Operator name and
  privacy contact come from `settings.CLUB_NAME` / `PRIVACY_EMAIL` (context
  processor); the imprint repeats the avatar credits (ADR 0012). When what
  is stored, who sees it or a processor changes, update the privacy page
  and `core.views.PRIVACY_UPDATED` in the same PR.
- Home page (#35): visitors see the landing page (#45,
  `core/_landing.html`: what Checkermint is, how it works, who can take
  part with a link to vrobot.ch, a note for parents on what is public;
  no images and no participant data). Logged-in participants see their dashboard
  (`submissions.dashboard`, template `submissions/dashboard.html`):
  "Überarbeiten" (tasks whose latest submission needs revision, with the
  feedback), "Als Nächstes" (started tasks first, then open ones with the
  lowest `min_level`, at most 4), levels per topic (the catalogue
  sections, so statuses and levels agree), "Zuletzt angenommen" (5, with
  points) and the badge feed; a note when solutions wait for a coach.
  Coaches see the number of waiting solutions with a link to the queue
  and the badge feed. 13 queries for a participant (tested).
- Badges (#34, ADR 0013): approving a submission of a task with a badge
  creates a `UserBadge` (once per user and badge) in the same transaction
  as the review; the review block says "Badge … vergeben". Shown in the
  feed "Neue Badges im Club" on the home page (logged-in users only,
  latest 8, inactive accounts left out), on the internal profile and as
  an event in the history. The icon is decorative (`alt=""`); the name is
  always text. Placeholder without artwork: a star in a circle.
- Review form (#32): `/warteschlange/<id>/` (coaches only; the submission
  is looked up after the permission check, so participants always get
  403). Shows the solution, a link to the admin preview of the exact
  version, a note if a newer version exists, and earlier submissions.
  `ReviewForm`: stars (radio), feedback (Markdown), the clicked button
  decides: "Annehmen" needs 1–3 stars, "Überarbeitung nötig" needs
  feedback and drops stars. `services.review_submission` locks the row
  and refuses submissions that are no longer waiting (two coaches at
  once). With htmx (`HX-Request`) only the `#bewertung` block is replaced
  and offers the next waiting submission; without JavaScript the form
  posts normally and redirects to the queue with a message.
- Private uploads (ADR 0009): models store files with
  `core.private_files.RandomUploadPath` (UUID names) and register a
  `PrivateFileKind` (owner model, file getter, access check, inline or
  download). `/dateien/<kind>/<pk>/[<variant>/]` loads the object, checks
  access and streams the stored file; no access, unknown objects or missing
  files all answer 404. Headers: `Cache-Control: private, no-store` (unless
  the kind says otherwise), `nosniff`, downloads as
  `application/octet-stream` attachments; inline only for images we
  re-encoded, with a sandboxing CSP. Registered kinds: `anleitungsbild`
  (instruction images, `tasks.apps`), `einreichungsfoto` and
  `einreichungsdatei` (submission items, `submissions.apps`).
- Images on upload: `core.images.process_image` decodes (JPEG, PNG, WebP,
  HEIC), applies the EXIF orientation, drops all metadata, limits to
  2000 px and re-encodes (JPEG, or PNG with transparency);
  `process_photo` also makes a thumbnail from the same decode. Markdown images are only allowed when the
  caller passes the allowed images (`core.markdown.render_markdown(text,
  images=…)`); external and unknown images never render.
- Navigation entries can be `members_only` (`core.navigation.NavItem`).
- Password reset: Django's flow with German templates
  (`accounts/templates/accounts/`). Only active users with a stored email
  address get a link (valid `PASSWORD_RESET_TIMEOUT`, 3 days, single use);
  the confirmation page looks the same for unknown addresses. Without an
  email address a coach sets a new password in the admin. Emails go to the
  console until SMTP is configured (#3, M9).
- Email notifications (#43, brief 5.11): `notifications.emails`. Coaches
  get a mail on every submission ("Neue Lösung" / "Erneut eingereicht",
  with a link to the review page) and every hint request (with the
  message, link to the queue). Recipients (`coach_recipients`): active
  coaches and superusers with an email address, unless their profile
  turns `email_notifications` off (no profile: on). Sent after the
  transaction commits, one message per recipient, links built from the
  triggering request (no site-address setting); a mail server error is
  logged and never breaks the action. Only nicknames, never real names.
- `/version` returns the Git commit of the running image as JSON
  (`APP_COMMIT`, set by CI); local builds report `dev`.

## Runtime

```
Browser ──HTTPS──▶ caddy ──▶ web (Gunicorn + Django, WhiteNoise for /static/)
                                    │
                                    ├── media volume (private uploads)
                                    └── db (PostgreSQL)
```

- **caddy**: TLS (Let's Encrypt), security headers (incl. a fixed
  `X-Robots-Tag: noindex, nofollow`), redirects of extra host names. No
  access to uploaded files.
- **web**: the image from GHCR, built by CI for `linux/amd64`. Static files
  are collected at build time and served by WhiteNoise. Uploaded files live
  in the `media` volume, mounted only here, and are served by Django after
  an access check (ADR 0009) – never from a public `/media/` URL.
- **db**: PostgreSQL 18, data in the `postgres_data` volume.

## Delivery

1. Pull request → CI: Ruff, `manage.py check`, missing-migration check,
   tests, image build (no push).
2. Merge to `main` → CI pushes `ghcr.io/kreuzlin/checkermint:latest` and
   `:sha-<commit>`.
3. `scripts/deploy.sh` on the server pulls the image, runs migrations and
   restarts the containers.

## Backups

Nightly `pg_dump` (`scripts/backup-db.sh`) followed by the UpCloud disk
backup (ADR 0008).
