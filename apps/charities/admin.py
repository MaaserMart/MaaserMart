from django.contrib import admin

from .models import Charity, CharityDomain, CharityLocation, Domain, Haskama, Link, Location, Review
from .services import hide_charity, publish_charity


@admin.register(Charity)
class CharityAdmin(admin.ModelAdmin):
    """is_visible changes only through the services, so each change records an event (D-038)."""

    list_display = ["name", "is_visible", "created"]
    readonly_fields = ["is_visible"]
    actions = ["publish", "hide"]

    @admin.action(description="Publish selected charities")
    def publish(self, request, queryset):
        for charity_id in queryset.values_list("id", flat=True):
            publish_charity(charity_id, by_user_id=request.user.id)

    @admin.action(description="Hide selected charities")
    def hide(self, request, queryset):
        for charity_id in queryset.values_list("id", flat=True):
            hide_charity(charity_id, by_user_id=request.user.id)


admin.site.register([Location, Domain, CharityDomain, CharityLocation, Link, Review, Haskama])
