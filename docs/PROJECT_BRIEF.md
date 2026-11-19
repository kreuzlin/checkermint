# Checkermint: Project Brief

- Owner: kreuzlin (personal project, run for the VRoboT robotics club)
- Domain: checkermint.ch (apex, no subdomain)
- Created: 2026-11-18, from the planning chat
- Repo: kreuzlin/checkermint, created from kreuzlin/django-template

## 1. Purpose

Checkermint is the training platform of the VRoboT robotics club. Coaches publish tasks ("Aufgaben"), participants submit solutions (text, code, photos, files), coaches review them with 1 to 3 stars and short feedback, and participants collect points, work their way up through levels per topic and earn badges. Every participant can look back at what they have achieved.

"Checkermint" is meant to become a term in the club: "Die Aufgabe liegt auf Checkermint."

There is no deadline. Version 1 starts simple and grows step by step (videos, simulators and more later). The data model must leave room for that.

## 2. Users and roles

- About 10 participants, school children aged 7 to 16
- 4 coaches
- 1 admin (kreuzlin)

| Role | What they can do |
|---|---|
| Participant | See unlocked tasks, request hints, submit and resubmit solutions, see own history, edit own profile and visibility settings, see other participants' internal profiles |
| Coach | Everything a participant can see, plus: create accounts, reset passwords, manage topics, tasks, hints and badges (Django admin), review submissions, grant or decline hint requests, see coach overviews, receive email notifications |
| Admin | Django superuser, everything |
| Public (not logged in, e.g. parents) | Landing page, public profile pages, only what each participant has made public |

Parents get no role and no account. They only see public information.

## 3. Language and terms

- UI language: German only (no i18n in v1, but use Django translation helpers in templates so it stays possible)
- Code, docs, commit messages: English
- UI terms: Aufgabe, Thema, Einreichung, Hinweis (hint), Sterne, Punkte, Level, Badge, Rangliste, Coach, Teilnehmer/in, Spitzname, Profil

## 4. Privacy principles

These are hard rules, not preferences.

1. Process as little personal data as possible.
2. Photos of children are never public. Every uploaded photo and file is private: only logged-in users can access it, and media is served through an authenticated Django view, never from a public `/media/` URL.
3. EXIF metadata (including GPS) is stripped from every image on upload.
4. The real name is stored for internal use only. It is shown to logged-in users and never on any public page.
5. Email address is optional. If present, it is only visible to the user themselves and to coaches.
6. Default visibility: everything private except nickname, avatar, points and levels. Each participant controls what else becomes public.
7. Nothing is indexed by search engines: `robots.txt` disallows everything, every response sends `X-Robots-Tag: noindex, nofollow`, no sitemap.
8. A short privacy page (Datenschutz) and an imprint page explain what is stored and why.
9. Avatars are generated locally on the server. No third-party avatar APIs, no external fonts, no trackers, no analytics.

## 5. Functional scope of version 1

### 5.1 Accounts and profiles

- Coaches create participant accounts (username, nickname, real name, optional email). No self-registration.
- Login with username and password.
- Password reset by email if an email address is stored, otherwise a coach sets a new password.
- Profile fields: nickname (public), real name (internal), avatar, short "about me" text, optional email.
- Visibility settings per participant, with these switches (default in brackets):
  - Nickname, avatar, points and levels per topic (always public)
  - Badges (private)
  - "About me" text (private)
  - List of solved tasks, titles only (private)
- Submission content (text, code, photos, files) is never public in v1.

### 5.2 Avatars

- Robot avatars, randomly generated from a seed stored on the profile.
- The participant can roll a new one ("neuen Roboter würfeln") until they like it.
- Generated locally (SVG). The generator or artwork library must have a license that allows this use; check and record the license in an ADR.

### 5.3 Topics, levels and tasks

- Topics, for example: Code, Konstruktion, Präsentation, Elektronik, Elektrotechnik. Managed in the admin.
- Levels are tracked per topic only. There is no overall level.
- A participant's level in a topic is derived from their points in that topic, using a threshold table (level 1 at 0 points, level 2 at X points, ...). One shared threshold table for all topics in v1, editable in the admin.
- Each task belongs to exactly one topic. A task is split into a stable part and versioned content (see 5.4):
  - Stable (on the task): topic, slug, order, minimum level in its topic (task is locked until the participant reaches it), optional badge (awarded when the task is approved), published / archived flag
  - Versioned (on each task version): title, instructions (Markdown, may include images uploaded by coaches), base points, hints, submission requirements (see 5.6), change note
- Locked tasks are shown greyed out with the required level, so participants see what comes next.
- Tasks that already have submissions are never deleted, only archived.

### 5.4 Task versions

Tasks change over time. A participant who is working on a task must not see it change under their feet, and every solution must record exactly which version was solved.

- **Immutable versions:** Each task has numbered versions (1, 2, 3, ...). A version is a draft while a coach edits it. Once published it can never be changed, not even for a typo. Any change means a new version. This is enforced in the model layer, not only in the admin.
- **Creating a new version:** In the admin, "Neue Version erstellen" copies the latest version, including hints and requirements, into a new draft. The coach edits the draft, adds an optional change note and publishes it. Images used in instructions are stored immutably, so older versions keep displaying correctly.
- **Starting a task pins the version:** When a participant starts a task, a task attempt is created that pins the version that is current at that moment. A task counts as started on the first of: creating a draft submission, requesting a hint, or clicking "Aufgabe starten". Before that, the participant always sees the latest published version.
- **Pinned means stable:** As long as the attempt exists, the participant sees the pinned version: instructions, hints and requirements. This also applies to resubmissions after "needs revision" and to resubmissions after approval to improve the stars.
- **Switching is explicit:** If a newer version exists, the participant sees a discreet notice ("Es gibt eine neuere Version dieser Aufgabe") with the change note. Only if they click "Auf neue Version wechseln" and confirm does the attempt move to the new version. Draft items are carried over where the new version has a requirement with the same key; anything that cannot be carried over is listed in the confirmation before switching.
- **Traceability:** Every submission stores the task version it was made against. The version number is shown unobtrusively on the submission (for example "Version 2" in small print), in the participant's history and in the coach's review form. The review form links to the full content of exactly that version and notes if a newer version exists.
- **Points follow the version:** Points use the base points of the version the best approved submission was made against.
- **Coach view:** The task detail lists all versions with publish date, change note and how many participants are pinned to each version.

### 5.5 Hints

Hints are not self-service: a coach decides whether a participant gets a hint.

- Hints belong to a task version and have an order. Like requirements, each hint has a stable key that is kept when a new version is created.
- The participant sees how many hints a task has, but not their content.
- The participant clicks "Hinweis anfragen" to request the next hint in order, optionally with a short message ("Ich komme beim Motor nicht weiter"). Only one open request per participant and task at a time.
- The request appears in the coach's queue (see 5.10). Any coach can grant or decline it, optionally with a short reply.
- Granted: the hint becomes visible to that participant, together with the coach's reply.
- Declined: the hint stays hidden, the participant sees the reply (for example "Versuch zuerst, die Verkabelung zu prüfen") and can request again later.
- While a request is open, the participant sees "Anfrage wartet auf einen Coach".
- Hints cost no points (the hint may have reached others indirectly anyway).
- All requests and decisions are kept, so coaches can see who asked for and received which hints.
- After switching to a newer task version, hints already granted stay granted where the new version has a hint with the same key. Coaches see the full request history in any case.

### 5.6 Submissions

The core design goal is flexibility: what a solution consists of is defined per task.

- Each task version has a list of requirements. Each requirement has a stable key (kept when a new version is created, used to carry over draft items, see 5.4), a type, a label, whether it is required, and limits (for example min/max number of photos).
- Requirement types in v1: `text`, `code` (pasted text or uploaded file, displayed with syntax highlighting), `photo`, `file`.
- New types (video, simulator result, link, ...) must be addable later without restructuring existing data. Record this design in an ADR.
- Team work is possible in the club, but the platform knows nothing about teams. Every participant who wants points submits their own solution.
- Submission states: `submitted` → `needs_revision` or `approved`.
- A participant can resubmit after `needs_revision`, and also after `approved` to improve their stars. The full history of submissions per task is kept and visible to the participant and the coaches.

### 5.7 Photo upload via QR code

Anyone should be able to take the photos: the participant with their own phone, a friend's phone, or a coach.

- While filling in a submission on any device (laptop, tablet), the page shows a QR code.
- The QR code contains a short-lived, signed link (for example 30 minutes, Django signing) bound to this participant and this task's draft submission.
- Scanning it opens a mobile-friendly upload page that needs no login. Photos uploaded there appear in the draft submission on the other device (htmx polling is enough).
- Coaches can also upload photos and files on behalf of a participant.
- On upload: accept JPEG, PNG and HEIC (convert HEIC), strip EXIF, auto-rotate, resize to a sensible maximum (for example 2000 px long edge), store a thumbnail.
- Enforce a file size limit in both Django and Caddy.

### 5.8 Review, points and badges

- Review form for coaches (custom view with htmx, not the admin): 1 to 3 stars plus short feedback text, then either "approved" or "needs revision" (feedback only, no stars).
- Points for a task = base points of the submission's task version × stars, taken from the best approved submission for that task. Resubmissions can only raise, never lower, a participant's points.
- When a task is approved for the first time and the task has a badge, the participant receives that badge.
- Points and levels are always computed from the data (or cached and recomputed on review), never edited by hand.

### 5.9 Participant views

- Dashboard: levels per topic with progress to the next level, open revisions, recently approved submissions, suggested next tasks.
- Recent badges feed: the latest badges awarded across the club, shown prominently, to keep motivation high for everyone (logged-in users only).
- Task catalogue grouped by topic, showing status per task: open, locked, submitted, needs revision, solved (with stars).
- History: everything the participant has submitted and achieved, in chronological order.
- Ranking per topic, deliberately low-key: a separate page, not on the dashboard or landing page, logged-in users only.

### 5.10 Coach views

1. Queue: everything waiting for a coach, oldest first, with participant, topic, task and waiting time. Two kinds of entries: submissions to review (one click opens the review form) and hint requests (grant or decline directly in the list, with an optional reply, via htmx).
2. Progress matrix: participants as rows, tasks as columns, filterable by topic. Each cell shows the status (solved with stars, submitted, needs revision, open, locked).
3. Participant detail: real name, levels per topic, submission history, hint requests with their outcome, and suggested next tasks (unlocked and not yet solved, lowest minimum level first).
4. Task detail: who has solved it (with the version solved), average stars, how often each hint was requested, granted and declined, and the list of versions with change notes and how many participants are pinned to each.

Task, topic, hint, badge and account management stays in the Django admin as long as that is good enough. A custom coach UI only when complexity demands it.

### 5.11 Email notifications

- Sender: mail@checkermint.ch via the Hostpoint SMTP server.
- To all coaches: when a submission, resubmission or hint request arrives. Each coach can turn this off in their profile.
- To a participant (only if they have an email address): when their submission has been reviewed, and when their hint request has been granted or declined.
- Password reset emails.
- SMTP credentials only in `.env` on the server.

### 5.12 Public area

- Landing page explaining what Checkermint is, with a link to vrobot.ch.
- Public profile pages: `/p/<nickname>/`, showing only what the participant has made public.
- Privacy page and imprint.
- No public task catalogue, no public rankings, no public submission content in v1.

## 6. Out of scope for v1 (later)

- Video submissions, simulators, automatic code testing
- Custom coach UI for managing tasks (beyond the admin)
- Automatic badges (for example level-up badges)
- Teams in the data model
- Email digests instead of single notifications
- Multiple languages
- Moving the repo to a GitHub organisation (when more people contribute)

## 7. Data model sketch

Starting point for Claude Code, to be refined in an ADR.

- `Profile` (one-to-one with User): nickname (unique), real_name, avatar_seed, about, visibility flags, notification settings
- `Topic`: name, slug, order, description
- `LevelThreshold`: level, min_points
- `Badge`: name, description, image
- `Task`: topic, slug, order, min_level, badge (nullable), is_published, is_archived
- `TaskVersion`: task, number, status (draft, published), title, instructions (Markdown), base_points, change_note, created_by, published_at. Immutable once published; unique (task, number)
- `TaskRequirement`: task_version, key, type (text, code, photo, file), label, required, min_count, max_count, order
- `Hint`: task_version, key, text, order
- `HintRequest`: user, task_attempt, hint, message, status (open, granted, declined), coach_reply, decided_by, requested_at, decided_at
- `TaskAttempt`: user, task, task_version (the pinned version), started_at, switched_at; unique (user, task)
- `Submission`: user, task, task_version (protected foreign key, never null), status, stars, feedback, reviewed_by, created_at, submitted_at, reviewed_at
- `SubmissionItem`: submission, requirement, text, file, thumbnail
- `UserBadge`: user, badge, task, awarded_at
- Upload tokens for the QR flow: signed values via `django.core.signing`, no table needed

## 8. Deviations from django-template

1. User accounts with roles (participant, coach via a Django group, admin).
2. Private media: uploads stored in a Docker volume, served only through an authenticated view. Caddy must not serve that volume directly.
3. Backups must include the media volume, not only `pg_dump`. Backup and restore of database and media are tested before go-live.
4. Image processing: Pillow plus HEIC support (for example pillow-heif).
5. Outgoing email via SMTP (Hostpoint).
6. htmx for the review form, hint request decisions in the coach queue, QR upload status and request status updates.
7. SEO basics from the template are inverted: noindex everywhere, no sitemap.
8. Markdown rendering with sanitising for task instructions and feedback.
9. Upload size limits in Django settings and in the Caddyfile.

## 9. Hosting, domain and mail

- New dedicated UpCloud server (for example 2 cores, 2 GB RAM, 30 GB), Ubuntu 26.04 LTS, Caddy with automatic HTTPS. Watch disk usage because of photos; this can be extended later.
- The platform runs on the apex domain checkermint.ch, with www redirecting to the apex.
- Only the records for `checkermint.ch` and `www.checkermint.ch` change. All other existing DNS records of the domain, in particular other subdomains and all mail records (MX, SPF, DKIM, DMARC), must not be touched. Before changing anything, list the current records and show them to kreuzlin.
- Mail for the domain is at Hostpoint. Check that SPF allows Hostpoint to send for checkermint.ch and that DKIM is set up.
- Secrets only in `.env` on the server.

## 10. Suggested milestones

Each milestone becomes a set of small GitHub issues, one issue per PR.

1. **Setup:** docs/NEW_PROJECT.md, GitHub settings, placeholders, ADRs for task versioning, the submission model and private media.
2. **Accounts and profiles:** roles, coach-created accounts, login, password reset, profile with visibility settings, avatars.
3. **Topics and tasks:** models, task versions (immutable, admin workflow for new versions), task attempts with pinned versions, task catalogue with lock status.
4. **Submissions:** requirement types, submission form linked to the pinned version, switching to a newer version, private media, image processing, history.
5. **QR upload:** signed links, mobile upload page, live update of the draft.
6. **Review and progress:** coach queue, review form, points, levels, badges, dashboard, recent badges feed.
7. **Hint requests:** request, entry in the coach queue, grant or decline with reply, carry-over on version switch.
8. **Coach overviews:** progress matrix, participant detail, task detail.
9. **Email:** SMTP, notifications (submissions, reviews, hint requests and decisions), notification settings.
10. **Public area:** landing page, public profiles, privacy page, imprint, noindex, per-topic ranking page.
11. **Go-live:** server, DNS (apex only), mail check, backup and restore test (database and media), rollback test, assets (logo, badges) delivered as original files.

Migrations and server or deployment changes are merged by kreuzlin, as usual.

## 11. Open decisions (proposed defaults)

Claude Code may proceed with these defaults; kreuzlin can override them at any time.

| Topic | Proposed default |
|---|---|
| Password rules for young children | Django default validators, minimum length relaxed to 6 for participants |
| Session length | Long sessions (for example 30 days) on personal devices, "remember me" checkbox |
| QR link lifetime | 30 minutes |
| Level thresholds | Same table for all topics, set in the admin |
| Badge and logo artwork | Placeholders until kreuzlin delivers original files. Claude Code never generates or recreates artwork itself. Artwork that kreuzlin delivers may have been made with AI tools (decision 2026-11-19, first case: the logo); source and tool are recorded in `design/README.md` |
| Notifications to coaches | Immediate email per submission, can be turned off per coach |
| Coach forcing a version switch | Not possible; only the participant switches. A coach can recommend it in the feedback |
| Draft task versions | Visible only to coaches, with a preview of how participants will see them |

## 12. Instructions for the first Claude Code session

1. Work through docs/NEW_PROJECT.md: do the GitHub settings and placeholders yourself, create issues for kreuzlin for server, DNS, mail and assets.
2. Copy this brief to docs/PROJECT_BRIEF.md and reference it from CLAUDE.md and docs/STATUS.md.
3. Write ADRs for: task versioning and pinning, flexible submission requirements, private media serving, avatar generation (including license), points and level calculation.
4. Create GitHub issues for version 1 following section 10, small enough for one PR each.
5. Show the plan. Do not build features yet.
