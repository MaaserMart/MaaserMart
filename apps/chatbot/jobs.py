"""Where a question waits for its answer, and the daily usage count (D-076).

Celery's SQS transport has no result backend (design doc concurrency decision),
so a job's state lives in Django's default cache, which is database-backed and
shared by the web processes and the worker. No model and no migration: the
chatbot owns no models (§6.1). A job outlives any answer a visitor waits for, and
then expires.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass

from django.core.cache import caches
from django.utils import timezone

PENDING = "pending"
ANSWERED = "answered"
FAILED = "failed"

JOB_SECONDS = 60 * 60
DAY_SECONDS = 24 * 60 * 60


def _cache():
    return caches["default"]


@dataclass
class Job:
    user_id: int
    question: str
    state: str = PENDING
    answer: str = ""
    created: float = 0.0


def _key(job_id: str) -> str:
    return f"chatbot:job:{job_id}"


def create(user_id: int, question: str) -> str:
    job_id = uuid.uuid4().hex
    _cache().set(_key(job_id), asdict(Job(user_id, question, created=time.time())), JOB_SECONDS)
    return job_id


def get(job_id: str) -> Job | None:
    raw = _cache().get(_key(job_id)) if job_id else None
    return Job(**raw) if raw else None


def _settle(job_id: str, state: str, answer: str = "") -> None:
    job = get(job_id)
    if job is None:
        return
    job.state, job.answer = state, answer
    _cache().set(_key(job_id), asdict(job), JOB_SECONDS)


def answer(job_id: str, text: str) -> None:
    _settle(job_id, ANSWERED, text)


def fail(job_id: str) -> None:
    _settle(job_id, FAILED)


def delete(job_id: str) -> None:
    _cache().delete(_key(job_id))


def _usage_key(user_id: int) -> str:
    return f"chatbot:uses:{user_id}:{timezone.now().date().isoformat()}"


def uses_today(user_id: int) -> int:
    return _cache().get(_usage_key(user_id), 0)


def count_use(user_id: int) -> int:
    """Add one question to today's (UTC) count and return the new total."""
    key = _usage_key(user_id)
    _cache().add(key, 0, DAY_SECONDS)
    try:
        return _cache().incr(key)
    except ValueError:  # expired between add and incr
        _cache().set(key, 1, DAY_SECONDS)
        return 1
