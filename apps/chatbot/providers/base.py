"""The provider-neutral shapes every chat model speaks through (D-075).

The rest of the chatbot builds `Message`s and `Tool`s and reads back a `Reply`.
It never sees a vendor's wire format, so switching models is a settings change
and adding one is a new subclass of `ChatProvider`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolCall:
    """The model asking to run one tool.

    `arguments` is None when the model sent something that is not a JSON object;
    the loop tells the model so rather than guessing what it meant.
    """

    id: str
    name: str
    arguments: dict[str, Any] | None


@dataclass(frozen=True)
class Message:
    """One turn of the conversation.

    An assistant turn may carry `tool_calls`; each answer to one is a `tool`
    turn naming the call it answers in `tool_call_id`.
    """

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


@dataclass(frozen=True)
class Tool:
    """A read-only function the model may call. `parameters` is a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False}
    )


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class Reply:
    """What the model said: text, tool calls, or both."""

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage | None = None


class ProviderError(Exception):
    """The model could not answer.

    `retryable` is True for what may pass on its own (timeouts, rate limits, the
    vendor's 5xx); False for what will not (a bad key, a malformed request).
    The message is for the logs, never for the visitor.
    """

    def __init__(self, message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status = status


class ProviderConfigError(ProviderError):
    """The provider is unknown or missing its key; retrying will not help."""


class ChatProvider(ABC):
    """One way of reaching a chat model. Subclasses set `name` and `default_model`."""

    name: str = ""
    default_model: str = ""

    def __init__(self, *, model: str = "", api_key: str = "", timeout: float = 30.0):
        self.model = model or self.default_model
        self.api_key = api_key
        self.timeout = timeout

    @abstractmethod
    def complete(self, messages: Sequence[Message], tools: Sequence[Tool] = ()) -> Reply:
        """Send the conversation and return the model's next turn.

        Raises ProviderError when no answer came back.
        """

    def __repr__(self) -> str:  # never shows the key
        return f"<{type(self).__name__} model={self.model!r}>"
