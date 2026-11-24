"""The chatbot's provider layer and tool loop (D-075). No test reaches a network."""

import io
import json
import urllib.error
from unittest import mock

import pytest

from apps.chatbot import loop
from apps.chatbot.providers import (
    BUILT_IN,
    ChatProvider,
    DeepSeekProvider,
    FakeProvider,
    Message,
    OpenAIProvider,
    ProviderConfigError,
    ProviderError,
    Reply,
    Tool,
    ToolCall,
    Usage,
    get_provider,
    provider_class,
)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _respond(body):
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return mock.patch("urllib.request.urlopen", return_value=_Response(raw))


def _http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, io.BytesIO(b""))


LOOKUP = Tool(
    "find_charity",
    "Find a charity by name.",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    },
)


# --- OpenAI-compatible wire format --------------------------------------------


def test_request_carries_model_key_messages_and_tools():
    provider = OpenAIProvider(api_key="sk-test", timeout=7)
    body = {"choices": [{"message": {"content": "Hi"}}], "usage": {"prompt_tokens": 3}}
    with _respond(body) as urlopen:
        reply = provider.complete([Message("user", "Hello")], [LOOKUP])
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.openai.com/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert urlopen.call_args.kwargs["timeout"] == 7
    sent = json.loads(request.data)
    assert sent["model"] == "gpt-4o-mini"
    assert sent["messages"] == [{"role": "user", "content": "Hello"}]
    assert sent["tools"][0]["function"]["name"] == "find_charity"
    assert reply == Reply(text="Hi", usage=Usage(prompt_tokens=3, completion_tokens=0))


def test_no_tools_key_when_no_tools_offered():
    with _respond({"choices": [{"message": {"content": "ok"}}]}) as urlopen:
        OpenAIProvider(api_key="k").complete([Message("user", "x")])
    assert "tools" not in json.loads(urlopen.call_args.args[0].data)


def test_deepseek_uses_its_own_address_and_model():
    provider = DeepSeekProvider(api_key="k", model="deepseek-other")
    with _respond({"choices": [{"message": {"content": "ok"}}]}) as urlopen:
        provider.complete([Message("user", "x")])
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert json.loads(request.data)["model"] == "deepseek-other"


def test_tool_turns_go_out_in_wire_format():
    call = ToolCall("c1", "find_charity", {"name": "Yad"})
    history = [
        Message("assistant", "", tool_calls=(call,)),
        Message("tool", '{"id": 1}', tool_call_id="c1"),
    ]
    with _respond({"choices": [{"message": {"content": "ok"}}]}) as urlopen:
        OpenAIProvider(api_key="k").complete(history)
    sent = json.loads(urlopen.call_args.args[0].data)["messages"]
    assert sent[0]["tool_calls"][0] == {
        "id": "c1",
        "type": "function",
        "function": {"name": "find_charity", "arguments": '{"name": "Yad"}'},
    }
    assert sent[1] == {"role": "tool", "content": '{"id": 1}', "tool_call_id": "c1"}


def test_tool_calls_are_parsed_and_bad_arguments_become_none():
    body = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"id": "a", "function": {"name": "f", "arguments": '{"x": 1}'}},
                        {"id": "b", "function": {"name": "g", "arguments": "not json"}},
                        {"id": "c", "function": {"name": "h", "arguments": "[1]"}},
                    ],
                }
            }
        ]
    }
    with _respond(body):
        reply = OpenAIProvider(api_key="k").complete([Message("user", "x")])
    assert reply.text == ""
    assert reply.tool_calls == (
        ToolCall("a", "f", {"x": 1}),
        ToolCall("b", "g", None),
        ToolCall("c", "h", None),
    )


@pytest.mark.parametrize(
    ("code", "retryable"), [(400, False), (401, False), (429, True), (500, True), (503, True)]
)
def test_http_errors_say_whether_to_retry(code, retryable):
    with mock.patch("urllib.request.urlopen", side_effect=_http_error(code)):
        with pytest.raises(ProviderError) as caught:
            OpenAIProvider(api_key="k").complete([Message("user", "x")])
    assert caught.value.status == code
    assert caught.value.retryable is retryable


@pytest.mark.parametrize("error", [urllib.error.URLError("down"), TimeoutError()])
def test_network_failures_are_retryable(error):
    with mock.patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ProviderError) as caught:
            OpenAIProvider(api_key="k").complete([Message("user", "x")])
    assert caught.value.retryable is True


@pytest.mark.parametrize("body", [b"<html>", {"choices": []}, {"nothing": 1}])
def test_unusable_responses_raise(body):
    with _respond(body):
        with pytest.raises(ProviderError) as caught:
            OpenAIProvider(api_key="k").complete([Message("user", "x")])
    assert caught.value.retryable is False


def test_missing_key_never_calls_out():
    with mock.patch("urllib.request.urlopen") as urlopen:
        with pytest.raises(ProviderError):
            OpenAIProvider().complete([Message("user", "x")])
    urlopen.assert_not_called()


def test_repr_hides_the_key():
    assert "sk-secret" not in repr(OpenAIProvider(api_key="sk-secret"))


# --- The registry ---------------------------------------------------------------


class CustomProvider(ChatProvider):
    name = "custom"
    default_model = "c-1"

    def complete(self, messages, tools=()):
        return Reply(text="custom")


def test_built_ins_are_registered_by_name():
    assert set(BUILT_IN) == {"openai", "deepseek", "fake"}
    assert provider_class(" deepseek ") is DeepSeekProvider


def test_a_dotted_path_plugs_in_a_new_provider():
    assert provider_class(f"{__name__}.CustomProvider") is CustomProvider


@pytest.mark.parametrize("name", ["", "claude", "no.such.Module", "json.dumps"])
def test_bad_provider_names_are_config_errors(name):
    with pytest.raises(ProviderConfigError):
        provider_class(name)


def test_get_provider_defaults_to_fake_in_tests():
    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    assert provider.complete([Message("user", "Hi")]).text.endswith("You asked: Hi")


def test_get_provider_reads_model_key_and_timeout(settings):
    settings.CHATBOT_PROVIDER = "deepseek"
    settings.DEEPSEEK_API_KEY = "dk"
    settings.CHATBOT_MODEL = "deepseek-x"
    settings.CHATBOT_TIMEOUT_SECONDS = 9
    provider = get_provider()
    assert isinstance(provider, DeepSeekProvider)
    assert (provider.api_key, provider.model, provider.timeout) == ("dk", "deepseek-x", 9)


def test_get_provider_without_a_key_is_a_config_error(settings):
    settings.CHATBOT_PROVIDER = "openai"
    settings.OPENAI_API_KEY = ""
    with pytest.raises(ProviderConfigError):
        get_provider()


def test_fake_plays_back_its_script_and_records_calls():
    fake = FakeProvider(script=[Reply(text="one"), ProviderError("boom", retryable=True)])
    assert fake.complete([Message("user", "a")], [LOOKUP]).text == "one"
    with pytest.raises(ProviderError):
        fake.complete([Message("user", "b")])
    assert fake.calls[0][1] == (LOOKUP,)
    assert len(fake.calls) == 2


# --- The tool loop --------------------------------------------------------------


def _lookup_function(run):
    return loop.ToolFunction(LOOKUP, run)


def _call(arguments, name="find_charity", id="c1"):
    return Reply(tool_calls=(ToolCall(id, name, arguments),))


def _tool_results(fake, call_index):
    messages = fake.calls[call_index][0]
    return [json.loads(m.content) for m in messages if m.role == "tool"]


def test_plain_answer_takes_one_round():
    fake = FakeProvider(script=[Reply(text="  Shalom  ", usage=Usage(5, 2))])
    outcome = loop.converse(fake, [Message("user", "hi")])
    assert (outcome.text, outcome.rounds, outcome.tools_called) == ("Shalom", 1, [])
    assert (outcome.prompt_tokens, outcome.completion_tokens) == (5, 2)


def test_model_looks_up_then_answers():
    seen = []

    def run(name):
        seen.append(name)
        return {"id": 7, "name": name}

    fake = FakeProvider(script=[_call({"name": "Yad"}), Reply(text="Found it.")])
    outcome = loop.converse(fake, [Message("user", "q")], [_lookup_function(run)])
    assert seen == ["Yad"]
    assert outcome.text == "Found it."
    assert outcome.tools_called == ["find_charity"]
    assert _tool_results(fake, 1) == [{"id": 7, "name": "Yad"}]
    assistant = fake.calls[1][0][1]
    assert assistant.role == "assistant" and assistant.tool_calls[0].id == "c1"


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        (_call({"name": "x"}, name="drop_tables"), "There is no tool called 'drop_tables'."),
        (_call(None), "The arguments were not a JSON object."),
        (_call({"name": "x", "sql": "1"}), "Unknown arguments: sql."),
        (_call({}), "Missing arguments: name."),
    ],
)
def test_bad_calls_are_told_to_the_model_not_run(reply, error):
    run = mock.Mock()
    fake = FakeProvider(script=[reply, Reply(text="ok")])
    loop.converse(fake, [Message("user", "q")], [_lookup_function(run)])
    run.assert_not_called()
    assert _tool_results(fake, 1) == [{"error": error}]


def test_a_refused_lookup_passes_its_reason_on():
    def run(name):
        raise loop.ToolError("No charity by that name.")

    fake = FakeProvider(script=[_call({"name": "x"}), Reply(text="ok")])
    loop.converse(fake, [Message("user", "q")], [_lookup_function(run)])
    assert _tool_results(fake, 1) == [{"error": "No charity by that name."}]


def test_a_broken_lookup_is_logged_and_hidden(caplog):
    def run(name):
        raise RuntimeError("secret internals")

    fake = FakeProvider(script=[_call({"name": "x"}), Reply(text="ok")])
    loop.converse(fake, [Message("user", "q")], [_lookup_function(run)])
    assert _tool_results(fake, 1) == [{"error": "That lookup failed."}]
    assert "find_charity failed" in caplog.text


def test_long_results_are_cut():
    fake = FakeProvider(script=[_call({"name": "x"}), Reply(text="ok")])
    loop.converse(fake, [Message("user", "q")], [_lookup_function(lambda name: "y" * 99999)])
    content = fake.calls[1][0][-1].content
    assert len(content) < loop.MAX_RESULT_CHARS + 50
    assert content.endswith("ask for something narrower)")


def test_results_with_dates_and_decimals_serialise():
    import datetime
    from decimal import Decimal

    fake = FakeProvider(script=[_call({"name": "x"}), Reply(text="ok")])
    result = {"when": datetime.date(2026, 1, 2), "amount": Decimal("1.50")}
    loop.converse(fake, [Message("user", "q")], [_lookup_function(lambda name: result)])
    assert _tool_results(fake, 1) == [{"when": "2026-01-02", "amount": "1.50"}]


def test_after_max_rounds_the_model_must_answer_without_tools():
    fake = FakeProvider(script=[_call({"name": "x"}, id=str(i)) for i in range(2)])
    fake.script.append(Reply(text="Best I can do."))
    outcome = loop.converse(
        fake, [Message("user", "q")], [_lookup_function(lambda name: 1)], max_rounds=2
    )
    assert outcome.rounds == 3
    assert [len(tools) for _, tools in fake.calls] == [1, 1, 0]
    assert outcome.text == "Best I can do."
    assert outcome.tools_called == ["find_charity", "find_charity"]


def test_provider_errors_reach_the_caller():
    fake = FakeProvider(script=[ProviderError("down", retryable=True)])
    with pytest.raises(ProviderError):
        loop.converse(fake, [Message("user", "q")])
