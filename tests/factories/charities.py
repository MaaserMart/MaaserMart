import factory
from factory.django import DjangoModelFactory

from apps.charities.models import (
    Charity,
    CharityDomain,
    CharityLocation,
    Domain,
    Haskama,
    Link,
    Location,
    Review,
)


class LocationFactory(DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Faker("city")
    region = factory.Faker("state")
    country = "USA"


class DomainFactory(DjangoModelFactory):
    class Meta:
        model = Domain
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Domain {n}")


class CharityFactory(DjangoModelFactory):
    class Meta:
        model = Charity

    name = factory.Faker("company")
    tagline = factory.Faker("catch_phrase")
    description = factory.Faker("paragraph", nb_sentences=5)
    image = None


class CharityDomainFactory(DjangoModelFactory):
    class Meta:
        model = CharityDomain

    charity = factory.SubFactory(CharityFactory)
    domain = factory.SubFactory(DomainFactory)


class CharityLocationFactory(DjangoModelFactory):
    class Meta:
        model = CharityLocation

    charity = factory.SubFactory(CharityFactory)
    location = factory.SubFactory(LocationFactory)


class LinkFactory(DjangoModelFactory):
    class Meta:
        model = Link

    charity = factory.SubFactory(CharityFactory)
    kind = Link.Kind.WEBSITE_DONATE
    url = factory.Faker("url")


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    charity = factory.SubFactory(CharityFactory)
    author = factory.SubFactory("tests.factories.accounts.UserFactory")
    rating = factory.Faker("random_int", min=1, max=5)
    body = factory.Faker("paragraph", nb_sentences=3)


class HaskamaFactory(DjangoModelFactory):
    class Meta:
        model = Haskama

    rabbi_user = factory.SubFactory("tests.factories.accounts.UserFactory")
    charity = factory.SubFactory(CharityFactory)
    verdict = Haskama.Verdict.APPROVE
    importance = factory.Faker("random_int", min=1, max=10)
    body = factory.Faker("sentence")
