"""Fill the local database with fake data: `uv run python manage.py seed`.

Dev tooling only (see CLAUDE.md): it builds every app's rows through the shared
factories in tests/factories. It refuses to run unless DEBUG is on.
"""

import random
from datetime import timedelta
from decimal import Decimal

import factory.random
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CharityOwner, RabbiProfile, RoleAssignment, User
from apps.approvals.models import (
    ApprovalRequest,
    EditRequest,
    NewCharityRequest,
    OwnerClaimRequest,
)
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
from apps.events.models import Event
from apps.support.models import Ticket
from apps.tools.models import Transaction
from tests import factories as f
from tests.factories.accounts import DEFAULT_PASSWORD

Role = RoleAssignment.Role

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
    ("Five Towns", "New York", "USA"),
    ("Lakewood", "New Jersey", "USA"),
    ("Passaic", "New Jersey", "USA"),
    ("Teaneck", "New Jersey", "USA"),
    ("Baltimore", "Maryland", "USA"),
    ("Chicago", "Illinois", "USA"),
    ("Cleveland", "Ohio", "USA"),
    ("Detroit", "Michigan", "USA"),
    ("Miami", "Florida", "USA"),
    ("Los Angeles", "California", "USA"),
    ("Toronto", "Ontario", "Canada"),
    ("Montreal", "Quebec", "Canada"),
    ("London", "England", "United Kingdom"),
    ("Manchester", "England", "United Kingdom"),
    ("Antwerp", "Flanders", "Belgium"),
    ("Jerusalem", "Jerusalem District", "Israel"),
    ("Bnei Brak", "Tel Aviv District", "Israel"),
    ("Beit Shemesh", "Jerusalem District", "Israel"),
]

NAME_PREFIXES = ["Keren", "Chasdei", "Yad", "Ezras", "Bais", "Tomchei", "Achiezer", "Lev"]
NAME_WORDS = ["Chesed", "Shalom", "Emunah", "Tzedakah", "Rachamim", "Simcha", "Torah", "Chaim"]
NAME_SUFFIXES = ["Fund", "Foundation", "Society", "Network", "Initiative", "Organization"]

COUNTS = {
    "charities": 200,
    "pending_charities": 15,
    "rejected_charities": 5,
    "members": 120,
    "owners": 40,
    "rabbis": 10,
    "supporters": 2,
    "events": 8000,
    "tickets": 15,
    "maaser_members": 30,
}

# Delete order respects PROTECT foreign keys (events and requests point at charities).
RESET_ORDER = [
    Event,
    Transaction,
    Ticket,
    EditRequest,
    NewCharityRequest,
    OwnerClaimRequest,
    ApprovalRequest,
    Review,
    Haskama,
    Link,
    CharityDomain,
    CharityLocation,
    CharityOwner,
    Charity,
    Domain,
    Location,
    RabbiProfile,
    RoleAssignment,
    User,
]


class Command(BaseCommand):
    help = "Fill the local database with ~200 fake charities and related data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete all existing app data first."
        )
        parser.add_argument("--seed", type=int, default=613, help="Random seed (default 613).")
        parser.add_argument(
            "--admin-password",
            default="admin",
            help="Password for the 'admin' superuser (default: admin).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed only runs with DEBUG on (local development).")
        if Charity.objects.exists() and not options["reset"]:
            raise CommandError("The database already has charities. Re-run with --reset.")

        self.rng = random.Random(options["seed"])
        factory.random.reseed_random(options["seed"])
        self.now = timezone.now()

        with transaction.atomic():
            if options["reset"]:
                for model in RESET_ORDER:
                    model.objects.all().delete()
            self.seed(options["admin_password"])

        self.stdout.write(self.style.SUCCESS(self.summary(options["admin_password"])))

    def seed(self, admin_password):
        self.admin = User.objects.create_superuser(
            "admin", "admin@example.com", admin_password, first_name="Site", last_name="Admin"
        )
        domains = [f.DomainFactory(name=name) for name in DOMAINS]
        locations = [f.LocationFactory(name=n, region=r, country=c) for n, r, c in LOCATIONS]
        users = self.seed_users()
        charities = self.seed_charities(domains, locations)
        self.seed_approvals(charities, users)
        self.seed_reviews_and_haskamas(charities["approved"], users)
        self.seed_events(charities["approved"], users["members"])
        self.seed_tickets_and_transactions(charities["approved"], users)

    def seed_users(self):
        def make(prefix, count, role):
            made = []
            for i in range(1, count + 1):
                user = f.UserFactory(username=f"{prefix}{i}")
                if role:
                    f.RoleAssignmentFactory(user=user, role=role)
                made.append(user)
            return made

        members = make("member", COUNTS["members"], Role.MEMBER)
        owners = make("owner", COUNTS["owners"], Role.CHARITY_OWNER)
        rabbis = make("rabbi", COUNTS["rabbis"], Role.RABBI)
        supporters = make("supporter", COUNTS["supporters"], Role.TECHNICAL_SUPPORTER)
        for rabbi in rabbis:
            f.RabbiProfileFactory(user=rabbi, title=self.rng.choice(["Rabbi", "Rav", "Dayan"]))
        # A few owners are also members, so the dashboard chooser has users to show.
        for owner in owners[:5]:
            f.RoleAssignmentFactory(user=owner, role=Role.MEMBER)
        # Applicants with an open request but no role yet (D-018).
        pending_rabbis = make("pending_rabbi", 2, None)
        for user in pending_rabbis:
            f.RabbiProfileFactory(user=user)
        return {
            "members": members,
            "owners": owners,
            "rabbis": rabbis,
            "supporters": supporters,
            "pending_rabbis": pending_rabbis,
        }

    def charity_name(self):
        if self.rng.random() < 0.5:
            return f"{self.rng.choice(NAME_PREFIXES)} {self.rng.choice(NAME_WORDS)}"
        return (
            f"{self.rng.choice(NAME_PREFIXES)} {self.rng.choice(NAME_WORDS)} "
            f"{self.rng.choice(NAME_SUFFIXES)}"
        )

    def seed_charities(self, domains, locations):
        total = COUNTS["charities"]
        charities = []
        for _ in range(total):
            charity = f.CharityFactory(
                name=self.charity_name(),
                image=self.rng.choice([None, None, "https://placehold.co/600x400.png"]),
            )
            for domain in self.rng.sample(domains, self.rng.randint(1, 3)):
                f.CharityDomainFactory(charity=charity, domain=domain)
            for location in self.rng.sample(locations, self.rng.randint(1, 2)):
                f.CharityLocationFactory(charity=charity, location=location)
            slug = charity.name.lower().replace(" ", "")
            for kind in self.rng.sample(list(Link.Kind), self.rng.randint(1, 3)):
                page = kind.value.removeprefix("website_")
                f.LinkFactory(charity=charity, kind=kind, url=f"https://{slug}.example.org/{page}")
            charities.append(charity)

        # Spread creation dates over the past two years.
        for charity in charities:
            charity.created = self.now - timedelta(days=self.rng.randint(0, 730))
        Charity.objects.bulk_update(charities, ["created"])

        pending = COUNTS["pending_charities"]
        rejected = COUNTS["rejected_charities"]
        return {
            "approved": charities[: total - pending - rejected],
            "pending": charities[total - pending - rejected : total - rejected],
            "rejected": charities[total - rejected :],
        }

    def seed_approvals(self, charities, users):
        Status = ApprovalRequest.Status
        owners = users["owners"]
        # Every charity has a NEW_CHARITY request; its status decides visibility (§5.3).
        for status, group in [
            (Status.APPROVED, charities["approved"]),
            (Status.PENDING, charities["pending"]),
            (Status.REJECTED, charities["rejected"]),
        ]:
            for charity in group:
                decided = status != Status.PENDING
                f.NewCharityRequestFactory(
                    charity=charity,
                    approval_request__submitted_by=self.rng.choice(owners),
                    approval_request__status=status,
                    approval_request__decided_by=self.admin if decided else None,
                    approval_request__decided_at=self.now if decided else None,
                )

        # Each owner owns one or two approved charities.
        approved = charities["approved"]
        for owner in owners:
            for charity in self.rng.sample(approved, self.rng.randint(1, 2)):
                f.CharityOwnerFactory(user=owner, charity=charity)

        for member in users["members"][:5]:
            f.OwnerClaimRequestFactory(
                charity=self.rng.choice(approved), approval_request__submitted_by=member
            )
        for owner in owners[:5]:
            f.EditRequestFactory(
                charity=owner.owned_charities.first().charity,
                approval_request__submitted_by=owner,
            )
        for user in users["pending_rabbis"]:
            f.ApprovalRequestFactory(submitted_by=user, kind=ApprovalRequest.Kind.RABBI)

    def seed_reviews_and_haskamas(self, approved, users):
        for charity in approved:
            reviewers = self.rng.sample(users["members"], self.rng.randint(0, 8))
            for author in reviewers:
                f.ReviewFactory(
                    charity=charity,
                    author=author,
                    rating=self.rng.choices([1, 2, 3, 4, 5], weights=[1, 1, 3, 6, 8])[0],
                )
        for rabbi in users["rabbis"]:
            for charity in self.rng.sample(approved, 15):
                verdict = (
                    Haskama.Verdict.APPROVE
                    if self.rng.random() < 0.9
                    else Haskama.Verdict.DISAPPROVE
                )
                f.HaskamaFactory(rabbi_user=rabbi, charity=charity, verdict=verdict)

    def seed_events(self, approved, members):
        links_by_charity = {}
        for link in Link.objects.filter(charity__in=approved):
            links_by_charity.setdefault(link.charity_id, []).append(link)
        # Weight popularity so "most visited" and "trending" have something to show.
        weights = [self.rng.paretovariate(1.2) for _ in approved]
        events = []
        for _ in range(COUNTS["events"]):
            charity = self.rng.choices(approved, weights=weights)[0]
            user = self.rng.choice(members) if self.rng.random() < 0.7 else None
            roll = self.rng.random()
            if roll < 0.75:
                action, link = Event.Action.VIEW, None
            elif roll < 0.98:
                action = Event.Action.LINK_CLICK
                link = self.rng.choice(links_by_charity[charity.id])
            else:
                action, link, user = Event.Action.CHARITY_UPDATED, None, None
            events.append(Event(charity=charity, user=user, link=link, action=action))
        events = Event.objects.bulk_create(events)
        # auto_now_add stamps "now" on insert; spread events over the last 90 days instead.
        for event in events:
            event.created = self.now - timedelta(minutes=self.rng.randint(0, 90 * 24 * 60))
        Event.objects.bulk_update(events, ["created"], batch_size=1000)

    def seed_tickets_and_transactions(self, approved, users):
        for _ in range(COUNTS["tickets"]):
            kind = self.rng.choice(list(Ticket.Kind))
            f.TicketFactory(
                submitted_by=self.rng.choice(users["members"]),
                kind=kind,
                charity=self.rng.choice(approved) if kind == Ticket.Kind.REPORT else None,
            )
        for member in users["members"][: COUNTS["maaser_members"]]:
            for month in range(1, 7):
                income = Decimal(self.rng.randint(3000, 9000))
                f.TransactionFactory(
                    user=member,
                    type=Transaction.Type.INCOME,
                    amount=income,
                    date=self.now.date().replace(day=1) - timedelta(days=30 * month),
                )
                f.TransactionFactory(
                    user=member,
                    type=Transaction.Type.DONATION,
                    amount=(income / 10).quantize(Decimal("1.00")),
                    charity=self.rng.choice(approved),
                    date=self.now.date().replace(day=1) - timedelta(days=30 * month - 5),
                )

    def summary(self, admin_password):
        counts = ", ".join(
            f"{model._meta.verbose_name_plural}: {model.objects.count()}"
            for model in [Charity, User, Review, Haskama, Event, ApprovalRequest]
        )
        return (
            f"Seeded. {counts}.\n"
            f"Log in at /django-admin/ as admin / {admin_password}. "
            f"Every other user (member1, owner1, rabbi1, supporter1, ...) has password "
            f"'{DEFAULT_PASSWORD}'."
        )
