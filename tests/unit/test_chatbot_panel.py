"""The chatbot panel: job store, services, task, lookups and views (§6.3.2, §7, D-076)."""

import time
from unittest import mock

import pytest
from django.template import Context, Template
from django.test import override_settings
from django.urls import reverse

from apps.charities import services as charity_services
from apps.chatbot import jobs, lookups, services, tasks, views
from apps.chatbot.loop import ToolError
from apps.chatbot.providers import FakeProvider, ProviderError, Reply, ToolCall
from apps.chatbot.templatetags.chat_text import chat_text
from tests.factories import CharityFactory, TransactionFactory, UserFactory
from tests.factories.accounts import DEFAULT_PASSWORD
from tests.factories.charities import CharityDomainFactory, DomainFactory

pytestmark = pytest.mark.django_db

PANEL = reverse("chatbot:panel")
ASK = reverse("chatbot:ask")
CLEAR = reverse("chatbot:clear")


def status_url(task_id):
    return reverse("chatbot:status", args=[task_id])


@pytest.fixture
def member(client):
    user = UserFactory()
    client.login(username=user.username, password=DEFAULT_PASSWORD)
    return user


@pytest.fixture
def scripted():
    """Run the task against a FakeProvider whose replies the test chooses."""

    def install(*steps):
        provider = FakeProvider(script=steps)
        patcher = mock.patch.object(tasks, "get_provider", return_value=provider)
        patcher.start()
        return provider, patcher

    started = []

    def run(*steps):
        provider, patcher = install(*steps)
        started.append(patcher)
        return provider

    yield run
    for patcher in started:
        patcher.stop()


# --- chat_text ---------------------------------------------------------------


class TestChatText:
    def test_escapes_html(self):
        assert "<script>" not in chat_text("<script>alert(1)</script>")
        assert "&lt;script&gt;" in chat_text("<script>alert(1)</script>")

    def test_links_a_charity_page(self):
        assert '<a href="/charity/12/">/charity/12/</a>' in chat_text("See /charity/12/ now.")

    def test_links_sefaria_but_not_trailing_punctuation(self):
        html = chat_text("Source: https://www.sefaria.org/Shulchan_Arukh,_Yoreh_De'ah.249.1.")
        assert 'href="https://www.sefaria.org/Shulchan_Arukh,_Yoreh_De&#x27;ah.249.1"' in html
        assert 'rel="noopener noreferrer"' in html

    def test_leaves_other_urls_as_text(self):
        html = chat_text("Go to https://evil.example/charity/1/ or http://x.test")
        assert "<a" not in html

    def test_cannot_break_out_of_the_attribute(self):
        html = chat_text('https://www.sefaria.org/a"onmouseover="x')
        assert 'onmouseover="' not in html

    def test_paragraphs_and_empty(self):
        assert chat_text("one\n\ntwo").count("<p>") == 2
        assert chat_text(None) == ""

    def test_usable_in_a_template(self):
        out = Template("{% load chat_text %}{{ v|chat_text }}").render(Context({"v": "<b>"}))
        assert "&lt;b&gt;" in out


# --- jobs --------------------------------------------------------------------


class TestJobs:
    def test_lifecycle(self):
        job_id = jobs.create(7, "Hi?")
        job = jobs.get(job_id)
        assert (job.user_id, job.question, job.state) == (7, "Hi?", jobs.PENDING)
        jobs.answer(job_id, "Hello")
        assert (jobs.get(job_id).state, jobs.get(job_id).answer) == (jobs.ANSWERED, "Hello")
        jobs.fail(job_id)
        assert jobs.get(job_id).state == jobs.FAILED
        jobs.delete(job_id)
        assert jobs.get(job_id) is None

    def test_unknown_and_empty_ids(self):
        assert jobs.get("nope") is None
        assert jobs.get("") is None
        jobs.answer("nope", "x")  # settling a vanished job is a no-op

    def test_counts_uses_per_user(self):
        assert jobs.uses_today(1) == 0
        assert jobs.count_use(1) == 1
        assert jobs.count_use(1) == 2
        assert jobs.uses_today(1) == 2
        assert jobs.uses_today(2) == 0


# --- services ----------------------------------------------------------------


class TestServices:
    def test_clean_question(self):
        assert services.clean_question("  a \n b  ") == "a b"
        assert len(services.clean_question("x" * 5000)) == services.MAX_QUESTION_CHARS
        assert services.clean_question(None) == ""

    def test_enqueue_answers_and_counts(self, scripted):
        scripted(Reply(text="Give generously."))
        task_id = services.enqueue_question(5, "How much?")
        status = services.poll_status(5, task_id)
        assert (status.state, status.answer, status.done) == ("answered", "Give generously.", True)
        assert jobs.uses_today(5) == 1

    def test_enqueue_sends_history(self, scripted):
        provider = scripted(Reply(text="ok"))
        services.enqueue_question(5, "And then?", [("First?", "First answer")])
        sent = provider.calls[0][0]
        assert [(m.role, m.content) for m in sent[1:]] == [
            ("user", "First?"),
            ("assistant", "First answer"),
            ("user", "And then?"),
        ]
        assert sent[0].role == "system"

    @override_settings(CHATBOT_DAILY_LIMIT=1)
    def test_daily_limit(self, scripted, caplog):
        caplog.set_level("INFO")
        scripted(Reply(text="ok"))
        services.enqueue_question(5, "One")
        with pytest.raises(services.LimitReached, match="reached the chatbot limit"):
            services.enqueue_question(5, "Two")
        assert "limit reached" in caplog.text

    def test_queue_failure(self, caplog):
        with mock.patch.object(tasks.answer_question, "delay", side_effect=OSError("down")):
            with pytest.raises(services.SubmitFailed, match="Could not submit"):
                services.enqueue_question(5, "Q")
        assert jobs.uses_today(5) == 0
        assert "could not be queued" in caplog.text

    def test_unknown_or_foreign_task(self, caplog):
        job_id = jobs.create(5, "Q")
        assert services.poll_status(6, job_id) is None
        assert services.poll_status(5, "missing") is None
        assert "unknown or foreign" in caplog.text

    @override_settings(CHATBOT_ANSWER_SECONDS=10)
    def test_a_stale_pending_job_fails(self, caplog):
        job_id = jobs.create(5, "Q")
        with mock.patch.object(services.time, "time", return_value=time.time() + 60):
            assert services.poll_status(5, job_id).state == "failed"
        assert jobs.get(job_id).state == jobs.FAILED
        assert "worker running" in caplog.text

    def test_a_fresh_pending_job_waits(self):
        job_id = jobs.create(5, "Q")
        status = services.poll_status(5, job_id)
        assert (status.state, status.done) == ("pending", False)


# --- task --------------------------------------------------------------------


class TestTask:
    def test_retries_a_retryable_error_then_answers(self, scripted):
        provider = scripted(ProviderError("timeout", retryable=True), Reply(text="Answer"))
        job_id = jobs.create(5, "Q")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "Q"]]])
        assert (jobs.get(job_id).state, jobs.get(job_id).answer) == (jobs.ANSWERED, "Answer")
        assert len(provider.calls) == 2

    def test_gives_up_after_the_retries(self, scripted, caplog):
        error = ProviderError("timeout", retryable=True)
        scripted(error, error, error, error)
        job_id = jobs.create(5, "Q")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "Q"]]], retries=tasks.MAX_RETRIES)
        assert jobs.get(job_id).state == jobs.FAILED
        assert "could not get an answer" in caplog.text

    def test_a_permanent_error_fails_at_once(self, scripted):
        provider = scripted(ProviderError("bad key", status=401), Reply(text="never"))
        job_id = jobs.create(5, "Q")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "Q"]]])
        assert jobs.get(job_id).state == jobs.FAILED
        assert len(provider.calls) == 1

    @override_settings(CHATBOT_PROVIDER="openai", OPENAI_API_KEY="")
    def test_missing_configuration_fails(self, caplog):
        job_id = jobs.create(5, "Q")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "Q"]]])
        assert jobs.get(job_id).state == jobs.FAILED
        assert "not configured" in caplog.text

    def test_an_empty_answer_fails(self, scripted):
        scripted(Reply(text=""))
        job_id = jobs.create(5, "Q")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "Q"]]])
        assert jobs.get(job_id).state == jobs.FAILED

    def test_logs_use_without_the_text(self, scripted, caplog):
        caplog.set_level("INFO")
        scripted(
            Reply(tool_calls=(ToolCall("c1", "list_domains", {}),)),
            Reply(text="secret answer"),
        )
        job_id = jobs.create(5, "secret question")
        tasks.answer_question.apply(args=[job_id, 5, [["user", "secret question"]]])
        assert "Chatbot use: user=5 provider=fake rounds=2 tools=list_domains" in caplog.text
        assert "secret" not in caplog.text


# --- lookups and the charity services they call -------------------------------


class TestLookups:
    def test_search_by_domain(self):
        wanted = CharityDomainFactory(domain=DomainFactory(name="Hachnasas Kallah")).charity
        CharityFactory()
        found = lookups.search_charities(domain="kallah")
        assert [c["id"] for c in found] == [wanted.id]
        assert found[0]["page"] == f"/charity/{wanted.id}/"
        assert found[0]["domains"] == ["Hachnasas Kallah"]

    def test_unknown_domain_finds_nothing(self):
        CharityDomainFactory()
        assert charity_services.search_charities(domain="no such cause") == ()

    def test_search_by_name_and_limit(self):
        for n in range(7):
            CharityFactory(name=f"Yad Eliezer {n}")
        CharityFactory(name="Other")
        found = lookups.search_charities(query="eliezer")
        assert len(found) == charity_services.CHAT_RESULT_LIMIT
        assert all("Eliezer" in c["name"] for c in found)

    def test_get_charity(self):
        charity = CharityFactory(description="x" * 5000)
        found = lookups.get_charity(charity.id)
        assert found["name"] == charity.name
        assert len(found["description"]) <= lookups.DESCRIPTION_CHARS + 1

    def test_get_missing_charity(self):
        with pytest.raises(ToolError):
            lookups.get_charity(999999)
        assert charity_services.get_charity("abc") is None

    def test_list_domains(self):
        DomainFactory(name="Torah")
        assert "Torah" in lookups.list_domains()

    def test_my_maaser_is_bound_to_the_member(self):
        user, other = UserFactory(), UserFactory()
        TransactionFactory(user=other, type="income", amount=1000)
        mine = {f.tool.name: f for f in lookups.functions_for(user.id)}["my_maaser"]
        assert mine.run()["income_recorded"] == 0
        assert mine.tool.parameters.get("properties", {}) == {}


# --- views -------------------------------------------------------------------


class TestViews:
    def test_guests_are_sent_to_log_in(self, client):
        for response in (client.get(PANEL), client.post(ASK, {"question": "Q"})):
            assert response.status_code == 302

    def test_panel(self, client, member):
        response = client.get(PANEL)
        assert response.status_code == 200
        assert b"data-chat-form" in response.content

    def test_ask_and_poll(self, client, member, scripted):
        scripted(Reply(text="See /charity/3/."))
        response = client.post(ASK, {"question": "  Which   charity? "})
        assert response.status_code == 200
        body = response.content.decode()
        assert "Which charity?" in body and "Thinking" in body
        task_id = body.split("/chatbot/status/")[1].split("/")[0]
        reply = client.get(status_url(task_id)).content.decode()
        assert '<a href="/charity/3/">' in reply
        assert client.session[views.HISTORY_KEY] == [
            {"id": task_id, "question": "Which charity?", "answer": "See /charity/3/."}
        ]
        client.get(status_url(task_id))  # a repeated poll does not duplicate
        assert len(client.session[views.HISTORY_KEY]) == 1
        assert "Which charity?" in client.get(PANEL).content.decode()

    def test_pending_keeps_polling(self, client, member):
        job_id = jobs.create(member.pk, "Q")
        body = client.get(status_url(job_id)).content.decode()
        assert 'hx-trigger="load delay:1s"' in body

    def test_failed(self, client, member):
        job_id = jobs.create(member.pk, "Q")
        jobs.fail(job_id)
        assert "couldn't get an answer" in client.get(status_url(job_id)).content.decode()

    def test_empty_question(self, client, member):
        assert "Type a question first" in client.post(ASK, {"question": " "}).content.decode()

    @override_settings(CHATBOT_DAILY_LIMIT=0)
    def test_limit_notice(self, client, member):
        body = client.post(ASK, {"question": "Q"}).content.decode()
        assert "reached the chatbot limit" in body

    def test_another_members_task_is_404(self, client, member):
        job_id = jobs.create(member.pk + 1000, "Q")
        assert client.get(status_url(job_id)).status_code == 404

    def test_history_is_capped(self, client, member, scripted):
        scripted(*[Reply(text=f"A{n}") for n in range(views.HISTORY_TURNS + 2)])
        for n in range(views.HISTORY_TURNS + 2):
            body = client.post(ASK, {"question": f"Q{n}"}).content.decode()
            client.get(status_url(body.split("/chatbot/status/")[1].split("/")[0]))
        history = client.session[views.HISTORY_KEY]
        assert len(history) == views.HISTORY_TURNS
        assert history[-1]["answer"] == f"A{views.HISTORY_TURNS + 1}"

    def test_clear(self, client, member, scripted):
        scripted(Reply(text="A"))
        body = client.post(ASK, {"question": "Q"}).content.decode()
        client.get(status_url(body.split("/chatbot/status/")[1].split("/")[0]))
        assert "Conversation cleared" in client.post(CLEAR).content.decode()
        assert views.HISTORY_KEY not in client.session

    def test_wrong_methods(self, client, member):
        assert client.get(ASK).status_code == 405
        assert client.post(PANEL).status_code == 405


class TestCornerPanel:
    def test_members_get_the_corner_panel(self, client, member):
        body = client.get(reverse("tools:index")).content.decode()
        assert f'hx-get="{PANEL}"' in body
        assert "js/chat.js" in body and "js/retry.js" in body

    def test_guests_do_not(self, client):
        body = client.get(reverse("charities:listing")).content.decode()
        assert 'class="chatbot"' not in body
        assert "js/chat.js" not in body
