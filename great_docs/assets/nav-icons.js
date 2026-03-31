/**
 * Navigation Icons for Great Docs
 *
 * Reads a JSON icon map from a <script id="gd-nav-icons-data"> element
 * and prepends inline SVG icons to matching navbar and sidebar entries.
 *
 * The icon map is emitted by the Python build pipeline and has the shape:
 *   { "navbar": { "Label": "<svg .../>", ... },
 *     "sidebar": { "Label": "<svg .../>", ... } }
 */
(function () {
  "use strict";

  /**
   * Inject an SVG icon before the text of a navigation link.
   *
   * @param {Element} menuText - The .menu-text span element.
   * @param {string} svgHtml - The inline SVG markup to prepend.
   */
  function injectIcon(menuText, svgHtml) {
    // Avoid double-injection on re-runs
    if (menuText.querySelector(".gd-nav-icon")) return;

    // Create a temporary container to parse the SVG string
    var wrapper = document.createElement("span");
    wrapper.innerHTML = svgHtml;
    var svg = wrapper.firstElementChild;
    if (!svg) return;

    menuText.insertBefore(svg, menuText.firstChild);
  }

  /**
   * Process a set of navigation items, matching by their text content.
   *
   * @param {string} selector - CSS selector to find .menu-text elements.
   * @param {Object} mapping - Label -> SVG HTML mapping.
   */
  function processNavItems(selector, mapping) {
    if (!mapping || typeof mapping !== "object") return;

    var items = document.querySelectorAll(selector);
    items.forEach(function (el) {
      // Get the trimmed text content (may include child node text)
      var text = el.textContent.trim();
      if (mapping[text]) {
        injectIcon(el, mapping[text]);
      }
    });
  }

  function run() {
    var dataEl = document.getElementById("gd-nav-icons-data");
    if (!dataEl) return;

    var iconMap;
    try {
      iconMap = JSON.parse(dataEl.textContent);
    } catch (_) {
      return;
    }
    if (!iconMap) return;

    // Process navbar items: look for .navbar .menu-text spans
    processNavItems(".navbar .nav-link > .menu-text", iconMap.navbar || {});

    // Process sidebar items: look for .sidebar .menu-text spans
    // This covers sidebar section titles and individual items
    processNavItems(
      "#quarto-sidebar .sidebar-item .menu-text",
      iconMap.sidebar || {}
    );

    // Also handle sidebar section headers (the collapsible section titles)
    processNavItems(
      "#quarto-sidebar .sidebar-item-section .sidebar-item-text",
      iconMap.sidebar || {}
    );
  }

  // Run after DOM is ready so that other scripts (e.g. sidebar-wrap.js)
  // that also use DOMContentLoaded have already processed the sidebar.
  // Listeners fire in registration order, and sidebar-wrap.js is loaded
  // earlier in include-after-body, so its handler runs first.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
