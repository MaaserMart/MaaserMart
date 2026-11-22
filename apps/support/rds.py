"""Wake the RDS instance the database lives on, through the AWS API (D-070).

The deployed database is stopped whenever nobody is using it, because a running
RDS instance is the bill (§4.9). That means a request can arrive when there is
no database to connect to, and two questions have to be answerable without one:
is the instance up, and if not, start it.

Both go through the AWS API (boto3), never a shell-out to `aws rds ...`: the
caller is a Gunicorn worker rather than a person, and a subprocess per request
would be an outage of its own.

Nothing here waits for the instance to come up except `wait()`, which is for
commands a person runs (D-070). A start takes minutes, so a request that waited
would hold a worker far longer than any client is willing to hold the
connection.
"""

from __future__ import annotations

import enum
import logging
import time
from collections.abc import Callable

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Statuses that mean "there is nothing to connect to". Every other status
# (`available`, `backing-up`, `modifying`, `storage-optimization`, and whatever
# RDS adds next) accepts connections, so the gate lets the request through and
# the query itself is the judge. Listing the healthy statuses instead would turn
# an unfamiliar one into an outage.
STOPPED_STATUSES = frozenset({"stopped"})
WAKING_STATUSES = frozenset({"starting", "stopping"})

# A wrong instance identifier is a configuration error an operator has to fix,
# so it is loud rather than another "waking up" page.
_NOT_FOUND_CODES = frozenset({"DBInstanceNotFound", "DBInstanceNotFoundFault"})

# `start_db_instance` on an instance another caller has just started. Both
# callers wanted the same thing and one of them has already achieved it.
_ALREADY_STARTING_CODES = frozenset({"InvalidDBInstanceState", "InvalidDBInstanceStateFault"})


class DatabaseState(enum.Enum):
    """What the gate needs to know about the instance."""

    AVAILABLE = "available"
    STOPPED = "stopped"
    WAKING = "waking"


class RdsConfigurationError(RuntimeError):
    """The instance named in the settings does not exist in that account."""


def _error_code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "")


def _state_of(status: str) -> DatabaseState:
    if status in STOPPED_STATUSES:
        return DatabaseState.STOPPED
    if status in WAKING_STATUSES:
        return DatabaseState.WAKING
    return DatabaseState.AVAILABLE


class RdsInstance:
    """One RDS instance, and the last answer the AWS API gave about it.

    The answer is cached: `available` for a minute, because a database that is
    up stays up, and anything else for a few seconds, so a page polling during a
    start notices the change instead of sitting on a stale answer.
    """

    def __init__(
        self,
        identifier: str,
        *,
        region: str | None = None,
        available_ttl: int = 60,
        waking_ttl: int = 10,
        client: object | None = None,
    ) -> None:
        if not identifier:
            raise ValueError("An RDS instance needs an identifier; set RDS_INSTANCE_ID.")
        self.identifier = identifier
        self.region = region or None
        self.available_ttl = available_ttl
        self.waking_ttl = waking_ttl
        self._client = client

    def __str__(self) -> str:
        return self.identifier

    @property
    def client(self):
        """The boto3 client, created on first use (tests pass their own)."""
        if self._client is None:
            # A status check that hangs is a request that hangs, and botocore's
            # default read timeout is 60 seconds.
            self._client = boto3.Session().client(
                "rds",
                region_name=self.region,
                config=Config(
                    connect_timeout=2,
                    read_timeout=4,
                    retries={"max_attempts": 2},
                ),
            )
        return self._client

    @property
    def _cache_key(self) -> str:
        return f"rds-state:{self.identifier}"

    def _ttl_for(self, state: DatabaseState) -> int:
        return self.available_ttl if state is DatabaseState.AVAILABLE else self.waking_ttl

    def state(self) -> DatabaseState:
        """The instance's state, from the cache when it has an answer."""
        cached = cache.get(self._cache_key)
        if cached is not None:
            return DatabaseState(cached)
        return self.refresh()

    def refresh(self, *, strict: bool = False) -> DatabaseState:
        """Ask the AWS API now, and remember the answer.

        An AWS problem is not evidence that the database is down: credentials,
        throttling and a bad endpoint all say nothing about the instance. Those
        fail open and are logged, so the query decides — failing closed would
        turn an AWS hiccup into an outage of its own.

        `strict=True` re-raises instead, and exists for `wake_db`: an operator
        running it is asking *whether* the instance is up, so an unreachable
        AWS API has to be reported rather than guessed over. A request has a
        query to fall back on; a person reading the command's output does not.
        """
        try:
            described = self.client.describe_db_instances(DBInstanceIdentifier=self.identifier)
        except ClientError as exc:
            code = _error_code(exc)
            if code in _NOT_FOUND_CODES:
                raise RdsConfigurationError(
                    f"RDS instance {self.identifier!r} does not exist "
                    f"in {self.region or 'the default region'}."
                ) from exc
            if strict:
                raise
            logger.warning(
                "RDS status check for %s failed (%s); assuming it is reachable.",
                self.identifier,
                code,
            )
            return DatabaseState.AVAILABLE
        except BotoCoreError as exc:
            if strict:
                raise
            logger.warning(
                "RDS status check for %s failed (%s); assuming it is reachable.",
                self.identifier,
                exc,
            )
            return DatabaseState.AVAILABLE

        instances = described.get("DBInstances") or []
        if not instances:
            if strict:
                raise RdsConfigurationError(f"RDS described no instance for {self.identifier!r}.")
            logger.warning(
                "RDS described no instance for %s; assuming it is reachable.",
                self.identifier,
            )
            return DatabaseState.AVAILABLE

        state = _state_of(instances[0].get("DBInstanceStatus", ""))
        cache.set(self._cache_key, state.value, self._ttl_for(state))
        return state

    def wake(self) -> None:
        """Start the instance if it is stopped.

        Safe to call when someone else is already starting it: RDS answers that
        with `InvalidDBInstanceState`, which means the caller got what it asked
        for. Every other error is the operator's to see, so it propagates.
        """
        try:
            self.client.start_db_instance(DBInstanceIdentifier=self.identifier)
        except ClientError as exc:
            code = _error_code(exc)
            if code not in _ALREADY_STARTING_CODES:
                raise
            logger.info("RDS instance %s was already being started (%s).", self.identifier, code)
        else:
            logger.warning("Started stopped RDS instance %s.", self.identifier)
        # The cached "stopped" is wrong now, whatever the API said.
        cache.delete(self._cache_key)

    def wait(
        self,
        *,
        timeout: int = 900,
        interval: int = 10,
        on_state: Callable[[DatabaseState], None] | None = None,
        strict: bool = False,
    ) -> bool:
        """Poll until the instance is available, or give up. True if it is up.

        For commands, where blocking is fine because a person is watching it.
        """
        deadline = time.monotonic() + timeout
        seen: DatabaseState | None = None
        while True:
            state = self.refresh(strict=strict)
            if on_state is not None and state is not seen:
                on_state(state)
            seen = state
            if state is DatabaseState.AVAILABLE:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(interval)
