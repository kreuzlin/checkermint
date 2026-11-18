# 0011: Flexible submission requirements with typed items

- Status: accepted
- Date: 2026-11-18

## Context

What a solution consists of differs per task: a text explanation, pasted
code, three photos of a robot, a CAD file. Version 1 needs `text`, `code`,
`photo` and `file`; later video, simulator results, links and more must be
addable without restructuring existing data (brief, section 5.6).

## Decision

**Requirements are rows on the task version.**

`TaskRequirement (task_version, key, type, label, help_text, required,
min_count, max_count, order, options)`

- `key`: stable slug, kept across versions (ADR 0010).
- `type`: a `CharField` with choices (`text`, `code`, `photo`, `file`), not a
  foreign key and not a subclass per type.
- `min_count` / `max_count`: how many items (e.g. 2–5 photos; 1–1 for text).
- `options`: a `JSONField` for type-specific settings (e.g. allowed file
  extensions, code language for highlighting), validated by the type
  handler.

**Submissions consist of items, one row per value.**

`SubmissionItem (submission, requirement, order, text, file,
original_filename, thumbnail, data)`

- A text or pasted code answer is one item with `text`; three photos are
  three items. The generic columns cover v1; `data` (`JSONField`) holds
  structured values of future types (e.g. a simulator score, a URL with
  metadata) so they need no new columns.
- `requirement` points to the requirement of the submission's own version;
  the item's type is the requirement's type.

**Behaviour lives in a handler registry, not in the schema.**

Each type has a handler class registered by its type name. It provides the
form field(s), validation (incl. counts and `options`), processing on save
(e.g. image pipeline from ADR 0009, syntax highlighting for code) and the
templates for the submission form, the review form and the history.
Forms and views iterate over requirements and delegate to the handler.

**Adding a type later** means: a new handler, a new choice value (a
trivial migration that only changes `choices`), templates and tests.
Existing requirements and items stay untouched.

## Consequences

- No polymorphic models or generic relations; queries stay simple and the
  admin can edit requirements as an inline of the task version.
- Some columns are unused for some types (e.g. `file` for text). Accepted;
  the handler validates which columns a type may use.
- `data` is schemaless; each handler owns its schema and validates it. Use
  it only for genuinely new types, not to avoid adding a proper column that
  every type needs.
- Draft items can be carried to a new version by matching requirement
  `key`s; items whose key no longer exists or whose type changed are listed
  before switching (ADR 0010).
