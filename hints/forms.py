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
