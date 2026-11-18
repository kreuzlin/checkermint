"""Robot avatars generated locally with Robohash set1 (ADR 0012).

The image depends only on the profile's random `avatar_seed`. Only set1 is
used (never "any", which could change avatars when the package adds sets);
Robohash's Gravatar feature and the robohash.org service are never used.
"""

import io
from functools import lru_cache

from robohash import Robohash

ROBOSET = "set1"

# Fixed sizes in pixels (square). Templates show them at half size on
# high-density screens, e.g. 128 px at 64 CSS pixels.
SIZES = (64, 128, 256)

# Credits for the artwork (CC-BY), shown in the footer and on the imprint.
CREDITS = {
    "work": "Robohash set1 «Classic robots»",
    "author": "Zikri Kader",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_url": "https://github.com/e1ven/Robohash",
}


@lru_cache(maxsize=512)
def render_avatar(seed: str, size: int) -> bytes:
    """PNG bytes of the robot for `seed` at `size` x `size` pixels."""
    if size not in SIZES:
        raise ValueError(f"Unsupported avatar size: {size}")
    robot = Robohash(seed)
    robot.assemble(roboset=ROBOSET, sizex=size, sizey=size)
    buffer = io.BytesIO()
    robot.img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
