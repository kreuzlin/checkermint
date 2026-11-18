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
by data migrations calling `sync_coach_group` (first: `accounts/0002`).
Current coach permissions: view and change profiles. Managing user accounts
follows with a hardened user admin (#11).

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
