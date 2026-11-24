"""The tool-calling loop: the model decides what to look up, and we look it up (D-075).

This is the retrieval half of the chatbot's RAG. The model is given read-only
tools, each a thin wrapper over another app's `services.py`, never SQL and never
a model row. It asks for what it needs, sees the results, and answers. The loop
knows nothing about any vendor: it speaks only `providers.base`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from .providers import ChatProvider, Message, Tool, ToolCall

logger = logging.getLogger(__name__)

# A question needs a few lookups, not dozens; past this the model must answer.
MAX_ROUNDS = 4
# A tool result is cut here, so one broad lookup cannot fill the context window.
MAX_RESULT_CHARS = 6000


class ToolError(ValueError):
    """A lookup refused as asked (bad id, no match). The message goes to the model."""


@dataclass(frozen=True)
class ToolFunction:
    """A tool the model sees (`tool`) and the Python that answers it (`run`)."""

    tool: Tool
    run: Callable[..., Any]


@dataclass
class Outcome:
    """The answer, and what it took to get it (for logging chatbot use, §3.4.2)."""

    text: str
    rounds: int = 0
    tools_called: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _check_arguments(tool: Tool, arguments: dict[str, Any] | None) -> str | None:
    """Why these arguments cannot be passed, or None when they can."""
    if arguments is None:
        return "The arguments were not a JSON object."
    schema = tool.parameters or {}
    known = set(schema.get("properties", {}))
    unknown = sorted(set(arguments) - known)
    if unknown:
        return f"Unknown arguments: {', '.join(unknown)}."
    missing = sorted(set(schema.get("required", ())) - set(arguments))
    if missing:
        return f"Missing arguments: {', '.join(missing)}."
    return None


def _run_call(call: ToolCall, functions: dict[str, ToolFunction]) -> str:
    """Answer one tool call with a JSON string; never raises."""
    function = functions.get(call.name)
    if function is None:
        return json.dumps({"error": f"There is no tool called {call.name!r}."})
    problem = _check_arguments(function.tool, call.arguments)
    if problem:
        return json.dumps({"error": problem})
    try:
        result = function.run(**call.arguments)
    except ToolError as exc:
        return json.dumps({"error": str(exc)})
    except Exception:
        # A bug in a lookup should cost one answer, not the request.
        logger.exception("Chatbot tool %s failed", call.name)
        return json.dumps({"error": "That lookup failed."})
    text = json.dumps(result, cls=DjangoJSONEncoder, ensure_ascii=False)
    if len(text) > MAX_RESULT_CHARS:
        # Cut the *data*, not the JSON: a half-written object is not parseable, so
        # the model would get garbage instead of a result and a usable hint.
        text = json.dumps(
            {
                "error": "That result is too long to pass on.",
                "hint": "Ask for something narrower.",
                "preview": text[: MAX_RESULT_CHARS - 200],
            },
            ensure_ascii=False,
        )
    return text


def converse(
    provider: ChatProvider,
    messages: Sequence[Message],
    functions: Sequence[ToolFunction] = (),
    *,
    max_rounds: int = MAX_ROUNDS,
) -> Outcome:
    """Run the conversation until the model answers in words.

    Each round the model may ask for tools; their results are added and it is
    asked again. After `max_rounds` it is asked once more with no tools, so it
    must answer with what it has. ProviderError propagates to the caller, which
    decides whether to retry.
    """
    by_name = {f.tool.name: f for f in functions}
    tools = [f.tool for f in functions]
    history = list(messages)
    outcome = Outcome(text="")
    while True:
        offer = tools if outcome.rounds < max_rounds else []
        reply = provider.complete(history, offer)
        outcome.rounds += 1
        if reply.usage:
            outcome.prompt_tokens += reply.usage.prompt_tokens
            outcome.completion_tokens += reply.usage.completion_tokens
        if not reply.tool_calls or not offer:
            outcome.text = reply.text.strip()
            return outcome
        history.append(Message("assistant", reply.text, tool_calls=reply.tool_calls))
        for call in reply.tool_calls:
            outcome.tools_called.append(call.name)
            history.append(Message("tool", _run_call(call, by_name), tool_call_id=call.id))
