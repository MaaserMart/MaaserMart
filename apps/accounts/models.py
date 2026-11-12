from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """The custom user model (AUTH_USER_MODEL). Fields from §5.2.1 arrive in step 2."""
