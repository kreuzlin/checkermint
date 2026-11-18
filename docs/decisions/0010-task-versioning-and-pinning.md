# 0010: Immutable task versions, pinned per participant

- Status: accepted
- Date: 2026-11-18

## Context

Coaches improve tasks over time: clearer instructions, other points, an
extra hint, a different set of required photos. A participant who is
working on a task must not see it change under their feet, and every
submission must record exactly what was asked (brief, section 5.4).

## Decision

**Split a task into a stable part and versions.**

- `Task`: what identifies the task and never needs versioning – topic, slug,
  order, minimum level, optional badge, published and archived flags.
- `TaskVersion`: everything participants read or fulfil – title,
  instructions (Markdown), base points, change note – plus its child rows
  `TaskRequirement` (ADR 0011) and `Hint`. Numbered per task
  (`unique (task, number)`), status `draft` or `published`, `published_at`,
  `created_by`.

**Published versions are immutable, enforced in the model layer.**

- `TaskVersion.save()` and `delete()` raise if the stored row is published
  (the only allowed write is the draft → published transition itself).
  The same guard applies to `TaskRequirement` and `Hint` via their version.
- A custom `QuerySet` refuses `update()` and `delete()` on querysets that
  contain published versions, so bulk operations cannot bypass the guard.
- The admin shows published versions read-only; tests cover the model guard
  independently of the admin.
- At most one draft per task. "Neue Version erstellen" copies the latest
  version with its requirements and hints into a new draft (number + 1),
  keeping their `key`s.
- Images in instructions are separate immutable rows (`InstructionImage`)
  referenced from the Markdown; they are never replaced or deleted while a
  published version uses them, so old versions keep rendering.

**A task attempt pins the version.**

- `TaskAttempt (user, task, task_version, started_at, switched_at)`,
  `unique (user, task)`. It is created on the first of: "Aufgabe starten",
  first draft submission, first hint request – always with the latest
  published version at that moment.
- Without an attempt, a participant sees the latest published version. With
  an attempt, they see the pinned version everywhere (instructions, hints,
  requirements), including after "needs revision" and when resubmitting to
  improve stars.
- **Switching is explicit and done by the participant only.** If a newer
  published version exists, a notice with the change note is shown.
  Switching updates `task_version` and `switched_at` on the attempt in one
  transaction; draft items move to requirements with the same `key`,
  granted hints carry over to hints with the same `key`. What cannot be
  carried over is listed in the confirmation step before switching.
  Coaches cannot force a switch.

**Every submission references its version.**

- `Submission.task_version` is a non-null foreign key with
  `on_delete=PROTECT`, set from the attempt when the submission is created
  and never changed afterwards.
- Points use the base points of that version (ADR 0013).
- Tasks with submissions are archived, never deleted (`PROTECT` makes this a
  database guarantee).

## Consequences

- A typo fix costs a new version. This is deliberate: it keeps the rule
  simple and the history honest. The change note can say "Tippfehler".
- Queries for "what does this participant see" always go through the
  attempt; a helper (`visible_version(user, task)`) keeps that in one place.
- Keys on requirements and hints become the contract between versions;
  the admin must make them visible and stable (pre-filled, read-only once
  the version is published).
- Draft versions are visible only to coaches, with a preview.
