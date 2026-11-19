"""Review form for coaches (brief 5.8, #32)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from submissions.models import Submission, SubmissionItem
from submissions.services import SubmissionNotAllowed, review_submission

from .test_form import review, text_and_code_task

User = get_user_model()
HTMX = {"HTTP_HX_REQUEST": "true"}


class ReviewTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")
        self.task, self.version = text_and_code_task()
        self.submission = self.submit(hours_ago=2, text="Meine Erklärung")
        self.url = reverse("submissions:review", kwargs={"pk": self.submission.pk})
        self.client.force_login(self.coach)

    def submit(self, hours_ago=1, text="Lösung", user=None):
        submission = Submission.objects.create(
            user=user or self.anna,
            task=self.task,
            task_version=self.task.latest_published_version(),
        )
        SubmissionItem.objects.create(
            submission=submission,
            requirement=submission.task_version.requirements.get(key="erklaerung"),
            text=text,
        )
        submission.status = Submission.Status.SUBMITTED
        submission.submitted_at = timezone.now() - timedelta(hours=hours_ago)
        submission.save()
        return submission

    def post(self, htmx=False, follow=False, **data):
        return self.client.post(self.url, data, follow=follow, **(HTMX if htmx else {}))

    def refresh(self):
        self.submission.refresh_from_db()
        return self.submission

    # Page

    def test_page_shows_solution_participant_and_exact_version(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Bewerten: Sensor auslesen – ")
        self.assertContains(response, '<meta name="description"')
        self.assertContains(response, "Meine Erklärung")
        self.assertContains(response, "RoboAnna")
        self.assertContains(
            response,
            reverse("admin:tasks_taskversion_preview", args=[self.version.pk]),
        )
        self.assertContains(response, 'value="annehmen"')
        self.assertNotContains(response, "neuere Version")

    def test_notes_a_newer_version(self):
        draft = self.task.create_draft()
        draft.change_note = "Jetzt mit Prozent"
        draft.save()
        draft.publish()
        response = self.client.get(self.url)
        self.assertContains(response, "Es gibt eine neuere Version (Version 2)")
        self.assertContains(response, "Jetzt mit Prozent")

    def test_lists_earlier_submissions(self):
        review(self.submission, Submission.Status.NEEDS_REVISION, feedback="Mehr!")
        again = self.submit(hours_ago=1, text="Zweiter Versuch")
        response = self.client.get(
            reverse("submissions:review", kwargs={"pk": again.pk})
        )
        self.assertContains(response, "Frühere Einreichungen")
        self.assertContains(response, "Meine Erklärung")
        self.assertContains(response, "Mehr!")

    def test_coaches_only_and_no_drafts(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        missing = reverse("submissions:review", kwargs={"pk": 99999})
        self.assertEqual(self.client.get(missing).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.coach)
        draft = Submission.objects.create(
            user=self.anna, task=self.task, task_version=self.version
        )
        url = reverse("submissions:review", kwargs={"pk": draft.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    # Approve and revise

    def test_approve_with_stars(self):
        response = self.post(
            follow=True, decision="annehmen", stars="2", feedback=" Toll! "
        )
        self.assertRedirects(response, reverse("submissions:queue"))
        self.assertContains(response, "Lösung von RoboAnna angenommen (★★).")
        submission = self.refresh()
        self.assertEqual(submission.status, Submission.Status.APPROVED)
        self.assertEqual(submission.stars, 2)
        self.assertEqual(submission.feedback, "Toll!")
        self.assertEqual(submission.reviewed_by, self.coach)
        self.assertIsNotNone(submission.reviewed_at)

    def test_approve_without_feedback_is_fine(self):
        self.post(decision="annehmen", stars="3")
        self.assertEqual(self.refresh().stars, 3)

    def test_approve_needs_stars(self):
        response = self.post(decision="annehmen", feedback="Gut")
        self.assertContains(response, "Zum Annehmen braucht es 1 bis 3 Sterne.")
        self.assertEqual(self.refresh().status, Submission.Status.SUBMITTED)

    def test_invalid_stars_are_refused(self):
        response = self.post(decision="annehmen", stars="5")
        self.assertContains(response, "Fehler:")
        self.assertEqual(self.refresh().status, Submission.Status.SUBMITTED)

    def test_revision_needs_feedback_and_drops_stars(self):
        response = self.post(decision="ueberarbeiten", stars="3")
        self.assertContains(response, "Schreib kurz, was noch fehlt")
        self.assertEqual(self.refresh().status, Submission.Status.SUBMITTED)
        self.post(decision="ueberarbeiten", stars="3", feedback="Erkläre `delay`.")
        submission = self.refresh()
        self.assertEqual(submission.status, Submission.Status.NEEDS_REVISION)
        self.assertIsNone(submission.stars)
        self.assertEqual(submission.feedback, "Erkläre `delay`.")

    def test_decision_is_required(self):
        response = self.post(stars="2")
        self.assertContains(response, "Wähle «Annehmen» oder «Überarbeitung nötig».")
        self.assertEqual(self.refresh().status, Submission.Status.SUBMITTED)

    def test_already_reviewed_is_not_reviewed_again(self):
        review_submission(self.submission, self.coach, "approved", 1, "")
        page = self.post(follow=True, decision="annehmen", stars="3")
        self.assertRedirects(page, self.url)
        self.assertEqual(self.refresh().stars, 1)
        self.assertContains(page, "Diese Lösung hat schon jemand bewertet.")
        self.assertNotContains(page, 'value="annehmen"')
        self.assertContains(page, "von CoachCarla")

    def test_participant_sees_the_review(self):
        self.post(decision="annehmen", stars="3", feedback="**Super**")
        self.client.force_login(self.anna)
        detail = self.client.get(
            reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        )
        self.assertContains(detail, "<strong>Super</strong>", html=True)
        self.assertContains(detail, "★★★")

    # htmx

    def test_htmx_returns_only_the_review_block_with_next_entry(self):
        ben = User.objects.create_user("ben", password="geheim123")
        Profile.objects.create(user=ben, nickname="BenBot", real_name="Ben")
        other = self.submit(hours_ago=1, user=ben)
        response = self.post(htmx=True, decision="annehmen", stars="2")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, 'id="bewertung"')
        self.assertContains(response, "Lösung von RoboAnna angenommen")
        self.assertContains(
            response, reverse("submissions:review", kwargs={"pk": other.pk})
        )
        self.assertContains(response, "Nächste Lösung: Sensor auslesen von BenBot")

    def test_htmx_errors_stay_in_the_block(self):
        response = self.post(htmx=True, decision="annehmen")
        self.assertNotContains(response, "<html")
        self.assertContains(response, "Zum Annehmen braucht es 1 bis 3 Sterne.")

    def test_htmx_already_reviewed(self):
        review_submission(self.submission, self.coach, "needs_revision", None, "x")
        response = self.post(htmx=True, decision="annehmen", stars="3")
        self.assertContains(response, "Diese Lösung hat schon jemand bewertet.")
        self.assertContains(response, "Die Warteschlange ist leer.")


class ReviewServiceTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.coach = User.objects.create_user("coach", password="geheim123")
        self.task, self.version = text_and_code_task()
        self.submission = Submission.objects.create(
            user=self.anna, task=self.task, task_version=self.version
        )

    def test_drafts_cannot_be_reviewed(self):
        with self.assertRaises(SubmissionNotAllowed):
            review_submission(self.submission, self.coach, "approved", 2, "")

    def test_only_review_outcomes(self):
        with self.assertRaises(ValueError):
            review_submission(self.submission, self.coach, "submitted", None, "")
