"""The rabbi application, filled in after signup (D-YOSEF-rabbi-signup)."""

from django import forms


class RabbiApplicationForm(forms.Form):
    display_name = forms.CharField(
        max_length=150, error_messages={"required": "Enter your name as it should be shown."}
    )
    title = forms.CharField(max_length=100, required=False)
    agree_hashkafa = forms.BooleanField(
        error_messages={"required": "Tick the box to agree to the hashkafa statement."}
    )
