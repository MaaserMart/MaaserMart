from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from apps.tools.models import Transaction


class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction

    user = factory.SubFactory("tests.factories.accounts.UserFactory")
    type = Transaction.Type.INCOME
    amount = Decimal("1000.00")
    date = factory.Faker("date_this_year")
    charity = None
    note = None
