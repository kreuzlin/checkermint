"""GearsBot simulator settings on task versions (ADR 0021, #144)."""

import json
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from tasks.admin import SimulatorFileForm
from tasks.models import PublishedVersionError, SimulatorConfig, SimulatorFile

from .test_versions import make_task, make_version

User = get_user_model()
SIM = "https://sim.example.ch"
WRAPPER = {
    "worldName": "challenges_basic",
    "options": {"jsonFile": "sim-file:maze-1.json", "useDefaultRobot": True},
}
CHALLENGE = {"worldName": "custom", "options": {"imageURL": "/mirror/a.jpg"}}


def simulator_task(slug="labyrinth-1", publish=True):
    task = make_task(slug)
    version = make_version(task, title="Labyrinth 1")
    SimulatorConfig.objects.create(
        task_version=version, world_scripts="challenges_basic", expected_code="MOLE"
    )
    SimulatorFile.objects.create(
        task_version=version, role="world", filename="welt.json", content=WRAPPER
    )
    SimulatorFile.objects.create(
        task_version=version,
        role="challenge_world",
        filename="maze-1.json",
        content=CHALLENGE,
    )
    SimulatorFile.objects.create(
        task_version=version,
        role="filter",
        filename="bloecke.json",
        content={"deny": {"categories": ["Motor"]}},
    )
    if publish:
        version.publish()
        task.is_published = True
        task.save()
    return task, version


def file_path(version, filename):
    return reverse(
        "simulator_file",
        kwargs={"token": version.simulator.token, "filename": filename},
    )


@override_settings(SIMULATOR_URL=SIM)
class SimulatorFileViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task, cls.version = simulator_task()

    def test_served_without_login_with_cors(self):
        response = self.client.get(file_path(self.version, "maze-1.json"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response["Access-Control-Allow-Origin"], SIM)
        self.assertEqual(response["Cache-Control"], "public, max-age=3600")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(response.json(), CHALLENGE)

    def test_file_references_become_absolute_urls(self):
        response = self.client.get(file_path(self.version, "welt.json"))
        json_file = response.json()["options"]["jsonFile"]
        self.assertEqual(
            json_file, "http://testserver" + file_path(self.version, "maze-1.json")
        )
        # Ends with the upstream name: GearsBot picks the challenge by it.
        self.assertTrue(json_file.endswith("/maze-1.json"))

    def test_unknown_token_or_file_is_404(self):
        token = self.version.simulator.token
        for path in (
            reverse(
                "simulator_file", kwargs={"token": "x" * 32, "filename": "welt.json"}
            ),
            reverse("simulator_file", kwargs={"token": token, "filename": "nope.json"}),
        ):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_archived_task_is_404(self):
        self.task.is_archived = True
        self.task.save()
        response = self.client.get(file_path(self.version, "welt.json"))
        self.assertEqual(response.status_code, 404)

    def test_draft_files_are_not_cached(self):
        _, draft = simulator_task("entwurf", publish=False)
        response = self.client.get(file_path(draft, "welt.json"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_only_get(self):
        path = file_path(self.version, "welt.json")
        self.assertEqual(self.client.post(path).status_code, 405)

    @override_settings(SIMULATOR_URL="")
    def test_no_cors_header_without_simulator(self):
        response = self.client.get(file_path(self.version, "welt.json"))
        self.assertNotIn("Access-Control-Allow-Origin", response)


@override_settings(SIMULATOR_URL=SIM)
class TaskPageButtonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task, cls.version = simulator_task()
        cls.anna = User.objects.create_user("anna", password="geheim123")
        cls.detail = reverse("tasks:task_detail", kwargs={"slug": cls.task.slug})

    def launch_link(self, response):
        content = response.content.decode()
        start = content.index(f'href="{SIM}/?')
        return content[start + 6 : content.index('"', start + 6)].replace("&amp;", "&")

    def test_button_opens_the_world_with_scripts_and_filter(self):
        self.client.force_login(self.anna)
        response = self.client.get(self.detail)
        self.assertContains(response, "Im Simulator öffnen")
        self.assertContains(response, 'target="_blank" rel="noopener"')
        query = parse_qs(urlsplit(self.launch_link(response)).query)
        self.assertEqual(query["worldScripts"], ["challenges_basic"])
        self.assertEqual(
            query["worldJSON"],
            ["http://testserver" + file_path(self.version, "welt.json")],
        )
        self.assertEqual(
            query["filterBlocksJSON"],
            ["http://testserver" + file_path(self.version, "bloecke.json")],
        )
        self.assertNotIn("robotJSON", query)

    def test_expected_code_is_never_shown_to_participants(self):
        self.client.force_login(self.anna)
        self.assertNotContains(self.client.get(self.detail), "MOLE")
        for name in ("welt.json", "maze-1.json", "bloecke.json"):
            self.assertNotIn(
                "MOLE", self.client.get(file_path(self.version, name)).content.decode()
            )

    @override_settings(SIMULATOR_URL="")
    def test_no_button_without_simulator(self):
        self.client.force_login(self.anna)
        self.assertNotContains(self.client.get(self.detail), "Im Simulator öffnen")

    def test_no_button_without_world_file(self):
        task = make_task("ohne-welt")
        version = make_version(task)
        SimulatorConfig.objects.create(task_version=version)
        version.publish()
        task.is_published = True
        task.save()
        self.client.force_login(self.anna)
        response = self.client.get(
            reverse("tasks:task_detail", kwargs={"slug": "ohne-welt"})
        )
        self.assertNotContains(response, "Im Simulator öffnen")

    def test_admin_preview_has_the_button(self):
        coach = User.objects.create_user("coach", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        preview = reverse("admin:tasks_taskversion_preview", args=[self.version.pk])
        self.assertContains(self.client.get(preview), "Im Simulator öffnen")


class ImmutabilityAndCopyTests(TestCase):
    def test_published_settings_and_files_are_immutable(self):
        _, version = simulator_task()
        config = version.simulator
        config.expected_code = "OTHER"
        with self.assertRaises(PublishedVersionError):
            config.save()
        file = version.simulator_files.get(role="world")
        with self.assertRaises(PublishedVersionError):
            file.delete()
        with self.assertRaises(PublishedVersionError):
            SimulatorFile.objects.filter(pk=file.pk).update(filename="x.json")
        with self.assertRaises(PublishedVersionError):
            SimulatorFile.objects.create(
                task_version=version, role="robot", filename="r.json", content={}
            )

    def test_new_version_copies_settings_with_a_new_token(self):
        task, version = simulator_task()
        draft = task.create_draft()
        self.assertNotEqual(draft.simulator.token, version.simulator.token)
        self.assertEqual(draft.simulator.world_scripts, "challenges_basic")
        self.assertEqual(draft.simulator.expected_code, "MOLE")
        copied = {f.filename: f.content for f in draft.simulator_files.all()}
        original = {f.filename: f.content for f in version.simulator_files.all()}
        self.assertEqual(copied, original)
        self.assertEqual(
            set(draft.simulator_files.values_list("role", flat=True)),
            {"world", "challenge_world", "filter"},
        )

    def test_coaches_may_manage_simulator_settings(self):
        group = Group.objects.get(name=COACH_GROUP_NAME)
        codenames = set(group.permissions.values_list("codename", flat=True))
        for model in ("simulatorconfig", "simulatorfile"):
            for action in ("view", "add", "change", "delete"):
                self.assertIn(f"{action}_{model}", codenames)


class SimulatorFileFormTests(TestCase):
    def form(self, upload=None, **data):
        files = {"upload": upload} if upload else {}
        return SimulatorFileForm(data={"role": "world", **data}, files=files)

    def test_upload_fills_content_and_filename(self):
        upload = SimpleUploadedFile("meine-welt.json", json.dumps(CHALLENGE).encode())
        form = self.form(upload)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["content"], CHALLENGE)
        self.assertEqual(form.cleaned_data["filename"], "meine-welt.json")

    def test_invalid_json_upload(self):
        form = self.form(SimpleUploadedFile("kaputt.json", b"{nope"))
        self.assertFalse(form.is_valid())
        self.assertIn("keine gültige JSON-Datei", str(form.errors))

    def test_content_must_be_an_object(self):
        form = self.form(filename="a.json", content="[1, 2]")
        self.assertFalse(form.is_valid())
        self.assertIn("JSON-Objekt", str(form.errors))

    def test_filename_must_be_a_plain_json_name(self):
        form = self.form(filename="../a.json", content="{}")
        self.assertFalse(form.is_valid())
        self.assertIn("filename", form.errors)

    def test_needs_content_or_upload(self):
        form = self.form(filename="a.json")
        self.assertFalse(form.is_valid())
        self.assertIn("Inhalt einfügen", str(form.errors))
