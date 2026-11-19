"""`manage.py seed_demo` (demo data for local development)."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import Profile
from accounts.roles import is_coach
from badges.models import UserBadge
from hints.models import HintRequest
from submissions.models import Submission
from submissions.queue import submission_entries
from tasks.models import Task, TaskAttempt, Topic

from .test_uploads import IN_MEMORY

User = get_user_model()


def seed(*args):
    out = StringIO()
    call_command("seed_demo", *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True, STORAGES=IN_MEMORY)
class SeedDemoTests(TestCase):
    def test_refuses_without_debug(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            seed("--password", "geheim123")
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())

    def test_creates_accounts_tasks_and_submissions_in_every_state(self):
        output = seed("--password", "geheim123")
        self.assertIn("Password for all of them: geheim123", output)
        coach = User.objects.get(username="demo-coach")
        self.assertTrue(is_coach(coach))
        self.assertTrue(self.client.login(username="demo-anna", password="geheim123"))
        self.assertEqual(
            set(Submission.objects.values_list("status", flat=True)),
            {"draft", "submitted", "needs_revision", "approved"},
        )
        entries = submission_entries()
        self.assertEqual(len(entries), 5)
        self.assertTrue(any(e.is_resubmission for e in entries))
        sensor = Task.objects.get(slug="demo-sensor-auslesen")
        self.assertEqual(sensor.latest_published_version().number, 2)
        pinned = TaskAttempt.objects.get(user__username="demo-max", task=sensor)
        self.assertEqual(pinned.task_version.number, 1)
        self.assertFalse(Task.objects.get(slug="demo-motor-ansteuern").is_published)
        self.assertEqual(
            sorted(UserBadge.objects.values_list("user__username", flat=True)),
            ["demo-anna", "demo-chiara", "demo-chiara"],
        )

    def test_creates_hint_requests_in_every_state(self):
        seed("--password", "geheim123")
        self.assertEqual(
            sorted(HintRequest.objects.values_list("status", flat=True)),
            ["declined", "granted", "open"],
        )
        seed("--remove")
        self.assertFalse(HintRequest.objects.exists())

    def test_random_password_is_printed(self):
        output = seed()
        password = output.rsplit(": ", 1)[1].strip()
        self.assertTrue(self.client.login(username="demo-ben", password=password))

    def test_second_run_needs_reset(self):
        seed("--password", "geheim123")
        with self.assertRaises(CommandError):
            seed("--password", "geheim123")
        seed("--reset", "--password", "anderes123")
        self.assertTrue(self.client.login(username="demo-ben", password="anderes123"))
        self.assertEqual(len(submission_entries()), 5)

    def test_remove_keeps_other_data(self):
        own = User.objects.create_user("anna", password="geheim123")
        topic = Topic.objects.create(name="Eigenes", slug="eigenes")
        task = Task.objects.create(topic=topic, slug="eigene")
        seed("--password", "geheim123")
        seed("--remove")
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())
        self.assertFalse(Task.objects.filter(slug__startswith="demo-").exists())
        self.assertFalse(Topic.objects.filter(slug__startswith="demo-").exists())
        self.assertTrue(User.objects.filter(pk=own.pk).exists())
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_name_clash_is_reported(self):
        user = User.objects.create_user("coach", password="geheim123")
        Profile.objects.create(user=user, nickname="RoboAnna", real_name="Anna")
        with self.assertRaisesMessage(CommandError, "RoboAnna"):
            seed("--password", "geheim123")
        self.assertFalse(User.objects.filter(username__startswith="demo-").exists())
