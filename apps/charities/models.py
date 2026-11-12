"""Tables owned by charities (design doc §5.2.9-5.2.16)."""

from django.conf import settings
from django.db import models


class Location(models.Model):
    """§5.2.10 LOCATION."""

    name = models.CharField(max_length=150)
    region = models.CharField(max_length=150)
    country = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "region", "country"], name="location_name_region_country_uniq"
            ),
        ]

    def __str__(self):
        return f"{self.name}, {self.region}, {self.country}"


class Domain(models.Model):
    """§5.2.11 DOMAIN: a cause area such as education or medical."""

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Charity(models.Model):
    """§5.2.9 CHARITY. Unapproved charities live here too; pending status is only in approvals."""

    name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=300, null=True, blank=True)
    # The doc marks description and image unique; held back pending a CEO decision.
    description = models.TextField(null=True, blank=True)
    image = models.CharField(max_length=500, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    domains = models.ManyToManyField(Domain, through="CharityDomain", related_name="charities")
    locations = models.ManyToManyField(
        Location, through="CharityLocation", related_name="charities"
    )

    class Meta:
        verbose_name_plural = "charities"

    def __str__(self):
        return self.name


class CharityDomain(models.Model):
    """§5.2.12 CHARITY_DOMAIN."""

    charity = models.ForeignKey(Charity, on_delete=models.CASCADE)
    domain = models.ForeignKey(Domain, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["charity", "domain"], name="charity_domain_uniq"),
        ]


class CharityLocation(models.Model):
    """§5.2.13 CHARITY_LOCATION."""

    charity = models.ForeignKey(Charity, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["charity", "location"], name="charity_location_uniq"),
        ]


class Link(models.Model):
    """§5.2.14 LINK: a charity's outbound links."""

    class Kind(models.TextChoices):
        WEBSITE_DONATE = "website_donate", "Donate page"
        WEBSITE_ABOUT = "website_about", "About page"
        WEBSITE_CONTACT = "website_contact", "Contact page"

    charity = models.ForeignKey(Charity, on_delete=models.CASCADE, related_name="links")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    url = models.URLField(max_length=500)

    def __str__(self):
        return f"{self.charity_id} {self.kind}"


class Review(models.Model):
    """§5.2.15 REVIEW. Index on charity_id (§5.2.20) is the FK index."""

    charity = models.ForeignKey(Charity, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"
            ),
        ]


class Haskama(models.Model):
    """§5.2.16 HASKAMA: a rabbi's endorsement. Index on charity_id (§5.2.20) is the FK index."""

    class Verdict(models.TextChoices):
        APPROVE = "approve", "Approve"
        DISAPPROVE = "disapprove", "Disapprove"

    rabbi_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="haskamas"
    )
    charity = models.ForeignKey(Charity, on_delete=models.CASCADE, related_name="haskamas")
    verdict = models.CharField(max_length=16, choices=Verdict.choices)
    importance = models.PositiveSmallIntegerField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(importance__isnull=True)
                | models.Q(importance__gte=1, importance__lte=10),
                name="haskama_importance_1_to_10",
            ),
            models.UniqueConstraint(
                fields=["rabbi_user", "charity"], name="haskama_rabbi_charity_uniq"
            ),
        ]
