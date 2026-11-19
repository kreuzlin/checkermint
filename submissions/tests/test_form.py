"""Submission form with text and code requirements (brief 5.6, #23)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import COACH_GROUP_NAME
from submissions.handlers import CodeHandler
from submissions.models import Submission, SubmissionItem
from tasks.catalogue import Status, catalogue
from tasks.models import LevelThreshold, Task, TaskRequirement, TaskVersion, Topic
from tasks.tests.test_attempts import new_version

User = get_user_model()


def text_and_code_task(slug="sensor", code_options=None, extra_photo=False):
    """A published task with a required text and an optional code part."""
    topic, _ = Topic.objects.get_or_create(name="Code", slug="code")
    task = Task.objects.create(topic=topic, slug=slug)
    version = TaskVersion.objects.create(
        task=task, title="Sensor auslesen", instructions="Lies den Sensor aus."
    )
    TaskRequirement.objects.create(
        task_version=version, key="erklaerung", type="text", label="Erklärung"
    )
    TaskRequirement.objects.create(
        task_version=version,
        key="programm",
        type="code",
        label="Programm",
        required=False,
        min_count=0,
        options=code_options or {},
        order=1,
    )
    if extra_photo:
        TaskRequirement.objects.create(
            task_version=version,
            key="fotos",
            type="photo",
            label="Fotos",
            order=2,
        )
    version.publish()
    task.is_published = True
    task.save()
    return task, version


def review(submission, status, stars=None, feedback=""):
    submission.status = status
    submission.stars = stars
    submission.feedback = feedback
    submission.reviewed_at = timezone.now()
    submission.save()


class SubmissionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = text_and_code_task()
        self.url = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.detail = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def post(self, action="speichern", **data):
        return self.client.post(self.url, {"aktion": action, **data})

    def test_form_shows_the_requirements_and_the_version(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Lösung: Sensor auslesen – ")
        self.assertContains(response, 'name="erklaerung"')
        self.assertContains(response, 'name="programm"')
        self.assertContains(response, 'name="programm-datei"')
        self.assertContains(response, "Version 1")
        # Opening the form does not start the task.
        self.assertFalse(self.user.task_attempts.exists())

    def test_saving_a_draft_starts_the_task_and_keeps_the_values(self):
        response = self.post(erklaerung="Erst mal so.")
        self.assertRedirects(response, self.url)
        draft = Submission.objects.get()
        self.assertEqual(draft.status, Submission.Status.DRAFT)
        self.assertEqual(draft.task_version, self.v1)
        self.assertEqual(self.user.task_attempts.get().task_version, self.v1)
        self.assertContains(self.client.get(self.url), "Erst mal so.")

        # Saving again replaces the item, never a second draft.
        self.post(erklaerung="Besser.")
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(SubmissionItem.objects.get().text, "Besser.")

    def test_draft_uses_the_pinned_version(self):
        self.post(erklaerung="Entwurf")
        new_version(self.task, title="Sensor neu")
        response = self.client.get(self.url)
        self.assertContains(response, "Lösung: Sensor auslesen")
        self.post(erklaerung="Noch immer v1")
        self.assertEqual(Submission.objects.get().task_version, self.v1)

    def test_submit_requires_the_required_parts(self):
        response = self.post("einreichen", programm="print(1)")
        self.assertContains(response, "Das fehlt noch.")
        self.assertContains(response, "<strong>Fehler:</strong>")
        draft = Submission.objects.get()
        self.assertEqual(draft.status, Submission.Status.DRAFT)
        # The draft was saved anyway, nothing is lost.
        self.assertEqual(draft.items.get().text, "print(1)")

    def test_submit(self):
        response = self.post("einreichen", erklaerung="Der Sensor misst Licht.")
        self.assertRedirects(response, self.detail)
        submission = Submission.objects.get()
        self.assertEqual(submission.status, Submission.Status.SUBMITTED)
        self.assertIsNotNone(submission.submitted_at)

        page = self.client.get(self.detail)
        self.assertContains(page, "Deine Lösung wartet auf einen Coach.")
        self.assertContains(page, "Der Sensor misst Licht.")
        self.assertNotContains(page, self.url)

    def test_no_new_draft_while_waiting_for_a_coach(self):
        self.post("einreichen", erklaerung="Fertig")
        response = self.client.get(self.url)
        self.assertRedirects(response, self.detail)
        response = self.post(erklaerung="Noch was")
        self.assertRedirects(response, self.detail)
        self.assertEqual(Submission.objects.count(), 1)

    def test_resubmit_after_needs_revision_starts_from_the_last_solution(self):
        self.post("einreichen", erklaerung="Erster Versuch")
        review(
            Submission.objects.get(),
            Submission.Status.NEEDS_REVISION,
            feedback="Erkläre, **warum** es funktioniert.",
        )
        page = self.client.get(self.detail)
        self.assertContains(page, "Überarbeitung nötig")
        self.assertContains(page, "<strong>warum</strong>")
        self.assertContains(page, "Lösung überarbeiten")

        self.assertContains(self.client.get(self.url), "Erster Versuch")
        self.post("einreichen", erklaerung="Zweiter Versuch, weil …")
        self.assertEqual(
            list(Submission.objects.values_list("status", flat=True).order_by("pk")),
            ["needs_revision", "submitted"],
        )
        # The reviewed submission is unchanged.
        first = Submission.objects.order_by("pk").first()
        self.assertEqual(first.items.get().text, "Erster Versuch")

    def test_resubmit_after_approval(self):
        self.post("einreichen", erklaerung="Gut")
        review(Submission.objects.get(), Submission.Status.APPROVED, stars=2)
        page = self.client.get(self.detail)
        self.assertContains(page, "★★")
        self.assertContains(page, "Neue Lösung einreichen")
        self.post("einreichen", erklaerung="Noch besser")
        self.assertEqual(Submission.objects.count(), 2)

    def test_code_file_upload_is_stored_as_text_and_highlighted(self):
        upload = SimpleUploadedFile("linie.py", b"def fahre():\n    return 1\n")
        response = self.client.post(
            self.url,
            {
                "aktion": "einreichen",
                "erklaerung": "Mit Datei",
                "programm-datei": upload,
            },
        )
        self.assertRedirects(response, self.detail)
        item = SubmissionItem.objects.get(requirement__key="programm")
        self.assertEqual(item.text, "def fahre():\n    return 1")
        self.assertEqual(item.original_filename, "linie.py")
        self.assertFalse(item.file)
        page = self.client.get(self.detail)
        self.assertContains(page, 'class="highlight"')
        self.assertContains(page, '<span class="k">def</span>')

    def test_code_is_escaped(self):
        self.post(
            "einreichen",
            erklaerung="<script>alert(1)</script>",
            programm="<script>alert(2)</script>",
        )
        page = self.client.get(self.detail)
        self.assertNotContains(page, "<script>alert")
        self.assertContains(page, "&lt;script&gt;alert(1)")

    def test_binary_and_oversized_code_files_are_rejected(self):
        cases = [
            (
                SimpleUploadedFile("bild.py", b"\xff\xd8\xff\xe0binary"),
                "keine Textdatei",
            ),
            (
                SimpleUploadedFile("gross.py", b"x" * (200 * 1024 + 1)),
                "zu gross",
            ),
        ]
        for upload, message in cases:
            response = self.client.post(
                self.url, {"aktion": "speichern", "programm-datei": upload}
            )
            self.assertContains(response, message)
        self.assertFalse(Submission.objects.exists())

    def test_locked_tasks_and_coaches_cannot_submit(self):
        LevelThreshold.objects.get_or_create(level=2, min_points=50)
        self.task.min_level = 2
        self.task.save()
        self.assertRedirects(self.post(erklaerung="x"), self.detail)
        self.task.min_level = 1
        self.task.save()

        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        self.assertRedirects(self.post(erklaerung="x"), self.detail)
        self.assertFalse(Submission.objects.exists())

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_hidden_task_is_not_found(self):
        self.task.is_archived = True
        self.task.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)


class UnsupportedTypeTests(TestCase):
    """Photo and file requirements follow with #24."""

    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, _ = text_and_code_task(extra_photo=True)
        self.url = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def test_draft_possible_but_no_submit(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Kommt bald:")
        self.assertNotContains(response, 'value="einreichen"')
        self.client.post(self.url, {"aktion": "speichern", "erklaerung": "Text"})
        response = self.client.post(
            self.url, {"aktion": "einreichen", "erklaerung": "Text"}
        )
        self.assertEqual(Submission.objects.get().status, Submission.Status.DRAFT)


class CodeHandlerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")

    def test_allowed_extensions(self):
        task, _ = text_and_code_task(code_options={"extensions": [".ino"]})
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        self.client.force_login(self.user)
        response = self.client.post(
            url,
            {
                "aktion": "speichern",
                "programm-datei": SimpleUploadedFile("a.py", b"print(1)"),
            },
        )
        self.assertContains(response, "Dateiendung ist hier nicht erlaubt")
        response = self.client.post(
            url,
            {
                "aktion": "speichern",
                "programm-datei": SimpleUploadedFile("a.ino", b"void loop() {}"),
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_language_option_wins_over_the_file_name(self):
        _, version = text_and_code_task(code_options={"language": "c"})
        requirement = version.requirements.get(key="programm")
        item = SubmissionItem(
            requirement=requirement, text="int x;", original_filename="a.py"
        )
        self.assertEqual(CodeHandler().lexer(item).name, "C")


class CatalogueStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = text_and_code_task()

    def status(self):
        entry = catalogue(self.user)[0].entries[0]
        return entry.status, entry.state.stars

    def make(self, status, stars=None):
        submission = Submission.objects.create(
            user=self.user, task=self.task, task_version=self.v1
        )
        if status != Submission.Status.DRAFT:
            submission.status = Submission.Status.SUBMITTED
            submission.submitted_at = timezone.now()
            submission.save()
            if status != Submission.Status.SUBMITTED:
                review(submission, status, stars=stars)
        return submission

    def test_statuses_from_submissions(self):
        self.make(Submission.Status.DRAFT)
        # A draft started the task in the real flow; on its own it counts nothing.
        self.assertEqual(self.status(), (Status.OPEN, None))
        Submission.objects.all().delete()

        self.make(Submission.Status.SUBMITTED)
        self.assertEqual(self.status(), (Status.SUBMITTED, None))
        Submission.objects.all().delete()

        self.make(Submission.Status.NEEDS_REVISION)
        self.assertEqual(self.status(), (Status.NEEDS_REVISION, None))

        self.make(Submission.Status.APPROVED, stars=1)
        self.make(Submission.Status.APPROVED, stars=3)
        self.make(Submission.Status.NEEDS_REVISION)
        # Solved with the best stars, even after a worse later review.
        self.assertEqual(self.status(), (Status.SOLVED, 3))

        self.make(Submission.Status.SUBMITTED)
        self.assertEqual(self.status(), (Status.SUBMITTED, None))

    def test_catalogue_page_shows_stars(self):
        self.make(Submission.Status.APPROVED, stars=2)
        self.client.force_login(self.user)
        response = self.client.get(reverse("tasks:catalogue"))
        self.assertContains(response, "Gelöst")
        self.assertContains(response, 'aria-label="2 von 3 Sternen">★★</span>')
