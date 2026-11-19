"""Ranking per topic (brief 5.9, #48)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from overviews.tests.test_matrix import participant
from submissions.ranking import topic_ranking
from tasks.models import Topic
from tasks.tests.test_levels import add_levels

from .test_progress import make_task, reviewed

User = get_user_model()


class RankingTests(TestCase):
    def setUp(self):
        add_levels(20)
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.build = Topic.objects.create(name="Bauen", slug="bauen", order=2)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.servo = make_task(self.code, "servo", base_points=10)
        self.arm = make_task(self.build, "arm", base_points=10)
        self.anna = participant("anna", "RoboAnna", "Anna Muster")
        self.ben = participant("ben", "BenBot")
        self.cleo = participant("cleo", "CleoChip")
        self.dan = participant("dan", "DanDiode")
        reviewed(self.anna, self.blink, "approved", stars=1)
        reviewed(self.anna, self.blink, "approved", stars=3)  # best counts: 30
        reviewed(self.ben, self.blink, "approved", stars=1)
        reviewed(self.ben, self.servo, "approved", stars=1)  # 20
        reviewed(self.cleo, self.blink, "approved", stars=2)  # 20
        reviewed(self.dan, self.arm, "approved", stars=3)  # only in Bauen
        reviewed(self.dan, self.servo, "submitted")
        self.url = reverse("submissions:ranking")

    def test_order_ties_and_levels(self):
        ranking = topic_ranking(self.code)
        self.assertEqual(
            [(r.rank, r.profile.nickname, r.points, r.level) for r in ranking.rows],
            [(1, "RoboAnna", 30, 2), (2, "BenBot", 20, 2), (2, "CleoChip", 20, 2)],
        )
        self.assertEqual(ranking.without_points, 1)

    def test_inactive_and_staff_are_left_out(self):
        self.anna.is_active = False
        self.anna.save()
        self.ben.is_staff = True
        self.ben.save()
        rows = topic_ranking(self.code).rows
        self.assertEqual(
            [(r.rank, r.profile.nickname) for r in rows], [(1, "CleoChip")]
        )

    def test_page_shows_first_topic_and_filters(self):
        self.client.force_login(self.ben)
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Rangliste – ")
        self.assertContains(response, "<h2>Code</h2>", html=True)
        self.assertContains(response, "(du)")
        self.assertNotContains(response, "Anna Muster")
        response = self.client.get(self.url, {"thema": "bauen"})
        self.assertContains(response, "DanDiode")
        self.assertNotContains(response, "RoboAnna")

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_linked_only_from_the_catalogue(self):
        self.client.force_login(self.ben)
        link = f'href="{self.url}"'
        self.assertContains(self.client.get(reverse("tasks:catalogue")), link)
        self.assertNotContains(self.client.get(reverse("core:home")), link)
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("core:home")), link)
