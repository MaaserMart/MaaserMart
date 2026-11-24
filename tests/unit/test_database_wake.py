"""The wake gate where it meets a request (D-070).

The interesting cases are the two the user named: a stopped instance must be
started instead of queried, and a query that finds the database gone must be the
thing that starts it — without turning a real database fault into a friendly
"still waking up" page that never ends.
"""

import pytest
from django.db import OperationalError
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import path

from apps.support.middleware import DatabaseWakeMiddleware
from apps.support.rds import RdsInstance
from config.urls import urlpatterns as project_urls
from tests.support.rds import FakeRds


@pytest.fixture
def build(settings):
    """A middleware wired to a fake client, so no test reaches AWS."""
    settings.RDS_INSTANCE_ID = "maasermart-db"
    settings.AWS_REGION = "us-east-2"

    def build(get_response, fake):
        middleware = DatabaseWakeMiddleware(get_response)
        middleware.instance = RdsInstance("maasermart-db", region="us-east-2", client=fake)
        return middleware

    return build


def page(request):
    return HttpResponse("the listing")


def failing(request):
    raise OperationalError("server closed the connection unexpectedly")


def test_an_available_database_serves_the_page(build):
    response = build(page, FakeRds("available"))(RequestFactory().get("/charity/"))

    assert response.status_code == 200
    assert response.content == b"the listing"


def test_a_stopped_database_is_started_instead_of_queried(build):
    fake = FakeRds("stopped")

    response = build(failing, fake)(RequestFactory().get("/charity/"))

    assert response.status_code == 503
    assert fake.starts == 1


def test_the_waiting_page_explains_itself_and_reloads(build):
    response = build(page, FakeRds("stopped"))(RequestFactory().get("/charity/"))
    body = response.content.decode()

    assert response.headers["Retry-After"] == "15"
    assert response.headers["Cache-Control"] == "no-store"
    assert "waking up" in body
    assert '<meta http-equiv="refresh" content="15">' in body
    # It extends base.html like every page (D-060), so it is not a bare string.
    assert "<nav" in body


@pytest.mark.parametrize("status", ["starting", "stopping"])
def test_a_waking_database_is_not_started_twice(build, status):
    fake = FakeRds(status)

    response = build(page, fake)(RequestFactory().get("/charity/"))

    assert response.status_code == 503
    assert fake.starts == 0


def gone(request):
    raise OperationalError("server closed the connection unexpectedly")


urlpatterns = [path("gone/", gone), *project_urls]


@pytest.fixture
def stack(settings, monkeypatch):
    """Django's real request handling with the gate installed.

    The cases where a query fails must go through it: Django turns a view's
    exception into a 500 at every middleware layer, so calling the middleware
    directly would pass a test that production fails.
    """
    settings.RDS_INSTANCE_ID = "maasermart-db"
    settings.MIDDLEWARE = [
        settings.MIDDLEWARE[0],
        "apps.support.middleware.DatabaseWakeMiddleware",
        *settings.MIDDLEWARE[1:],
    ]
    settings.ROOT_URLCONF = __name__

    def stack(fake):
        monkeypatch.setattr(
            "apps.support.middleware.RdsInstance",
            lambda identifier, **kwargs: RdsInstance(identifier, **{**kwargs, "client": fake}),
        )
        return Client(raise_request_exception=False)

    return stack


@pytest.mark.django_db
def test_a_query_that_finds_the_database_gone_starts_it(stack):
    """The cached check passed, the query failed, the fresh answer is 'stopped'."""
    fake = FakeRds()
    fake.statuses = ["available", "stopped"]

    response = stack(fake).get("/gone/")

    assert response.status_code == 503
    assert fake.starts == 1


@pytest.mark.django_db
def test_a_real_database_error_is_not_hidden_behind_the_waiting_page(stack):
    """Bad credentials, no disk, too many connections: starting fixes none of them."""
    fake = FakeRds("available")

    response = stack(fake).get("/gone/")

    assert response.status_code == 500
    assert fake.starts == 0


def test_static_files_are_served_without_asking_aws(build):
    """Otherwise the waiting page would arrive with no stylesheet at all."""
    fake = FakeRds("stopped")

    response = build(page, fake)(RequestFactory().get("/static/css/site.css"))

    assert response.status_code == 200
    assert fake.describes == 0
