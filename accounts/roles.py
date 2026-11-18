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
# User accounts (auth.user) are added together with a hardened user admin
# (#11), so that coaches can never grant themselves staff or superuser
# rights.
COACH_PERMISSIONS = {
    "accounts": {"profile": ["view", "change"]},
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
