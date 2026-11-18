"""Private uploads, served only through an access-checked view (ADR 0009).

Uploads are never public: no URL maps to a file system path. Each kind of
private file is registered here with the model that owns it, a function
that returns the stored file and an access check. The view
`core:private_file` loads the object, checks access and streams the file.

    register(
        "anleitungsbild",
        PrivateFileKind(
            model=InstructionImage,
            get_file=lambda obj, variant: obj.image,
            can_access=lambda user, obj: ...,
            inline=True,  # only for images we re-encoded ourselves
        ),
    )

Templates and code build links with `private_file_url(kind, obj)`.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from django.db.models import Model
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class RandomUploadPath:
    """`upload_to` that stores files as `<directory>/<uuid4><ext>`.

    The original name never reaches the file system (ADR 0009); keep it in
    a model field if it is needed for display or download.
    """

    def __init__(self, directory: str):
        self.directory = directory

    def __call__(self, instance, filename: str) -> str:
        extension = PurePath(filename).suffix.lower()
        if not extension[1:].isalnum() or len(extension) > 6:
            extension = ""
        return f"{self.directory}/{uuid.uuid4().hex}{extension}"

    def __eq__(self, other):
        return isinstance(other, RandomUploadPath) and other.directory == self.directory


@dataclass(frozen=True)
class PrivateFileKind:
    model: type[Model]
    # (object, variant or None) → FieldFile or None; e.g. variant "vorschau"
    # for a thumbnail.
    get_file: Callable
    # (user, object) → bool. Anonymous users reach this too.
    can_access: Callable
    # Show in the browser instead of downloading. Only for images that we
    # decoded and re-encoded ourselves (never for raw uploads, HTML or SVG).
    inline: bool = False
    # (object) → file name offered for downloads.
    get_filename: Callable | None = None
    cache_control: str = "private, no-store"


_registry: dict[str, PrivateFileKind] = {}


def register(name: str, kind: PrivateFileKind) -> None:
    if name in _registry and _registry[name] != kind:
        raise ValueError(f"Private file kind {name!r} is already registered.")
    _registry[name] = kind


def unregister(name: str) -> None:
    _registry.pop(name, None)


def get_kind(name: str) -> PrivateFileKind | None:
    return _registry.get(name)


def private_file_url(name: str, obj: Model, variant: str | None = None) -> str:
    if name not in _registry:
        raise ValueError(f"Unknown private file kind {name!r}.")
    kwargs = {"kind": name, "pk": obj.pk}
    if variant:
        kwargs["variant"] = variant
    return reverse("core:private_file", kwargs=kwargs)
