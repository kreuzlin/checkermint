"""Task detail for coaches (brief 5.10.4, #41)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from hints.models import HintRequest
from hints.services import decide_request, request_hint
from hints.tests.test_requests import task_with_hints
from overviews.task import task_detail
from submissions.tests.test_progress import reviewed
from tasks.models import Hint

from .test_matrix import participant

User = get_user_model()
GRANTED = HintRequest.Status.GRANTED
DECLINED = HintRequest.Status.DECLINED


class TaskDetailTests(TestCase):
    def setUp(self):
        self.anna = participant("anna", "RoboAnna", "Anna Muster")
        self.ben = participant("ben", "BenBot")
        self.luna = participant("luna", "LunaLED")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")

        self.task, self.v1 = task_with_hints()  # hints: motor, sensor
        decide_request(request_hint(self.anna, self.task), self.coach, GRANTED)
        decide_request(request_hint(self.ben, self.task), self.coach, DECLINED)
        request_hint(self.ben, self.task)  # motor again, open
        self.anna_v1 = reviewed(self.anna, self.task, "approved", stars=2)

        self.v2 = self.task.create_draft()
        self.v2.change_note = "Sensor-Hinweis ersetzt."
        self.v2.save()
        self.v2.hints.filter(key="sensor").delete()
        Hint.objects.create(task_version=self.v2, key="kabel", order=5, text="Kabel")
        self.v2.publish()

        self.anna_v2 = reviewed(self.anna, self.task, "approved", stars=3)
        self.ben_v1 = reviewed(
            self.ben, self.task, "approved", stars=1, version=self.v1
        )
        reviewed(self.luna, self.task, "needs_revision")
        self.url = reverse("overviews:task", kwargs={"slug": self.task.slug})

    def test_solvers_with_best_submission_and_average(self):
        detail = task_detail(self.task)
        self.assertEqual(
            [(s.profile.nickname, s.submission) for s in detail.solvers],
            [("BenBot", self.ben_v1), ("RoboAnna", self.anna_v2)],
        )
        self.assertEqual(detail.average_stars, 2.0)

    def test_inactive_participants_are_not_solvers(self):
        self.ben.is_active = False
        self.ben.save()
        detail = task_detail(self.task)
        self.assertEqual([s.profile.nickname for s in detail.solvers], ["RoboAnna"])
        self.assertEqual(detail.average_stars, 3.0)

    def test_hint_statistics_by_key(self):
        stats = {
            s.hint.key: (s.requested, s.granted, s.declined, s.open)
            for s in task_detail(self.task).hints
        }
        self.assertEqual(
            stats,
            {"motor": (3, 1, 1, 1), "kabel": (0, 0, 0, 0), "sensor": (0, 0, 0, 0)},
        )
        keys = [s.hint.key for s in task_detail(self.task).hints]
        self.assertEqual(keys, ["motor", "kabel", "sensor"])  # newest version first

    def test_versions_with_pinned_participants(self):
        versions = task_detail(self.task).versions
        self.assertEqual([(v.number, v.pinned) for v in versions], [(2, 0), (1, 2)])

    def test_without_submissions(self):
        task, _ = task_with_hints(slug="leer")
        detail = task_detail(task)
        self.assertEqual(detail.solvers, [])
        self.assertIsNone(detail.average_stars)

    def test_page_for_coaches(self):
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, f"<title>Auswertung: {self.v2.title} – ")
        self.assertContains(response, "im Schnitt 2,0 von 3 Sternen")
        self.assertContains(response, "Anna Muster")
        self.assertContains(
            response, reverse("submissions:review", kwargs={"pk": self.anna_v2.pk})
        )
        self.assertNotContains(response, "LunaLED")
        self.assertContains(response, "Sensor-Hinweis ersetzt.")
        self.assertContains(response, "zuletzt in Version 1")  # sensor

    def test_archived_task_is_shown_to_coaches(self):
        self.task.is_archived = True
        self.task.save()
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, "archiviert")

    def test_linked_from_matrix_and_task_page(self):
        self.client.force_login(self.coach)
        link = f'href="{self.url}"'
        self.assertContains(self.client.get(reverse("overviews:matrix")), link)
        task_page = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.assertContains(self.client.get(task_page), link)

    def test_participants_get_403_and_no_link(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        task_page = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.assertNotContains(self.client.get(task_page), self.url)

    def test_unknown_task_is_404(self):
        self.client.force_login(self.coach)
        url = reverse("overviews:task", kwargs={"slug": "gibt-es-nicht"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
