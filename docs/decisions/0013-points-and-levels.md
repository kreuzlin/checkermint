# 0013: Points and levels are derived, never stored by hand

- Status: accepted
- Date: 2026-11-18

## Context

Participants collect points per task, which determine their level per
topic (brief, sections 5.3 and 5.8). Points must be traceable to reviews,
must never drop because of a resubmission, and must not be edited by hand.

## Decision

**Points per task.**

- Only `approved` submissions count. Among a participant's approved
  submissions for a task, the one with the highest points counts:
  `points = submission.task_version.base_points × submission.stars`
  (stars 1–3).
- So a resubmission can only raise points: a worse review of a later
  submission does not replace a better earlier one. Hints cost nothing.
- Archiving a task does not remove points already earned.

**Points per topic** are the sum of the per-task points of all tasks in that
topic. There is no overall level and no overall points total in the UI.

**Levels.**

- `LevelThreshold (level, min_points)`, one shared table for all topics,
  editable by coaches in the admin. Level 1 at 0 points must exist
  (validated); levels and thresholds must both be strictly increasing.
- A participant's level in a topic is the highest level whose `min_points`
  is reached; progress to the next level is shown as points still missing.
- Changing the table immediately changes everyone's levels, including the
  unlock state of tasks (`Task.min_level`).

**Computation.**

- Computed from the data with database aggregation in one service module
  (`progress`), not stored on the profile. With about 10 participants this
  is cheap; the queries are covered by tests.
- If it ever becomes slow, a cache table per (user, topic) is recomputed in
  the same transaction as each review and threshold change. That is an
  optimisation, not a second source of truth.

**Badges** are awarded once, on the first approval of a task that has a
badge (`UserBadge`, unique per user and badge). They are stored, not
derived, because they are an event with a date; revoking is a manual admin
action.

## Consequences

- No drift between stored and real points; any review correction is
  reflected immediately.
- Rankings (per topic) use the same service, so the dashboard, profile,
  ranking and coach matrix always agree.
- Base points are part of the immutable version (ADR 0010), so changing
  points for a task in a new version only affects submissions made against
  that version.
