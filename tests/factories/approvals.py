import factory
from factory.django import DjangoModelFactory

from apps.approvals.models import (
    ApprovalRequest,
    EditRequest,
    NewCharityRequest,
    OwnerClaimRequest,
)


class ApprovalRequestFactory(DjangoModelFactory):
    class Meta:
        model = ApprovalRequest

    submitted_by = factory.SubFactory("tests.factories.accounts.UserFactory")
    kind = ApprovalRequest.Kind.NEW_CHARITY
    status = ApprovalRequest.Status.PENDING


class NewCharityRequestFactory(DjangoModelFactory):
    class Meta:
        model = NewCharityRequest

    approval_request = factory.SubFactory(
        ApprovalRequestFactory, kind=ApprovalRequest.Kind.NEW_CHARITY
    )
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")


class OwnerClaimRequestFactory(DjangoModelFactory):
    class Meta:
        model = OwnerClaimRequest

    approval_request = factory.SubFactory(
        ApprovalRequestFactory, kind=ApprovalRequest.Kind.OWNER_CLAIM
    )
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")


class EditRequestFactory(DjangoModelFactory):
    class Meta:
        model = EditRequest

    approval_request = factory.SubFactory(ApprovalRequestFactory, kind=ApprovalRequest.Kind.EDIT)
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")
    user = None
    target_type = EditRequest.TargetType.CHARITY
    field = EditRequest.Field.TAGLINE
    old_value = None
    new_value = factory.Faker("catch_phrase")
