from functools import cache

import factory
from django.contrib.auth.hashers import make_password
from factory.django import DjangoModelFactory

from apps.accounts.models import CharityOwner, RabbiProfile, RoleAssignment, User

DEFAULT_PASSWORD = "password"


@cache
def default_password_hash():
    """Hash DEFAULT_PASSWORD once per process; hashing per user makes seeding slow."""
    return make_password(DEFAULT_PASSWORD)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda u: f"{u.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.LazyFunction(default_password_hash)


class RoleAssignmentFactory(DjangoModelFactory):
    class Meta:
        model = RoleAssignment

    user = factory.SubFactory(UserFactory)
    role = RoleAssignment.Role.MEMBER


class RabbiProfileFactory(DjangoModelFactory):
    class Meta:
        model = RabbiProfile

    user = factory.SubFactory(UserFactory)
    title = "Rabbi"
    display_name = factory.LazyAttribute(lambda p: f"Rabbi {p.user.last_name}")


class CharityOwnerFactory(DjangoModelFactory):
    class Meta:
        model = CharityOwner

    user = factory.SubFactory(UserFactory)
    charity = factory.SubFactory("tests.factories.charities.CharityFactory")
