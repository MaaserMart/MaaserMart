"""Login that ignores username case (D-032, D-YOSEF-accounts-login)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Value
from django.db.models.functions import Lower


class CaseInsensitiveModelBackend(ModelBackend):
    """ModelBackend, except "Yosef", "yosef" and "YOSEF" are the same username.

    The lookup is LOWER(username) = LOWER(%s), which matches the
    user_username_ci_uniq index. Django's iexact compiles to UPPER(...) on
    PostgreSQL and would scan the whole table.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        if username is None:
            username = kwargs.get(user_model.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = user_model._default_manager.alias(username_lower=Lower("username")).get(
                username_lower=Lower(Value(username))
            )
        except user_model.DoesNotExist:
            # Hash anyway, so a wrong username takes as long as a wrong password
            # and response time doesn't reveal which usernames exist.
            user_model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
