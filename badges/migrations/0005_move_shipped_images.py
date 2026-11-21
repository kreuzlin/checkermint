"""Move the shipped badge images into the uploaded image field (ADR 0018).

For every badge that uses one of the images shipped in
badges/static/badges/img/ (field `image`), the image goes through the same
processing as an upload (badges.images) and is stored in `image_file`.
Badges that already have an uploaded image are left alone. Backwards: the
uploaded files are deleted and `image_file` is emptied; `image` is never
changed here.
"""

from pathlib import Path

from django.core.files import File
from django.db import migrations

SHIPPED = Path(__file__).resolve().parent.parent / "static" / "badges" / "img"


def move_shipped_images(apps, schema_editor):
    from badges.images import process_badge_image

    Badge = apps.get_model("badges", "Badge")
    for badge in Badge.objects.exclude(image="").filter(image_file=""):
        path = SHIPPED / badge.image
        if path.suffix.lower() not in {".png", ".webp"} or not path.is_file():
            continue
        with path.open("rb") as handle:
            content = process_badge_image(File(handle))
        badge.image_file.save(content.name, content, save=False)
        badge.save(update_fields=["image_file"])


def remove_uploaded_images(apps, schema_editor):
    Badge = apps.get_model("badges", "Badge")
    for badge in Badge.objects.exclude(image_file=""):
        badge.image_file.delete(save=False)
        badge.save(update_fields=["image_file"])


class Migration(migrations.Migration):
    dependencies = [
        ("badges", "0004_badge_image_file"),
    ]

    operations = [
        migrations.RunPython(move_shipped_images, remove_uploaded_images),
    ]
