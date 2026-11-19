"""Email to coaches on submissions and hint requests (brief 5.11, #43)."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from hints.tests.test_requests import task_with_hints
from notifications.emails import coach_recipients
from submissions.models import Submission
from submissions.tests.test_form import review, text_and_code_task

User = get_user_model()


def coach(username, email, notifications=True, profile=True):
    user = User.objects.create_user(
        username, email=email, password="geheim123", is_staff=True
    )
    user.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
    if profile:
        Profile.objects.create(
            user=user, nickname=username.title(), email_notifications=notifications
        )
    return user


class CoachRecipientsTests(TestCase):
    def test_only_active_coaches_with_email_and_switch_on(self):
        coach("carla", "carla@example.org")
        coach("dora", "dora@example.org", notifications=False)
        coach("emil", "")
        gone = coach("fritz", "fritz@example.org")
        gone.is_active = False
        gone.save()
        coach("gina", "gina@example.org", profile=False)  # no profile: on
        User.objects.create_user("staff", email="s@example.org", is_staff=True)
        User.objects.create_user("kid", email="kid@example.org")
        User.objects.create_superuser("admin", "admin@example.org", "geheim123")
        self.assertEqual(
            coach_recipients(),
            ["carla@example.org", "gina@example.org", "admin@example.org"],
        )


class CoachEmailTests(TestCase):
    def setUp(self):
        coach("carla", "carla@example.org")
        coach("dora", "dora@example.org")
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna M")
        self.client.force_login(self.anna)

    def submit(self, task, text):
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        return self.client.post(url, {"aktion": "einreichen", "erklaerung": text})

    def test_submission_and_resubmission(self):
        task, _ = text_and_code_task()
        with self.captureOnCommitCallbacks(execute=True):
            self.submit(task, "Erster Versuch")
        self.assertEqual(len(mail.outbox), 2)  # one per coach
        message = mail.outbox[0]
        self.assertEqual(message.to, ["carla@example.org"])
        self.assertEqual(message.subject, "Neue Lösung: Sensor auslesen von RoboAnna")
        submission = Submission.objects.get(user=self.anna)
        self.assertIn(
            "http://testserver"
            + reverse("submissions:review", kwargs={"pk": submission.pk}),
            message.body,
        )
        self.assertIn("/profil/", message.body)
        self.assertNotIn("Anna M", message.body)

        review(submission, Submission.Status.NEEDS_REVISION, feedback="Mehr")
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.submit(task, "Zweiter Versuch")
        self.assertEqual(
            mail.outbox[0].subject, "Erneut eingereicht: Sensor auslesen von RoboAnna"
        )

    def test_saving_a_draft_sends_nothing(self):
        task, _ = text_and_code_task()
        url = reverse("submissions:edit", kwargs={"slug": task.slug})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"aktion": "speichern", "erklaerung": "Halb"})
        self.assertEqual(mail.outbox, [])

    def test_hint_request(self):
        task, version = task_with_hints()
        url = reverse("hints:request", kwargs={"slug": task.slug})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"message": "Motor dreht nicht"})
        self.assertEqual(len(mail.outbox), 2)
        message = mail.outbox[0]
        self.assertEqual(
            message.subject, f"Hinweis-Anfrage: {version.title} von RoboAnna"
        )
        self.assertIn("«Motor dreht nicht»", message.body)
        self.assertIn("http://testserver/warteschlange/", message.body)

    def test_mail_server_error_does_not_break_the_submission(self):
        task, _ = text_and_code_task()
        with (
            mock.patch(
                "notifications.emails.send_mass_mail", side_effect=OSError("down")
            ),
            self.assertLogs("notifications.emails", "ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.submit(task, "Fertig")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Submission.objects.get(user=self.anna).status, Submission.Status.SUBMITTED
        )

    def test_coach_profile_explains_the_switch(self):
        self.client.force_login(User.objects.get(username="carla"))
        response = self.client.get(reverse("accounts:profile_edit"))
        self.assertContains(response, "jeder Hinweis-Anfrage")
