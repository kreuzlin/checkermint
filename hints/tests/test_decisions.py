"""Coaches grant or decline hint requests in the queue (brief 5.5, 5.10.1, #37)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from hints.models import HintRequest
from hints.services import HintRequestNotAllowed, decide_request, request_hint
from submissions.models import Submission
from submissions.queue import HINT_REQUEST, SUBMISSION, queue_entries

from .test_requests import task_with_hints

User = get_user_model()
HTMX = {"HTTP_HX_REQUEST": "true"}


class DecisionTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna M")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")
        self.task, self.version = task_with_hints()
        self.request = request_hint(self.anna, self.task, "Motor dreht nicht")
        self.url = reverse("hints:decide", kwargs={"pk": self.request.pk})
        self.queue = reverse("submissions:queue")
        self.client.force_login(self.coach)

    def test_open_request_is_in_the_queue_with_hint_and_message(self):
        response = self.client.get(self.queue)
        self.assertContains(response, "Hinweis-Anfrage")
        self.assertContains(response, "RoboAnna (Anna M)")
        self.assertContains(response, "«Motor dreht nicht»")
        self.assertContains(response, "Tipp <strong>motor</strong>", html=False)
        self.assertContains(response, self.url)
        self.assertContains(response, "htmx-2.0.4.min.js")

    def test_grant_with_htmx_replaces_the_entry(self):
        response = self.client.post(
            self.url, {"decision": "freigeben", "reply": " Pin 9 "}, **HTMX
        )
        self.assertTemplateUsed(response, "hints/_queue_entry.html")
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Hinweis-Anfrage von RoboAnna freigegeben.")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, HintRequest.Status.GRANTED)
        self.assertEqual(self.request.coach_reply, "Pin 9")
        self.assertEqual(self.request.decided_by, self.coach)
        self.assertIsNotNone(self.request.decided_at)

    def test_decline_without_javascript_redirects_to_the_queue(self):
        response = self.client.post(
            self.url, {"decision": "ablehnen", "reply": "Erst selbst probieren"}
        )
        self.assertRedirects(response, self.queue, fetch_redirect_response=False)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, HintRequest.Status.DECLINED)
        page = self.client.get(self.queue)
        self.assertContains(page, "Hinweis-Anfrage von RoboAnna abgelehnt.")
        self.assertNotContains(page, self.url)

    def test_participant_sees_the_decision(self):
        self.client.post(self.url, {"decision": "freigeben", "reply": "Pin 9"})
        self.client.force_login(self.anna)
        page = self.client.get(
            reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        )
        self.assertContains(page, "Tipp <strong>motor</strong>", html=False)
        self.assertContains(page, "Antwort von CoachCarla:")

    def test_second_decision_is_refused_and_shows_the_first(self):
        decide_request(self.request, self.coach, HintRequest.Status.DECLINED, "Nein")
        response = self.client.post(self.url, {"decision": "freigeben"}, **HTMX)
        self.assertContains(response, "Fehler:")
        self.assertContains(response, "schon entschieden")
        self.assertContains(response, "Abgelehnt")
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, HintRequest.Status.DECLINED)

    def test_service_refuses_deciding_twice(self):
        decide_request(self.request, self.coach, HintRequest.Status.GRANTED)
        with self.assertRaises(HintRequestNotAllowed):
            decide_request(self.request, self.coach, HintRequest.Status.DECLINED)

    def test_missing_decision_or_too_long_reply_is_refused(self):
        response = self.client.post(self.url, {"reply": "x"}, **HTMX)
        self.assertContains(response, "Fehler:")
        response = self.client.post(
            self.url, {"decision": "freigeben", "reply": "x" * 301}, **HTMX
        )
        self.assertContains(response, "Fehler:")
        self.request.refresh_from_db()
        self.assertTrue(self.request.is_open)

    def test_participants_cannot_decide(self):
        self.client.force_login(self.anna)
        response = self.client.post(self.url, {"decision": "freigeben"})
        self.assertEqual(response.status_code, 403)
        self.request.refresh_from_db()
        self.assertTrue(self.request.is_open)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_queue_merges_both_kinds_oldest_first(self):
        self.request.requested_at = timezone.now() - timedelta(hours=2)
        self.request.save()
        submission = Submission.objects.create(
            user=self.anna, task=self.task, task_version=self.version
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now() - timedelta(hours=3)
        submission.save()
        self.assertEqual(
            [entry.kind for entry in queue_entries()], [SUBMISSION, HINT_REQUEST]
        )

    def test_requests_of_deactivated_participants_are_hidden(self):
        self.anna.is_active = False
        self.anna.save()
        self.assertEqual(queue_entries(), [])

    def test_coach_home_counts_hint_requests(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Warteschlange: 1 Hinweis-Anfrage wartet")
