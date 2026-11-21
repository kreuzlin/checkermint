"""Coaches reach the admin from the site without typing /admin/ (#138)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import COACH_GROUP_NAME
from submissions.tests.test_form import text_and_code_task

User = get_user_model()


class AdminLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.task, _ = text_and_code_task()
        cls.anna = User.objects.create_user("anna", password="geheim123")
        cls.coach = User.objects.create_user(
            "coach", password="geheim123", is_staff=True
        )
        cls.coach.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
        cls.admin_index = reverse("admin:index")
        cls.add_task = reverse("admin:tasks_task_add")
        cls.edit_task = reverse("admin:tasks_task_change", args=[cls.task.pk])
        cls.catalogue = reverse("tasks:catalogue")
        cls.detail = reverse("tasks:task_detail", kwargs={"slug": cls.task.slug})

    def test_coach_sees_the_links(self):
        self.client.force_login(self.coach)
        catalogue = self.client.get(self.catalogue)
        self.assertContains(catalogue, f'href="{self.admin_index}">Verwaltung</a>')
        self.assertContains(catalogue, f'href="{self.add_task}">Neue Aufgabe erstellen')
        detail = self.client.get(self.detail)
        self.assertContains(
            detail, f'href="{self.edit_task}">In der Verwaltung bearbeiten'
        )
        # The links lead somewhere the coach may go.
        self.assertEqual(self.client.get(self.admin_index).status_code, 200)
        self.assertEqual(self.client.get(self.add_task).status_code, 200)
        self.assertEqual(self.client.get(self.edit_task).status_code, 200)

    def test_participants_do_not_see_them(self):
        self.client.force_login(self.anna)
        for url in (self.catalogue, self.detail):
            response = self.client.get(url)
            self.assertNotContains(response, self.admin_index)
            self.assertNotContains(response, "Neue Aufgabe erstellen")
            self.assertNotContains(response, "In der Verwaltung bearbeiten")
