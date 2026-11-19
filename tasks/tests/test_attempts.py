"""Task attempts pin the version a participant sees (brief 5.4, #19)."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from tasks.attempts import (
    TaskNotStartable,
    get_attempt,
    start_attempt,
    visible_version,
)
from tasks.models import TaskAttempt

from .test_versions import make_task, make_version

User = get_user_model()


def published_task(slug="linienfolger"):
    task = make_task(slug)
    version = make_version(task)
    version.publish()
    task.is_published = True
    task.save()
    return task, version


def new_version(task, title="Linienfolger 2"):
    draft = task.create_draft()
    draft.title = title
    draft.save()
    draft.publish()
    return draft


class StartAttemptTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()

    def test_without_attempt_the_latest_published_version_is_visible(self):
        v2 = new_version(self.task)
        self.assertEqual(visible_version(self.user, self.task), v2)
        self.assertIsNone(get_attempt(self.user, self.task))

    def test_drafts_are_never_visible(self):
        self.task.create_draft()
        self.assertEqual(visible_version(self.user, self.task), self.v1)

    def test_start_pins_the_current_version(self):
        attempt = start_attempt(self.user, self.task)
        self.assertEqual(attempt.task_version, self.v1)
        self.assertIsNone(attempt.switched_at)

    def test_pinned_version_stays_after_a_new_version(self):
        start_attempt(self.user, self.task)
        new_version(self.task)
        self.assertEqual(visible_version(self.user, self.task), self.v1)

    def test_other_participants_see_the_new_version(self):
        start_attempt(self.user, self.task)
        v2 = new_version(self.task)
        other = User.objects.create_user("ben", password="geheim123")
        self.assertEqual(visible_version(other, self.task), v2)
        self.assertEqual(start_attempt(other, self.task).task_version, v2)

    def test_starting_again_keeps_the_pinned_version(self):
        first = start_attempt(self.user, self.task)
        new_version(self.task)
        again = start_attempt(self.user, self.task)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.task_version, self.v1)
        self.assertEqual(TaskAttempt.objects.count(), 1)

    def test_concurrent_start_returns_the_existing_attempt(self):
        existing = TaskAttempt.objects.create(
            user=self.user, task=self.task, task_version=self.v1
        )
        # The other request has not seen the attempt yet.
        with mock.patch("tasks.attempts.get_attempt", return_value=None):
            attempt = start_attempt(self.user, self.task)
        self.assertEqual(attempt.pk, existing.pk)

    def test_hidden_archived_or_unpublished_tasks_cannot_be_started(self):
        hidden = make_task("versteckt")
        make_version(hidden).publish()
        archived, _ = published_task("archiviert")
        archived.is_archived = True
        archived.save()
        empty = make_task("leer")
        make_version(empty)  # draft only
        for task in (hidden, archived, empty):
            with self.subTest(task=task.slug), self.assertRaises(TaskNotStartable):
                start_attempt(self.user, task)
        self.assertFalse(TaskAttempt.objects.exists())

    def test_anonymous_users_cannot_start(self):
        with self.assertRaises(TaskNotStartable):
            start_attempt(AnonymousUser(), self.task)
        self.assertEqual(visible_version(AnonymousUser(), self.task), self.v1)

    def test_archiving_keeps_existing_attempts(self):
        start_attempt(self.user, self.task)
        self.task.is_archived = True
        self.task.save()
        self.assertEqual(start_attempt(self.user, self.task).task_version, self.v1)


class AttemptIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = published_task()

    def test_one_attempt_per_user_and_task(self):
        TaskAttempt.objects.create(user=self.user, task=self.task, task_version=self.v1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskAttempt.objects.create(
                user=self.user, task=self.task, task_version=self.v1
            )

    def test_cannot_pin_a_draft(self):
        draft = self.task.create_draft()
        with self.assertRaises(ValueError):
            TaskAttempt.objects.create(
                user=self.user, task=self.task, task_version=draft
            )
        attempt = TaskAttempt(user=self.user, task=self.task, task_version=draft)
        with self.assertRaises(ValidationError):
            attempt.full_clean()

    def test_cannot_pin_a_version_of_another_task(self):
        _, other_version = published_task("andere")
        with self.assertRaises(ValueError):
            TaskAttempt.objects.create(
                user=self.user, task=self.task, task_version=other_version
            )
        attempt = TaskAttempt(
            user=self.user, task=self.task, task_version=other_version
        )
        with self.assertRaises(ValidationError):
            attempt.full_clean()


class PinnedCountAdminTests(TestCase):
    def test_task_page_shows_how_many_are_pinned_per_version(self):
        task, _ = published_task()
        for name in ("anna", "ben"):
            start_attempt(User.objects.create_user(name, password="geheim123"), task)
        new_version(task)
        start_attempt(User.objects.create_user("cleo", password="geheim123"), task)

        coach = User.objects.create_user("coach", password="geheim1234", is_staff=True)
        coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        self.client.force_login(coach)
        response = self.client.get(reverse("admin:tasks_task_change", args=[task.pk]))
        self.assertContains(response, "Teilnehmende auf dieser Version")
        html = response.content.decode()
        # Versions are listed newest first: version 2 has 1, version 1 has 2.
        self.assertRegex(
            html,
            r'(?s)field-number">\s*<p>2</p>.*?field-pinned">\s*<p>1</p>'
            r'.*?field-number">\s*<p>1</p>.*?field-pinned">\s*<p>2</p>',
        )
