# 0020: GearsBot pinning, patches and monthly update PRs

- Status: accepted (maintainer, 2026-11-21)
- Date: 2026-11-21

## Context

[`GEARSBOT_BRIEF.md`](../GEARSBOT_BRIEF.md) (section 3.2): the deployed
GearsBot comes from an exact upstream commit, pinned in one place; no fork;
patches only if unavoidable; a monthly workflow proposes updates as PRs;
updating GearsBot never changes existing task versions. Upstream
(`QuirkyCort/gears`, branch `master`) gets commits every few days, mostly new
worlds for competitions we do not use.

## Decision

### 1. The pin

- **`sim/gears/UPSTREAM`**: the full 40-character commit SHA, one line,
  nothing else. It is the only place that names the version; the
  Dockerfile, the start page (`/v/<short-sha>/`, ADR 0019) and the import
  command (ADR 0021) read it.
- The upstream repository URL is fixed in `sim/gears/Dockerfile`
  (`https://github.com/QuirkyCort/gears.git`). GitHub is contacted only by
  CI while building the image, never by the server at runtime.

### 2. Patch policy

- Default: **no patches.** Things are solved outside GearsBot: asset
  mirroring and URL rewriting as a build step (ADR 0019, section 3), the
  German default by our start page (ADR 0019, section 5), the deep link by
  URL parameters (ADR 0021).
- If a patch becomes unavoidable: one small file per change in
  `sim/gears/patches/NNNN-<topic>.patch` (unified diff against the pinned
  commit, applied with `git apply --check` then `git apply` in the build),
  each listed in `sim/gears/README.md` with why it exists and when it can
  go. A new patch needs an ADR or an ADR update first. Patches are GPLv3
  (ADR 0022).
- A patch that no longer applies fails the build; the update PR then shows
  it and must refresh or drop the patch.

### 3. Monthly update workflow

`.github/workflows/gearsbot-update.yml`, `schedule` on the 1st of each month
plus `workflow_dispatch`:

1. Read `sim/gears/UPSTREAM`; `git ls-remote` upstream `master`.
2. Same SHA: stop.
3. Otherwise: shallow clone up to the pinned commit, write the new SHA to
   `UPSTREAM`, run the GearsBot checks (below) for **both** versions and
   compare.
4. Open or update one PR from branch `chore/gearsbot-update` ("Update
   GearsBot to <short-sha>"), label `ops`, with:
   - the upstream commit log `<old>..<new>` (`git log --oneline`, with links),
   - changed files under `public/js/worlds/extra/challenges_basic.js` and
     `public/worlds/challenges_basic/`,
   - a table of **changed, added or removed challenges**: title, world file
     (`?v=` hash changed), completion code changed, block limit changed,
   - new external URLs that are not in the mirror manifest (these make the
     check fail, see below).
   It updates `docs/STATUS.md` in the same PR ("GearsBot pin" line in the
   infrastructure table).
- The workflow uses the default `GITHUB_TOKEN` with `contents: write` and
  `pull-requests: write`. PRs opened with `GITHUB_TOKEN` do not trigger
  other workflows, so the workflow then runs the CI by
  `gh workflow run` on the branch, or the maintainer closes and reopens the
  PR. Details are settled in the workflow's PR; if neither works, a
  fine-grained token becomes a new secret (needs the maintainer).

### 4. GearsBot checks in CI

A Python script `sim/gears/check.py` (no Django, standard library only) runs
in a CI job **"GearsBot"** on every PR that touches `sim/`, and inside the
image build:

- `UPSTREAM` is a full SHA and the checked-out commit matches it;
- all patches apply;
- every `files.aposteriori.com.sg` / `raw.githubusercontent.com` URL in
  `public/` has an entry in `sim/gears/mirror.json`, every manifest
  file exists and matches its SHA-256; after the rewrite no such URL is left;
- `challenges_basic.js` can be parsed: every option has a world file that
  exists and is valid JSON with `worldName` and `options`, every world file
  has exactly one success branch with a completion code, no branch is left
  without an option (the parser from the spike);
- it writes the **challenge bundle** `sim/gears/challenges_basic/`:
  `challenges.json` (order, title, file, `?v=` hash, code, block limit) and
  the 61 world files with the mirror URLs already rewritten (about 1 MB).
  The bundle is **committed**: the Django image contains no GearsBot, and
  the import command (ADR 0021) reads only the bundle. Update PRs
  regenerate it, so changed worlds show up in the diff; CI fails if the
  committed bundle does not match the pinned commit.

The job becomes a required check once it exists (ruleset "protect main";
the maintainer adds it).

### 5. Who merges

Update PRs change third-party code that participants run, so **the
maintainer merges them** (brief, sections 3.2 and 5), after looking at the
report. Claude does not merge them, even when green. After the merge the
normal deployment applies (CLAUDE.md, Workflow).

### 6. Effect on tasks

- An update changes the GearsBot code, the mirrored assets and the
  challenge rules in `challenges_basic.js` for everyone at once.
- Task versions keep their own copies of world, robot and filter JSON and
  their expected completion code (ADR 0021), so what a task asks for does
  not change. What can change with an update: GearsBot's behaviour, the
  completion code shown on success, a block limit, the mission text. The PR
  report lists such changes. If a code changed, the review form shows
  "Code stimmt nicht" for submissions on older versions; the coach decides
  (no automatic approval, brief 3.4). The import command then creates new
  draft versions with the new code (ADR 0021).
- Rollback: pin the old SHA again in a PR, or deploy the previous `sim`
  image (`SIM_IMAGE_TAG=sha-…`).

## Consequences

- One small, readable place to see what runs (`UPSTREAM`) and why it
  differs from upstream (`patches/`, `mirror/`, README).
- A monthly PR to review; most months it will only touch worlds we do not
  use, and the report says so.
- Full immutability of the challenge rules is not possible without a fork:
  the success check lives in upstream JavaScript. We accept that and make
  changes visible instead.
