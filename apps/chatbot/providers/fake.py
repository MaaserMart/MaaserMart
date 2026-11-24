"""A provider that needs no network: for tests and for local work without a key (D-075)."""

from __future__ import annotations

from collections.abc import Sequence

from .base import ChatProvider, Message, ProviderError, Reply, Tool


class FakeProvider(ChatProvider):
    """Plays back `script`, one Reply (or ProviderError, raised) per call.

    With no script it echoes the last user message, so the panel can be clicked
    through locally. Every call is kept in `calls` for tests to inspect.
    """

    name = "fake"
    default_model = "fake"

    def __init__(self, *, script: Sequence[Reply | ProviderError] = (), **kwargs):
        super().__init__(**kwargs)
        self.script = list(script)
        self.calls: list[tuple[tuple[Message, ...], tuple[Tool, ...]]] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[Tool] = ()) -> Reply:
        self.calls.append((tuple(messages), tuple(tools)))
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, ProviderError):
                raise step
            return step
        asked = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return Reply(text=f"(No model is configured.) You asked: {asked}")
