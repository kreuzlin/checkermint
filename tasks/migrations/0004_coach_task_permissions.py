from django.db import migrations

from accounts.roles import sync_coach_group


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0003_tasks_and_versions"),
    ]

    operations = [
        migrations.RunPython(sync_coach_group, migrations.RunPython.noop),
    ]
