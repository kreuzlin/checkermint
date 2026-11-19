"""Participant history (brief 5.9, #27)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from submissions.history import history_events
from submissions.models import Submission, SubmissionItem

from .test_form import text_and_code_task

User = get_user_model()


class HistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.coach = User.objects.create_user("coach", password="geheim123")
        self.task, self.version = text_and_code_task()
        self.url = reverse("submissions:history")
        self.start = timezone.now() - timedelta(days=10)

    def make(self, days, status="submitted", stars=None, feedback="", text="Lösung"):
        submission = Submission.objects.create(
            user=self.user, task=self.task, task_version=self.version
        )
        SubmissionItem.objects.create(
            submission=submission,
            requirement=self.version.requirements.get(key="erklaerung"),
            text=text,
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = self.start + timedelta(days=days)
        submission.save()
        if status != "submitted":
            submission.status = status
            submission.stars = stars
            submission.feedback = feedback
            submission.reviewed_by = self.coach
            submission.reviewed_at = self.start + timedelta(days=days, hours=5)
            submission.save()
        return submission

    def test_events_newest_first(self):
        first = self.make(1, "needs_revision", feedback="Mehr Details")
        second = self.make(2, "approved", stars=3)
        third = self.make(3)
        Submission.objects.create(  # drafts are not history
            user=self.user, task=self.task, task_version=self.version
        )
        events = [(e.submission, e.kind) for e in history_events(self.user)]
        self.assertEqual(
            events,
            [
                (third, "submitted"),
                (second, "reviewed"),
                (second, "submitted"),
                (first, "reviewed"),
                (first, "submitted"),
            ],
        )

    def test_page_shows_status_stars_feedback_and_version(self):
        self.make(1, "needs_revision", feedback="Erkläre **warum**.")
        self.make(2, "approved", stars=2, text="Weil der Sensor Licht misst.")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Mein Verlauf – ")
        self.assertContains(response, 'aria-current="page">Mein Verlauf</a>')
        self.assertContains(response, "Überarbeitung nötig")
        self.assertContains(response, "<strong>warum</strong>")
        self.assertContains(response, 'aria-label="2 von 3 Sternen">★★</span>')
        self.assertContains(response, "Version 1")
        self.assertContains(response, "Weil der Sensor Licht misst.")
        self.assertContains(
            response, reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        )

    def test_only_own_submissions(self):
        self.make(1, text="Von Anna")
        ben = User.objects.create_user("ben", password="geheim123")
        self.client.force_login(ben)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Von Anna")
        self.assertContains(response, "Hier erscheint alles")

    def test_archived_tasks_stay_in_the_history_without_link(self):
        self.make(1, "approved", stars=1)
        self.task.is_archived = True
        self.task.save()
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Sensor auslesen")
        self.assertNotContains(
            response, reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        )

    def test_pagination(self):
        for day in range(16):  # 16 approved submissions = 32 events
            self.make(day, "approved", stars=1)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page_obj"]), 30)
        self.assertContains(response, "Seite 1 von 2")
        response = self.client.get(self.url, {"seite": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")
