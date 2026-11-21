# Design originals

Originals of the logo and other artwork. This folder is **not served** and
not part of the Docker image (`.dockerignore`). Web assets are generated from
it by a script and never edited by hand.

## Generating the web assets

```bash
uv run python design/generate_assets.py
```

Writes `core/static/core/brand/`:

| File | From | Used for |
|---|---|---|
| `logo-header.svg` | `logo/CHECKERMINT_Header.svg` | Logo in the site header (dark background) |
| `icon.svg` | `logo/CHECKERMINT_Icon.svg` | SVG favicon |
| `favicon-32.png` | `logo/CHECKERMINT_Icon_512.png` | PNG favicon fallback |
| `apple-touch-icon.png` | `logo/CHECKERMINT_Icon_512.png` | iOS home screen (180 px) |

Badge images are no longer generated here: coaches upload them in the
badge admin (ADR 0018, #120), where they are cropped, centred and saved as
512 px PNGs. `badges/` keeps the originals and prompts as an archive.

SVGs are copied without editor metadata (Inkscape/Sodipodi), PNGs are resized
and saved without metadata. The SVGs contain the lettering as paths, so no
font files are needed (no external requests). Commit the generated files.

## Sources and usage rights

| File(s) | Source / author | Rights |
|---|---|---|
| `badges/*.png` (eight badges: Erste LED, Code-Starter, Greifarm, Sensor-Profi, Konstrukteur/in, Durchhalter/in, Linienfolger, Motor) | Delivered by the maintainer (kreuzlin) on 2026-11-21. Created by the maintainer with ChatGPT (image generation) from the prompts in [`badges/PROMPT.md`](badges/PROMPT.md) | Released by the maintainer for Checkermint; AI-made artwork allowed (maintainer's decision 2026-11-19, brief section 11) |
| `logo/CHECKERMINT_*` (logo package: header, portrait logo dark/light/transparent, icon) | Delivered by the maintainer (kreuzlin) on 2026-11-19. Created by the maintainer with an AI image tool, then vectorised (see `logo/CHECKERMINT_README.txt`, which came with the package) | Released by the maintainer for Checkermint; the maintainer decided on 2026-11-19 that artwork made with AI tools may be used (brief, section 11) |

Not in the repository: the RoboChallenge 2027 flyer that the maintainer gave
as the style reference for the dark "hackathon" theme (dark petrol, glowing
panels), in mint instead of the flyer's colours.

Colours of the logo, used as tokens in `core/static/core/css/site.css`:
petrol `#020d16`, `#031b23`, `#072a33`, `#0a3640`; mint `#a6fff9`,
`#76fff5`, `#36f4e4`, `#00dcad`; ice white `#f5ffff`.

Badges without an image show the mint hexagon placeholder.
