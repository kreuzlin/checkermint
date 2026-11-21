# GearsBot packaging

Builds the image `ghcr.io/kreuzlin/checkermint-sim` that serves the GearsBot
simulator on `sim.checkermint.ch` (ADR 0019). Brief:
[`docs/GEARSBOT_BRIEF.md`](../../docs/GEARSBOT_BRIEF.md).

| File | What |
|---|---|
| `UPSTREAM` | The pinned upstream commit of https://github.com/QuirkyCort/gears (the only place that names the version, ADR 0020) |
| `Dockerfile` | Fetches exactly that commit, runs `build.py`, serves the result with Caddy on port 8080 |
| `build.py` | Checks the commit and the mirror, copies `public/` to `/v/<short-sha>/`, rewrites mirrored URLs to `/mirror/<name>`, fails if a URL of a mirrored host is left, writes the start page |
| `mirror/`, `mirror.json` | Files GearsBot would load from `files.aposteriori.com.sg` and `raw.githubusercontent.com`, with source URL and SHA-256 |
| `start/` | Start page `/`: sets German and hides the "What's New" dialog if the browser has no setting yet, then forwards to the pinned version with the same query string |
| `Caddyfile` | Caching (`/v/<current>/` and `/mirror/` immutable, the rest `no-cache`, old versions redirect to `/`) and headers incl. CSP; `CHECKERMINT_ORIGIN` sets `connect-src` |
| `patches/` | Patch files against upstream – none. Policy: ADR 0020, section 2 |
| `LICENSE` | GNU GPL v3, copied from upstream |

## License

GearsBot is © Cort Wee (A Posteriori), licensed under the GNU GPL v3; the
libraries it bundles keep their own licenses. Our files in this folder
(build script, start page, Caddyfile, Dockerfile, patches) are licensed
under the GNU GPL v3 as well (ADR 0022). The rest of Checkermint is a
separate program and not covered by this.

The mirrored files are published by the GearsBot author for use in
GearsBot; we use them unchanged. Their license is to be confirmed with
upstream (ADR 0019, section 3).

## Locally

```bash
docker compose --profile sim up --build sim   # http://localhost:8081/
```

The first build downloads upstream GearsBot (about 215 MB).

## New external URL after an update

`build.py` fails with the list of URLs. Download each file into `mirror/`
(file name = last part of the URL) and add an entry to `mirror.json` with
its SHA-256 (`shasum -a 256 mirror/<name>`). ADR 0020 automates this report
in the update PR.
