/**
 * Content Area Gradient Style for Great Docs
 *
 * Reads the gd-content-style meta tag and applies a subtle radial
 * gradient glow at the top of the main content area using the
 * corresponding gradient preset colours.
 */
(function () {
  "use strict";

  var meta = document.querySelector('meta[name="gd-content-style"]');
  if (!meta) return;

  var preset = meta.getAttribute("data-preset") || "";
  if (!preset) return;

  var pages = meta.getAttribute("data-pages") || "all";

  if (pages === "homepage") {
    // Normalize: strip trailing /index.html or trailing /
    var path = window.location.pathname
      .replace(/\/index\.html$/i, "/")
      .replace(/\/+$/, "");
    // The homepage is the site root. For GitHub Pages deployed at /repo-name/,
    // the root has exactly one segment (e.g., "/great-docs").  For custom
    // domains it's "" (empty after stripping "/").  Any deeper path means
    // we're on a subpage.
    var segments = path.split("/").filter(Boolean);
    if (segments.length > 1) {
      return;
    }
  }

  var content = document.getElementById("quarto-content");
  if (content) {
    var glow = document.createElement("div");
    glow.className = "gd-content-glow gd-content-glow-" + preset;
    for (var i = 1; i <= 3; i++) {
      var pulse = document.createElement("div");
      pulse.className = "gd-glow-pulse gd-glow-pulse-" + i;
      glow.appendChild(pulse);
    }
    document.body.appendChild(glow);
  }
})();
