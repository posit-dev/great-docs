/**
 * GD Lightbox — Great Docs Lightbox Engine
 *
 * A documentation-focused lightbox built from scratch. Features:
 * - Origin-aware zoom animation (image grows from thumbnail position)
 * - Dark-mode image variant swapping
 * - Gallery with filmstrip navigation
 * - Keyboard & touch navigation
 * - Copy/download/deep-link toolbar
 * - Accessible: focus trap, ARIA, screen reader announcements
 *
 * No dependencies. ~12KB minified+gzipped target.
 */
(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------

  const PREFIX = "gd-lightbox";
  const ATTR_LB = "data-gd-lightbox";
  const ATTR_ID = "data-gd-lightbox-id";
  const ATTR_GROUP = "data-gd-lightbox-group";
  const ATTR_DARK = "data-gd-lightbox-dark";
  const ATTR_CAPTION = "data-gd-lightbox-caption";
  const ATTR_CREDIT = "data-gd-lightbox-credit";
  const ATTR_DESC_POS = "data-gd-lightbox-desc-position";
  const ATTR_ZOOM_TARGET = "data-gd-lightbox-zoom-target";

  const TRANSITION_MS = 300;
  const TOOLBAR_HIDE_MS = 3000;

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  let overlay = null; // The lightbox overlay DOM element
  let isOpen = false;
  let currentIndex = -1;
  let currentGroup = null; // Array of items in the active gallery
  let allItems = []; // All lightbox items on the page
  let groups = {}; // { groupName: [items...] }
  let toolbarTimer = null;
  let previousFocus = null; // Element that had focus before lightbox opened
  let isDarkMode = false;

  // Touch/gesture state
  let touchStartX = 0;
  let touchStartY = 0;
  let touchDeltaX = 0;
  let touchDeltaY = 0;
  let isSwiping = false;

  // ---------------------------------------------------------------------------
  // Utilities
  // ---------------------------------------------------------------------------

  function qs(sel, ctx) {
    return (ctx || document).querySelector(sel);
  }

  function qsa(sel, ctx) {
    return Array.from((ctx || document).querySelectorAll(sel));
  }

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "className") {
          node.className = attrs[k];
        } else if (k.startsWith("on")) {
          node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
        } else {
          node.setAttribute(k, attrs[k]);
        }
      });
    }
    if (children) {
      children.forEach(function (c) {
        if (typeof c === "string") {
          node.appendChild(document.createTextNode(c));
        } else if (c) {
          node.appendChild(c);
        }
      });
    }
    return node;
  }

  function detectDarkMode() {
    const html = document.documentElement;
    return (
      html.classList.contains("quarto-dark") ||
      html.getAttribute("data-bs-theme") === "dark"
    );
  }

  function getImageSrc(item) {
    if (isDarkMode && item.darkSrc) {
      return item.darkSrc;
    }
    return item.src;
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  // ---------------------------------------------------------------------------
  // Collect Items
  // ---------------------------------------------------------------------------

  function collectItems() {
    allItems = [];
    groups = {};

    qsa("[" + ATTR_LB + "]").forEach(function (wrapper) {
      var img = qs(".gd-lightbox-img", wrapper);
      if (!img) return;

      var item = {
        wrapper: wrapper,
        img: img,
        id: wrapper.getAttribute(ATTR_ID),
        src: img.getAttribute("src"),
        darkSrc: wrapper.getAttribute(ATTR_DARK) || null,
        group: wrapper.getAttribute(ATTR_GROUP) || null,
        caption: wrapper.getAttribute(ATTR_CAPTION) || "",
        credit: wrapper.getAttribute(ATTR_CREDIT) || "",
        descPosition: wrapper.getAttribute(ATTR_DESC_POS) || "bottom",
        zoomTarget: wrapper.getAttribute(ATTR_ZOOM_TARGET) || null,
        alt: img.getAttribute("alt") || "",
      };

      allItems.push(item);

      if (item.group) {
        if (!groups[item.group]) {
          groups[item.group] = [];
        }
        groups[item.group].push(item);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Overlay DOM
  // ---------------------------------------------------------------------------

  function createOverlay() {
    if (overlay) return;

    overlay = el("div", {
      className: PREFIX + "-overlay",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "Image lightbox",
    });

    // Backdrop
    var backdrop = el("div", {
      className: PREFIX + "-backdrop",
      onClick: close,
    });
    overlay.appendChild(backdrop);

    // Content container
    var content = el("div", { className: PREFIX + "-content" });

    // Main image
    var imageWrap = el("div", { className: PREFIX + "-image-wrap" });
    var mainImg = el("img", {
      className: PREFIX + "-main-img",
      alt: "",
    });
    imageWrap.appendChild(mainImg);
    content.appendChild(imageWrap);

    // Caption area
    var captionEl = el("div", { className: PREFIX + "-caption" });
    var captionText = el("p", { className: PREFIX + "-caption-text" });
    var creditText = el("p", { className: PREFIX + "-credit-text" });
    captionEl.appendChild(captionText);
    captionEl.appendChild(creditText);
    content.appendChild(captionEl);

    overlay.appendChild(content);

    // Toolbar
    var toolbar = el("div", { className: PREFIX + "-toolbar" });

    // Counter (for galleries)
    var counter = el("span", { className: PREFIX + "-counter" });
    toolbar.appendChild(counter);

    // Spacer
    toolbar.appendChild(el("span", { className: PREFIX + "-toolbar-spacer" }));

    // Copy button
    var copyBtn = el(
      "button",
      {
        className: PREFIX + "-btn " + PREFIX + "-btn-copy",
        "aria-label": "Copy image to clipboard",
        title: "Copy image",
        onClick: handleCopy,
      },
      [createCopyIcon()]
    );
    toolbar.appendChild(copyBtn);

    // Download button
    var downloadBtn = el(
      "button",
      {
        className: PREFIX + "-btn " + PREFIX + "-btn-download",
        "aria-label": "Download image",
        title: "Download image",
        onClick: handleDownload,
      },
      [createDownloadIcon()]
    );
    toolbar.appendChild(downloadBtn);

    // Close button
    var closeBtn = el(
      "button",
      {
        className: PREFIX + "-btn " + PREFIX + "-btn-close",
        "aria-label": "Close lightbox",
        title: "Close (Esc)",
        onClick: close,
      },
      [createCloseIcon()]
    );
    toolbar.appendChild(closeBtn);

    overlay.appendChild(toolbar);

    // Navigation arrows
    var prevBtn = el(
      "button",
      {
        className: PREFIX + "-nav " + PREFIX + "-nav-prev",
        "aria-label": "Previous image",
        onClick: prev,
      },
      [createChevronLeft()]
    );
    var nextBtn = el(
      "button",
      {
        className: PREFIX + "-nav " + PREFIX + "-nav-next",
        "aria-label": "Next image",
        onClick: next,
      },
      [createChevronRight()]
    );
    overlay.appendChild(prevBtn);
    overlay.appendChild(nextBtn);

    // Filmstrip
    var filmstrip = el("div", { className: PREFIX + "-filmstrip" });
    overlay.appendChild(filmstrip);

    // Live region for screen reader announcements
    var liveRegion = el("div", {
      className: PREFIX + "-sr-announce",
      "aria-live": "polite",
      "aria-atomic": "true",
    });
    overlay.appendChild(liveRegion);

    document.body.appendChild(overlay);
  }

  // ---------------------------------------------------------------------------
  // SVG Icons (inline, no external deps)
  // ---------------------------------------------------------------------------

  function svgEl(paths, size) {
    size = size || 20;
    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    paths.forEach(function (d) {
      var path = document.createElementNS(ns, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  }

  function createCloseIcon() {
    return svgEl(["M18 6L6 18", "M6 6l12 12"]);
  }

  function createChevronLeft() {
    return svgEl(["M15 18l-6-6 6-6"], 24);
  }

  function createChevronRight() {
    return svgEl(["M9 18l6-6-6-6"], 24);
  }

  function createCopyIcon() {
    return svgEl([
      "M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2",
      "M9 2h6a1 1 0 011 1v1a1 1 0 01-1 1H9a1 1 0 01-1-1V3a1 1 0 011-1z",
    ]);
  }

  function createDownloadIcon() {
    return svgEl(["M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4", "M7 10l5 5 5-5", "M12 15V3"]);
  }

  // ---------------------------------------------------------------------------
  // Open / Close / Navigate
  // ---------------------------------------------------------------------------

  function open(item) {
    if (isOpen) return;

    previousFocus = document.activeElement;
    isOpen = true;
    isDarkMode = detectDarkMode();

    createOverlay();

    // Determine the gallery group
    if (item.group && groups[item.group]) {
      currentGroup = groups[item.group];
    } else {
      currentGroup = [item];
    }
    currentIndex = currentGroup.indexOf(item);
    if (currentIndex < 0) currentIndex = 0;

    showSlide(currentIndex, item);

    // Show overlay with animation
    overlay.classList.add(PREFIX + "-visible");
    document.body.classList.add(PREFIX + "-open");

    // Origin animation: get thumbnail rect and animate from there
    if (!prefersReducedMotion()) {
      animateOpen(item);
    }

    // Update URL hash for deep linking
    if (item.id) {
      history.replaceState(null, "", "#lightbox=" + item.id);
    }

    // Focus the close button
    setTimeout(function () {
      var closeBtn = qs("." + PREFIX + "-btn-close", overlay);
      if (closeBtn) closeBtn.focus();
    }, TRANSITION_MS);

    startToolbarTimer();
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;

    overlay.classList.remove(PREFIX + "-visible");
    overlay.classList.add(PREFIX + "-closing");
    document.body.classList.remove(PREFIX + "-open");

    // Remove hash
    if (window.location.hash.startsWith("#lightbox=")) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }

    setTimeout(function () {
      overlay.classList.remove(PREFIX + "-closing");
      // Restore focus
      if (previousFocus) {
        previousFocus.focus();
      }
    }, TRANSITION_MS);
  }

  function next() {
    if (!currentGroup || currentGroup.length <= 1) return;
    currentIndex = (currentIndex + 1) % currentGroup.length;
    showSlide(currentIndex);
    announce("Image " + (currentIndex + 1) + " of " + currentGroup.length);
  }

  function prev() {
    if (!currentGroup || currentGroup.length <= 1) return;
    currentIndex = (currentIndex - 1 + currentGroup.length) % currentGroup.length;
    showSlide(currentIndex);
    announce("Image " + (currentIndex + 1) + " of " + currentGroup.length);
  }

  function showSlide(index, originItem) {
    var item = currentGroup[index];
    if (!item) return;

    var mainImg = qs("." + PREFIX + "-main-img", overlay);
    var captionText = qs("." + PREFIX + "-caption-text", overlay);
    var creditText = qs("." + PREFIX + "-credit-text", overlay);
    var counter = qs("." + PREFIX + "-counter", overlay);

    // Update image source (with dark mode awareness)
    var src = getImageSrc(item);
    mainImg.setAttribute("src", src);
    mainImg.setAttribute("alt", item.alt);

    // Update caption
    if (item.caption) {
      captionText.textContent = item.caption;
      captionText.style.display = "";
    } else {
      captionText.style.display = "none";
    }

    if (item.credit) {
      creditText.textContent = item.credit;
      creditText.style.display = "";
    } else {
      creditText.style.display = "none";
    }

    // Update counter
    if (currentGroup.length > 1) {
      counter.textContent = (index + 1) + " / " + currentGroup.length;
      counter.style.display = "";
    } else {
      counter.style.display = "none";
    }

    // Update navigation visibility
    var prevBtn = qs("." + PREFIX + "-nav-prev", overlay);
    var nextBtn = qs("." + PREFIX + "-nav-next", overlay);
    if (currentGroup.length <= 1) {
      prevBtn.style.display = "none";
      nextBtn.style.display = "none";
    } else {
      prevBtn.style.display = "";
      nextBtn.style.display = "";
    }

    // Update filmstrip
    updateFilmstrip();
  }

  // ---------------------------------------------------------------------------
  // Filmstrip
  // ---------------------------------------------------------------------------

  function updateFilmstrip() {
    var filmstrip = qs("." + PREFIX + "-filmstrip", overlay);
    if (!filmstrip) return;

    if (!currentGroup || currentGroup.length <= 1) {
      filmstrip.style.display = "none";
      return;
    }

    filmstrip.style.display = "";
    filmstrip.innerHTML = "";

    currentGroup.forEach(function (item, i) {
      var thumb = el("button", {
        className:
          PREFIX + "-filmstrip-thumb" + (i === currentIndex ? " active" : ""),
        "aria-label": "Go to image " + (i + 1),
        onClick: function () {
          currentIndex = i;
          showSlide(i);
          announce("Image " + (i + 1) + " of " + currentGroup.length);
        },
      });
      var img = el("img", {
        src: getImageSrc(item),
        alt: "",
        "aria-hidden": "true",
      });
      thumb.appendChild(img);
      filmstrip.appendChild(thumb);
    });

    // Scroll active thumb into view
    var active = qs("." + PREFIX + "-filmstrip-thumb.active", filmstrip);
    if (active) {
      active.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }

  // ---------------------------------------------------------------------------
  // Origin-Aware Animation
  // ---------------------------------------------------------------------------

  function animateOpen(item) {
    var rect = item.img.getBoundingClientRect();
    var mainImg = qs("." + PREFIX + "-main-img", overlay);
    if (!mainImg) return;

    // Set starting transform to match thumbnail position
    var vpW = window.innerWidth;
    var vpH = window.innerHeight;

    // Calculate scale and translation
    var targetW = Math.min(vpW * 0.9, mainImg.naturalWidth || vpW * 0.8);
    var scaleX = rect.width / targetW;
    var scaleY = rect.height / (targetW * (rect.height / rect.width));

    mainImg.style.transition = "none";
    mainImg.style.transform =
      "translate(" +
      (rect.left + rect.width / 2 - vpW / 2) +
      "px, " +
      (rect.top + rect.height / 2 - vpH / 2) +
      "px) scale(" +
      scaleX +
      ")";
    mainImg.style.opacity = "0.8";

    // Force reflow
    mainImg.offsetHeight;

    // Animate to center
    mainImg.style.transition =
      "transform " + TRANSITION_MS + "ms cubic-bezier(0.4, 0, 0.2, 1), " +
      "opacity " + TRANSITION_MS + "ms ease";
    mainImg.style.transform = "translate(0, 0) scale(1)";
    mainImg.style.opacity = "1";

    // Clean up after animation
    setTimeout(function () {
      mainImg.style.transition = "";
      mainImg.style.transform = "";
    }, TRANSITION_MS + 50);
  }

  // ---------------------------------------------------------------------------
  // Toolbar Actions
  // ---------------------------------------------------------------------------

  function handleCopy() {
    var mainImg = qs("." + PREFIX + "-main-img", overlay);
    if (!mainImg || !mainImg.src) return;

    // Fetch image as blob and copy to clipboard
    fetch(mainImg.src)
      .then(function (r) { return r.blob(); })
      .then(function (blob) {
        var item = new ClipboardItem({ [blob.type]: blob });
        return navigator.clipboard.write([item]);
      })
      .then(function () {
        showToast("Copied to clipboard");
      })
      .catch(function () {
        // Fallback: copy the URL
        navigator.clipboard.writeText(mainImg.src).then(function () {
          showToast("Image URL copied");
        });
      });
  }

  function handleDownload() {
    var mainImg = qs("." + PREFIX + "-main-img", overlay);
    if (!mainImg || !mainImg.src) return;

    var item = currentGroup[currentIndex];
    var filename = item
      ? (item.alt || item.src.split("/").pop() || "image")
      : "image";
    // Sanitize filename
    filename = filename.replace(/[^a-zA-Z0-9_\-. ]/g, "_").slice(0, 100);

    var a = document.createElement("a");
    a.href = mainImg.src;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function showToast(msg) {
    var existing = qs("." + PREFIX + "-toast");
    if (existing) existing.remove();

    var toast = el("div", { className: PREFIX + "-toast" }, [msg]);
    overlay.appendChild(toast);

    // Animate in
    requestAnimationFrame(function () {
      toast.classList.add("visible");
    });

    setTimeout(function () {
      toast.classList.remove("visible");
      setTimeout(function () { toast.remove(); }, 300);
    }, 2000);
  }

  // ---------------------------------------------------------------------------
  // Toolbar Auto-Hide
  // ---------------------------------------------------------------------------

  function startToolbarTimer() {
    clearTimeout(toolbarTimer);
    showToolbar();
    toolbarTimer = setTimeout(hideToolbar, TOOLBAR_HIDE_MS);
  }

  function showToolbar() {
    var tb = qs("." + PREFIX + "-toolbar", overlay);
    if (tb) tb.classList.remove("hidden");
  }

  function hideToolbar() {
    var tb = qs("." + PREFIX + "-toolbar", overlay);
    if (tb) tb.classList.add("hidden");
  }

  // ---------------------------------------------------------------------------
  // Keyboard Navigation
  // ---------------------------------------------------------------------------

  function handleKeydown(e) {
    if (!isOpen) return;

    switch (e.key) {
      case "Escape":
        close();
        e.preventDefault();
        break;
      case "ArrowRight":
        next();
        e.preventDefault();
        break;
      case "ArrowLeft":
        prev();
        e.preventDefault();
        break;
      case "Tab":
        trapFocus(e);
        break;
    }
  }

  function trapFocus(e) {
    var focusable = qsa(
      'button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      overlay
    );
    if (focusable.length === 0) return;

    var first = focusable[0];
    var last = focusable[focusable.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === first) {
        last.focus();
        e.preventDefault();
      }
    } else {
      if (document.activeElement === last) {
        first.focus();
        e.preventDefault();
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Touch / Swipe
  // ---------------------------------------------------------------------------

  function handleTouchStart(e) {
    if (!isOpen) return;
    var touch = e.touches[0];
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchDeltaX = 0;
    touchDeltaY = 0;
    isSwiping = false;
  }

  function handleTouchMove(e) {
    if (!isOpen) return;
    var touch = e.touches[0];
    touchDeltaX = touch.clientX - touchStartX;
    touchDeltaY = touch.clientY - touchStartY;

    // Determine if horizontal or vertical swipe
    if (!isSwiping && (Math.abs(touchDeltaX) > 10 || Math.abs(touchDeltaY) > 10)) {
      isSwiping = true;
    }

    // Prevent page scroll while swiping in lightbox
    if (isSwiping) {
      e.preventDefault();
    }
  }

  function handleTouchEnd() {
    if (!isOpen || !isSwiping) return;

    var threshold = 50;

    // Horizontal swipe → gallery navigation
    if (Math.abs(touchDeltaX) > Math.abs(touchDeltaY)) {
      if (touchDeltaX > threshold) {
        prev();
      } else if (touchDeltaX < -threshold) {
        next();
      }
    } else {
      // Vertical swipe down → close
      if (touchDeltaY > threshold) {
        close();
      }
    }

    isSwiping = false;
  }

  // ---------------------------------------------------------------------------
  // Dark Mode Observer
  // ---------------------------------------------------------------------------

  function setupDarkModeObserver() {
    var html = document.documentElement;
    var observer = new MutationObserver(function (mutations) {
      var newDarkMode = detectDarkMode();
      if (newDarkMode !== isDarkMode) {
        isDarkMode = newDarkMode;
        if (isOpen) {
          // Swap image source
          showSlide(currentIndex);
        }
        // Also swap thumbnails on the page
        swapThumbnails();
      }
    });
    observer.observe(html, {
      attributes: true,
      attributeFilter: ["class", "data-bs-theme"],
    });
  }

  function swapThumbnails() {
    allItems.forEach(function (item) {
      if (item.darkSrc) {
        item.img.setAttribute("src", getImageSrc(item));
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Screen Reader Announcements
  // ---------------------------------------------------------------------------

  function announce(msg) {
    var region = qs("." + PREFIX + "-sr-announce", overlay);
    if (region) {
      region.textContent = msg;
    }
  }

  // ---------------------------------------------------------------------------
  // Deep Linking
  // ---------------------------------------------------------------------------

  function checkDeepLink() {
    var hash = window.location.hash;
    if (!hash.startsWith("#lightbox=")) return;

    var id = hash.slice("#lightbox=".length);
    var item = allItems.find(function (it) {
      return it.id === id;
    });
    if (item) {
      // Delay to allow page to render
      setTimeout(function () { open(item); }, 100);
    }
  }

  // ---------------------------------------------------------------------------
  // Event Binding
  // ---------------------------------------------------------------------------

  function bindClick(item) {
    // Click on wrapper or expand button opens lightbox
    item.wrapper.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      open(item);
    });

    // Make wrapper keyboard-accessible
    item.wrapper.setAttribute("tabindex", "0");
    item.wrapper.setAttribute("role", "button");
    item.wrapper.setAttribute("aria-label", "View image: " + (item.alt || "image"));
    item.wrapper.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open(item);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------

  function init() {
    isDarkMode = detectDarkMode();
    collectItems();

    if (allItems.length === 0) return;

    allItems.forEach(bindClick);
    setupDarkModeObserver();

    // Global keyboard handler
    document.addEventListener("keydown", handleKeydown);

    // Touch handlers on overlay (after it's created)
    document.addEventListener("touchstart", function (e) {
      if (isOpen) handleTouchStart(e);
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (isOpen) handleTouchMove(e);
    }, { passive: false });
    document.addEventListener("touchend", function (e) {
      if (isOpen) handleTouchEnd(e);
    }, { passive: true });

    // Mouse movement re-shows toolbar
    document.addEventListener("mousemove", function () {
      if (isOpen) startToolbarTimer();
    });

    // Deep link check
    checkDeepLink();
    window.addEventListener("hashchange", checkDeepLink);
  }

  // Run on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
