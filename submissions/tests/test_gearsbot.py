"""GearsBot submissions: completion code check and project ZIP (ADR 0021, #145)."""

import io
import zipfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from submissions.handlers import read_gearsbot_project
from submissions.models import Submission, SubmissionItem
from tasks.models import SimulatorConfig, Task, TaskRequirement, TaskVersion, Topic
from tasks.simulator import codes_match

from .test_uploads import IN_MEMORY, upload_task

User = get_user_model()
GEARSBOT_ZIP = {"extensions": [".zip"], "gearsbot_project": True}


def project_zip(files=None, name="gearsBot.zip"):
    files = files or {
        "gearsBlocks.xml": "<xml></xml>",
        "main.py": "#!/usr/bin/env python3\nmove_tank(50, 50)\n",
        "gearsRobot.json": "{}",
        "meta.json": '{"name": "gearsBot"}',
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="application/zip")


class CodeComparisonTests(SimpleTestCase):
    def test_ignores_case_and_extra_spaces(self):
        self.assertTrue(codes_match("mole", "MOLE"))
        self.assertTrue(codes_match("  salted   caramel ", "SALTED CARAMEL"))
        self.assertTrue(codes_match("zapus", "Zapus"))
        self.assertFalse(codes_match("MOL", "MOLE"))
        self.assertFalse(codes_match("", "MOLE"))


class ProjectZipTests(SimpleTestCase):
    def assert_rejected(self, upload, message):
        with self.assertRaisesMessage(ValidationError, message):
            read_gearsbot_project(upload)

    def test_block_project_gives_main_py(self):
        files = read_gearsbot_project(project_zip())
        self.assertEqual(
            files,
            [{"name": "main.py", "text": "#!/usr/bin/env python3\nmove_tank(50, 50)"}],
        )

    def test_python_project_lists_main_first(self):
        files = read_gearsbot_project(
            project_zip(
                {"helper.py": "x = 1", "main.py": "import helper", "meta.json": "{}"}
            )
        )
        self.assertEqual([f["name"] for f in files], ["main.py", "helper.py"])

    def test_upload_can_be_read_again_afterwards(self):
        upload = project_zip()
        read_gearsbot_project(upload)
        self.assertEqual(upload.read(2), b"PK")

    def test_not_a_zip(self):
        self.assert_rejected(SimpleUploadedFile("a.zip", b"nope"), "keine ZIP-Datei")

    def test_folders_and_paths_are_rejected(self):
        for name in (
            "src/main.py",
            "../main.py",
            "/main.py",
            "C:main.py",
            "a\\main.py",
        ):
            with self.subTest(name=name):
                self.assert_rejected(project_zip({name: "x"}), "keine Ordner")

    def test_unexpected_files_are_rejected(self):
        self.assert_rejected(
            project_zip({"main.py": "x", "virus.exe": "MZ"}),
            "virus.exe gehört nicht in ein GearsBot-Projekt",
        )

    def test_too_many_entries(self):
        files = {f"f{n}.py": "x" for n in range(51)}
        self.assert_rejected(project_zip(files), "zu viele Dateien")

    def test_large_entry_is_rejected_although_it_compresses_well(self):
        files = {"main.py": "x" * (1024 * 1024 + 1)}
        self.assert_rejected(project_zip(files), "main.py ist zu gross")

    def test_needs_blocks_or_python(self):
        self.assert_rejected(project_zip({"meta.json": "{}"}), "kein GearsBot-Projekt")


@override_settings(STORAGES=IN_MEMORY)
class ProjectUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.client.force_login(self.user)

    def upload(self, task, upload):
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        return self.client.post(url, {"aktion": "speichern", "cad": [upload]})

    def test_gearsbot_project_is_checked_and_its_code_shown(self):
        task, _ = upload_task(file_options=GEARSBOT_ZIP, photos=(0, 1))
        self.upload(task, project_zip())
        item = SubmissionItem.objects.get(requirement__key="cad")
        self.assertEqual(item.data["python_files"][0]["name"], "main.py")
        form = self.client.get(reverse("submissions:edit", kwargs={"slug": task.slug}))
        self.assertContains(form, "main.py aus dem GearsBot-Projekt")
        self.assertContains(form, "move_tank")

    def test_invalid_project_is_refused_with_the_file_name(self):
        task, _ = upload_task(file_options=GEARSBOT_ZIP, photos=(0, 1))
        response = self.upload(task, project_zip({"src/main.py": "x"}, name="mein.zip"))
        self.assertContains(response, "mein.zip: Die ZIP-Datei darf keine Ordner")
        self.assertFalse(SubmissionItem.objects.exists())

    def test_other_zip_files_are_not_checked(self):
        task, _ = upload_task(file_options={"extensions": [".zip"]}, photos=(0, 1))
        self.upload(task, project_zip({"src/sketch.ino": "void loop() {}"}))
        item = SubmissionItem.objects.get(requirement__key="cad")
        self.assertEqual(item.data, {})


def challenge_task(expected="MOLE"):
    topic, _ = Topic.objects.get_or_create(name="Code", slug="code")
    task = Task.objects.create(topic=topic, slug="gearsbot-maze-1", is_published=False)
    version = TaskVersion.objects.create(
        task=task, title="Labyrinth 1", instructions="Löse die Challenge."
    )
    TaskRequirement.objects.create(
        task_version=version,
        key="completion-code",
        type="text",
        label="Completion-Code",
    )
    SimulatorConfig.objects.create(
        task_version=version, world_scripts="challenges_basic", expected_code=expected
    )
    version.publish()
    task.is_published = True
    task.save()
    return task, version


class CodeCheckTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.coach = User.objects.create_user("coach", is_staff=True)
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")
        self.task, self.version = challenge_task()

    def submit(self, code):
        submission = Submission.objects.create(
            user=self.anna, task=self.task, task_version=self.version
        )
        SubmissionItem.objects.create(
            submission=submission,
            requirement=self.version.requirements.get(),
            text=code,
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        return submission

    def review_page(self, submission):
        self.client.force_login(self.coach)
        return self.client.get(
            reverse("submissions:review", kwargs={"pk": submission.pk})
        )

    def test_matching_code(self):
        response = self.review_page(self.submit("mole"))
        self.assertContains(response, "Code stimmt</p>")
        self.assertNotContains(response, "Code stimmt nicht")
        # The coach still decides: the normal review form is there.
        self.assertContains(response, "Annehmen")

    def test_wrong_code_shows_the_expected_one(self):
        response = self.review_page(self.submit("UNICORN"))
        self.assertContains(response, "<strong>Code stimmt nicht</strong>")
        self.assertContains(response, "erwartet: <code>MOLE</code>")
        self.assertEqual(Submission.objects.get().status, Submission.Status.SUBMITTED)

    def test_participants_never_see_the_check_or_the_expected_code(self):
        self.submit("UNICORN")
        self.client.force_login(self.anna)
        for url in (
            reverse("tasks:task_detail", kwargs={"slug": self.task.slug}),
            reverse("submissions:history"),
        ):
            response = self.client.get(url)
            self.assertContains(response, "UNICORN")
            self.assertNotContains(response, "Code stimmt")
            self.assertNotContains(response, "MOLE")

    def test_no_check_without_expected_code(self):
        task, version = challenge_task_without_code()
        submission = Submission.objects.create(
            user=self.anna, task=task, task_version=version
        )
        SubmissionItem.objects.create(
            submission=submission, requirement=version.requirements.get(), text="X"
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        self.assertNotContains(self.review_page(submission), "Code stimmt")


def challenge_task_without_code():
    topic, _ = Topic.objects.get_or_create(name="Code", slug="code")
    task = Task.objects.create(topic=topic, slug="eigene-welt")
    version = TaskVersion.objects.create(
        task=task, title="Eigene Welt", instructions="x"
    )
    TaskRequirement.objects.create(
        task_version=version, key="completion-code", type="text", label="Code"
    )
    SimulatorConfig.objects.create(task_version=version)
    version.publish()
    task.is_published = True
    task.save()
    return task, version
