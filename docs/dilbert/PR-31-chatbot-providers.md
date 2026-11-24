# PR #31 — The chatbot talks to its model through a swappable provider

- Branch: `chatbot/providers` → `main`
- Merge commit: `eff42a8` (2026-11-24)
- Author: Platform Lead (Shaul)
- Decision recorded: D-075
- Size: 11 files, +866 / −0
- Amended after review: branch `docs/dilbert-and-review-fixes` keeps an oversized tool result valid JSON instead of chopping it (section 7.5). The code quoted below is the amended code, not the merge exactly.

---

## 1. Read this part even if you read nothing else

MaaserMart is getting a chat box: press the corner icon and ask the site a
question, in plain words. "Where do I see how much maaser I owe?" Underneath the
box is an AI model — and here is the part this change is really about: **the box
must survive the model being swapped for a different one.**

That is not a theory. The requirement (D-075's parent, §6.3.2) names two vendors —
OpenAI and DeepSeek — and says the chatbot should not be tied to either. Two
models, one chat box, no code changes between them.

So this change builds two things. First, an **adapter**: a thin, agreed-upon
shape for "a conversation and its answer" that every model can be wrapped to
speak. OpenAI and DeepSeek both come wrapped, and — here is the design decision —
so does a **fake**: a pretend model that answers without any internet, which is
what the site uses in tests and in development, so nobody needs a paid key to
try the box.

Second, the **loop**: when you ask a question whose answer lives in the site's
database — "is Hatzolah listed?" — the box gives the model a small menu of
read-only lookups instead of letting it rummage around. The model picks: "run the
lookup 'find a charity by name' with 'Hatzolah'". The site runs it and hands the
result back. The model reads it and answers you. If it asks for something that is
not on the menu, or forgets an argument, it is told politely and must try again —
it can never run anything dangerous, because the menu is the only door, and every
item on it is a read-only question to an approved part of the site.

The rule that makes both of these work is a one-sided promise familiar from the
earlier pull requests in this series: **the chatbot never touches another
area's tables.** Every lookup the model may ask for goes through that area's
services, the same door the pages use.

What is *not* here, on purpose: the panel, the question form, the queue that runs
the model in the background, and the "you've used your daily questions" cap.
That is the next pull request (PR #32). This one is the engine.

Everything below is the same idea in more detail.

---

## 2. How to read this file

For two people at once.

- If you do not write software, read the **glossary**, then the **story**, then the
  bold one-line summary at the top of each file section.
- If you are reviewing the code, the same sections carry it, quoted, in reading
  order, with a `file.py:line` address on each box.

Three rules:

1. **Read the glossary first.** Every term is defined there.
2. **Every code box is optional.** The sentence above it says the same thing in
   plain English.
3. **Skim the bold lines.** They are the summary.

---

## 3. The glossary

Ten words, one table.

- **Model** — the AI that writes the answers: a service paid per question, OpenAI's
  or DeepSeek's, sitting on the internet.
- **Provider** — one concrete way of reaching a model. A wrapper. The site has
  three: openai, deepseek, and fake.
- **Adapter — same thing as provider**, from a different direction. When there is no
  adapter, the rest of the chatbot would have to speak one vendor's private dialect
  everywhere; the adapter confines that dialect to one file.
- **Wire format** — the exact shape of the message that travels over the internet
  to and from a model's office. OpenAI's and DeepSeek's are the same shape, which is
  why one adapter serves both.
- **Message** — one turn of conversation: "you said this", "I said that". A
  conversation is a list of messages in order.
- **Tool** — one read-only thing the model is allowed to ask for, described in
  plain words, with a list of the arguments it must supply. In this change the
  tools themselves (find a charity, show the member's maaser) are still to come;
  the machinery for them is what is built.
- **Tool call** — the model actually asking: "run the lookup 'find a charity' with
  name = Hatzolah."
- **Reply** — the model's next turn: an answer in words, or tool calls, or (usually
  in real use) both — "I'll look that up" plus the call.
- **RAG** — retrieval-augmented generation, the industry's word for "the model is
  allowed to look things up before answering". Here it is done through tool calls,
  so "look things up" always means "call a service", never "read the database".
- **Token** — the units a model bills by, roughly fragments of words. Providers
  report how many were used; the site logs the number without logging what was said.

Names that exist only in this code, and the plain word used here:

| in the code | in this file |
|---|---|
| `ChatProvider.complete(...)` | "have the model take its next turn" |
| `Message`, `Tool`, `ToolCall`, `Reply` | the four shapes in the glossary |
| `script` (on the fake) | a recorded answer list, played back for tests |
| `usage` | token counts |
| `retryable` | "worth trying again" |
| `CHATBOT_PROVIDER` | the setting naming which model the site uses |
| `BUILT_IN` | the three providers the site knows by name |
| `_run_call` | "answer one tool call" |
| `converse(...)` | "run the whole conversation" |

---

## 4. The story

### What the site does all day

1. A visitor browses charities, or uses a tool.
2. Somewhere in a corner sits an unopened chat box.
3. A member opens it, asks, and the model answers — looking up real facts from the
   site's own data when the question needs them.

Until this change, steps 2 and 3 could not happen: no engine existed. The chatbot
app was a directory with no code in it.

### What was wrong — the three problems this change solves

**First: the site would have been glued to a vendor.** The naive way to add a chat
box is to install OpenAI's helper library and call it. Then the day the requirement
says "now add DeepSeek" (and it does), you install DeepSeek's library and sprinkle
it through the code. Every month one of them changes its prices or its API, and
every month the chat box code changes with it. The requirement asks for the
opposite: model-agnostic, plug and play.

**Second: "plug and play" has no honest meaning without a fake.** It is impossible
to develop and test a chat box that reaches a paid internet API on every keystroke.
Tests would be slow, flaky, and cost money. So part of the point of an adapter is a
third adapter that needs no internet at all.

**Third: nobody had said *how* the model learns facts.** A chatbot with the site's
own data in it has two naive options, and both are bad. One: every question is
sent along with a dump of every charity — expensive, and the prompt fills up. Two:
the model builds database queries itself, which means a model (or a question
planted inside a model's input) can read anything. The requirement refuses the
second: the model asks through read-only service calls, which is the tool-call
design. The model is *not* told "here is the database"; it is told "here is a menu
of things you may ask for".

### The cost of leaving it

Concrete case, carried through. A member asks: "Which charity in Jerusalem offers
clothing assistance?" The naive glued-to-OpenAI box replies with a confident
paragraph naming a charity that does not exist, invented from its training data.
The member tells the admins; the admins cannot fix it, because the box cannot
check anything. With this change, the same question makes the model ask for the
lookup, the lookup returns the real list the site itself uses, and the answer is
drawn from the listing — name, link, real.

### The fix, in one sentence

A provider-neutral conversation shape with three adapters (openai, deepseek,
fake) chosen purely by a setting, and a loop that offers the model a menu of
read-only service-call lookups, runs whichever it asks for, returns the results,
and stops the whole thing at four rounds so it must eventually answer in words.

The consequences, listed plainly:

- Switching model vendors is editing one environment setting, not code.
- Adding a fourth vendor is writing one small class — no edits to the chatbot.
- Tests and local development use the fake, so the suite never touches the
  network and never spends money.
- The model can run only lookups that exist and that are read-only; bad calls
  come back as messages, never as crashes.
- A question's answer can be checked against real site data, so the box stops
  inventing charities.
- Every failure knows whether retrying will help; the visitor-facing message is
  one size: "couldn't get an answer."

---

## 5. Contradictions

None between the pull request, the D-075 entry and the code. The three agree on the
same five facts: three adapters, the choice by setting, no vendor SDK, failures
carrying a retry flag, and four tool rounds.

One wording point that a careful reader will trip over, so it is worth stating
plainly. The summaries say the model gets "at most 4 rounds". The code's
`MAX_ROUNDS = 4` counts rounds *with the tool menu offered*; when those are used up
the model is asked one final time with the menu withdrawn, so a single question can
cost five calls to the model, not four. `test_after_max_rounds_the_model_must_answer_without_tools`
shows this exactly: with the maximum set to two, the fake is called three times and
sees the tool list 1, 1, 0. Trust the code: four rounds of tools, plus the forced
answer.

---

## 6. Reading order

| # | File | What it is | Why here |
|---|---|---|---|
| 1 | `apps/chatbot/providers/base.py` | the agreed shapes and the abstract adapter | everything speaks through these |
| 2 | `apps/chatbot/providers/openai_compat.py` | the real adapters: openai and deepseek | the wire dialect, confined |
| 3 | `apps/chatbot/providers/fake.py` | the pretend model for tests | no network, ever |
| 4 | `apps/chatbot/providers/__init__.py` | the registry: names → adapters, plus settings | choosing the model |
| 5 | `apps/chatbot/loop.py` | the conversation loop and the tool menu | the retrieval half |
| 6 | `config/settings/base.py`, `prod.py`, `test.py` | the settings | where the model is chosen |
| 7 | `.env.example` | documentation of the settings | the operator's view |
| 8 | `docs/DECISIONS.md` | the D-075 record: the decision in prose | the argument, not the code |
| 9 | `tests/unit/test_chatbot_providers.py` | the proof | last |

The shape in one sentence: **`base.py` defines one language, `openai_compat.py` and
`fake.py` speak it for three models, `__init__.py` picks one from settings, and
`loop.py` runs the conversation with a read-only tool menu the model may ask from.**

---

## 7. The files

### 7.1 `apps/chatbot/providers/base.py` — the one language everyone speaks

**This new file defines the four conversation shapes — message, tool, tool call, reply — and the abstract adapter every model must be wrapped in, with a rule that failures carry a "retry?" flag.**

Before this change, nothing in the whole codebase defined even a "message". The
chatbot directory was empty of logic.

The central contract, in the abstract adapter's own words (`apps/chatbot/providers/base.py:89`):

```python
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
```

`complete` is the whole adapter: send a conversation and a tool list, get a reply.
Subclasses provide `name` and `default_model`; a caller can override the model
explicitly, and an empty override means "the provider's own default". The class is
abstract, so an adapter that forgets `complete` cannot be instantiated.

The message shape (`apps/chatbot/providers/base.py:32`):

```python
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
```

The four roles are the fixed vocabulary of any chat model's conversation:
`system` (standing instructions), `user` (what the visitor said), `assistant`
(what the model said), and `tool` (a lookup result fed back). The point of the
comment on the class is the pairing rule: when the model calls tools, the site
answers each call with a `tool` message that names *which* call it answers
(`tool_call_id`), so a conversation with three lookups in one turn still reads as a
thread, not a pile.

The rest of the vocabulary (`apps/chatbot/providers/base.py:19`, `:46`, `:57`,
`:63`):

```python
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
```

Two details matter beyond their size. `Tool.parameters` is "a JSON Schema object"
— the machine-readable way of describing the arguments a tool takes (name: string,
required: name). It pulls double duty: `openai_compat.py` forwards it to the model
verbatim, and the loop uses it to refuse calls with unknown or missing arguments
without ever needing to guess. And `ToolCall.arguments` being *allowed to be None*
is a deliberate contrast with "empty": the comment says the loop will tell the
model so — a model that sends unparseable arguments is corrected, not silently run
with whatever the site assumed, and not silently crashed.

The failure contract (`apps/chatbot/providers/base.py:71`):

```python
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


...
    def __repr__(self) -> str:  # never shows the key
        return f"<{type(self).__name__} model={self.model!r}>"
```

The box above is a re-quote, so nothing is hidden: one flag decides the whole failure policy of the chatbot later: `retryable`. A
timeout or a rate limit may clear on its own — the panel will retry twice. A bad
API key will *never* clear — retrying would just cost money. And the code comment
is a promise: the message is for the logs, never for the visitor, because it may
contain vendor internals. The `__repr__` at the end is the same promise in a
different form — an adapter object printed in a log or a debugger shows `model=`
but never `api_key=`.

What it buys: every other file in this change speaks only these four shapes, so a
new model needs one adapter and nothing else changes.

### 7.2 `apps/chatbot/providers/openai_compat.py` — the real models, one class

**This new file contains the one adapter class both real models use — because OpenAI's and DeepSeek's internet wire format is the same shape — plus the model's three-line subclasses.**

Before this change, no code in the repository had ever talked to a chat model. The
design decision to reach with the standard library rather than an installed SDK
(no `openai` package, no `deepseek` package) keeps the dependency list empty and
the adapter small; it also means this file contains every place the wire format
appears, which is the point of an adapter.

The file's docstring makes the economic argument (`apps/chatbot/providers/openai_compat.py:1`):

```python
"""Providers that speak the OpenAI Chat Completions API: OpenAI and DeepSeek (D-075).

DeepSeek's API is the same wire format at a different address, so both are one
class with different defaults. Another compatible vendor is a three-line
subclass. Requests go out through the standard library, so no SDK is added.
"""
```

Sending a conversation out (`apps/chatbot/providers/openai_compat.py:93`):

```python
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
```

The body of the request starts with the model and the conversation, and the tools
only if there *are* any — the `if tools:` guard means a plain question costs no
extra payload, which `test_no_tools_key_when_no_tools_offered` pins. The request
goes to `<base_url>/chat/completions` — the one fact that differs between the two
vendors — and the key rides in the `Authorization` header.

The error mapping is where `retryable` gets its meaning. An HTTP error is
retryable exactly when it is a rate limit (429) or a server failure (5xx), because
those may clear; everything else — a 400 (bad request), a 401 (bad key) — is not.
A network failure or timeout is always retryable. A response that is not JSON at
all is not. Every path turns into a `ProviderError`, so the loop below needs only
one exception to handle.

Reading a reply back (`apps/chatbot/providers/openai_compat.py:59`):

```python
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
```

The conversation is converted piece by piece: each tool call the model made becomes
a `ToolCall`; the "arguments" arrive as a JSON *string* and are parsed into a dict,
with anything unparseable becoming None (the loop's message-of-correction path);
token counts become `Usage`. A response with no `choices` at all — which happens
when a vendor changes shape — is a non-retryable error, not a crash.

The two models are subclasses so thin they show the whole design
(`apps/chatbot/providers/openai_compat.py:130`):

```python
class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    base_url = "https://api.openai.com/v1"
    default_model = "gpt-4o-mini"


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    # deepseek-chat supports tool calls; deepseek-reasoner does not.
    default_model = "deepseek-chat"
```

The comment on `default_model` is a small piece of vendor knowledge that would
otherwise be lost: DeepSeek has two models, and only one of them speaks tool calls
— worth a note so nobody "upgrades" the setting to the other one and wonders why
the lookups stop.

What it buys: both required vendors work today, and the price of a third is three
lines — a name, an address, a default model.

### 7.3 `apps/chatbot/providers/fake.py` — the pretend model

**A second adapter that needs no network: it answers from a recorded script in tests, or echoes the question in local development, so every test and every keyless developer visits the chat box free.**

Before this change no such thing existed, and no honest "plug and play" claim can
be tested without it — using the real API in tests would make the suite slow,
flaky and paid.

The whole implementation (`apps/chatbot/providers/fake.py:10`):

```python
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
```

Two behaviours, one recorder. A test hands it a `script` — a list of prepared
replies, or prepared *failures* — and it plays them back one per call, so tests can
stage "the model wants a lookup, then answers" or "the network died" with no
internet at all. Without a script it answers "(No model is configured.) You asked:
…", which is what a developer without an API key sees in the browser. And every
call — what messages and what tools were offered — is recorded in `calls`,
which is how the tests below *see inside* the loop: `test_model_looks_up_then_answers`
inspects the second recorded call to prove the assistant message carried the tool
call.

What it buys: the whole provider layer and loop are tested without one byte
touching a network, and the box is clickable by anyone on the team.

### 7.4 `apps/chatbot/providers/__init__.py` — the registry and the setting

**This file turns the setting `CHATBOT_PROVIDER` into a ready adapter: a built-in name is looked up, or a dotted path to any `ChatProvider` subclass is imported, and the key and timeout are read from settings.**

Before this change, nothing connected settings to adapters — there was no chatbot
code at all outside empty directories.

The registry (`apps/chatbot/providers/__init__.py:27`):

```python
BUILT_IN: dict[str, type[ChatProvider]] = {
    cls.name: cls for cls in (OpenAIProvider, DeepSeekProvider, FakeProvider)
}
```

Built from the classes' own `name` attributes, so a new adapter is registered just
by existing. The naming logic (`apps/chatbot/providers/__init__.py:50`):

```python
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
```

"openai" or "deepseek" (spaces trimmed) is a built-in. Anything containing a dot is
treated as a full address within the code, imported — which is the plug-in door: a
new vendor is a class *anywhere*, and the person configuring the site names it in a
setting. Everything else is a configuration error with the built-in list named in
the message, because "the model setting is a typo" is a problem that should fail
loudly at startup, in a sentence, not with a stack trace three layers down.

Creating the ready adapter (`apps/chatbot/providers/__init__.py:66`):

```python
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
```

Two rules here. The key is read from a setting whose name is *derived from the
provider's own name* — `OPENAI_API_KEY` for openai, `DEEPSEEK_API_KEY` for
deepseek — so a third vendor gets its key from settings with no code change, only a
paragraph in the environment file. And the fake is exempt from having a key, with
an explicit `is not FakeProvider` check rather than "if it has a name", because the
no-key promise is what makes local development zero-configuration.

What it buys: the person who deploys the site picks the model by editing one
environment line, and a missing or misspelled choice fails with a sentence.

### 7.5 `apps/chatbot/loop.py` — the conversation, with read-only lookups the model may ask for

**This new file is the engine: a loop that offers the model the tool menu, runs whatever it asks for, cuts long results, refuses bad calls with messages instead of crashes, and stops at four tool rounds so the model must answer.**

Before this change, nothing on the site could hold a conversation with a model at
all.

The limits, stated at the top (`apps/chatbot/loop.py:24`):

```python
# A question needs a few lookups, not dozens; past this the model must answer.
MAX_ROUNDS = 4
# A tool result is cut here, so one broad lookup cannot fill the context window.
MAX_RESULT_CHARS = 6000
```

The two things that keep a single question from eating the whole budget: rounds and
result size. The second matters more than it looks — a lookup that returns 200
charities could dwarf the whole conversation in tokens if uncut.

The wrapper that ties a tool's description to its real function
(`apps/chatbot/loop.py:34`):

```python
@dataclass(frozen=True)
class ToolFunction:
    """A tool the model sees (`tool`) and the Python that answers it (`run`)."""

    tool: Tool
    run: Callable[..., Any]
```

The model sees `tool` (the name and description); the site calls `run` (the actual
service function) — and the two travel together, so nothing can advertise one
thing and do another.

The safety check on arguments (`apps/chatbot/loop.py:52`):

```python
def _check_arguments(tool: Tool, arguments: dict[str, Any] | None) -> str | None:
    """Why these arguments cannot be passed, or None when they can."""
    if arguments is None:
        return "The arguments were not a JSON object."
    schema = tool.parameters or {}
    known = set(schema.get("properties", {}))
    unknown = sorted(set(arguments) - known)
    if unknown:
        return f"Unknown arguments: {', '.join(unknown)}."
    missing = sorted(set(schema.get("required", ()) - set(arguments)))
    if missing:
        return f"Missing arguments: {', '.join(missing)}."
    return None
```

The tool's own JSON schema is the referees' rulebook: every argument offered must
be in the schema's list of properties, and every required property must be present.
Unknown arguments are refused — this is what keeps a model from sneaking a stray
`sql` argument into a lookup call, and the test file explicitly stages that
attempt. None of it is guessed; the schema the model itself was shown is the schema
that is enforced.

Answering one call, never raising (`apps/chatbot/loop.py:67`):

```python
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
```

The escalating refusals are the interesting part. An unknown tool name, an argument
problem, or a lookup that itself refuses (raises `ToolError`, carrying a sentence
like "No charity by that name") all become a JSON `{"error": "…"}` *result* fed
back to the model — the model is told "that didn't work, try something else", the
conversation continues, nobody crashes. A *bug* in a lookup — any other exception —
becomes "That lookup failed." with the real traceback in the server log, so
internals (and any data they carried) never reach the model.

The length guard has a story worth telling, because it was wrong once. As first
merged it chopped the finished JSON at 6,000 characters and glued a note on the end.
That keeps the *size* down but breaks the *format*: a half-written object is not
JSON, so the model received an unparseable fragment where the contract says a result,
and reasoning about what to do next from garbage is exactly the sort of thing that
produces a nonsense answer. The review-branch fix keeps the shape: when a result is
too long, it is replaced by a small valid object carrying a plain `error`, a `hint`
("Ask for something narrower.") and a `preview` of the oversized text. The model still
reads a normal result, still gets the instruction to narrow the request, and simply
cannot see the whole of what it asked for — which is the intended behaviour.

The result is JSON-serialised with `DjangoJSONEncoder`, which knows how to write
dates and decimal amounts — the exact things a maaser figure or a charity record
contains — into text the model can read.

The loop itself (`apps/chatbot/loop.py:89`):

```python
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
```

Reading the loop in order. The tools are indexed by name and offered every round as
long as rounds remain. With fewer than `max_rounds` used, the model may answer in
words *or* call tools; the moment it answers in words — or the rounds run out and
the tools are withdrawn (`offer` becomes empty) — the loop returns. Otherwise the
model's tool calls are appended to the history as assistant messages, each answered
by a tool message, and the loop asks again. The forced-final-round is why
`test_after_max_rounds_the_model_must_answer_without_tools` sees three calls when
the maximum tool rounds were two.

The `Outcome` dataclass (`apps/chatbot/loop.py:42`) accumulates exactly what §3.4.2
wants the site to log and nothing else:

```python
@dataclass
class Outcome:
    """The answer, and what it took to get it (for logging chatbot use, §3.4.2)."""

    text: str
    rounds: int = 0
    tools_called: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
```

Rounds, tool names and token counts — the usage log's data, with no question text
and no answer text, so the log never records what people actually asked.

What it buys: the model can only ask from a menu of read-only service calls, its
mistakes come back as corrections, and a question can never burn more than a
bounded amount of the model's attention.

### 7.6 The settings — where the model is chosen

**Three files: the base default is the fake for everyone; production defaults to openai; tests force the fake so no test can reach a real model no matter what your local `.env` says.**

Before this change there were no chatbot settings at all.

The base choice (`config/settings/base.py:179`):

```python
# The chatbot's model (D-075). A built-in name ("openai", "deepseek", "fake") or
# the dotted path of a ChatProvider subclass. "fake" needs no key and no network;
# production defaults to "openai" in prod.py. An empty model means the
# provider's own default. Each provider reads its key from <NAME>_API_KEY.
CHATBOT_PROVIDER = env("CHATBOT_PROVIDER", default="fake")
CHATBOT_MODEL = env("CHATBOT_MODEL", default="")
CHATBOT_TIMEOUT_SECONDS = env.int("CHATBOT_TIMEOUT_SECONDS", default=30)
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
DEEPSEEK_API_KEY = env("DEEPSEEK_API_KEY", default="")
```

The production override (`config/settings/prod.py:60`):

```python
# A real model in production; without its key the chatbot answers "couldn't get
# an answer" rather than echoing like the fake (D-075).
CHATBOT_PROVIDER = env("CHATBOT_PROVIDER", default="openai")
```

This is the split that makes the whole thing honest: local work and CI are free and
network-free; production asks a real model, or, if the key is missing, fails with a
clear configuration error rather than pretending to answer. The test override
(`config/settings/test.py:19`) hard-codes `CHATBOT_PROVIDER = "fake"` and clears
both keys, with the comment "No test reaches a real model, whatever .env says" —
which is the safety net: a developer's stray `.env` key cannot make the suite
spend money.

The `.env.example` block documents the four switches the operator can touch
(`.env.example:37`):

The docs block begins at `.env.example:37` and the four values start on line 40 (`git show eff42a8^2:.env.example`).

```text
# --- The chatbot's model (D-075) ---
# "fake" (the default outside production) needs no key and echoes the question.
# Switch by name, or give the dotted path of your own ChatProvider subclass.
#   CHATBOT_PROVIDER=deepseek
#   CHATBOT_MODEL=            # empty: the provider's default model
#   OPENAI_API_KEY=
#   DEEPSEEK_API_KEY=
```

What it buys: one person setting up the site can go from "echo" to a real vendor
by uncommenting lines, without reading any code.

---

## 8. The tests

The new file is `tests/unit/test_chatbot_providers.py` (39 collected tests at the
merge, 39 now: the review branch renamed one and strengthened it rather than adding
to the count). The PR body's claim checks out. No test touches the network — the
real adapter's network call is mocked in every test that uses it.

**The wire format** — `test_request_carries_model_key_messages_and_tools` reads the
actual bytes of the outgoing request: address, bearer header, timeout, model,
messages, and the tool's name; `test_no_tools_key_when_no_tools_offered`;
`test_deepseek_uses_its_own_address_and_model`; `test_tool_turns_go_out_in_wire_format`
(an assistant message with a tool call and the answering tool message appear in the
exact shape OpenAI expects); `test_tool_calls_are_parsed_and_bad_arguments_become_none`
(valid JSON parses; broken JSON and a JSON list both become None).

**Failure handling** — `test_http_errors_say_whether_to_retry` runs all five
classes: 400 and 401 not retryable, 429, 500 and 503 retryable;
`test_network_failures_are_retryable` (a wrapped network error and a timeout);
`test_unusable_responses_raise` (HTML instead of JSON, an empty choices list,
nothing at all); `test_missing_key_never_calls_out` proves the urlopen was not
called; `test_repr_hides_the_key`.

**The registry** — `test_built_ins_are_registered_by_name`; the plug-in door in one
test: `test_a_dotted_path_plugs_in_a_new_provider` defines a custom provider in the
test itself and imports it by dotted path; `test_bad_provider_names_are_config_errors`
(blank, unknown, a missing module, and — nicely — `json.dumps`, which imports but
is not a provider); `test_get_provider_defaults_to_fake_in_tests`;
`test_get_provider_reads_model_key_and_timeout`; `test_get_provider_without_a_key_is_a_config_error`;
`test_fake_plays_back_its_script_and_records_calls`.

**The loop** — `test_plain_answer_takes_one_round` (and the token counters);
`test_model_looks_up_then_answers` (the tool ran with the right arguments, the
result reached the model as a tool message, the assistant call carried the right
id); the four staged misbehaviours in `test_bad_calls_are_told_to_the_model_not_run`
— unknown tool, unparseable arguments, unknown argument (an attempted `sql`!), and
missing required argument — flowed back to the model as error messages and the real
function was never called; `test_a_refused_lookup_passes_its_reason_on`;
`test_a_broken_lookup_is_logged_and_hidden` ("secret internals" become "That lookup
failed." with the function name in the log);
`test_long_results_are_cut_to_something_the_model_can_still_read` (the review-branch
version: it checks the answer is still parseable JSON, carries the "narrower" hint,
and keeps a preview — rather than the old test, which only measured length and the
tail of a string);
`test_results_with_dates_and_decimals_serialise` (a date and a decimal amount
survive the JSON round-trip); `test_after_max_rounds_the_model_must_answer_without_tools`
(the tool offer per round is 1, 1, 0); `test_provider_errors_reach_the_caller`
(retrying is the caller's business, not the loop's).

One test worth calling out by name: `test_a_dotted_path_plugs_in_a_new_provider`
is the entire "plug and play" promise in executable form — a vendor added with no
edits to the chatbot, only a string.

## 9. What the review changed

One thing, in `apps/chatbot/loop.py`: an oversized tool result is no longer chopped out
of its own JSON (section 7.5 quotes the fix). The old code kept the *size* down and
broke the *format*, handing the model an unparseable fragment when the contract says a
result. Now it receives a small valid object with an error, a "narrow this" hint and a
preview of what it asked for.

The test that pinned the old behaviour was rewritten rather than deleted, so the
contract "the model always gets parseable JSON" is what the suite now holds.

Everything else is as merged: the provider interface, the two adapters, the fake, the
settings switch, D-075.
