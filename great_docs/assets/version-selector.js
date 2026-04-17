/**
 * Version Selector Widget for Great Docs
 *
 * Provides a navbar dropdown for switching between documentation versions.
 * Reads version metadata from _version_map.json (embedded as a meta tag).
 *
 * Features:
 * - Dropdown in the navbar showing all configured versions
 * - Pre-release and end-of-life indicators
 * - Graceful fallback when a page doesn't exist in the target version
 * - localStorage persistence of selected version
 * - URL parameter override (?v=0.2)
 * - Keyboard accessible
 */

(function () {
  "use strict";

  // Configurable storage key
  var STORAGE_KEY = "great-docs-version";

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function getVersionMap() {
    try {
      var meta = document.querySelector('meta[name="gd-version-map"]');
      return meta ? JSON.parse(meta.getAttribute("content")) : null;
    } catch (e) {
      return null;
    }
  }

  function getStoredVersion() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function setStoredVersion(tag) {
    try {
      localStorage.setItem(STORAGE_KEY, tag);
    } catch (e) {
      // localStorage not available
    }
  }

  /**
   * Determine the current version tag by inspecting the URL path.
   * If the path starts with /v/<tag>/, return that tag.  Otherwise return
   * the tag of whichever version has an empty path_prefix (latest).
   */
  function detectCurrentVersion(versionMap) {
    var path = window.location.pathname;

    for (var i = 0; i < versionMap.versions.length; i++) {
      var v = versionMap.versions[i];
      if (v.path_prefix && path.indexOf("/" + v.path_prefix + "/") === 0) {
        return v.tag;
      }
    }

    // No prefix matched — we're on the latest (root) version
    for (var j = 0; j < versionMap.versions.length; j++) {
      if (versionMap.versions[j].latest) {
        return versionMap.versions[j].tag;
      }
    }

    return versionMap.versions.length ? versionMap.versions[0].tag : null;
  }

  /**
   * Build the URL for a given page path under a specific version.
   */
  function buildVersionUrl(versionMap, targetTag, currentRelPath) {
    var targetVersion = null;
    for (var i = 0; i < versionMap.versions.length; i++) {
      if (versionMap.versions[i].tag === targetTag) {
        targetVersion = versionMap.versions[i];
        break;
      }
    }
    if (!targetVersion) return null;

    var basePath = window.location.pathname.replace(/\/[^/]*$/, "");

    // Strip current version prefix to get the relative page path
    var pagePath = currentRelPath;

    // Check if the page exists in the target version
    var pageExists =
      versionMap.pages &&
      versionMap.pages[pagePath] &&
      versionMap.pages[pagePath].indexOf(targetTag) !== -1;

    if (!pageExists && versionMap.fallbacks && versionMap.fallbacks[pagePath]) {
      pagePath = versionMap.fallbacks[pagePath];
    } else if (!pageExists) {
      // Ultimate fallback: version root
      pagePath = "index.html";
    }

    var prefix = targetVersion.path_prefix;
    if (prefix) {
      return "/" + prefix + "/" + pagePath;
    }
    return "/" + pagePath;
  }

  /**
   * Get the current page's relative path (without version prefix).
   */
  function getCurrentRelPath(versionMap) {
    var path = window.location.pathname;

    // Strip version prefix if present
    for (var i = 0; i < versionMap.versions.length; i++) {
      var v = versionMap.versions[i];
      if (v.path_prefix && path.indexOf("/" + v.path_prefix + "/") === 0) {
        return path.substring(v.path_prefix.length + 2); // +2 for leading and trailing /
      }
    }

    // No prefix — strip leading /
    return path.substring(1) || "index.html";
  }

  // ---------------------------------------------------------------------------
  // Widget creation
  // ---------------------------------------------------------------------------

  function createVersionSelector(versionMap) {
    var currentTag = detectCurrentVersion(versionMap);
    var currentRelPath = getCurrentRelPath(versionMap);

    // Find current version entry
    var currentVersion = null;
    for (var i = 0; i < versionMap.versions.length; i++) {
      if (versionMap.versions[i].tag === currentTag) {
        currentVersion = versionMap.versions[i];
        break;
      }
    }
    if (!currentVersion) return;

    // Create container (mirrors #github-widget structure)
    var container = document.createElement("div");
    container.id = "gd-version-selector";
    container.className = "gd-version-selector";
    container.setAttribute("role", "navigation");
    container.setAttribute("aria-label", "Version selector");

    // Build the trigger button (mirrors .gh-widget-trigger)
    var trigger = document.createElement("div");
    trigger.className = "gd-vs-trigger";
    trigger.setAttribute("role", "button");
    trigger.setAttribute("aria-haspopup", "true");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("tabindex", "0");

    // Git-branch SVG icon (Lucide)
    trigger.innerHTML =
      '<svg class="gd-vs-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<line x1="6" y1="3" x2="6" y2="15"/>' +
      '<circle cx="18" cy="6" r="3"/>' +
      '<circle cx="6" cy="18" r="3"/>' +
      '<path d="M18 9a9 9 0 0 1-9 9"/>' +
      "</svg>" +
      '<span class="gd-vs-label">v' +
      currentVersion.tag +
      "</span>" +
      '<svg class="gd-vs-arrow" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">' +
      '<path d="M4.427 7.427l3.396 3.396a.25.25 0 00.354 0l3.396-3.396A.25.25 0 0011.396 7H4.604a.25.25 0 00-.177.427z"/>' +
      "</svg>";

    // Build the dropdown (mirrors .gh-dropdown)
    var dropdown = document.createElement("div");
    dropdown.className = "gd-vs-dropdown";
    dropdown.setAttribute("role", "menu");
    dropdown.setAttribute("aria-hidden", "true");

    for (var j = 0; j < versionMap.versions.length; j++) {
      var v = versionMap.versions[j];
      var isCurrent = v.tag === currentTag;

      var link = document.createElement("a");
      link.href = buildVersionUrl(versionMap, v.tag, currentRelPath) || "#";
      link.className = "gd-vs-item" + (isCurrent ? " gd-vs-item-active" : "");
      link.setAttribute("role", "menuitem");
      link.setAttribute("data-version", v.tag);

      // Status indicator
      var indicator = "";
      if (v.prerelease) {
        indicator =
          '<span class="gd-vs-badge gd-vs-badge-pre" title="Pre-release">●</span>';
      } else if (v.eol) {
        indicator =
          '<span class="gd-vs-badge gd-vs-badge-eol" title="End of life">⚠</span>';
      } else if (isCurrent) {
        indicator =
          '<span class="gd-vs-badge gd-vs-badge-current" title="Current">✓</span>';
      }

      link.innerHTML = indicator + "<span>" + v.label + "</span>";

      link.addEventListener(
        "click",
        (function (tag) {
          return function () {
            setStoredVersion(tag);
          };
        })(v.tag)
      );

      dropdown.appendChild(link);
    }

    container.appendChild(trigger);
    container.appendChild(dropdown);

    // Toggle dropdown (mirrors GitHub widget behavior)
    function openDropdown() {
      container.classList.add("gd-vs-open");
      trigger.setAttribute("aria-expanded", "true");
      dropdown.setAttribute("aria-hidden", "false");
    }
    function closeDropdown() {
      container.classList.remove("gd-vs-open");
      trigger.setAttribute("aria-expanded", "false");
      dropdown.setAttribute("aria-hidden", "true");
    }

    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      if (container.classList.contains("gd-vs-open")) {
        closeDropdown();
      } else {
        openDropdown();
      }
    });

    trigger.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        trigger.click();
      }
    });

    document.addEventListener("click", function () {
      closeDropdown();
    });

    container.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeDropdown();
        trigger.focus();
      }
    });

    // Insert into navbar (will be collected by navbar-widgets.js)
    var navbar = document.querySelector(".navbar .container-fluid");
    if (navbar) {
      // Place as a direct child so navbar-widgets.js can find it
      navbar.appendChild(container);
    }
  }

  // ---------------------------------------------------------------------------
  // Warning banners
  // ---------------------------------------------------------------------------

  function injectWarningBanner(versionMap) {
    var currentTag = detectCurrentVersion(versionMap);
    var currentVersion = null;
    var latestVersion = null;

    for (var i = 0; i < versionMap.versions.length; i++) {
      if (versionMap.versions[i].tag === currentTag)
        currentVersion = versionMap.versions[i];
      if (versionMap.versions[i].latest)
        latestVersion = versionMap.versions[i];
    }

    if (!currentVersion || currentVersion.latest) return;
    if (!latestVersion) return;

    var banner = document.createElement("div");
    banner.className = "gd-version-banner";

    var currentRelPath = getCurrentRelPath(versionMap);
    var latestUrl =
      buildVersionUrl(versionMap, latestVersion.tag, currentRelPath) || "/";

    if (currentVersion.eol) {
      banner.classList.add("gd-version-banner-eol");
      banner.innerHTML =
        '<span class="gd-vb-icon">⛔</span> ' +
        "Version " +
        currentVersion.label +
        " is no longer supported. " +
        '<a href="' +
        latestUrl +
        '">Switch to ' +
        latestVersion.label +
        " →</a>";
    } else if (currentVersion.prerelease) {
      banner.classList.add("gd-version-banner-pre");
      banner.innerHTML =
        '<span class="gd-vb-icon">🔬</span> ' +
        "Pre-release documentation (" +
        currentVersion.label +
        "). May contain unreleased features. " +
        '<a href="' +
        latestUrl +
        '">Switch to stable →</a>';
    } else {
      banner.classList.add("gd-version-banner-old");
      banner.innerHTML =
        '<span class="gd-vb-icon">⚠️</span> ' +
        "You are viewing documentation for version " +
        currentVersion.label +
        ". " +
        '<a href="' +
        latestUrl +
        '">Switch to ' +
        latestVersion.label +
        " (latest) →</a>";
    }

    // Insert before main content
    var main =
      document.querySelector("#quarto-content") || document.querySelector("main");
    if (main && main.parentNode) {
      main.parentNode.insertBefore(banner, main);
    }
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    var versionMap = getVersionMap();
    if (!versionMap || !versionMap.versions || !versionMap.versions.length) return;

    createVersionSelector(versionMap);

    // Check if warning banners are enabled (meta tag)
    var bannerMeta = document.querySelector(
      'meta[name="gd-version-warning-banner"]'
    );
    var showBanner = !bannerMeta || bannerMeta.getAttribute("content") !== "false";
    if (showBanner) {
      injectWarningBanner(versionMap);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
