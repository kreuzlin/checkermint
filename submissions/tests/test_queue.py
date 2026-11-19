"""Coach queue (brief 5.10.1, #31)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission
from submissions.queue import queue_entries

from .test_form import review, text_and_code_task

User = get_user_model()


class CoachQueueTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.ben = User.objects.create_user("ben", password="geheim123")
        Profile.objects.create(user=self.ben, nickname="BenBot", real_name="Ben")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.task, self.version = text_and_code_task()
        self.other_task, _ = text_and_code_task(slug="motor")
        self.url = reverse("submissions:queue")
        self.now = timezone.now()

    def submit(self, user, task=None, hours_ago=1):
        task = task or self.task
        submission = Submission.objects.create(
            user=user, task=task, task_version=task.versions.get()
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = self.now - timedelta(hours=hours_ago)
        submission.save()
        return submission

    def test_only_submitted_oldest_first(self):
        newer = self.submit(self.anna, hours_ago=1)
        older = self.submit(self.ben, task=self.other_task, hours_ago=30)
        reviewed = self.submit(self.ben, hours_ago=50)
        review(reviewed, Submission.Status.APPROVED, stars=2)
        Submission.objects.create(  # drafts do not wait for a coach
            user=self.anna,
            task=self.other_task,
            task_version=self.other_task.versions.get(),
        )
        self.assertEqual([e.submission for e in queue_entries()], [older, newer])

    def test_resubmission_is_marked(self):
        first = self.submit(self.anna, hours_ago=20)
        review(first, Submission.Status.NEEDS_REVISION, feedback="Mehr Details")
        again = self.submit(self.anna, hours_ago=2)
        first_time = self.submit(self.ben, hours_ago=1)
        entries = queue_entries()
        self.assertEqual([e.submission for e in entries], [again, first_time])
        self.assertEqual([e.is_resubmission for e in entries], [True, False])

    def test_deactivated_participants_are_left_out(self):
        self.submit(self.anna)
        self.anna.is_active = False
        self.anna.save()
        self.assertEqual(queue_entries(), [])

    def test_page_lists_entries_with_link_and_waiting_time(self):
        submission = self.submit(self.anna, hours_ago=3)
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Warteschlange – ")
        self.assertContains(response, '<meta name="description"')
        self.assertContains(response, "RoboAnna (Anna)")
        self.assertContains(response, "Sensor auslesen")
        self.assertContains(response, "Code")
        self.assertContains(response, "wartet seit 3")
        self.assertContains(
            response,
            reverse("admin:submissions_submission_change", args=[submission.pk]),
        )

    def test_empty_queue(self):
        self.client.force_login(self.coach)
        self.assertContains(self.client.get(self.url), "Nichts zu tun")

    def test_coaches_only(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_navigation_entry_for_coaches_only(self):
        self.client.force_login(self.anna)
        catalogue = reverse("tasks:catalogue")
        self.assertNotContains(self.client.get(catalogue), self.url)
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, f'href="{self.url}" aria-current="page"')
