"""Participant dashboard on the home page (brief 5.9, #35)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from badges.models import Badge, UserBadge
from submissions.dashboard import dashboard
from submissions.models import Submission
from tasks.attempts import start_attempt
from tasks.models import Topic
from tasks.tests.test_levels import add_levels

from .test_progress import make_task, reviewed

User = get_user_model()


class DashboardTests(TestCase):
    def setUp(self):
        add_levels(20, 50)
        self.anna = User.objects.create_user("anna", password="geheim123")
        Profile.objects.create(user=self.anna, nickname="RoboAnna", real_name="Anna")
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.build = Topic.objects.create(name="Bauen", slug="bauen", order=2)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.sensor = make_task(self.code, "sensor")
        self.line = make_task(self.code, "linie", min_level=2)
        self.arm = make_task(self.build, "arm")
        self.client.force_login(self.anna)

    def home(self):
        return self.client.get(reverse("core:home"))

    def test_greets_and_shows_levels_per_topic(self):
        reviewed(self.anna, self.blink, stars=3)
        response = self.home()
        self.assertTemplateUsed(response, "submissions/dashboard.html")
        self.assertContains(response, "Hallo RoboAnna!")
        self.assertContains(response, "<strong>Level 2</strong> · 30 Punkte")
        self.assertContains(response, "<strong>Level 1</strong> · 0 Punkte")

    def test_open_revisions_with_feedback(self):
        first = reviewed(self.anna, self.sensor, "needs_revision")
        first.feedback = "Erkläre den **Sensor**."
        first.save()
        # Revised and approved later: no longer open.
        reviewed(self.anna, self.arm, "needs_revision")
        reviewed(self.anna, self.arm, stars=1)
        board = dashboard(self.anna)
        self.assertEqual([s.task for s in board.revisions], [self.sensor])
        response = self.home()
        self.assertContains(response, "Überarbeiten")
        self.assertContains(response, "Erkläre den <strong>Sensor</strong>.")

    def test_resubmitted_revision_is_waiting_not_open(self):
        reviewed(self.anna, self.sensor, "needs_revision")
        reviewed(self.anna, self.sensor, "submitted")
        board = dashboard(self.anna)
        self.assertEqual(board.revisions, [])
        self.assertEqual(board.waiting, 1)
        self.assertContains(self.home(), "1 Lösung wartet auf einen Coach.")

    def test_recently_approved_with_points(self):
        reviewed(self.anna, self.blink, stars=2)
        reviewed(self.anna, self.arm, stars=1)
        board = dashboard(self.anna)
        self.assertEqual(
            [(s.task, s.points) for s in board.approved],
            [(self.arm, 10), (self.blink, 20)],
        )
        self.assertContains(self.home(), "20 Punkte")

    def test_suggestions_started_first_then_lowest_level_without_locked(self):
        start_attempt(self.anna, self.arm)
        tasks = [e.task for e in dashboard(self.anna).suggestions]
        self.assertEqual(tasks, [self.arm, self.blink, self.sensor])
        reviewed(self.anna, self.blink, stars=3)  # level 2: line unlocks
        reviewed(self.anna, self.sensor, "submitted")
        tasks = [e.task for e in dashboard(self.anna).suggestions]
        self.assertEqual(tasks, [self.arm, self.line])

    def test_nothing_left(self):
        for task in (self.blink, self.sensor, self.arm):
            reviewed(self.anna, task, stars=3)
        reviewed(self.anna, self.line, stars=1)
        response = self.home()
        self.assertContains(response, "Gerade gibt es keine offene Aufgabe für dich.")

    def test_badge_feed_on_dashboard(self):
        UserBadge.objects.create(
            user=self.anna, badge=Badge.objects.create(name="Sensorprofi")
        )
        self.assertContains(self.home(), "<strong>Sensorprofi</strong> für")

    def test_query_count_stays_small(self):
        reviewed(self.anna, self.blink, stars=3)
        reviewed(self.anna, self.sensor, "needs_revision")
        with self.assertNumQueries(13):
            self.home()

    def test_other_participants_data_is_not_mixed_in(self):
        ben = User.objects.create_user("ben", password="geheim123")
        reviewed(ben, self.blink, stars=3)
        reviewed(ben, self.sensor, "needs_revision")
        board = dashboard(self.anna)
        self.assertEqual((board.revisions, board.approved, board.waiting), ([], [], 0))


class HomeForOthersTests(TestCase):
    def test_visitors_see_the_start_page(self):
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "Hallo")
        self.assertTemplateNotUsed(response, "submissions/dashboard.html")

    def test_coaches_see_the_queue(self):
        coach = User.objects.create_user("coach", password="geheim123", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        anna = User.objects.create_user("anna", password="geheim123")
        topic = Topic.objects.create(name="Code", slug="code")
        reviewed(anna, make_task(topic, "blink"), "submitted")
        self.client.force_login(coach)
        response = self.client.get(reverse("core:home"))
        self.assertTemplateNotUsed(response, "submissions/dashboard.html")
        self.assertContains(response, "Warteschlange: 1 Lösung wartet")
        self.assertContains(response, "Neue Badges im Club")
        self.assertEqual(Submission.objects.count(), 1)
