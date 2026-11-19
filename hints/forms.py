from django import forms

from .models import MESSAGE_MAX_LENGTH


class HintRequestForm(forms.Form):
    message = forms.CharField(
        label="Nachricht an den Coach",
        required=False,
        max_length=MESSAGE_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Freiwillig. Wo kommst du nicht weiter? "
        "Zum Beispiel: «Ich komme beim Motor nicht weiter.»",
    )


GRANT = "freigeben"
DECLINE = "ablehnen"


class HintDecisionForm(forms.Form):
    """Coach: grant or decline a hint request in the queue (#37)."""

    decision = forms.ChoiceField(
        choices=[(GRANT, "Freigeben"), (DECLINE, "Ablehnen")],
        error_messages={"required": "Bitte «Freigeben» oder «Ablehnen» wählen."},
    )
    reply = forms.CharField(
        label="Antwort",
        required=False,
        max_length=MESSAGE_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Freiwillig, die Teilnehmerin oder der Teilnehmer sieht sie. "
        "Beim Ablehnen zum Beispiel: «Prüf zuerst die Verkabelung.»",
    )
