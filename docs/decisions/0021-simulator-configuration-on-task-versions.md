# 0021: Simulator configuration on task versions, completion code check

- Status: accepted (maintainer, 2026-11-21)
- Date: 2026-11-21

## Context

[`GEARSBOT_BRIEF.md`](../GEARSBOT_BRIEF.md), sections 3.3–3.5: a task
version can be linked to a GearsBot world; the JSON files are copied into
the version and immutable with it (ADR 0010); they are served without login
under unguessable URLs; imported challenges get a completion code
requirement and an optional project ZIP; the review form shows whether the
code matches. Spike results: [`gearsbot-spike.md`](../gearsbot-spike.md).

Spike findings that shape this:

- A single challenge opens with `worldScripts=challenges_basic` and a
  wrapper world JSON whose `options.jsonFile` points to the challenge world
  file. **That URL must end with the upstream file name** (`maze-1.json`),
  because GearsBot picks the success check with `jsonFile.includes(…)`.
- `fetch()` in GearsBot accepts any URL; ours are cross-origin
  (ADR 0019), so they need CORS.
- The block filter matches English category ids and block types, so it
  works with the German UI.

## Decision

### 1. Models (app `tasks`)

- **`SimulatorConfig`**, one-to-one with `TaskVersion`, optional (a
  version without it is a normal task):
  - `world_scripts` (comma-separated names, validated against
    `^[a-z0-9_]+$`, e.g. `challenges_basic`),
  - `expected_code` ("Erwarteter Code", internal; blank = no check),
  - `token` (random, 32 URL-safe characters, generated, never edited;
    copied versions get a **new** token),
  - admin labels in German, help texts for coaches.
- **`SimulatorFile`**, child of the config, built like `TaskRequirement`
  and `Hint` on `VersionChild` (immutable with a published version,
  ADR 0010):
  - `role`: `world` ("Welt"), `challenge_world` ("Challenge-Welt"),
    `robot` ("Roboter"), `filter` ("Blockauswahl"); at most one per role;
  - `filename`: the name in the URL, `^[A-Za-z0-9_-]+\.json$`, unique per
    config. For a challenge world it is the upstream file name;
  - `content`: `JSONField`, validated as a JSON object, at most 2 MB.
    JSON in the database instead of files in the media volume: these are
    small, task content only, need no access check, and are copied with the
    version in one transaction like requirements and hints.
- `create_draft` (ADR 0010) copies the config and its files into the new
  draft (new token). Both models share the immutability guard of
  requirements and hints (abstract base `VersionBound`, #144).
- **References between files** (decided in #144): a JSON string value
  `"sim-file:<filename>"` stands for the absolute URL of that file of the
  same version and is replaced when the file is served. Stored files
  therefore contain no host name and no token: they work locally and live,
  the import command needs no request, and copies need no rewriting. The version preview in the admin shows the
  "Im Simulator öffnen" button too.
- Coaches edit a draft's config as inlines on the version admin
  ("Simulator (GearsBot)" and "Simulator-Dateien"): world scripts, expected
  code, and per file the role, the file name and a JSON upload or pasted
  JSON (the upload fills an empty file name). Published
  versions are read-only as before.

### 2. Serving the files

- `GET /sim/<token>/<filename>` (app `tasks`, no login): looks up
  `SimulatorFile` by config token and file name; returns the JSON with
  `Content-Type: application/json`,
  `Access-Control-Allow-Origin: <SIMULATOR_URL origin>`,
  `Cache-Control: public, max-age=3600` for published versions and
  `no-store` for drafts, `X-Robots-Tag` as everywhere. Unknown → 404.
- Visible for **published** versions of tasks that are not archived, and
  for drafts (the coach's preview needs them; the 32-character token is
  the protection, and the files hold task content only, never personal
  data). Archived tasks → 404.
- The token is in the URL path, not in a query string, and the simulator
  origin sends no referrer (ADR 0019).

### 3. The link "Im Simulator öffnen"

On the task page (and the admin preview), for versions with a config and
only when `SIMULATOR_URL` is set: a button that opens a new tab
(`target="_blank" rel="noopener"`) to

```
<SIMULATOR_URL>/?worldScripts=<scripts>&worldJSON=<abs URL of world>&robotJSON=<…>&filterBlocksJSON=<…>
```

with absolute, URL-encoded Checkermint URLs, only for the roles that exist.
For an imported challenge the `world` file is the wrapper
`{"worldName": "challenges_basic", "options": {"jsonFile": "<abs URL of the challenge_world file>", "useDefaultRobot": true}}`,
stored as `{"worldName": "challenges_basic", "options": {"jsonFile":
"sim-file:maze-1.json", "useDefaultRobot": true}}`; the view turns the
reference into the absolute URL, which ends with the upstream file name.

Shown to participants who may see the task (same rules as the task page),
also before "Aufgabe starten".

### 4. Submissions and the code check

- Imported challenges get two requirements (ADR 0011), keys fixed:
  1. `completion-code` – type `text`, "Completion-Code", required, help text
     "Den Code zeigt GearsBot, wenn du die Challenge geschafft hast.";
  2. `projekt` – type `file`, "GearsBot-Projekt (.zip)", optional,
     `options: {"extensions": [".zip"]}`.
- The review form shows next to the completion code answer **"Code stimmt"** (✓ and
  the word) or **"Code stimmt nicht"** (✗ and the word; not by colour
  alone) when the version's config has an `expected_code`. Comparison:
  both sides `casefold()`ed, inner whitespace collapsed, outer stripped.
  The coach still reviews and gives the stars; nothing is approved
  automatically. Which requirement is checked: the `text` requirement with
  key `completion-code`.
- `expected_code` is never rendered for participants: not on the task page,
  not in the submission form, not in the history, not on public profiles,
  not in the JSON files (tested). Coaches see it in the admin and the review
  form. It is a convenience check, not a secret: upstream publishes it.

### 5. Project ZIP

- A `file` requirement with `.zip` gets an extra validation step (a small
  handler in `submissions`): at most `UPLOAD_MAX_FILE_MB`; opened with
  `zipfile` without extracting; at most 50 entries, each at most 1 MB
  uncompressed and 5 MB in total (zip bombs); every name must be a plain
  file name (no `/`, `\`, `..`, absolute paths or drive letters) and one of
  `gearsBlocks.xml`, `gearsRobot.json`, `meta.json` or `*.py`
  (participants name their own Python files). Otherwise a German error
  message names the problem.
- The ZIP stays a private file (ADR 0009, 0014). For the review form the
  handler stores the text of the Python files (at most 200 KB together) in
  the item's `data`, read once on upload; the review form shows `main.py`
  first, then the other `.py` files, with Pygments highlighting like `code`
  requirements. The ZIP is never extracted to disk.

### 6. Import command

`manage.py import_gearsbot_challenges` reads the committed challenge bundle
(ADR 0020), not GearsBot itself:

- One `Task` per challenge, in bundle order, topic "Code" (created if
  missing), identified by a fixed slug `gearsbot-<file stem>`
  (e.g. `gearsbot-maze-1`), so re-running finds the same tasks.
- New task: unpublished task with one **draft** version: German title
  ("Labyrinth 1", from the group table in the brief, section 3.5, numbered
  as upstream, e.g. "Schleifen 2b"), base points and minimum level from the
  table, generated German instructions (standard text on how to work with
  GearsBot plus the challenge title), the two requirements, the config
  (`world_scripts=challenges_basic`, `expected_code`, files `world`
  (wrapper), `challenge_world` (bundle file, upstream name) and `filter`
  (the group's block filter)). No hints.
- Existing task: compares the latest version's challenge world content and
  expected code with the bundle. Equal → nothing. Different → if the latest
  version is a draft, it is updated; if it is published, a new draft is
  created (`create_draft`) with the new world and code and change note
  "GearsBot-Update: Welt/Code geändert". Published versions are never
  touched. Coaches' edits to title, instructions, points or level in later
  versions are kept (only the config is replaced).
- `--dry-run` lists what would happen. Output in English (for the
  operator), labels in German.
- Runs on the server only with the maintainer's OK (it writes;
  CLAUDE.md, Workflow).

### 7. Block filters per group

Stored in the bundle generator as fixed JSON, one per group (`filter` file
of each imported version; coaches can change it in a draft):

| Group | Visible blocks |
|---|---|
| Grundlagen (Basic: Move, Move and Turn) | `Movement` (forward, back, left, right) |
| Warten (Sleep) | + `sleep` |
| Labyrinth, Verlies | as Warten |
| Schleifen | + `controls_repeat_ext` |
| Bedingungen | + `Conditions` (if), `tw_color`, `logic_compare`, `logic_operation`, `logic_boolean` |
| Funktionen | + `Variables`, `Functions` |

Turns are in the first group already, unlike the brief's proposal:
"Basic: Move and Turn 1–3" need them (spike). Each filter denies all
categories except those listed and shows single blocks with `show.blocks`
(the spike explains why not `deny.blocks`). Checked by hand in the import
PR with the German UI; the exact JSON goes into the coach guide.

## Consequences

- One migration that only adds two tables (no OK needed by the CLAUDE.md
  merge rule, which applies to this brief too: maintainer's decision
  2026-11-21).
- Imported challenges keep working after GearsBot updates as long as the
  upstream file name stays the same; the update report (ADR 0020) says when
  it does not.
- The world files are public under unguessable URLs. If a coach puts
  something private into a world JSON, it would be reachable with the
  link; the admin help text says "nur Aufgabeninhalt, keine Personendaten".
- Python solutions are not limited by GearsBot's block limits; coaches see
  the code in the review form.
