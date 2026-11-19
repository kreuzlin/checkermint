# 0016: Demo data for local development, removable despite ADR 0010

- Status: accepted
- Date: 2026-11-19

## Context

Coach and participant views (queue, review, progress) can only be tried by
hand with realistic data: participants, tasks with several versions and
submissions in every state. Creating that in the admin each time is slow.
Fixtures do not fit: they bypass the model guards, would contain password
hashes, and break as the models change.

The data must be removable to start over. ADR 0010 makes published task
versions immutable: `TaskVersion.delete()`, the version `QuerySet` and the
`on_delete` of `TaskVersion.task` refuse to delete them, and tasks with
submissions are archived, never deleted.

## Decision

- A management command `seed_demo` (`submissions/demo.py`) creates the data
  through the normal services (`save_draft`, `submit`, `create_draft`,
  `publish`, `process_photo`), so it goes through the same rules as real
  use. Review fields are set directly until the review form exists.
- It runs only with `DEBUG=true`. Passwords are given on the command line
  or generated and printed, never stored in the repo (CLAUDE.md, Secrets).
  Names are invented; photos are drawn with Pillow.
- Demo rows are recognised by the prefix `demo-` (usernames, task and
  topic slugs) and one badge name. Before seeding, clashes of nicknames,
  topic names or the badge name with other data are reported.
- `--reset` / `--remove` delete only demo rows. For the demo tasks'
  published versions the immutability guard is bypassed on purpose with
  the plain `django.db.models.QuerySet.delete`. If a non-demo account has
  submitted to a demo task, `PROTECT` stops the deletion and nothing is
  removed.
- Extra level thresholds are added only if the table holds nothing but
  level 1, and they are not removed again (the table is shared).

## Consequences

- One command gives a complete local playground; tests check it, so it
  breaks visibly when models change.
- The command has to grow with the features (badges, hint requests).
- ADR 0010 gets a single, development-only exception; the guards stay in
  force everywhere else, including the admin and production.
