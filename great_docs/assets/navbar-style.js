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

/* Widget collection is handled by navbar-widgets.js (always loaded).
   Mobile sidebar toggle is also in navbar-widgets.js. */
