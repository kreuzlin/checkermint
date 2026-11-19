"""One handler per requirement type (ADR 0011).

A handler knows the form fields of its type, how to validate them, how to
turn them into `SubmissionItem`s and how to display those items. Forms and
views only iterate over requirements and delegate to the handler; adding a
type means adding a handler and registering it here.

Types without a handler yet (photo and file follow with #24) are shown as
"not possible yet" in the form; a version that requires one cannot be
submitted.
"""

from pathlib import PurePath

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, get_lexer_for_filename
from pygments.util import ClassNotFound

from tasks.models import TaskRequirement

from .models import SubmissionItem

MAX_TEXT_LENGTH = 10_000
MAX_CODE_LENGTH = 100_000
MAX_CODE_FILE_BYTES = 200 * 1024


def normalise_newlines(text: str) -> str:
    """Browsers send textarea content with CRLF; files may use either."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class RequirementHandler:
    """Base class. `cleaned` is the handler's part of the form data."""

    type: str = ""
    display_template: str = ""

    def form_fields(self, requirement) -> dict[str, forms.Field]:
        """Fields by suffix; the form names them `<key>` or `<key>-<suffix>`."""
        raise NotImplementedError

    def initial(self, requirement, items) -> dict:
        """Initial values (by suffix) from existing items."""
        raise NotImplementedError

    def clean(self, requirement, cleaned: dict, previous: list) -> list[dict]:
        """Validate and return the items to store, as field dicts.

        `previous`: the items stored so far (draft or earlier submission)."""
        raise NotImplementedError

    def is_complete(self, requirement, items: list[dict]) -> bool:
        if not requirement.required:
            return True
        return len(items) >= max(requirement.min_count, 1)

    def render(self, item: SubmissionItem) -> dict:
        """Template context for `display_template`."""
        return {"item": item}


class TextHandler(RequirementHandler):
    type = TaskRequirement.Type.TEXT
    display_template = "submissions/items/text.html"

    def form_fields(self, requirement):
        return {
            "": forms.CharField(
                label=requirement.label,
                help_text=requirement.help_text,
                required=False,
                max_length=MAX_TEXT_LENGTH,
                strip=True,
                widget=forms.Textarea(attrs={"rows": 6}),
            )
        }

    def initial(self, requirement, items):
        return {"": items[0].text if items else ""}

    def clean(self, requirement, cleaned, previous):
        text = cleaned.get("") or ""
        return [{"text": text}] if text else []


class CodeHandler(RequirementHandler):
    """Pasted code or an uploaded text file; stored as text (no file kept).

    `options`: `language` (Pygments name, e.g. "python"), `extensions`
    (allowed file endings, e.g. [".py", ".ino"]).
    """

    type = TaskRequirement.Type.CODE
    display_template = "submissions/items/code.html"

    def extensions(self, requirement) -> list[str]:
        return [str(e).lower() for e in requirement.options.get("extensions", [])]

    def form_fields(self, requirement):
        extensions = self.extensions(requirement)
        file_help = "Oder lade eine Textdatei hoch (höchstens 200 KB)."
        if extensions:
            file_help += " Erlaubt: " + ", ".join(extensions) + "."
        return {
            "": forms.CharField(
                label=requirement.label,
                help_text=requirement.help_text or "Füge deinen Code hier ein.",
                required=False,
                max_length=MAX_CODE_LENGTH,
                strip=False,
                widget=forms.Textarea(
                    attrs={"rows": 12, "class": "code-input", "spellcheck": "false"}
                ),
            ),
            "datei": forms.FileField(
                label=f"{requirement.label}: Datei",
                help_text=file_help,
                required=False,
                widget=forms.ClearableFileInput(
                    attrs={"accept": ",".join(extensions)} if extensions else {}
                ),
            ),
        }

    def initial(self, requirement, items):
        return {"": items[0].text if items else ""}

    def clean(self, requirement, cleaned, previous):
        code = normalise_newlines(cleaned.get("") or "").rstrip()
        upload = cleaned.get("datei")
        if upload:
            return [self._from_file(requirement, upload)]
        if not code.strip():
            return []
        item = {"text": code}
        # Unchanged code from an uploaded file keeps its name (highlighting).
        if previous and previous[0].text == code:
            item["original_filename"] = previous[0].original_filename
        return [item]

    def _from_file(self, requirement, upload) -> dict:
        name = PurePath(upload.name).name[:200]
        extensions = self.extensions(requirement)
        if extensions and PurePath(name).suffix.lower() not in extensions:
            raise ValidationError(
                "Diese Dateiendung ist hier nicht erlaubt. Erlaubt: %(allowed)s.",
                params={"allowed": ", ".join(extensions)},
            )
        if upload.size > MAX_CODE_FILE_BYTES:
            raise ValidationError("Die Datei ist zu gross (höchstens 200 KB).")
        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError(
                "Das ist keine Textdatei. Lade eine Code-Datei hoch oder füge den "
                "Code oben ein."
            ) from None
        if "\x00" in text:
            raise ValidationError("Das ist keine Textdatei.")
        if not text.strip():
            raise ValidationError("Die Datei ist leer.")
        return {"text": normalise_newlines(text).rstrip(), "original_filename": name}

    def lexer(self, item):
        language = item.requirement.options.get("language")
        try:
            if language:
                return get_lexer_by_name(str(language))
            if item.original_filename:
                return get_lexer_for_filename(item.original_filename)
        except ClassNotFound:
            pass
        return TextLexer()

    def render(self, item):
        # Pygments escapes the code; the output contains only its own spans.
        html = highlight(item.text, self.lexer(item), HtmlFormatter(wrapcode=True))
        return {"item": item, "highlighted": mark_safe(html)}


HANDLERS: dict[str, RequirementHandler] = {
    handler.type: handler for handler in [TextHandler(), CodeHandler()]
}


def handler_for(requirement) -> RequirementHandler | None:
    return HANDLERS.get(requirement.type)
