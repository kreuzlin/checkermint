# Checkermint: GearsBot Integration Brief

- Owner: kreuzlin
- Created: 2026-11-21, from the planning chat
- Builds on: docs/PROJECT_BRIEF.md (version 1 is complete)
- This brief authorizes the work described below. Anything beyond it still needs kreuzlin's approval first.

## 1. Goal

Integrate the GearsBot robotics simulator into Checkermint so that participants learn programming with blocks and then Python in a simulated EV3-style robot, and solve these exercises as normal Checkermint tasks with submissions, review, points and levels.

Three results:

1. GearsBot is hosted by us, reproducibly built from a pinned upstream version, and kept up to date through a reviewed update process.
2. A task can be linked to a GearsBot world. "Im Simulator öffnen" opens GearsBot with exactly that world, robot and block selection.
3. The upstream "Basic Challenges" (`challenges_basic`, about 60 challenges) are imported as draft tasks that coaches review, adjust and publish.

## 2. Facts about GearsBot (checked in upstream, commit c0549600, 2026-11-16)

Upstream: https://github.com/QuirkyCort/gears (default branch `master`). Verify everything below again during the spike, it may have changed.

- **License:** GPLv3. Bundled libraries (Babylon.js, Blockly, Ace, Skulpt, Ammo.js and others) keep their own licenses.
- **Deployment:** static files in `public/` (about 216 MB). Must be served over HTTP(S), not from `file://`.
- **German UI:** selectable in the language menu, stored in the browser's localStorage under `LANG`. The challenge dialogs ("COMPLETED!", "Try Again!") are hard-coded in English.
- **URL parameters** read by `public/index.html`:
  - `worldJSON`: URL of a world configuration JSON
  - `robotJSON`: URL of a robot configuration JSON
  - `filterBlocksJSON`: URL of a block filter JSON (`deny` / `show` for categories and blocks, see `public/samples/filter.json`)
  - `worldScripts`: comma-separated names of extra world scripts from `public/js/worlds/extra/`

  External JSON URLs must be HTTPS and allow CORS (see `public/genURL.html`).
- **Basic Challenges:** defined in `public/js/worlds/extra/challenges_basic.js` with world files in `public/worlds/challenges_basic/*.json`. Groups: Basic (move, turn), Sleep, Maze, Dungeon, Loops, Conditions (color sensor), Abstraction (functions).
- **Automatic success detection:** in `challenges_basic`, the world checks whether the robot stopped in the target area (some challenges also require all target areas, or a maximum number of blocks). On success it shows a dialog with a fixed **completion code** per challenge (for example `UNICORN`, `ELEPHANT`). The codes are visible in the upstream source, so they are a convenience check, not a security feature.
- **External assets:** the challenge world files reference 5 unique images on `https://files.aposteriori.com.sg` (511 references in total).
- **Saving:** "Save" downloads a ZIP containing `gearsBlocks.xml`, `main.py` (or the Python files), `gearsRobot.json` and `meta.json`. GearsBot can load such a ZIP again. It also autosaves to localStorage.
- **No analytics** found in `index.html` or `js/`.

## 3. Requirements

### 3.1 Hosting

- GearsBot is served by our own server. Participants' browsers must not contact third-party servers when using GearsBot or a task's world. This includes the images on files.aposteriori.com.sg: mirror them and rewrite the URLs.
- Reproducible: the deployed GearsBot is built from an exact upstream commit, pinned in the repo. The server never fetches code from GitHub at runtime.
- Built in CI as part of the linux/amd64 image or as a separate image, like the rest of the stack.
- **Origin (decision for the ADR, proposed default):** serve GearsBot on its own subdomain `sim.checkermint.ch`, not under a path of checkermint.ch. Reason: third-party JavaScript then runs isolated from the Checkermint session and cookies. Consequences: one new DNS record (only add it, never touch other records of the domain), and world, robot and filter JSON served by Checkermint need a CORS header that allows exactly that origin. Document the alternative (same origin under `/sim/gears/`) and why it was not chosen.
- Do not describe or list any other existing subdomains of checkermint.ch in issues, ADRs or docs.
- Long-term caching for GearsBot's static files, with cache busting when the pinned version changes.
- A suitable Content Security Policy for the simulator origin.
- License: keep upstream's LICENSE, and add a short note with the link to the upstream source and the pinned commit to the imprint or an "about" page.

### 3.2 Keeping it up to date

- Pinned upstream commit in one place (for example `sim/gears/UPSTREAM` with the commit SHA).
- Avoid a fork. If we must change upstream files, keep the changes as small patch files that are applied at build time and documented. Prefer solving things outside GearsBot (for example asset mirroring as a build step).
- A scheduled GitHub Actions workflow (monthly) compares the pinned commit with upstream `master`. If there is something new, it opens a PR that bumps the pin, with the upstream commit log in the description.
- CI for such a PR: build, check that patches still apply, check that mirrored assets are complete, and check that the challenge list and completion codes can still be parsed. Report changed challenge worlds or codes in the PR.
- kreuzlin merges these update PRs himself (third-party code and deployment).
- Updating GearsBot never changes existing task versions (see 3.3).

### 3.3 Tasks linked to GearsBot

- A task version can optionally have a simulator configuration: world JSON, optional robot JSON, optional block filter JSON, and optional extra world scripts.
- The JSON files are **copied into the task version** when it is created and are immutable with it, like all task version content. A later GearsBot update must not change what a participant who pinned that version sees.
- These files are served by Checkermint without login (needed for CORS fetches from the simulator) under unguessable URLs. They contain task content only, never personal data.
- The task page shows a button "Im Simulator öffnen" that opens GearsBot in a new tab with the right URL parameters.
- Find out during the spike how to open a single Basic Challenge directly (most likely `worldScripts=challenges_basic` plus a world configuration that selects the challenge's world file) and document it.
- Default UI language in GearsBot should be German for our users. Prefer a solution without patching (for example setting `LANG` before GearsBot starts). If that is not possible, a minimal patch is acceptable.

### 3.4 Submissions for GearsBot tasks

- Imported challenges get two submission requirements:
  1. **Completion code** (`text`, required): the code GearsBot shows on success.
  2. **GearsBot project** (`file`, `.zip`, optional): the saved project.
- Store the expected completion code with the task version (internal, never shown to participants).
- In the review form, show the coach whether the entered code matches ("Code stimmt" / "Code stimmt nicht"). The coach still decides and gives the stars. No automatic approval.
- If a ZIP is uploaded: validate it (size limit, expected file names only, no path traversal), and show `main.py` with syntax highlighting in the review form, so the coach can see the solution without opening GearsBot.
- Participants may solve challenges as a team, as before each submits separately.

### 3.5 Importing the Basic Challenges

- A Django management command imports the challenges from the pinned GearsBot version: one task per challenge, in the order of `challenges_basic.js`. It is idempotent: running it again does not create duplicates. If an upstream world or code has changed, it creates a new **draft** version instead of changing a published one.
- All imported tasks start as **drafts**. Coaches review and publish them.
- Default topic: "Code" (create it if missing).
- German titles, derived from the upstream group names. Proposal:

| Upstream group | German title prefix | Base points | Minimum level in "Code" |
|---|---|---|---|
| Basic (Move, Turn) | Grundlagen | 10 | 1 |
| Sleep | Warten | 10 | 1 |
| Maze | Labyrinth | 15 | 2 |
| Dungeon | Verlies | 15 | 2 |
| Loops | Schleifen | 20 | 3 |
| Conditions | Bedingungen | 25 | 4 |
| Abstraction | Funktionen | 30 | 5 |

  kreuzlin and the coaches will adjust points and levels in the admin afterwards.
- Generated German instructions per task: a short standard text on how to work with GearsBot (open, solve, note the completion code, optionally save and upload the ZIP), plus the challenge title. Coaches will rewrite them.
- One block filter per group, so beginners only see the blocks they need. Proposal: Grundlagen and Warten: movement and wait blocks only. Labyrinth and Verlies: plus turns. Schleifen: plus loops. Bedingungen: plus sensors and logic. Funktionen: plus functions and variables. Verify how the filter matches category names when the UI is in German.
- No hints are imported. Coaches add them.

### 3.6 Documentation

- A short German guide for coaches in `docs/`: how GearsBot tasks work, how to review them, how to create a new GearsBot task from an own world, and how to update GearsBot.
- Update `docs/STATUS.md`, `docs/architecture.md` and `docs/deployment.md`.

## 4. Out of scope (later, ask first)

- A button that submits the project directly from GearsBot to Checkermint (would need a postMessage bridge or a small patch).
- Automatic approval based on the completion code.
- Other GearsBot worlds (line following, sensor challenges, FLL and WRO missions, arena, sumo).
- Coach-built custom worlds beyond uploading a JSON in the admin.
- Translating GearsBot's built-in English dialogs.

## 5. Process

- Start with a **spike** (no features): verify the facts in section 2, find out how to deep-link a single challenge, how the completion codes map to the world files, and how the block filter behaves in German. Then write ADRs for:
  1. Hosting origin and build (subdomain vs. path, image layout, caching, CSP)
  2. Pinning and update process (including the patch policy)
  3. Simulator configuration on task versions and the completion code check
  4. License and attribution (GPLv3)
- Show kreuzlin the ADRs and the issue plan before building.
- Then one issue per PR, in this order: hosting and build, update workflow, simulator configuration on tasks, submissions and review, import command, coach guide.
- As before: migrations and changes to server, DNS, Caddy or deployment are merged by kreuzlin. Update PRs from the scheduled workflow too.
  - Clarified by kreuzlin on 2026-11-21, after the spike: merging follows the current rule in CLAUDE.md (Claude merges once green and asks first for destructive migrations, server/DNS/Caddy/secrets/deploy changes and CI changes that weaken checks). Only the update PRs from the scheduled workflow are merged by kreuzlin (ADR 0020).
- Test the simulator once on the devices used in the club (3D performance) before publishing the first tasks.
