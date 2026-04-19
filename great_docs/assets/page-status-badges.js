/**
 * Page Status Badges
 *
 * Renders visual status indicators (e.g. "New", "Deprecated") in sidebar
 * navigation and below page titles. Status is set via `status:` frontmatter.
 *
 * Reads data from window.__GD_STATUS_DATA__ (injected inline during build).
 *
 * Data shape:
 * {
 *   page_statuses: { "user-guide/intro.qmd": "new", ... },
 *   definitions: {
 *     "new": { label: "New", icon: "<svg ...>", color: "#10b981", description: "Recently added" },
 *     ...
 *   },
 *   show_in_sidebar: true,
 *   show_on_pages: true
 * }
 */

(function () {
  "use strict";

  /**
   * Match the current page URL to a key in the page_statuses map.
   * @param {object} pageStatuses - Mapping of page href → status string
   * @returns {{key: string, status: string}|null}
   */
  function findPageStatus(pageStatuses) {
    var path = window.location.pathname;
    path = path.replace(/^\//, "");
    path = path.replace(/\/index\.html$/, "/index.qmd");
    path = path.replace(/\.html$/, ".qmd");

    if (pageStatuses[path]) return { key: path, status: pageStatuses[path] };

    var segments = path.split("/");
    for (var i = 1; i < segments.length; i++) {
      var subPath = segments.slice(i).join("/");
      if (pageStatuses[subPath])
        return { key: subPath, status: pageStatuses[subPath] };
    }
    return null;
  }

  /**
   * Render a status indicator below the page title.
   * @param {string} status - Status key (e.g. "new")
   * @param {object} def - Status definition {label, icon, color, description}
   */
  function renderPageBadge(status, def) {
    var titleEl = document.querySelector(
      "h1.title, header#title-block-header h1, main h1"
    );
    if (!titleEl) return;

    var badge = document.createElement("div");
    badge.className = "gd-page-status gd-page-status-" + status;
    badge.setAttribute("role", "status");
    badge.setAttribute("aria-label", "Page status: " + def.label);
    badge.style.setProperty("--gd-status-color", def.color);

    var inner = "";
    if (def.icon) {
      inner +=
        '<span class="gd-status-badge-icon">' + def.icon + "</span>";
    }
    inner += '<span class="gd-status-badge-label">' + def.label + "</span>";
    if (def.description) {
      inner +=
        '<span class="gd-status-badge-desc"> \u2014 ' +
        def.description +
        "</span>";
    }
    badge.innerHTML = inner;

    // Insert after title (and subtitle if present), before tags
    var insertAfter = titleEl;
    var next = titleEl.nextElementSibling;
    if (
      next &&
      (next.classList.contains("subtitle") ||
        next.classList.contains("lead") ||
        (next.tagName === "P" && next.classList.contains("subtitle")))
    ) {
      insertAfter = next;
    }

    if (insertAfter.nextSibling) {
      insertAfter.parentNode.insertBefore(badge, insertAfter.nextSibling);
    } else {
      insertAfter.parentNode.appendChild(badge);
    }
  }

  /**
   * Inject status badges into sidebar navigation links.
   * @param {object} pageStatuses - Mapping of page href → status string
   * @param {object} definitions - Status definitions
   */
  function renderSidebarBadges(pageStatuses, definitions) {
    var sidebarLinks = document.querySelectorAll(
      ".sidebar-navigation .sidebar-item .sidebar-link"
    );

    sidebarLinks.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href) return;

      // Extract pathname (handles both raw attributes and resolved URLs)
      var path = href;
      try {
        var url = new URL(href, window.location.href);
        path = url.pathname;
      } catch (_) {}

      // Normalize path to match page_statuses keys:
      // strip leading slash, replace .html → .qmd
      var normalized = path
        .replace(/^\//, "")
        .replace(/\.html$/, ".qmd")
        .replace(/\/index\.html$/, "/index.qmd");

      // Try direct match first
      var status = pageStatuses[normalized];

      // If no match, try progressively shorter subpaths to handle
      // subdirectory deployments (e.g. /great-docs/user-guide/foo.qmd → user-guide/foo.qmd)
      if (!status) {
        var segments = normalized.split("/");
        for (var i = 1; i < segments.length && !status; i++) {
          var subPath = segments.slice(i).join("/");
          status = pageStatuses[subPath];
        }
      }

      if (!status) return;

      var def = definitions[status];
      if (!def) return;

      // Check if badge already exists
      if (link.querySelector(".gd-sidebar-status-badge")) return;

      var badge = document.createElement("span");
      badge.className = "gd-sidebar-status-badge gd-sidebar-status-" + status;
      badge.style.setProperty("--gd-status-color", def.color);
      badge.setAttribute("title", def.label + (def.description ? " \u2014 " + def.description : ""));

      if (def.icon) {
        badge.innerHTML = def.icon;
      } else {
        badge.textContent = def.label;
      }

      link.appendChild(badge);
    });
  }

  /**
   * Render the "upcoming" visual indicator on the page title.
   * Independent from status badges — a page can be "experimental" and
   * "upcoming" simultaneously.
   * @param {string|true} version - Upcoming version (e.g. "0.8") or true
   */
  function renderUpcomingIndicator(version) {
    var titleEl = document.querySelector(
      "h1.title, header#title-block-header h1, main h1"
    );
    if (!titleEl) return;

    titleEl.classList.add("gd-upcoming-title");

    var tip = typeof version === "string"
      ? "Expected in " + version
      : "Coming in a future release";

    var icon = document.createElement("span");
    icon.className = "gd-upcoming-icon";
    icon.setAttribute("title", tip);
    icon.setAttribute("aria-label", tip);
    icon.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"' +
      ' fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"' +
      ' stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84' +
      '.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62' +
      ' 0-5 0-5"/><path d="M9 12a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78' +
      ' 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5' +
      ' .05 5 .05"/></svg>';
    titleEl.appendChild(icon);
  }

  /**
   * Render small rocket icons in the sidebar for upcoming pages.
   * @param {object} upcomingPages - Mapping of page href → version string or true
   */
  function renderSidebarUpcoming(upcomingPages) {
    var sidebarLinks = document.querySelectorAll(
      ".sidebar-navigation .sidebar-item .sidebar-link"
    );

    sidebarLinks.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href) return;

      var path = href;
      try {
        var url = new URL(href, window.location.href);
        path = url.pathname;
      } catch (_) {}

      var normalized = path
        .replace(/^\//, "")
        .replace(/\.html$/, ".qmd")
        .replace(/\/index\.html$/, "/index.qmd");

      var version = upcomingPages[normalized];
      if (!version) {
        var segments = normalized.split("/");
        for (var i = 1; i < segments.length && !version; i++) {
          version = upcomingPages[segments.slice(i).join("/")];
        }
      }
      if (!version) return;
      if (link.querySelector(".gd-sidebar-upcoming")) return;

      var tip = typeof version === "string"
        ? "Expected in " + version
        : "Coming in a future release";

      var badge = document.createElement("span");
      badge.className = "gd-sidebar-upcoming";
      badge.setAttribute("title", tip);
      badge.innerHTML =
        '<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24"' +
        ' fill="none" stroke="#e63946" stroke-width="2.5" stroke-linecap="round"' +
        ' stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84' +
        '.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62' +
        ' 0-5 0-5"/><path d="M9 12a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78' +
        ' 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5' +
        ' .05 5 .05"/></svg>';
      link.appendChild(badge);
    });
  }

  /**
   * Initialize: read inline status data and render.
   */
  function init() {
    var data = window.__GD_STATUS_DATA__;
    if (!data || !data.page_statuses) return;

    var definitions = data.definitions || {};

    // Render page-level badge
    if (data.show_on_pages) {
      var result = findPageStatus(data.page_statuses);
      if (result) {
        var def = definitions[result.status];
        if (def) {
          renderPageBadge(result.status, def);
        }
      }
    }

    // Render sidebar badges
    if (data.show_in_sidebar) {
      renderSidebarBadges(data.page_statuses, definitions);
    }

    // Render upcoming indicators (from separate __GD_UPCOMING_DATA__ global)
    var upcoming = window.__GD_UPCOMING_DATA__;
    if (upcoming) {
      var upResult = findPageStatus(upcoming);
      if (upResult) {
        renderUpcomingIndicator(upResult.status);
      }
      if (data.show_in_sidebar) {
        renderSidebarUpcoming(upcoming);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
