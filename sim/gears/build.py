"""Assemble the GearsBot site served by the sim image (ADR 0019, 0020).

Usage: python build.py <upstream checkout> <sim/gears dir> <output dir>

Standard library only. Steps:

1. Check that the checkout is exactly the commit in UPSTREAM.
2. Check every mirrored file against mirror.json (SHA-256).
3. Copy upstream public/ to <output>/v/<short-sha>/ and rewrite every
   mirrored URL to /mirror/<name>.
4. Fail if a URL of a mirrored host is left in the copied files.
5. Write the start page, robots.txt and the Caddy snippet with the version.

This file is part of Checkermint's GearsBot packaging and licensed under
the GNU GPL v3 (see LICENSE in this folder).
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Hosts whose files we mirror. No URL of these hosts may remain.
MIRRORED_HOSTS = ("files.aposteriori.com.sg", "raw.githubusercontent.com")
# Text files in which URLs are rewritten.
TEXT_SUFFIXES = {".html", ".js", ".json", ".css", ".xml"}
SHORT = 12


def fail(message):
    sys.exit(f"build.py: {message}")


def check_commit(checkout: Path, sha: str):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        fail(f"UPSTREAM must be a full commit SHA, got {sha!r}")
    head = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != sha:
        fail(f"checkout is at {head}, UPSTREAM pins {sha}")


def load_mirror(sim_dir: Path) -> dict[str, str]:
    """Return {source URL: local name}, after checking every file."""
    manifest = json.loads((sim_dir / "mirror.json").read_text())
    urls = {}
    names = set()
    for entry in manifest["files"]:
        name = entry["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in names:
            fail(f"bad or duplicate mirror name {name!r}")
        names.add(name)
        path = sim_dir / "mirror" / name
        if not path.is_file():
            fail(f"mirrored file missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            fail(f"checksum mismatch for {name}")
        urls[entry["url"]] = name
    extra = {p.name for p in (sim_dir / "mirror").iterdir()} - names
    if extra:
        fail(f"files in mirror/ without manifest entry: {sorted(extra)}")
    return urls


def rewrite(public: Path, urls: dict[str, str]) -> int:
    """Rewrite mirrored URLs in place; return the number of replacements."""
    # Longest first, so no URL is a prefix of another one being replaced.
    ordered = sorted(urls, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(u) for u in ordered))
    leftover = re.compile(
        r"https?://(?:"
        + "|".join(re.escape(h) for h in MIRRORED_HOSTS)
        + r")/[^\s\"'<>)]*"
    )
    count = 0
    problems = []
    for path in sorted(public.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        new, n = pattern.subn(lambda m: "/mirror/" + urls[m.group(0)], text)
        if n:
            path.write_text(new, encoding="utf-8", errors="surrogateescape")
            count += n
        for m in leftover.finditer(new):
            problems.append(f"{path.relative_to(public)}: {m.group(0)[:100]}")
    if problems:
        fail(
            "URLs of mirrored hosts without a mirror entry:\n  " + "\n  ".join(problems)
        )
    return count


def write_site(sim_dir: Path, out: Path, short: str):
    start = sim_dir / "start"
    for name in ("index.html", "robots.txt"):
        shutil.copy(start / name, out / name)
    js = (start / "start.js").read_text().replace("__GEARS_VERSION__", short)
    if "__GEARS_VERSION__" in js or short not in js:
        fail("start.js: version placeholder not replaced")
    (out / "start.js").write_text(js)
    # Imported by the image's Caddyfile: the current version's path.
    (out / "version.caddy").write_text(f"@current path /v/{short}/*\n")
    (out / "VERSION").write_text(short + "\n")


def main():
    if len(sys.argv) != 4:
        fail("usage: build.py <upstream checkout> <sim/gears dir> <output dir>")
    checkout, sim_dir, out = (Path(a) for a in sys.argv[1:])
    sha = (sim_dir / "UPSTREAM").read_text().strip()
    check_commit(checkout, sha)
    short = sha[:SHORT]
    patches = (
        sorted((sim_dir / "patches").glob("*.patch"))
        if (sim_dir / "patches").is_dir()
        else []
    )
    for patch in patches:
        for args in (["--check"], []):
            subprocess.run(
                ["git", "-C", str(checkout), "apply", *args, str(patch.resolve())],
                check=True,
            )
    urls = load_mirror(sim_dir)
    if out.exists():
        shutil.rmtree(out)
    target = out / "v" / short
    shutil.copytree(checkout / "public", target)
    shutil.copy(checkout / "LICENSE", target / "LICENSE")
    count = rewrite(target, urls)
    shutil.copytree(sim_dir / "mirror", out / "mirror")
    write_site(sim_dir, out, short)
    print(
        f"GearsBot {short}: {len(patches)} patches, {len(urls)} mirrored files, {count} URLs rewritten"
    )


if __name__ == "__main__":
    main()
