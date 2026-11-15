from django.contrib import admin

from .models import Charity, CharityDomain, CharityLocation, Domain, Haskama, Link, Location, Review
from .services import EDITABLE_FIELDS, hide_charity, publish_charity, update_charity


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
        """
        if not change:
            super().save_model(request, obj, form, change)
            return
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
