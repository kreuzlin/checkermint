from django.db import migrations

from accounts.roles import sync_coach_group


def create_first_level(apps, schema_editor):
    """Level 1 at 0 points must always exist (ADR 0013)."""
    LevelThreshold = apps.get_model("tasks", "LevelThreshold")
    LevelThreshold.objects.get_or_create(level=1, defaults={"min_points": 0})


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0001_initial"),
        ("badges", "0001_initial"),
        ("accounts", "0002_coach_group"),
    ]

    operations = [
        migrations.RunPython(create_first_level, migrations.RunPython.noop),
        migrations.RunPython(sync_coach_group, migrations.RunPython.noop),
    ]
