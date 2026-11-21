"""German missions of GearsBot's Basic Challenges (#146).

GearsBot only has English mission texts. The import translates them
paragraph by paragraph with this table; a paragraph that is not in it
(e.g. new upstream text after a GearsBot update) stays English, so nothing
is lost, and `untranslated` lists it for the next update PR.

Block limit sentences ("You're may only use 4 blocks.") are dropped: the
instructions state the real limit from the success check, and upstream's
sentence is sometimes wrong (loops-5 says 4, the check allows 7).
"""

import re

BLOCK_LIMIT = re.compile(r"^You're may only use \d+ blocks?\.$")

PARAGRAPHS = {
    "Move your robot into the green box and stop inside.": (
        "Fahre mit deinem Roboter in das grüne Feld und halte darin an."
    ),
    'Try using multiple "Move Forward" blocks.': (
        "Versuch es mit mehreren Blöcken zum Vorwärtsfahren."
    ),
    'You will need to use a "Turn" block.': "Du brauchst einen Block zum Drehen.",
    "Sometimes the box is behind you!": "Manchmal liegt das Feld hinter dir!",
    "Move your robot into every box.": "Fahre mit deinem Roboter in jedes Feld.",
    "You will need to stop inside each box for 1 second before moving to the next!": (
        "Halte in jedem Feld 1 Sekunde lang an, bevor du zum nächsten fährst!"
    ),
    "Be careful! The shortest route isn't always the best...": (
        "Pass auf! Der kürzeste Weg ist nicht immer der beste …"
    ),
    "Watch out for the monster!": "Achtung, das Monster!",
    "How can we get that gate open?": "Wie bekommst du das Tor auf?",
    "You'll need to use everything you've learned!": (
        "Hier brauchst du alles, was du bisher gelernt hast!"
    ),
    "Watch out for the ghost!": "Achtung, das Gespenst!",
    "Move your robot into every box and stop for 1 second.": (
        "Fahre mit deinem Roboter in jedes Feld und halte darin 1 Sekunde lang an."
    ),
    "You may need to use more than one repeat loop.": (
        "Vielleicht brauchst du mehr als eine Wiederholen-Schleife."
    ),
    "Not every block needs to be inside a loop.": (
        "Nicht jeder Block muss in einer Schleife stehen."
    ),
    "Collect all the coins.": "Sammle alle Münzen ein.",
    "Hint: Look at the example.": "Tipp: Schau dir das Beispiel an.",
    "Drive into the green box.": "Fahre in das grüne Feld.",
    "The position of the box changes randomly every time the world is reset.": (
        "Bei jedem «Zurücksetzen» liegt das Feld an einer anderen, zufälligen Stelle."
    ),
    "Use the color on the ground to figure out where it will appear.": (
        "Die Farbe auf dem Boden verrät dir, wo es auftaucht."
    ),
    "Don't get distracted by the alien!": "Lass dich nicht vom Alien ablenken!",
    "Why is there a zebra in the dungeon?": "Was macht eigentlich ein Zebra im Verlies?",
    "The cat looks fascinated by the ball!": "Die Katze findet den Ball total spannend!",
    "Everything is spinning!": "Alles dreht sich!",
    "Don't let the water distract you! The green box changes position on reset.": (
        "Lass dich nicht vom Wasser ablenken! Das grüne Feld liegt nach jedem "
        "«Zurücksetzen» an einer anderen Stelle."
    ),
    "No blocks limits, but the green box changes position on reset.": (
        "Hier gibt es keine Blockgrenze, aber das grüne Feld liegt nach jedem "
        "«Zurücksetzen» an einer anderen Stelle."
    ),
}


def paragraphs(mission: str) -> list[str]:
    return [p.strip() for p in mission.split("\n\n") if p.strip()]


def untranslated(mission: str) -> list[str]:
    """Paragraphs of an English mission that the table does not cover."""
    return [
        p
        for p in paragraphs(mission)
        if p not in PARAGRAPHS and not BLOCK_LIMIT.match(p)
    ]


def translate(mission: str) -> str:
    """German mission; unknown paragraphs stay English, limits are dropped."""
    return "\n\n".join(
        PARAGRAPHS.get(p, p) for p in paragraphs(mission) if not BLOCK_LIMIT.match(p)
    )
