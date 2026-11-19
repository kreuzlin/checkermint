"""Participant detail for coaches (brief 5.10.3, #40)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from hints.models import HintRequest
from hints.services import decide_request, request_hint
from hints.tests.test_requests import task_with_hints
from overviews.participant import participant_detail
from submissions.tests.test_progress import make_task, reviewed
from tasks.attempts import start_attempt
from tasks.models import Topic
from tasks.tests.test_levels import add_levels

from .test_matrix import participant

User = get_user_model()


class ParticipantDetailTests(TestCase):
    def setUp(self):
        add_levels(20)
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.line = make_task(self.code, "linie", base_points=10, min_level=2)
        self.servo = make_task(self.code, "servo", base_points=10, min_level=3)
        self.anna = participant("anna", "RoboAnna", "Anna Muster")
        self.ben = participant("ben", "BenBot")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")

        self.first = reviewed(self.anna, self.blink, "needs_revision")
        self.first.feedback = "Die LED blinkt noch nicht."
        self.first.save()
        self.approved = reviewed(self.anna, self.blink, "approved", stars=2)
        self.hint_task, _ = task_with_hints()
        declined = request_hint(self.anna, self.hint_task, "Motor dreht nicht")
        decide_request(declined, self.coach, HintRequest.Status.DECLINED, "Kabel?")
        self.open_request = request_hint(self.anna, self.hint_task)
        reviewed(self.ben, self.blink, "approved", stars=3)  # not Anna's
        self.url = reverse("overviews:participant", kwargs={"nickname": "roboanna"})

    def test_detail(self):
        detail = participant_detail(self.anna.profile)
        levels = {s.topic.slug: s.progress.level for s in detail.sections}
        self.assertEqual(levels["code"], 2)  # 2 stars × 10 points
        self.assertEqual(detail.submissions, [self.approved, self.first])
        self.assertEqual(detail.submissions[0].points, 20)
        self.assertEqual(
            [r.status for r in detail.hint_requests],
            [HintRequest.Status.OPEN, HintRequest.Status.DECLINED],
        )
        # Started first, then open; solved and locked (servo) tasks left out.
        self.assertEqual(
            [e.task for e in detail.suggestions], [self.hint_task, self.line]
        )

    def test_drafts_are_left_out(self):
        start_attempt(self.ben, self.line)
        detail = participant_detail(self.ben.profile)
        self.assertEqual(len(detail.submissions), 1)
        self.assertEqual(detail.hint_requests, [])

    def test_archived_tasks_stay_in_the_history(self):
        self.blink.is_archived = True
        self.blink.save()
        detail = participant_detail(self.anna.profile)
        self.assertEqual(detail.submissions, [self.approved, self.first])

    def test_page_for_coaches(self):
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Fortschritt: RoboAnna – ")
        self.assertContains(response, "Anna Muster")
        self.assertContains(response, "Level 2")
        self.assertContains(response, "2 von 3 Sternen")
        self.assertContains(response, "20 Punkte")
        self.assertContains(response, "Die LED blinkt noch nicht.")
        self.assertContains(
            response, reverse("submissions:review", kwargs={"pk": self.approved.pk})
        )
        self.assertContains(response, "Abgelehnt")
        self.assertContains(response, "Motor dreht nicht")
        self.assertContains(response, "Antwort: «Kabel?»")
        self.assertContains(response, "in der Warteschlange")
        self.assertNotContains(response, "BenBot")

    def test_linked_from_matrix_and_profile(self):
        self.client.force_login(self.coach)
        link = 'href="/fortschritt/teilnehmende/RoboAnna/"'
        self.assertContains(self.client.get(reverse("overviews:matrix")), link)
        profile = reverse(
            "accounts:participant_detail", kwargs={"nickname": "RoboAnna"}
        )
        self.assertContains(self.client.get(profile), link)

    def test_participants_get_403_and_no_link(self):
        self.client.force_login(self.ben)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        profile = reverse(
            "accounts:participant_detail", kwargs={"nickname": "RoboAnna"}
        )
        self.assertNotContains(self.client.get(profile), "/fortschritt/")

    def test_unknown_staff_or_inactive_is_404(self):
        self.client.force_login(self.coach)
        for nickname in ("gibt-es-nicht", "CoachCarla"):
            url = reverse("overviews:participant", kwargs={"nickname": nickname})
            self.assertEqual(self.client.get(url).status_code, 404)
        self.anna.is_active = False
        self.anna.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
