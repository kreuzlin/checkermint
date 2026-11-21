"""Tests for check.py (run: python -m unittest discover -s sim/gears/tests)."""

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import check

SCRIPT = """
var challenges_basic = new function() {
  this.optionsConfigurations = [
    {
      option: 'jsonFile',
      options: [
        ['Basic: Move', 'worlds/challenges_basic/basic-1.json?v=aaaa1111'],
        ['Loops: Repeat 2', 'worlds/challenges_basic/loops-2.json?v=bbbb2222'],
      ]
    },
  ];
  this.displayMission = function() {
    if (self.options.jsonFile.includes('basic-1.json')) {
      $message = $(
        '<p>Move into the box.</p>' +
        '<p>Don\\'t give up!</p>'
      );
    } else if (self.options.jsonFile.includes('loops-2.json')) {
      $message = $('<p>Use a loop &amp; few blocks.</p>');
    }
  };
  this.render = function(delta){
    if (self.options.jsonFile.includes('basic-1.json')) {
      self.renderIntersectOne(delta, 'worldBaseObject_box0', 'UNICORN');
    } else if (self.options.jsonFile.includes('loops-2.json')) {
      self.renderIntersectMulti(
        delta,
        ['worldBaseObject_box1', 'worldBaseObject_box2'],
        true,
        'Salted Caramel',
        'hide',
        [{type: 'drop', trigger: 'a', move: 'b'}],
        6
      );
    }
  };
}
"""

WORLD = {"worldName": "custom", "options": {"imageURL": "x"}}


def make_checkout(root, script=SCRIPT, files=("basic-1.json", "loops-2.json")):
    extra = root / "public/js/worlds/extra"
    worlds = root / "public/worlds/challenges_basic"
    extra.mkdir(parents=True)
    worlds.mkdir(parents=True)
    (extra / "challenges_basic.js").write_text(script)
    for name in files:
        (worlds / name).write_text(json.dumps(WORLD))
    return root


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parses_codes_limits_and_missions(self):
        challenges = check.parse(make_checkout(self.root))
        self.assertEqual(
            [c["file"] for c in challenges], ["basic-1.json", "loops-2.json"]
        )
        first, second = challenges
        self.assertEqual(first["code"], "UNICORN")
        self.assertIsNone(first["blocks_limit"])
        self.assertEqual(first["group"], "basic")
        self.assertEqual(first["version"], "aaaa1111")
        self.assertEqual(first["mission"], "Move into the box.\n\nDon't give up!")
        self.assertEqual(second["code"], "Salted Caramel")
        self.assertEqual(second["blocks_limit"], 6)
        self.assertEqual(second["mission"], "Use a loop & few blocks.")

    def test_missing_world_file_fails(self):
        make_checkout(self.root, files=("basic-1.json",))
        with self.assertRaises(FileNotFoundError):
            check.parse(self.root)

    def test_success_check_must_match_the_file_gearsbot_picks(self):
        # GearsBot picks the first branch whose name is part of the path:
        # 'basic-1.json' also matches 'xbasic-1.json'.
        script = SCRIPT.replace(
            "'worlds/challenges_basic/loops-2.json?v=bbbb2222'",
            "'worlds/challenges_basic/xbasic-1.json?v=bbbb2222'",
        ).replace("includes('loops-2.json')", "includes('xbasic-1.json')")
        make_checkout(self.root, script, files=("basic-1.json", "xbasic-1.json"))
        with self.assertRaisesRegex(check.ParseError, "xbasic-1.json"):
            check.parse(self.root)

    def test_challenge_without_success_check_fails(self):
        script = SCRIPT.replace("includes('loops-2.json'))", "includes('other.json'))")
        make_checkout(self.root, script)
        with self.assertRaises(check.ParseError):
            check.parse(self.root)


class ReportTests(unittest.TestCase):
    def write(self, directory, challenges, worlds):
        directory.mkdir()
        data = {"upstream": "x", "challenges": challenges}
        (directory / "challenges.json").write_text(json.dumps(data))
        for name, content in worlds.items():
            (directory / name).write_text(content)

    def challenge(self, name, **changes):
        base = {
            "order": 1,
            "title": name,
            "file": name,
            "code": "A",
            "blocks_limit": None,
            "mission": "m",
        }
        return {**base, **changes}

    def test_lists_new_removed_and_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            self.write(
                old,
                [
                    self.challenge("a.json"),
                    self.challenge("b.json"),
                    self.challenge("c.json"),
                ],
                {"a.json": "1", "b.json": "1", "c.json": "1"},
            )
            self.write(
                new,
                [
                    self.challenge("a.json", code="B", order=2),
                    self.challenge("c.json"),
                    self.challenge("d.json"),
                ],
                {"a.json": "2", "c.json": "1", "d.json": "1"},
            )
            out = StringIO()
            with redirect_stdout(out):
                check.report(old, new)
        text = out.getvalue()
        self.assertIn("| `a.json` | a.json | Welt, Code |", text)
        self.assertIn("| `b.json` | b.json | entfernt |", text)
        self.assertIn("| `d.json` | d.json | neu |", text)
        self.assertNotIn("c.json", text)


if __name__ == "__main__":
    unittest.main()
