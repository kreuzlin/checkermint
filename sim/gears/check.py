"""GearsBot challenge bundle and checks (ADR 0020).

Usage (standard library only):

  python check.py bundle <upstream checkout> [<out dir>]
      Parse the Basic Challenges of the checkout and write the bundle
      (default: challenges_basic/ next to this file): challenges.json and
      the world files with mirrored URLs rewritten to /mirror/<name>.

  python check.py verify <upstream checkout>
      Fail if the committed bundle differs from what `bundle` would write.

  python check.py report <old bundle dir> <new bundle dir>
      Print a Markdown table of added, removed and changed challenges.

  python check.py mirror-add <upstream checkout>
      Download files of mirrored hosts that have no mirror entry yet into
      mirror/ and add them to mirror.json; print them as Markdown.

This file is part of Checkermint's GearsBot packaging and licensed under
the GNU GPL v3 (see LICENSE in this folder).
"""

import filecmp
import hashlib
import html
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build  # noqa: E402

SCRIPT = "public/js/worlds/extra/challenges_basic.js"
WORLDS = "public/worlds/challenges_basic"
BUNDLE = HERE / "challenges_basic"
OPTION = re.compile(
    r"\['([^']+)',\s*'worlds/challenges_basic/([\w-]+\.json)\?v=(\w+)'\]"
)
BRANCH = re.compile(r"jsonFile\.includes\('([\w-]+\.json)'\)\)\s*\{")


class ParseError(Exception):
    pass


def call_args(text, open_paren):
    """Argument text of the call whose '(' is at text[open_paren]."""
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i]
    raise ParseError("unbalanced parentheses")


def flatten(args):
    """Collapse nested [...] and {...} so top-level arguments are visible."""
    previous = None
    while args != previous:
        previous = args
        args = re.sub(r"\{[^{}]*\}", "{}", args)
        args = re.sub(r"\[[^\[\]]*\]", "[]", args)
    return args


def branches(source, function):
    """{file name: branch body} of an `if (jsonFile.includes(...))` chain."""
    start = source.find(f"this.{function} = function")
    if start < 0:
        raise ParseError(f"this.{function} not found")
    chain = source[start:]
    matches = list(BRANCH.finditer(chain))
    result = {}
    for match, following in zip(matches, [*matches[1:], None], strict=True):
        end = following.start() if following else len(chain)
        result.setdefault(match.group(1), chain[match.end() : end])
    return list(result.items())


def success_rule(body):
    """Completion code and block limit of one render branch."""
    match = re.search(r"self\.(renderIntersectOne|renderIntersectMulti)\(", body)
    if not match:
        raise ParseError("no renderIntersect call")
    args = flatten(call_args(body, match.end() - 1))
    strings = [
        s
        for s in re.findall(r"'([^']*)'", args)
        if s not in ("color", "hide") and not s.startswith("worldBaseObject_")
    ]
    if len(strings) != 1:
        raise ParseError(f"expected one completion code, found {strings}")
    limit = re.search(r",\s*(-?\d+)\s*$", args.strip())
    return strings[0], int(limit.group(1)) if limit else None


def mission_text(body):
    """Plain text of the mission dialog of one displayMission branch."""
    literals = re.findall(r"'((?:[^'\\]|\\.)*)'", body.split("}", 1)[0])
    text = "".join(s.replace("\\'", "'") for s in literals)
    paragraphs = [
        html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in text.split("</p>")
    ]
    return "\n\n".join(p for p in paragraphs if p)


def first_match(file_name, names):
    """The branch GearsBot uses: the first whose name is in the file path."""
    for name in names:
        if name in f"worlds/challenges_basic/{file_name}":
            return name
    return None


def parse(checkout):
    """List of challenges in upstream order; raises ParseError."""
    source = (checkout / SCRIPT).read_text()
    options = OPTION.findall(source)
    if not options:
        raise ParseError("no challenge options found")
    render = branches(source, "render")
    missions = dict(branches(source, "displayMission"))
    render_names = [name for name, _ in render]
    rules = dict(render)
    challenges = []
    seen = set()
    for order, (title, file_name, version) in enumerate(options, start=1):
        if file_name in seen:
            raise ParseError(f"{file_name} listed twice")
        seen.add(file_name)
        matched = first_match(file_name, render_names)
        if matched != file_name:
            raise ParseError(f"{file_name}: success check matches {matched!r}")
        world = json.loads((checkout / WORLDS / file_name).read_text())
        if not {"worldName", "options"} <= world.keys():
            raise ParseError(f"{file_name}: not a world file")
        code, limit = success_rule(rules[file_name])
        challenges.append(
            {
                "order": order,
                "title": title,
                "group": file_name.split("-")[0],
                "file": file_name,
                "version": version,
                "code": code,
                "blocks_limit": limit,
                "mission": mission_text(missions.get(file_name, "")),
            }
        )
    orphans = set(rules) - seen
    if orphans:
        raise ParseError(f"success checks without a challenge: {sorted(orphans)}")
    return challenges


def write_bundle(checkout, out):
    sha = (HERE / "UPSTREAM").read_text().strip()
    urls = build.load_mirror(HERE)
    challenges = parse(checkout)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.json"):
        old.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        worlds = Path(tmp)
        for challenge in challenges:
            name = challenge["file"]
            (worlds / name).write_bytes((checkout / WORLDS / name).read_bytes())
        build.rewrite(worlds, urls)
        for challenge in challenges:
            name = challenge["file"]
            (out / name).write_bytes((worlds / name).read_bytes())
    data = {"upstream": sha, "challenges": challenges}
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    (out / "challenges.json").write_text(text)
    return challenges


def verify(checkout):
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        challenges = write_bundle(checkout, fresh)
        committed = {p.name for p in BUNDLE.glob("*.json")}
        expected = {p.name for p in fresh.glob("*.json")}
        _, mismatch, errors = filecmp.cmpfiles(
            fresh, BUNDLE, sorted(expected), shallow=False
        )
        problems = sorted(set(mismatch) | set(errors) | (committed ^ expected))
    if problems:
        sys.exit(
            "check.py: the committed bundle does not match the pinned commit "
            f"({', '.join(problems)}). Run: python check.py bundle <checkout>"
        )
    print(f"Bundle OK: {len(challenges)} challenges, codes and worlds match.")


def report(old_dir, new_dir):
    def load(directory):
        path = directory / "challenges.json"
        if not path.exists():
            return {}
        return {c["file"]: c for c in json.loads(path.read_text())["challenges"]}

    old, new = load(old_dir), load(new_dir)
    rows = []
    for name in sorted(old.keys() | new.keys()):
        before, after = old.get(name), new.get(name)
        if before is None:
            rows.append((name, after["title"], "neu"))
            continue
        if after is None:
            rows.append((name, before["title"], "entfernt"))
            continue
        changes = []
        if (old_dir / name).read_bytes() != (new_dir / name).read_bytes():
            changes.append("Welt")
        for key, label in (
            ("code", "Code"),
            ("blocks_limit", "Block-Limit"),
            ("title", "Titel"),
            ("mission", "Missionstext"),
        ):
            if before[key] != after[key]:
                changes.append(label)
        if changes:
            rows.append((name, after["title"], ", ".join(changes)))
    if not rows:
        print("Keine Änderungen an den Basic Challenges.")
        return
    print("| Datei | Challenge | Geändert |")
    print("|---|---|---|")
    for name, title, change in rows:
        print(f"| `{name}` | {title} | {change} |")


def mirror_add(checkout):
    manifest_path = HERE / "mirror.json"
    manifest = json.loads(manifest_path.read_text())
    known = {entry["url"] for entry in manifest["files"]}
    names = {entry["name"] for entry in manifest["files"]}
    pattern = re.compile(
        r"https?://(?:"
        + "|".join(re.escape(h) for h in build.MIRRORED_HOSTS)
        + r")/[^\s\"'<>)\\]*"
    )
    found = set()
    for path in (checkout / "public").rglob("*"):
        if path.is_file() and path.suffix.lower() in build.TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8", errors="surrogateescape")
            found.update(pattern.findall(text))
    added = []
    for url in sorted(found - known):
        name = url.rsplit("/", 1)[1]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in names:
            sys.exit(f"check.py: cannot mirror {url} (name {name!r})")
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
        (HERE / "mirror" / name).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        manifest["files"].append({"url": url, "name": name, "sha256": digest})
        names.add(name)
        added.append((url, name, len(content)))
    manifest["files"].sort(key=lambda entry: entry["url"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for url, name, size in added:
        print(f"- `{name}` ({size} Bytes) von {url}")


def main():
    args = sys.argv[1:]
    try:
        if args[:1] == ["bundle"] and len(args) in (2, 3):
            out = Path(args[2]) if len(args) == 3 else BUNDLE
            challenges = write_bundle(Path(args[1]), out)
            print(f"Bundle written: {len(challenges)} challenges -> {out}")
        elif args[:1] == ["verify"] and len(args) == 2:
            verify(Path(args[1]))
        elif args[:1] == ["report"] and len(args) == 3:
            report(Path(args[1]), Path(args[2]))
        elif args[:1] == ["mirror-add"] and len(args) == 2:
            mirror_add(Path(args[1]))
        else:
            sys.exit(__doc__)
    except ParseError as error:
        sys.exit(f"check.py: cannot parse challenges_basic.js: {error}")


if __name__ == "__main__":
    main()
