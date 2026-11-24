"""Pick the chat model from settings (D-075).

`CHATBOT_PROVIDER` names a built-in ("openai", "deepseek", "fake") or gives the
dotted path of any `ChatProvider` subclass, so a new vendor plugs in without
touching this file. `CHATBOT_MODEL` overrides the provider's default model. Each
provider's key comes from its own setting, `<NAME>_API_KEY`.
"""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from .base import (
    ChatProvider,
    Message,
    ProviderConfigError,
    ProviderError,
    Reply,
    Tool,
    ToolCall,
    Usage,
)
from .fake import FakeProvider
from .openai_compat import DeepSeekProvider, OpenAICompatibleProvider, OpenAIProvider

BUILT_IN: dict[str, type[ChatProvider]] = {
    cls.name: cls for cls in (OpenAIProvider, DeepSeekProvider, FakeProvider)
}

__all__ = [
    "BUILT_IN",
    "ChatProvider",
    "DeepSeekProvider",
    "FakeProvider",
    "Message",
    "OpenAICompatibleProvider",
    "OpenAIProvider",
    "ProviderConfigError",
    "ProviderError",
    "Reply",
    "Tool",
    "ToolCall",
    "Usage",
    "get_provider",
    "provider_class",
]


def provider_class(name: str) -> type[ChatProvider]:
    """The class a CHATBOT_PROVIDER value names."""
    name = (name or "").strip()
    if name in BUILT_IN:
        return BUILT_IN[name]
    if "." in name:
        try:
            cls = import_string(name)
        except ImportError as exc:
            raise ProviderConfigError(f"Cannot import chat provider {name!r}: {exc}") from None
        if isinstance(cls, type) and issubclass(cls, ChatProvider):
            return cls
        raise ProviderConfigError(f"{name!r} is not a ChatProvider subclass.")
    raise ProviderConfigError(f"Unknown chat provider {name!r}; built in: {', '.join(BUILT_IN)}.")


def get_provider() -> ChatProvider:
    """The provider settings ask for, ready to call.

    Raises ProviderConfigError when it is unknown or has no key, so the caller
    can give the visitor the "couldn't get an answer" state (§6.3).
    """
    cls = provider_class(settings.CHATBOT_PROVIDER)
    api_key = ""
    if cls is not FakeProvider:
        api_key = getattr(settings, f"{cls.name.upper()}_API_KEY", "") if cls.name else ""
        if not api_key:
            raise ProviderConfigError(
                f"No API key is set for the {cls.name or cls.__name__} provider."
            )
    return cls(
        model=settings.CHATBOT_MODEL,
        api_key=api_key,
        timeout=settings.CHATBOT_TIMEOUT_SECONDS,
    )
