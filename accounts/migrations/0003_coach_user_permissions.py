from django.db import migrations

from accounts.roles import sync_coach_group


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_coach_group"),
    ]

    operations = [
        migrations.RunPython(sync_coach_group, migrations.RunPython.noop),
    ]
