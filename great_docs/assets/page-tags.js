/**
 * Page Tags Display
 *
 * Renders tag pills below the page title (and subtitle, if present).
 * Tags link to the tag index page.
 * Reads tag data from window.__GD_TAGS_DATA__ (injected inline during build)
 *
 * Shadow tags are excluded from the visible pill display.
 */

(function () {
  "use strict";

  // Lucide "tag" icon SVG (inlined for performance)
  var TAG_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" ' +
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round"><path d="M20.59 13.41 11 3H4v7l9.59 9.59a2 2 0 0 0 2.82 0' +
    'l4.18-4.18a2 2 0 0 0 0-2.82Z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>';

  /**
   * Convert a tag name to a URL-friendly slug.
   * @param {string} tag - Tag name
   * @returns {string} - Slug
   */
  function tagSlug(tag) {
    return tag.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  }

  /**
   * Resolve the current page's .qmd-relative path from the URL.
   * Returns a short relative path like "user-guide/intro.qmd".
   * Also caches the matched key for depth calculation.
   * @param {object} pageTags - Mapping of page href → tag list (keys are .qmd paths)
   * @returns {{key: string, tags: string[]}|null}
   */
  function findPageTags(pageTags) {
    var path = window.location.pathname;
    // Remove leading /
    path = path.replace(/^\//, "");
    // Remove trailing /index.html
    path = path.replace(/\/index\.html$/, "/index.qmd");
    // Convert .html → .qmd
    path = path.replace(/\.html$/, ".qmd");

    // Direct match
    if (pageTags[path]) return { key: path, tags: pageTags[path] };

    // Try stripping leading segments one at a time
    var segments = path.split("/");
    for (var i = 1; i < segments.length; i++) {
      var subPath = segments.slice(i).join("/");
      if (pageTags[subPath]) return { key: subPath, tags: pageTags[subPath] };
    }
    return null;
  }

  /**
   * Insert the tag container at the bottom of the page, after page metadata
   * (if present) or at the end of main content under a horizontal rule.
   * @param {HTMLElement} container - The tag pills container element
   */
  function insertTagsBottom(container) {
    // Look for existing page metadata element
    var metadataEl = document.querySelector(".gd-page-metadata");
    if (metadataEl) {
      // Insert tags after the metadata block
      if (metadataEl.nextSibling) {
        metadataEl.parentNode.insertBefore(container, metadataEl.nextSibling);
      } else {
        metadataEl.parentNode.appendChild(container);
      }
    } else {
      // No page metadata: append to end of main content with a horizontal rule
      var mainContent = document.querySelector("#quarto-content > main");
      if (!mainContent) {
        mainContent = document.querySelector("main");
      }
      if (mainContent) {
        var hr = document.createElement("hr");
        hr.className = "gd-tags-rule";
        mainContent.appendChild(hr);
        mainContent.appendChild(container);
      }
    }
  }

  /**
   * Render tag pills into the DOM, below the page title and subtitle.
   * @param {string[]} tags - List of tag names
   * @param {object} tagsData - Full tags data object
   * @param {string} matchedKey - The matched key from page_tags (e.g. "user-guide/intro.qmd")
   */
  function renderTagPills(tags, tagsData, matchedKey) {
    // Find the page title element
    var titleEl = document.querySelector("h1.title, header#title-block-header h1, main h1");
    if (!titleEl) return;

    var shadow = new Set(tagsData.shadow || []);
    var icons = tagsData.icons || {};
    var tagMeta = tagsData.tag_meta || {};
    var tt = tagsData.tooltip_templates || {};

    // Filter out shadow tags
    var visibleTags = tags.filter(function (t) {
      return !shadow.has(t);
    });
    if (visibleTags.length === 0) return;

    // Build the container
    var container = document.createElement("div");
    container.className = "gd-page-tags";
    container.setAttribute("role", "list");
    container.setAttribute("aria-label", "Page tags");

    visibleTags.forEach(function (tag) {
      var pill = document.createElement("a");
      pill.className = "gd-tag-pill";
      pill.setAttribute("role", "listitem");
      var slug = tagSlug(tag);

      // Fix relative path: we need to go up to the site root
      // Count how deep we are from the site root using the matched key
      var depth = matchedKey.split("/").length - 1;
      var prefix = "";
      for (var j = 0; j < depth; j++) {
        prefix += "../";
      }
      pill.href = prefix + "tags/index.html#" + slug;

      // Icon (if configured) – expects pre-resolved Lucide SVG markup
      // Tag names may contain escaped slashes ("\\/") for literal "/" display;
      // look up icons using the unescaped (display) form.
      var displayTag = tag.replace(/\\\//g, '/');
      var iconSvg = icons[displayTag] || icons[tag];
      var iconHtml = '';
      if (iconSvg) {
        iconHtml =
          '<span style="margin-right:0.3em;display:inline-flex;vertical-align:middle">' + iconSvg + '</span>';
      } else {
        iconHtml = '<span class="gd-tag-icon">' + TAG_ICON + "</span>";
      }

      // Tooltip with tag metadata (page count + sections)
      var meta = tagMeta[tag];
      if (meta) {
        var hasSections = meta.sections && meta.sections.length > 0;
        var sectionStr = hasSections ? meta.sections.join(", ") : "";
        var template;
        if (hasSections) {
          template = meta.count === 1 ? (tt.one || "1 page in {sections}") : (tt.other || "{count} pages in {sections}");
        } else {
          template = meta.count === 1 ? (tt.one_no_section || "1 page") : (tt.other_no_section || "{count} pages");
        }
        var tip = template.replace("{count}", String(meta.count)).replace("{sections}", sectionStr);
        pill.setAttribute("data-tippy-content", tip);
      }

      // Segmented pill for hierarchical tags (e.g. Python/Advanced)
      // Only split on unescaped "/" — escaped "\\/" is a literal slash in the tag name
      // Use a sentinel to protect escaped slashes during splitting
      var sentinel = '\x00';
      var safeSplit = tag.replace(/\\\//g, sentinel).split('/');
      var hasHierarchy = safeSplit.length > 1;
      if (hasHierarchy) {
        var parts = safeSplit.map(function(p) { return p.replace(new RegExp(sentinel, 'g'), '/'); });        var leaf = parts[parts.length - 1].replace(/\\\//g, '/');
        var parent = parts.slice(0, -1).join("/").replace(/\\\//g, '/');
        // Icon goes on the parent (LHS), never on the child (RHS)
        var parentIcon = icons[parent]
          ? '<span style="margin-right:0.3em;display:inline-flex;vertical-align:middle">' + icons[parent] + '</span>'
          : '';
        pill.classList.add("gd-tag-pill-segmented");
        pill.innerHTML =
          '<span class="gd-tag-pill-segment gd-tag-pill-parent">' + parentIcon + parent + "</span>" +
          '<span class="gd-tag-pill-sep"></span>' +
          '<span class="gd-tag-pill-segment">' + leaf + "</span>";
      } else {
        pill.innerHTML = iconHtml + "<span>" + displayTag + "</span>";
      }

      container.appendChild(pill);
    });

    // Determine placement: per-page override → global default → "top"
    var pageLocations = tagsData.page_tag_locations || {};
    var location = pageLocations[matchedKey] || tagsData.default_location || "top";

    if (location === "bottom") {
      insertTagsBottom(container);
      return;
    }

    // Default "top" placement: after the title and subtitle, before description
    // Structure: .quarto-title contains h1 + optional p.subtitle
    // Description is in a sibling div outside .quarto-title
    var insertAfter = titleEl;
    var next = titleEl.nextElementSibling;
    if (next && (next.classList.contains("subtitle") || next.classList.contains("lead") ||
        (next.tagName === "P" && next.classList.contains("subtitle")))) {
      insertAfter = next;
    }

    // Insert the tags container after the determined element
    if (insertAfter.nextSibling) {
      insertAfter.parentNode.insertBefore(container, insertAfter.nextSibling);
    } else {
      insertAfter.parentNode.appendChild(container);
    }
  }

  /**
   * Initialize: read inline tag data and render if applicable.
   */
  function init() {
    var data = window.__GD_TAGS_DATA__;
    if (!data || !data.page_tags) return;

    var result = findPageTags(data.page_tags);
    if (!result || result.tags.length === 0) return;

    // Determine if this page uses bottom placement
    var pageLocations = data.page_tag_locations || {};
    var location = pageLocations[result.key] || data.default_location || "top";

    if (location === "bottom") {
      // Defer so page-metadata.js (also on DOMContentLoaded) inserts first
      requestAnimationFrame(function () {
        renderTagPills(result.tags, data, result.key);
      });
    } else {
      renderTagPills(result.tags, data, result.key);
    }
  }

  // Run on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
