/**
 * marimo-islands.js — Lazy-loads marimo islands and handles copy-notebook.
 *
 * Attached to pages that use the {{< marimo >}} shortcode.
 * - Uses IntersectionObserver to defer Pyodide boot until islands scroll into view.
 * - Provides "Copy Notebook" button handler.
 */
(function () {
  "use strict";

  // --- Copy Notebook Handler ---
  function initCopyButtons() {
    document.querySelectorAll(".gd-marimo-copy-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var group = btn.closest(".gd-marimo-island-group");
        if (!group) return;
        var sourceEl = group.querySelector("script.gd-marimo-source");
        if (!sourceEl) return;

        var text = sourceEl.textContent;
        navigator.clipboard.writeText(text).then(function () {
          var original = btn.innerHTML;
          btn.innerHTML =
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied!';
          btn.classList.add("gd-marimo-copied");
          setTimeout(function () {
            btn.innerHTML = original;
            btn.classList.remove("gd-marimo-copied");
          }, 2000);
        });
      });
    });
  }

  // --- Lazy-Load Islands Runtime ---
  var runtimeLoaded = false;

  function loadIslandsRuntime() {
    if (runtimeLoaded) return;
    runtimeLoaded = true;

    // The actual marimo islands JS/CSS is loaded via <head> tags injected by
    // the build pipeline. Once those are present, the custom elements
    // (<marimo-island>) self-initialize. This function just marks that we've
    // triggered observation. The CDN script handles the rest.
    document.querySelectorAll(".gd-marimo-island-group").forEach(function (group) {
      group.classList.add("gd-marimo-active");
    });
  }

  function initLazyLoad() {
    var groups = document.querySelectorAll(".gd-marimo-island-group");
    if (groups.length === 0) return;

    if (!("IntersectionObserver" in window)) {
      // Fallback: load immediately
      loadIslandsRuntime();
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) {
            loadIslandsRuntime();
            observer.disconnect();
            return;
          }
        }
      },
      { rootMargin: "200px" }
    );

    groups.forEach(function (group) {
      observer.observe(group);
    });
  }

  // --- Init ---
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initCopyButtons();
      initLazyLoad();
    });
  } else {
    initCopyButtons();
    initLazyLoad();
  }
})();
