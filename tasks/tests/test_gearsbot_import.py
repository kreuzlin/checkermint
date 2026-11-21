"""Import of GearsBot's Basic Challenges (ADR 0021, #146)."""

import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from tasks.gearsbot_import import BUNDLE, FILTERS, import_challenges
from tasks.models import SimulatorFile, Task, Topic


class ImportTests(TestCase):
    def test_creates_one_unpublished_draft_task_per_challenge(self):
        result = import_challenges()
        self.assertEqual(len(result.created), 61)
        tasks = Task.objects.filter(slug__startswith="gearsbot-")
        self.assertEqual(tasks.count(), 61)
        self.assertFalse(tasks.filter(is_published=True).exists())
        self.assertEqual(Topic.objects.get(slug="code").name, "Code")
        for task in tasks:
            self.assertEqual(task.versions.count(), 1)
            self.assertFalse(task.versions.get().is_published)

    def test_titles_points_levels_and_order(self):
        import_challenges()
        expected = {
            "gearsbot-basic-1": ("Grundlagen 1", 10, 1, 1),
            "gearsbot-sleep-2": ("Warten 2", 10, 1, 7),
            "gearsbot-maze-1": ("Labyrinth 1", 15, 2, 8),
            "gearsbot-dungeon-0": ("Verlies 0", 15, 2, 14),
            "gearsbot-loops-2b": ("Schleifen 2b", 20, 3, 25),
            "gearsbot-conditions-8b": ("Bedingungen 8b", 25, 4, 45),
            "gearsbot-abstraction-11": ("Funktionen 11", 30, 5, 61),
        }
        for slug, (title, points, level, order) in expected.items():
            task = Task.objects.get(slug=slug)
            version = task.versions.get()
            self.assertEqual(
                (version.title, version.base_points, task.min_level, task.order),
                (title, points, level, order),
            )

    def test_version_content(self):
        import_challenges()
        version = Task.objects.get(slug="gearsbot-loops-2").versions.get()
        self.assertIn("«Loops: Repeat 2»", version.instructions)
        self.assertIn("Im Simulator öffnen", version.instructions)
        self.assertIn("höchstens **6 Blöcke**", version.instructions)
        self.assertIn("> ", version.instructions)  # English mission as a quote
        code, project = version.requirements.order_by("order")
        self.assertEqual(
            (code.key, code.type, code.required), ("completion-code", "text", True)
        )
        self.assertEqual(
            (project.key, project.type, project.required), ("projekt", "file", False)
        )
        self.assertEqual(
            project.options, {"extensions": [".zip"], "gearsbot_project": True}
        )
        self.assertEqual(version.simulator.world_scripts, "challenges_basic")
        self.assertEqual(version.simulator.expected_code, "URANUS")
        files = {f.role: f for f in version.simulator_files.all()}
        self.assertEqual(files["world"].filename, "welt.json")
        self.assertEqual(
            files["world"].content["options"]["jsonFile"], "sim-file:loops-2.json"
        )
        self.assertEqual(files["challenge_world"].filename, "loops-2.json")
        self.assertEqual(
            files["challenge_world"].content,
            json.loads((BUNDLE / "loops-2.json").read_text()),
        )
        self.assertEqual(files["filter"].content, FILTERS["loops"])
        self.assertFalse(version.hints.exists())

    def test_filters_build_up_per_group(self):
        def shown(group):
            return set(FILTERS[group]["show"].get("blocks", [])) | set(
                FILTERS[group]["show"]["categories"]
            )

        self.assertEqual(shown("basic"), {"Movement"})  # turns are in Movement
        self.assertLess(shown("basic"), shown("sleep"))
        self.assertEqual(shown("sleep"), shown("maze"))
        self.assertLess(shown("maze"), shown("loops"))
        self.assertLess(shown("loops"), shown("conditions"))
        self.assertLess(shown("conditions"), shown("abstraction"))
        self.assertIn("tw_color", shown("conditions"))
        self.assertTrue({"Variables", "Functions"} <= shown("abstraction"))

    def test_second_run_changes_nothing(self):
        import_challenges()
        result = import_challenges()
        self.assertEqual(len(result.unchanged), 61)
        self.assertEqual(result.created + result.updated_drafts + result.new_drafts, [])

    def test_dry_run_saves_nothing(self):
        out = StringIO()
        call_command("import_gearsbot_challenges", "--dry-run", stdout=out)
        self.assertIn("New tasks (unpublished drafts): 61", out.getvalue())
        self.assertIn("Dry run: nothing was saved.", out.getvalue())
        self.assertFalse(Task.objects.exists())

    def test_archived_tasks_are_skipped(self):
        import_challenges()
        Task.objects.filter(slug="gearsbot-maze-1").update(is_archived=True)
        result = import_challenges()
        self.assertEqual(result.skipped, ["gearsbot-maze-1 (Labyrinth 1): archiviert"])


class UpstreamChangeTests(TestCase):
    """A changed world or code creates a new draft; published stays as is."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bundle = Path(self.tmp.name) / "bundle"
        shutil.copytree(BUNDLE, self.bundle)
        import_challenges(self.bundle)

    def tearDown(self):
        self.tmp.cleanup()

    def change_code(self, file, code):
        path = self.bundle / "challenges.json"
        data = json.loads(path.read_text())
        for entry in data["challenges"]:
            if entry["file"] == file:
                entry["code"] = code
        path.write_text(json.dumps(data))

    def test_draft_is_updated_in_place_keeping_coach_edits(self):
        task = Task.objects.get(slug="gearsbot-maze-1")
        draft = task.versions.get()
        draft.title = "Mein Labyrinth"
        draft.save()
        self.change_code("maze-1.json", "NEWCODE")
        result = import_challenges(self.bundle)
        self.assertEqual(result.updated_drafts, ["gearsbot-maze-1 (Labyrinth 1)"])
        draft.refresh_from_db()
        self.assertEqual(draft.title, "Mein Labyrinth")
        self.assertEqual(draft.simulator.expected_code, "NEWCODE")
        self.assertEqual(task.versions.count(), 1)

    def test_published_version_gets_a_new_draft(self):
        task = Task.objects.get(slug="gearsbot-maze-1")
        published = task.versions.get()
        published.publish()
        world_path = self.bundle / "maze-1.json"
        world = json.loads(world_path.read_text())
        world["options"]["timer"] = 99
        world_path.write_text(json.dumps(world))
        result = import_challenges(self.bundle)
        self.assertEqual(result.new_drafts, ["gearsbot-maze-1 (Labyrinth 1)"])
        published.refresh_from_db()
        old_world = published.simulator_files.get(
            role=SimulatorFile.Role.CHALLENGE_WORLD
        )
        self.assertNotEqual(old_world.content["options"].get("timer"), 99)
        draft = task.draft_version()
        self.assertEqual(draft.number, 2)
        self.assertIn("GearsBot-Update", draft.change_note)
        new_world = draft.simulator_files.get(role=SimulatorFile.Role.CHALLENGE_WORLD)
        self.assertEqual(new_world.content["options"]["timer"], 99)
        self.assertEqual(draft.requirements.count(), 2)
        self.assertNotEqual(draft.simulator.token, published.simulator.token)
        # Running again finds the draft current.
        self.assertIn(
            "gearsbot-maze-1 (Labyrinth 1)", import_challenges(self.bundle).unchanged
        )

    def test_tasks_missing_upstream_are_reported_not_deleted(self):
        path = self.bundle / "challenges.json"
        data = json.loads(path.read_text())
        data["challenges"] = [
            c for c in data["challenges"] if c["file"] != "maze-6.json"
        ]
        path.write_text(json.dumps(data))
        result = import_challenges(self.bundle)
        self.assertEqual(result.missing_upstream, ["gearsbot-maze-6"])
        self.assertTrue(Task.objects.filter(slug="gearsbot-maze-6").exists())
