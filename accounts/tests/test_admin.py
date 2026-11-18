"""Coaches manage participant accounts in the admin (brief 5.1, #11)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME

User = get_user_model()


def add_form_data(**overrides):
    data = {
        "username": "lena",
        "password1": "Robo42",
        "password2": "Robo42",
        "email": "",
        "profile-TOTAL_FORMS": "1",
        "profile-INITIAL_FORMS": "0",
        "profile-MIN_NUM_FORMS": "1",
        "profile-MAX_NUM_FORMS": "1",
        "profile-0-nickname": "Lena-Bot",
        "profile-0-real_name": "Lena Beispiel",
        "profile-0-about": "",
        "profile-0-email_notifications": "on",
        "_save": "Sichern",
    }
    data.update(overrides)
    return data


class CoachAccountAdminTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(
            "coach", password="Coach-Pass-1", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.admin = User.objects.create_superuser("chef", password="Chef-Pass-1")
        self.other_coach = User.objects.create_user("coach2", is_staff=True)
        self.participant = User.objects.create_user("anna", password="Robo42x")
        Profile.objects.create(
            user=self.participant, nickname="Robo-Anna", real_name="Anna Muster"
        )
        self.client.force_login(self.coach)

    # --- Creating accounts ------------------------------------------------

    def test_coach_creates_participant_with_profile_in_one_form(self):
        response = self.client.post(reverse("admin:auth_user_add"), add_form_data())
        self.assertEqual(response.status_code, 302, response.content[:3000])
        user = User.objects.get(username="lena")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password("Robo42"))
        self.assertEqual(user.profile.nickname, "Lena-Bot")
        self.assertEqual(user.profile.real_name, "Lena Beispiel")
        self.assertFalse(user.profile.show_badges)

    def test_add_form_has_no_unusable_password_option(self):
        response = self.client.get(reverse("admin:auth_user_add"))
        # Django's add template always loads the field's CSS/JS; the field
        # itself must be missing.
        self.assertNotContains(response, 'name="usable_password"')
        self.assertContains(response, "profile-0-nickname")

    def test_profile_is_required_for_coaches(self):
        data = add_form_data(**{"profile-TOTAL_FORMS": "0"})
        response = self.client.post(reverse("admin:auth_user_add"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="lena").exists())

    def test_participant_password_rule_applies(self):
        data = add_form_data(password1="Rob42", password2="Rob42")
        response = self.client.post(reverse("admin:auth_user_add"), data)
        self.assertContains(response, "mindestens 6 Zeichen")
        self.assertFalse(User.objects.filter(username="lena").exists())

    def test_coach_cannot_create_staff_or_superuser(self):
        data = add_form_data(is_staff="on", is_superuser="on")
        self.client.post(reverse("admin:auth_user_add"), data)
        user = User.objects.get(username="lena")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    # --- Editing accounts -------------------------------------------------

    def change_url(self, user):
        return reverse("admin:auth_user_change", args=[user.pk])

    def test_change_form_hides_rights_fields(self):
        response = self.client.get(self.change_url(self.participant))
        self.assertEqual(response.status_code, 200)
        for field in ["is_superuser", "is_staff", "groups", "user_permissions"]:
            self.assertNotContains(response, f'name="{field}"')
        self.assertContains(response, 'name="is_active"')

    def test_coach_cannot_escalate_participant(self):
        data = {
            "username": "anna",
            "email": "",
            "is_active": "on",
            "is_staff": "on",
            "is_superuser": "on",
            "groups": [Group.objects.get(name=COACH_GROUP_NAME).pk],
            "profile-TOTAL_FORMS": "1",
            "profile-INITIAL_FORMS": "1",
            "profile-MIN_NUM_FORMS": "1",
            "profile-MAX_NUM_FORMS": "1",
            "profile-0-id": self.participant.profile.pk,
            "profile-0-user": self.participant.pk,
            "profile-0-nickname": "Robo-Anna",
            "profile-0-real_name": "Anna Muster",
            "_save": "Sichern",
        }
        response = self.client.post(self.change_url(self.participant), data)
        self.assertEqual(response.status_code, 302)
        self.participant.refresh_from_db()
        self.assertFalse(self.participant.is_staff)
        self.assertFalse(self.participant.is_superuser)
        self.assertFalse(self.participant.groups.exists())

    def test_coach_sets_new_password_for_participant(self):
        url = reverse("admin:auth_user_password_change", args=[self.participant.pk])
        response = self.client.post(
            url, {"password1": "Neu-123", "password2": "Neu-123"}
        )
        self.assertEqual(response.status_code, 302)
        self.participant.refresh_from_db()
        self.assertTrue(self.participant.check_password("Neu-123"))

    def test_coach_cannot_delete_accounts(self):
        url = reverse("admin:auth_user_delete", args=[self.participant.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    # --- Staff accounts are out of reach ----------------------------------

    def test_list_shows_only_participants(self):
        response = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertContains(response, "Robo-Anna")
        self.assertContains(response, "Anna Muster")
        for username in ["chef", "coach2"]:
            self.assertNotContains(response, f">{username}<")

    def test_coach_cannot_open_staff_accounts(self):
        for user in [self.admin, self.other_coach, self.coach]:
            with self.subTest(user=user.username):
                response = self.client.get(self.change_url(user))
                self.assertNotEqual(response.status_code, 200)

    def test_coach_cannot_change_admin_password(self):
        url = reverse("admin:auth_user_password_change", args=[self.admin.pk])
        response = self.client.post(
            url, {"password1": "Gekapert-1", "password2": "Gekapert-1"}
        )
        self.assertNotEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("Chef-Pass-1"))

    def test_profile_admin_lists_only_participants_and_has_no_add(self):
        Profile.objects.create(user=self.admin, nickname="Chef", real_name="C")
        response = self.client.get(reverse("admin:accounts_profile_changelist"))
        self.assertContains(response, "Robo-Anna")
        self.assertNotContains(response, ">Chef<")
        add = self.client.get(reverse("admin:accounts_profile_add"))
        self.assertEqual(add.status_code, 403)

    def test_coach_cannot_manage_groups(self):
        response = self.client.get(reverse("admin:auth_group_changelist"))
        self.assertEqual(response.status_code, 403)


class AdminUserAdminTests(TestCase):
    def test_superuser_keeps_full_form(self):
        admin = User.objects.create_superuser("chef", password="Chef-Pass-1")
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:auth_user_change", args=[admin.pk]))
        self.assertContains(response, 'name="is_superuser"')
        self.assertContains(response, 'name="groups"')
        add = self.client.get(reverse("admin:auth_user_add"))
        self.assertContains(add, 'name="usable_password"')
