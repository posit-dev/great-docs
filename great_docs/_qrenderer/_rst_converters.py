"""RST / Sphinx / Google-style docstring → Markdown converters.

All text-level transforms that convert reStructuredText markup, Sphinx field
lists, and Google-style sections into Quarto-compatible Markdown live here.
"""

from __future__ import annotations

import re

# Shared text utilities --------------------------------------------------------


def escape(val: str):
    return f"`{val}`"


def sanitize(val: str, allow_markdown=False, escape_quotes=False, preserve_newlines=False):
    if preserve_newlines:
        res = val
    else:
        res = val.replace("\n", " ")
    res = res.replace("|", "\\|")

    if escape_quotes:
        res = res.replace("'", r"\'").replace('"', r"\"")

    if not allow_markdown:
        return res.replace("[", "\\[").replace("]", "\\]")

    return res


# RST text transforms --------------------------------------------------------
# These were previously applied as QMD-level patches in core.py (Steps 1.5–1.8).
# Now they are applied at render time so the QMD is correct from the start.

_RST_CODE_BLOCK_RE = re.compile(
    r"^(.*?)::[ ]*\n"  # line ending in ::
    r"(\n)"  # mandatory blank line
    r"((?:[ ]{4,}\S.*\n?)+)",  # one or more indented lines (≥4 spaces)
    re.MULTILINE,
)

_RST_DIRECTIVES = frozenset(
    {
        "versionadded",
        "versionchanged",
        "deprecated",
        "note",
        "warning",
        "caution",
        "danger",
        "important",
        "tip",
        "hint",
        "seealso",
        "todo",
    }
)


def _replace_rst_code_block(m: re.Match) -> str:
    """Callback for _RST_CODE_BLOCK_RE — converts one RST ``::`` block."""
    prefix_text = m.group(1)
    indented_block = m.group(3)

    # Skip known RST directives (e.g. ``.. note::``) — preserved for
    # post-render's directive handler.
    stripped_prefix = prefix_text.strip()
    if stripped_prefix.startswith(".."):
        directive_name = stripped_prefix[2:].strip()
        if directive_name == "math":
            # ``.. math::`` → display math ``$$…$$``
            lines = indented_block.splitlines()
            if lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
                dedented = "\n".join(line[min_indent:] for line in lines)
            else:
                dedented = indented_block
            return f"\n$$\n{dedented.strip()}\n$$\n"
        if directive_name in _RST_DIRECTIVES:
            return m.group(0)  # leave untouched

    # Dedent the code block
    lines = indented_block.splitlines()
    if lines:
        min_indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
        dedented = "\n".join(line[min_indent:] for line in lines)
    else:
        dedented = indented_block

    prefix = prefix_text.rstrip()
    if prefix:
        prefix += ":"
    return f"{prefix}\n\n```python\n{dedented}\n```\n"


def _smart_dedent(text: str) -> str:
    """Dedent text using the first non-blank line's indent as the margin.

    Unlike `textwrap.dedent`, this tolerates lines with *less* indentation than the margin (e.g. a
    string-literal continuation at column 0 that made `inspect.cleandoc` choose margin=0). We strip
    up to *margin* leading spaces from every line, so lines already at 0-indent stay put.
    """
    lines = text.splitlines(True)

    # Determine margin from first non-blank line
    margin = 0
    for line in lines:
        stripped = line.strip()
        if stripped:
            margin = len(line) - len(line.lstrip())
            break

    if not margin:
        return text

    result: list[str] = []
    for line in lines:
        if line.strip():
            current_indent = len(line) - len(line.lstrip())
            strip_amount = min(margin, current_indent)
            result.append(line[strip_amount:])
        else:
            result.append(line)
    return "".join(result)


def _convert_rst_text(text: str) -> str:
    """Apply all RST -> Markdown transforms to a docstring text section."""
    # Fix docstrings where inspect.cleandoc failed to dedent (e.g. a
    # multiline string literal created a 0-indent line, preventing
    # proper margin detection).
    text = _smart_dedent(text)

    # Quarto executable cell syntax -> regular fenced code blocks
    # e.g. ```{python} -> ```python so Quarto doesn't treat them as cells
    text = re.sub(r"```\{\s*(\w+)\s*\}", r"```\1", text)

    # RST `::` code blocks -> fenced code blocks (includes `.. math::`)
    text = _RST_CODE_BLOCK_RE.sub(_replace_rst_code_block, text)

    # RST inline math `:math:`…`` -> `$…$`
    text = re.sub(r":math:`([^`]+)`", r"$\1$", text)

    # Sphinx cross-reference roles -> markdown code spans
    text = _convert_sphinx_roles(text)

    # RST admonition / version directives -> Quarto callout blocks
    text = _convert_rst_directives(text)

    # RST simple tables -> Markdown pipe tables
    text = _convert_rst_simple_tables(text)

    # RST grid tables -> Markdown pipe tables
    text = _convert_rst_grid_tables(text)

    # RST citation markers ``.. [1] Text`` -> numbered list
    text = _convert_rst_citations(text)

    return text


# RST citation converter ------------------------------------------------------

# Match lines/paragraphs containing `.. [N]` citation markers.
_RST_CITATION_RE = re.compile(
    r"^([ \t]*)\.\.\s+\[(\d+)\]\s+",
    re.MULTILINE,
)


def _convert_rst_citations(text: str) -> str:
    """Convert RST `.. [N] body` citation markers to a numbered markdown list.

    Input like::

        .. [1] Author (Year). "Title."
        .. [2] https://example.com

    becomes::

        1. Author (Year). "Title."
        2. <https://example.com>
    """
    if not _RST_CITATION_RE.search(text):
        return text

    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        m = _RST_CITATION_RE.match(lines[i])
        if m:
            num = m.group(2)
            body = lines[i][m.end() :]
            # Collect continuation lines (indented more than the marker)
            while i + 1 < len(lines) and lines[i + 1] and lines[i + 1][0] in (" ", "\t"):
                i += 1
                body += " " + lines[i].strip()
            body = body.strip()
            # Auto-link bare URLs
            body = re.sub(
                r"(?<![<\"])(https?://\S+)(?![>\"])",
                r"<\1>",
                body,
            )
            result.append(f"{num}. {body}")
        else:
            result.append(lines[i])
        i += 1
    return "\n".join(result)


# RST table converters -------------------------------------------------------


def _convert_rst_simple_tables(text: str) -> str:
    """Convert RST simple tables (`=====` delimited) to Markdown pipe tables."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if re.match(r"^=+(\s+=+)+\s*$", line):
            table_lines = [line]
            sep_count = 1
            second_col_match = re.search(r"\s+(=+)", line)
            second_col_start = second_col_match.start(1) if second_col_match else 4
            j = i + 1
            while j < len(lines):
                cur = lines[j]
                is_sep = bool(re.match(r"^=+(\s+=+)+\s*$", cur))
                table_lines.append(cur)
                if is_sep:
                    sep_count += 1
                    if sep_count >= 3:
                        j += 1
                        break
                    peek = j + 1
                    if (
                        peek < len(lines)
                        and lines[peek].strip()
                        and not re.match(r"^=+(\s+=+)+\s*$", lines[peek])
                        and len(lines[peek]) > second_col_start
                        and lines[peek][second_col_start] != " "
                    ):
                        pass
                    else:
                        j += 1
                        break
                j += 1

            md_table = _rst_simple_table_to_md(table_lines)
            if md_table is not None:
                result.append(md_table)
                i = j
                continue
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def _convert_rst_grid_tables(text: str) -> str:
    """Convert RST grid tables (`+---+` delimited) to Markdown pipe tables."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if re.match(r"^\+[-=]+(\+[-=]+)+\+\s*$", line):
            table_lines = [line]
            j = i + 1
            while j < len(lines):
                if re.match(r"^\+[-=]+(\+[-=]+)+\+\s*$", lines[j]):
                    table_lines.append(lines[j])
                    if j + 1 >= len(lines) or not re.match(r"^\|", lines[j + 1]):
                        j += 1
                        break
                elif re.match(r"^\|", lines[j]):
                    table_lines.append(lines[j])
                else:
                    break
                j += 1

            md_table = _rst_grid_table_to_md(table_lines)
            if md_table is not None:
                result.append(md_table)
                i = j
                continue
            else:
                result.append(line)
                i += 1
        else:
            result.append(line)
            i += 1

    return "\n".join(result)


def _rst_simple_table_to_md(table_lines: list[str]) -> str | None:
    """Convert an RST simple table (list of raw lines) to a Markdown pipe table."""
    separators = [
        (idx, line) for idx, line in enumerate(table_lines) if re.match(r"^=+(\s+=+)+\s*$", line)
    ]
    if len(separators) < 2:
        return None

    sep_line = separators[0][1]
    col_spans: list[tuple[int, int]] = []
    for m in re.finditer(r"=+", sep_line):
        col_spans.append((m.start(), m.end()))

    if not col_spans:
        return None

    def _extract_cells(line: str) -> list[str]:
        cells = []
        for idx, (start, _end) in enumerate(col_spans):
            if idx + 1 < len(col_spans):
                next_start = col_spans[idx + 1][0]
                cell = line[start:next_start] if len(line) > start else ""
            else:
                cell = line[start:] if len(line) > start else ""
            cells.append(cell.strip())
        return cells

    first_sep_idx = separators[0][0]
    last_sep_idx = separators[-1][0]
    data_rows: list[list[str]] = []
    header_rows: list[list[str]] = []

    if len(separators) == 2:
        for idx in range(first_sep_idx + 1, last_sep_idx):
            line = table_lines[idx]
            if not re.match(r"^=+(\s+=+)+\s*$", line):
                data_rows.append(_extract_cells(line))
        if data_rows:
            header_rows = [data_rows[0]]
            data_rows = data_rows[1:]
    elif len(separators) >= 3:
        second_sep_idx = separators[1][0]
        for idx in range(first_sep_idx + 1, second_sep_idx):
            line = table_lines[idx]
            if not re.match(r"^=+(\s+=+)+\s*$", line):
                header_rows.append(_extract_cells(line))
        for idx in range(second_sep_idx + 1, last_sep_idx):
            line = table_lines[idx]
            if not re.match(r"^=+(\s+=+)+\s*$", line):
                data_rows.append(_extract_cells(line))

    if not header_rows:
        return None

    num_cols = len(col_spans)
    md_lines = []
    header = header_rows[-1]
    while len(header) < num_cols:
        header.append("")
    md_lines.append("| " + " | ".join(header) + " |")
    md_lines.append("| " + " | ".join("---" for _ in range(num_cols)) + " |")
    for row in data_rows:
        while len(row) < num_cols:
            row.append("")
        md_lines.append("| " + " | ".join(row) + " |")
    return "\n".join(md_lines)


def _rst_grid_table_to_md(table_lines: list[str]) -> str | None:
    """Convert an RST grid table (list of raw lines) to a Markdown pipe table."""
    border_line = table_lines[0]
    col_positions = [m.start() for m in re.finditer(r"\+", border_line)]

    if len(col_positions) < 2:
        return None

    col_spans = list(zip(col_positions[:-1], col_positions[1:]))

    def _extract_cells(line: str) -> list[str]:
        cells = []
        for start, end in col_spans:
            cell = line[start + 1 : end] if len(line) > start else ""
            cells.append(cell.strip())
        return cells

    header_rows: list[list[str]] = []
    body_rows: list[list[str]] = []
    has_header_sep = False
    current_rows: list[list[str]] = []

    for line in table_lines:
        if re.match(r"^\+[=+]+\+\s*$", line):
            has_header_sep = True
            header_rows = current_rows
            current_rows = []
        elif re.match(r"^\+[-+]+\+\s*$", line):
            continue
        elif line.startswith("|"):
            current_rows.append(_extract_cells(line))

    body_rows = current_rows

    if has_header_sep:
        if not header_rows:
            return None
    else:
        all_rows = body_rows
        if not all_rows:
            return None
        header_rows = [all_rows[0]]
        body_rows = all_rows[1:]

    num_cols = len(col_spans)
    md_lines = []
    header = header_rows[-1] if header_rows else [""] * num_cols
    while len(header) < num_cols:
        header.append("")
    md_lines.append("| " + " | ".join(header) + " |")
    md_lines.append("| " + " | ".join("---" for _ in range(num_cols)) + " |")
    for row in body_rows:
        while len(row) < num_cols:
            row.append("")
        md_lines.append("| " + " | ".join(row) + " |")
    return "\n".join(md_lines)


# Sphinx role conversion ------------------------------------------------------


_CALLABLE_RST_ROLES = frozenset({"func", "meth"})

# Roles we recognise (a subset of Sphinx Python domain + generic roles)
_SPHINX_ROLE_NAMES = "exc|class|func|meth|attr|const|mod|obj|data|type"

_SPHINX_ROLE_RE = re.compile(rf":(?:py:)?(?P<role>{_SPHINX_ROLE_NAMES}):`(?P<inner>[^`]+)`")


def _convert_sphinx_roles(text: str) -> str:
    """Convert Sphinx cross-reference roles to markdown code spans.

    ``:func:`name``` → ```name()```
    ``:class:`name``` → ```name```
    ``:py:exc:`ValueError``` → ```ValueError```
    """

    def _replace(m: re.Match) -> str:
        role = m.group("role")
        inner = m.group("inner")
        if role in _CALLABLE_RST_ROLES and not inner.endswith("()"):
            inner += "()"
        return f"`{inner}`"

    return _SPHINX_ROLE_RE.sub(_replace, text)


# RST directive → Quarto callout conversion -----------------------------------


_RST_DIRECTIVE_CALLOUT_MAP: dict[str, str] = {
    "note": "note",
    "warning": "warning",
    "caution": "caution",
    "danger": "important",
    "important": "important",
    "tip": "tip",
    "hint": "tip",
}

_RST_VERSION_DIRECTIVES = frozenset({"versionadded", "versionchanged", "deprecated"})

_RST_VERSION_LABELS: dict[str, str] = {
    "versionadded": "Added in version",
    "versionchanged": "Changed in version",
    "deprecated": "Deprecated since version",
}

# Build alternation of all recognised RST directive names
_ALL_RST_DIRECTIVE_NAMES = sorted(
    set(_RST_DIRECTIVE_CALLOUT_MAP) | _RST_VERSION_DIRECTIVES,
    key=len,
    reverse=True,
)
_RST_DIRECTIVE_NAME_PAT = "|".join(re.escape(n) for n in _ALL_RST_DIRECTIVE_NAMES)


def _rst_directive_to_callout(name: str, body: str, inline: str = "") -> str:
    """Build a Quarto callout div from a parsed RST directive."""
    if name in _RST_VERSION_DIRECTIVES:
        label = _RST_VERSION_LABELS[name]
        # Version number may be on the inline portion or the start of body
        version_text = (inline.strip() + " " + body.strip()).strip()
        parts = version_text.split(None, 1) if version_text else []
        version = parts[0] if parts else ""
        desc = parts[1] if len(parts) > 1 else ""
        callout = "warning" if name == "deprecated" else "note"
        title = f"{label} {version}" if version else label
        body_line = f"\n{desc}\n" if desc else "\n"
        return f'::: {{.callout-{callout} title="{title}"}}{body_line}:::'
    else:
        callout = _RST_DIRECTIVE_CALLOUT_MAP.get(name, "note")
        content = (inline.strip() + " " + body.strip()).strip()
        body_line = f"\n{content}\n" if content else "\n"
        return f"::: {{.callout-{callout}}}{body_line}:::"


def _convert_rst_directives(text: str) -> str:
    """Convert RST admonition / version directives to Quarto callout blocks.

    Handles inline form (``.. note:: body``) and block form
    (``.. note::\\n\\n    indented body``).
    """

    # --- block form (with optional blank line before indented body) ----------
    def _replace_block(m: re.Match) -> str:
        name = m.group("name")
        inline = m.group("inline") or ""
        raw_body = m.group("body")
        # Dedent the indented body
        lines = raw_body.splitlines()
        if lines:
            min_indent = min(
                (len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()),
                default=0,
            )
            body = "\n".join(ln[min_indent:] for ln in lines)
        else:
            body = ""
        return _rst_directive_to_callout(name, body, inline)

    text = re.sub(
        rf"^\.\.\s+(?P<name>{_RST_DIRECTIVE_NAME_PAT})::"
        rf"\s*(?P<inline>[^\n]*)\n"
        rf"(?:\n)?"  # optional blank line
        rf"(?P<body>(?:[ ]{{4,}}\S.*\n?)+)",
        _replace_block,
        text,
        flags=re.MULTILINE,
    )

    # --- inline form (body text on the same line, no block follows) ----------
    def _replace_inline(m: re.Match) -> str:
        name = m.group("name")
        body = m.group("body").strip()
        return _rst_directive_to_callout(name, "", body)

    text = re.sub(
        rf"^\.\.\s+(?P<name>{_RST_DIRECTIVE_NAME_PAT})::\s*(?P<body>[^\n]+)$",
        _replace_inline,
        text,
        flags=re.MULTILINE,
    )

    # --- bare form (directive with no body at all) ---------------------------
    text = re.sub(
        rf"^\.\.\s+(?P<name>{_RST_DIRECTIVE_NAME_PAT})::\s*$",
        lambda m: _rst_directive_to_callout(m.group("name"), ""),
        text,
        flags=re.MULTILINE,
    )

    return text


# Bold section-header conversion ----------------------------------------------


_BOLD_SECTION_NAMES: dict[str, str] = {
    "Examples": "examples",
    "Example": "examples",
    "Notes": "notes",
    "Note": "notes",
    "References": "references",
    "Warnings": "warnings",
    "Warning": "warnings",
    "See Also": "see-also",
}

_BOLD_SECTION_PAT = "|".join(re.escape(n) for n in _BOLD_SECTION_NAMES)


def _convert_bold_section_headers(text: str, heading_level: int) -> str:
    r"""Convert ``**Examples**::`` bold headers into proper QMD section headings.

    ``**Examples**::`` → ``## Examples {.doc-section .doc-section-examples}``
    """
    hashes = "#" * heading_level

    def _replace(m: re.Match) -> str:
        name = m.group("name")
        slug = _BOLD_SECTION_NAMES.get(name, name.lower().replace(" ", "-"))
        return f"{hashes} {name} {{.doc-section .doc-section-{slug}}}"

    return re.sub(
        rf"\*\*(?P<name>{_BOLD_SECTION_PAT})\*\*::",
        _replace,
        text,
    )


# Sphinx field-list conversion ------------------------------------------------


_SPHINX_FIELD_RE = re.compile(
    r":(?P<directive>param|type|returns?|rtype|raises?)"
    r"(?:\s+(?P<name>[^:]*?))?"
    r":\s*(?P<body>(?:(?!:(?:param|type|returns?|rtype|raises?)\b).)*)",
    re.DOTALL,
)

# Match a block of text that contains at least one Sphinx field marker
_SPHINX_FIELD_BLOCK_RE = re.compile(r"(?:^|\n)(?=:(?:param|type|returns?|rtype|raises?)\b)")


def _convert_sphinx_fields(text: str, heading_level: int) -> str:
    """Parse Sphinx-style ``:param:`` / ``:returns:`` / ``:raises:`` field lists
    and generate proper QMD section headings with Markdown pipe tables.
    """
    if not _SPHINX_FIELD_BLOCK_RE.search(text):
        return text

    # Split text into "before fields" and "fields portion"
    first_field = re.search(r"(?:^|\n)\s*:(?:param|type|returns?|rtype|raises?)\b", text)
    if first_field is None:
        return text

    before = text[: first_field.start()].rstrip()
    fields_text = text[first_field.start() :]

    # Parse fields
    params: dict[str, dict[str, str]] = {}  # name → {desc, type}
    returns: list[dict[str, str]] = []
    raises: list[tuple[str, str]] = []

    for m in _SPHINX_FIELD_RE.finditer(fields_text):
        directive = m.group("directive")
        name = (m.group("name") or "").strip()
        body = (m.group("body") or "").strip()

        if directive == "param":
            params.setdefault(name, {"desc": "", "type": ""})
            params[name]["desc"] = body
        elif directive == "type":
            params.setdefault(name, {"desc": "", "type": ""})
            params[name]["type"] = body
        elif directive in ("returns", "return"):
            returns.append({"desc": body, "type": ""})
        elif directive == "rtype":
            if returns:
                returns[-1]["type"] = body
            else:
                returns.append({"desc": "", "type": body})
        elif directive in ("raises", "raise"):
            raises.append((name, body))

    if not params and not returns and not raises:
        return text

    hashes = "#" * heading_level
    parts: list[str] = []
    if before:
        parts.append(before)

    # Parameters table
    if params:
        header = "| Name | Type | Description | Default |"
        sep = "| --- | --- | --- | --- |"
        rows = []
        for pname, pinfo in params.items():
            ptype = sanitize(pinfo["type"], escape_quotes=True) if pinfo["type"] else ""
            pdesc = sanitize(pinfo["desc"], allow_markdown=True) if pinfo["desc"] else ""
            rows.append(f"| {pname} | {ptype} | {pdesc} | - |")
        table = "\n".join([header, sep, *rows])
        parts.append(f"{hashes} Parameters {{.doc-section .doc-section-parameters}}\n\n{table}")

    # Returns table
    if returns:
        header = "| Name | Type | Description |"
        sep = "| --- | --- | --- |"
        rows = []
        for rinfo in returns:
            rtype = sanitize(rinfo["type"], escape_quotes=True) if rinfo["type"] else ""
            rdesc = sanitize(rinfo["desc"], allow_markdown=True) if rinfo["desc"] else ""
            rows.append(f"|  | {rtype} | {rdesc} |")
        table = "\n".join([header, sep, *rows])
        parts.append(f"{hashes} Returns {{.doc-section .doc-section-returns}}\n\n{table}")

    # Raises table
    if raises:
        header = "| Name | Type | Description |"
        sep = "| --- | --- | --- |"
        rows = []
        for exc, desc in raises:
            exc_s = sanitize(exc, escape_quotes=True) if exc else ""
            desc_s = sanitize(desc, allow_markdown=True) if desc else ""
            rows.append(f"|  | {exc_s} | {desc_s} |")
        table = "\n".join([header, sep, *rows])
        parts.append(f"{hashes} Raises {{.doc-section .doc-section-raises}}\n\n{table}")

    return "\n\n".join(parts)


# Google-style section conversion ---------------------------------------------


_GOOGLE_PARAM_SECTIONS = frozenset({"Args", "Arguments", "Parameters", "Params"})
_GOOGLE_RETURN_SECTIONS = frozenset({"Returns", "Return"})
_GOOGLE_RAISE_SECTIONS = frozenset({"Raises", "Raise"})
_GOOGLE_PROSE_SECTIONS: dict[str, str] = {
    "Note": "notes",
    "Notes": "notes",
    "Example": "examples",
    "Examples": "examples",
    "Warning": "warnings",
    "Warnings": "warnings",
    "References": "references",
    "See Also": "see-also",
}

_ALL_GOOGLE_SECTIONS = sorted(
    _GOOGLE_PARAM_SECTIONS
    | _GOOGLE_RETURN_SECTIONS
    | _GOOGLE_RAISE_SECTIONS
    | set(_GOOGLE_PROSE_SECTIONS),
    key=len,
    reverse=True,
)
_GOOGLE_SECTION_PAT = "|".join(re.escape(s) for s in _ALL_GOOGLE_SECTIONS)

# Match a Google-style section header: ``SectionName:\n`` (at start of line,
# followed by indented body or by text on the same line).
_GOOGLE_SECTION_RE = re.compile(
    rf"^(?P<section>{_GOOGLE_SECTION_PAT}):\s*(?P<inline>[^\n]*)$",
    re.MULTILINE,
)


def _parse_google_entries(body: str) -> list[tuple[str, str]]:
    """Parse indented ``name: description`` entries from a Google-style section body.

    Returns a list of ``(name, description)`` tuples.
    """
    # Entries look like: ``name (type): description`` or ``name: desc``
    entry_re = re.compile(r"^(?P<name>[A-Za-z_]\w*)(?:\s*\([^)]*\))?\s*:\s*(?P<desc>.*)$")
    entries: list[tuple[str, str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = entry_re.match(line)
        if m:
            entries.append((m.group("name"), m.group("desc").strip()))
        elif entries:
            # Continuation line — append to last entry
            prev_name, prev_desc = entries[-1]
            entries[-1] = (prev_name, (prev_desc + " " + line).strip())
    return entries


def _parse_google_raises(body: str) -> list[tuple[str, str]]:
    """Parse ``ExceptionType: description`` entries from a Raises section."""
    entry_re = re.compile(r"^(?P<exc>[A-Z]\w+)\s*:\s*(?P<desc>.*)$")
    entries: list[tuple[str, str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        m = entry_re.match(line)
        if m:
            entries.append((m.group("exc"), m.group("desc").strip()))
        elif entries:
            prev_exc, prev_desc = entries[-1]
            entries[-1] = (prev_exc, (prev_desc + " " + line).strip())
    return entries


def _convert_google_sections(text: str, heading_level: int) -> str:
    """Parse Google-style docstring sections (``Args:``, ``Returns:``, etc.)
    and generate proper QMD section headings with tables or prose blocks.
    """
    if not _GOOGLE_SECTION_RE.search(text):
        return text

    hashes = "#" * heading_level
    result_parts: list[str] = []

    # Split text at section boundaries
    splits = list(_GOOGLE_SECTION_RE.finditer(text))
    if not splits:
        return text

    # Text before the first section
    before = text[: splits[0].start()].rstrip()
    if before:
        result_parts.append(before)

    for idx, m in enumerate(splits):
        section = m.group("section")
        inline = m.group("inline").strip()

        # Gather indented body lines that follow
        body_start = m.end() + 1  # skip the newline
        if idx + 1 < len(splits):
            body_end = splits[idx + 1].start()
        else:
            body_end = len(text)
        raw_body = text[body_start:body_end] if body_start < len(text) else ""

        # Collect indented lines (4-space or tab indented, or continuation)
        body_lines: list[str] = []
        for ln in raw_body.splitlines():
            if ln and (ln[0] == " " or ln[0] == "\t"):
                body_lines.append(ln)
            elif ln.strip() == "":
                body_lines.append("")
            else:
                break
        body = "\n".join(body_lines)
        # Dedent
        if body_lines:
            non_empty = [ln for ln in body_lines if ln.strip()]
            if non_empty:
                min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
                body = "\n".join(
                    ln[min_indent:] if len(ln) > min_indent else ln for ln in body_lines
                )

        full_body = (inline + "\n" + body).strip() if inline else body.strip()

        slug = None

        # --- Parameters sections ---
        if section in _GOOGLE_PARAM_SECTIONS:
            entries = _parse_google_entries(full_body)
            if entries:
                header_row = "| Name | Type | Description | Default |"
                sep_row = "| --- | --- | --- | --- |"
                rows = []
                for pname, pdesc in entries:
                    pdesc_s = sanitize(pdesc, allow_markdown=True)
                    rows.append(f"| {pname} |  | {pdesc_s} | - |")
                table = "\n".join([header_row, sep_row, *rows])
                result_parts.append(
                    f"{hashes} Parameters {{.doc-section .doc-section-parameters}}\n\n{table}"
                )
            else:
                result_parts.append(full_body)

        # --- Returns sections ---
        elif section in _GOOGLE_RETURN_SECTIONS:
            slug = "returns"
            result_parts.append(
                f"{hashes} Returns {{.doc-section .doc-section-{slug}}}\n\n{full_body}"
            )

        # --- Raises sections ---
        elif section in _GOOGLE_RAISE_SECTIONS:
            entries = _parse_google_raises(full_body)
            if entries:
                header_row = "| Name | Type | Description |"
                sep_row = "| --- | --- | --- |"
                rows = []
                for exc, desc in entries:
                    desc_s = sanitize(desc, allow_markdown=True)
                    rows.append(f"|  | {exc} | {desc_s} |")
                table = "\n".join([header_row, sep_row, *rows])
                result_parts.append(
                    f"{hashes} Raises {{.doc-section .doc-section-raises}}\n\n{table}"
                )
            else:
                result_parts.append(full_body)

        # --- Prose sections (Note, Examples, etc.) ---
        elif section in _GOOGLE_PROSE_SECTIONS:
            slug = _GOOGLE_PROSE_SECTIONS[section]
            result_parts.append(
                f"{hashes} {section} {{.doc-section .doc-section-{slug}}}\n\n{full_body}"
            )

        else:
            result_parts.append(full_body)

    return "\n\n".join(result_parts)


# Doctest fencing --------------------------------------------------------------


def _fence_doctest_blocks(text: str) -> str:
    """Wrap unfenced ``>>>`` doctest lines in ````python`` fenced code blocks.

    Detects consecutive lines that start with ``>>>`` or ``...`` (doctest
    continuation) and wraps each group in a fenced code block so Quarto renders
    them as syntax-highlighted Python instead of nested blockquotes.
    """
    lines = text.split("\n")
    result: list[str] = []
    doctest_buf: list[str] = []

    def _flush():
        if doctest_buf:
            result.append("```python")
            result.extend(doctest_buf)
            result.append("```")
            doctest_buf.clear()

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(">>> ") or stripped == ">>>" or stripped.startswith("... "):
            doctest_buf.append(line)
        else:
            _flush()
            result.append(line)

    _flush()
    return "\n".join(result)
