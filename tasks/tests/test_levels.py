"""Topics and the shared level table (brief 5.3, ADR 0013, issue #15)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from tasks.levels import level_for_points
from tasks.models import LevelThreshold, Topic

User = get_user_model()


def add_levels(*min_points):
    """Levels 2, 3, … with the given thresholds (level 1 exists already)."""
    for level, points in enumerate(min_points, start=2):
        LevelThreshold.objects.create(level=level, min_points=points)


class LevelThresholdValidationTests(TestCase):
    def check(self, **fields):
        LevelThreshold(**fields).full_clean()

    def test_level_one_exists_after_migration(self):
        self.assertTrue(LevelThreshold.objects.filter(level=1, min_points=0).exists())

    def test_level_one_must_start_at_zero(self):
        level1 = LevelThreshold.objects.get(level=1)
        level1.min_points = 5
        with self.assertRaisesMessage(ValidationError, "bei 0 Punkten"):
            level1.full_clean()

    def test_only_level_one_at_zero(self):
        with self.assertRaises(ValidationError):
            self.check(level=2, min_points=0)

    def test_no_gaps(self):
        with self.assertRaisesMessage(ValidationError, "Zuerst muss es Level 2"):
            self.check(level=3, min_points=50)

    def test_points_rise_strictly(self):
        add_levels(10, 30)
        with self.assertRaisesMessage(ValidationError, "Höhere Levels"):
            self.check(level=4, min_points=30)
        middle = LevelThreshold.objects.get(level=2)
        middle.min_points = 40
        with self.assertRaisesMessage(ValidationError, "Höhere Levels"):
            middle.full_clean()
        self.check(level=4, min_points=31)

    def test_level_number_is_fixed(self):
        add_levels(10)
        threshold = LevelThreshold.objects.get(level=2)
        threshold.level = 5
        with self.assertRaisesMessage(ValidationError, "nicht ändern"):
            threshold.full_clean()

    def test_only_highest_level_can_be_deleted(self):
        add_levels(10, 30)
        self.assertFalse(LevelThreshold.objects.get(level=1).can_be_deleted())
        self.assertFalse(LevelThreshold.objects.get(level=2).can_be_deleted())
        self.assertTrue(LevelThreshold.objects.get(level=3).can_be_deleted())


class LevelForPointsTests(TestCase):
    def test_only_level_one(self):
        info = level_for_points(500)
        self.assertEqual(info.level, 1)
        self.assertIsNone(info.points_missing)

    def test_levels_and_missing_points(self):
        add_levels(10, 30)
        cases = {0: (1, 10), 9: (1, 1), 10: (2, 20), 29: (2, 1), 30: (3, None)}
        for points, (level, missing) in cases.items():
            with self.subTest(points=points):
                info = level_for_points(points)
                self.assertEqual(info.level, level)
                self.assertEqual(info.points_missing, missing)


class CoachAdminTests(TestCase):
    def setUp(self):
        self.coach = User.objects.create_user(
            "coach", password="Roboter-777", is_staff=True
        )
        self.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(self.coach)

    def test_coach_permissions(self):
        for codename in (
            "tasks.add_topic",
            "tasks.change_topic",
            "tasks.delete_topic",
            "tasks.add_levelthreshold",
            "tasks.change_levelthreshold",
            "badges.add_badge",
            "badges.delete_badge",
        ):
            self.assertTrue(self.coach.has_perm(codename), codename)

    def test_coach_creates_topic(self):
        response = self.client.post(
            reverse("admin:tasks_topic_add"),
            {"name": "Konstruktion", "slug": "konstruktion", "order": 2},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Topic.objects.filter(slug="konstruktion").exists())

    def test_admin_add_level_validates(self):
        response = self.client.post(
            reverse("admin:tasks_levelthreshold_add"), {"level": 3, "min_points": 50}
        )
        self.assertContains(response, "Zuerst muss es Level 2 geben")
        response = self.client.post(
            reverse("admin:tasks_levelthreshold_add"), {"level": 2, "min_points": 20}
        )
        self.assertEqual(response.status_code, 302)

    def test_level_one_cannot_be_deleted_in_admin(self):
        level1 = LevelThreshold.objects.get(level=1)
        url = reverse("admin:tasks_levelthreshold_delete", args=[level1.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_pages_have_no_sharp_s(self):
        for name in ("tasks_topic", "tasks_levelthreshold", "badges_badge"):
            for view in ("changelist", "add"):
                response = self.client.get(reverse(f"admin:{name}_{view}"))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "ß")
