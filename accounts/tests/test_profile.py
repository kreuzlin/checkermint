"""Profile model and roles (brief, sections 2, 4 and 5.1)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME, COACH_PERMISSIONS, is_coach

User = get_user_model()


def make_profile(username="anna", nickname="Robo-Anna", **kwargs):
    user = User.objects.create_user(username, password="geheim123")
    return Profile.objects.create(
        user=user, nickname=nickname, real_name="Anna Muster", **kwargs
    )


class ProfileTests(TestCase):
    def test_visibility_is_private_by_default(self):
        profile = make_profile()
        self.assertFalse(profile.show_badges)
        self.assertFalse(profile.show_about)
        self.assertFalse(profile.show_solved_tasks)

    def test_avatar_seed_is_random(self):
        a = make_profile("a", "Alpha")
        b = make_profile("b", "Beta")
        self.assertEqual(len(a.avatar_seed), 16)
        self.assertNotEqual(a.avatar_seed, b.avatar_seed)

    def test_str_is_nickname(self):
        self.assertEqual(str(make_profile()), "Robo-Anna")

    def test_valid_nicknames(self):
        for nickname in ["Max", "Zoë", "robo_2", "Lea-Sophie", "R2"]:
            with self.subTest(nickname=nickname):
                profile = Profile(
                    user=User(username="x"), nickname=nickname, real_name="X"
                )
                profile.full_clean(exclude=["user"])

    def test_invalid_nicknames(self):
        for nickname in ["A", "mit Leerzeichen", "-start", "_start", "a/b", "x" * 31]:
            with self.subTest(nickname=nickname):
                profile = Profile(nickname=nickname, real_name="X")
                with self.assertRaises(ValidationError) as cm:
                    profile.full_clean(exclude=["user"])
                self.assertIn("nickname", cm.exception.message_dict)

    def test_nickname_unique_ignoring_case(self):
        make_profile()
        other = Profile(nickname="robo-anna", real_name="Andere")
        with self.assertRaises(ValidationError) as cm:
            other.full_clean(exclude=["user"])
        self.assertIn("Dieser Spitzname ist schon vergeben.", str(cm.exception))


class CoachRoleTests(TestCase):
    def test_coach_group_permissions(self):
        group = Group.objects.get(name=COACH_GROUP_NAME)
        permissions = set(
            group.permissions.values_list("content_type__app_label", "codename")
        )
        expected = {
            (app_label, f"{action}_{model}")
            for app_label, models in COACH_PERMISSIONS.items()
            for model, actions in models.items()
            for action in actions
        }
        self.assertEqual(permissions, expected)
        self.assertIn(("accounts", "change_profile"), permissions)
        self.assertIn(("auth", "add_user"), permissions)
        # Accounts are deactivated, never deleted by coaches.
        self.assertNotIn(("auth", "delete_user"), permissions)

    def test_is_coach(self):
        group = Group.objects.get(name=COACH_GROUP_NAME)
        participant = User.objects.create_user("teilnehmer")
        coach = User.objects.create_user("coach", is_staff=True)
        coach.groups.add(group)
        staff_without_group = User.objects.create_user("staff", is_staff=True)
        group_without_staff = User.objects.create_user("nostaff")
        group_without_staff.groups.add(group)
        inactive_coach = User.objects.create_user("alt", is_staff=True, is_active=False)
        inactive_coach.groups.add(group)
        admin = User.objects.create_superuser("admin")

        self.assertFalse(is_coach(participant))
        self.assertTrue(is_coach(coach))
        self.assertFalse(is_coach(staff_without_group))
        self.assertFalse(is_coach(group_without_staff))
        self.assertFalse(is_coach(inactive_coach))
        self.assertTrue(is_coach(admin))
