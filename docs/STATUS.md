# Project status

Current state of https://checkermint.ch and the next steps. **Every PR updates
this file** (at least "Last updated" and whatever the PR changes). Details
live in the linked docs; open work lives in GitHub issues.

Requirements and scope of version 1:
[`PROJECT_BRIEF.md`](PROJECT_BRIEF.md) (milestones in section 10).

_Last updated: 2026-11-18 (PR "Let participants edit their profile")_

## Live

- **https://checkermint.ch** – not live yet. The apex does not point to a
  server of this project yet (certificate mismatch, 2026-11-18). Planned:
  apex only, `www` redirects to the apex (#2).
- Deployed commit: `curl -s https://checkermint.ch/version`, compare with
  `git rev-parse origin/main`. Last deploy: `—`. Docs- or CI-only changes
  need no deploy (the live commit then lags behind `main`).
- Search engines: never indexed (brief, section 4). Django sends
  `X-Robots-Tag: noindex, nofollow` on every response, `/robots.txt`
  disallows everything, `<meta name="robots">` in the layout, no sitemap,
  canonical or Open Graph tags. Caddy sets the same header, fixed (no
  `ROBOTS_TAG` variable any more).

## Infrastructure

| What | Where |
|---|---|
| Server | Not set up yet (#1). Planned: UpCloud, Ubuntu 26.04, 2 cores / 2 GB / 30 GB, time zone Europe/Zurich |
| Access | `ssh {{SSH_TARGET}}` (key only, no root login, passwordless sudo) – placeholder until #1 is done |
| App | `/srv/checkermint` (git checkout), `compose.prod.yaml`: `db` (PostgreSQL 18), `web` (GHCR image, Gunicorn), `caddy` (HTTPS) |
| Secrets | `/srv/checkermint/.env` on the server only |
| Deploy | `scripts/deploy.sh` on the server after CI has pushed the image for the merged commit |
| Backups | cron 02:00 `scripts/backup-db.sh` (14 days in `backups/`), UpCloud backup _daily at …_; must include the `media` volume (ADR 0009) |
| Cron | _scheduled jobs_ |
| Mail | Hostpoint SMTP, sender `coach@checkermint.ch` (#3) |
| DNS | Hostpoint; only apex and `www` of checkermint.ch are changed (#2) |
| CI | GitHub Actions: lint + tests, `linux/amd64` image to `ghcr.io/kreuzlin/checkermint` (`latest`, `sha-<commit>`) on `main`; runs on `main` are queued, never cancelled |
| GitHub | Squash merge only (PR title/body), auto-merge, head branches deleted; ruleset "protect main" active (PR, CI checks, no force push/deletion); labels `ops`, `content`, `bug`, `enhancement` |

Runbook: [`deployment.md`](deployment.md). Architecture:
[`architecture.md`](architecture.md). Decisions: [`decisions/`](decisions/)
(project-specific: 0009–0013).

## Done (version 1)

- Milestone 1 (setup), partly: GitHub settings, placeholders replaced
  (except `{{SSH_TARGET}}`), project brief added, ADRs 0009–0013 (private
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
- #12: password reset by email (`/passwort-vergessen/`, German pages and
  email, link valid 3 days) for accounts with an email address; otherwise a
  coach sets a new password. Emails go to the console until SMTP (#3, M9).
- #13: own profile `/profil/` (about text, optional email, visibility
  switches, notifications; nickname and real name only via coaches),
  internal directory and profiles `/teilnehmende/` for logged-in users
  (email only for the person and coaches).

## Open issues

Overview: `gh issue list`. At the time of writing:

| # | Topic | Who |
|---|---|---|
| 1 | Production server (UpCloud), SSH target, backups, GHCR visibility | Maintainer |
| 2 | DNS for checkermint.ch (apex and `www` only) | Maintainer |
| 3 | Outgoing mail `coach@checkermint.ch` (Hostpoint SMTP) | Maintainer |
| 4 | Logo, colours and badge artwork | Maintainer |
| 6–51 | Version 1, one issue per PR, grouped in milestones M1–M11 (brief, section 10); PRs with migrations or server changes are marked and merged by the maintainer | Claude Code |

## Next steps

1. Maintainer merges PR #57 (#11 coach-created accounts, contains a
   migration).
2. M2 (accounts and profiles): #14 avatars.
3. Libraries agreed: `markdown` + `nh3` (sanitised Markdown), `segno` (QR
   codes), htmx served as a local static file, `robohash` (avatars).

## Working agreements (summary)

- Conversation with the maintainer in German; docs and code in English; site
  content German (Swiss spelling). See CLAUDE.md.
- Every change via branch + PR. Claude merges its own PRs with
  `gh pr merge <N> --squash --auto` once the checks are green, verifies with
  `gh pr view` and deploys. PRs with database migrations or server/deployment
  changes are merged by the maintainer. Never pipe `gh` output.
- Content on the live site lives only in the production database, not in
  git; local data is a playground.
- Privacy principles (brief, section 4) are hard rules.
