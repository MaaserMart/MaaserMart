from django.contrib import admin

from .models import Charity, CharityDomain, CharityLocation, Domain, Haskama, Link, Location, Review
from .services import EDITABLE_FIELDS, hide_charity, publish_charity, update_charity


class CharityAdminUnappliedFieldError(ValueError):
    """The admin form changed a field the charity service will not write (audit B2)."""


@admin.register(Charity)
class CharityAdmin(admin.ModelAdmin):
    """is_visible changes only through the services, so each change records an event (D-038)."""

    list_display = ["name", "is_visible", "created"]
    readonly_fields = ["is_visible"]
    actions = ["publish", "hide"]

    def save_model(self, request, obj, form, change):
        """Save edits through the service, so each one records an event (D-052).

        Creating a charity is not a change, so that path uses Django's own save
        and records no event, exactly as the factories and the seed do (D-022).
        An admin-added charity is approved by definition, so it is published in
        the same request (D-038): it must not sit hidden with no way to publish
        it except a bulk action (audit B7).

        On a change, every changed field must be one the service applies. A
        field the admin form offers but `update_charity` does not accept would
        otherwise report "changed successfully" while the value never reached
        the database, so that is an error, not a silent drop (audit B2).
        """
        if not change:
            super().save_model(request, obj, form, change)
            publish_charity(obj.pk, by_user_id=request.user.id)
            return
        readonly = set(self.get_readonly_fields(request, obj))
        unapplied = [
            field
            for field in form.changed_data
            if field not in EDITABLE_FIELDS and field not in readonly
        ]
        if unapplied:
            raise CharityAdminUnappliedFieldError(
                "This admin form changed fields the charity service does not apply: "
                + ", ".join(sorted(unapplied))
                + ". Add them to EDITABLE_FIELDS and update_charity, or make them read-only."
            )
        changes = {
            field: form.cleaned_data[field]
            for field in form.changed_data
            if field in EDITABLE_FIELDS
        }
        update_charity(obj.pk, by_user_id=request.user.id, **changes)

    @admin.action(description="Publish selected charities")
    def publish(self, request, queryset):
        for charity_id in queryset.values_list("id", flat=True):
            publish_charity(charity_id, by_user_id=request.user.id)

    @admin.action(description="Hide selected charities")
    def hide(self, request, queryset):
        for charity_id in queryset.values_list("id", flat=True):
            hide_charity(charity_id, by_user_id=request.user.id)


admin.site.register([Location, Domain, CharityDomain, CharityLocation, Link, Review, Haskama])
