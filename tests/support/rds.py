"""Fakes for the AWS calls the wake gate makes (D-070)."""

from __future__ import annotations

from botocore.exceptions import ClientError


class FakeRds:
    """Stands in for `boto3.client("rds")` in the gate's tests.

    `statuses` is a queue: each `describe_db_instances` returns the first entry
    and drops it, so a test can describe one state before a query and a
    different one after it. The last entry sticks.
    """

    def __init__(self, status: str = "available") -> None:
        self.statuses = [status]
        self.describes = 0
        self.starts = 0
        self.describe_error: Exception | None = None
        self.start_error: Exception | None = None

    @property
    def status(self) -> str:
        return self.statuses[0]

    def describe_db_instances(self, **kwargs):
        self.describes += 1
        if self.describe_error is not None:
            raise self.describe_error
        status = self.statuses[0]
        if len(self.statuses) > 1:
            self.statuses.pop(0)
        return {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": kwargs["DBInstanceIdentifier"],
                    "DBInstanceStatus": status,
                }
            ]
        }

    def start_db_instance(self, **kwargs):
        self.starts += 1
        if self.start_error is not None:
            raise self.start_error
        self.statuses = ["starting"]


class FakeCache:
    """A dict with the three `django.core.cache` calls the gate makes."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ttl):
        self.data[key] = value
        self.ttls[key] = ttl

    def delete(self, key):
        self.data.pop(key, None)
        self.ttls.pop(key, None)


def client_error(code: str, operation: str = "DescribeDBInstances") -> ClientError:
    """The ClientError boto3 raises for an API-level failure."""
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)
