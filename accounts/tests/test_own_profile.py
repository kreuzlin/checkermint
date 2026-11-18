"""Own profile, visibility switches and internal profiles (issue #13)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME

User = get_user_model()


def participant(username, nickname, **user_fields):
    user = User.objects.create_user(username, password="Roboter-77", **user_fields)
    Profile.objects.create(user=user, nickname=nickname, real_name=f"Echt {username}")
    return user


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = participant("anna", "Robo-Anna", email="anna@example.com")
        self.url = reverse("accounts:profile_edit")
        self.client.force_login(self.user)

    def post(self, **data):
        base = {"email": "anna@example.com", "about": "", "email_notifications": "on"}
        return self.client.post(self.url, {**base, **data}, follow=True)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_page_shows_profile_and_private_defaults(self):
        response = self.client.get(self.url)
        self.assertContains(response, "<title>Mein Profil – Checkermint</title>")
        self.assertContains(response, "Echt anna")
        self.assertContains(response, "Was ist öffentlich?")
        for name in ("show_about", "show_badges", "show_solved_tasks"):
            field = response.context["form"][name]
            self.assertFalse(field.value(), name)
        self.assertNotContains(response, "ß")

    def test_header_links_to_own_profile(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, f'href="{self.url}"')

    def test_saves_about_switches_and_email(self):
        response = self.post(
            about="Ich baue **Roboter**.",
            show_about="on",
            show_badges="on",
            email="neu@example.com",
            email_notifications="",
        )
        self.assertContains(response, "Dein Profil ist gespeichert.")
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.about, "Ich baue **Roboter**.")
        self.assertTrue(profile.show_about)
        self.assertTrue(profile.show_badges)
        self.assertFalse(profile.show_solved_tasks)
        self.assertFalse(profile.email_notifications)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "neu@example.com")

    def test_email_can_be_removed(self):
        self.post(email="")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "")

    def test_invalid_email_and_too_long_about(self):
        response = self.post(email="kein-mail", about="x" * 1001)
        self.assertContains(response, "Fehler:")
        self.assertEqual(len(response.context["form"].errors), 2)

    def test_nickname_and_real_name_cannot_be_changed(self):
        self.post(nickname="Hacker", real_name="Anders")
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.nickname, "Robo-Anna")
        self.assertEqual(profile.real_name, "Echt anna")

    def test_staff_without_profile_sees_hint(self):
        admin = User.objects.create_superuser("chef", password="Roboter-777")
        self.client.force_login(admin)
        response = self.client.get(self.url)
        self.assertContains(response, "noch kein Profil")


class InternalProfileTests(TestCase):
    def setUp(self):
        self.anna = participant("anna", "Robo-Anna", email="anna@example.com")
        self.ben = participant("ben", "Blitz", email="ben@example.com")
        Profile.objects.filter(user=self.anna).update(about="Ich mag *Lego*.")
        self.anna_url = reverse(
            "accounts:participant_detail", kwargs={"nickname": "Robo-Anna"}
        )

    def test_requires_login(self):
        for url in (reverse("accounts:participant_list"), self.anna_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_nav_entry_only_for_logged_in_users(self):
        list_url = reverse("accounts:participant_list")
        self.assertNotContains(self.client.get(reverse("core:home")), list_url)
        self.client.force_login(self.ben)
        self.assertContains(self.client.get(reverse("core:home")), list_url)

    def test_list_shows_active_participants_only(self):
        participant("weg", "Weg", is_active=False)
        coach = participant("coach", "CoachX", is_staff=True)
        self.client.force_login(self.ben)
        response = self.client.get(reverse("accounts:participant_list"))
        self.assertContains(response, "Robo-Anna")
        self.assertContains(response, "Blitz")
        self.assertNotContains(response, "Weg")
        self.assertNotContains(response, coach.profile.nickname)

    def test_other_participant_sees_real_name_and_about_but_not_email(self):
        self.client.force_login(self.ben)
        response = self.client.get(self.anna_url)
        self.assertContains(response, "<title>Robo-Anna – Checkermint</title>")
        self.assertContains(response, "Echt anna")
        self.assertContains(response, "<em>Lego</em>", html=False)
        self.assertNotContains(response, "anna@example.com")
        self.assertNotContains(response, "Profil bearbeiten")

    def test_own_internal_profile_shows_email_and_edit_link(self):
        self.client.force_login(self.anna)
        response = self.client.get(self.anna_url)
        self.assertContains(response, "anna@example.com")
        self.assertContains(response, "Profil bearbeiten")

    def test_coach_sees_email(self):
        coach = User.objects.create_user("coach", password="Roboter-777", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        response = self.client.get(self.anna_url)
        self.assertContains(response, "anna@example.com")

    def test_nickname_lookup_ignores_case(self):
        self.client.force_login(self.ben)
        url = reverse("accounts:participant_detail", kwargs={"nickname": "robo-anna"})
        self.assertContains(self.client.get(url), "Echt anna")

    def test_inactive_or_staff_profiles_are_not_found(self):
        participant("weg", "Weg", is_active=False)
        participant("coach", "CoachX", is_staff=True)
        self.client.force_login(self.ben)
        for nickname in ("Weg", "CoachX", "Unbekannt"):
            url = reverse("accounts:participant_detail", kwargs={"nickname": nickname})
            self.assertEqual(self.client.get(url).status_code, 404, nickname)
