"""Demo data for local development (`manage.py seed_demo`).

Creates a coach, participants, topics, levels, tasks (one with two
versions, one unpublished draft), hints, badges (awarded on approval) and
submissions in every
state, so the coach queue, review and progress views can be tried by hand.

Demo rows are recognised by the `demo-` prefix of usernames, task slugs
and topic slugs, and by `DEMO_BADGES`; `remove_demo_data` deletes only those.
Names are invented; photos are drawn with Pillow (no image rights, no
metadata) and go through the normal photo pipeline.
"""

import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import Profile
from accounts.roles import COACH_GROUP_NAME
from badges.awards import award_for
from badges.models import Badge
from core.images import process_photo
from tasks.attempts import start_attempt
from tasks.models import Hint, LevelThreshold, Task, TaskRequirement, TaskVersion, Topic

from .models import Submission, SubmissionItem
from .services import save_draft, submit

User = get_user_model()

PREFIX = "demo-"
LED_BADGE = "Erste Schaltung (Demo)"
BLINK_BADGE = "Erstes Programm (Demo)"
DEMO_BADGES = [LED_BADGE, BLINK_BADGE]
COACH = ("demo-coach", "CoachCarla", "Carla Coach")
PARTICIPANTS = [
    ("demo-anna", "RoboAnna", "Anna Muster"),
    ("demo-ben", "BenBot", "Ben Beispiel"),
    ("demo-chiara", "Chipsy", "Chiara Test"),
    ("demo-max", "MaxMotor", "Max Probst"),
    ("demo-luna", "LunaLED", "Luna Demo"),
]
TOPIC_NAMES = ["Code", "Konstruktion", "Elektronik"]
# Only added when the table holds nothing but level 1.
LEVELS = [(2, 20), (3, 50), (4, 100)]

BLINK_CODE = """\
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(LED_BUILTIN, LOW);
  delay(500);
}"""

SENSOR_CODE = """\
from machine import ADC, Pin
import time

sensor = ADC(Pin(26))
while True:
    print(sensor.read_u16())
    time.sleep(0.5)"""

STL = b"""solid gehaeuse
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 10 0 0
      vertex 0 10 0
    endloop
  endfacet
endsolid gehaeuse
"""


class DemoDataExists(Exception):
    pass


class DemoNameTaken(Exception):
    """A nickname or topic name of the demo data is used by real data."""


def demo_users():
    return User.objects.filter(username__startswith=PREFIX)


def demo_tasks():
    return Task.objects.filter(slug__startswith=PREFIX)


def has_demo_data() -> bool:
    return (
        demo_users().exists()
        or demo_tasks().exists()
        or Topic.objects.filter(slug__startswith=PREFIX).exists()
    )


@transaction.atomic
def remove_demo_data() -> None:
    """Delete demo rows and their stored files.

    Published versions are immutable by design (ADR 0010); for demo tasks
    the guards are bypassed on purpose by using the plain QuerySet delete.
    Fails (ProtectedError) if non-demo users submitted to a demo task.
    """
    items = SubmissionItem.objects.filter(submission__user__in=demo_users())
    files = [
        (field.name, field.storage)
        for item in items
        for field in (item.file, item.thumbnail)
        if field
    ]
    demo_users().delete()  # profiles, attempts, submissions and items cascade
    models.QuerySet.delete(TaskVersion.objects.filter(task__in=demo_tasks()))
    demo_tasks().delete()
    Badge.objects.filter(name__in=DEMO_BADGES).delete()
    Topic.objects.filter(slug__startswith=PREFIX).delete()
    for name, storage in files:
        transaction.on_commit(lambda n=name, s=storage: s.delete(n))


def make_user(username, nickname, real_name, password, coach=False):
    user = User.objects.create_user(username, password=password, is_staff=coach)
    if coach:
        user.groups.add(Group.objects.get(name=COACH_GROUP_NAME))
    Profile.objects.create(user=user, nickname=nickname, real_name=real_name)
    return user


def make_version(task, title, instructions, requirements, hints=(), points=10):
    version = TaskVersion.objects.create(
        task=task, title=title, instructions=instructions, base_points=points
    )
    add_children(version, requirements, hints)
    return version


def add_children(version, requirements, hints=()):
    for order, (key, type_, label, extra) in enumerate(requirements):
        TaskRequirement.objects.create(
            task_version=version, key=key, type=type_, label=label, order=order, **extra
        )
    for order, (key, text) in enumerate(hints):
        Hint.objects.create(task_version=version, key=key, order=order, text=text)


def make_task(topic, slug, order, *version_args, min_level=1, badge=None, **kwargs):
    task = Task.objects.create(
        topic=topic, slug=PREFIX + slug, order=order, min_level=min_level, badge=badge
    )
    version = make_version(task, *version_args, **kwargs)
    version.publish()
    task.is_published = True
    task.save()
    return task


def photo(label: str, colour: str) -> dict:
    """A drawn "photo" processed like an upload (re-encoded, thumbnail)."""
    image = Image.new("RGB", (1200, 900), colour)
    draw = ImageDraw.Draw(image)
    draw.rectangle((350, 250, 850, 650), outline="white", width=12)
    draw.ellipse((450, 350, 550, 450), fill="white")
    draw.ellipse((650, 350, 750, 450), fill="white")
    draw.text((60, 60), label, fill="white", font_size=64)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    upload = ContentFile(buffer.getvalue(), name=f"{label}.png")
    full, thumbnail = process_photo(upload)
    full.content.name = f"foto{full.extension}"
    thumbnail.content.name = f"vorschau{thumbnail.extension}"
    return {
        "file": full.content,
        "thumbnail": thumbnail.content,
        "original_filename": f"{label}.png",
        "data": {"width": full.width, "height": full.height},
    }


class Seeder:
    def __init__(self, password: str):
        self.password = password
        self.now = timezone.now()

    def ago(self, **kwargs):
        return self.now - timedelta(**kwargs)

    @transaction.atomic
    def run(self):
        if has_demo_data():
            raise DemoDataExists
        self.check_names()
        self.levels()
        self.coach = make_user(*COACH, self.password, coach=True)
        self.users = {
            nickname: make_user(username, nickname, real_name, self.password)
            for username, nickname, real_name in PARTICIPANTS
        }
        self.tasks()
        self.submissions()
        self.sensor_v2()

    def check_names(self):
        nicknames = [COACH[1]] + [nickname for _, nickname, _ in PARTICIPANTS]
        taken = list(
            Profile.objects.filter(nickname__in=nicknames).values_list(
                "nickname", flat=True
            )
        )
        taken += Topic.objects.filter(name__in=TOPIC_NAMES).values_list(
            "name", flat=True
        )
        taken += Badge.objects.filter(name__in=DEMO_BADGES).values_list(
            "name", flat=True
        )
        if taken:
            raise DemoNameTaken(", ".join(taken))

    def levels(self):
        if LevelThreshold.objects.exclude(level=1).exists():
            return
        for level, points in LEVELS:
            LevelThreshold.objects.create(level=level, min_points=points)

    def tasks(self):
        code = Topic.objects.create(
            name="Code",
            slug=PREFIX + "code",
            order=1,
            description="Programme für Arduino und Raspberry Pi Pico.",
        )
        build = Topic.objects.create(
            name="Konstruktion",
            slug=PREFIX + "konstruktion",
            order=2,
            description="Mechanik, Getriebe und Gehäuse.",
        )
        electro = Topic.objects.create(
            name="Elektronik",
            slug=PREFIX + "elektronik",
            order=3,
            description="Schaltungen, Sensoren und Motoren.",
        )
        badge = Badge.objects.create(
            name=LED_BADGE, description="Für die erste eigene LED-Schaltung."
        )
        blink_badge = Badge.objects.create(
            name=BLINK_BADGE, description="Für das erste Programm, das läuft."
        )
        text = TaskRequirement.Type.TEXT
        code_type = TaskRequirement.Type.CODE
        photo_type = TaskRequirement.Type.PHOTO
        file_type = TaskRequirement.Type.FILE

        self.blink = make_task(
            code,
            "blinklicht",
            1,
            "Blinklicht",
            "Lass die eingebaute LED **jede halbe Sekunde** blinken.",
            [
                (
                    "programm",
                    code_type,
                    "Programm",
                    {"options": {"language": "arduino", "extensions": [".ino"]}},
                ),
                ("erklaerung", text, "Was macht dein Programm?", {}),
            ],
            [
                ("delay", "Schau dir die Funktion `delay()` an."),
                ("pin", "Die eingebaute LED heisst `LED_BUILTIN`."),
            ],
            badge=blink_badge,
        )
        self.sensor = make_task(
            code,
            "sensor-auslesen",
            2,
            "Sensor auslesen",
            "Lies einen analogen Sensor aus und gib den Wert aus.",
            [
                (
                    "programm",
                    code_type,
                    "Programm",
                    {"options": {"language": "python"}},
                ),
                ("erklaerung", text, "Welche Werte hast du gemessen?", {}),
            ],
            [("adc", "Der Pico hat analoge Eingänge an GP26 bis GP28.")],
            points=15,
        )
        self.line = make_task(
            code,
            "linienfolger",
            3,
            "Linienfolger",
            "Dein Roboter folgt einer schwarzen Linie.",
            [
                (
                    "programm",
                    code_type,
                    "Programm",
                    {"options": {"language": "python"}},
                ),
                ("foto", photo_type, "Foto vom Roboter auf der Strecke", {}),
            ],
            min_level=2,
            points=25,
        )
        self.arm = make_task(
            build,
            "greifarm",
            1,
            "Greifarm",
            "Baue einen Greifarm, der einen Würfel hochheben kann.",
            [
                (
                    "fotos",
                    photo_type,
                    "Fotos vom Greifarm",
                    {"min_count": 1, "max_count": 3},
                ),
                ("beschreibung", text, "Wie funktioniert der Greifer?", {}),
            ],
            [("hebel", "Ein längerer Hebel braucht weniger Kraft.")],
        )
        self.case = make_task(
            build,
            "gehaeuse",
            2,
            "Gehäuse für den Controller",
            "Konstruiere ein Gehäuse für den Controller und exportiere es als STL.",
            [
                (
                    "modell",
                    file_type,
                    "3D-Modell",
                    {"options": {"extensions": [".stl"]}},
                ),
                (
                    "foto",
                    photo_type,
                    "Foto vom Druck",
                    {"required": False, "min_count": 0},
                ),
            ],
            points=20,
        )
        self.led = make_task(
            electro,
            "led-schaltung",
            1,
            "LED-Schaltung",
            "Baue eine LED mit Vorwiderstand auf dem Steckbrett auf.",
            [
                ("foto", photo_type, "Foto der Schaltung", {}),
                (
                    "widerstand",
                    text,
                    "Welchen Widerstand hast du gewählt und warum?",
                    {},
                ),
            ],
            [
                ("ohm", "U = R · I – rechne mit 20 mA."),
                ("polung", "Das lange Bein der LED ist die Anode (+)."),
            ],
            badge=badge,
        )
        # A task that only has a draft: visible in the admin, not in the catalogue.
        draft_task = Task.objects.create(
            topic=electro, slug=PREFIX + "motor-ansteuern", order=2
        )
        make_version(
            draft_task,
            "Motor ansteuern",
            "Steuere einen Motor mit einem Motortreiber an. (Entwurf)",
            [("foto", photo_type, "Foto der Schaltung", {})],
        )

    def solution(self, user, task, values, submitted, review=None):
        """Draft → submitted at `submitted`, optionally reviewed.

        `values`: requirement key → list of item dicts. `review`:
        (status, stars, feedback, reviewed).
        """
        version = start_attempt(user, task).task_version
        requirements = {r.key: r.pk for r in version.requirements.all()}
        draft = save_draft(
            user, task, {requirements[key]: items for key, items in values.items()}
        )
        if submitted is None:
            return draft
        submission = submit(draft)
        changes = {"submitted_at": submitted}
        if review:
            status, stars, feedback, reviewed = review
            changes.update(
                status=status,
                stars=stars,
                feedback=feedback,
                reviewed_by=self.coach,
                reviewed_at=reviewed,
            )
        Submission.objects.filter(pk=submission.pk).update(**changes)
        submission.refresh_from_db()
        award_for(submission)  # as review_submission does
        return submission

    def submissions(self):
        approved = Submission.Status.APPROVED
        revise = Submission.Status.NEEDS_REVISION
        anna, ben, chiara, max_, luna = (self.users[p[1]] for p in PARTICIPANTS)

        def blink(text):
            return {
                "programm": [{"text": BLINK_CODE, "original_filename": "blink.ino"}],
                "erklaerung": [{"text": text}],
            }

        # Anna: blink approved, arm waiting (photos), sensor still a draft.
        self.solution(
            anna,
            self.blink,
            blink("Die LED geht an und aus, je 500 ms."),
            self.ago(days=5),
            (
                approved,
                3,
                "Super erklärt! Probier als Nächstes den Sensor.",
                self.ago(days=4, hours=20),
            ),
        )
        self.solution(
            anna,
            self.arm,
            {
                "fotos": [
                    photo("Greifarm offen", "#2f6f8f"),
                    photo("Greifarm zu", "#3f7f5f"),
                ],
                "beschreibung": [
                    {
                        "text": "Ein Servo zieht an einer Schnur, "
                        "zwei Finger schliessen sich."
                    }
                ],
            },
            self.ago(days=2, hours=3),
        )
        self.solution(
            anna,
            self.sensor,
            {"programm": [{"text": "from machine import ADC\n# TODO"}]},
            None,
        )

        # Ben: blink needs revision, resubmitted (marked in the queue);
        # LED circuit waiting for three hours.
        self.solution(
            ben,
            self.blink,
            blink("Blinkt."),
            self.ago(days=4),
            (
                revise,
                None,
                "Erkläre bitte, was `delay(500)` bewirkt.",
                self.ago(days=3, hours=22),
            ),
        )
        self.solution(
            ben,
            self.blink,
            blink(
                "Blinkt. `delay(500)` wartet eine halbe Sekunde, "
                "bevor die LED umschaltet."
            ),
            self.ago(days=1),
        )
        self.solution(
            ben,
            self.led,
            {
                "foto": [photo("LED-Schaltung", "#8f3f3f")],
                "widerstand": [
                    {
                        "text": "220 Ohm, weil (5 V − 2 V) / 0,02 A = 150 Ohm "
                        "und 220 der nächste in der Kiste war."
                    }
                ],
            },
            self.ago(hours=3),
        )

        # Chiara: LED circuit approved (badge), blink approved with 2 stars
        # and resubmitted to improve them (badge too).
        self.solution(
            self.users["Chipsy"],
            self.led,
            {
                "foto": [photo("Meine LED", "#6f4f8f")],
                "widerstand": [{"text": "330 Ohm, damit die LED nicht zu hell ist."}],
            },
            self.ago(days=2),
            (
                Submission.Status.APPROVED,
                3,
                "Saubere Verkabelung!",
                self.ago(days=1, hours=20),
            ),
        )
        self.solution(
            chiara,
            self.blink,
            blink("LED an, warten, LED aus, warten."),
            self.ago(days=6),
            (
                approved,
                2,
                "Funktioniert. Für drei Sterne: erkläre `setup()`.",
                self.ago(days=5, hours=12),
            ),
        )
        self.solution(
            chiara,
            self.blink,
            blink(
                "`setup()` läuft einmal und macht den Pin zum Ausgang, "
                "`loop()` läuft immer wieder."
            ),
            self.ago(minutes=20),
        )

        # Max: sensor approved on version 1 (version 2 follows), case waiting.
        self.solution(
            max_,
            self.sensor,
            {
                "programm": [{"text": SENSOR_CODE, "original_filename": "sensor.py"}],
                "erklaerung": [{"text": "Hell: etwa 60000, dunkel: etwa 3000."}],
            },
            self.ago(days=3),
            (approved, 2, "Gut gemessen!", self.ago(days=2, hours=18)),
        )
        self.solution(
            max_,
            self.case,
            {
                "modell": [
                    {
                        "file": ContentFile(STL, name="gehaeuse.stl"),
                        "original_filename": "gehaeuse.stl",
                    }
                ]
            },
            self.ago(hours=30),
        )

        # Luna: new, has only started the LED circuit.
        start_attempt(luna, self.led)

    def sensor_v2(self):
        """Version 2 of the sensor task: Max stays pinned to version 1."""
        draft = self.sensor.create_draft(self.coach)
        draft.instructions += "\n\nGib den Wert zusätzlich in Prozent aus."
        draft.change_note = "Neu: Wert zusätzlich in Prozent ausgeben."
        draft.save()
        draft.publish()


def seed(password: str) -> None:
    Seeder(password).run()
