"""Fill an empty local database with fake data: `manage.py seed`.

Dev tooling only (see CLAUDE.md): it builds every app's rows through the shared
factories in tests/factories. It refuses to run unless DEBUG is on and every app
table is empty (D-030).
"""

import random
from datetime import timedelta

import factory.random
from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleAssignment, User
from apps.approvals.models import ApprovalRequest
from apps.charities.models import Charity, Haskama, Link
from apps.charities.services import publish_charity
from apps.events.models import Event
from tests import factories as f
from tests.factories.accounts import DEFAULT_PASSWORD

Role = RoleAssignment.Role
Status = ApprovalRequest.Status

DOMAINS = [
    "Education",
    "Torah Study",
    "Hachnasas Kallah",
    "Medical",
    "Bikur Cholim",
    "Food Security",
    "Poverty Relief",
    "Orphans and Widows",
    "Elderly Care",
    "Special Needs",
    "Israel",
    "Disaster Relief",
]

LOCATIONS = [
    ("Brooklyn", "New York", "USA"),
    ("Monsey", "New York", "USA"),
    ("Lakewood", "New Jersey", "USA"),
    ("Passaic", "New Jersey", "USA"),
    ("Baltimore", "Maryland", "USA"),
    ("Chicago", "Illinois", "USA"),
    ("Los Angeles", "California", "USA"),
    ("Toronto", "Ontario", "Canada"),
    ("London", "England", "United Kingdom"),
    ("Jerusalem", "Jerusalem District", "Israel"),
    ("Bnei Brak", "Tel Aviv District", "Israel"),
    ("Beit Shemesh", "Jerusalem District", "Israel"),
]

NAME_PREFIXES = ["Keren", "Chasdei", "Yad", "Ezras", "Bais", "Tomchei", "Achiezer", "Lev"]
NAME_WORDS = ["Chesed", "Shalom", "Emunah", "Tzedakah", "Rachamim", "Simcha", "Torah", "Chaim"]

# Dev images come from the SVGs already in the repo (D-043, superseding D-024).
# Repo-relative paths, so the template serves them through {% static %}.
IMAGE_PATHS = [f"charities/img/charity-{index:02d}.svg" for index in range(1, 13)]
APPROVED, PENDING = 185, 15
MEMBERS, OWNERS, RABBIS = 100, 30, 10
EVENTS = 8000


class Command(BaseCommand):
    help = "Seed an empty database with ~200 fake charities, users, reviews, haskamas and events."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed only runs with DEBUG on (local development).")
        # Never wipe or add to existing data: this could be pointed at a real database.
        filled = [
            model._meta.label
            for model in django_apps.get_models()
            if model.__module__.startswith("apps.") and model.objects.exists()
        ]
        if filled:
            raise CommandError(
                "seed only runs on an empty database, and these tables have rows: "
                + ", ".join(sorted(filled))
                + ". Drop and recreate the database, run migrate, then seed."
            )
        self.rng = random.Random(613)
        factory.random.reseed_random(613)
        self.now = timezone.now()
        with transaction.atomic():
            self.seed()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Charity.objects.count()} charities, {User.objects.count()} users, "
                f"{Event.objects.count()} events. Log in as admin / admin; every other "
                f"user (member1, owner1, rabbi1) has password '{DEFAULT_PASSWORD}'."
            )
        )

    def seed(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", "admin")
        domains = [f.DomainFactory(name=name) for name in DOMAINS]
        locations = [f.LocationFactory(name=n, region=r, country=c) for n, r, c in LOCATIONS]

        members = self.users("member", MEMBERS, Role.MEMBER)
        owners = self.users("owner", OWNERS, Role.CHARITY_OWNER)
        rabbis = self.users("rabbi", RABBIS, Role.RABBI)
        for rabbi in rabbis:
            f.RabbiProfileFactory(user=rabbi)

        charities = []
        for i in range(APPROVED + PENDING):
            name = f"{self.rng.choice(NAME_PREFIXES)} {self.rng.choice(NAME_WORDS)}"
            approved = i < APPROVED
            charity = f.CharityFactory(name=name, image=IMAGE_PATHS[i % len(IMAGE_PATHS)])
            for domain in self.rng.sample(domains, self.rng.randint(1, 3)):
                f.CharityDomainFactory(charity=charity, domain=domain)
            f.CharityLocationFactory(charity=charity, location=self.rng.choice(locations))
            for kind in Link.Kind:
                f.LinkFactory(charity=charity, kind=kind, url=f"https://charity{i}.example.org/")
            f.NewCharityRequestFactory(
                charity=charity,
                approval_request__submitted_by=self.rng.choice(owners),
                approval_request__status=Status.APPROVED if approved else Status.PENDING,
                approval_request__decided_by=admin if approved else None,
            )
            if approved:
                # Through the service, as approvals will do, so it records its event (D-038).
                publish_charity(charity.id, by_user_id=admin.id)
            charities.append(charity)
        approved = charities[:APPROVED]

        for owner in owners:
            f.CharityOwnerFactory(user=owner, charity=self.rng.choice(approved))
        for charity in approved:
            for author in self.rng.sample(members, self.rng.randint(0, 6)):
                f.ReviewFactory(charity=charity, author=author)
        for rabbi in rabbis:
            for charity in self.rng.sample(approved, 15):
                verdict = self.rng.choices(list(Haskama.Verdict), weights=[9, 1])[0]
                f.HaskamaFactory(rabbi_user=rabbi, charity=charity, verdict=verdict)
        self.events(approved, members)

    def users(self, prefix, count, role):
        made = []
        for i in range(1, count + 1):
            user = f.UserFactory(username=f"{prefix}{i}")
            f.RoleAssignmentFactory(user=user, role=role)
            made.append(user)
        return made

    def events(self, approved, members):
        links = {}
        for link in Link.objects.filter(charity__in=approved):
            links.setdefault(link.charity_id, []).append(link)
        # Skewed popularity, so most-visited and trending have something to show.
        weights = [self.rng.paretovariate(1.2) for _ in approved]
        events = []
        for _ in range(EVENTS):
            charity = self.rng.choices(approved, weights=weights)[0]
            user = self.rng.choice(members) if self.rng.random() < 0.7 else None
            click = self.rng.random() < 0.25
            events.append(
                Event(
                    charity=charity,
                    user=user,
                    action=Event.Action.LINK_CLICK if click else Event.Action.VIEW,
                    link=self.rng.choice(links[charity.id]) if click else None,
                )
            )
        events = Event.objects.bulk_create(events)
        # auto_now_add stamps "now" on insert; spread events over the last 90 days instead.
        for event in events:
            event.created = self.now - timedelta(minutes=self.rng.randint(0, 90 * 24 * 60))
        Event.objects.bulk_update(events, ["created"], batch_size=1000)
