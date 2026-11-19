"""Public profile pages /p/<nickname>/ (brief 4, 5.1, 5.12, #46)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from badges.models import Badge, UserBadge
from submissions.tests.test_progress import make_task, reviewed
from tasks.models import Topic
from tasks.tests.test_levels import add_levels

User = get_user_model()


class PublicProfileTests(TestCase):
    def setUp(self):
        add_levels(20)
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.hidden = make_task(self.code, "geheim", base_points=10)
        self.user = User.objects.create_user(
            "anna", password="geheim123", email="anna@example.org"
        )
        self.profile = Profile.objects.create(
            user=self.user,
            nickname="RoboAnna",
            real_name="Anna Muster",
            about="Ich baue **Roboter**.",
        )
        approved = reviewed(self.user, self.blink, "approved", stars=2)
        approved.feedback = "Geheimes Feedback"
        approved.save()
        reviewed(self.user, self.hidden, "approved", stars=1)
        self.hidden.is_archived = True
        self.hidden.save()
        badge = Badge.objects.create(name="Blinkprofi")
        UserBadge.objects.create(user=self.user, badge=badge, submission=approved)
        self.url = reverse("accounts:public_profile", kwargs={"nickname": "roboanna"})

    def get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response

    def assert_never_private(self, response):
        for private in (
            "Anna Muster",
            "anna@example.org",
            "anna",  # username
            "Geheimes Feedback",
            "/dateien/",
        ):
            self.assertNotContains(response, private)

    def test_defaults_show_only_nickname_avatar_and_levels(self):
        response = self.get()
        self.assertContains(response, "<title>RoboAnna – ")
        self.assertContains(response, "/avatar/")
        self.assertContains(response, "Level 2")  # 20 + 10 points in Code
        self.assertContains(response, "30 Punkte")  # archived tasks count too
        self.assertNotContains(response, "Blinkprofi")
        self.assertNotContains(response, "Roboter</strong>")
        self.assertNotContains(response, "Gelöste Aufgaben")
        self.assertNotContains(response, "Blink")
        self.assert_never_private(response)

    def test_everything_public(self):
        self.profile.show_about = True
        self.profile.show_badges = True
        self.profile.show_solved_tasks = True
        self.profile.save()
        response = self.get()
        self.assertContains(response, "<strong>Roboter</strong>")
        self.assertContains(response, "Blinkprofi")
        self.assertContains(response, "Gelöste Aufgaben")
        self.assertContains(response, '<span class="task-title">Blink</span>')
        # The badge does not reveal the task unless solved tasks are public.
        self.assertNotContains(response, "Geheim")  # archived task left out
        self.assert_never_private(response)

    def test_badges_public_without_solved_tasks_hides_the_task(self):
        self.profile.show_badges = True
        self.profile.save()
        response = self.get()
        self.assertContains(response, "Blinkprofi")
        self.assertNotContains(response, "Blink<")
        self.assertNotContains(response, "Blink ·")

    def test_no_login_needed_and_noindex(self):
        response = self.get()
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertNotContains(response, "Internes Profil")

    def test_staff_inactive_and_unknown_are_404(self):
        coach = User.objects.create_user("coach", password="x" * 10, is_staff=True)
        Profile.objects.create(user=coach, nickname="CoachCarla")
        for nickname in ("CoachCarla", "gibt-es-nicht"):
            url = reverse("accounts:public_profile", kwargs={"nickname": nickname})
            self.assertEqual(self.client.get(url).status_code, 404)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_linked_from_own_and_internal_profile(self):
        self.client.force_login(self.user)
        link = 'href="/p/RoboAnna/"'
        self.assertContains(self.client.get(reverse("accounts:profile_edit")), link)
        internal = reverse(
            "accounts:participant_detail", kwargs={"nickname": "RoboAnna"}
        )
        self.assertContains(self.client.get(internal), link)
        self.assertContains(self.get(), "Internes Profil")
