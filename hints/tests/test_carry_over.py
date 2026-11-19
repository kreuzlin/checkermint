"""Granted hints on a version switch (brief 5.5, ADR 0010, #38)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from hints.models import HintRequest
from hints.services import decide_request, hint_state, plan_carry_over, request_hint
from submissions.switching import SwitchNotPossible, plan_switch, switch_version
from tasks.attempts import get_attempt
from tasks.models import Hint

from .test_requests import task_with_hints

User = get_user_model()
GRANTED = HintRequest.Status.GRANTED


class CarryOverTests(TestCase):
    def setUp(self):
        self.anna = User.objects.create_user("anna", password="geheim123")
        self.coach = User.objects.create_user("coach", password="geheim123")
        self.task, self.v1 = task_with_hints()  # hints: motor, sensor
        self.detail = reverse("tasks:task_detail", kwargs={"slug": self.task.slug})
        self.switch = reverse("submissions:switch", kwargs={"slug": self.task.slug})
        self.client.force_login(self.anna)

    def grant(self, reply=""):
        request = request_hint(self.anna, self.task)
        return decide_request(request, self.coach, GRANTED, reply)

    def publish_v2(self, drop=("sensor",), add=("kabel",)):
        draft = self.task.create_draft()
        draft.change_note = "Neue Hinweise."
        draft.save()
        draft.hints.filter(key__in=drop).delete()
        for order, key in enumerate(add, start=10):
            Hint.objects.create(
                task_version=draft, key=key, order=order, text=f"Tipp **{key}**"
            )
        draft.publish()
        return draft

    def attempt(self):
        return get_attempt(self.anna, self.task)

    def test_plan_lists_kept_and_lost_hints(self):
        self.grant()  # motor
        self.grant()  # sensor
        v2 = self.publish_v2()
        plan = plan_carry_over(self.attempt(), v2)
        self.assertEqual([h.key for h in plan.kept], ["motor"])
        self.assertEqual(plan.kept[0].task_version, v2)
        self.assertEqual([(n, h.key) for n, h in plan.lost], [(2, "sensor")])
        self.assertFalse(plan.blocks_switch)

    def test_confirmation_shows_the_hints(self):
        self.grant()
        self.grant()
        self.publish_v2()
        response = self.client.get(self.switch)
        self.assertContains(response, "Deine Hinweise")
        self.assertContains(response, "1 erhaltener Hinweis bleibt freigeschaltet.")
        self.assertContains(response, "Hinweis 2: «Tipp **sensor**»")
        self.assertContains(response, "Ja, auf Version 2 wechseln")

    def test_confirmation_without_granted_hints_has_no_hint_section(self):
        request_hint(self.anna, self.task)  # open, for "motor" (kept in v2)
        self.publish_v2()
        self.assertNotContains(self.client.get(self.switch), "Deine Hinweise")

    def test_after_the_switch_kept_hints_stay_granted(self):
        self.grant("Pin 9")
        v2 = self.publish_v2()
        switch_version(self.anna, self.task, v2.pk)
        state = hint_state(self.attempt(), v2)
        self.assertEqual([g.hint.key for g in state.granted], ["motor"])
        self.assertEqual(state.next_hint.key, "kabel")

        page = self.client.get(self.detail)
        self.assertContains(page, "Tipp <strong>motor</strong>", html=False)
        self.assertContains(page, "Pin 9")
        self.assertContains(page, "Du hast 1 von 2 Hinweisen erhalten.")

    def test_open_request_for_a_kept_hint_survives_the_switch(self):
        request = request_hint(self.anna, self.task)  # motor
        v2 = self.publish_v2()
        switch_version(self.anna, self.task, v2.pk)
        decide_request(request, self.coach, GRANTED)
        state = hint_state(self.attempt(), v2)
        self.assertEqual([g.hint.task_version for g in state.granted], [v2])

    def test_open_request_for_a_dropped_hint_blocks_the_switch(self):
        self.grant()  # motor
        request = request_hint(self.anna, self.task)  # sensor, open
        v2 = self.publish_v2()

        self.assertTrue(plan_switch(self.anna, self.task).hints.blocks_switch)
        response = self.client.get(self.switch)
        self.assertContains(response, "Wechseln geht gerade nicht:")
        self.assertNotContains(response, "Ja, auf Version 2 wechseln")
        with self.assertRaises(SwitchNotPossible):
            switch_version(self.anna, self.task, v2.pk)

        response = self.client.post(self.switch, {"version": v2.pk}, follow=True)
        self.assertContains(response, "Warte auf die Antwort eines Coachs")
        self.assertEqual(self.attempt().task_version, self.v1)

        decide_request(request, self.coach, HintRequest.Status.DECLINED)
        switch_version(self.anna, self.task, v2.pk)
        self.assertEqual(self.attempt().task_version, v2)
