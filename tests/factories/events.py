import factory
from factory.django import DjangoModelFactory

from apps.events.models import Event


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    user = factory.SubFactory("tests.factories.accounts.UserFactory")
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")
    link = None
    action = Event.Action.VIEW
