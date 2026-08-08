/**
 * marimo-islands.js — Lazy-loads marimo islands and handles copy-notebook.
 *
 * Attached to pages that use the {{< marimo >}} shortcode.
 * - Uses IntersectionObserver to defer Pyodide boot until islands scroll into view.
 * - Provides "Copy Notebook" button handler.
 * - Syncs marimo's dark theme to the Great Docs site theme (marimo islands read a
 *   `.dark` class on an ancestor element).
 * - Hides the "Initializing…" loader island once the notebook cells have hydrated.
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

  // --- Theme Sync ---
  // marimo islands render in the light DOM and pick up dark styling from a
  // `.dark` class on an ancestor. The Great Docs site signals dark mode via a
  // `quarto-dark` class / `data-bs-theme="dark"` on <html>, so bridge the two.
  function siteIsDark() {
    var el = document.documentElement;
    return (
      el.classList.contains("quarto-dark") ||
      el.getAttribute("data-bs-theme") === "dark"
    );
  }

  function applyTheme() {
    var dark = siteIsDark();
    document.querySelectorAll(".gd-marimo-island-group").forEach(function (group) {
      // Per-shortcode override: data-theme="light" | "dark" | "auto" (default).
      var mode = group.getAttribute("data-theme") || "auto";
      var isDark = mode === "dark" || (mode !== "light" && dark);
      group.classList.toggle("dark", isDark);
    });
  }

  function initThemeSync() {
    if (document.querySelectorAll(".gd-marimo-island-group").length === 0) return;
    applyTheme();
    // React to the site's dark-mode toggle (class / attribute changes on <html>).
    var observer = new MutationObserver(applyTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "data-bs-theme"],
    });
  }

  // --- Hide the "Initializing…" loader once cells hydrate ---
  // marimo's init island renders a spinner that boots the kernel but isn't
  // auto-removed in embedded islands mode. marimo mounts its cells (CodeMirror
  // editors, rendered output) inside shadow DOM, so detection must pierce shadow
  // roots — and shadow mutations don't bubble to a light-DOM observer, so we
  // poll rather than rely on MutationObserver.
  function deepHas(root, selector) {
    if (root.querySelector(selector)) return true;
    var hosts = root.querySelectorAll("*");
    for (var i = 0; i < hosts.length; i++) {
      if (hosts[i].shadowRoot && deepHas(hosts[i].shadowRoot, selector)) return true;
    }
    return false;
  }

  // Inject style fixes into marimo's shadow roots (which our external stylesheet
  // and CSS variables can't reach — CodeMirror's styles in particular live in
  // adopted stylesheets):
  //   1. `.marimo{color:inherit}` — the widget wrapper carries a hardcoded
  //      light-mode text color that marimo's own dark styling never overrides,
  //      so labels (e.g. a slider's) stay dark on a dark site. `!important`
  //      because marimo appends its own rule after ours. Only the container is
  //      forced to inherit; children with their own color are unaffected.
  //   2. Shrink the CodeMirror font — marimo's `.9rem` renders large against the
  //      docs site's root, so code wraps early (worse on mobile / narrow content).
  // Idempotent; recurses into nested roots.
  function injectShadowStyles(root) {
    var els = root.querySelectorAll("*");
    for (var i = 0; i < els.length; i++) {
      var sr = els[i].shadowRoot;
      if (!sr) continue;
      var needed = sr.querySelector(".marimo") || sr.querySelector(".cm-editor");
      if (needed && !sr.querySelector("style[data-gd-marimo-fix]")) {
        var st = document.createElement("style");
        st.setAttribute("data-gd-marimo-fix", "1");
        st.textContent =
          ".marimo{color:inherit!important;}" +
          ".cm-editor,.cm-content,.cm-line,.cm-gutters{font-size:0.78rem!important;}";
        sr.appendChild(st);
      }
      injectShadowStyles(sr);
    }
  }

  // Length of *rendered output* text. marimo renders cell output into shadow
  // roots, so count only shadow-DOM text — this deliberately ignores the cell's
  // hidden source (a light-DOM <marimo-cell-code>), which the runtime strips
  // slightly after boot and which must not count as "has output".
  function renderedTextLen(root) {
    var len = 0;
    var hosts = root.querySelectorAll("*");
    for (var i = 0; i < hosts.length; i++) {
      var sr = hosts[i].shadowRoot;
      if (sr) len += (sr.textContent || "").trim().length + renderedTextLen(sr);
    }
    return len;
  }

  function groupHasHydrated(group) {
    // A code editor mounted (code visible) …
    if (deepHas(group, ".cm-editor")) return true;
    // … or a reactive cell rendered marimo output (no-code mode). marimo output
    // lands in an element carrying the `marimo` class once hydrated.
    var cells = group.querySelectorAll('marimo-island[data-reactive="true"]');
    for (var i = 0; i < cells.length; i++) {
      if (deepHas(cells[i], ".markdown, .prose, table, img, .cm-editor")) return true;
    }
    return false;
  }

  // In no-code mode, utility cells (e.g. `import marimo as mo`) are kept in the
  // markup so the reactive kernel can run them, but render no visible output.
  // Once cells have settled, collapse islands that produced neither text nor an
  // interactive widget so they don't show as empty boxes. Cells that render only
  // a widget (e.g. a bare slider) have no text but must be kept.
  function pruneEmptyNocodeCells(group) {
    if (!group.classList.contains("gd-marimo-nocode")) return;
    group
      .querySelectorAll('marimo-island[data-reactive="true"]')
      .forEach(function (island) {
        var hasText = renderedTextLen(island) > 0;
        var hasWidget = deepHas(
          island,
          "input, button, select, textarea, [role=slider], canvas, svg, img, table"
        );
        if (!hasText && !hasWidget) island.style.display = "none";
      });
  }

  // Collapse the "setup" cells behind a disclosure toggle so the boilerplate
  // doesn't clutter the notebook. Setup cells are tagged at build time with
  // `data-gd-setup` (where emptiness is authoritative — no render race) and
  // hidden by CSS from first paint; this just wires up the reveal toggle.
  // No-op in no-code mode (which prunes these cells entirely).
  function wireSetupToggle(group) {
    if (group.classList.contains("gd-marimo-nocode")) return;
    if (group.classList.contains("gd-marimo-setup-done")) return;
    var setupCells = group.querySelectorAll("marimo-island[data-gd-setup]");
    if (setupCells.length === 0) return;
    group.classList.add("gd-marimo-setup-done");

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "gd-marimo-setup-toggle";
    toggle.setAttribute("aria-expanded", "false");
    var label = setupCells.length > 1 ? "Setup (" + setupCells.length + " cells)" : "Setup";
    toggle.innerHTML =
      '<svg class="gd-marimo-setup-chevron" xmlns="http://www.w3.org/2000/svg"' +
      ' width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"' +
      ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
      '<polyline points="9 18 15 12 9 6"/></svg><span></span>';
    toggle.querySelector("span").textContent = label;
    toggle.addEventListener("click", function () {
      var open = group.classList.toggle("gd-marimo-setup-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    setupCells[0].parentNode.insertBefore(toggle, setupCells[0]);
  }

  // Reveal a group's cells and drop its loader. Called once the notebook has
  // settled (or as a timeout fallback so a failed boot still shows something).
  function revealGroup(group, loaderIsland) {
    if (loaderIsland) loaderIsland.style.display = "none";
    group.classList.add("gd-marimo-ready");
  }

  function initPostHydrationCleanup() {
    document.querySelectorAll(".gd-marimo-island-group").forEach(function (group) {
      // Capture the loader island now, while its spinner is present: the runtime
      // may clear the spinner before we hide it, and the empty island would then
      // linger as a tall blank box above the content.
      var spinner = group.querySelector(".animate-spin");
      var loaderIsland = spinner ? spinner.closest("marimo-island") : null;
      if (loaderIsland) loaderIsland.classList.add("gd-marimo-loader");
      // Enter the loading state: CSS hides the assembling cells (reserving space)
      // and centers the loader, so readers don't see cells shuffle/collapse as
      // widgets mount. Added via JS so no-JS/failed-boot still shows static output.
      group.classList.add("gd-marimo-booting");

      // Wire the setup-collapse toggle up-front: the setup cells are tagged at
      // build time and hidden by CSS already, so this is race-free.
      wireSetupToggle(group);

      var elapsed = 0;
      var settled = false;
      var timer = setInterval(function () {
        elapsed += 500;
        // Re-apply on every tick: marimo mounts widget shadow roots lazily as
        // cells execute, so late-mounted sliders/labels still get themed. The
        // injection is idempotent, so repeating is cheap.
        injectShadowStyles(group);
        if (!settled && groupHasHydrated(group)) {
          settled = true;
          // Let widgets finish mounting, then prune empty cells and reveal.
          setTimeout(function () {
            injectShadowStyles(group);
            pruneEmptyNocodeCells(group);
            revealGroup(group, loaderIsland);
          }, 1500);
        }
        if (elapsed >= 30000) {
          // Fallback: never leave cells hidden if boot stalls.
          revealGroup(group, loaderIsland);
          clearInterval(timer);
        }
      }, 500);
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
  function init() {
    initCopyButtons();
    initThemeSync();
    initPostHydrationCleanup();
    initLazyLoad();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
