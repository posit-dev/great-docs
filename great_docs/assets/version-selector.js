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
 *
 * Other scripts can read the versions through `window.greatDocsVersions`, which
 * builds its URLs with the same functions as the selector's links.
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
   * Compute the site base path (e.g. "/great-docs" on GitHub Pages,
   * "" on a root-hosted site).  Works by finding a known version prefix
   * in the current pathname, or by detecting `quarto:offset`.
   */
  function getSiteBasePath(versionMap) {
    var path = window.location.pathname;

    // Try to locate a version prefix in the URL
    for (var i = 0; i < versionMap.versions.length; i++) {
      var v = versionMap.versions[i];
      if (!v.path_prefix) continue;
      var needle = "/" + v.path_prefix + "/";
      var idx = path.indexOf(needle);
      if (idx >= 0) {
        // Everything before the version prefix is the base path
        return path.substring(0, idx);
      }
    }

    // No version prefix in URL — we're on the latest version.
    // Use Quarto's offset meta to compute the base path.
    var offsetMeta = document.querySelector('meta[name="quarto:offset"]');
    if (offsetMeta) {
      var offset = offsetMeta.getAttribute("content") || "./";
      // offset is relative like "./" or "../" — resolve it against the current page
      var dir = path.replace(/\/[^/]*$/, "/");
      // Count ".." segments
      var segments = offset.replace(/\/$/, "").split("/");
      for (var s = 0; s < segments.length; s++) {
        if (segments[s] === "..") {
          dir = dir.replace(/\/[^/]+\/$/, "/");
        }
      }
      return dir.replace(/\/$/, "");
    }

    return "";
  }

  /**
   * Determine the current version tag by inspecting the URL path.
   * If the path contains /v/<tag>/, return that tag.  Otherwise return
   * the tag of whichever version has an empty path_prefix (latest).
   */
  function detectCurrentVersion(versionMap) {
    var path = window.location.pathname;

    for (var i = 0; i < versionMap.versions.length; i++) {
      var v = versionMap.versions[i];
      if (v.path_prefix && path.indexOf("/" + v.path_prefix + "/") !== -1) {
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
  function buildVersionUrl(versionMap, targetTag, currentRelPath, basePath) {
    var targetVersion = null;
    for (var i = 0; i < versionMap.versions.length; i++) {
      if (versionMap.versions[i].tag === targetTag) {
        targetVersion = versionMap.versions[i];
        break;
      }
    }
    if (!targetVersion) return null;

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
      return basePath + "/" + prefix + "/" + pagePath;
    }
    return basePath + "/" + pagePath;
  }

  /**
   * Get the current page's relative path (without version prefix or base path).
   */
  function getCurrentRelPath(versionMap, basePath) {
    var path = window.location.pathname;

    // Strip base path first
    if (basePath && path.indexOf(basePath) === 0) {
      path = path.substring(basePath.length);
    }

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
  // Public API
  // ---------------------------------------------------------------------------

  function copyVersion(version) {
    var entry = {};
    for (var key in version) {
      if (Object.prototype.hasOwnProperty.call(version, key)) entry[key] = version[key];
    }
    return entry;
  }

  /**
   * Build `window.greatDocsVersions`. Each call reads the current location, so
   * its answers match the selector's links on the open page.
   *
   * - current(): the tag of the version this page belongs to
   * - list(): copies of the version map's entries, in the selector's order
   * - urlFor(tag): this page's path in that version, with the selector's
   *   fallbacks, or null for an unknown tag
   */
  function createVersionsApi(versionMap) {
    return {
      current: function () {
        return detectCurrentVersion(versionMap);
      },
      list: function () {
        return versionMap.versions.map(copyVersion);
      },
      urlFor: function (tag) {
        var basePath = getSiteBasePath(versionMap);
        var currentRelPath = getCurrentRelPath(versionMap, basePath);
        return buildVersionUrl(versionMap, tag, currentRelPath, basePath);
      },
    };
  }

  // ---------------------------------------------------------------------------
  // Widget creation
  // ---------------------------------------------------------------------------

  function createVersionSelector(versionMap, versions) {
    var currentTag = versions.current();

    // Find current version entry
    var currentVersion = null;
    for (var i = 0; i < versionMap.versions.length; i++) {
      if (versionMap.versions[i].tag === currentTag) {
        currentVersion = versionMap.versions[i];
        break;
      }
    }
    if (!currentVersion) return;

    // Create container (mirrors #repository-widget structure)
    var container = document.createElement("div");
    container.id = "gd-version-selector";
    container.className = "gd-version-selector";
    container.setAttribute("role", "navigation");
    container.setAttribute("aria-label", "Version selector");

    // Build the trigger button (mirrors .repo-widget-trigger)
    var trigger = document.createElement("div");
    trigger.className = "gd-vs-trigger";
    trigger.setAttribute("role", "button");
    trigger.setAttribute("aria-haspopup", "true");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("tabindex", "0");

    // Git-branch SVG icon (Lucide)
    trigger.innerHTML =
      '<svg class="gd-vs-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<line x1="6" y1="3" x2="6" y2="15"/>' +
      '<circle cx="18" cy="6" r="3"/>' +
      '<circle cx="6" cy="18" r="3"/>' +
      '<path d="M18 9a9 9 0 0 1-9 9"/>' +
      "</svg>" +
      '<span class="gd-vs-label">' +
      (currentVersion.tag === "dev" ? "dev" : "v" + currentVersion.tag) +
      "</span>" +
      '<svg class="gd-vs-arrow" viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">' +
      '<path d="M4.427 7.427l3.396 3.396a.25.25 0 00.354 0l3.396-3.396A.25.25 0 0011.396 7H4.604a.25.25 0 00-.177.427z"/>' +
      "</svg>";

    // Build the dropdown (mirrors .repo-dropdown)
    var dropdown = document.createElement("div");
    dropdown.className = "gd-vs-dropdown";
    dropdown.setAttribute("role", "menu");
    dropdown.setAttribute("aria-hidden", "true");

    for (var j = 0; j < versionMap.versions.length; j++) {
      var v = versionMap.versions[j];
      var isCurrent = v.tag === currentTag;

      var link = document.createElement("a");
      link.href = versions.urlFor(v.tag) || "#";
      link.className = "gd-vs-item" + (isCurrent ? " gd-vs-item-active" : "");
      link.setAttribute("role", "menuitem");
      link.setAttribute("data-version", v.tag);

      // Status indicator (left side) — spacer for alignment when no badge
      var indicator = "";
      if (v.prerelease) {
        indicator =
          '<span class="gd-vs-badge gd-vs-badge-pre" title="Pre-release">●</span>';
      } else if (v.eol) {
        indicator =
          '<span class="gd-vs-badge gd-vs-badge-eol" title="End of life">⚠</span>';
      } else {
        indicator = '<span class="gd-vs-badge-spacer"></span>';
      }

      // Current-version check on the right
      var check = isCurrent
        ? '<span class="gd-vs-check" title="Current">✓</span>'
        : "";

      link.innerHTML = indicator + "<span>" + v.label + "</span>" + check;

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

  function injectWarningBanner(versionMap, versions) {
    var currentTag = versions.current();
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

    var latestUrl = versions.urlFor(latestVersion.tag) || "/";

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
        "Pre-release documentation. May contain unreleased features. " +
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

  var versionMap = getVersionMap();
  if (!versionMap || !versionMap.versions || !versionMap.versions.length) return;

  // The version map is in the page's head, so the API is ready before the DOM is.
  var versions = createVersionsApi(versionMap);
  window.greatDocsVersions = versions;

  function init() {
    createVersionSelector(versionMap, versions);

    // Check if warning banners are enabled (meta tag)
    var bannerMeta = document.querySelector(
      'meta[name="gd-version-warning-banner"]'
    );
    var showBanner = !bannerMeta || bannerMeta.getAttribute("content") !== "false";
    if (showBanner) {
      injectWarningBanner(versionMap, versions);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
