# 0015: A version switch replaces the draft

- Status: accepted
- Date: 2026-11-19

## Context

ADR 0010 says that on a switch to a newer version "draft items move to
requirements with the same `key`", and that `Submission.task_version` is
"set when the submission is created and never changed afterwards". A draft
is a submission, and there is at most one draft per participant and task
(partial unique constraint, which PostgreSQL cannot defer). Moving the
draft to the new version would mean changing its version, contradicting
the second rule.

## Decision

- The switch (`submissions.switching.switch_version`) runs in one
  transaction: it copies the carried items, deletes the old draft with all
  its items, creates a new draft on the new version with the copies, and
  updates `task_version` and `switched_at` on the attempt.
- Carried over: items whose requirement exists in the new version with the
  same key **and** the same type, up to the new `max_count` (first items by
  order). Everything else is listed in the confirmation step before the
  switch (missing key, changed type, more items than allowed).
- Copies get their own files (ADR 0014); the old files are deleted after
  the commit.
- The switch only happens for the version the participant confirmed: if
  an even newer version was published in between, the switch is refused
  and the confirmation is shown again.
- There is no way back to an older version.

## Consequences

- `Submission.task_version` stays immutable without exception; the old
  draft's id disappears, which nothing references.
- Submissions already submitted keep their version, as before.
- A switch copies photos and files once more (storage for a moment, then
  the old files are deleted).
- After a switch, a new draft does not start from the last submission
  (that one belongs to the old version); the participant fills the new
  version's form. Carrying content from older submissions across versions
  can be added later if participants miss it.
