"""Task catalogue and task page (brief 5.3, 5.9, #20)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from tasks.attempts import start_attempt
from tasks.catalogue import Status, catalogue
from tasks.models import Hint, LevelThreshold, TaskAttempt, Topic

from .test_attempts import new_version, published_task
from .test_versions import make_task, make_version

User = get_user_model()


class CatalogueTests(TestCase):
    def setUp(self):
        LevelThreshold.objects.get_or_create(level=2, min_points=50)
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()

    def entries(self, user=None):
        return [
            entry
            for section in catalogue(user or self.user)
            for entry in section.entries
        ]

    def test_only_published_non_archived_tasks_are_listed(self):
        make_task("entwurf")  # never published
        archived, _ = published_task("alt")
        archived.is_archived = True
        archived.save()
        hidden, _ = published_task("versteckt")
        hidden.is_published = False
        hidden.save()
        self.assertEqual([e.task for e in self.entries()], [self.task])

    def test_grouped_by_topic_in_order(self):
        later = Topic.objects.create(name="Konstruktion", slug="konstruktion", order=5)
        first = Topic.objects.create(name="Elektronik", slug="elektronik", order=1)
        for topic, slug in [(later, "bruecke"), (first, "led")]:
            task, _ = published_task(slug)
            task.topic = topic
            task.save()
        names = [section.topic.name for section in catalogue(self.user)]
        # "Code" has order 0 (default).
        self.assertEqual(names, ["Code", "Elektronik", "Konstruktion"])

    def test_task_above_the_participants_level_is_locked(self):
        locked, _ = published_task("schwer")
        locked.min_level = 2
        locked.save()
        statuses = {e.task.slug: e.status for e in self.entries()}
        self.assertEqual(statuses["linienfolger"], Status.OPEN)
        self.assertEqual(statuses["schwer"], Status.LOCKED)

    def test_coaches_see_no_locks(self):
        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.task.min_level = 2
        self.task.save()
        self.assertEqual(self.entries(coach)[0].status, Status.OPEN)

    def test_started_task_shows_the_pinned_version(self):
        start_attempt(self.user, self.task)
        new_version(self.task, title="Linienfolger neu")
        entry = self.entries()[0]
        self.assertEqual(entry.status, Status.STARTED)
        self.assertEqual(entry.version, self.v1)

    def test_others_see_the_latest_version(self):
        v2 = new_version(self.task, title="Linienfolger neu")
        self.assertEqual(self.entries()[0].version, v2)


class CataloguePageTests(TestCase):
    def setUp(self):
        LevelThreshold.objects.get_or_create(level=2, min_points=50)
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()
        self.url = reverse("tasks:catalogue")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_title_description_and_navigation(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Aufgaben – ")
        self.assertContains(
            response, '<meta name="description" content="Alle Aufgaben nach Thema'
        )
        self.assertContains(response, 'aria-current="page">Aufgaben</a>')

    def test_lists_tasks_with_status_and_locked_without_link(self):
        locked, _ = published_task("schwer")
        locked.min_level = 2
        locked.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(
            response, reverse("tasks:task_detail", kwargs={"slug": "linienfolger"})
        )
        self.assertContains(response, "Offen")
        self.assertContains(response, "Gesperrt – ab Level 2")
        self.assertNotContains(
            response, reverse("tasks:task_detail", kwargs={"slug": "schwer"})
        )


class TaskPageTests(TestCase):
    def setUp(self):
        LevelThreshold.objects.get_or_create(level=2, min_points=50)
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task = make_task()
        self.v1 = make_version(self.task)  # with the hint "sensor"
        Hint.objects.create(task_version=self.v1, key="motor", text="Geheim B", order=1)
        self.v1.publish()
        self.task.is_published = True
        self.task.save()
        self.url = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.start_url = reverse("tasks:start", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)

    def test_shows_instructions_requirements_and_hint_count_not_content(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Linienfolger – ")
        self.assertContains(response, "<strong>Linienfolger</strong>")
        self.assertContains(response, "Fotos")
        self.assertContains(response, "Es gibt 2 Hinweise.")
        self.assertContains(response, "Version 1")
        self.assertNotContains(response, "Prüfe den Sensor")
        self.assertNotContains(response, "Geheim")
        self.assertContains(response, "Aufgabe starten")

    def test_shows_the_latest_version_before_starting(self):
        new_version(self.task, title="Linienfolger neu")
        response = self.client.get(self.url)
        self.assertContains(response, "<h1>Linienfolger neu</h1>")

    def test_start_pins_the_version_and_hides_the_button(self):
        response = self.client.post(self.start_url)
        self.assertRedirects(response, self.url)
        attempt = TaskAttempt.objects.get(user=self.user, task=self.task)
        self.assertEqual(attempt.task_version, self.v1)

        new_version(self.task, title="Linienfolger neu")
        response = self.client.get(self.url)
        self.assertContains(response, "<h1>Linienfolger</h1>")
        self.assertContains(response, "Begonnen am")
        self.assertNotContains(response, "Aufgabe starten")

    def test_start_is_post_only(self):
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        self.assertFalse(TaskAttempt.objects.exists())

    def test_locked_task_hides_content_and_cannot_be_started(self):
        self.task.min_level = 2
        self.task.save()
        response = self.client.get(self.url)
        self.assertContains(response, "ab Level 2")
        self.assertNotContains(response, "Baue einen")
        self.assertNotContains(response, "Aufgabe starten")

        response = self.client.post(self.start_url, follow=True)
        self.assertContains(response, "noch nicht starten")
        self.assertFalse(TaskAttempt.objects.exists())

    def test_hidden_tasks_are_not_found(self):
        draft_only = make_task("entwurf")
        make_version(draft_only)
        archived, _ = published_task("alt")
        archived.is_archived = True
        archived.save()
        for slug in ["entwurf", "alt", "gibt-es-nicht"]:
            url = reverse("tasks:task_detail", kwargs={"slug": slug})
            self.assertEqual(self.client.get(url).status_code, 404, slug)
            start = reverse("tasks:start", kwargs={"slug": slug})
            self.assertEqual(self.client.post(start).status_code, 404, slug)

    def test_coach_sees_the_task_but_does_not_start_it(self):
        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.task.min_level = 2
        self.task.save()
        self.client.force_login(coach)
        response = self.client.get(self.url)
        self.assertContains(response, "Baue einen")
        self.assertNotContains(response, "Aufgabe starten")
        self.client.post(self.start_url)
        self.assertFalse(TaskAttempt.objects.exists())

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post(self.start_url).status_code, 302)
