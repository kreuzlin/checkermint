"""One handler per requirement type (ADR 0011).

A handler knows the form fields of its type, how to validate them, how to
turn them into `SubmissionItem`s and how to display those items. Forms and
views only iterate over requirements and delegate to the handler; adding a
type means adding a handler and registering it here.

`clean` returns the items to store for a requirement: dicts for new items,
and stored `SubmissionItem`s from `previous` to keep (photos and files stay
in the draft until removed; when resubmitting they are copied). A type
without a handler is shown as "not possible yet" in the form; a version that
requires one cannot be submitted.
"""

from pathlib import PurePath

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, get_lexer_for_filename
from pygments.util import ClassNotFound

from core.images import process_photo
from core.private_files import private_file_url
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
    form_template: str = "submissions/fields/default.html"

    def form_fields(self, requirement, previous) -> dict[str, forms.Field]:
        """Fields by suffix; the form names them `<key>` or `<key>-<suffix>`."""
        raise NotImplementedError

    def initial(self, requirement, items) -> dict:
        """Initial values (by suffix) from existing items."""
        raise NotImplementedError

    def clean(self, requirement, cleaned: dict, previous: list) -> list:
        """Validate and return the items to store: dicts of fields for new
        items, or items from `previous` to keep.

        `previous`: the items stored so far (draft or earlier submission)."""
        raise NotImplementedError

    def is_complete(self, requirement, items: list) -> bool:
        if not requirement.required:
            return True
        return len(items) >= max(requirement.min_count, 1)

    def render(self, item: SubmissionItem) -> dict:
        """Template context for `display_template`."""
        return {"item": item}


class TextHandler(RequirementHandler):
    type = TaskRequirement.Type.TEXT
    display_template = "submissions/items/text.html"

    def form_fields(self, requirement, previous):
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

    def form_fields(self, requirement, previous):
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


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Several files in one input; cleans to a list."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, list | tuple) else [data]
        return [super(MultipleFileField, self).clean(f, None) for f in files if f]


def upload_name(upload) -> str:
    return PurePath(upload.name or "").name[:200]


class UploadHandler(RequirementHandler):
    """Common part of photos and files: upload several, keep or remove."""

    form_template = "submissions/fields/upload.html"
    accept = ""
    file_kind = ""

    def accept_for(self, requirement) -> str:
        """`accept` attribute of the file input (a hint, not a check)."""
        return self.accept

    def upload_help(self, requirement) -> str:
        raise NotImplementedError

    def form_fields(self, requirement, previous):
        accept = self.accept_for(requirement)
        attrs = {"accept": accept} if accept else {}
        if requirement.max_count == 1:
            widget = forms.ClearableFileInput(attrs=attrs)
        else:
            widget = MultipleFileInput(attrs=attrs)
        help_text = self.upload_help(requirement)
        if requirement.help_text:
            help_text = f"{requirement.help_text} {help_text}"
        fields = {
            "": MultipleFileField(
                label=requirement.label,
                help_text=help_text,
                required=False,
                widget=widget,
            )
        }
        if previous:
            fields["entfernen"] = forms.MultipleChoiceField(
                label="Entfernen",
                required=False,
                choices=[
                    (str(item.pk), item.original_filename or f"Nr. {n}")
                    for n, item in enumerate(previous, start=1)
                ],
                widget=forms.CheckboxSelectMultiple,
            )
        return fields

    def initial(self, requirement, items):
        return {}

    def clean(self, requirement, cleaned, previous):
        remove = set(cleaned.get("entfernen") or [])
        kept = [item for item in previous if str(item.pk) not in remove]
        uploads = cleaned.get("") or []
        if len(kept) + len(uploads) > requirement.max_count:
            raise ValidationError(
                "Höchstens %(max)d. Entferne zuerst etwas oder lade weniger hoch.",
                params={"max": requirement.max_count},
            )
        new = []
        for upload in uploads:
            try:
                new.append(self.process(requirement, upload))
            except ValidationError as error:
                raise ValidationError(
                    "%(name)s: %(error)s",
                    params={
                        "name": upload_name(upload),
                        "error": " ".join(error.messages),
                    },
                ) from None
        return kept + new

    def process(self, requirement, upload) -> dict:
        raise NotImplementedError

    def render(self, item):
        return {"item": item, "url": private_file_url(self.file_kind, item)}


class PhotoHandler(UploadHandler):
    """Photos: JPEG, PNG, HEIC, WebP; re-encoded without metadata, at most
    2000 px, with a thumbnail (ADR 0009)."""

    type = TaskRequirement.Type.PHOTO
    display_template = "submissions/items/photo.html"
    accept = "image/jpeg,image/png,image/heic,image/heif,image/webp,.heic,.heif"
    file_kind = "einreichungsfoto"

    def upload_help(self, requirement):
        return (
            f"Fotos als JPEG, PNG oder HEIC, je höchstens "
            f"{settings.UPLOAD_MAX_PHOTO_MB} MB."
        )

    def process(self, requirement, upload):
        photo, thumbnail = process_photo(
            upload, max_bytes=settings.UPLOAD_MAX_PHOTO_MB * 1024 * 1024
        )
        photo.content.name = f"foto{photo.extension}"
        thumbnail.content.name = f"vorschau{thumbnail.extension}"
        return {
            "file": photo.content,
            "thumbnail": thumbnail.content,
            "original_filename": upload_name(upload),
            "data": {"width": photo.width, "height": photo.height},
        }

    def render(self, item):
        context = super().render(item)
        if item.thumbnail:
            context["thumbnail_url"] = private_file_url(
                self.file_kind, item, variant="vorschau"
            )
        else:
            context["thumbnail_url"] = context["url"]
        return context


class FileHandler(UploadHandler):
    """Any file (e.g. CAD), stored as uploaded and always offered as a
    download. `options`: `extensions` (allowed endings, e.g. [".stl"])."""

    type = TaskRequirement.Type.FILE
    display_template = "submissions/items/file.html"
    file_kind = "einreichungsdatei"

    def extensions(self, requirement) -> list[str]:
        return [str(e).lower() for e in requirement.options.get("extensions", [])]

    def accept_for(self, requirement):
        return ",".join(self.extensions(requirement))

    def upload_help(self, requirement):
        text = f"Je höchstens {settings.UPLOAD_MAX_FILE_MB} MB."
        extensions = self.extensions(requirement)
        if extensions:
            text += " Erlaubt: " + ", ".join(extensions) + "."
        return text

    def process(self, requirement, upload):
        name = upload_name(upload)
        extensions = self.extensions(requirement)
        if extensions and PurePath(name).suffix.lower() not in extensions:
            raise ValidationError(
                "Diese Dateiendung ist hier nicht erlaubt. Erlaubt: %(allowed)s.",
                params={"allowed": ", ".join(extensions)},
            )
        if upload.size > settings.UPLOAD_MAX_FILE_MB * 1024 * 1024:
            raise ValidationError(
                "Die Datei ist zu gross (höchstens %(mb)d MB).",
                params={"mb": settings.UPLOAD_MAX_FILE_MB},
            )
        if not upload.size:
            raise ValidationError("Die Datei ist leer.")
        return {"file": upload, "original_filename": name}


HANDLERS: dict[str, RequirementHandler] = {
    handler.type: handler
    for handler in [TextHandler(), CodeHandler(), PhotoHandler(), FileHandler()]
}


def handler_for(requirement) -> RequirementHandler | None:
    return HANDLERS.get(requirement.type)
