from django.contrib import admin

from .models import ApprovalRequest, EditRequest, NewCharityRequest, OwnerClaimRequest

admin.site.register([ApprovalRequest, NewCharityRequest, OwnerClaimRequest, EditRequest])
