from django.db import migrations

from accounts.roles import sync_coach_group


class Migration(migrations.Migration):
    dependencies = [
        ("badges", "0002_userbadge"),
    ]

    operations = [
        migrations.RunPython(sync_coach_group, migrations.RunPython.noop),
    ]
