"""Tables owned by accounts (design doc §5.2.1-5.2.4)."""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """§5.2.1 USER. Admin status is Django's is_superuser (§5.2.2)."""

    email = models.EmailField()

    class Meta:
        constraints = [
            # Case-insensitive, so "A@x.com" and "a@x.com" can't be two accounts.
            models.UniqueConstraint(Lower("email"), name="user_email_ci_uniq"),
            models.UniqueConstraint(Lower("username"), name="user_username_ci_uniq"),
        ]


class RoleAssignment(models.Model):
    """§5.2.2 ROLE_ASSIGNMENT: which roles a user holds."""

    class Role(models.TextChoices):
        RABBI = "rabbi", "Rabbi"
        TECHNICAL_SUPPORTER = "technical_supporter", "Technical supporter"
        MEMBER = "member", "Member"
        CHARITY_OWNER = "charity_owner", "Charity owner"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.CharField(max_length=32, choices=Role.choices)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="role_assignment_user_role_uniq"),
        ]

    def __str__(self):
        return f"{self.user} as {self.role}"


class RabbiProfile(models.Model):
    """§5.2.3 RABBI_PROFILE: a rabbi's public display name and title."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="rabbi_profile")
    title = models.CharField(max_length=100, null=True, blank=True)
    display_name = models.CharField(max_length=150)

    def __str__(self):
        return self.display_name


class CharityOwner(models.Model):
    """§5.2.4 CHARITY_OWNER: which users own which charities."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_charities")
    charity = models.ForeignKey("charities.Charity", on_delete=models.CASCADE, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "charity"], name="charity_owner_user_charity_uniq"
            ),
        ]

    def __str__(self):
        return f"{self.user} owns {self.charity_id}"
