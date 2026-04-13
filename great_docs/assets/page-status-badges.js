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
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
