"""Roles: participant, coach, admin (brief, section 2).

- Participant: a plain user without staff status.
- Coach: a staff user in the group "Coach" (never a superuser). The group is
  created and kept in sync by data migrations; when a new model needs coach
  permissions, extend `COACH_PERMISSIONS` and add a migration calling
  `sync_coach_group` again.
- Admin: Django superuser.
"""

COACH_GROUP_NAME = "Coach"

# app_label → model → actions.
# Users: the user admin (accounts.admin.UserAdmin) limits coaches to
# participant accounts and never shows staff, superuser, group or permission
# fields. No delete: accounts are deactivated instead.
COACH_PERMISSIONS = {
    "auth": {"user": ["view", "add", "change"]},
    # "add" is needed for the profile inline on the account form.
    "accounts": {"profile": ["view", "add", "change"]},
    "tasks": {
        "topic": ["view", "add", "change", "delete"],
        "levelthreshold": ["view", "add", "change", "delete"],
        # Published versions, requirements and hints stay immutable through
        # the model guards (ADR 0010), whatever the permissions say.
        "task": ["view", "add", "change", "delete"],
        "taskversion": ["view", "add", "change", "delete"],
        "taskrequirement": ["view", "add", "change", "delete"],
        "hint": ["view", "add", "change", "delete"],
        "instructionimage": ["view", "add", "change", "delete"],
    },
    "badges": {"badge": ["view", "add", "change", "delete"]},
    # View only: submissions are made by participants and reviewed in the
    # coach views (#31, #32), never edited in the admin.
    "submissions": {"submission": ["view"], "submissionitem": ["view"]},
}


def is_coach(user) -> bool:
    """True for active staff users in the coach group, and for superusers."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.is_staff and user.groups.filter(name=COACH_GROUP_NAME).exists()


def sync_coach_group(apps, schema_editor=None):
    """Create the group and set exactly the permissions above."""
    from django.contrib.auth.management import create_permissions

    # Permissions are normally created after all migrations ran; make sure
    # they exist now.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group, _ = Group.objects.get_or_create(name=COACH_GROUP_NAME)
    permissions = []
    for app_label, models in COACH_PERMISSIONS.items():
        for model, actions in models.items():
            for action in actions:
                # filter() instead of get(): models added by later migrations
                # do not exist yet on a fresh database; a later migration
                # syncs again.
                permissions.extend(
                    Permission.objects.filter(
                        content_type__app_label=app_label,
                        codename=f"{action}_{model}",
                    )
                )
    group.permissions.set(permissions)
