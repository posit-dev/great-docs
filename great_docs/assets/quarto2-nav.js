/**
 * Quarto 2 (experimental): announce the navbar offset changes
 *
 * Quarto 1's quarto-nav.js fires `quarto-hrChanged` each time it moves the page and its
 * sidebars below the navbar, and Great Docs' scripts listen for it to place the floating
 * sidebar and the skill switcher again. Quarto 2's quarto-nav.js moves them the same way
 * but fires no event. It records each move in the body's `data-bs-offset` and `style`
 * attributes, so this script fires the event when those change.
 */
(function () {
  "use strict";

  var observer = new MutationObserver(function () {
    window.dispatchEvent(new CustomEvent("quarto-hrChanged", { detail: {} }));
  });
  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-bs-offset", "style"],
  });
})();
