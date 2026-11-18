# Architecture

Overview of how the project is built and run. Decisions and their rationale:
[`decisions/`](decisions/). Operations: [`deployment.md`](deployment.md).

## Code

| Path | Purpose |
|---|---|
| `config/` | Settings (one module, configured via environment), URLs, WSGI |
| `core/` | Base layout, home page, SEO (`core/seo.py`), noindex middleware, Markdown rendering (`core/markdown.py`, `markdown` template filter), navigation, `/version`, `/robots.txt`, error pages |
| `accounts/` | Profiles, roles (`is_coach`, group "Coach"), login/logout (`/anmelden/`, `/abmelden/`), password reset by email (`/passwort-vergessen/`), own profile (`/profil/`), internal profiles (`/teilnehmende/`), robot avatars (`accounts/avatars.py`, `/avatar/<seed>-<size>.png`), password rules |
| `tasks/` | Topics, shared level table (`LevelThreshold`), `tasks.levels.level_for_points`; tasks and versions follow (M3) |
| `badges/` | Badges with static artwork (`badges/static/badges/img/`) or a placeholder |
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
- Avatars (ADR 0012): Robohash set1 rendered locally as PNG in 64, 128 or
  256 px, only for seeds of existing profiles, kept in an in-process LRU
  cache and sent with `Cache-Control: public, max-age=1 year, immutable`
  (a new seed is a new URL). "Neuen Roboter würfeln" (POST
  `/profil/roboter-wuerfeln/`) sets a new seed. The footer credits the
  CC-BY artwork; a snapshot test of a few seeds guards package upgrades.
- Navigation entries can be `members_only` (`core.navigation.NavItem`).
- Password reset: Django's flow with German templates
  (`accounts/templates/accounts/`). Only active users with a stored email
  address get a link (valid `PASSWORD_RESET_TIMEOUT`, 3 days, single use);
  the confirmation page looks the same for unknown addresses. Without an
  email address a coach sets a new password in the admin. Emails go to the
  console until SMTP is configured (#3, M9).
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
