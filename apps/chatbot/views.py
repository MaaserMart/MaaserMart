"""The chatbot panel's HTMX endpoints (§6.3.2, §7: a panel, not a page)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import services

# The session keeps the last few exchanges, so a follow-up has its context.
HISTORY_KEY = "chatbot_history"
HISTORY_TURNS = 6


def _history(request: HttpRequest) -> list[dict]:
    return request.session.get(HISTORY_KEY, [])


@login_required
@require_GET
def panel(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "chatbot/panel.html",
        {"history": _history(request), "max_length": services.MAX_QUESTION_CHARS},
    )


@login_required
@require_POST
def ask(request: HttpRequest) -> HttpResponse:
    question = services.clean_question(request.POST.get("question", ""))
    if not question:
        return render(request, "chatbot/_notice.html", {"notice": "Type a question first."})
    pairs = [(turn["question"], turn["answer"]) for turn in _history(request)]
    try:
        task_id = services.enqueue_question(request.user.pk, question, pairs)
    except services.ChatbotError as exc:
        return render(request, "chatbot/_notice.html", {"question": question, "notice": str(exc)})
    return render(request, "chatbot/_exchange.html", {"question": question, "task_id": task_id})


@login_required
@require_GET
def status(request: HttpRequest, task_id: str) -> HttpResponse:
    found = services.poll_status(request.user.pk, task_id)
    if found is None:
        raise Http404("No such question.")
    if found.state == "answered":
        history = [turn for turn in _history(request) if turn["id"] != task_id]
        history.append({"id": task_id, "question": found.question, "answer": found.answer})
        request.session[HISTORY_KEY] = history[-HISTORY_TURNS:]
    return render(request, "chatbot/_reply.html", {"status": found, "task_id": task_id})


@login_required
@require_POST
def clear(request: HttpRequest) -> HttpResponse:
    request.session.pop(HISTORY_KEY, None)
    return render(request, "chatbot/_notice.html", {"notice": "Conversation cleared."})
