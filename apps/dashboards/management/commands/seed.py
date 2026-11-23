"""Fill an empty local database from a small directory of real charities.

Dev tooling only (see CLAUDE.md): it builds every app's rows through the shared
factories in tests/factories. Names, causes and links come from REAL_CHARITIES;
users and events are still generated, but reviews and haskamas are not. It
refuses to run unless DEBUG is on and every app table is empty (D-030). The
tests package is imported lazily (S2): seeding is the only runtime code that needs it, so a
production install can leave the package out and never pay for it.
"""

import random
import secrets
import uuid
from datetime import timedelta
from typing import NamedTuple

import factory.random
from django.apps import apps as django_apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleAssignment, User
from apps.approvals.models import ApprovalRequest
from apps.charities.models import Charity, Link
from apps.charities.services import publish_charity
from apps.events.models import Event

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
    ("Far Rockaway", "New York", "USA"),
    ("Jackson", "New Jersey", "USA"),
    ("New York", "New York", "USA"),
    ("Silver Spring", "Maryland", "USA"),
    ("Suffern", "New York", "USA"),
]


class SeedCharity(NamedTuple):
    name: str
    tagline: str
    about: str
    donate: str
    domains: tuple[str, ...]
    location: str


# Real organizations and their real sites, checked 2026-11-22. This is dev seed
# data, not a vetted list to give donors: names, causes, links and listed
# locations are taken from each organization's own site. Users and events are
# generated; reviews and haskamas are deliberately not, since they would be
# fake endorsements of real organizations.
REAL_CHARITIES = (
    # name, tagline, about URL, donate URL, domains, location
    SeedCharity(
        "Colel Chabad",
        "Israel's oldest continuous charity, serving the needy since 1788.",
        "https://colelchabad.org/",
        "https://colelchabad.org/donate-2/",
        ("Orphans and Widows", "Food Security", "Israel"),
        "Brooklyn",
    ),
    SeedCharity(
        "Rabbi Meir Baal Haness Charities",
        "Kollel Ahavas Yisroel Vyerushalaim: aid for scholars, brides, widows and orphans.",
        "https://rmbhcharities.com/about/",
        "https://rmbhcharities.com/main-page-donation/",
        ("Hachnasas Kallah", "Orphans and Widows", "Poverty Relief", "Torah Study", "Israel"),
        "Brooklyn",
    ),
    SeedCharity(
        "American Friends of Yad Eliezer",
        "Food, clothing and relief for families across Israel.",
        "https://www.af-ye.org/",
        "https://www.af-ye.org/",
        ("Food Security", "Poverty Relief", "Israel"),
        "Jackson",
    ),
    SeedCharity(
        "Tomchei Shabbos",
        "Kosher pantry staples for thousands of families in New Jersey.",
        "https://tomchei.org/",
        "https://tomchei.org/donate",
        ("Food Security", "Poverty Relief"),
        "Lakewood",
    ),
    SeedCharity(
        "Tomchei Shabbos of Toronto",
        "Shabbos food boxes for families across the Toronto area.",
        "https://rfro.org/",
        "https://rfro.org/donate/",
        ("Food Security",),
        "Toronto",
    ),
    SeedCharity(
        "Tomchei Shabbos of the Five Towns and Far Rockaway",
        "Weekly food packages for families in the Five Towns and Rockaways.",
        "http://tomchei5tfr.org/",
        "http://tomchei5tfr.org/",
        ("Food Security",),
        "Far Rockaway",
    ),
    SeedCharity(
        "Bikur Cholim of Los Angeles",
        "Medical crisis funds, therapy and housing for patients and families.",
        "https://www.bikurcholim.net/",
        "https://www.bikurcholim.net/donate",
        ("Bikur Cholim", "Medical", "Poverty Relief"),
        "Los Angeles",
    ),
    SeedCharity(
        "Bikur Cholim Chesed Organization",
        "Patient advocacy, food pantries and medical equipment loans in Brooklyn.",
        "https://bicco.org/",
        "https://bicco.org/donate/",
        ("Bikur Cholim", "Medical", "Elderly Care"),
        "Brooklyn",
    ),
    SeedCharity(
        "Ezras Torah",
        "Relief for needy Torah families in Israel since 1915.",
        "https://ezrastorah.org/",
        "https://ezrastorah.org/choose_content.php?action=donation",
        ("Poverty Relief", "Hachnasas Kallah", "Orphans and Widows", "Medical", "Israel"),
        "Suffern",
    ),
    SeedCharity(
        "Ezras Yisroel",
        "Grants and loans for families facing illness, weddings and holidays.",
        "https://www.ezrasyisroel.org/about.php",
        "https://www.ezrasyisroel.org/donate",
        ("Poverty Relief", "Hachnasas Kallah", "Orphans and Widows"),
        "Brooklyn",
    ),
    SeedCharity(
        "Torah Umesorah",
        "Supporting Torah education in yeshivos and day schools nationwide.",
        "https://www.torahumesorah.org/",
        "https://www.torahumesorah.org/donate",
        ("Education", "Torah Study"),
        "Brooklyn",
    ),
    SeedCharity(
        "Yad L'Achim",
        "Rescue and rehabilitation for women and children in Israel.",
        "https://yadlachim.org/",
        "https://support.yadlachim.org/",
        ("Israel", "Orphans and Widows"),
        "Bnei Brak",
    ),
    SeedCharity(
        "Orthodox Union",
        "Strengthening Orthodox communities, schools and institutions.",
        "https://www.ou.org/",
        "https://www.ou.org/donate/",
        ("Education", "Torah Study", "Special Needs", "Israel"),
        "New York",
    ),
    SeedCharity(
        "Agudath Israel of America",
        "Advocacy and services for Orthodox Jews across the United States.",
        "https://agudah.org/about",
        "https://agudah.org/donate-now/",
        ("Education", "Torah Study", "Special Needs", "Elderly Care", "Poverty Relief"),
        "New York",
    ),
    SeedCharity(
        "Agudath Israel of Illinois",
        "Community programs and assistance for Jewish Chicago.",
        "https://www.agudahil.org/",
        "https://www.agudahil.org/donate",
        ("Education", "Torah Study", "Food Security"),
        "Chicago",
    ),
    SeedCharity(
        "Torah Community Fund",
        "Sustaining Torah life and families in communities across Israel.",
        "https://www.torahcommunityfund.com/",
        "https://www.torahcommunityfund.com/",
        ("Torah Study", "Israel", "Poverty Relief"),
        "Passaic",
    ),
    SeedCharity(
        "Chabad-Lubavitch",
        "A global network of social services, education and relief.",
        "https://www.lubavitch.com/",
        "https://www.lubavitch.com/donate/",
        ("Torah Study", "Education", "Israel"),
        "Brooklyn",
    ),
    SeedCharity(
        "Tomchei Yosef Tzvi",
        "Research-led aid for families in need in Eretz Yisroel.",
        "http://tomcheiyt.org/",
        "http://tomcheiyt.org/",
        ("Poverty Relief", "Israel"),
        "Chicago",
    ),
    SeedCharity(
        "Yad Yehuda of Greater Washington",
        "Hachnasas kallah and support for families near Washington.",
        "https://yadyehuda.org/",
        "https://yadyehuda.org/donate/",
        ("Hachnasas Kallah", "Orphans and Widows"),
        "Silver Spring",
    ),
    SeedCharity(
        "American Friends of Magen David Adom",
        "Support for Israel's emergency medical and ambulance service.",
        "https://afmda.org/",
        "https://afmda.org/donate/",
        ("Medical", "Disaster Relief", "Israel"),
        "New York",
    ),
    SeedCharity(
        "Aish",
        "Jewish learning and outreach for people at every level.",
        "https://aish.com/",
        "https://aish.com/",
        ("Torah Study", "Education"),
        "Jerusalem",
    ),
)

# Dev images come from the SVGs already in the repo (D-043, superseding D-024).
# Repo-relative paths, so the template serves them through {% static %}.
IMAGE_PATHS = [f"charities/img/charity-{index:02d}.svg" for index in range(1, 13)]
PENDING = 3
APPROVED = len(REAL_CHARITIES) - PENDING
# Requests submitted together share one batch (§5.2.5), and the admin queue
# decides a whole batch at once (§7.1.6). Batching the seed the same way gives
# that screen something real to work on in dev (D-055, superseding D-006's own
# single-request batches).
BATCH_SIZE = 10
MEMBERS, OWNERS, RABBIS = 100, 30, 10
EVENTS = 8000


class Command(BaseCommand):
    help = "Seed an empty database with real charities plus generated users and events."

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
        # SEC4: the admin account must not come with the public password 'admin'. That
        # is safe only on a throwaway local box, and the DB check above already refuses
        # anything that might be real. Use a random password, or an explicit one.
        admin_password = settings.ADMIN_SEED_PASSWORD or secrets.token_urlsafe(18)
        self.rng = random.Random(613)
        factory.random.reseed_random(613)
        self.now = timezone.now()
        with transaction.atomic():
            self.seed(admin_password)
        from tests.factories.accounts import DEFAULT_PASSWORD

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Charity.objects.count()} charities, {User.objects.count()} users, "
                f"{Event.objects.count()} events. Log in as admin / {admin_password}; every other "
                f"user (member1, owner1, rabbi1) has password '{DEFAULT_PASSWORD}'."
            )
        )

    def seed(self, admin_password):
        from tests import factories as f

        admin = User.objects.create_superuser("admin", "admin@example.com", admin_password)
        domains = [f.DomainFactory(name=name) for name in DOMAINS]
        locations = [f.LocationFactory(name=n, region=r, country=c) for n, r, c in LOCATIONS]
        domains_by_name = {domain.name: domain for domain in domains}
        location_by_name = {location.name: location for location in locations}

        members = self.users("member", MEMBERS, Role.MEMBER)
        owners = self.users("owner", OWNERS, Role.CHARITY_OWNER)
        rabbis = self.users("rabbi", RABBIS, Role.RABBI)
        for rabbi in rabbis:
            f.RabbiProfileFactory(user=rabbi)

        # One batch id per group of requests, so the queue can decide several at once.
        batch_ids = [uuid.uuid4() for _ in range(-(-(APPROVED + PENDING) // BATCH_SIZE))]
        charities = []
        for i, seed_charity in enumerate(REAL_CHARITIES):
            approved = i < APPROVED
            charity = f.CharityFactory(
                name=seed_charity.name,
                tagline=seed_charity.tagline,
                image=IMAGE_PATHS[i % len(IMAGE_PATHS)],
            )
            for domain_name in seed_charity.domains:
                f.CharityDomainFactory(charity=charity, domain=domains_by_name[domain_name])
            f.CharityLocationFactory(
                charity=charity, location=location_by_name[seed_charity.location]
            )
            for kind, url in (
                (Link.Kind.WEBSITE_DONATE, seed_charity.donate),
                (Link.Kind.WEBSITE_ABOUT, seed_charity.about),
                (Link.Kind.WEBSITE_CONTACT, seed_charity.about),
            ):
                f.LinkFactory(charity=charity, kind=kind, url=url)
            f.NewCharityRequestFactory(
                charity=charity,
                approval_request__submitted_by=self.rng.choice(owners),
                approval_request__status=Status.APPROVED if approved else Status.PENDING,
                approval_request__decided_by=admin if approved else None,
                approval_request__batch_id=batch_ids[i // BATCH_SIZE],
            )
            if approved:
                # Through the service, as approvals will do, so it records its event (D-038).
                publish_charity(charity.id, by_user_id=admin.id)
            charities.append(charity)
        approved = charities[:APPROVED]

        for owner in owners:
            f.CharityOwnerFactory(user=owner, charity=self.rng.choice(approved))
        # No reviews or haskamas: fabricating either would be a fake endorsement
        # of a real organization named above.
        self.events(approved, members)

    def users(self, prefix, count, role):
        from tests import factories as f

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
