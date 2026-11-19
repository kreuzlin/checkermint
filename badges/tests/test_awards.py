"""Awarding badges and showing them (brief 5.8, 5.9, ADR 0013, #34)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from badges.awards import award_for, recent_badges
from badges.models import Badge, UserBadge
from submissions.models import Submission
from submissions.services import review_submission
from submissions.tests.test_form import text_and_code_task

User = get_user_model()


def participant(username, nickname, active=True):
    user = User.objects.create_user(username, password="geheim123", is_active=active)
    Profile.objects.create(user=user, nickname=nickname, real_name=nickname)
    return user


def coach():
    user = User.objects.create_user("coach", password="geheim123", is_staff=True)
    user.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
    Profile.objects.create(user=user, nickname="CoachCarla", real_name="Carla")
    return user


def submitted(user, task):
    submission = Submission.objects.create(
        user=user, task=task, task_version=task.latest_published_version()
    )
    submission.status = Submission.Status.SUBMITTED
    submission.submitted_at = timezone.now()
    submission.save()
    return submission


class AwardTests(TestCase):
    def setUp(self):
        self.anna = participant("anna", "RoboAnna")
        self.coach = coach()
        self.badge = Badge.objects.create(name="Sensorprofi")
        self.task, _ = text_and_code_task()
        self.task.badge = self.badge
        self.task.save()

    def approve(self, user=None, stars=2):
        return review_submission(
            submitted(user or self.anna, self.task), self.coach, "approved", stars, ""
        )

    def test_first_approval_awards_the_badge(self):
        submission = self.approve()
        award = UserBadge.objects.get()
        self.assertEqual(
            (award.user, award.badge, award.submission),
            (self.anna, self.badge, submission),
        )
        self.assertEqual(award.awarded_at, submission.reviewed_at)

    def test_only_once(self):
        self.approve(stars=1)
        self.approve(stars=3)
        self.assertEqual(UserBadge.objects.count(), 1)
        self.assertEqual(UserBadge.objects.get().submission.stars, 1)

    def test_not_for_needs_revision(self):
        review_submission(
            submitted(self.anna, self.task), self.coach, "needs_revision", None, "x"
        )
        self.assertFalse(UserBadge.objects.exists())

    def test_task_without_badge(self):
        self.task.badge = None
        self.task.save()
        self.approve()
        self.assertFalse(UserBadge.objects.exists())

    def test_badge_added_later_comes_with_the_next_approval(self):
        self.task.badge = None
        self.task.save()
        self.approve()
        self.task.badge = self.badge
        self.task.save()
        self.assertFalse(UserBadge.objects.exists())
        self.approve()
        self.assertEqual(UserBadge.objects.count(), 1)

    def test_award_for_ignores_unapproved(self):
        self.assertIsNone(award_for(submitted(self.anna, self.task)))

    def test_review_page_says_badge_was_awarded(self):
        submission = submitted(self.anna, self.task)
        self.client.force_login(self.coach)
        response = self.client.post(
            reverse("submissions:review", kwargs={"pk": submission.pk}),
            {"decision": "annehmen", "stars": "3"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "Badge «Sensorprofi» vergeben.")


class DisplayTests(TestCase):
    def setUp(self):
        self.anna = participant("anna", "RoboAnna")
        self.ben = participant("ben", "BenBot")
        self.coach = coach()
        self.badge = Badge.objects.create(
            name="Sensorprofi", description="Sensor ausgelesen."
        )
        self.task, _ = text_and_code_task()
        self.task.badge = self.badge
        self.task.save()
        review_submission(
            submitted(self.anna, self.task), self.coach, "approved", 2, ""
        )

    def test_recent_feed_on_home_page_for_logged_in_users_only(self):
        home = reverse("core:home")
        self.assertNotContains(self.client.get(home), "Neue Badges im Club")
        self.assertNotContains(self.client.get(home), "RoboAnna")
        self.client.force_login(self.ben)
        response = self.client.get(home)
        self.assertContains(response, "Neue Badges im Club")
        self.assertContains(response, "<strong>Sensorprofi</strong> für")
        self.assertContains(response, "RoboAnna")
        self.assertContains(response, "Sensor auslesen")

    def test_feed_newest_first_without_inactive_users(self):
        other = Badge.objects.create(name="Zweiter")
        UserBadge.objects.create(user=self.ben, badge=other)
        gone = participant("gone", "Weg", active=False)
        UserBadge.objects.create(user=gone, badge=other)
        self.assertEqual(
            [(a.user, a.badge) for a in recent_badges()],
            [(self.ben, other), (self.anna, self.badge)],
        )
        self.assertEqual(len(recent_badges(limit=1)), 1)

    def test_empty_feed(self):
        UserBadge.objects.all().delete()
        self.client.force_login(self.ben)
        self.assertContains(self.client.get(reverse("core:home")), "Noch keine Badges")

    def test_history_shows_the_badge_above_the_review(self):
        self.client.force_login(self.anna)
        response = self.client.get(reverse("submissions:history"))
        content = response.content.decode()
        self.assertIn("Badge erhalten: Sensorprofi", content)
        self.assertLess(
            content.index("Badge erhalten"), content.index("<strong>Angenommen")
        )

    def test_internal_profile_lists_badges(self):
        self.client.force_login(self.ben)
        url = reverse("accounts:participant_detail", kwargs={"nickname": "RoboAnna"})
        response = self.client.get(url)
        self.assertContains(
            response, "<strong>Sensorprofi</strong> – Sensor ausgelesen."
        )
        own = reverse("accounts:participant_detail", kwargs={"nickname": "BenBot"})
        self.assertContains(self.client.get(own), "Noch keine Badges.")


class AdminTests(TestCase):
    def setUp(self):
        self.anna = participant("anna", "RoboAnna")
        self.coach = coach()
        badge = Badge.objects.create(name="Sensorprofi")
        self.award = UserBadge.objects.create(user=self.anna, badge=badge)
        self.client.force_login(self.coach)

    def test_coaches_see_awards_and_can_revoke_but_not_add(self):
        changelist = reverse("admin:badges_userbadge_changelist")
        response = self.client.get(changelist)
        self.assertContains(response, "RoboAnna")
        self.assertEqual(
            self.client.get(reverse("admin:badges_userbadge_add")).status_code, 403
        )
        delete = reverse("admin:badges_userbadge_delete", args=[self.award.pk])
        self.client.post(delete, {"post": "yes"})
        self.assertFalse(UserBadge.objects.exists())

    def test_coach_group_permissions(self):
        codenames = set(
            Group.objects.get(name=COACH_GROUP_NAME)
            .permissions.filter(
                content_type__app_label="badges", content_type__model="userbadge"
            )
            .values_list("codename", flat=True)
        )
        self.assertEqual(codenames, {"view_userbadge", "delete_userbadge"})
