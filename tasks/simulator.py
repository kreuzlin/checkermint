"""GearsBot simulator links and files of task versions (ADR 0019, 0021)."""

import re
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import SimulatorConfig, SimulatorFile

# A JSON string value "sim-file:<name>" stands for the absolute URL of that
# file of the same version. Resolved when the file is served, so stored
# files need no host name and copies need no rewriting.
FILE_REFERENCE = re.compile(r"^sim-file:([A-Za-z0-9_-]+\.json)$")

# URL parameters of GearsBot's index.html per file role.
ROLE_PARAMETERS = {
    SimulatorFile.Role.WORLD: "worldJSON",
    SimulatorFile.Role.ROBOT: "robotJSON",
    SimulatorFile.Role.FILTER: "filterBlocksJSON",
}


# Key of the text requirement whose answer is compared with the expected
# completion code (ADR 0021).
COMPLETION_CODE_KEY = "completion-code"


def normalise_code(code: str) -> str:
    """Case and extra spaces do not matter: "salted  caramel" = "SALTED CARAMEL"."""
    return " ".join(code.split()).casefold()


def codes_match(given: str, expected: str) -> bool:
    return normalise_code(given) == normalise_code(expected)


def simulator_origin() -> str:
    """Scheme and host of SIMULATOR_URL, e.g. https://sim.checkermint.ch."""
    parts = urlsplit(settings.SIMULATOR_URL)
    return f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""


def file_url(request, token: str, filename: str) -> str:
    return request.build_absolute_uri(
        reverse("simulator_file", kwargs={"token": token, "filename": filename})
    )


def resolve_references(value, request, token):
    """Replace "sim-file:<name>" strings anywhere in the JSON value."""
    if isinstance(value, dict):
        return {k: resolve_references(v, request, token) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_references(v, request, token) for v in value]
    if isinstance(value, str):
        match = FILE_REFERENCE.match(value)
        if match:
            return file_url(request, token, match.group(1))
    return value


def launch_url(request, version) -> str:
    """Link for "Im Simulator öffnen", or "" if there is nothing to open."""
    if not settings.SIMULATOR_URL:
        return ""
    config = SimulatorConfig.objects.filter(task_version=version).first()
    if config is None:
        return ""
    files = {f.role: f for f in version.simulator_files.all()}
    if SimulatorFile.Role.WORLD not in files:
        return ""
    params = {}
    if config.world_scripts:
        params["worldScripts"] = config.world_scripts
    for role, parameter in ROLE_PARAMETERS.items():
        if role in files:
            params[parameter] = file_url(request, config.token, files[role].filename)
    return f"{settings.SIMULATOR_URL}/?{urlencode(params)}"


@require_GET
def simulator_file(request, token, filename):
    """A version's simulator JSON, without login, for GearsBot (CORS).

    The token is the protection; the files hold task content only. Files of
    archived tasks are gone.
    """
    file = get_object_or_404(
        SimulatorFile.objects.select_related("task_version__task"),
        task_version__simulator__token=token,
        filename=filename,
    )
    version = file.task_version
    if version.task.is_archived:
        raise Http404
    content = resolve_references(file.content, request, token)
    response = JsonResponse(content, json_dumps_params={"ensure_ascii": False})
    origin = simulator_origin()
    if origin:
        response["Access-Control-Allow-Origin"] = origin
    response["Cache-Control"] = (
        "public, max-age=3600" if version.is_published else "no-store"
    )
    return response
