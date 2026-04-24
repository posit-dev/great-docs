/**
 * Great Docs Table Explorer — Interactive table enhancement
 *
 * Progressive enhancement for .gd-tbl-explorer tables.
 * Zero external dependencies. Works in all modern browsers.
 *
 * Features: sorting, filtering, pagination, column toggling,
 * copy-to-clipboard, CSV download, search highlighting, sticky header.
 */
(function () {
  "use strict";

  var DEBOUNCE_MS = 200;
  var COPIED_MS = 2000;
  var PAGE_WINDOW = 2;

  // SVG sort indicator icons (all same viewBox for consistent width)
  var SORT_W = 10, SORT_H = 14;
  var SVG_SORT_NONE = '<svg width="' + SORT_W + '" height="' + SORT_H + '" viewBox="0 0 10 14" fill="currentColor" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M5 0L9.5 5.5H0.5Z"/><path d="M5 14L0.5 8.5H9.5Z"/></svg>';
  var SVG_SORT_ASC = '<svg width="' + SORT_W + '" height="' + SORT_H + '" viewBox="0 0 10 14" fill="currentColor" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M5 0L9.5 5.5H0.5Z"/></svg>';
  var SVG_SORT_DESC = '<svg width="' + SORT_W + '" height="' + SORT_H + '" viewBox="0 0 10 14" fill="currentColor" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M5 14L0.5 8.5H9.5Z"/></svg>';

  function setSortIcon(iconEl, dir) {
    if (dir === "asc") iconEl.innerHTML = SVG_SORT_ASC;
    else if (dir === "desc") iconEl.innerHTML = SVG_SORT_DESC;
    else iconEl.innerHTML = SVG_SORT_NONE;
  }

  // SVG toolbar button icons (all 14×14, viewBox 0 0 24 24, stroke style)
  var ICON_ATTRS = ' width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
  var SVG_COPY = '<svg' + ICON_ATTRS + '><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
  var SVG_CHECK = '<svg' + ICON_ATTRS + ' style="color:#198754"><polyline points="20 6 9 17 4 12"/></svg>';
  var SVG_DOWNLOAD = '<svg' + ICON_ATTRS + '><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
  var SVG_RESET = '<svg' + ICON_ATTRS + '><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg>';

  /** Create an icon button with a tooltip that appears below, anchored left. */
  function makeIconBtn(svgHtml, ariaLabel, tooltipText) {
    var wrap = document.createElement("span");
    wrap.className = "gd-tbl-btn-wrap";
    var btn = document.createElement("button");
    btn.className = "gd-tbl-btn gd-tbl-btn-icon";
    btn.innerHTML = svgHtml;
    btn.setAttribute("aria-label", ariaLabel);
    var tip = document.createElement("span");
    tip.className = "gd-tbl-tooltip";
    tip.textContent = tooltipText;
    wrap.appendChild(btn);
    wrap.appendChild(tip);
    return { wrap: wrap, btn: btn, tip: tip };
  }

  // ── State ──────────────────────────────────────────────────

  function TableState(id, data) {
    this.id = id;
    this.columns = data.columns;
    this.allRows = data.rows;
    this.totalRows = data.totalRows;
    this.tableType = data.tableType;
    this.cfg = data.config || {};

    this.filteredRows = this.allRows.slice();
    this.sortCols = [];
    this.filterQuery = "";
    this.visibleCols = this.columns.map(function (_, i) { return i; });
    this.currentPage = 1;
    this.pageSize = this.cfg.pageSize || 20;
  }

  // ── Init ───────────────────────────────────────────────────

  function init() {
    var containers = document.querySelectorAll(".gd-tbl-explorer");
    for (var i = 0; i < containers.length; i++) {
      enhance(containers[i]);
    }
  }

  function enhance(el) {
    // Guard: skip if already enhanced (multiple inline scripts on the same page)
    if (el.dataset.gdEnhanced) return;
    el.dataset.gdEnhanced = "1";

    var jsonEl = el.querySelector("script.gd-tbl-data");
    if (!jsonEl) return;
    var data;
    try {
      data = JSON.parse(jsonEl.textContent);
    } catch (e) {
      return;
    }
    var state = new TableState(el.id, data);

    if (state.cfg.filterable || state.cfg.columnToggle ||
        state.cfg.copyable || state.cfg.downloadable) {
      injectToolbar(el, state);
    }

    if (state.cfg.sortable) {
      makeSortable(el, state);
    }

    applyState(el, state);
  }

  // ── Toolbar ────────────────────────────────────────────────

  function injectToolbar(el, state) {
    var bar = document.createElement("div");
    bar.className = "gd-tbl-toolbar";
    bar.setAttribute("role", "toolbar");
    bar.setAttribute("aria-label", "Table controls");

    if (state.cfg.filterable) {
      var input = document.createElement("input");
      input.type = "search";
      input.className = "gd-tbl-filter";
      input.placeholder = "Filter all columns\u2026";
      input.setAttribute("aria-label", "Filter all columns");
      input.addEventListener("input", debounce(function () {
        state.filterQuery = input.value;
        state.currentPage = 1;
        applyFilter(state);
        applyState(el, state);
      }, DEBOUNCE_MS));
      bar.appendChild(input);
    }

    if (state.cfg.columnToggle) {
      bar.appendChild(buildColumnToggle(el, state));
    }

    if (state.cfg.copyable) {
      var copy = makeIconBtn(SVG_COPY, "Copy table to clipboard", "Copy");
      copy.btn.addEventListener("click", function () {
        handleCopy(state, false, copy.btn);
      });
      bar.appendChild(copy.wrap);
    }

    if (state.cfg.downloadable) {
      var dl = makeIconBtn(SVG_DOWNLOAD, "Download as CSV", "Download");
      dl.btn.addEventListener("click", function () {
        handleDownload(state);
      });
      bar.appendChild(dl.wrap);
    }

    // Reset button (always present if toolbar exists)
    var reset = makeIconBtn(SVG_RESET, "Reset all filters and sorting", "Reset");
    reset.btn.addEventListener("click", function () {
      handleReset(el, state);
    });
    bar.appendChild(reset.wrap);

    // Insert toolbar before the table
    var tbl = el.querySelector("table");
    if (tbl) {
      el.insertBefore(bar, tbl);
    }
  }

  // ── Column Toggle ──────────────────────────────────────────

  function buildColumnToggle(el, state) {
    var wrap = document.createElement("span");
    wrap.className = "gd-tbl-col-wrap";

    var btn = document.createElement("button");
    btn.className = "gd-tbl-btn";
    btn.setAttribute("aria-haspopup", "true");
    btn.setAttribute("aria-expanded", "false");
    updateColBtnLabel(btn, state);

    var menu = document.createElement("div");
    menu.className = "gd-tbl-col-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", "Toggle columns");

    state.columns.forEach(function (col, idx) {
      var label = document.createElement("label");
      label.className = "gd-tbl-col-option";
      label.setAttribute("role", "menuitemcheckbox");
      label.setAttribute("aria-checked", "true");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      cb.dataset.colIdx = idx;
      cb.addEventListener("change", function () {
        if (cb.checked) {
          if (state.visibleCols.indexOf(idx) === -1) {
            state.visibleCols.push(idx);
            state.visibleCols.sort(function (a, b) { return a - b; });
          }
        } else {
          if (state.visibleCols.length <= 1) {
            cb.checked = true;
            return;
          }
          state.visibleCols = state.visibleCols.filter(function (c) { return c !== idx; });
        }
        label.setAttribute("aria-checked", String(cb.checked));
        updateColBtnLabel(btn, state);
        applyFilter(state);
        applyState(el, state);
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(" " + col.name));
      menu.appendChild(label);
    });

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var open = menu.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(open));
    });

    // Close on outside click
    document.addEventListener("click", function () {
      menu.classList.remove("open");
      btn.setAttribute("aria-expanded", "false");
    });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });

    // Close on Escape
    wrap.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        menu.classList.remove("open");
        btn.setAttribute("aria-expanded", "false");
        btn.focus();
      }
    });

    wrap.appendChild(btn);
    wrap.appendChild(menu);
    return wrap;
  }

  function updateColBtnLabel(btn, state) {
    var total = state.columns.length;
    var vis = state.visibleCols.length;
    btn.textContent = vis < total ? "Columns (" + vis + "/" + total + ")" : "Columns";
  }

  // ── Sorting ────────────────────────────────────────────────

  function makeSortable(el, state) {
    var ths = el.querySelectorAll("th.gt_col_heading");
    // Skip the row-number header (first th if showRowNumbers)
    var offset = state.cfg.showRowNumbers ? 1 : 0;
    for (var i = offset; i < ths.length; i++) {
      (function (th, colIdx) {
        th.classList.add("gd-tbl-sortable", "gd-tbl-sort-none");
        var icon = document.createElement("span");
        icon.className = "gd-tbl-sort-icon";
        setSortIcon(icon, "none");
        th.appendChild(icon);
        th.setAttribute("aria-sort", "none");
        th.setAttribute("tabindex", "0");
        th.setAttribute("role", "columnheader button");

        function doSort(additive) {
          // Capture current direction before any clearing
          var existing = findSortCol(state.sortCols, colIdx);
          var prevDir = existing ? existing.dir : null;

          if (!additive) {
            clearSortClasses(el, offset);
            state.sortCols = [];
          } else if (existing) {
            // Remove existing entry; we'll re-add with new direction below
            state.sortCols = state.sortCols.filter(function (s) { return s.idx !== colIdx; });
          }

          if (!prevDir) {
            // Was unsorted → ascending
            state.sortCols.push({ idx: colIdx, dir: "asc" });
            th.classList.remove("gd-tbl-sort-none", "gd-tbl-sort-desc");
            th.classList.add("gd-tbl-sort-asc");
            th.setAttribute("aria-sort", "ascending");
            setSortIcon(icon, "asc");
          } else if (prevDir === "asc") {
            // Was ascending → descending
            state.sortCols.push({ idx: colIdx, dir: "desc" });
            th.classList.remove("gd-tbl-sort-none", "gd-tbl-sort-asc");
            th.classList.add("gd-tbl-sort-desc");
            th.setAttribute("aria-sort", "descending");
            setSortIcon(icon, "desc");
          } else {
            // Was descending → unsorted
            th.classList.remove("gd-tbl-sort-desc", "gd-tbl-sort-asc");
            th.classList.add("gd-tbl-sort-none");
            th.setAttribute("aria-sort", "none");
            setSortIcon(icon, "none");
          }
          state.currentPage = 1;
          applySort(state);
          applyState(el, state);
        }

        th.addEventListener("click", function (e) {
          doSort(e.shiftKey);
        });
        th.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            doSort(e.shiftKey);
          }
        });
      })(ths[i], i - offset);
    }
  }

  function findSortCol(sortCols, idx) {
    for (var i = 0; i < sortCols.length; i++) {
      if (sortCols[i].idx === idx) return sortCols[i];
    }
    return null;
  }

  function clearSortClasses(el, offset) {
    var ths = el.querySelectorAll("th.gt_col_heading");
    for (var i = offset; i < ths.length; i++) {
      ths[i].classList.remove("gd-tbl-sort-asc", "gd-tbl-sort-desc");
      ths[i].classList.add("gd-tbl-sort-none");
      ths[i].setAttribute("aria-sort", "none");
      var iconEl = ths[i].querySelector(".gd-tbl-sort-icon");
      if (iconEl) setSortIcon(iconEl, "none");
    }
  }

  function applySort(state) {
    if (state.sortCols.length === 0) {
      // Re-apply filter from original order
      applyFilter(state);
      return;
    }
    state.filteredRows.sort(function (a, b) {
      for (var i = 0; i < state.sortCols.length; i++) {
        var sc = state.sortCols[i];
        var cmp = compareValues(a[sc.idx], b[sc.idx], state.columns[sc.idx].dtype);
        if (cmp !== 0) return sc.dir === "asc" ? cmp : -cmp;
      }
      return 0;
    });
  }

  function compareValues(a, b, dtype) {
    // Nulls always last
    if (a == null && b == null) return 0;
    if (a == null) return 1;
    if (b == null) return -1;

    var numericTypes = {
      i8: 1, i16: 1, i32: 1, i64: 1, u8: 1, u16: 1, u32: 1, u64: 1,
      f16: 1, f32: 1, f64: 1, dec: 1
    };
    if (numericTypes[dtype]) {
      return (a - b) || 0;
    }
    if (dtype === "bool") {
      return (a === b) ? 0 : (a ? 1 : -1);
    }
    if (dtype === "date" || dtype === "dtime") {
      var da = new Date(a), db = new Date(b);
      return da.getTime() - db.getTime();
    }
    // String: locale-aware comparison
    return String(a).localeCompare(String(b));
  }

  // ── Filtering ──────────────────────────────────────────────

  function applyFilter(state) {
    if (!state.filterQuery) {
      state.filteredRows = state.allRows.slice();
    } else {
      var q = state.filterQuery.toLowerCase();
      state.filteredRows = state.allRows.filter(function (row) {
        for (var i = 0; i < state.visibleCols.length; i++) {
          var ci = state.visibleCols[i];
          var v = row[ci];
          if (v != null && String(v).toLowerCase().indexOf(q) !== -1) {
            return true;
          }
        }
        return false;
      });
    }
    // Re-apply sort after filter
    if (state.sortCols.length > 0) {
      applySort(state);
    }
  }

  // ── Copy ───────────────────────────────────────────────────

  function handleCopy(state, allRows, btnEl) {
    var rows = allRows ? state.allRows : getVisiblePageRows(state);
    var tsv = rowsToTSV(rows, state.columns, state.visibleCols);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(tsv).then(function () {
        btnEl.innerHTML = SVG_CHECK;
        btnEl.classList.add("gd-tbl-btn-copied");
        setTimeout(function () {
          btnEl.innerHTML = SVG_COPY;
          btnEl.classList.remove("gd-tbl-btn-copied");
        }, COPIED_MS);
      });
    }
  }

  function rowsToTSV(rows, columns, visibleCols) {
    var header = visibleCols.map(function (ci) { return columns[ci].name; }).join("\t");
    var lines = [header];
    rows.forEach(function (row) {
      var vals = visibleCols.map(function (ci) {
        var v = row[ci];
        return v == null ? "" : String(v);
      });
      lines.push(vals.join("\t"));
    });
    return lines.join("\n");
  }

  // ── Download ───────────────────────────────────────────────

  function handleDownload(state) {
    var rows = state.filteredRows;
    var csv = rowsToCSV(rows, state.columns, state.visibleCols);
    var blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    var ts = new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
    a.href = url;
    a.download = "table-" + ts + ".csv";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }, 100);
  }

  function rowsToCSV(rows, columns, visibleCols) {
    var header = visibleCols.map(function (ci) {
      return csvEscape(columns[ci].name);
    }).join(",");
    var lines = [header];
    rows.forEach(function (row) {
      var vals = visibleCols.map(function (ci) {
        var v = row[ci];
        return v == null ? "" : csvEscape(String(v));
      });
      lines.push(vals.join(","));
    });
    return lines.join("\r\n");
  }

  function csvEscape(s) {
    if (/[,"\r\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  // ── Reset ──────────────────────────────────────────────────

  function handleReset(el, state) {
    state.filterQuery = "";
    state.sortCols = [];
    state.currentPage = 1;
    state.visibleCols = state.columns.map(function (_, i) { return i; });
    state.filteredRows = state.allRows.slice();

    // Reset filter input
    var input = el.querySelector(".gd-tbl-filter");
    if (input) input.value = "";

    // Reset column checkboxes
    var cbs = el.querySelectorAll(".gd-tbl-col-menu input[type=checkbox]");
    for (var i = 0; i < cbs.length; i++) cbs[i].checked = true;

    // Reset column button label
    var colBtn = el.querySelector(".gd-tbl-col-wrap .gd-tbl-btn");
    if (colBtn) updateColBtnLabel(colBtn, state);

    // Reset sort classes
    var offset = state.cfg.showRowNumbers ? 1 : 0;
    clearSortClasses(el, offset);

    applyState(el, state);
  }

  // ── Render ─────────────────────────────────────────────────

  function applyState(el, state) {
    renderBody(el, state);
    renderPagination(el, state);
  }

  function renderBody(el, state) {
    var tbl = el.querySelector("table");
    if (!tbl) return;
    var oldBody = tbl.querySelector("tbody");

    var pageRows = getVisiblePageRows(state);
    var startIdx = state.pageSize > 0 ? (state.currentPage - 1) * state.pageSize : 0;

    var tbody = document.createElement("tbody");
    tbody.className = "gt_table_body";

    for (var r = 0; r < pageRows.length; r++) {
      var row = pageRows[r];
      var tr = document.createElement("tr");

      if (state.cfg.showRowNumbers) {
        var rnTd = document.createElement("td");
        rnTd.className = "gt_row gt_right gd-tbl-rownum";
        rnTd.textContent = String(startIdx + r);
        tr.appendChild(rnTd);
      }

      for (var c = 0; c < state.visibleCols.length; c++) {
        var ci = state.visibleCols[c];
        var val = row[ci];
        var td = document.createElement("td");
        var align = state.columns[ci].align || "left";
        td.className = "gt_row gt_" + align;

        var isMissing = val == null;
        if (isMissing && state.cfg.highlightMissing) {
          td.classList.add("gd-tbl-missing");
        }

        var cellText = formatCell(val);

        if (state.filterQuery && state.cfg.searchHighlight && !isMissing) {
          td.innerHTML = highlightText(escapeHTML(cellText), state.filterQuery);
        } else {
          td.textContent = cellText;
        }
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }

    if (oldBody) {
      tbl.replaceChild(tbody, oldBody);
    } else {
      tbl.appendChild(tbody);
    }

    // Update colgroup to hide toggled columns
    updateColgroup(el, state);
    // Update column headers visibility
    updateHeaders(el, state);
  }

  function updateColgroup(el, state) {
    var colgroup = el.querySelector("colgroup");
    if (!colgroup) return;
    var cols = colgroup.querySelectorAll("col");
    var offset = state.cfg.showRowNumbers ? 1 : 0;
    for (var i = offset; i < cols.length; i++) {
      var dataIdx = i - offset;
      cols[i].style.display = state.visibleCols.indexOf(dataIdx) !== -1 ? "" : "none";
    }
  }

  function updateHeaders(el, state) {
    var ths = el.querySelectorAll("th.gt_col_heading");
    var offset = state.cfg.showRowNumbers ? 1 : 0;
    for (var i = offset; i < ths.length; i++) {
      var dataIdx = i - offset;
      ths[i].style.display = state.visibleCols.indexOf(dataIdx) !== -1 ? "" : "none";
    }
  }

  function formatCell(v) {
    if (v == null) return "None";
    if (typeof v === "boolean") return String(v);
    if (typeof v === "number") {
      if (!isFinite(v)) return v > 0 ? "Inf" : "-Inf";
      // Match Python's %.12g
      var s = v.toPrecision(12);
      return String(parseFloat(s));
    }
    return String(v);
  }

  function escapeHTML(s) {
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(s));
    return d.innerHTML;
  }

  function highlightText(escapedHTML, query) {
    if (!query) return escapedHTML;
    var q = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var re = new RegExp("(" + q + ")", "gi");
    return escapedHTML.replace(re, '<span class="gd-tbl-highlight">$1</span>');
  }

  // ── Pagination ─────────────────────────────────────────────

  function getVisiblePageRows(state) {
    if (state.pageSize <= 0) return state.filteredRows;
    var start = (state.currentPage - 1) * state.pageSize;
    return state.filteredRows.slice(start, start + state.pageSize);
  }

  function renderPagination(el, state) {
    var existing = el.querySelector(".gd-tbl-pagination");
    if (existing) existing.parentNode.removeChild(existing);

    if (state.pageSize <= 0) return;

    var totalFiltered = state.filteredRows.length;
    var totalPages = Math.max(1, Math.ceil(totalFiltered / state.pageSize));

    if (totalFiltered <= state.pageSize) return;

    var nav = document.createElement("nav");
    nav.className = "gd-tbl-pagination";
    nav.setAttribute("aria-label", "Table pagination");

    // Info
    var start = (state.currentPage - 1) * state.pageSize + 1;
    var end = Math.min(state.currentPage * state.pageSize, totalFiltered);
    var info = document.createElement("span");
    info.className = "gd-tbl-page-info";
    info.textContent = "Showing " + fmtNum(start) + "\u2013" +
      fmtNum(end) + " of " + fmtNum(totalFiltered) + " rows";
    nav.appendChild(info);

    // Page buttons
    var btns = document.createElement("span");
    btns.className = "gd-tbl-page-nav";

    // Prev
    var prev = makePageBtn("\u25C0", state.currentPage > 1, function () {
      state.currentPage--;
      applyState(el, state);
    });
    prev.setAttribute("aria-label", "Previous page");
    btns.appendChild(prev);

    // Page numbers with ellipsis
    var range = getPageRange(state.currentPage, totalPages);
    for (var i = 0; i < range.length; i++) {
      if (range[i] === "...") {
        var ell = document.createElement("span");
        ell.className = "gd-tbl-page-ellipsis";
        ell.textContent = "\u2026";
        btns.appendChild(ell);
      } else {
        var pNum = range[i];
        (function (p) {
          var b = makePageBtn(String(p), true, function () {
            state.currentPage = p;
            applyState(el, state);
          });
          if (p === state.currentPage) b.classList.add("active");
          b.setAttribute("aria-label", "Page " + p);
          if (p === state.currentPage) b.setAttribute("aria-current", "page");
          btns.appendChild(b);
        })(pNum);
      }
    }

    // Next
    var next = makePageBtn("\u25B6", state.currentPage < totalPages, function () {
      state.currentPage++;
      applyState(el, state);
    });
    next.setAttribute("aria-label", "Next page");
    btns.appendChild(next);

    nav.appendChild(btns);
    el.appendChild(nav);
  }

  function makePageBtn(text, enabled, onClick) {
    var btn = document.createElement("button");
    btn.className = "gd-tbl-page-btn";
    btn.textContent = text;
    btn.disabled = !enabled;
    if (enabled) btn.addEventListener("click", onClick);
    return btn;
  }

  function getPageRange(current, total) {
    if (total <= 7) {
      var r = [];
      for (var i = 1; i <= total; i++) r.push(i);
      return r;
    }
    var pages = [1];
    var lo = Math.max(2, current - PAGE_WINDOW);
    var hi = Math.min(total - 1, current + PAGE_WINDOW);
    if (lo > 2) pages.push("...");
    for (var j = lo; j <= hi; j++) pages.push(j);
    if (hi < total - 1) pages.push("...");
    pages.push(total);
    return pages;
  }

  // ── Utilities ──────────────────────────────────────────────

  function debounce(fn, ms) {
    var timer;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function fmtNum(n) {
    return n.toLocaleString();
  }

  // ── Boot ───────────────────────────────────────────────────

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
