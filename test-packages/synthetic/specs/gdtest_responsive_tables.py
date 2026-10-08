"""
gdtest_responsive_tables — Column sizing for Markdown tables (issue #363).

Focus: A showcase of how Great Docs sizes the columns of Markdown tables, all
       in one place for visual review:

       1. **Default sizing**: plain pipe tables with long text fit the content
          width. Short columns (names, types, defaults) stay on one line;
          prose columns wrap. Includes tables that previously overflowed on
          the Great Docs site (hero summary, color-swatch parameters, etc.).
       2. **Explicit widths**: `tbl-colwidths` caption attributes (with and
          without a caption, and with widths summing past 100) and a raw HTML
          table with a `<colgroup>`. These fill the content width with the
          given proportions.
       3. **Overflow and opt-out**: a many-column table that must scroll, a
          `.gd-table-nowrap` div restoring one-line cells, a long
          URL, a table with a spanning row, and a table inside a hidden tab
          (measured once it becomes visible).
       4. **Left alone**: tables with custom classes keep their own layout.

Static checks: Pandoc's dash-derived `<colgroup>` is absent from long-line
pipe tables (`tbl-colwidths: false`), explicit widths survive post-render,
and the sizing script and CSS ship with the site. Column widths themselves are
computed client-side by responsive-tables.js, so review the rendered pages in
a browser (including a narrow viewport) to judge the layout.
"""

_DEFAULT_SIZING = """\
---
title: Default Sizing
---

Plain Markdown tables fit the content width. Short columns stay on one line,
columns of longer text wrap, and nothing scrolls unless it has to. Resize the
window to watch the columns rebalance.

## Option Reference (Hero Section Summary)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hero` | `bool` / `dict` | auto | `false` to disable; `true` to force-enable; dict to customize (auto-enables with a logo) |
| `hero.name` | `str` / `false` | display name | Package name shown in hero |
| `hero.tagline` | `str` / `false` | description | Tagline shown below the name |
| `hero.logo` | `str` / `dict` / `false` | auto-detect | Hero-specific logo (can have `light`/`dark` keys); auto-detects `logo-hero.*` files |
| `hero.logo_height` | `str` | `200px` | CSS max-height for the hero logo |
| `hero.badges` | `list` / `false` | `auto` | Explicit badge list or `false` to suppress |

## Shortcode Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | string | — | Path to a YAML file with color definitions (relative to the project root) |
| `palette` | string | — | Preset name: `sky`, `peach`, `prism`, `lilac`, `slate`, `honey`, `dusk`, `mint`, or `all` |
| `mode` | string | `"circles"` | Display mode: `circles` or `rectangles` |
| `size` | string | `"56px"` | Circle swatch diameter (CSS length) |
| `show-contrast` | string | `"true"` | `"true"`, `"false"`, or `"inline"` |
| `title` | string | — | Title above the palette |

## Feature Comparison

| | `tbl_preview()` | `tbl_explorer()` |
|---|---|---|
| **Interactivity** | None (static HTML) | Sorting, filtering, pagination, column toggle |
| **JavaScript** | Not required | Required for interactivity; static fallback without it |
| **Data embedding** | Head/tail rows only | All rows as inline JSON |
| **Best for** | Quick dataset snapshots, lightweight pages | Exploratory data docs, dashboards, reference tables |
| **Large datasets** | Efficient (shows only head + tail) | All data embedded (watch page weight) |

## Two Prose Columns

| Setting | Before | After |
|---------|--------|-------|
| `x` | The quick brown fox jumps over the lazy dog, repeatedly and with much enthusiasm, for hours. | Short text. |
| `longer_option_name` | Tiny. | The quick brown fox jumps over the lazy dog, repeatedly and with much enthusiasm, for hours on end. |

## Two Columns: Value and Behavior

| `show-contrast` value | Behavior |
|----------------------|----------|
| `"true"` (default) | Contrast info appears in tooltips and rectangle "Aa" samples |
| `"inline"` | Contrast ratios also appear below the hex code on each circle swatch |
| `"false"` | Contrast info is hidden everywhere |

## A Table That Already Fits

Nothing here needs to wrap, so the browser lays it out as usual.

| Value | Pixels |
|-------|--------|
| `thin` | 1px |
| `medium` | 2px (default) |
| `thick` | 4px |

## Horizontal Rules in Cells

Rules inside table cells get tighter spacing and a visible minimum length.

| Name | Light | Dark | Example |
|------|-------|------|---------|
| `sky` | Deep blue | Bright sky | {{< hr color="sky" >}} |
| `peach` | Warm orange | Soft peach | {{< hr color="peach" >}} |
| `prism` | Rich purple | Soft violet | {{< hr color="prism" >}} |
| `mint` | Teal | Bright mint | {{< hr color="mint" >}} |
"""

_EXPLICIT_WIDTHS = """\
---
title: Explicit Widths
---

Add a `tbl-colwidths` attribute in a caption line below a table to set its
column widths as percentages. Tables with explicit widths fill the content
width.

## Widths Without a Caption

| Option | Type | Description |
|--------|------|-------------|
| `title` | `str` | The page title, shown in the browser tab and the navbar |
| `subtitle` | `str` | A line of text shown below the title |

: {tbl-colwidths="[25,15,60]"}

## Widths With a Caption

| Column A | Column B | Column C |
|----------|----------|----------|
| Short | A long sentence that goes on for some time to show wrapping with explicit widths. | Another fairly long sentence in the last column. |

: Three columns at 30/40/30 {tbl-colwidths="[30,40,30]"}

## Widths Summing Past 100

Quarto normalizes these proportionally (here, to 50/50).

| Left | Right |
|------|-------|
| Equal share | Equal share, even though the widths given were 80 and 80 |

: {tbl-colwidths="[80,80]"}

## Raw HTML With a Colgroup

```{=html}
<table class="caption-top table">
<colgroup><col style="width: 20%"><col style="width: 80%"></colgroup>
<thead><tr><th>Key</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td><code>a</code></td><td>A hand-written HTML table whose column widths come from its own colgroup.</td></tr>
</tbody>
</table>
```
"""

_OVERFLOW = """\
---
title: Overflow and Opt-Out
---

## Many Columns

When even the narrowest sensible column widths don't fit, the table scrolls
horizontally and shows scroll indicators.

| Header 0 | Header 1 | Header 2 | Header 3 | Header 4 | Header 5 | Header 6 | Header 7 | Notes |
|----------|----------|----------|----------|----------|----------|----------|----------|-------|
| `value_0_long` | `value_1_long` | `value_2_long` | `value_3_long` | `value_4_long` | `value_5_long` | `value_6_long` | `value_7_long` | Notes that are long enough to wrap within a minimum width rather than stretching the table. |

## Opting Out With `.gd-table-nowrap`

Inside a `.gd-table-nowrap` div every cell stays on one line and the table
scrolls if it is too wide.

::: {.gd-table-nowrap}
| Option | Type | Description |
|--------|------|-------------|
| `hero` | `bool` / `dict` | `false` to disable; `true` to force-enable; dict to customize (auto-enables with a logo) |
| `hero.logo` | `str` / `dict` / `false` | Hero-specific logo (can have `light`/`dark` keys); auto-detects `logo-hero.*` files |
:::

## A Long URL

Inline code can break at slashes and hyphens, so a long URL wraps alongside
the description instead of forcing the table to scroll.

| Source | URL | Notes |
|--------|-----|-------|
| Docs | `https://posit-dev.github.io/great-docs/user-guide/theming.html` | The theming guide, which covers colors, fonts, the hero section, and more. |

## A Spanning Row

```{=html}
<table class="caption-top table">
<thead><tr><th>Group</th><th>Item</th><th>Description</th></tr></thead>
<tbody>
<tr><td colspan="3"><strong>Section heading spanning all columns</strong></td></tr>
<tr><td>Alpha</td><td><code>alpha_item</code></td><td>Rows without spans are used to measure the columns, so the spanning row doesn't confuse the layout.</td></tr>
<tr><td>Beta</td><td><code>beta_item</code></td><td>Another description that is long enough to need wrapping in the content area.</td></tr>
</tbody>
</table>
```

## In a Hidden Tab

The table in the second tab is hidden when the page loads; it is sized when the
tab is shown.

::: {.panel-tabset}
### First Tab

Nothing to see here; switch to the second tab.

### Second Tab

| Option | Type | Description |
|--------|------|-------------|
| `hero.tagline` | `str` / `false` | Tagline shown below the name; set it to `false` to hide the tagline entirely |
| `hero.logo_height` | `str` | CSS max-height for the hero logo, as any valid CSS length such as `200px` or `12rem` |
:::
"""

_LEFT_ALONE = """\
---
title: Tables Left Alone
---

Tables that carry their own classes keep their own layout; the column-sizing
heuristics only apply to plain Markdown tables.

## A Table With a Custom Class

```{=html}
<table class="dataframe">
<thead><tr><th>id</th><th>name</th><th>comment</th></tr></thead>
<tbody>
<tr><td>1</td><td>alpha</td><td>A data-frame-style table: cells stay on one line and the table scrolls if it is too wide for the content area.</td></tr>
</tbody>
</table>
```
"""

SPEC = {
    "name": "gdtest_responsive_tables",
    "description": "Markdown table column sizing: default heuristics, explicit widths, opt-out",
    "dimensions": ["A1", "B1", "C1", "D1", "E6", "F1", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-responsive-tables",
            "version": "1.0.0",
            "description": "A package demonstrating responsive Markdown tables",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        # ── Python module (minimal, one documented function) ─────────────
        "gdtest_responsive_tables/__init__.py": (
            '"""Responsive tables demo package."""\n'
            "\n"
            '__version__ = "1.0.0"\n'
            '__all__ = ["greet"]\n'
            "\n"
            "\n"
            "def greet(name: str) -> str:\n"
            '    """Return a friendly greeting.\n'
            "\n"
            "    Parameters\n"
            "    ----------\n"
            "    name\n"
            "        Who to greet.\n"
            "\n"
            "    Returns\n"
            "    -------\n"
            "    str\n"
            "        The greeting.\n"
            '    """\n'
            '    return f"Hello, {name}!"\n'
        ),
        # ── User guide ───────────────────────────────────────────────────
        "docs/user_guide/01-default-sizing.qmd": _DEFAULT_SIZING,
        "docs/user_guide/02-explicit-widths.qmd": _EXPLICIT_WIDTHS,
        "docs/user_guide/03-overflow.qmd": _OVERFLOW,
        "docs/user_guide/04-left-alone.qmd": _LEFT_ALONE,
    },
    "config": {
        "dark_mode": True,
    },
    "expected": {
        "files_exist": [
            "reference/index.html",
            "reference/greet.html",
            "user-guide/default-sizing.html",
            "user-guide/explicit-widths.html",
            "user-guide/overflow.html",
            "user-guide/left-alone.html",
        ],
        "files_contain": {
            "user-guide/default-sizing.html": ["hero.logo_height", "responsive-tables.js"],
            "user-guide/explicit-widths.html": ["width: 25%", "width: 60%"],
            "user-guide/overflow.html": ["gd-table-nowrap", "panel-tabset"],
        },
        "coverage_exclude": [
            "ref",
            "nodoc",
            "bigcl",
            "ug",
            "supp",
            "title",
            "badge",
            "sig",
            "desc",
            "param",
            "pmatch",
            "ret",
            "refidx",
            "sechdg",
            "sbsec",
            "hdg",
        ],
    },
}
