# Deployment and operations

How the production server runs https://checkermint.ch. Architecture and rationale:
[`architecture.md`](architecture.md), ADRs 0005–0008. Placeholders in
examples: `<server-ip>`, `<domain>`.

## Overview

- UpCloud server, Ubuntu 26.04 LTS, Docker Engine with the Compose plugin.
- Repo checkout in `/srv/checkermint` (public repo, no credentials
  needed). It provides `compose.prod.yaml`, `deploy/Caddyfile` and the
  scripts; the app itself comes as an image from GHCR.
- `.env` in `/srv/checkermint` holds all secrets (mode `600`, never
  committed).
- Containers: `db` (PostgreSQL 18), `web` (Gunicorn), `caddy` (HTTPS).

## 1. Server setup (once)

As root on a fresh server:

```bash
# Updates, automatic security updates (enabled by default once installed)
apt update && apt upgrade -y
apt install -y ufw unattended-upgrades git ca-certificates curl
# reboot if /var/run/reboot-required exists

# Time zone (cron times below are Swiss time)
timedatectl set-timezone Europe/Zurich

# Swap as a safety net (small servers have ~2 GB RAM)
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo "/swapfile none swap sw 0 0" >> /etc/fstab
echo "vm.swappiness=10" > /etc/sysctl.d/99-swappiness.conf && sysctl -p /etc/sysctl.d/99-swappiness.conf

# Firewall
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw enable

# Admin user with SSH key login (copies root's authorized_keys).
# No password, so sudo without password – the docker group is
# root-equivalent anyway.
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy && chmod 440 /etc/sudoers.d/deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Docker publishes ports past `ufw`; only Caddy publishes ports (80/443), so
this is fine – never publish the database or `web`.

SSH hardening: first check that `ssh deploy@<server-ip>` and `sudo -n true`
work in a second session. Then create
`/etc/ssh/sshd_config.d/00-hardening.conf` (the `00-` prefix matters: sshd
uses the first value it reads, and `50-cloud-init.conf` may enable
passwords), run `sshd -t && systemctl reload ssh` and verify with `sshd -T`:

```
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
```

From now on log in as `deploy`. Install Docker Engine from Docker's apt
repository (docs.docker.com, "Install Docker Engine on Ubuntu"), then
`usermod -aG docker deploy` and limit container log size in
`/etc/docker/daemon.json`, then `systemctl restart docker`:

```json
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "5"}
}
```

## 2. DNS

At the DNS provider: an `A` record (and `AAAA` only if the server has IPv6
configured) for the site's host name pointing to the server. Caddy can only
obtain the certificate once this record resolves. Watch out for wildcard
records and existing `AAAA` records that point elsewhere – they make some
clients reach the old host. Never touch `MX`, `SPF`, `DKIM` or `DMARC`
records as part of the website.

Check the authoritative name servers directly (bypasses local caches):

```bash
dig +short <domain> A @<authoritative-name-server>
dig +short <domain> AAAA @<authoritative-name-server>
```

## 3. First deployment

As `deploy`:

```bash
sudo mkdir -p /srv/checkermint && sudo chown deploy:deploy /srv/checkermint
git clone https://github.com/kreuzlin/checkermint.git /srv/checkermint
cd /srv/checkermint
cp .env.example .env && chmod 600 .env
```

Edit `.env` for production:

| Variable | Value |
|---|---|
| `SECRET_KEY` | new random key (see comment in `.env.example`) |
| `DEBUG` | `false` |
| `ALLOWED_HOSTS` | `<domain>` |
| `CSRF_TRUSTED_ORIGINS` | `https://<domain>` |
| `SITE_ADDRESS` | `<domain>` (`:80` for a test on the IP, see below) |
| `REDIRECT_ADDRESSES` | e.g. `www.<domain>`, or empty |
| `POSTGRES_PASSWORD` | new random password, same in `DATABASE_URL` |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP server and the website's own mailbox |

Secrets are entered on the server by the maintainer, never passed through
chat, issues or the repo. Put passwords in **single quotes**
(`EMAIL_HOST_PASSWORD='...'`): Docker Compose interpolates `$` in unquoted
values. A password can be written without echoing it, e.g. with
`read -rsp "Passwort: " PW` and a small script that updates `.env`.

**Before DNS points to the server**, test over plain HTTP on the IP: set
`SITE_ADDRESS=:80`, leave `REDIRECT_ADDRESSES` empty and add the IP to
`ALLOWED_HOSTS`. Do not set the domain earlier – Caddy would keep failing the
ACME challenge and can hit Let's Encrypt's rate limit for failed validations.
Once the authoritative name servers answer with the new IP, set
`SITE_ADDRESS=<domain>`, remove the IP from `ALLOWED_HOSTS` and recreate the
containers (see "Changing `.env`"). Caddy obtains the certificate within
seconds.

The GHCR image must be pullable: make the package public (GitHub → package
settings → visibility) or `docker login ghcr.io` on the server with a
read-only token.

Then:

```bash
scripts/deploy.sh
docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
```

Check `https://<domain>/`, log in to `/admin/`. Test email sending:

```bash
docker compose -f compose.prod.yaml exec -T web python manage.py sendtestemail <address>
```

Hostpoint: `EMAIL_HOST=asmtp.mail.hostpoint.ch`, `EMAIL_PORT=465`,
`EMAIL_USE_SSL=true`, user = the full mailbox address. To change the
mailbox password later without it showing up anywhere (the value stays out
of the shell history and the screen):

```bash
read -rsp "Neues Passwort: " PW && echo && \
  sed -i "s|^EMAIL_HOST_PASSWORD=.*|EMAIL_HOST_PASSWORD='$PW'|" .env && unset PW && \
  docker compose -f compose.prod.yaml up -d --force-recreate web
```

The password must not contain `'` or `|`.

### Changing `.env`

`docker compose up -d` does not notice changes inside `.env`. Recreate the
affected containers:

```bash
docker compose -f compose.prod.yaml up -d --force-recreate web    # Django settings
docker compose -f compose.prod.yaml up -d --force-recreate caddy  # SITE_ADDRESS, REDIRECT_ADDRESSES, UPLOAD_MAX_REQUEST_MB
```

Upload limits: `UPLOAD_MAX_PHOTO_MB` and `UPLOAD_MAX_FILE_MB` (per file,
Django, recreate `web`) and `UPLOAD_MAX_REQUEST_MB` (per request, Caddy,
recreate `caddy` and `web`, which shows the value in help texts). All have
defaults (15, 20, 100); `python manage.py check` warns (`submissions.W001`)
if the request limit is smaller than a file limit. Too large requests get
a 413 with a short German message from Caddy.

## 4. Deploying updates

After a PR is merged, CI pushes a new image (`latest` and `sha-<commit>`).
Wait until the CI run for the merge commit has pushed it
(`gh run list --branch main --limit 1`), otherwise `latest` is still the
previous build. Then:

```bash
ssh deploy@85.9.202.23 'cd /srv/checkermint && scripts/deploy.sh'
curl -s https://checkermint.ch/version   # {"commit": "<sha>", "short": "<sha7>"}
```

The script pulls the repo and images, runs migrations, restarts the
containers and removes old images. The commit is baked into the image by CI
(`GIT_COMMIT` build arg → `APP_COMMIT`); locally built images report `dev`.

**Rollback** to an earlier build (tested 2026-11-20, #50: about 10 seconds,
`/version` shows the old commit):

```bash
sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=sha-<full commit>|" .env
scripts/deploy.sh
curl -s https://checkermint.ch/version
# later, once the fix is merged and its image pushed:
sed -i "s|^IMAGE_TAG=.*|IMAGE_TAG=latest|" .env
scripts/deploy.sh
```

Every merge to `main` has an image `sha-<full commit>` on GHCR (docs-only
merges too). `scripts/deploy.sh` also pulls the repo, so scripts and
`compose.prod.yaml` stay at `main` – only the app image goes back.

Migrations are **not** rolled back. The old code then runs against the newer
schema, which is fine for reading, but it can break writing: a column added
as `NOT NULL` without a database default makes the old code's inserts fail.
Example: rolling back to before #77 (`submissions/0003`, `via_phone`) would
break new uploads. Before rolling back across a migration:

1. List the migrations in between:
   `git diff --stat <old>..<new> -- '*/migrations/*'`.
2. Only data and nullable columns added → rollback is safe.
3. Otherwise prefer a fix forward (new PR), or restore the database dump
   taken before the deploy (section 6) and accept losing what happened
   since. Take a backup (`scripts/backup.sh`) before deploying a PR with
   migrations once the site is productive.

## 5. Scheduled jobs

`crontab -e` as `deploy`:

```cron
# Database dump and media copy before the UpCloud backup, nightly 02:00
0 2 * * * cd /srv/checkermint && scripts/backup.sh
```

Add project-specific jobs (e.g. deleting old form submissions) here and in
`docs/STATUS.md`. After changing the time zone, `systemctl restart cron`.
Schedule the UpCloud backup after the dump (ADR 0008).

## 6. Backups and restore

`scripts/backup.sh` (cron, nightly, ADR 0017) writes to `backups/`
(mode `600`, not in git):

- `db-YYYY-MM-DD-HHMMSS.dump` – `pg_dump` custom format, the last 14 days
  (`KEEP_DAYS`). The time of day keeps a manual run (e.g. before a risky
  migration) from replacing the nightly dump of the same day; dumps from
  before 2026-11-21 are named `db-YYYY-MM-DD.dump`.
- `media.tar` – copy of the uploaded files from the Docker volume
  `<project>_media` (mounted only into `web`, private, ADR 0009); only the
  latest. Older states are in the UpCloud backups of the disk.

**Restore test** (changes nothing on the live site):

```bash
scripts/backup.sh && scripts/test-restore.sh
```

It restores the latest dump into a throwaway PostgreSQL container and
extracts `media.tar` into a temporary directory, then compares rows per
table and the SHA-256 sum of every file with the running site. The last
lines must read `Database matches the live site: yes` and
`Media matches the live site: yes` (exit code 0); differences are printed
above them. Run it after changes to the backup and before the go-live.

**Restore for real** (overwrites the live data – stop and think first,
take a fresh `scripts/backup.sh` of the current state if it is worth
keeping):

```bash
# Database
docker compose -f compose.prod.yaml exec -T db \
  sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < backups/db-YYYY-MM-DD-HHMMSS.dump

# Uploaded files: empty the volume, then unpack the copy
docker compose -f compose.prod.yaml exec -T web \
  sh -c 'find /app/media -mindepth 1 -delete'
docker compose -f compose.prod.yaml exec -T web tar -C /app/media -xf - \
  < backups/media.tar
```

From an UpCloud backup: restore the disk (whole server) in the control
panel, or attach the backup as an extra disk to a server and copy
`/srv/checkermint/backups/` from it, then restore as above.

## 7. Logs and status

```bash
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs --tail 100 web    # Django/Gunicorn
docker compose -f compose.prod.yaml logs --tail 100 caddy  # access log, TLS
```

## 8. Domain switch

Done for checkermint.ch on 2026-11-20 (first deploy). The site then runs
but is not productive yet – that is section 9.

1. DNS: point the main domain (and e.g. `www`) to the server; remove old
   `AAAA` records that point elsewhere. Do not touch mail records. If the
   domain is attached to an old web hosting, detach it there first, otherwise
   the provider may reset the records.
2. Wait until the authoritative name servers answer with the new IP (`dig`,
   see section 2).
3. Update `.env` and deploy:

   ```
   SITE_ADDRESS=<domain>
   REDIRECT_ADDRESSES=www.<domain>
   ALLOWED_HOSTS=<domain>
   CSRF_TRUSTED_ORIGINS=https://<domain>
   ```

   ```bash
   scripts/deploy.sh   # recreates web and caddy with the new .env
   ```

4. Check: `https://<domain>/` (200, `X-Robots-Tag: noindex, nofollow` –
   the site is never indexed), `https://<domain>/media/…` is not served
   (404), redirects
   (301 to the main address), admin login, forms and email.
5. Record the deploy in `docs/STATUS.md`. Caddy sends HSTS for one year
   (without subdomains) – from now on the domain must stay on HTTPS.

## 9. Go-live checklist

The app is **productive** once the maintainer says so: real participants
get accounts and their data must be kept. Before that, go through this
list (brief, sections 8.3 and 10, milestone 11). Items marked with the
issue are tracked there.

**Operations**

- [x] Server set up (section 1), domain switched (section 8), checks of
  section 8 step 4 pass (2026-11-20).
- [ ] Email works (#3, #42): `sendtestemail` to an outside address
  arrives; a password reset email arrives and its link works; a
  notification about a submission reaches a coach. Not in spam.
  (2026-11-21: SPF, DKIM and DMARC pass, the external test email arrived
  in the inbox; the coach notification on a submission arrived in the
  inbox; the password reset works, its email landed in spam – accepted by
  the maintainer, common for reset emails. Still to try: the email to a
  participant after a review.)
- [x] Backups: cron runs `scripts/backup.sh` at 02:00, UpCloud backup after
  it (02:15); `scripts/backup.sh && scripts/test-restore.sh` passes (#49).
  After the first night: today's files in `backups/` (2026-11-21 OK).
- [x] Rollback tested (section 4, #50, 2026-11-20).
- [x] Container log retention matches the privacy page: 50 MB per
  container (`/etc/docker/daemon.json`, section 1; #97).
- [x] Disk: `df -h /` well below 80 % (25 % on 2026-11-21).

**Accounts and content** (in the admin, by the maintainer and coaches)

- [ ] Maintainer's superuser exists; coaches have staff accounts in the
  group "Coach" (no superusers).
- [ ] Topics, level table, first tasks with published versions and hints.
- [ ] Badges attached to tasks (the eight badges with images exist since
  2026-11-21, #4, #120).
- [ ] No demo or test data on the server. Demo data was loaded for
  testing on 2026-11-20; remove it (same one-off container, the site
  keeps `DEBUG=false`):
  `docker compose -f compose.prod.yaml run --rm -e DEBUG=true web python manage.py seed_demo --remove`.
  If a real account has submitted to a demo task, the command refuses
  and removes nothing. Then check the admin lists.

**Pages and privacy**

- [ ] Landing page wording, privacy page and imprint reviewed; decision
  on a postal address in the imprint (2026-11-20: none, contact
  `privacy@checkermint.ch`).
- [x] Manual test of phone upload and live update
  ([`manual-testing.md`](manual-testing.md)) on the live site (2026-11-21,
  after fixing #128, #130, #132, #134).
- [ ] Public profile of a test participant shows nothing private (no real
  name, no email, no feedback).

**Switch to productive**

- [ ] `docs/STATUS.md`: the app is productive (date).
- [ ] Participants get their accounts.
