// The network retry indicator (D-035). When an htmx request cannot reach the
// server at all (no response, not an error page), say so and try again for a
// few seconds before giving up. Server errors are answered by the server's own
// pages and messages, so they are not retried here.

(function () {
  "use strict";

  var RETRY_FOR_MS = 5000;
  var RETRY_EVERY_MS = 1000;
  var banner = null;

  function show(text) {
    if (!banner) {
      banner = document.createElement("p");
      banner.className = "net-status";
      banner.setAttribute("role", "status");
      document.body.appendChild(banner);
    }
    banner.textContent = text;
    banner.hidden = false;
  }

  function hide() {
    if (banner) {
      banner.hidden = true;
    }
  }

  document.addEventListener("htmx:sendError", function (event) {
    var detail = event.detail;
    var config = detail.requestConfig || {};
    var started = detail.elt._netRetryStarted || Date.now();
    if (Date.now() - started > RETRY_FOR_MS) {
      detail.elt._netRetryStarted = null;
      show("Couldn't reach MaaserMart. Check your connection and try again.");
      return;
    }
    detail.elt._netRetryStarted = started;
    show("Connecting…");
    window.setTimeout(function () {
      window.htmx.ajax(config.verb.toUpperCase(), config.path, {
        source: detail.elt,
        target: detail.target,
        // The source element supplies its own values and CSRF token again.
        swap: detail.elt.getAttribute("hx-swap") || undefined
      });
    }, RETRY_EVERY_MS);
  });

  document.addEventListener("htmx:afterRequest", function (event) {
    if (event.detail.successful) {
      event.detail.elt._netRetryStarted = null;
      hide();
    }
  });
})();
