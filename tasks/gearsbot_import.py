"""Import GearsBot's Basic Challenges as draft tasks (ADR 0021, #146).

Reads the committed bundle `sim/gears/challenges_basic/` (ADR 0020), never
GearsBot itself. Idempotent: tasks are found by their slug
`gearsbot-<file stem>`; published versions are never changed.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .gearsbot_missions import translate
from .models import (
    SimulatorConfig,
    SimulatorFile,
    Task,
    TaskRequirement,
    TaskVersion,
    Topic,
)
from .simulator import COMPLETION_CODE_KEY

BUNDLE = settings.BASE_DIR / "sim" / "gears" / "challenges_basic"
WORLD_FILENAME = "welt.json"
FILTER_FILENAME = "bloecke.json"
PROJECT_KEY = "projekt"
CHANGE_NOTE = "GearsBot-Update: Welt oder Code der Challenge geändert."
TOPIC_NAME = "Code"
TOPIC_SLUG = "code"

# Upstream group (file prefix) → German title, base points, minimum level
# in "Code" (brief, section 3.5). Coaches adjust them in the admin.
GROUPS = {
    "basic": ("Grundlagen", 10, 1),
    "sleep": ("Warten", 10, 1),
    "maze": ("Labyrinth", 15, 2),
    "dungeon": ("Verlies", 15, 2),
    "loops": ("Schleifen", 20, 3),
    "conditions": ("Bedingungen", 25, 4),
    "abstraction": ("Funktionen", 30, 5),
}

# Visible toolbox categories of GearsBot (ids, language independent).
ALL_CATEGORIES = [
    "Motion",
    "Motor",
    "Sensors",
    "Sound",
    "Pen",
    "Experimental",
    "Control",
    "Logic",
    "Loops",
    "Math",
    "Text",
    "Lists",
    "Variables",
    "Functions",
]


def block_filter(categories=(), blocks=()):
    """Hide every category, then show the beginner category `Movement`, the
    given categories and single blocks (ADR 0021, section 7)."""
    show = {"categories": ["Movement", *categories]}
    if blocks:
        show["blocks"] = list(blocks)
    return {"deny": {"categories": ALL_CATEGORIES}, "show": show}


_WAIT = ["sleep"]
_LOOPS = [*_WAIT, "controls_repeat_ext"]
_CONDITIONS = [*_LOOPS, "tw_color", "logic_compare", "logic_operation", "logic_boolean"]
FILTERS = {
    "basic": block_filter(),
    "sleep": block_filter(blocks=_WAIT),
    "maze": block_filter(blocks=_WAIT),
    "dungeon": block_filter(blocks=_WAIT),
    "loops": block_filter(blocks=_LOOPS),
    "conditions": block_filter(["Conditions"], _CONDITIONS),
    "abstraction": block_filter(["Conditions", "Variables", "Functions"], _CONDITIONS),
}

INSTRUCTIONS = """\
Eine Challenge im Roboter-Simulator GearsBot: «{upstream_title}».

**Mission:**

{mission}

Im Simulator zeigt der Knopf «Mission» denselben Auftrag auf Englisch.
{limit}
So gehst du vor:

1. Klicke auf **«Im Simulator öffnen»**. GearsBot öffnet sich in einem neuen Tab.
2. Baue dein Programm im Tab **«Blöcke»**.
3. Wechsle zum Tab **«Simulator»** und starte den Roboter mit ▶.
   Mit **«Zurücksetzen»** stellst du ihn wieder an den Start.
4. Geschafft? GearsBot zeigt «COMPLETED!» und einen **Completion code**.
   Trag ihn hier unten ein.
5. Freiwillig: Speichere dein Projekt in GearsBot unter **«Datei»** →
   «Exportiere eine zip Datei auf deinen Computer» und lade die ZIP-Datei
   hier hoch.
"""


@dataclass
class ImportResult:
    created: list[str] = field(default_factory=list)
    updated_drafts: list[str] = field(default_factory=list)
    new_drafts: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing_upstream: list[str] = field(default_factory=list)


def load_bundle(bundle: Path = BUNDLE):
    data = json.loads((bundle / "challenges.json").read_text())
    for challenge in data["challenges"]:
        challenge["world"] = json.loads((bundle / challenge["file"]).read_text())
    return data


def slug_for(challenge) -> str:
    return "gearsbot-" + challenge["file"].removesuffix(".json")


def title_for(challenge) -> str:
    prefix = GROUPS[challenge["group"]][0]
    number = challenge["file"].removesuffix(".json").split("-", 1)[1]
    return f"{prefix} {number}"


def instructions_for(challenge) -> str:
    mission = "\n".join(
        f"> {line}" if line else ">"
        for line in translate(challenge["mission"]).splitlines()
    )
    limit = ""
    if challenge["blocks_limit"]:
        limit = (
            f"\nDu darfst höchstens **{challenge['blocks_limit']} Blöcke** verwenden.\n"
        )
    return INSTRUCTIONS.format(
        upstream_title=challenge["title"], mission=mission or "> –", limit=limit
    )


def wrapper_world(challenge) -> dict:
    """The world GearsBot opens: `challenges_basic` with this challenge."""
    return {
        "worldName": "challenges_basic",
        "options": {
            "jsonFile": f"sim-file:{challenge['file']}",
            "useDefaultRobot": True,
        },
    }


def fill_version(version, challenge):
    """Requirements and simulator settings of a new version."""
    TaskRequirement.objects.create(
        task_version=version,
        key=COMPLETION_CODE_KEY,
        type=TaskRequirement.Type.TEXT,
        label="Completion-Code",
        help_text="Den Code zeigt GearsBot, wenn du die Challenge geschafft hast.",
    )
    TaskRequirement.objects.create(
        task_version=version,
        key=PROJECT_KEY,
        type=TaskRequirement.Type.FILE,
        label="GearsBot-Projekt (.zip)",
        help_text="Freiwillig: dein in GearsBot gespeichertes Projekt.",
        required=False,
        min_count=0,
        max_count=1,
        options={"extensions": [".zip"], "gearsbot_project": True},
        order=1,
    )
    SimulatorConfig.objects.create(
        task_version=version,
        world_scripts="challenges_basic",
        expected_code=challenge["code"],
    )
    files = [
        (SimulatorFile.Role.WORLD, WORLD_FILENAME, wrapper_world(challenge)),
        (SimulatorFile.Role.CHALLENGE_WORLD, challenge["file"], challenge["world"]),
        (SimulatorFile.Role.FILTER, FILTER_FILENAME, FILTERS[challenge["group"]]),
    ]
    for role, filename, content in files:
        SimulatorFile.objects.create(
            task_version=version, role=role, filename=filename, content=content
        )


def create_task(topic, challenge):
    _, points, level = GROUPS[challenge["group"]]
    task = Task.objects.create(
        topic=topic,
        slug=slug_for(challenge),
        order=challenge["order"],
        min_level=level,
        is_published=False,
    )
    version = TaskVersion.objects.create(
        task=task,
        title=title_for(challenge),
        instructions=instructions_for(challenge),
        base_points=points,
    )
    fill_version(version, challenge)
    return task


def is_current(version, challenge) -> bool:
    """Whether the version has the bundle's challenge world and code."""
    config = SimulatorConfig.objects.filter(task_version=version).first()
    world = version.simulator_files.filter(
        role=SimulatorFile.Role.CHALLENGE_WORLD
    ).first()
    return (
        config is not None
        and world is not None
        and config.expected_code == challenge["code"]
        and world.filename == challenge["file"]
        and world.content == challenge["world"]
    )


def apply_upstream(version, challenge):
    """Put the bundle's world and code into a draft; coaches' other edits
    (title, text, points, filter, …) stay."""
    config, _ = SimulatorConfig.objects.get_or_create(
        task_version=version, defaults={"world_scripts": "challenges_basic"}
    )
    config.expected_code = challenge["code"]
    config.save()
    SimulatorFile.objects.update_or_create(
        task_version=version,
        role=SimulatorFile.Role.CHALLENGE_WORLD,
        defaults={"filename": challenge["file"], "content": challenge["world"]},
    )
    SimulatorFile.objects.update_or_create(
        task_version=version,
        role=SimulatorFile.Role.WORLD,
        defaults={"filename": WORLD_FILENAME, "content": wrapper_world(challenge)},
    )


class TopicNameTaken(Exception):
    """Another topic (e.g. the demo topic) already has the name "Code"."""


def get_topic():
    topic = Topic.objects.filter(slug=TOPIC_SLUG).first()
    if topic is not None:
        return topic
    other = Topic.objects.filter(name=TOPIC_NAME).first()
    if other is not None:
        raise TopicNameTaken(
            f"Es gibt schon ein Thema «{TOPIC_NAME}» (Kennung «{other.slug}»), "
            f"aber nicht das Thema mit der Kennung «{TOPIC_SLUG}», in das die "
            "Challenges gehören. Ist es das Übungs-Thema der Demo-Daten, "
            f"benenne es zuerst in der Verwaltung um, z. B. in «{TOPIC_NAME} "
            "(Demo)». Danach legt der Import das echte Thema an."
        )
    return Topic.objects.create(name=TOPIC_NAME, slug=TOPIC_SLUG)


def import_challenges(bundle: Path = BUNDLE, dry_run=False) -> ImportResult:
    data = load_bundle(bundle)
    result = ImportResult()
    with transaction.atomic():
        topic = get_topic()
        slugs = set()
        for challenge in data["challenges"]:
            slug = slug_for(challenge)
            slugs.add(slug)
            label = f"{slug} ({title_for(challenge)})"
            task = Task.objects.filter(slug=slug).first()
            if task is None:
                create_task(topic, challenge)
                result.created.append(label)
                continue
            if task.is_archived:
                result.skipped.append(f"{label}: archiviert")
                continue
            latest = task.versions.order_by("-number").first()
            if latest is not None and is_current(latest, challenge):
                result.unchanged.append(label)
                continue
            if latest is not None and not latest.is_published:
                apply_upstream(latest, challenge)
                result.updated_drafts.append(label)
                continue
            draft = task.create_draft()
            if latest is None:
                # A task without any version: build the draft from scratch.
                fill_version(draft, challenge)
            else:
                draft.change_note = CHANGE_NOTE
                draft.save()
                apply_upstream(draft, challenge)
            result.new_drafts.append(label)
        result.missing_upstream = sorted(
            Task.objects.filter(slug__startswith="gearsbot-")
            .exclude(slug__in=slugs)
            .values_list("slug", flat=True)
        )
        if dry_run:
            transaction.set_rollback(True)
    return result
