import uuid

import factory
from factory.django import DjangoModelFactory

from apps.approvals.models import ApprovalRequest, NewCharityRequest


class ApprovalRequestFactory(DjangoModelFactory):
    class Meta:
        model = ApprovalRequest

    submitted_by = factory.SubFactory("tests.factories.accounts.UserFactory")
    kind = ApprovalRequest.Kind.NEW_CHARITY
    status = ApprovalRequest.Status.PENDING
    batch_id = factory.LazyFunction(uuid.uuid4)


class NewCharityRequestFactory(DjangoModelFactory):
    class Meta:
        model = NewCharityRequest

    approval_request = factory.SubFactory(
        ApprovalRequestFactory, kind=ApprovalRequest.Kind.NEW_CHARITY
    )
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")
