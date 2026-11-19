"""Email to participants on reviews and hint decisions (brief 5.11, #44)."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from badges.models import Badge
from hints.services import request_hint
from hints.tests.test_requests import task_with_hints
from submissions.models import Submission, SubmissionItem
from submissions.tests.test_form import text_and_code_task

from .test_coach_emails import coach

User = get_user_model()


class ParticipantEmailTests(TestCase):
    def setUp(self):
        self.coach = coach("carla", "")  # no coach mails in the outbox
        self.anna = User.objects.create_user(
            "anna", email="anna@example.org", password="geheim123"
        )
        self.profile = Profile.objects.create(
            user=self.anna, nickname="RoboAnna", real_name="Anna M"
        )
        self.client.force_login(self.coach)

    def submission(self):
        task, version = text_and_code_task()
        submission = Submission.objects.create(
            user=self.anna, task=task, task_version=version
        )
        SubmissionItem.objects.create(
            submission=submission,
            requirement=version.requirements.get(key="erklaerung"),
            text="Lösung",
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        return submission

    def review(self, submission, **data):
        url = reverse("submissions:review", kwargs={"pk": submission.pk})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, data)

    def decide(self, hint_request, decision, reply=""):
        url = reverse("hints:decide", kwargs={"pk": hint_request.pk})
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"decision": decision, "reply": reply})

    def test_approved_with_stars_points_and_badge(self):
        submission = self.submission()
        task = submission.task
        task.badge = Badge.objects.create(name="Sensorprofi")
        task.save()
        self.review(submission, decision="annehmen", stars="2", feedback="Toll!")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["anna@example.org"])
        self.assertEqual(message.subject, "Angenommen: Sensor auslesen")
        self.assertIn("Hallo RoboAnna", message.body)
        self.assertIn("2 von 3 Sternen", message.body)
        self.assertIn("Badge «Sensorprofi»", message.body)
        self.assertIn("Toll!", message.body)
        self.assertIn("http://testserver/aufgaben/sensor/", message.body)
        self.assertNotIn("Anna M", message.body)

    def test_needs_revision(self):
        self.review(self.submission(), decision="ueberarbeiten", feedback="Mehr Text")
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Bitte überarbeiten: Sensor auslesen")
        self.assertIn("Mehr Text", message.body)
        self.assertNotIn("Sterne", message.body)

    def test_hint_granted_and_declined(self):
        task, version = task_with_hints()
        first = request_hint(self.anna, task)
        self.decide(first, "freigeben", "Viel Glück")
        self.assertEqual(
            mail.outbox[0].subject, f"Dein Hinweis ist da: {version.title}"
        )
        self.assertIn("«Viel Glück»", mail.outbox[0].body)
        self.decide(request_hint(self.anna, task), "ablehnen")
        self.assertEqual(
            mail.outbox[1].subject,
            f"Antwort auf deine Hinweis-Anfrage: {version.title}",
        )

    def test_no_mail_without_address_or_with_switch_off(self):
        self.profile.email_notifications = False
        self.profile.save()
        self.review(self.submission(), decision="annehmen", stars="1")
        self.anna.email = ""
        self.anna.save()
        self.profile.email_notifications = True
        self.profile.save()
        task, _ = task_with_hints()
        self.decide(request_hint(self.anna, task), "freigeben")
        self.assertEqual(mail.outbox, [])

    def test_refused_second_review_sends_nothing(self):
        submission = self.submission()
        self.review(submission, decision="annehmen", stars="1")
        mail.outbox.clear()
        self.review(submission, decision="ueberarbeiten", feedback="Doch nicht")
        self.assertEqual(mail.outbox, [])
