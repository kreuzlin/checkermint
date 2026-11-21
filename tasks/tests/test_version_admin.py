"""Admin workflow for task versions (brief 5.4, ADR 0010, issue #17)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from tasks.models import Hint, Task, TaskRequirement, TaskVersion, Topic

User = get_user_model()


def published_task():
    topic = Topic.objects.create(name="Code", slug="code")
    task = Task.objects.create(topic=topic, slug="linienfolger")
    version = TaskVersion.objects.create(
        task=task,
        title="Linienfolger",
        instructions="Baue einen **Linienfolger**.",
        base_points=20,
    )
    TaskRequirement.objects.create(
        task_version=version,
        key="fotos",
        type="photo",
        label="Fotos",
        min_count=2,
        max_count=5,
        options={"note": "x"},
    )
    Hint.objects.create(task_version=version, key="sensor", text="Prüfe den *Sensor*.")
    version.publish()
    return task, version


class CreateDraftTests(TestCase):
    def test_copies_latest_version_with_keys(self):
        task, v1 = published_task()
        coach = User.objects.create_user("coach")
        draft = task.create_draft(user=coach)
        self.assertEqual(draft.number, 2)
        self.assertEqual(draft.status, TaskVersion.Status.DRAFT)
        self.assertEqual(draft.title, v1.title)
        self.assertEqual(draft.base_points, 20)
        self.assertEqual(draft.change_note, "")
        self.assertEqual(draft.created_by, coach)
        requirement = draft.requirements.get()
        self.assertEqual(
            (requirement.key, requirement.min_count, requirement.options),
            ("fotos", 2, {"note": "x"}),
        )
        self.assertEqual(draft.hints.get().key, "sensor")
        # The published version is untouched.
        self.assertEqual(v1.requirements.count(), 1)

    def test_returns_existing_draft(self):
        task, _ = published_task()
        self.assertEqual(task.create_draft(), task.create_draft())
        self.assertEqual(task.versions.drafts().count(), 1)

    def test_first_version_is_empty_draft(self):
        topic = Topic.objects.create(name="Code", slug="code")
        task = Task.objects.create(topic=topic, slug="neu")
        draft = task.create_draft()
        self.assertEqual((draft.number, draft.title), (1, "neu"))
        self.assertFalse(draft.requirements.exists())


class VersionAdminTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(
            "coach", password="Roboter-777", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(self.coach)
        self.task, self.v1 = published_task()

    def version_url(self, version, view="change"):
        return reverse(f"admin:tasks_taskversion_{view}", args=[version.pk])

    def test_task_page_lists_versions_and_offers_new_version(self):
        response = self.client.get(
            reverse("admin:tasks_task_change", args=[self.task.pk])
        )
        self.assertContains(response, "Neue Version erstellen")
        self.assertContains(response, "Linienfolger")
        self.assertNotContains(response, "ß")

    def test_new_version_creates_draft_and_opens_it(self):
        url = reverse("admin:tasks_task_new_version", args=[self.task.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(url)
        draft = self.task.draft_version()
        self.assertRedirects(response, self.version_url(draft))
        response = self.client.get(
            reverse("admin:tasks_task_change", args=[self.task.pk])
        )
        self.assertContains(response, "Entwurf bearbeiten (Version 2)")

    def test_published_version_is_read_only(self):
        response = self.client.get(self.version_url(self.v1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nicht mehr änderbar")
        self.assertNotContains(response, 'name="title"')
        self.assertNotContains(response, "Veröffentlichen</a>")
        response = self.client.post(self.version_url(self.v1), {"title": "X"})
        self.assertEqual(response.status_code, 403)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.title, "Linienfolger")
        self.assertEqual(
            self.client.get(self.version_url(self.v1, "publish")).status_code, 403
        )
        self.assertEqual(
            self.client.get(self.version_url(self.v1, "delete")).status_code, 403
        )

    def test_edit_draft_with_inlines_and_publish(self):
        draft = self.task.create_draft(self.coach)
        requirement = draft.requirements.get()
        hint = draft.hints.get()
        data = {
            "title": "Linienfolger 2",
            "instructions": "Neu",
            "base_points": 30,
            "change_note": "Mehr Punkte",
            "requirements-TOTAL_FORMS": 2,
            "requirements-INITIAL_FORMS": 1,
            "requirements-MIN_NUM_FORMS": 0,
            "requirements-MAX_NUM_FORMS": 1000,
            "requirements-0-id": requirement.pk,
            "requirements-0-task_version": draft.pk,
            "requirements-0-key": "fotos",
            "requirements-0-label": "Fotos",
            "requirements-0-type": "photo",
            "requirements-0-required": "on",
            "requirements-0-min_count": 1,
            "requirements-0-max_count": 3,
            "requirements-0-order": 0,
            "requirements-0-options": "{}",
            "requirements-1-key": "code",
            "requirements-1-label": "Code",
            "requirements-1-type": "code",
            "requirements-1-required": "on",
            "requirements-1-min_count": 1,
            "requirements-1-max_count": 1,
            "requirements-1-order": 1,
            "requirements-1-options": "{}",
            "hints-TOTAL_FORMS": 1,
            "hints-INITIAL_FORMS": 1,
            "hints-MIN_NUM_FORMS": 0,
            "hints-MAX_NUM_FORMS": 1000,
            "hints-0-id": hint.pk,
            "hints-0-task_version": draft.pk,
            "hints-0-key": "sensor",
            "hints-0-order": 0,
            "hints-0-text": "Neuer Text",
            "hints-0-DELETE": "",
            # Simulator inlines (ADR 0021): empty, but always posted.
            "simulator-TOTAL_FORMS": 0,
            "simulator-INITIAL_FORMS": 0,
            "simulator-MIN_NUM_FORMS": 0,
            "simulator-MAX_NUM_FORMS": 1,
            "simulator_files-TOTAL_FORMS": 0,
            "simulator_files-INITIAL_FORMS": 0,
            "simulator_files-MIN_NUM_FORMS": 0,
            "simulator_files-MAX_NUM_FORMS": 1000,
        }
        response = self.client.post(self.version_url(draft), data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        draft.refresh_from_db()
        self.assertEqual(draft.title, "Linienfolger 2")
        self.assertEqual(draft.requirements.count(), 2)

        response = self.client.get(self.version_url(draft, "publish"))
        self.assertContains(response, "nicht mehr ändern")
        response = self.client.post(self.version_url(draft, "publish"))
        self.assertRedirects(
            response, reverse("admin:tasks_task_change", args=[self.task.pk])
        )
        draft.refresh_from_db()
        self.assertTrue(draft.is_published)
        self.assertEqual(self.task.latest_published_version(), draft)
        # Version 1 still has its own content.
        self.assertEqual(self.v1.requirements.get().max_count, 5)

    def test_publish_without_requirement_shows_error(self):
        topic = Topic.objects.get(slug="code")
        task = Task.objects.create(topic=topic, slug="leer")
        draft = task.create_draft()
        response = self.client.post(self.version_url(draft, "publish"), follow=True)
        self.assertContains(response, "mindestens eine Anforderung")
        draft.refresh_from_db()
        self.assertFalse(draft.is_published)

    def test_preview_shows_participant_view(self):
        draft = self.task.create_draft()
        response = self.client.get(self.version_url(draft, "preview"))
        self.assertContains(response, "Vorschau")
        self.assertContains(response, "<strong>Linienfolger</strong>", html=False)
        self.assertContains(response, "2 bis 5")
        self.assertContains(response, "Es gibt 1 Hinweis.")
        self.assertNotContains(response, "ß")

    def test_preview_requires_staff(self):
        participant = User.objects.create_user("kind")
        self.client.force_login(participant)
        response = self.client.get(self.version_url(self.v1, "preview"))
        self.assertEqual(response.status_code, 302)

    def test_draft_can_be_deleted(self):
        draft = self.task.create_draft()
        response = self.client.post(self.version_url(draft, "delete"), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TaskVersion.objects.filter(pk=draft.pk).exists())

    def test_task_with_published_version_cannot_be_deleted_in_admin(self):
        url = reverse("admin:tasks_task_delete", args=[self.task.pk])
        response = self.client.post(url, {"post": "yes"})
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertIn(response.status_code, (200, 403))

    def test_versions_not_on_admin_index(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Aufgaben")
        self.assertNotContains(response, "Aufgaben-Versionen")
