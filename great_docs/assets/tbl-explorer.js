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
    this.filterTokens = [];  // [{colIdx, op, value, id}]
    this.filterQuery = "";   // kept for search highlight compat
    this.visibleCols = this.columns.map(function (_, i) { return i; });
    this.currentPage = 1;
    this.pageSize = this.cfg.pageSize || 20;
    this._nextFilterId = 1;
  }

  // ── Filter operator definitions ────────────────────────────

  var NUMERIC_DTYPES = {
    i8:1,i16:1,i32:1,i64:1,u8:1,u16:1,u32:1,u64:1,
    f16:1,f32:1,f64:1,dec:1
  };

  function isNumeric(dtype) { return !!NUMERIC_DTYPES[dtype]; }
  function isBool(dtype) { return dtype === "bool"; }

  // {key, label, needsValue, appliesTo(dtype)}
  var FILTER_OPS = [
    // String ops
    {key:"contains",    label:"contains",      needsValue:true,  appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"not_contains",label:"doesn\u2019t contain",needsValue:true,appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"starts_with", label:"starts with",   needsValue:true,  appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"ends_with",   label:"ends with",     needsValue:true,  appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"eq_str",      label:"equals",        needsValue:true,  appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"is_empty",    label:"is empty",      needsValue:false, appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    {key:"not_empty",   label:"is not empty",  needsValue:false, appliesTo:function(d){return !isNumeric(d) && !isBool(d);}},
    // Numeric ops
    {key:"eq",  label:"\u003D",  needsValue:true, appliesTo:isNumeric},
    {key:"neq", label:"\u2260",  needsValue:true, appliesTo:isNumeric},
    {key:"lt",  label:"\u003C",  needsValue:true, appliesTo:isNumeric},
    {key:"lte", label:"\u2264",  needsValue:true, appliesTo:isNumeric},
    {key:"gt",  label:"\u003E",  needsValue:true, appliesTo:isNumeric},
    {key:"gte", label:"\u2265",  needsValue:true, appliesTo:isNumeric},
    {key:"between",label:"between",needsValue:"two",appliesTo:isNumeric},
    // Bool ops
    {key:"is_true",  label:"is true",  needsValue:false, appliesTo:isBool},
    {key:"is_false", label:"is false", needsValue:false, appliesTo:isBool},
    // Universal ops
    {key:"is_null",     label:"is null",     needsValue:false, appliesTo:function(){return true;}},
    {key:"is_not_null", label:"is not null", needsValue:false, appliesTo:function(){return true;}}
  ];

  function getOpsForDtype(dtype) {
    var ops = [];
    for (var i = 0; i < FILTER_OPS.length; i++) {
      if (FILTER_OPS[i].appliesTo(dtype)) ops.push(FILTER_OPS[i]);
    }
    return ops;
  }

  function findOp(key) {
    for (var i = 0; i < FILTER_OPS.length; i++) {
      if (FILTER_OPS[i].key === key) return FILTER_OPS[i];
    }
    return null;
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
      var filterBar = document.createElement("div");
      filterBar.className = "gd-tbl-filter-bar";

      var tokenArea = document.createElement("span");
      tokenArea.className = "gd-tbl-filter-tokens";
      filterBar.appendChild(tokenArea);

      var addBtn = document.createElement("button");
      addBtn.className = "gd-tbl-btn gd-tbl-btn-icon gd-tbl-filter-add";
      addBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="6" y1="1" x2="6" y2="11"/><line x1="1" y1="6" x2="11" y2="6"/></svg>';
      addBtn.setAttribute("aria-label", "Add filter");
      addBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        startFilterWizard(el, state, filterBar, tokenArea);
      });
      filterBar.appendChild(addBtn);

      bar.appendChild(filterBar);
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

  // ── Filter Wizard (multi-step: column → operator → value) ──

  function startFilterWizard(el, state, filterBar, tokenArea) {
    // Remove any existing wizard
    closeFilterWizard(filterBar);

    var wizard = document.createElement("div");
    wizard.className = "gd-tbl-filter-wizard";
    wizard.addEventListener("click", function (e) { e.stopPropagation(); });

    // Step 1: pick column
    var heading = document.createElement("span");
    heading.className = "gd-tbl-fw-label";
    heading.textContent = "Column";
    wizard.appendChild(heading);

    var colList = document.createElement("div");
    colList.className = "gd-tbl-fw-options";
    state.columns.forEach(function (col, idx) {
      var btn = document.createElement("button");
      btn.className = "gd-tbl-fw-option";
      btn.textContent = col.name;
      var dtypeTag = document.createElement("span");
      dtypeTag.className = "gd-tbl-fw-dtype";
      dtypeTag.textContent = col.dtype;
      btn.appendChild(dtypeTag);
      btn.addEventListener("click", function () {
        showOpStep(wizard, el, state, filterBar, tokenArea, idx);
      });
      colList.appendChild(btn);
    });
    wizard.appendChild(colList);

    filterBar.appendChild(wizard);

    // Close on outside click
    function onDocClick() {
      closeFilterWizard(filterBar);
      document.removeEventListener("click", onDocClick);
    }
    setTimeout(function () {
      document.addEventListener("click", onDocClick);
    }, 0);
  }

  function showOpStep(wizard, el, state, filterBar, tokenArea, colIdx) {
    var col = state.columns[colIdx];
    var ops = getOpsForDtype(col.dtype);

    // Clear wizard content
    wizard.innerHTML = "";
    var heading = document.createElement("span");
    heading.className = "gd-tbl-fw-label";
    heading.textContent = col.name;
    wizard.appendChild(heading);

    var opList = document.createElement("div");
    opList.className = "gd-tbl-fw-options";
    ops.forEach(function (op) {
      var btn = document.createElement("button");
      btn.className = "gd-tbl-fw-option";
      btn.textContent = op.label;
      btn.addEventListener("click", function () {
        if (!op.needsValue) {
          // No value needed — commit immediately
          commitFilterToken(el, state, tokenArea, colIdx, op.key, null, null);
          closeFilterWizard(filterBar);
        } else if (op.needsValue === "two") {
          showBetweenValueStep(wizard, el, state, filterBar, tokenArea, colIdx, op.key);
        } else {
          showValueStep(wizard, el, state, filterBar, tokenArea, colIdx, op.key);
        }
      });
      opList.appendChild(btn);
    });
    wizard.appendChild(opList);
  }

  function showValueStep(wizard, el, state, filterBar, tokenArea, colIdx, opKey) {
    var col = state.columns[colIdx];
    var op = findOp(opKey);
    var isText = !isNumeric(col.dtype) && !isBool(col.dtype);
    var caseSensitive = false;
    wizard.innerHTML = "";

    var heading = document.createElement("span");
    heading.className = "gd-tbl-fw-label";
    heading.textContent = col.name + " " + op.label;
    wizard.appendChild(heading);

    var inputRow = document.createElement("div");
    inputRow.className = "gd-tbl-fw-input-row";

    var input = document.createElement("input");
    input.type = isNumeric(col.dtype) ? "number" : "text";
    input.className = "gd-tbl-fw-input";
    input.placeholder = "Enter value\u2026";
    input.setAttribute("aria-label", "Filter value");
    inputRow.appendChild(input);

    // Case-sensitivity toggle for text columns
    var caseBtn = null;
    if (isText) {
      caseBtn = document.createElement("button");
      caseBtn.className = "gd-tbl-fw-case";
      caseBtn.textContent = "Aa";
      caseBtn.setAttribute("aria-label", "Toggle case sensitivity");
      caseBtn.title = "Case insensitive";
      caseBtn.addEventListener("click", function () {
        caseSensitive = !caseSensitive;
        caseBtn.classList.toggle("active", caseSensitive);
        caseBtn.title = caseSensitive ? "Case sensitive" : "Case insensitive";
      });
      inputRow.appendChild(caseBtn);
    }
    wizard.appendChild(inputRow);

    var commitBtn = document.createElement("button");
    commitBtn.className = "gd-tbl-btn gd-tbl-fw-commit";
    commitBtn.textContent = "Apply";
    commitBtn.addEventListener("click", function () {
      var val = input.value.trim();
      if (!val) return;
      commitFilterToken(el, state, tokenArea, colIdx, opKey, val, null, caseSensitive);
      closeFilterWizard(filterBar);
    });
    wizard.appendChild(commitBtn);

    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        commitBtn.click();
      }
      if (e.key === "Escape") {
        closeFilterWizard(filterBar);
      }
    });
    setTimeout(function () { input.focus(); }, 0);
  }

  function showBetweenValueStep(wizard, el, state, filterBar, tokenArea, colIdx, opKey) {
    var col = state.columns[colIdx];
    wizard.innerHTML = "";

    var heading = document.createElement("span");
    heading.className = "gd-tbl-fw-label";
    heading.textContent = col.name + " between";
    wizard.appendChild(heading);

    var row = document.createElement("span");
    row.className = "gd-tbl-fw-between";

    var inputLo = document.createElement("input");
    inputLo.type = "number";
    inputLo.className = "gd-tbl-fw-input";
    inputLo.placeholder = "min";
    inputLo.setAttribute("aria-label", "Minimum value");
    row.appendChild(inputLo);

    var sep = document.createElement("span");
    sep.textContent = " and ";
    sep.className = "gd-tbl-fw-sep";
    row.appendChild(sep);

    var inputHi = document.createElement("input");
    inputHi.type = "number";
    inputHi.className = "gd-tbl-fw-input";
    inputHi.placeholder = "max";
    inputHi.setAttribute("aria-label", "Maximum value");
    row.appendChild(inputHi);
    wizard.appendChild(row);

    var commitBtn = document.createElement("button");
    commitBtn.className = "gd-tbl-btn gd-tbl-fw-commit";
    commitBtn.textContent = "Apply";
    commitBtn.addEventListener("click", function () {
      var lo = inputLo.value.trim();
      var hi = inputHi.value.trim();
      if (!lo || !hi) return;
      commitFilterToken(el, state, tokenArea, colIdx, opKey, lo, hi);
      closeFilterWizard(filterBar);
    });
    wizard.appendChild(commitBtn);

    function onKey(e) {
      if (e.key === "Enter") { e.preventDefault(); commitBtn.click(); }
      if (e.key === "Escape") closeFilterWizard(filterBar);
    }
    inputLo.addEventListener("keydown", onKey);
    inputHi.addEventListener("keydown", onKey);
    setTimeout(function () { inputLo.focus(); }, 0);
  }

  function commitFilterToken(el, state, tokenArea, colIdx, opKey, value, value2, caseSensitive) {
    var token = {
      id: state._nextFilterId++,
      colIdx: colIdx,
      op: opKey,
      value: value,
      value2: value2,
      caseSensitive: !!caseSensitive
    };
    state.filterTokens.push(token);
    renderFilterTokens(el, state, tokenArea);
    state.currentPage = 1;
    applyFilter(state);
    applyState(el, state);
  }

  function removeFilterToken(el, state, tokenArea, tokenId) {
    state.filterTokens = state.filterTokens.filter(function (t) { return t.id !== tokenId; });
    renderFilterTokens(el, state, tokenArea);
    state.currentPage = 1;
    applyFilter(state);
    applyState(el, state);
  }

  function renderFilterTokens(el, state, tokenArea) {
    tokenArea.innerHTML = "";
    for (var i = 0; i < state.filterTokens.length; i++) {
      var t = state.filterTokens[i];
      var col = state.columns[t.colIdx];
      var op = findOp(t.op);
      var pill = document.createElement("span");
      pill.className = "gd-tbl-filter-token";

      var label = col.name + " " + (op ? op.label : t.op);
      if (t.value != null) {
        if (t.value2 != null) {
          label += " " + t.value + "\u2013" + t.value2;
        } else {
          var isText = !isNumeric(col.dtype);
          label += " " + (isText ? "\u2018" + t.value + "\u2019" : t.value);
        }
      }
      var text = document.createElement("span");
      text.className = "gd-tbl-filter-token-text";
      text.textContent = label;
      pill.appendChild(text);

      // Show case-sensitivity badge when active
      if (t.caseSensitive) {
        var caseBadge = document.createElement("span");
        caseBadge.className = "gd-tbl-filter-token-case";
        caseBadge.textContent = "Aa";
        caseBadge.title = "Case sensitive";
        pill.appendChild(caseBadge);
      }

      var closeBtn = document.createElement("button");
      closeBtn.className = "gd-tbl-filter-token-x";
      closeBtn.innerHTML = "\u00D7";
      closeBtn.setAttribute("aria-label", "Remove filter: " + label);
      (function (tid) {
        closeBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          removeFilterToken(el, state, tokenArea, tid);
        });
      })(t.id);
      pill.appendChild(closeBtn);
      tokenArea.appendChild(pill);
    }
  }

  function closeFilterWizard(filterBar) {
    var w = filterBar.querySelector(".gd-tbl-filter-wizard");
    if (w && w.parentNode) w.parentNode.removeChild(w);
  }

  // ── Column Toggle ──────────────────────────────────────────

  function buildColumnToggle(el, state) {
    var wrap = document.createElement("span");
    wrap.className = "gd-tbl-col-wrap gd-tbl-btn-wrap";

    var btn = document.createElement("button");
    btn.className = "gd-tbl-btn";
    btn.setAttribute("aria-haspopup", "true");
    btn.setAttribute("aria-expanded", "false");
    updateColBtnLabel(btn, state);

    var tip = document.createElement("span");
    tip.className = "gd-tbl-tooltip";
    tip.textContent = "Select Columns";

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
    wrap.appendChild(tip);
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
    if (state.filterTokens.length === 0) {
      state.filteredRows = state.allRows.slice();
    } else {
      state.filteredRows = state.allRows.filter(function (row) {
        for (var i = 0; i < state.filterTokens.length; i++) {
          if (!evalToken(state.filterTokens[i], row)) return false;
        }
        return true;
      });
    }
    // Re-apply sort after filter
    if (state.sortCols.length > 0) {
      applySort(state);
    }
  }

  function evalToken(tok, row) {
    var v = row[tok.colIdx];
    switch (tok.op) {
      // Null checks
      case "is_null":     return v == null;
      case "is_not_null": return v != null;
      // Bool
      case "is_true":  return v === true;
      case "is_false": return v === false;
      // String ops (case-sensitive when tok.caseSensitive is set)
      case "contains": {
        if (v == null) return false;
        var sv = String(v), fv = tok.value;
        if (!tok.caseSensitive) { sv = sv.toLowerCase(); fv = fv.toLowerCase(); }
        return sv.indexOf(fv) !== -1;
      }
      case "not_contains": {
        if (v == null) return false;
        var sv = String(v), fv = tok.value;
        if (!tok.caseSensitive) { sv = sv.toLowerCase(); fv = fv.toLowerCase(); }
        return sv.indexOf(fv) === -1;
      }
      case "starts_with": {
        if (v == null) return false;
        var sv = String(v), fv = tok.value;
        if (!tok.caseSensitive) { sv = sv.toLowerCase(); fv = fv.toLowerCase(); }
        return sv.indexOf(fv) === 0;
      }
      case "ends_with": {
        if (v == null) return false;
        var sv = String(v), fv = tok.value;
        if (!tok.caseSensitive) { sv = sv.toLowerCase(); fv = fv.toLowerCase(); }
        return sv.length >= fv.length && sv.lastIndexOf(fv) === sv.length - fv.length;
      }
      case "eq_str": {
        if (v == null) return false;
        var sv = String(v), fv = tok.value;
        if (!tok.caseSensitive) { sv = sv.toLowerCase(); fv = fv.toLowerCase(); }
        return sv === fv;
      }
      case "is_empty":
        return v != null && String(v).trim() === "";
      case "not_empty":
        return v != null && String(v).trim() !== "";
      // Numeric ops
      case "eq":  return v != null && Number(v) === Number(tok.value);
      case "neq": return v != null && Number(v) !== Number(tok.value);
      case "lt":  return v != null && Number(v) <  Number(tok.value);
      case "lte": return v != null && Number(v) <= Number(tok.value);
      case "gt":  return v != null && Number(v) >  Number(tok.value);
      case "gte": return v != null && Number(v) >= Number(tok.value);
      case "between":
        return v != null && Number(v) >= Number(tok.value) && Number(v) <= Number(tok.value2);
      default: return true;
    }
  }

  /** Return a highlight substring for a given column, or "" if none. */
  function getHighlightQuery(state, colIdx) {
    for (var i = 0; i < state.filterTokens.length; i++) {
      var t = state.filterTokens[i];
      if (t.colIdx === colIdx && t.op === "contains" && t.value) {
        return t.value;
      }
    }
    return "";
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
    state.filterTokens = [];
    state.sortCols = [];
    state.currentPage = 1;
    state.visibleCols = state.columns.map(function (_, i) { return i; });
    state.filteredRows = state.allRows.slice();

    // Reset filter tokens display
    var tokenArea = el.querySelector(".gd-tbl-filter-tokens");
    if (tokenArea) tokenArea.innerHTML = "";

    // Close any open filter wizard
    var filterBar = el.querySelector(".gd-tbl-filter-bar");
    if (filterBar) closeFilterWizard(filterBar);

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

        // Highlight matching "contains" filter values in relevant cells
        var highlightQ = getHighlightQuery(state, ci);
        if (highlightQ && state.cfg.searchHighlight && !isMissing) {
          td.innerHTML = highlightText(escapeHTML(cellText), highlightQ);
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
