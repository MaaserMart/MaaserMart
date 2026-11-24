// The chatbot panel (D-076). Production's CSP allows no inline script, so the
// panel's one bit of behaviour lives here: empty the question box once it has
// been sent, and keep the newest message in view.

(function () {
  "use strict";

  document.addEventListener("htmx:afterRequest", function (event) {
    var form = event.detail.elt;
    if (form instanceof HTMLFormElement && form.matches("form[data-chat-form]") &&
        event.detail.successful) {
      form.reset();
    }
  });

  document.addEventListener("htmx:afterSwap", function () {
    var log = document.getElementById("chat-log");
    if (log) {
      log.scrollTop = log.scrollHeight;
    }
  });

  // Enter sends; Shift+Enter starts a new line.
  document.addEventListener("keydown", function (event) {
    var box = event.target;
    if (event.key === "Enter" && !event.shiftKey && box instanceof HTMLTextAreaElement &&
        box.form && box.form.matches("form[data-chat-form]")) {
      event.preventDefault();
      box.form.requestSubmit();
    }
  });
})();
