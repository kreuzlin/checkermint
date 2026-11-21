# GearsBot spike (2026-11-21)

Results of the spike in [`GEARSBOT_BRIEF.md`](GEARSBOT_BRIEF.md), section 5.
Checked against upstream https://github.com/QuirkyCort/gears, branch
`master` at `c0549600a26f9811906b4e02fd9246fe2413a072` (2026-11-16, still
the head of `master` on 2026-11-21). Decisions based on it: ADRs 0019–0022.

## Facts from the brief, section 2

| Fact | Result |
|---|---|
| License GPLv3, bundled libraries keep their own | Confirmed (`LICENSE`, GPLv3, © 2020 Cort Wee) |
| Static files in `public/`, about 216 MB | Confirmed: 215 MB. Several library versions side by side (Blockly 9.0.0, 12.3.0, 12.5.1; Ace 1.4.10, 1.11.2; Babylon 4.1.0, 4.2.1) |
| German UI via localStorage `LANG` | Confirmed: `js/msg.js` reads `localStorage.LANG` once at load, default `en`; the language menu writes it and reloads |
| Challenge dialogs hard-coded in English | Confirmed ("COMPLETED!", "Try Again!", the "Mission" texts). The "What's New" dialog (English, links to YouTube) opens automatically until `localStorage.whatsNew` is set |
| URL parameters `worldJSON`, `robotJSON`, `filterBlocksJSON`, `worldScripts` | Confirmed (`public/index.html`). Loaded after the 3D scene is ready: world scripts first, then world, robot and filter |
| External JSON must be HTTPS with CORS | Partly: the code just calls `fetch(url)`, so relative and same-origin URLs work too. HTTPS is only advice in `genURL.html`. Cross-origin URLs need CORS |
| Basic Challenges in `challenges_basic.js` and `worlds/challenges_basic/*.json` | Confirmed: **61** challenges, 61 world files, groups as in the brief |
| Success detection and completion codes | Confirmed, details below. 61 challenges, **61 distinct codes** |
| 5 images on `files.aposteriori.com.sg`, 511 references | Confirmed for the challenge worlds. **New:** `challenges_basic.js` itself loads the default robot (`twBasic`) from `files.aposteriori.com.sg` (a JSON file). Other worlds in GearsBot's menu reference 27 more files there and one file on `raw.githubusercontent.com`. In total 33 files, about 0.8 MB |
| Save: ZIP with `gearsBlocks.xml`, `main.py`, `gearsRobot.json`, `meta.json` | Confirmed for block mode. **New:** if Python was edited, the ZIP contains the participant's Python files with their own names instead of the generated `main.py` |
| No analytics | Confirmed: no analytics or trackers in `index.html` or `js/`. Only links (About, Help, What's New), nothing loaded automatically besides the external assets above |

## Opening a single challenge

The 61 world files are worlds of type `custom` (`{"worldName": "custom",
"options": {…}}`). `challenges_basic` is a wrapper world: its option
`jsonFile` names the challenge world file, and its success check and
completion code are chosen with `jsonFile.includes('<file name>')`.

A deep link to one challenge therefore needs:

- `worldScripts=challenges_basic`
- `worldJSON=<URL of a wrapper JSON>` with
  `{"worldName": "challenges_basic", "options": {"jsonFile": "<URL of the challenge world file>", "useDefaultRobot": true}}`

**The URL in `jsonFile` must end with the upstream file name** (for example
`…/maze-1.json`). Otherwise no success check matches and the challenge never
ends. A copy served by Checkermint works if its URL keeps that name.

With `useDefaultRobot` (default `true`) the world loads its own robot
(`twBasic`), so imported challenges need no `robotJSON`.

## Completion codes

- `this.render` in `challenges_basic.js` is an `if … else if` chain over
  `jsonFile.includes('<file>.json')`; each branch calls
  `renderIntersectOne(delta, mesh, CODE, interacts, blocksLimit)` or
  `renderIntersectMulti(delta, meshes, stopRequired, CODE, effect, interacts, blocksLimit)`.
- A parser that reads the option list (title, file, `?v=` hash) and the
  render chain with the code and the optional block limit finds all 61
  challenges, each with a code. The spike's parser becomes the CI check of
  ADR 0020. The codes are not listed in this repository.
- Codes are mostly upper case but not all (some are mixed case, one has a
  space). The comparison in the review form must ignore case and extra
  spaces (ADR 0021).
- Block limits (20 challenges) are counted on the block workspace. A
  participant who writes Python instead is not limited by them.

## Block filter

- The filter matches **category `id`s and block `type`s**, not the shown
  names. Ids are English and fixed (`Motion`, `Control`, `Loops`, …), so the
  filter works the same with the German UI.
- `public/samples/filter.json` is out of date (`"Pen (Experimental)"` is no
  id any more).
- The toolbox has two hidden beginner categories made for these
  challenges: `Movement` (`tw_fwd`, `tw_rev`, `tw_left`, `tw_right`) and
  `Conditions` (`controls_if`). `tw_color` is in `Sensors`, `sleep` in
  `Control`, `controls_repeat_ext` in `Loops`; variables and functions are
  the dynamic categories `Variables` and `Functions`.
- Semantics: `deny.categories` hides a category and removes its blocks;
  `show.blocks` keeps single blocks of a denied category (the category stays
  visible with only those blocks); `show.categories` un-hides a category,
  which is the only way to show the hidden-by-default `Movement` and
  `Conditions`. `deny.blocks` removes only the
  **first** block of that type (three types appear in two categories), so
  filters should work with categories plus `show.blocks`.
- **The brief's proposal does not fit the first group:** "Basic: Move and
  Turn 1–3" need turn blocks, so "Grundlagen" needs turns, not only from
  "Labyrinth" on. Corrected proposal in ADR 0021.

## German as the default language

`js/msg.js` reads `LANG` when it is loaded. A small start page of our own on
the simulator origin can set `LANG=de` (and `whatsNew`) in localStorage if
they are not set yet and then forward to GearsBot with the same query
string. No upstream file has to change. A participant can still switch the
language in the menu.

## Other observations

- `worldScripts` are loaded with `?v=<Date.now()>`, so these scripts are never
  taken from the browser cache. That is fine (`challenges_basic.js` is about
  40 KB).
- GearsBot autosaves the block program in localStorage (`blocklyXML`,
  `gearsPythonCode`), for the whole origin. The next challenge opens with
  the previous program. The privacy page must mention this local storage.
- The simulator runs Python with Skulpt (compiles to JavaScript and runs it
  with `eval`) and physics with Ammo.js (WebAssembly). This matters for the
  CSP (ADR 0019).
