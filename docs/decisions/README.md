# Architecture Decision Records

Fundamental decisions, one file each, numbered sequentially.
An ADR is not rewritten after the fact; a changed decision gets a new ADR that
marks the old one as "superseded by".

Template: [`0000-template.md`](0000-template.md). ADRs 0001–0008 come from
the project template (`kreuzlin/django-template`); 0009 onwards are specific
to Checkermint.

| No.  | Title                                                                  | Status   |
|------|------------------------------------------------------------------------|----------|
| 0001 | [Use ADRs](0001-use-adrs.md)                                           | accepted |
| 0002 | [Django with server-side templates](0002-django-with-templates.md)     | accepted |
| 0003 | [PostgreSQL as database](0003-postgresql.md)                           | accepted |
| 0004 | [Python tooling: uv and Ruff](0004-uv-and-ruff.md)                     | accepted |
| 0005 | [Hosting: Docker Compose, Caddy, UpCloud](0005-hosting-docker-caddy-upcloud.md) | accepted |
| 0006 | [Build images in GitHub Actions](0006-build-images-in-github-actions.md) | accepted |
| 0007 | [Secrets only in .env](0007-secrets-in-env.md)                         | accepted |
| 0008 | [Backups with UpCloud's backup service](0008-backups-with-upcloud.md) | accepted |
| 0009 | [Private media served by Django](0009-private-media.md)                | accepted |
| 0010 | [Immutable task versions, pinned per participant](0010-task-versioning-and-pinning.md) | accepted |
| 0011 | [Flexible submission requirements with typed items](0011-flexible-submission-requirements.md) | accepted |
| 0012 | [Robot avatars generated locally with Robohash](0012-avatar-generation.md) | accepted |
| 0013 | [Points and levels are derived, never stored by hand](0013-points-and-levels.md) | accepted |
| 0014 | [Files in submissions: code as text, own files per item, generated alt text](0014-submission-files.md) | accepted |
| 0015 | [A version switch replaces the draft](0015-version-switch-replaces-draft.md) | accepted |
| 0016 | [Demo data for local development, removable despite ADR 0010](0016-demo-data-command.md) | accepted |
| 0017 | [File copy of the media volume in the nightly backup](0017-file-copy-of-media-in-nightly-backup.md) | accepted |
