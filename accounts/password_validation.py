"""Password rules (brief, section 11).

Participants are children aged 7 to 16: their passwords need at least 6
characters. Coaches and admins (staff users) keep Django's default of 8.
The other Django validators (similarity, common, numeric) apply to everyone.
"""

from django.core.exceptions import ValidationError


class RoleMinimumLengthValidator:
    def __init__(self, participant_min_length=6, staff_min_length=8):
        self.participant_min_length = participant_min_length
        self.staff_min_length = staff_min_length

    def min_length_for(self, user) -> int:
        # Without a user (e.g. a form that does not know it yet), apply the
        # stricter rule.
        if user is None or user.is_staff or user.is_superuser:
            return self.staff_min_length
        return self.participant_min_length

    def validate(self, password, user=None):
        min_length = self.min_length_for(user)
        if len(password) < min_length:
            raise ValidationError(
                "Das Passwort ist zu kurz. Es muss mindestens %(min_length)d "
                "Zeichen lang sein.",
                code="password_too_short",
                params={"min_length": min_length},
            )

    def get_help_text(self):
        return (
            f"Mindestens {self.participant_min_length} Zeichen für "
            f"Teilnehmende, {self.staff_min_length} für Coaches."
        )
