/**
 * Page Metadata Display
 *
 * Renders page creation/modification dates and optional author information
 * at the bottom of main content. Uses a horizontal layout with icons and
 * relative timestamps ("4 months ago").
 *
 * Meta tags read:
 * - gd-page-created: ISO 8601 creation date
 * - gd-page-modified: ISO 8601 modification date
 * - gd-page-author: Author name(s), comma-separated for multiple
 * - gd-page-author-image: Author avatar URL(s), comma-separated
 * - gd-page-author-url: Author profile URL(s), comma-separated
 * - gd-auto-generated: Boolean, true for reference/changelog pages
 */

(function () {
  "use strict";

  // Lucide icon SVGs (inlined for performance)
  const ICONS = {
    // Pencil icon for "modified/edited"
    pencil: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>`,
    // File-plus icon for "created"
    filePlus: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 15h6"/><path d="M12 18v-6"/></svg>`,
    // Refresh-cw icon for "refreshed" (auto-generated)
    refreshCw: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>`,
  };

  /**
   * Get content from a meta tag by name.
   * @param {string} name - Meta tag name attribute value
   * @returns {string|null} - Content value or null
   */
  function getMeta(name) {
    const tag = document.querySelector(`meta[name="${name}"]`);
    return tag ? tag.getAttribute("content") || tag.getAttribute("data-content") : null;
  }

  /**
   * Format a date as a relative time string ("4 months ago").
   * @param {string} isoDate - ISO 8601 date string
   * @returns {string} - Relative time string
   */
  function formatRelativeTime(isoDate) {
    if (!isoDate) return "";

    try {
      const date = new Date(isoDate);
      if (isNaN(date.getTime())) return "";

      const now = new Date();
      const diffMs = now - date;
      const diffSec = Math.floor(diffMs / 1000);
      const diffMin = Math.floor(diffSec / 60);
      const diffHour = Math.floor(diffMin / 60);
      const diffDay = Math.floor(diffHour / 24);
      const diffMonth = Math.floor(diffDay / 30);
      const diffYear = Math.floor(diffDay / 365);

      if (diffYear > 0) return `${diffYear} year${diffYear > 1 ? "s" : ""} ago`;
      if (diffMonth > 0) return `${diffMonth} month${diffMonth > 1 ? "s" : ""} ago`;
      if (diffDay > 0) return `${diffDay} day${diffDay > 1 ? "s" : ""} ago`;
      if (diffHour > 0) return `${diffHour} hour${diffHour > 1 ? "s" : ""} ago`;
      if (diffMin > 0) return `${diffMin} minute${diffMin > 1 ? "s" : ""} ago`;
      return "just now";
    } catch {
      return "";
    }
  }

  /**
   * Format a date for display in tooltip (absolute date).
   * @param {string} isoDate - ISO 8601 date string
   * @returns {string} - Formatted date string (e.g., "March 24, 2026")
   */
  function formatAbsoluteDate(isoDate) {
    if (!isoDate) return "";

    try {
      const date = new Date(isoDate);
      if (isNaN(date.getTime())) return "";

      return date.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch {
      return "";
    }
  }

  /**
   * Get initials from a name for avatar fallback.
   * @param {string} name - Full name
   * @returns {string} - Up to 2 initials
   */
  function getInitials(name) {
    if (!name) return "?";
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) {
      return parts[0].charAt(0).toUpperCase();
    }
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  }

  /**
   * Create the author avatar element.
   * @param {string|null} imageUrl - Avatar image URL
   * @param {string} name - Author name (for fallback initials and tooltip)
   * @param {string|null} url - Author profile URL (optional link)
   * @returns {HTMLElement} - Avatar element (img or span with initials)
   */
  function createAvatar(imageUrl, name, url) {
    let avatar;

    if (imageUrl) {
      avatar = document.createElement("img");
      avatar.className = "gd-author-avatar";
      avatar.src = imageUrl;
      avatar.alt = name ? `${name}'s avatar` : "Author avatar";
      avatar.title = name || "Author";
      avatar.loading = "lazy";

      // Fallback to initials on error
      avatar.onerror = function () {
        const initials = document.createElement("span");
        initials.className = "gd-author-initials";
        initials.textContent = getInitials(name);
        initials.title = name || "Author";
        this.replaceWith(initials);
      };
    } else {
      avatar = document.createElement("span");
      avatar.className = "gd-author-initials";
      avatar.textContent = getInitials(name);
      avatar.title = name || "Author";
    }

    // Wrap in link if URL provided
    if (url) {
      const link = document.createElement("a");
      link.href = url;
      link.className = "gd-author-link";
      link.rel = "author";
      link.appendChild(avatar);
      return link;
    }

    return avatar;
  }

  /**
   * Build the page metadata element.
   * @returns {HTMLElement|null} - The metadata element or null if no data
   */
  function buildMetadataElement() {
    const created = getMeta("gd-page-created");
    const modified = getMeta("gd-page-modified");
    const authorNames = getMeta("gd-page-author");
    const authorImages = getMeta("gd-page-author-image");
    const authorUrls = getMeta("gd-page-author-url");
    const isAutoGenerated = getMeta("gd-auto-generated") === "true";

    // If no dates, nothing to display
    if (!created && !modified) {
      return null;
    }

    const container = document.createElement("div");
    container.className = "gd-page-metadata";

    // For auto-generated pages, show "Refreshed X ago" only
    if (isAutoGenerated) {
      if (modified) {
        const refreshedItem = document.createElement("span");
        refreshedItem.className = "gd-metadata-item";
        refreshedItem.innerHTML = `<span class="gd-icon">${ICONS.refreshCw}</span>`;

        const timeSpan = document.createElement("span");
        timeSpan.className = "gd-timestamp";
        timeSpan.textContent = `Refreshed ${formatRelativeTime(modified)}`;
        timeSpan.title = formatAbsoluteDate(modified);
        refreshedItem.appendChild(timeSpan);

        container.appendChild(refreshedItem);
      }
      return container;
    }

    // Create dates section
    const datesSection = document.createElement("div");
    datesSection.className = "gd-metadata-dates";

    // Modified date (edit icon)
    if (modified) {
      const modifiedItem = document.createElement("span");
      modifiedItem.className = "gd-metadata-item";
      modifiedItem.innerHTML = `<span class="gd-icon">${ICONS.pencil}</span>`;

      const timeSpan = document.createElement("span");
      timeSpan.className = "gd-timestamp";
      timeSpan.textContent = formatRelativeTime(modified);
      timeSpan.title = formatAbsoluteDate(modified);
      modifiedItem.appendChild(timeSpan);

      datesSection.appendChild(modifiedItem);
    }

    // Created date (file-plus icon)
    if (created) {
      const createdItem = document.createElement("span");
      createdItem.className = "gd-metadata-item";
      createdItem.innerHTML = `<span class="gd-icon">${ICONS.filePlus}</span>`;

      const timeSpan = document.createElement("span");
      timeSpan.className = "gd-timestamp";
      timeSpan.textContent = formatRelativeTime(created);
      timeSpan.title = formatAbsoluteDate(created);
      createdItem.appendChild(timeSpan);

      datesSection.appendChild(createdItem);
    }

    container.appendChild(datesSection);

    // Add authors section if author info is present
    if (authorNames) {
      // Parse comma-separated values for multiple authors
      const names = authorNames.split(",").map((s) => s.trim());
      const images = authorImages ? authorImages.split(",").map((s) => s.trim()) : [];
      const urls = authorUrls ? authorUrls.split(",").map((s) => s.trim()) : [];

      if (names.length > 0 && names[0]) {
        // Add separator
        const separator = document.createElement("span");
        separator.className = "gd-metadata-separator";
        separator.innerHTML = "—";
        container.appendChild(separator);

        // Add authors
        const authorsSection = document.createElement("div");
        authorsSection.className = "gd-metadata-authors";

        for (let i = 0; i < names.length; i++) {
          const name = names[i];
          const image = images[i] || "";
          const url = urls[i] || "";

          if (name) {
            const avatar = createAvatar(image, name, url);
            authorsSection.appendChild(avatar);
          }
        }

        container.appendChild(authorsSection);
      }
    }

    return container;
  }

  /**
   * Insert the metadata element into the page.
   */
  function insertMetadata() {
    const metadataEl = buildMetadataElement();
    if (!metadataEl) return;

    // Try to insert after main content, before the page footer
    // Quarto uses #quarto-content > main as the content area
    const mainContent = document.querySelector("#quarto-content > main");
    if (mainContent) {
      // Insert at the end of main content
      mainContent.appendChild(metadataEl);
      return;
    }

    // Fallback: insert before nav-footer if it exists
    const navFooter = document.querySelector(".nav-footer");
    if (navFooter) {
      navFooter.parentNode.insertBefore(metadataEl, navFooter);
      return;
    }

    // Last resort: append to body
    document.body.appendChild(metadataEl);
  }

  // Run after DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", insertMetadata);
  } else {
    insertMetadata();
  }
})();
