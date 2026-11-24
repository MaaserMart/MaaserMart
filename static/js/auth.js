// The password eye and the signup code boxes (D-YOSEF-csp-widgets).
//
// Plain script, not Alpine: production's Content-Security-Policy forbids
// eval, and Alpine's regular build evaluates its attribute expressions with
// it. Without this script the password stays a password box and the code is
// typed into one plain field, so both pages still work.

(function () {
  "use strict";

  function setUpPassword(wrapper) {
    const input = wrapper.querySelector("input");
    const button = wrapper.querySelector(".password__toggle");
    const showIcon = button.querySelector('[data-icon="show"]');
    const hideIcon = button.querySelector('[data-icon="hide"]');
    button.hidden = false;
    button.addEventListener("click", function () {
      const shown = input.type === "password";
      input.type = shown ? "text" : "password";
      button.setAttribute("aria-pressed", String(shown));
      button.setAttribute("aria-label", shown ? "Hide password" : "Show password");
      showIcon.toggleAttribute("hidden", shown);
      hideIcon.toggleAttribute("hidden", !shown);
      input.focus();
    });
  }

  // Six boxes like a one-time-code field: typing moves on, backspace moves
  // back, pasting "482917" fills them all, and a full code submits itself.
  function setUpCodeBoxes(form) {
    const group = form.querySelector(".code");
    const field = form.querySelector("[data-code-field]");
    const code = field.querySelector("input");
    const length = Number(group.dataset.length);
    const boxes = [];

    function sync() {
      code.value = boxes.map((box) => box.value).join("");
      if (code.value.length === length) form.requestSubmit();
    }

    function fill(start, text) {
      const digits = text.replace(/\D/g, "").slice(0, length - start).split("");
      digits.forEach((d, n) => {
        boxes[start + n].value = d;
      });
      boxes[Math.min(start + digits.length, length - 1)].focus();
      sync();
    }

    for (let i = 0; i < length; i++) {
      const box = document.createElement("input");
      box.className = "code__box";
      box.type = "text";
      box.inputMode = "numeric";
      box.autocomplete = i === 0 ? "one-time-code" : "off";
      box.setAttribute("aria-label", "Digit " + (i + 1));
      box.addEventListener("input", function () {
        const typed = box.value;
        box.value = "";
        if (/\d/.test(typed)) fill(i, typed);
        else sync();
      });
      box.addEventListener("keydown", function (event) {
        if (event.key === "Backspace" && !box.value && i > 0) {
          boxes[i - 1].value = "";
          boxes[i - 1].focus();
          sync();
          event.preventDefault();
        } else if (event.key === "ArrowLeft" && i > 0) boxes[i - 1].focus();
        else if (event.key === "ArrowRight" && i < length - 1) boxes[i + 1].focus();
      });
      box.addEventListener("paste", function (event) {
        event.preventDefault();
        fill(i, event.clipboardData.getData("text"));
      });
      box.addEventListener("focus", function () {
        box.select();
      });
      boxes.push(box);
      group.appendChild(box);
    }

    code.removeAttribute("autofocus");
    field.hidden = true;
    group.hidden = false;
    boxes[0].focus();
  }

  function setUp() {
    document.querySelectorAll(".password").forEach(setUpPassword);
    document.querySelectorAll("form[data-code-form]").forEach(setUpCodeBoxes);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setUp);
  else setUp();
})();
