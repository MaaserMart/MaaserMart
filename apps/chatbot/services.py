"""Public interface of the chatbot app.

Other apps call only the functions defined here, never this app's models.
§6.1: the chatbot exposes `enqueue_question(…)` and `poll_status(task_id)`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from django.conf import settings

from . import jobs

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000


class ChatbotError(Exception):
    """A question that could not be put on the queue. The message is for the visitor."""


class LimitReached(ChatbotError):
    def __init__(self):
        super().__init__("You've reached the chatbot limit")


class SubmitFailed(ChatbotError):
    def __init__(self):
        super().__init__("Could not submit, try again")


@dataclass(frozen=True)
class Status:
    """Where a question stands: pending, answered (with `answer`) or failed."""

    state: str
    question: str
    answer: str = ""

    @property
    def done(self) -> bool:
        return self.state != jobs.PENDING


def clean_question(text: str) -> str:
    return " ".join((text or "").split())[:MAX_QUESTION_CHARS]


def enqueue_question(user_id: int, question: str, history: Sequence[tuple[str, str]] = ()) -> str:
    """Put a question on the queue and return the task id to poll.

    `history` is the earlier (question, answer) pairs of this conversation, so
    the model can follow up. Raises LimitReached past the daily cap and
    SubmitFailed when the queue cannot take the job (§6.3).
    """
    from .tasks import answer_question  # the task module imports the providers

    if jobs.uses_today(user_id) >= settings.CHATBOT_DAILY_LIMIT:
        logger.info("Chatbot limit reached for user %s", user_id)
        raise LimitReached()
    turns: list[list[str]] = []
    for asked, answered in history:
        turns += [["user", asked], ["assistant", answered]]
    turns.append(["user", question])
    job_id = jobs.create(user_id, question)
    try:
        answer_question.delay(job_id, user_id, turns)
    except Exception:
        logger.exception("Chatbot question could not be queued")
        jobs.delete(job_id)
        raise SubmitFailed() from None
    jobs.count_use(user_id)
    return job_id


def poll_status(user_id: int, task_id: str) -> Status | None:
    """The question's state, or None for an unknown task or another user's (§6.3: 404).

    A job still pending after CHATBOT_ANSWER_SECONDS is reported failed, so a
    stopped worker ends in "try again" instead of polling forever.
    """
    job = jobs.get(task_id)
    if job is None or job.user_id != user_id:
        logger.warning("Chatbot status asked for an unknown or foreign task by user %s", user_id)
        return None
    if job.state == jobs.PENDING and time.time() - job.created > settings.CHATBOT_ANSWER_SECONDS:
        logger.error("Chatbot job %s got no answer in time; is the worker running?", task_id)
        jobs.fail(task_id)
        job.state = jobs.FAILED
    return Status(state=job.state, question=job.question, answer=job.answer)
