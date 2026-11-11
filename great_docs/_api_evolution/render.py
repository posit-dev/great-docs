"""API evolution tables and timeline diagrams"""

from __future__ import annotations

from pathlib import Path

from great_docs._api_evolution.history import SymbolHistory, symbol_history
from great_docs._api_evolution.model import ParameterInfo
from great_docs._api_evolution.snapshot import list_version_tags
from great_docs._translations import translate


def _augment_params_with_separators(
    params: list[ParameterInfo],
) -> list[ParameterInfo]:
    """Insert a synthetic `*` separator before keyword-only parameters.

    If the parameter list has `KEYWORD_ONLY` parameters but no `VAR_POSITIONAL` (`*args`) parameter,
    a `ParameterInfo(name="*")` entry is inserted at the boundary so that the evolution table can
    display the separator row.
    """
    has_var_positional = any(p.kind == "VAR_POSITIONAL" for p in params)
    if has_var_positional:
        return params  # *args already acts as the separator

    first_kw_idx: int | None = None
    for i, p in enumerate(params):
        if p.kind == "KEYWORD_ONLY":
            first_kw_idx = i
            break

    if first_kw_idx is None:
        return params  # no keyword-only params

    augmented = list(params[:first_kw_idx])
    augmented.append(
        ParameterInfo(name="*", annotation=None, default=None, kind="KEYWORD_ONLY_SEPARATOR")
    )
    augmented.extend(params[first_kw_idx:])
    return augmented


def _cell_text(param: ParameterInfo) -> str:
    """Render a parameter's type + default as file line 2 of a cell."""
    parts: list[str] = []
    if param.annotation:
        parts.append(param.annotation)
    if param.default is not None:
        parts.append(f"= {param.default}")
    return " ".join(parts) if parts else ""


def _cell_lines(param: ParameterInfo) -> tuple[str, str]:
    """Return (line1, line2) for a parameter cell.

    Line 1 is the parameter name, line 2 is `type (= default)`.
    """
    return (param.name, _cell_text(param))


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for table cell content."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def evolution_table(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> list[list[tuple[str, str]]]:
    """
    Build a positional-slot table of a symbol's parameter evolution.

    Each cell is a `(line1, line2)` tuple where *line1* is the parameter name and *line2* is
    `type (= default)`. Parameters are laid out by **position** (row 0 is the first parameter in
    each version, row 1 is the second, etc.) so insertions, removals, and reorderings are visible.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    list[list[tuple[str, str]]]
        Row 0 is the header: `[("", version1), ("", version2), ...]`. Subsequent rows are positional
        parameter slots. A row with `line1 == "*"` marks the keyword-only boundary. A trailing row
        with `line1 == "Returns:"` is appended when any version has a return annotation. Empty slots
        use `("—", "")`.
    """
    entries = history.changed_entries if changes_only else history.entries
    present_entries = [e for e in entries if e.present and e.symbol_info is not None]

    if not present_entries:
        return []

    versions = [e.version for e in present_entries]
    header: list[tuple[str, str]] = [("", v) for v in versions]

    # Augment each version's params with * separators
    augmented_params = [
        _augment_params_with_separators(e.symbol_info.parameters)  # type: ignore[union-attr]
        for e in present_entries
    ]

    # Determine the maximum parameter count across all versions
    max_params = max(len(p) for p in augmented_params)

    rows: list[list[tuple[str, str]]] = [header]
    empty_cell: tuple[str, str] = ("\u2014", "")

    for slot in range(max_params):
        row: list[tuple[str, str]] = []
        for params in augmented_params:
            if slot < len(params):
                row.append(_cell_lines(params[slot]))
            else:
                row.append(empty_cell)
        rows.append(row)

    # Return-type row
    return_values: list[tuple[str, str]] = []
    has_return = False
    for entry in present_entries:
        assert entry.symbol_info is not None
        ann = entry.symbol_info.return_annotation
        if ann:
            has_return = True
            return_values.append(("Returns:", ann))
        else:
            return_values.append(("Returns:", "\u2014"))
    if has_return:
        rows.append(return_values)

    return rows


def evolution_table_text(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> str:
    """
    Render the evolution table as aligned plain-text (for terminal output).

    Each cell is two lines: the parameter name and its type/default.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    str
        A formatted text table.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return "(no data)"

    header = rows[0]
    body = rows[1:]
    n_cols = len(header)

    # Compute column widths (widest of: version label, any param name, any type line)
    widths = [0] * n_cols
    for _, version in header:
        for i in range(n_cols):
            widths[i] = max(widths[i], len(header[i][1]))
    for row in body:
        for i, (line1, line2) in enumerate(row):
            widths[i] = max(widths[i], len(line1), len(line2))

    col_sep = "  \u2502  "
    lines: list[str] = []

    # Header row (version labels)
    hdr_line = col_sep.join(header[i][1].center(widths[i]) for i in range(n_cols))
    lines.append(hdr_line)
    lines.append(col_sep.join("\u2500" * widths[i] for i in range(n_cols)))

    # Body rows — each logical row is two text lines
    for row_idx, row in enumerate(body):
        line1_parts = []
        line2_parts = []
        for i, (l1, l2) in enumerate(row):
            line1_parts.append(l1.ljust(widths[i]))
            line2_parts.append(l2.ljust(widths[i]))
        lines.append(col_sep.join(line1_parts))
        lines.append(col_sep.join(line2_parts))
        # Thin separator between parameter slots (not after the last)
        if row_idx < len(body) - 1:
            lines.append(col_sep.join("\u2504" * widths[i] for i in range(n_cols)))

    return "\n".join(lines)


def evolution_table_html(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
    disclosure: bool = False,
    summary_text: str | None = None,
) -> str:
    """
    Render the evolution table as an HTML `<table>`.

    Each body cell contains the parameter name on one line and the type/default on a second line.
    When *disclosure* is True the table is wrapped in a `<details>` element so it starts collapsed.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If True (default), only include versions where the symbol changed.
    disclosure
        Wrap the table in a `<details>/<summary>` element.
    summary_text
        Custom text for the `<summary>` label. Defaults to `"Signature evolution for <symbol>"`.

    Returns
    -------
    str
        An HTML string.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return "<!-- no evolution data -->"

    header = rows[0]
    body = rows[1:]

    # Build a version→date lookup from the history entries
    date_map: dict[str, str] = {}
    entries = history.changed_entries if changes_only else history.entries
    for entry in entries:
        if entry.date:
            date_map[entry.version] = entry.date

    parts: list[str] = []
    parts.append('<table class="gd-evolution-table">')

    # Header
    parts.append("  <thead>")
    parts.append("    <tr>")
    for _, version in header:
        date = date_map.get(version)
        title_attr = f' title="{_escape_html(date)}"' if date else ""
        parts.append(f"      <th{title_attr}>{_escape_html(version)}</th>")
    parts.append("    </tr>")
    parts.append("  </thead>")

    # Body
    parts.append("  <tbody>")
    for row in body:
        parts.append("    <tr>")
        for line1, line2 in row:
            is_absent = line1 == "\u2014" and not line2
            is_star = line1 == "*" and not line2
            is_return = line1 == "Returns:"
            if is_absent:
                parts.append('      <td class="gd-evo-absent">\u2014</td>')
            elif is_star:
                parts.append('      <td class="gd-evo-separator">*</td>')
            elif is_return:
                type_html = _escape_html(line2) if line2 else ""
                inner = '<span class="gd-evo-return-label">Returns:</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
            else:
                name_html = _escape_html(line1)
                type_html = _escape_html(line2) if line2 else ""
                inner = f'<span class="gd-evo-name">{name_html}</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
        parts.append("    </tr>")
    parts.append("  </tbody>")
    parts.append("</table>")

    table_html = "\n".join(parts)

    if disclosure:
        if summary_text:
            label = summary_text
        else:
            template = translate("evo_disclosure_summary")
            label = template.format(symbol=_escape_html(history.symbol_name))
        return (
            f'<details class="gd-evolution-disclosure">\n'
            f"  <summary>{label}</summary>\n"
            f"  {table_html}\n"
            f"</details>"
        )

    return table_html


_EVOLUTION_TABLE_CSS = """\
<style>
.gd-evolution-table {
  border-collapse: collapse;
  font-size: 0.8em;
  width: 100%;
  margin-top: 0.5em;
}
.gd-evolution-table th {
  background: var(--bs-tertiary-bg, #f0f0f0);
  padding: 0.5em 1em;
  text-align: center;
  border: 1px solid var(--bs-border-color, #dee2e6);
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  cursor: help;
}
.gd-evolution-table td {
  padding: 0.5em 1em;
  border: 1px solid var(--bs-border-color, #dee2e6);
  vertical-align: top;
  min-width: 8em;
}
.gd-evo-name {
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  color: var(--bs-emphasis-color, #212529);
}
.gd-evo-type {
  font-family: var(--bs-font-monospace, monospace);
  font-size: 0.88em;
  color: var(--bs-secondary-color, #6c757d);
}
.gd-evo-absent {
  text-align: center;
  color: var(--bs-secondary-color, #adb5bd);
  vertical-align: middle;
}
.gd-evo-separator {
  text-align: center;
  font-family: var(--bs-font-monospace, monospace);
  font-weight: 600;
  color: var(--bs-secondary-color, #6c757d);
  vertical-align: middle;
}
.gd-evo-return-label {
  font-weight: 600;
  font-style: italic;
  color: var(--bs-emphasis-color, #212529);
}
.gd-evolution-disclosure summary {
  cursor: pointer;
  font-weight: 600;
  margin-bottom: 0.5em;
}
</style>"""


def render_evolution_table(
    project_path: str | Path,
    symbol: str,
    *,
    package: str | None = None,
    old_version: str | None = None,
    new_version: str | None = None,
    changes_only: bool = True,
    disclosure: bool = False,
    summary_text: str | None = None,
    include_css: bool = True,
) -> str:
    """
    Generate a self-contained HTML block for a symbol's evolution table.

    This is the high-level entry point that combines git history lookup, parameter evolution
    analysis, and HTML rendering into a single call. The output is ready to be inserted into a
    documentation page (e.g., via a `%` directive or a Quarto shortcode).

    Parameters
    ----------
    project_path
        Root of the git repository.
    symbol
        Fully qualified or short name of the symbol to track (e.g., `"build"` or
        `"GreatDocs.build"`).
    package
        Python package name. Auto-detected from *project_path* if omitted.
    old_version
        Earliest version tag to include. If omitted, starts from the first tag where the symbol
        appears.
    new_version
        Latest version tag to include. If omitted, goes through the most recent tag.
    changes_only
        If `True` (default), only show versions where the signature actually changed.
    disclosure
        If `True` (default), wrap the table in a collapsible `<details>/<summary>` element.
    summary_text
        Custom label for the `<summary>` element. Defaults to
        `"Signature evolution for <symbol>()"`.
    include_css
        If `True` (default), prepend the CSS `<style>` block so the output is fully self-contained.
        Set to `False` when the page already includes the styles (e.g., multiple tables on one
        page).

    Returns
    -------
    str
        A complete HTML string (optionally with embedded CSS) that can be inserted directly into a
        page. Returns an HTML comment `<!-- no evolution data for <symbol> -->` when the symbol has
        no history.

    Examples
    --------
    >>> html = render_evolution_table(".", "build")  # doctest: +SKIP
    >>> print(html[:30])                             # doctest: +SKIP
    <style>
    .gd-evolution-table {
    """
    project_root = Path(project_path).resolve()

    # Resolve tags
    all_tags = list_version_tags(project_root)
    if not all_tags:
        return f"<!-- no version tags found for {_escape_html(symbol)} -->"

    # Filter tag range
    tags = _filter_tag_range(all_tags, old_version, new_version)
    if not tags:
        return f"<!-- no matching tags for {_escape_html(symbol)} -->"

    # Build history
    history = symbol_history(project_root, symbol, package_name=package, tags=tags)
    if history is None or not history.entries:
        return f"<!-- no evolution data for {_escape_html(symbol)} -->"

    # Render HTML table
    html = evolution_table_html(
        history,
        changes_only=changes_only,
        disclosure=disclosure,
        summary_text=summary_text,
    )

    if html.startswith("<!--"):
        return html

    if include_css:
        return f"{_EVOLUTION_TABLE_CSS}\n{html}"
    return html


def render_evolution_table_from_dict(
    data: dict,
    *,
    disclosure: bool = False,
    summary_text: str | None = None,
    include_css: bool = True,
) -> str:
    """
    Render an evolution table from a JSON-compatible dict.

    This accepts the same schema produced by :func:`evolution_table_to_dict` (or loaded from a
    `.json` file) and renders it as a self-contained HTML block. This is useful for demo tables,
    pre-computed snapshots, or CI-generated data where a live git repository is not available.

    Parameters
    ----------
    data
        A dict matching the `evolution_table_to_dict` schema::

            {
              "symbol": "build",
              "versions": ["v1.0", "v2.0"],
              "slots": [{"position": 0, "cells": [...]}],
              "returns": ["None", "int"],       // optional
              "dates": ["2024-01-15", null]     // optional
            }
    disclosure
        Wrap in a `<details>/<summary>` element.
    summary_text
        Custom `<summary>` label.
    include_css
        Prepend the `<style>` block.

    Returns
    -------
    str
        A complete HTML string.
    """
    versions: list[str] = data.get("versions", [])
    if not versions:
        return "<!-- no evolution data -->"

    symbol_name: str = data.get("symbol", "unknown")
    dates: list[str | None] = data.get("dates", [])
    n_cols = len(versions)

    # Build the rows structure: list[list[tuple[str, str]]]
    header: list[tuple[str, str]] = [("", v) for v in versions]
    rows: list[list[tuple[str, str]]] = [header]
    empty_cell: tuple[str, str] = ("\u2014", "")

    for slot in data.get("slots", []):
        # Handle * separator slots
        if "separator" in slot:
            row: list[tuple[str, str]] = [("*", "")] * n_cols
            rows.append(row)
            continue

        cells = slot.get("cells", [])
        row = []
        for cell in cells:
            if cell is None:
                row.append(empty_cell)
            else:
                name = cell.get("name", "")
                type_str = cell.get("type") or ""
                default = cell.get("default")
                line2_parts: list[str] = []
                if type_str:
                    line2_parts.append(type_str)
                if default is not None:
                    line2_parts.append(f"= {default}")
                row.append((name, " ".join(line2_parts)))
        # Pad if fewer cells than versions
        while len(row) < n_cols:
            row.append(empty_cell)
        rows.append(row)

    # Return-type row
    returns: list[str | None] | None = data.get("returns")
    if returns and any(r is not None for r in returns):
        ret_row: list[tuple[str, str]] = []
        for r in returns:
            ret_row.append(("Returns:", r if r else "\u2014"))
        while len(ret_row) < n_cols:
            ret_row.append(("Returns:", "\u2014"))
        rows.append(ret_row)

    # Build date map
    date_map: dict[str, str] = {}
    for i, v in enumerate(versions):
        if i < len(dates) and dates[i]:
            date_map[v] = dates[i]  # type: ignore[assignment]

    # Render HTML using the same logic as evolution_table_html
    body = rows[1:]
    parts: list[str] = []
    parts.append('<table class="gd-evolution-table">')
    parts.append("  <thead>")
    parts.append("    <tr>")
    for _, version in header:
        date = date_map.get(version)
        title_attr = f' title="{_escape_html(date)}"' if date else ""
        parts.append(f"      <th{title_attr}>{_escape_html(version)}</th>")
    parts.append("    </tr>")
    parts.append("  </thead>")

    parts.append("  <tbody>")
    for row in body:
        parts.append("    <tr>")
        for line1, line2 in row:
            is_absent = line1 == "\u2014" and not line2
            is_star = line1 == "*" and not line2
            is_return = line1 == "Returns:"
            if is_absent:
                parts.append('      <td class="gd-evo-absent">\u2014</td>')
            elif is_star:
                parts.append('      <td class="gd-evo-separator">*</td>')
            elif is_return:
                type_html = _escape_html(line2) if line2 else ""
                inner = '<span class="gd-evo-return-label">Returns:</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
            else:
                name_html = _escape_html(line1)
                type_html = _escape_html(line2) if line2 else ""
                inner = f'<span class="gd-evo-name">{name_html}</span>'
                if type_html:
                    inner += f'<br><span class="gd-evo-type">{type_html}</span>'
                parts.append(f"      <td>{inner}</td>")
        parts.append("    </tr>")
    parts.append("  </tbody>")
    parts.append("</table>")

    table_html = "\n".join(parts)

    if disclosure:
        if summary_text:
            label = summary_text
        else:
            template = translate("evo_disclosure_summary")
            label = template.format(symbol=_escape_html(symbol_name))
        table_html = (
            f'<details class="gd-evolution-disclosure">\n'
            f"  <summary>{label}</summary>\n"
            f"  {table_html}\n"
            f"</details>"
        )

    if include_css:
        return f"{_EVOLUTION_TABLE_CSS}\n{table_html}"
    return table_html


def _filter_tag_range(
    tags: list[str],
    old_version: str | None,
    new_version: str | None,
) -> list[str]:
    """Return the sub-list of *tags* between *old_version* and *new_version*.

    Both bounds are inclusive. If a bound is `None`, the corresponding end of the list is used. If a
    bound is not found in *tags*, the full list is returned.
    """
    if old_version is None and new_version is None:
        return tags

    start = 0
    end = len(tags)

    if old_version is not None:
        for i, t in enumerate(tags):
            if t == old_version:
                start = i
                break

    if new_version is not None:
        for i, t in enumerate(tags):
            if t == new_version:
                end = i + 1
                break

    return tags[start:end]


def evolution_table_to_dict(
    history: SymbolHistory,
    *,
    changes_only: bool = True,
) -> dict:
    """
    Serialize the positional evolution table to a JSON-compatible dict.

    The returned structure captures everything needed to render the table in a documentation page,
    CI report, or external tool.

    Parameters
    ----------
    history
        A `SymbolHistory` for the symbol.
    changes_only
        If `True` (default), only include versions where the symbol changed.

    Returns
    -------
    dict
        Schema::

            {
              "symbol": "build",
              "package": "my_package",
              "versions": ["v1.0", "v2.0", "v3.0"],
              "slots": [
                {
                  "position": 0,
                  "cells": [
                    {"name": "src", "type": "str", "default": null},
                    {"name": "src", "type": "Path", "default": null},
                    ...
                  ]
                },
                ...
              ],
              "returns": ["None", "None", "int"]   // omitted if no return types
            }

        Each `cells` list is parallel to `versions`. A `null` entry in `cells` means the parameter
        slot did not exist in that version.
    """
    rows = evolution_table(history, changes_only=changes_only)
    if not rows:
        return {
            "symbol": history.symbol_name,
            "package": history.package_name,
            "versions": [],
            "slots": [],
        }

    header = rows[0]
    body = rows[1:]
    versions = [v for _, v in header]

    slots: list[dict] = []
    returns: list[str | None] = None  # type: ignore[assignment]

    for row in body:
        # Detect if this is the return-type row
        if any(line1 == "Returns:" for line1, _ in row):
            returns = []
            for line1, line2 in row:
                returns.append(line2 if line2 and line2 != "\u2014" else None)
            continue

        # Detect * separator row
        if any(line1 == "*" and not line2 for line1, line2 in row):
            slots.append({"position": len(slots), "separator": "*"})
            continue

        slot_cells: list[dict | None] = []
        for line1, line2 in row:
            if line1 == "\u2014" and not line2:
                slot_cells.append(None)
            else:
                # Parse line2 back into type and default
                cell: dict = {"name": line1}
                if line2:
                    if " = " in line2:
                        type_part, default_part = line2.split(" = ", 1)
                        cell["type"] = type_part if type_part else None
                        cell["default"] = default_part
                    else:
                        cell["type"] = line2
                        cell["default"] = None
                else:
                    cell["type"] = None
                    cell["default"] = None
                slot_cells.append(cell)

        slots.append(
            {
                "position": len(slots),
                "cells": slot_cells,
            }
        )

    result: dict = {
        "symbol": history.symbol_name,
        "package": history.package_name,
        "versions": versions,
        "slots": slots,
    }
    if returns is not None:
        result["returns"] = returns

    return result


def timeline_to_mermaid(timeline: list[dict]) -> str:
    """Render a timeline as a Mermaid bar chart."""
    lines = [
        "xychart-beta",
        '    title "API Surface Growth"',
        "    x-axis [{}]".format(", ".join(f'"{e["version"]}"' for e in timeline)),
        '    y-axis "Symbol count"',
        "    bar [{}]".format(", ".join(str(e["symbols"]) for e in timeline)),
    ]
    return "\n".join(lines)
