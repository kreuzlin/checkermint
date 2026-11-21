# 0022: GearsBot license (GPLv3) and attribution

- Status: proposed
- Date: 2026-11-21

## Context

GearsBot is GPLv3 (© 2020 Cort Wee); its bundled libraries (Babylon.js,
Blockly, Ace, Skulpt, Ammo.js, jQuery, JSZip and others) keep their own
licenses. Serving GearsBot's JavaScript to participants' browsers is
conveying it under the GPL. The brief (section 3.1) asks us to keep
upstream's LICENSE and to name the upstream source and the pinned commit on
the imprint or an "about" page. The Checkermint repository is public and has
no license file.

This ADR is a technical decision, not legal advice.

## Decision

1. **Unchanged upstream files.** The `sim` image serves upstream `public/`
   as it is, with upstream's `LICENSE` copied to `/v/<sha>/LICENSE` and the
   libraries' own license files where upstream ships them. GearsBot's own
   "About" dialog (credits) stays as it is.
2. **Corresponding source.** Everything needed to rebuild exactly what we
   serve is public: the upstream commit (`sim/gears/UPSTREAM`), our patch
   files (none planned), the mirror manifest and files, the rewrite step and
   the start page, all in `sim/gears/` of this public repository.
3. **Our files under `sim/gears/`** (patches, build and check scripts, the
   start page) are licensed **GPLv3** too: `sim/gears/LICENSE` (copy of
   upstream's) and a line in `sim/gears/README.md`. This keeps anything that
   might count as a modified version of GearsBot under its license.
4. **Checkermint itself is a separate program.** It links to the simulator
   and serves JSON world files to it over HTTP; it does not include,
   import or run GearsBot code. GPLv3 does not apply to the Django app.
   Task world files are content, not code.
5. **Attribution in Checkermint.** The imprint (`/impressum/`) gets a section
   "Simulator":
   > Der Simulator ist GearsBot von Cort Wee (A Posteriori), lizenziert
   > unter der GNU GPL v3. Quellcode: github.com/QuirkyCort/gears, bei uns
   > eingesetzt in Version `<short-sha>` (Link auf den Commit). Unsere
   > Anpassungen: github.com/kreuzlin/checkermint, Ordner `sim/gears`.
   The short SHA comes from `sim/gears/UPSTREAM` (read once at start,
   shown as text). The same note, shorter, sits in the simulator's start
   page while it forwards.
6. **Mirrored assets.** Their rights are noted in `sim/gears/README.md`
   once upstream answers (ADR 0019, section 3). Until then they are used as
   GearsBot uses them, unchanged.

## Consequences

- No change to how Checkermint is licensed.
- Every update PR that changes the pin also changes the version shown on
  the imprint automatically.
- If we ever change GearsBot files (patches), those changes must be
  published, which they are by being in this repository.
