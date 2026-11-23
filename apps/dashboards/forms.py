"""The haskama box on the rabbi dashboard (§6.2.9, UC-06)."""

from django import forms

from apps.charities import services as charities

LOW, HIGH = charities.HASKAMA_IMPORTANCE_RANGE
BODY_MAX_LENGTH = 5000


class HaskamaForm(forms.Form):
    verdict = forms.ChoiceField(
        choices=charities.HASKAMA_VERDICTS,
        widget=forms.RadioSelect,
        error_messages={"required": "Choose approve or disapprove."},
    )
    importance = forms.IntegerField(
        min_value=LOW,
        max_value=HIGH,
        required=False,
        error_messages={
            "min_value": f"Importance is {LOW} to {HIGH}.",
            "max_value": f"Importance is {LOW} to {HIGH}.",
            "invalid": f"Importance is a whole number from {LOW} to {HIGH}.",
        },
    )
    body = forms.CharField(max_length=BODY_MAX_LENGTH, required=False, widget=forms.Textarea)
