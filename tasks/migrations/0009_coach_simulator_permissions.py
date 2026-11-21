from django.db import migrations

from accounts.roles import sync_coach_group


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0008_simulator"),
    ]

    operations = [
        migrations.RunPython(sync_coach_group, migrations.RunPython.noop),
    ]
