from django.contrib import admin

from .models import ApprovalRequest, EditRequest, NewCharityRequest, OwnerClaimRequest


class ViewOnlyAdmin(admin.ModelAdmin):
    """Requests are decided only in the approval queue, through decide_request.

    Changing a status here would skip what a decision does: grant the role and
    email the applicant (D-YOSEF-rabbi-signup). So Django admin can view requests,
    not add, change or delete them.
    """

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(ViewOnlyAdmin):
    list_display = ["kind", "status", "submitted_by", "submitted_at", "decided_by"]
    list_filter = ["kind", "status"]


admin.site.register([NewCharityRequest, OwnerClaimRequest, EditRequest], ViewOnlyAdmin)
