from django import forms
from django.core.exceptions import ValidationError

from .handlers import UploadHandler, handler_for


def field_name(requirement, suffix: str) -> str:
    return requirement.key if not suffix else f"{requirement.key}-{suffix}"


def stored_signature(items) -> str:
    """Changes whenever stored items are added or removed (polling)."""
    return "-".join(str(item.pk) for item in items) or "0"


class RequirementRow:
    """One requirement in the form, for the template."""

    def __init__(self, requirement, handler, fields, previous):
        self.requirement = requirement
        self.handler = handler
        self.fields = fields  # field names
        self.previous = previous  # stored items shown in the form

    @property
    def signature(self) -> str:
        return stored_signature(self.previous)

    @property
    def template(self) -> str:
        return self.handler.form_template if self.handler else ""

    @property
    def is_supported(self) -> bool:
        return self.handler is not None


class SubmissionForm(forms.Form):
    """Fields for all requirements of a version, built by their handlers.

    `previous` maps requirement ids to the items stored so far (the draft,
    or the last submission when resubmitting). After `is_valid()`,
    `items` maps requirement ids to the item dicts to store.
    """

    def __init__(self, requirements, previous=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requirements = list(requirements)
        self.previous = previous or {}
        self.items: dict[int, list[dict]] = {}
        self.rows: list[RequirementRow] = []
        for requirement in self.requirements:
            handler = handler_for(requirement)
            names = []
            stored = self.previous.get(requirement.pk, [])
            if handler is not None:
                initial = handler.initial(requirement, stored)
                for suffix, field in handler.form_fields(requirement, stored).items():
                    name = field_name(requirement, suffix)
                    self.fields[name] = field
                    if suffix in initial:
                        self.initial[name] = initial[suffix]
                    names.append(name)
            self.rows.append(RequirementRow(requirement, handler, names, stored))

    def bound_rows(self):
        for row in self.rows:
            yield (
                row,
                {
                    name.removeprefix(row.requirement.key).removeprefix("-")
                    or "main": self[name]
                    for name in row.fields
                },
            )

    def clean(self):
        cleaned = super().clean()
        for row in self.rows:
            if row.handler is None:
                continue
            requirement = row.requirement
            part = {
                name.removeprefix(requirement.key).removeprefix("-"): cleaned.get(name)
                for name in row.fields
            }
            try:
                self.items[requirement.pk] = row.handler.clean(
                    requirement, part, self.previous.get(requirement.pk, [])
                )
            except ValidationError as error:
                self.add_error(
                    row.fields[-1] if part.get("datei") else row.fields[0], error
                )
        return cleaned

    def unsupported_required(self):
        """Required requirements whose type cannot be submitted yet."""
        return [
            row.requirement
            for row in self.rows
            if row.handler is None and row.requirement.required
        ]

    def check_complete(self) -> bool:
        """For "Einreichen": adds an error to every incomplete requirement."""
        complete = not self.unsupported_required()
        for row in self.rows:
            if row.handler is None:
                continue
            items = self.items.get(row.requirement.pk, [])
            if not row.handler.is_complete(row.requirement, items):
                self.add_error(row.fields[0], "Das fehlt noch.")
                complete = False
        return complete


class PhoneUploadForm(forms.Form):
    """Only the upload fields (photos, files) of a draft, for the phone page.

    Adds to what is stored; removing happens in the full form.
    """

    def __init__(self, requirements, previous, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous = previous
        self.items: dict[int, list] = {}
        self.rows = []
        for requirement in requirements:
            handler = handler_for(requirement)
            if not isinstance(handler, UploadHandler):
                continue
            stored = previous.get(requirement.pk, [])
            field = handler.form_fields(requirement, stored)[""]
            self.fields[requirement.key] = field
            self.rows.append((requirement, handler, stored))

    def bound_rows(self):
        for requirement, _, stored in self.rows:
            yield requirement, stored, self[requirement.key]

    def clean(self):
        cleaned = super().clean()
        uploaded = False
        for requirement, handler, stored in self.rows:
            files = cleaned.get(requirement.key) or []
            if not files:
                continue
            uploaded = True
            try:
                self.items[requirement.pk] = handler.clean(
                    requirement, {"": files}, stored
                )
            except ValidationError as error:
                self.add_error(requirement.key, error)
        if not uploaded and not self.errors:
            raise ValidationError("Wähle zuerst ein Foto oder eine Datei aus.")
        return cleaned

    def added_count(self) -> int:
        return sum(
            sum(1 for value in values if isinstance(value, dict))
            for values in self.items.values()
        )
