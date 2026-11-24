"""Forms for the charity page."""

from django import forms


class ReviewForm(forms.Form):
    """A rating is required; a written explanation is optional (D-020)."""

    rating = forms.TypedChoiceField(
        label="Rating",
        choices=[("", "Choose a rating")] + [(i, f"{i} out of 5") for i in range(1, 6)],
        coerce=int,
        empty_value=None,
    )
    body = forms.CharField(
        label="Your review (optional)", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
