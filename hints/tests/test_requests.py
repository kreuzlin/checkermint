"""Participants request hints (brief 5.5, #36)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from hints.models import HintRequest
from hints.services import (
    HintRequestNotAllowed,
    hint_state,
    next_hint,
    request_hint,
)
from tasks.attempts import get_attempt, start_attempt
from tasks.models import Hint, LevelThreshold, TaskAttempt
from tasks.tests.test_versions import make_task, make_version

User = get_user_model()


def task_with_hints(slug="linienfolger", keys=("motor", "sensor"), **task_fields):
    task = make_task(slug, **task_fields)
    version = make_version(task)
    version.hints.all().delete()  # replace the helper's default hint
    for order, key in enumerate(keys):
        Hint.objects.create(
            task_version=version, key=key, order=order, text=f"Tipp **{key}**"
        )
    version.publish()
    task.is_published = True
    task.save()
    return task, version


def decide(request, status, reply="", coach=None):
    request.status = status
    request.coach_reply = reply
    request.decided_by = coach
    request.decided_at = timezone.now()
    request.save()
    return request


class RequestHintServiceTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.task, self.version = task_with_hints()

    def test_request_starts_the_task_and_asks_for_the_first_hint(self):
        request = request_hint(self.anna, self.task, "  Motor dreht nicht  ")
        attempt = get_attempt(self.anna, self.task)
        self.assertEqual(request.task_attempt, attempt)
        self.assertEqual(attempt.task_version, self.version)
        self.assertEqual(request.hint.key, "motor")
        self.assertEqual(request.message, "Motor dreht nicht")
        self.assertTrue(request.is_open)

    def test_only_one_open_request_per_task(self):
        request_hint(self.anna, self.task)
        with self.assertRaisesMessage(HintRequestNotAllowed, "wartet noch"):
            request_hint(self.anna, self.task)
        self.assertEqual(HintRequest.objects.count(), 1)

    def test_database_allows_only_one_open_request(self):
        first = request_hint(self.anna, self.task)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HintRequest.objects.create(task_attempt=first.task_attempt, hint=first.hint)

    def test_after_grant_the_next_hint_is_requested(self):
        decide(request_hint(self.anna, self.task), HintRequest.Status.GRANTED)
        self.assertEqual(request_hint(self.anna, self.task).hint.key, "sensor")

    def test_after_decline_the_same_hint_can_be_requested_again(self):
        decide(request_hint(self.anna, self.task), HintRequest.Status.DECLINED)
        self.assertEqual(request_hint(self.anna, self.task).hint.key, "motor")

    def test_no_request_when_all_hints_are_granted(self):
        for _ in range(2):
            decide(request_hint(self.anna, self.task), HintRequest.Status.GRANTED)
        with self.assertRaisesMessage(HintRequestNotAllowed, "alle Hinweise"):
            request_hint(self.anna, self.task)

    def test_decided_request_needs_a_date(self):
        request = request_hint(self.anna, self.task)
        request.status = HintRequest.Status.GRANTED
        with self.assertRaises(IntegrityError), transaction.atomic():
            request.save()

    def test_granted_hints_follow_the_key_on_a_newer_version(self):
        decide(request_hint(self.anna, self.task), HintRequest.Status.GRANTED)
        draft = self.task.create_draft()
        draft.publish()
        attempt = get_attempt(self.anna, self.task)
        attempt.task_version = draft
        attempt.save()

        state = hint_state(attempt, draft)
        self.assertEqual([g.hint.key for g in state.granted], ["motor"])
        self.assertEqual(state.granted[0].hint.task_version, draft)
        self.assertEqual(next_hint(attempt).key, "sensor")

    def test_state_without_attempt_offers_the_first_hint(self):
        state = hint_state(None, self.version)
        self.assertEqual(state.total, 2)
        self.assertEqual(state.next_hint.key, "motor")
        self.assertTrue(state.can_request)

    def test_state_shows_open_and_declined_requests(self):
        attempt = start_attempt(self.anna, self.task)
        request = request_hint(self.anna, self.task)
        state = hint_state(attempt, self.version)
        self.assertEqual(state.open_request, request)
        self.assertFalse(state.can_request)

        decide(request, HintRequest.Status.DECLINED, "Prüf die Kabel")
        state = hint_state(attempt, self.version)
        self.assertIsNone(state.open_request)
        self.assertEqual(state.last_declined, request)
        self.assertTrue(state.can_request)


class TaskPageHintTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")
        self.task, self.version = task_with_hints()
        self.page = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.url = reverse("hints:request", kwargs={"slug": self.task.slug})
        self.client.force_login(self.anna)

    def test_page_offers_the_request_form_but_hides_the_hint_text(self):
        response = self.client.get(self.page)
        self.assertContains(response, "Hinweis anfragen")
        self.assertContains(response, "Du hast 0 von 2 Hinweisen erhalten.")
        self.assertNotContains(response, "Tipp")

    def test_request_via_form(self):
        response = self.client.post(self.url, {"message": "Hilfe beim Motor"})
        self.assertRedirects(response, self.page)
        request = HintRequest.objects.get()
        self.assertEqual(request.message, "Hilfe beim Motor")
        self.assertTrue(TaskAttempt.objects.filter(user=self.anna).exists())

        response = self.client.get(self.page)
        self.assertContains(response, "Anfrage wartet auf einen Coach.")
        self.assertContains(response, "Hilfe beim Motor")
        self.assertNotContains(
            response,
            '<button type="submit" class="button button-secondary">Hinweis anfragen',
        )

    def test_second_request_while_open_is_refused(self):
        self.client.post(self.url)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Fehler: Deine Anfrage wartet noch")
        self.assertEqual(HintRequest.objects.count(), 1)

    def test_too_long_message_is_refused(self):
        response = self.client.post(self.url, {"message": "x" * 301}, follow=True)
        self.assertContains(response, "Fehler: Die Nachricht ist zu lang")
        self.assertFalse(HintRequest.objects.exists())

    def test_granted_hint_and_reply_are_shown(self):
        request = request_hint(self.anna, self.task)
        decide(request, HintRequest.Status.GRANTED, "Schau dir Pin 9 an", self.coach)
        response = self.client.get(self.page)
        self.assertContains(response, "Tipp <strong>motor</strong>", html=False)
        self.assertNotContains(response, "Tipp <strong>sensor</strong>")
        self.assertContains(response, "Antwort von CoachCarla:")
        self.assertContains(response, "Schau dir Pin 9 an")
        self.assertContains(response, "Du hast 1 von 2 Hinweisen erhalten.")

    def test_declined_reply_is_shown_and_asking_again_is_possible(self):
        request = request_hint(self.anna, self.task)
        decide(
            request, HintRequest.Status.DECLINED, "Versuch es zuerst selbst", self.coach
        )
        response = self.client.get(self.page)
        self.assertContains(response, "Deine letzte Anfrage wurde abgelehnt.")
        self.assertContains(response, "Versuch es zuerst selbst")
        self.assertContains(response, self.url)

    def test_coach_cannot_request(self):
        self.client.force_login(self.coach)
        self.client.post(self.url)
        self.assertFalse(HintRequest.objects.exists())
        self.assertNotContains(self.client.get(self.page), self.url)

    def test_locked_task_cannot_be_requested(self):
        LevelThreshold.objects.create(level=2, min_points=20)
        locked, _ = task_with_hints("greifarm", min_level=2)
        url = reverse("hints:request", kwargs={"slug": locked.slug})
        response = self.client.post(url, follow=True)
        self.assertContains(response, "keinen Hinweis anfragen")
        self.assertFalse(HintRequest.objects.exists())
        self.assertFalse(TaskAttempt.objects.filter(task=locked).exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_task_without_hints_shows_no_hint_section(self):
        task, _ = task_with_hints("ohne", keys=())
        response = self.client.get(
            reverse("tasks:task_detail", kwargs={"slug": task.slug})
        )
        self.assertNotContains(response, "Hinweis anfragen")


class CoachPermissionTests(TestCase):
    def test_coach_group_can_view_but_not_change_requests(self):
        group = Group.objects.get(name=COACH_GROUP_NAME)
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_hintrequest", codenames)
        self.assertNotIn("change_hintrequest", codenames)
        self.assertNotIn("delete_hintrequest", codenames)
