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

/* Widget collection is handled by navbar-widgets.js (always loaded). */

/**
 * Mobile sidebar toggle → menu overlay redirect.
 *
 * On mobile (< 992px) the sidebar toggle button in the Title Bar
 * (.quarto-btn-toggle) opens the polished menu overlay (same as the
 * 'm'/'n' keyboard shortcut) instead of Bootstrap's collapse sidebar.
 * This gives a smooth fade-in/slide, rounded card, backdrop blur, and
 * auto-scroll to the current page — matching the desktop overlay UX.
 */
(function () {
  "use strict";

  var mql = window.matchMedia("(max-width: 991.98px)");

  function intercept(e) {
    if (!mql.matches) return;           // desktop — let Bootstrap handle it
    if (!window.__gdMenu) return;       // keyboard-nav.js not loaded yet

    // Stop Bootstrap collapse and Quarto headroom toggle
    e.preventDefault();
    e.stopPropagation();

    if (window.__gdMenu.isOpen()) {
      window.__gdMenu.hide();
    } else {
      window.__gdMenu.show();
    }
  }

  function attach() {
    // The secondary-nav has two clickable elements: the <button> and
    // the <a> that wraps the title text.  Intercept both.
    var targets = document.querySelectorAll(
      ".quarto-secondary-nav .quarto-btn-toggle, " +
      ".quarto-secondary-nav a[data-bs-toggle='collapse']"
    );
    targets.forEach(function (el) {
      el.addEventListener("click", intercept, /* capture */ true);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach);
  } else {
    attach();
  }
})();
