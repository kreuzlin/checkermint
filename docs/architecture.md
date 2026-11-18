# Architecture

Overview of how the project is built and run. Decisions and their rationale:
[`decisions/`](decisions/). Operations: [`deployment.md`](deployment.md).

## Code

| Path | Purpose |
|---|---|
| `config/` | Settings (one module, configured via environment), URLs, WSGI |
| `core/` | Base layout, home page, SEO (`core/seo.py`), noindex middleware, Markdown rendering (`core/markdown.py`, `markdown` template filter), navigation, `/version`, `/robots.txt`, error pages |
| `<app>/` | One small Django app per topic (added per project) |

- Every public view sets title and meta description via `core.seo.SeoMixin`;
  `base.html` renders `<title>` and description. Nothing is indexed:
  `core.middleware.NoIndexMiddleware` sends `X-Robots-Tag: noindex, nofollow`
  on every response, `/robots.txt` disallows everything, `base.html` adds
  `<meta name="robots" content="noindex, nofollow">`; no canonical, Open
  Graph or sitemap.
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
