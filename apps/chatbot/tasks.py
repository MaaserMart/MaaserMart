"""The Celery task that asks the model (§6.3.2, D-076)."""

from __future__ import annotations

import logging

from celery import shared_task

from . import jobs
from .lookups import functions_for
from .loop import converse
from .prompt import system_prompt
from .providers import Message, ProviderConfigError, ProviderError, get_provider

logger = logging.getLogger(__name__)

# Timeouts, rate limits and the vendor's 5xx get two more tries before the
# visitor is told "couldn't get an answer" (§6.3).
MAX_RETRIES = 2


@shared_task(bind=True, max_retries=MAX_RETRIES, ignore_result=True)
def answer_question(self, job_id: str, user_id: int, history: list[list[str]]) -> None:
    """Answer the last user turn of `history` ([role, text] pairs) into the job."""
    messages = [Message("system", system_prompt())]
    messages += [Message(role, text) for role, text in history]
    try:
        provider = get_provider()
        outcome = converse(provider, messages, functions_for(user_id))
    except ProviderConfigError as exc:
        logger.error("Chatbot is not configured: %s", exc)
        jobs.fail(job_id)
        return
    except ProviderError as exc:
        if exc.retryable and self.request.retries < MAX_RETRIES:
            raise self.retry(countdown=2 ** (self.request.retries + 1)) from None
        logger.error("Chatbot could not get an answer for job %s: %s", job_id, exc)
        jobs.fail(job_id)
        return
    if not outcome.text:
        logger.error("Chatbot model gave an empty answer for job %s", job_id)
        jobs.fail(job_id)
        return
    jobs.answer(job_id, outcome.text)
    # §3.4.2 logs chatbot use: who, how much, which lookups. Never the text.
    logger.info(
        "Chatbot use: user=%s provider=%s rounds=%s tools=%s tokens=%s+%s",
        user_id,
        provider.name,
        outcome.rounds,
        ",".join(outcome.tools_called) or "-",
        outcome.prompt_tokens,
        outcome.completion_tokens,
    )
