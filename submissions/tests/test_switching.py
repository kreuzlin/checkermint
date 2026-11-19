"""Switching to a newer task version (brief 5.4, ADR 0010, #26)."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from submissions.models import Submission, SubmissionItem
from submissions.switching import (
    SwitchNotPossible,
    newer_version,
    plan_switch,
    switch_version,
)
from tasks.attempts import get_attempt
from tasks.models import TaskRequirement

from .test_uploads import IN_MEMORY, jpeg, upload_task

User = get_user_model()


def publish_v2(task, change_note="Neu mit Video-Erklärung.", edit=None):
    draft = task.create_draft()
    draft.change_note = change_note
    draft.save()
    if edit:
        edit(draft)
    draft.publish()
    return draft


@override_settings(STORAGES=IN_MEMORY)
class SwitchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="geheim123")
        self.task, self.v1 = upload_task(photos=(1, 3))
        self.edit = reverse("submissions:edit", kwargs={"slug": self.task.slug})
        self.detail = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.switch = reverse("submissions:switch", kwargs={"slug": self.task.slug})
        self.client.force_login(self.user)
        self.client.post(
            self.edit,
            {
                "aktion": "speichern",
                "fotos": [jpeg("a.jpg"), jpeg("b.jpg"), jpeg("c.jpg")],
                "cad": SimpleUploadedFile("bruecke.stl", b"solid b"),
            },
        )
        self.draft = Submission.objects.get()

    def attempt(self):
        return get_attempt(self.user, self.task)

    def test_no_notice_without_a_newer_version(self):
        self.assertIsNone(newer_version(self.attempt()))
        self.assertNotContains(self.client.get(self.detail), "neuere Version")
        self.assertRedirects(self.client.get(self.switch), self.detail)

    def test_notice_with_change_note_on_task_page_and_form(self):
        publish_v2(self.task)
        for url in (self.detail, self.edit):
            response = self.client.get(url)
            self.assertContains(response, "Es gibt eine neuere Version dieser Aufgabe")
            self.assertContains(response, "Neu mit Video-Erklärung.")
            self.assertContains(response, self.switch)
        # The participant still sees the pinned version.
        self.assertEqual(self.attempt().task_version, self.v1)

    def test_participants_without_attempt_see_no_notice(self):
        publish_v2(self.task)
        ben = User.objects.create_user("ben", password="geheim123")
        self.client.force_login(ben)
        self.assertNotContains(self.client.get(self.detail), "neuere Version")

    def test_confirmation_lists_what_is_lost(self):
        def edit(draft):
            fotos = draft.requirements.get(key="fotos")
            draft.requirements.filter(pk=fotos.pk).update(max_count=2, min_count=1)
            draft.requirements.filter(key="cad").delete()
            TaskRequirement.objects.create(
                task_version=draft, key="video", type="file", label="Video"
            )

        v2 = publish_v2(self.task, edit=edit)
        response = self.client.get(self.switch)
        self.assertContains(response, "Auf Version 2 wechseln?")
        self.assertContains(response, "Neu mit Video-Erklärung.")
        self.assertContains(response, "2 Teile deines Entwurfs werden übernommen.")
        self.assertContains(response, "Fotos (1): neu sind höchstens 2 erlaubt")
        self.assertContains(
            response, "CAD-Datei (1): gibt es in der neuen Version nicht mehr"
        )
        self.assertContains(response, f'name="version" value="{v2.pk}"')
        # Looking does not switch.
        self.assertEqual(self.attempt().task_version, self.v1)

    def test_type_change_is_not_carried_over(self):
        def edit(draft):
            draft.requirements.filter(key="cad").update(type="photo")

        publish_v2(self.task, edit=edit)
        plan = plan_switch(self.user, self.task)
        self.assertEqual(
            [(d.requirement_label, d.reason) for d in plan.dropped],
            [("CAD-Datei", "ist jetzt «Foto»")],
        )

    def test_switch_moves_matching_items_into_a_new_draft(self):
        v2 = publish_v2(self.task)
        old_files = set(SubmissionItem.objects.values_list("file", flat=True))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.switch, {"version": v2.pk})
        self.assertRedirects(response, self.detail)

        attempt = self.attempt()
        self.assertEqual(attempt.task_version, v2)
        self.assertIsNotNone(attempt.switched_at)
        draft = Submission.objects.get()
        self.assertNotEqual(draft.pk, self.draft.pk)
        self.assertEqual(draft.task_version, v2)
        items = list(draft.items.select_related("requirement").order_by("pk"))
        self.assertEqual(
            [(i.requirement.key, i.original_filename, i.order) for i in items],
            [
                ("fotos", "a.jpg", 0),
                ("fotos", "b.jpg", 1),
                ("fotos", "c.jpg", 2),
                ("cad", "bruecke.stl", 0),
            ],
        )
        self.assertTrue(all(i.requirement.task_version_id == v2.pk for i in items))
        # New files; the old ones are deleted with the old draft.
        storage = items[0].file.storage
        for item in items:
            self.assertNotIn(item.file.name, old_files)
            self.assertTrue(storage.exists(item.file.name))
        for name in old_files:
            self.assertFalse(storage.exists(name))

        page = self.client.get(self.edit)
        self.assertContains(page, "Version 2")
        self.assertNotContains(page, "neuere Version")

    def test_dropped_items_and_order_after_switch(self):
        def edit(draft):
            draft.requirements.filter(key="fotos").update(max_count=2)

        v2 = publish_v2(self.task, edit=edit)
        switch_version(self.user, self.task, v2.pk)
        photos = SubmissionItem.objects.filter(requirement__key="fotos").order_by(
            "order"
        )
        self.assertEqual(
            [(p.original_filename, p.order) for p in photos],
            [("a.jpg", 0), ("b.jpg", 1)],
        )

    def test_switch_refuses_an_unconfirmed_version(self):
        v2 = publish_v2(self.task)
        publish_v2(self.task, change_note="Noch neuer.")
        with self.assertRaises(SwitchNotPossible):
            switch_version(self.user, self.task, v2.pk)
        response = self.client.post(self.switch, {"version": v2.pk}, follow=True)
        self.assertContains(response, "Inzwischen gibt es eine andere Version.")
        self.assertEqual(self.attempt().task_version, self.v1)
        # The confirmation shows both change notes.
        self.assertContains(response, "Neu mit Video-Erklärung.")
        self.assertContains(response, "Noch neuer.")

    def test_submitted_solutions_keep_their_version(self):
        self.client.post(self.edit, {"aktion": "einreichen"})
        submitted = Submission.objects.get()
        self.assertEqual(submitted.status, Submission.Status.SUBMITTED)
        v2 = publish_v2(self.task)
        switch_version(self.user, self.task, v2.pk)
        submitted.refresh_from_db()
        self.assertEqual(submitted.task_version, self.v1)
        self.assertEqual(submitted.items.count(), 4)
        self.assertEqual(self.attempt().task_version, v2)

    def test_switch_without_draft(self):
        with self.captureOnCommitCallbacks(execute=True):
            for item in self.draft.items.all():
                item.delete()
        self.draft.delete()
        v2 = publish_v2(self.task)
        self.assertContains(self.client.get(self.switch), "Auf Version 2 wechseln?")
        switch_version(self.user, self.task, v2.pk)
        self.assertEqual(self.attempt().task_version, v2)
        self.assertFalse(Submission.objects.exists())

    def test_only_the_participant_switches(self):
        v2 = publish_v2(self.task)
        ben = User.objects.create_user("ben", password="geheim123")
        self.client.force_login(ben)
        # Ben has no attempt: nothing to switch.
        self.assertRedirects(
            self.client.post(self.switch, {"version": v2.pk}), self.detail
        )
        self.assertEqual(self.attempt().task_version, self.v1)
        self.client.logout()
        self.assertEqual(
            self.client.post(self.switch, {"version": v2.pk}).status_code, 302
        )
        self.assertEqual(self.attempt().task_version, self.v1)
