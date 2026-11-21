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
| `check.py`, `tests/` | Parses the Basic Challenges and writes the committed bundle `challenges_basic/` (codes, block limits, mission texts, world files with mirror URLs) for the import command; `verify` (CI job "GearsBot"), `report` and `mirror-add` for the update workflow (ADR 0020) |
| `challenges_basic/` | The bundle, generated – never edit by hand |
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

## Updating GearsBot

The workflow "GearsBot update" does it monthly (or via "Run workflow"): new
pin, new mirrored files, new bundle, a PR with a report. The maintainer
merges it. By hand, with an upstream checkout at the new commit:

```bash
git rev-parse HEAD > sim/gears/UPSTREAM        # in the upstream checkout
python3 sim/gears/check.py mirror-add <checkout>
python3 sim/gears/check.py bundle <checkout>
python3 sim/gears/build.py <checkout> sim/gears /tmp/site
```
