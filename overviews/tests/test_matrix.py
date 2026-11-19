"""Progress matrix for coaches (brief 5.10.2, #39)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from overviews.matrix import progress_matrix
from submissions.tests.test_progress import make_task, reviewed
from tasks.attempts import start_attempt
from tasks.catalogue import Status
from tasks.models import Topic
from tasks.tests.test_levels import add_levels

User = get_user_model()


def participant(username, nickname, real_name=""):
    user = User.objects.create_user(username, password="geheim123")
    Profile.objects.create(user=user, nickname=nickname, real_name=real_name)
    return user


class ProgressMatrixTests(TestCase):
    def setUp(self):
        add_levels(20)
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.build = Topic.objects.create(name="Bauen", slug="bauen", order=2)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.line = make_task(self.code, "linie", base_points=10, min_level=2)
        self.arm = make_task(self.build, "arm", base_points=10)
        self.anna = participant("anna", "RoboAnna", "Anna Muster")
        self.ben = participant("ben", "BenBot")
        self.luna = participant("luna", "LunaLED")
        self.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        Profile.objects.create(user=self.coach, nickname="CoachCarla", real_name="C")
        self.url = reverse("overviews:matrix")

        reviewed(self.anna, self.blink, "approved", stars=2)  # 20 points: level 2
        reviewed(self.ben, self.blink, "submitted")
        reviewed(self.ben, self.arm, "needs_revision")
        start_attempt(self.luna, self.blink)

    def cells(self, matrix):
        return {
            row.profile.nickname: [(state.status, state.stars) for state in row.cells]
            for row in matrix.rows
        }

    def test_status_per_participant_and_task(self):
        matrix = progress_matrix()
        self.assertEqual(
            [column.task for column in matrix.columns],
            [self.blink, self.line, self.arm],
        )
        self.assertEqual(
            self.cells(matrix),
            {
                "BenBot": [
                    (Status.SUBMITTED, None),
                    (Status.LOCKED, None),
                    (Status.NEEDS_REVISION, None),
                ],
                "LunaLED": [
                    (Status.STARTED, None),
                    (Status.LOCKED, None),
                    (Status.OPEN, None),
                ],
                "RoboAnna": [
                    (Status.SOLVED, 2),
                    (Status.OPEN, None),  # level 2 in Code unlocks it
                    (Status.OPEN, None),
                ],
            },
        )

    def test_filter_by_topic_shows_the_level(self):
        matrix = progress_matrix(self.code)
        self.assertEqual(
            [column.task for column in matrix.columns], [self.blink, self.line]
        )
        levels = {row.profile.nickname: row.level for row in matrix.rows}
        self.assertEqual(levels, {"BenBot": 1, "LunaLED": 1, "RoboAnna": 2})

    def test_coaches_and_inactive_participants_are_not_rows(self):
        self.luna.is_active = False
        self.luna.save()
        nicknames = [row.profile.nickname for row in progress_matrix().rows]
        self.assertEqual(nicknames, ["BenBot", "RoboAnna"])

    def test_hidden_tasks_are_not_columns(self):
        self.arm.is_archived = True
        self.arm.save()
        columns = [column.task for column in progress_matrix().columns]
        self.assertNotIn(self.arm, columns)

    def test_query_count_does_not_grow_with_participants(self):
        with self.assertNumQueries(7):
            progress_matrix()
        for i in range(5):
            reviewed(participant(f"p{i}", f"P{i}"), self.blink, "approved", stars=1)
        with self.assertNumQueries(7):
            progress_matrix()

    def test_page_for_coaches(self):
        self.client.force_login(self.coach)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Fortschritt – ")
        self.assertContains(response, "RoboAnna")
        self.assertContains(response, "Anna Muster")
        self.assertContains(response, "2 von 3 Sternen")
        self.assertContains(response, "Eingereicht")
        self.assertContains(response, "Überarbeitung nötig")
        self.assertContains(response, "Gesperrt")
        self.assertContains(response, 'href="/fortschritt/"')  # navigation

    def test_page_filter(self):
        self.client.force_login(self.coach)
        response = self.client.get(self.url, {"thema": "bauen"})
        self.assertContains(response, '<option value="bauen" selected>')
        self.assertContains(response, '<th scope="col">Level</th>', html=True)
        self.assertNotContains(response, "/aufgaben/blink/")
        # Unknown topics fall back to all topics.
        response = self.client.get(self.url, {"thema": "gibt-es-nicht"})
        self.assertContains(response, "/aufgaben/blink/")

    def test_participants_get_403(self):
        self.client.force_login(self.anna)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(
            self.client.get(reverse("tasks:catalogue")), 'href="/fortschritt/"'
        )

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
