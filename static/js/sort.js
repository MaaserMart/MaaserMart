// The listing's sort control (D-053).
//
// A changed dropdown applies at once, and Enter in it does the same. Both paths
// submit the form with no submitter, so no `direction` value is sent and the
// server uses the chosen mechanism's default direction. Without this script the
// browser's implicit submission would click the first direction button (always
// ascending) and the two-click flow would apply the new order only on the second
// click. The direction buttons keep working on their own with no script at all.

(function () {
  "use strict";

  function sortSelect(node) {
    return (
      node instanceof HTMLSelectElement &&
      node.form !== null &&
      node.form.matches("form[data-sort-form]")
    );
  }

  document.addEventListener("change", function (event) {
    if (sortSelect(event.target)) {
      event.target.form.submit();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && sortSelect(event.target)) {
      event.preventDefault();
      event.target.form.submit();
    }
  });
})();
