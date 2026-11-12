import factory
from factory.django import DjangoModelFactory

from apps.support.models import Ticket


class TicketFactory(DjangoModelFactory):
    class Meta:
        model = Ticket

    submitted_by = factory.SubFactory("tests.factories.accounts.UserFactory")
    kind = Ticket.Kind.HELP
    charity = None
    body = factory.Faker("paragraph", nb_sentences=2)
    status = Ticket.Status.NOT_RESPONDED
