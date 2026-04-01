/**
 * Navbar Gradient Style for Great Docs
 *
 * Reads the gd-navbar-style meta tag and applies the corresponding
 * animated gradient CSS class to the navbar element.
 */
(function () {
  "use strict";

  var meta = document.querySelector('meta[name="gd-navbar-style"]');
  if (!meta) return;

  var preset = meta.getAttribute("data-preset") || "";
  if (!preset) return;

  var navbar = document.querySelector(".navbar");
  if (navbar) {
    navbar.classList.add("gd-gradient-" + preset);
  }
})();

/**
 * Sticky navbar on desktop — keep sidebars positioned below the header.
 *
 * Quarto's headroom.js hides the navbar on scroll-down and shifts sidebars
 * (top: 0) to fill the vacated space. Our CSS keeps the navbar visible on
 * desktop (>= 992px), so we must also prevent the sidebar repositioning.
 * Listens for the quarto-hrChanged event that fires after every headroom
 * pin/unpin and re-applies the correct sidebar top/maxHeight.
 */
(function () {
  "use strict";

  var mql = window.matchMedia("(min-width: 992px)");

  function fixSidebars() {
    if (!mql.matches) return;

    var header = document.querySelector("#quarto-header");
    if (!header) return;
    var h = header.offsetHeight;

    var els = document.querySelectorAll(".sidebar, .headroom-target");
    els.forEach(function (el) {
      el.style.top = h + "px";
      el.style.maxHeight = "calc(100vh - " + h + "px)";
    });
  }

  window.addEventListener("quarto-hrChanged", fixSidebars);
  mql.addEventListener("change", fixSidebars);
})();

/**
 * Move the footer inside #quarto-content on desktop so sticky sidebars
 * remain pinned through the footer region.
 *
 * Sticky positioning is bounded by the parent container. Because the footer
 * lives outside #quarto-content, the sidebars unstick when the container
 * ends. Moving the footer inside extends the grid rows, keeping the
 * sidebars' sticky context active through the footer.
 */
(function () {
  "use strict";

  var mql = window.matchMedia("(min-width: 992px)");
  var moved = false;
  var originalParent = null;
  var originalNext = null;

  function update() {
    var content = document.getElementById("quarto-content");
    var footer = document.querySelector("footer.footer");
    if (!content || !footer) return;

    if (mql.matches && !moved) {
      // Remember original position so we can restore on mobile
      originalParent = footer.parentNode;
      originalNext = footer.nextSibling;
      // Move footer inside the grid container, spanning all columns
      footer.style.gridColumn = "1 / -1";
      content.appendChild(footer);
      moved = true;
    } else if (!mql.matches && moved) {
      // Restore footer to its original position for mobile
      footer.style.gridColumn = "";
      if (originalNext) {
        originalParent.insertBefore(footer, originalNext);
      } else {
        originalParent.appendChild(footer);
      }
      moved = false;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", update);
  } else {
    update();
  }
  mql.addEventListener("change", update);
})();

/**
 * Collect navbar action widgets (search, dark-mode toggle, GitHub icon)
 * into a single flex container for consistent alignment and spacing.
 *
 * Each widget lives in a different part of the Quarto-generated DOM:
 *   - #quarto-search: outside #navbarCollapse
 *   - dark-mode toggle: JS-injected <li> inside ul.ms-auto
 *   - GitHub icon: <li class="nav-item compact"> inside ul.ms-auto
 *   - GitHub widget: <li> wrapping #github-widget inside ul.ms-auto
 *
 * This IIFE moves them into a shared #gd-navbar-widgets container placed
 * after #navbarCollapse for uniform flex alignment on desktop.
 */
(function () {
  "use strict";

  function collect() {
    var containerFluid = document.querySelector(".navbar .container-fluid");
    if (!containerFluid) return;

    // Don't run twice
    if (document.getElementById("gd-navbar-widgets")) return;

    var wrapper = document.createElement("div");
    wrapper.id = "gd-navbar-widgets";

    // 1. Keyboard shortcuts button (unwrap from its <li>)
    var kbContainer = document.getElementById('gd-keyboard-btn-container');
    if (kbContainer) {
      var kbLi = kbContainer.closest('li.nav-item');
      wrapper.appendChild(kbContainer);
      if (kbLi && !kbLi.hasChildNodes()) kbLi.remove();
    }

    // 2. Dark-mode toggle (unwrap from its <li>)
    var toggleContainer = document.getElementById("dark-mode-toggle-container");
    if (toggleContainer) {
      var li = toggleContainer.closest("li.nav-item");
      wrapper.appendChild(toggleContainer);
      if (li && !li.hasChildNodes()) li.remove();
    }

    // 3. GitHub icon – compact nav-item (unwrap the <a> from its <li>)
    var compactItem = containerFluid.querySelector(
      "#navbarCollapse .nav-item.compact"
    );
    if (compactItem) {
      var link = compactItem.querySelector(".nav-link");
      if (link) {
        // Mark the extracted link so CSS can target it without the .nav-item.compact parent
        link.classList.add("gd-navbar-icon");
        wrapper.appendChild(link);
        compactItem.remove();
      }
    }

    // 4. GitHub widget – #github-widget (unwrap from its <li>)
    var ghWidget = document.getElementById("github-widget");
    if (ghWidget) {
      var ghLi = ghWidget.closest("li.nav-item");
      wrapper.appendChild(ghWidget);
      if (ghLi && !ghLi.hasChildNodes()) ghLi.remove();
    }

    // 5. Search button
    var search = document.getElementById("quarto-search");
    if (search) wrapper.appendChild(search);

    // Remove the now-empty ul.ms-auto (or one left with only empty items)
    var msAuto = containerFluid.querySelector(
      "#navbarCollapse .navbar-nav.ms-auto"
    );
    if (msAuto) {
      // Remove child <li> items that have no meaningful content
      Array.prototype.forEach.call(msAuto.querySelectorAll('li.nav-item'), function (li) {
        if (!li.textContent.trim() && !li.querySelector('button, input, img, svg')) {
          li.remove();
        }
      });
      if (msAuto.children.length === 0) msAuto.remove();
    }

    // Place inside .quarto-navbar-tools (the rightmost navbar slot)
    var tools = containerFluid.querySelector(".quarto-navbar-tools");
    if (tools) {
      tools.appendChild(wrapper);
    } else {
      // Fallback: append to container-fluid
      containerFluid.appendChild(wrapper);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", collect);
  } else {
    collect();
  }
})();
