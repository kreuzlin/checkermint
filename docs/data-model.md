# Data model

One section per app with its models, fields and rules (visibility, ordering,
retention). Keep this file in sync with every model change. Planned models
for version 1: brief, section 7; decisions in ADRs 0010–0013.

## Roles (`accounts.roles`)

| Role | How it is represented |
|---|---|
| Participant | Active user, `is_staff = False`, with a `Profile` |
| Coach | Active user, `is_staff = True`, member of the group "Coach" (never a superuser) |
| Admin | Superuser |

`is_coach(user)` checks this (superusers count as coaches). The group
"Coach" and its permissions are defined in `COACH_PERMISSIONS` and applied
by data migrations calling `sync_coach_group` (`accounts/0002`, `0003`).

Current coach permissions (`COACH_PERMISSIONS`): users view/add/change,
profiles view/add/change; topics, level thresholds and badges
view/add/change/delete; tasks, versions, requirements, hints and
instruction images view/add/change/delete (published versions stay
immutable through the model guards); submissions and their items view
only (`submissions/0002`).
No delete: accounts are deactivated (`is_active`). The user admin
(`accounts.admin.UserAdmin`) restricts coaches to participant accounts:

- list, change and password pages only for users with `is_staff = False`
  and `is_superuser = False`;
- the add form creates the account (username, password, optional email)
  and its profile in one step; the profile is required;
- staff, superuser, group and permission fields are never shown, and
  `save_model` forces `is_staff = False`, `is_superuser = False`;
- the profile admin is a list of participant profiles without "add".

Superusers keep Django's full user admin (plus the profile inline, optional
for them).

## accounts

### Profile

One-to-one with `auth.User` (`user.profile`). The email address is the
optional `User.email`; it is visible only to the user and to coaches.

| Field | Type | Rules |
|---|---|---|
| `user` | OneToOne → User, cascade | fixed once created |
| `nickname` | char 30 | public; 2–30 letters/digits/`-`/`_`, starts with a letter or digit, no spaces; unique, also case-insensitively (`Lower(nickname)` constraint); used in `/p/<nickname>/` |
| `real_name` | char 100 | internal: only shown to logged-in users, never on public pages |
| `avatar_seed` | char 32 | random hex (`secrets.token_hex(8)`), input for the Robohash avatar (ADR 0012); re-rolled by the participant |
| `about` | text, optional | Markdown, rendered with the `markdown` filter |
| `show_badges` | bool, default `False` | public profile shows badges |
| `show_about` | bool, default `False` | public profile shows "Über mich" |
| `show_solved_tasks` | bool, default `False` | public profile lists titles of solved tasks |
| `email_notifications` | bool, default `True` | only effective with an email address (brief 5.11) |
| `created_at`, `updated_at` | datetime | automatic |

Always public: nickname, avatar, points and levels per topic. Submission
content is never public. Default ordering: nickname, case-insensitive.

## tasks

### Topic

| Field | Type | Rules |
|---|---|---|
| `name` | char 50, unique | e.g. Code, Konstruktion |
| `slug` | slug 50, unique | prefilled from the name in the admin |
| `order` | small int, default 0 | catalogue order (then name) |
| `description` | text, optional | Markdown |

### LevelThreshold

One shared table for all topics (ADR 0013); a participant's level in a topic
is the highest level whose `min_points` their points in that topic reach
(`tasks.levels.level_for_points`).

| Field | Type | Rules |
|---|---|---|
| `level` | small int ≥ 1, unique | fixed once created; no gaps |
| `min_points` | int ≥ 0, unique | level 1 is always 0, all other levels > 0; strictly increasing with the level |

Level 1 at 0 points is created by migration `tasks/0002` and cannot be
deleted; only the highest level can be deleted (no bulk delete).

### Task

The stable part of a task (brief 5.3, ADR 0010); everything participants
read or fulfil lives in its versions.

| Field | Type | Rules |
|---|---|---|
| `topic` | FK → Topic, protect | exactly one topic |
| `slug` | slug 60, unique | stays when the title changes |
| `order` | small int, default 0 | order within the topic |
| `min_level` | small int ≥ 1, default 1 | locked until this level in the topic is reached |
| `badge` | FK → Badge, optional, protect | awarded on the first approval |
| `is_published` | bool, default `False` | visible to participants; needs a published version |
| `is_archived` | bool, default `False` | hidden from the catalogue, points and history stay |
| `created_at` | datetime | automatic |

`str(task)` is the title of the latest published version (else the slug).
Deleting a task is refused while it has a published version
(`on_delete=protect_published_versions`); drafts are deleted with it.

### TaskVersion

| Field | Type | Rules |
|---|---|---|
| `task` | FK → Task | see above |
| `number` | small int | 1, 2, 3, … per task, set automatically; unique per task |
| `status` | `draft` / `published` | at most one draft per task (partial unique constraint) |
| `title` | char 120 | |
| `instructions` | text | Markdown |
| `base_points` | small int ≥ 1, default 10 | points = base points × stars (ADR 0013) |
| `change_note` | char 200, optional | shown to participants when switching |
| `created_by` | FK → User, optional, set null | |
| `created_at` | datetime | automatic |
| `published_at` | datetime, optional | set if and only if published (check constraint) |

**Immutability (ADR 0010), enforced in the model layer:** once the stored row
is published, `save()` and `delete()` raise `PublishedVersionError`; the
only allowed transition is `publish()` (draft → published, needs at least
one requirement). The `QuerySet` refuses `update()` and `delete()` when
published versions are included.

### TaskRequirement (ADR 0011) and Hint

Both belong to a version (`task_version`, cascade with drafts) and have a
`key` (slug 50, unique per version, kept across versions) and an `order`.
Their `save()`, `delete()` and the `QuerySet`'s `update()`, `delete()` and
`bulk_create()` raise `PublishedVersionError` for published versions (also
when moving a row out of one).

| TaskRequirement field | Type | Rules |
|---|---|---|
| `type` | `text` / `code` / `photo` / `file` | behaviour comes from a handler per type (later) |
| `label` | char 100 | |
| `help_text` | char 300, optional | |
| `required` | bool, default `True` | required → `min_count` ≥ 1 |
| `min_count`, `max_count` | small int, default 1 | `min_count` ≤ `max_count`, `max_count` ≥ 1 |
| `options` | JSON object, default `{}` | type-specific settings, validated by the handler |

| Hint field | Type | Rules |
|---|---|---|
| `text` | text | Markdown |

### InstructionImage

Images for the instructions of a task, shared by its versions (ADR 0010),
stored privately (ADR 0009).

| Field | Type | Rules |
|---|---|---|
| `task` | FK → Task, cascade | |
| `image` | image | `anleitungen/<uuid>.jpg` or `.png`; re-encoded on upload by `core.images.process_image` (no EXIF/GPS, max. 2000 px, JPEG/PNG/WebP in, max. 10 MB) |
| `width`, `height` | int | set from the stored file |
| `alt_text` | char 200 | required |
| `original_filename` | char 200 | shown on download only |
| `uploaded_by` | FK → User, optional, set null | |
| `created_at` | datetime | automatic |

Referenced in Markdown as `![…](bild:<id>)` (the admin shows the code to
copy); only images of the same task are rendered
(`instructions_markdown` filter), everything else shows "[Bild fehlt]".
Once saved, the file is never replaced; while a published version
references an image, it cannot be changed or deleted. Served at
`/dateien/anleitungsbild/<id>/`: coaches always, other logged-in users
only if a published version of a visible, not archived task uses it.

### TaskAttempt

A participant has started a task; the attempt pins the version they see
(brief 5.4, ADR 0010).

| Field | Type | Rules |
|---|---|---|
| `user` | FK → User, cascade | |
| `task` | FK → Task, protect | unique together with `user` |
| `task_version` | FK → TaskVersion, protect | a published version of `task` (checked in `save()` and `clean()`) |
| `started_at` | datetime | default now |
| `switched_at` | datetime, optional | last explicit switch to a newer version (#26) |

Helpers in `tasks.attempts`: `visible_version(user, task)` returns the
pinned version, or the latest published version without an attempt;
`start_attempt(user, task)` creates the attempt with the latest published
version (idempotent, safe against double clicks; refuses hidden, archived
or unpublished tasks). It is called by "Aufgabe starten" (#20), the first
draft submission (#23) and the first hint request (#36); the level lock is
checked by the caller. The admin's version list on a task shows how many
participants are pinned to each version.

## badges

### Badge

| Field | Type | Rules |
|---|---|---|
| `name` | char 60, unique | |
| `description` | char 200, optional | what the badge is for |
| `image` | char 100, optional | file name in `badges/static/badges/img/`; empty = neutral placeholder |
| `created_at` | datetime | automatic |

Badge artwork is a **static asset**, not an upload: badges can appear on
public profiles, while uploads are always private (ADR 0009). Originals go
to `design/` with their source and rights (#4); the web files are added to
`badges/static/badges/img/` by a PR. Artwork is never generated by AI.
Awarding (`UserBadge`) follows with reviews (M6).

## submissions

### Submission

A participant's solution to a task, made against exactly one published
version (brief 5.6, ADR 0010).

| Field | Type | Rules |
|---|---|---|
| `user` | FK → User, cascade | |
| `task` | FK → Task, protect | tasks with submissions are archived, never deleted |
| `task_version` | FK → TaskVersion, protect | a published version of `task`; fixed at creation, like `user` and `task` (checked in `save()`) |
| `status` | `draft`, `submitted`, `needs_revision`, `approved` | at most one `draft` per user and task (partial unique constraint) |
| `stars` | 1–3, optional | set if and only if `approved` (check constraint) |
| `feedback` | text, Markdown | the coach's feedback |
| `reviewed_by` | FK → User, set null | |
| `created_at` | datetime | automatic |
| `submitted_at` | datetime, optional | set if and only if not `draft` (check constraint) |
| `reviewed_at` | datetime, optional | set if and only if `needs_revision` or `approved` (check constraint) |

A resubmission is a new row; the full history per task stays (brief 5.6).
Points use the best approved submission (ADR 0013, #33).

### SubmissionItem (ADR 0011)

One value of a submission: a text, a code snippet, one photo, one file.

| Field | Type | Rules |
|---|---|---|
| `submission` | FK → Submission, cascade | |
| `requirement` | FK → TaskRequirement, protect | a requirement of the submission's version (checked in `save()`); its type is the item's type |
| `order` | small int | e.g. the order of several photos |
| `text` | text | text and pasted code |
| `file` | file, optional | private (ADR 0009), stored as `einreichungen/<uuid>.<ext>` |
| `original_filename` | char 200 | for display and download |
| `thumbnail` | file, optional | `einreichungen/vorschau/<uuid>.<ext>` |
| `data` | JSON | structured values of future types only |
| `created_at` | datetime | automatic |

Items can only be added, changed or deleted while the submission is a
draft (`save`, `delete` and QuerySet guards raise
`SubmissionLockedError`); afterwards only the review fields of the
submission change. Deleting an item deletes its files. Serving the files
(`PrivateFileKind`, owner and coaches) comes with photo and file
requirements (#24). The admin shows submissions read-only to coaches.
