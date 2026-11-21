# 0019: GearsBot hosting: own origin, own image, caching, CSP

- Status: proposed
- Date: 2026-11-21

## Context

[`GEARSBOT_BRIEF.md`](../GEARSBOT_BRIEF.md) (section 3.1) asks us to host
the GearsBot simulator ourselves: built reproducibly from a pinned upstream
commit, no requests to third-party servers from participants' browsers,
long-term caching, a suitable CSP. Spike results:
[`gearsbot-spike.md`](../gearsbot-spike.md).

What matters for hosting:

- GearsBot is 215 MB of static files (`public/`), third-party JavaScript
  that runs Python with `eval` (Skulpt) and physics with WebAssembly
  (Ammo.js), and has three inline `<script>` blocks in `index.html`.
- It stores state in localStorage (language, autosaved programs).
- 33 files (about 0.8 MB) are loaded from `files.aposteriori.com.sg`, one
  from `raw.githubusercontent.com`: 5 images in the challenge worlds, the
  default robot JSON in `challenges_basic.js`, the rest in other worlds that
  are reachable from GearsBot's menu.
- Today production is `db`, `web` (Django, WhiteNoise for `/static/`) and the
  stock `caddy:2.10` image with `deploy/Caddyfile` (ADR 0005). The server
  has 2 GB RAM and 30 GB disk (25 % used).

## Decision

### 1. Origin: `sim.checkermint.ch`

GearsBot is served on its own subdomain **`https://sim.checkermint.ch`**.

- Third-party JavaScript with `eval` then runs on a different origin than
  Checkermint: it cannot read Checkermint's session or CSRF cookies (both
  host-only, no `Domain` attribute) or call Checkermint pages with the
  participant's login, and Checkermint's own CSP and headers stay strict.
- GearsBot's localStorage is separate from Checkermint's.
- One new DNS record `sim` (A and AAAA to the server), **added** by the
  maintainer; no other record of the domain changes. Caddy gets its own
  certificate for it.
- World, robot and filter JSON served by Checkermint (ADR 0021) need CORS:
  `Access-Control-Allow-Origin: https://sim.checkermint.ch` exactly, only
  on those JSON views, `GET` only, no credentials. The origin comes from a
  new setting `SIMULATOR_URL` (documented in `.env.example`; empty = no
  simulator, the button is hidden).
- Checkermint's `Referrer-Policy: same-origin` stays, so the simulator does
  not learn which Checkermint page linked to it.

**Alternative not chosen: same origin under `https://checkermint.ch/sim/gears/`.**
No DNS record and no CORS needed, relative URLs would work. But GearsBot's
JavaScript (with `eval`, from upstream we do not review line by line) would
run on Checkermint's origin: it could read Checkermint pages with the
participant's session, and Checkermint's CSP would have to allow `eval` for
that path or stay split by path, which browsers do not isolate. A
compromised or careless upstream change could then reach participants'
data. The subdomain costs one DNS record and one CORS header.

### 2. Image: a separate `checkermint-sim` image

- `sim/gears/Dockerfile` builds **`ghcr.io/kreuzlin/checkermint-sim`**
  (linux/amd64, tags `sha-<commit>` and `latest`, ADR 0006):
  1. Build stage: fetch upstream at the pinned commit
     (`git fetch --depth 1 <url> <sha>`, then check that `HEAD` is exactly
     that SHA – the commit hash verifies the content), apply our patch
     files (ADR 0020; none planned), copy the mirrored assets and rewrite
     their URLs (section 3), add our start page (section 5), check that no
     `files.aposteriori.com.sg` or other third-party URL is left in files
     loaded automatically.
  2. Final stage: `caddy:2.10` serving the files on port 8080 (plain HTTP,
     inside the Docker network only) with the cache and security headers
     below, configured by `sim/gears/Caddyfile` baked into the image.
- In `compose.prod.yaml` a new service `sim` (image above, `expose: 8080`,
  no volumes, no secrets). The main Caddy gets a site block for
  `{$SIM_ADDRESS}` that only does `reverse_proxy sim:8080` and adds the
  same `X-Robots-Tag` and HSTS as the main site. `SIM_ADDRESS` is a new
  variable (empty: the block is a harmless placeholder, like
  `REDIRECT_ADDRESSES`).
- Why a separate image and not inside the Django image: the Django image
  stays small and fast to build; the simulator image only changes when the
  pin changes (CI builds it only when `sim/` changes, otherwise it reuses the
  last one) and can be rolled back on its own. Why not files in a volume
  served by the main Caddy: it would need a copy step on the server for
  every update; the image is the unit we already deploy and roll back.
- We serve upstream's `public/` as it is, including unused library
  versions. Removing files would be a change to maintain on every update;
  disk space is not a problem (one image about 220 MB, old images are
  pruned by the deploy).
- `scripts/deploy.sh` also pulls and restarts `sim`; it removes dangling
  images afterwards (`docker image prune -f`), so old 220 MB images do not
  pile up.
- Locally, `compose.yaml` gets the same `sim` service on
  `http://localhost:8081`; `SIMULATOR_URL` points there.

### 3. Mirrored assets

- All 34 external files are stored **in our repository** under
  `sim/gears/mirror/` with a manifest (`mirror.json`: source URL, local
  name, SHA-256). The build does not download them, so it does not depend
  on that server.
- The build rewrites `https://files.aposteriori.com.sg/get/<name>` and the
  one `raw.githubusercontent.com` URL in `public/` to root-relative
  `/mirror/<name>` (a mechanical text replacement, not a patch file). The
  world files are loaded by the simulator page, so root-relative URLs
  resolve against `sim.checkermint.ch`, also inside task world files served
  by Checkermint (ADR 0021).
- Usage rights: the files are published by the GearsBot author for use in
  GearsBot. We ask upstream (an issue) whether they fall under the project's
  license and note the answer in `sim/gears/README.md`.

### 4. Caching

- Upstream files go under a versioned path **`/v/<short-sha>/`** (the
  pinned commit), served with `Cache-Control: public, max-age=31536000,
  immutable`. A new pin is a new path, so browsers never use stale files.
  `/mirror/` is cached the same way (files never change; a changed file
  gets a new name in the manifest).
- `/` (our start page) and `/robots.txt` are `Cache-Control: no-cache`.
- Requests for an older `/v/<sha>/…` that is no longer in the image are
  redirected to `/` with the same query string, so old links keep working.
- Compression: `encode zstd gzip` in the image's Caddy.

### 5. Start page and German default

`/` is a small page of ours (`sim/gears/start/index.html` with
`start.js`, no inline script): it sets `localStorage.LANG = "de"` and
`localStorage.whatsNew` (so the English "What's New" dialog does not pop
up) **only if they are not set yet**, then forwards with
`location.replace("/v/<short-sha>/index.html" + location.search)`.
Checkermint always links to `/` with the GearsBot query parameters, never
to the versioned path. No upstream file changes. A participant can still
pick another language in GearsBot's menu.

### 6. Headers and CSP on `sim.checkermint.ch`

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob:;
  media-src 'self' data: blob:;
  font-src 'self' data:;
  connect-src 'self' https://checkermint.ch;
  worker-src 'self' blob:;
  object-src 'none';
  base-uri 'self';
  form-action 'none';
  frame-ancestors 'none'
X-Robots-Tag: noindex, nofollow
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Opener-Policy: same-origin
```

- `'unsafe-eval'` and `'wasm-unsafe-eval'` are needed by Skulpt and Ammo.js;
  `'unsafe-inline'` by the inline scripts in upstream `index.html` (hashes
  would change with every update). This is acceptable only because the
  origin is isolated (section 1) and holds no Checkermint data.
- The point of the CSP is mainly **`connect-src`, `img-src`, `media-src`,
  `font-src` without third-party hosts**: even if upstream adds a new
  external URL we have not mirrored yet, browsers do not contact it (the
  file just does not load). `connect-src` allows exactly Checkermint
  (`SIMULATOR_URL`'s counterpart, set from the environment at container
  start) for the task JSON.
- `/robots.txt` disallows everything, no sitemap.
- The exact list is checked in the hosting PR in Chrome, Firefox and Safari
  (CSP violations in the console) and adjusted there; changes go into this
  ADR.

### 7. Privacy page and logs

- The privacy page (`/datenschutz/`) gets a paragraph on the simulator:
  same server, no third parties, programs and language are stored only in
  the browser (localStorage) and never sent to Checkermint unless the
  participant uploads a saved project.
- The `sim` access log goes to stdout like the rest (container log limits,
  ADR 0005 / #97).

## Consequences

- One more container (a few MB of RAM) and one more image to build and
  deploy. The deploy pulls about 220 MB when the pin changes, otherwise
  nothing new.
- Needs the maintainer: the DNS record `sim`, the new `.env` values
  (`SIM_ADDRESS`, `SIMULATOR_URL`) on the server, and the OK for the
  changes to `compose.prod.yaml`, the Caddyfile and `scripts/deploy.sh`
  (CLAUDE.md, Workflow).
- CLAUDE.md's rule "only the apex and `www` records are ever changed" gets
  the exception `sim` for this brief.
- `docs/PROJECT_BRIEF.md` says "apex, no subdomain"; that stays true for
  Checkermint itself, the simulator is the authorised exception.
- Tests: Django tests for the CORS header and the `SIMULATOR_URL` setting;
  the image build checks the rewrites; a smoke test in CI starts the `sim`
  image and requests `/`, `/robots.txt` and one versioned file.
