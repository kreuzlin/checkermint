"""Main navigation.

Each feature app adds its entry here once its URLs exist, e.g.
`NavItem("Kontakt", "contact:form")`; the URL is resolved at render time.
`members_only` entries are shown to logged-in users only. The home page has
no entry: the site name in the header links to it.
"""

from typing import NamedTuple


class NavItem(NamedTuple):
    label: str
    url_name: str
    members_only: bool = False


MAIN_NAVIGATION: list[NavItem] = [
    NavItem("Aufgaben", "tasks:catalogue", members_only=True),
    NavItem("Mein Verlauf", "submissions:history", members_only=True),
    NavItem("Teilnehmende", "accounts:participant_list", members_only=True),
]
