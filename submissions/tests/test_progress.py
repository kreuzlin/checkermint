"""Points and levels (brief 5.8, ADR 0013, #33)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from submissions.models import Submission
from submissions.progress import (
    levels_by_topic,
    points_by_task,
    points_by_topic,
    task_points,
    topic_progress,
)
from tasks.catalogue import Status, catalogue
from tasks.models import LevelThreshold, Task, TaskRequirement, TaskVersion, Topic
from tasks.tests.test_levels import add_levels

User = get_user_model()


def make_task(topic, slug, base_points=10, min_level=1):
    task = Task.objects.create(topic=topic, slug=slug, min_level=min_level)
    publish_version(task, base_points)
    task.is_published = True
    task.save()
    return task


def publish_version(task, base_points):
    version = TaskVersion.objects.create(
        task=task, title=task.slug.title(), instructions="…", base_points=base_points
    )
    TaskRequirement.objects.create(
        task_version=version, key="text", type="text", label="Text"
    )
    version.publish()
    return version


def reviewed(user, task, status="approved", stars=None, version=None):
    """A submission against `version` (default: latest) with a review."""
    submission = Submission.objects.create(
        user=user, task=task, task_version=version or task.latest_published_version()
    )
    submission.status = Submission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()
    if status != "submitted":
        submission.status = status
        submission.stars = stars if status == "approved" else None
        submission.reviewed_at = timezone.now()
        submission.save()
    return submission


class PointsTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.ben = User.objects.create_user("ben", password="geheim123")
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.build = Topic.objects.create(name="Bauen", slug="bauen", order=2)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.sensor = make_task(self.code, "sensor", base_points=15)
        self.arm = make_task(self.build, "arm", base_points=20)

    def test_nothing_approved_means_no_points(self):
        reviewed(self.anna, self.blink, "submitted")
        reviewed(self.anna, self.sensor, "needs_revision")
        Submission.objects.create(
            user=self.anna,
            task=self.arm,
            task_version=self.arm.latest_published_version(),
        )
        self.assertEqual(points_by_task(self.anna), {})
        self.assertEqual(points_by_topic(self.anna), {})
        self.assertIsNone(task_points(self.anna, self.blink))

    def test_base_points_times_stars(self):
        reviewed(self.anna, self.sensor, stars=2)
        self.assertEqual(points_by_task(self.anna), {self.sensor.pk: 30})
        self.assertEqual(task_points(self.anna, self.sensor), 30)

    def test_resubmissions_never_lower_points(self):
        reviewed(self.anna, self.blink, stars=2)
        reviewed(self.anna, self.blink, stars=1)
        reviewed(self.anna, self.blink, "needs_revision")
        self.assertEqual(task_points(self.anna, self.blink), 20)
        reviewed(self.anna, self.blink, stars=3)
        self.assertEqual(task_points(self.anna, self.blink), 30)

    def test_base_points_of_the_submissions_version(self):
        v1 = self.blink.latest_published_version()
        reviewed(self.anna, self.blink, stars=3, version=v1)  # 10 × 3
        v2 = publish_version(self.blink, base_points=20)
        reviewed(self.anna, self.blink, stars=1, version=v2)  # 20 × 1
        self.assertEqual(task_points(self.anna, self.blink), 30)
        reviewed(self.anna, self.blink, stars=2, version=v2)  # 20 × 2
        self.assertEqual(task_points(self.anna, self.blink), 40)

    def test_sum_per_topic_only_own_submissions(self):
        reviewed(self.anna, self.blink, stars=3)  # 30
        reviewed(self.anna, self.sensor, stars=1)  # 15
        reviewed(self.anna, self.arm, stars=2)  # 40
        reviewed(self.ben, self.blink, stars=3)
        self.assertEqual(
            points_by_topic(self.anna), {self.code.pk: 45, self.build.pk: 40}
        )
        self.assertEqual(points_by_topic(self.ben), {self.code.pk: 30})

    def test_archived_and_hidden_tasks_keep_their_points(self):
        reviewed(self.anna, self.blink, stars=1)
        reviewed(self.anna, self.sensor, stars=1)
        self.blink.is_archived = True
        self.blink.save()
        self.sensor.is_published = False
        self.sensor.save()
        self.assertEqual(points_by_topic(self.anna), {self.code.pk: 25})

    def test_queries(self):
        reviewed(self.anna, self.blink, stars=3)
        reviewed(self.anna, self.arm, stars=1)
        with self.assertNumQueries(1):
            points_by_topic(self.anna)
        with self.assertNumQueries(2):
            levels_by_topic(self.anna, [self.code.pk, self.build.pk])


class LevelTests(TestCase):
    def setUp(self):
        add_levels(20, 50)
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.code = Topic.objects.create(name="Code", slug="code", order=1)
        self.build = Topic.objects.create(name="Bauen", slug="bauen", order=2)
        self.blink = make_task(self.code, "blink", base_points=10)
        self.sensor = make_task(self.code, "sensor", base_points=10)
        self.line = make_task(self.code, "linie", min_level=2)
        self.arm = make_task(self.build, "arm", base_points=20)

    def test_level_and_progress_per_topic(self):
        reviewed(self.anna, self.blink, stars=3)  # 30 → level 2
        levels = levels_by_topic(self.anna, [self.code.pk, self.build.pk])
        code = levels[self.code.pk]
        self.assertEqual((code.level, code.points, code.points_missing), (2, 30, 20))
        build = levels[self.build.pk]
        self.assertEqual((build.level, build.points, build.points_missing), (1, 0, 20))

    def test_highest_level(self):
        reviewed(self.anna, self.blink, stars=3)
        reviewed(self.anna, self.sensor, stars=3)  # 60
        level = levels_by_topic(self.anna, [self.code.pk])[self.code.pk]
        self.assertEqual(level.level, 3)
        self.assertIsNone(level.points_missing)

    def test_topic_progress_lists_every_topic(self):
        reviewed(self.anna, self.arm, stars=1)
        progress = topic_progress(self.anna)
        self.assertEqual([p.topic for p in progress], [self.code, self.build])
        self.assertEqual([p.level.points for p in progress], [0, 20])

    def test_reaching_a_level_unlocks_tasks(self):
        def line_status():
            entries = [e for s in catalogue(self.anna) for e in s.entries]
            return next(e for e in entries if e.task == self.line).status

        self.assertIs(line_status(), Status.LOCKED)
        reviewed(self.anna, self.blink, stars=1)  # 10
        self.assertIs(line_status(), Status.LOCKED)
        reviewed(self.anna, self.blink, stars=2)  # 20 → level 2
        self.assertIs(line_status(), Status.OPEN)

    def test_changing_thresholds_changes_levels(self):
        reviewed(self.anna, self.blink, stars=3)  # 30
        LevelThreshold.objects.filter(level=3).delete()
        LevelThreshold.objects.filter(level=2).update(min_points=40)
        level = levels_by_topic(self.anna, [self.code.pk])[self.code.pk]
        self.assertEqual((level.level, level.points_missing), (1, 10))

    def test_catalogue_shows_level_points_and_missing(self):
        reviewed(self.anna, self.blink, stars=3)
        self.client.force_login(self.anna)
        response = self.client.get(reverse("tasks:catalogue"))
        self.assertContains(response, "<strong>Level 2</strong> · 30 Punkte")
        self.assertContains(response, "noch 20 bis Level 3")
        self.assertContains(response, '<progress value="30" max="50"')
        self.assertContains(response, "<strong>Level 1</strong> · 0 Punkte")

    def test_task_page_shows_earned_points(self):
        reviewed(self.anna, self.blink, stars=2)
        self.client.force_login(self.anna)
        url = reverse("tasks:task_detail", kwargs={"slug": self.blink.slug})
        self.assertContains(self.client.get(url), "Deine Punkte für diese Aufgabe: 20")
        other = reverse("tasks:task_detail", kwargs={"slug": self.sensor.slug})
        self.assertNotContains(self.client.get(other), "Deine Punkte")
