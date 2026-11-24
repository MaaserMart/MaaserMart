"""Providers that speak the OpenAI Chat Completions API: OpenAI and DeepSeek (D-075).

DeepSeek's API is the same wire format at a different address, so both are one
class with different defaults. Another compatible vendor is a three-line
subclass. Requests go out through the standard library, so no SDK is added.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from .base import ChatProvider, Message, ProviderError, Reply, Tool, ToolCall, Usage


def _wire_message(message: Message) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments or {}),
                },
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _wire_tool(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_arguments(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _parse_reply(body: dict[str, Any]) -> Reply:
    try:
        message = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        raise ProviderError("The response had no message.") from None
    calls = tuple(
        ToolCall(
            id=str(call.get("id", "")),
            name=str(call.get("function", {}).get("name", "")),
            arguments=_parse_arguments(call.get("function", {}).get("arguments")),
        )
        for call in message.get("tool_calls") or ()
    )
    usage = body.get("usage") or {}
    return Reply(
        text=message.get("content") or "",
        tool_calls=calls,
        usage=Usage(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        ),
    )


class OpenAICompatibleProvider(ChatProvider):
    """POST {base_url}/chat/completions with a bearer key."""

    base_url = ""

    def __init__(self, *, base_url: str = "", **kwargs):
        super().__init__(**kwargs)
        if base_url:
            self.base_url = base_url

    def complete(self, messages: Sequence[Message], tools: Sequence[Tool] = ()) -> Reply:
        if not self.api_key:
            raise ProviderError(f"No API key is set for {self.name}.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_wire_message(m) for m in messages],
        }
        if tools:
            payload["tools"] = [_wire_tool(t) for t in tools]
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                body = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            # 429 and the vendor's own failures pass; a bad key or request will not.
            raise ProviderError(
                f"{self.name} answered HTTP {exc.code}.",
                retryable=exc.code == 429 or exc.code >= 500,
                status=exc.code,
            ) from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(
                f"{self.name} could not be reached: {exc}", retryable=True
            ) from None
        except ValueError:
            raise ProviderError(f"{self.name} sent a response that is not JSON.") from None
        return _parse_reply(body)


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    # deepseek-chat supports tool calls; deepseek-reasoner does not.
    default_model = "deepseek-chat"
