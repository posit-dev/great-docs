from __future__ import annotations

import re
import typing
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

from great_docs._renderer import ast as qast
from great_docs._renderer import layout
from great_docs._renderer._griffe_compat import dataclasses as dc
from great_docs._renderer._griffe_compat import docstrings as ds
from great_docs._renderer._griffe_compat import expressions as expr
from great_docs._renderer.ast import (
    DocstringSectionNotes,
    DocstringSectionSeeAlso,
    DocstringSectionWarnings,
    ExampleCode,
    ExampleText,
)
from great_docs._renderer.pandoc.blocks import DefinitionList
from great_docs._renderer.pandoc.inlines import Attr, Code, Inlines, Span, Strong

if typing.TYPE_CHECKING:
    pass


# utils -----------------------------------------------------------------------


def escape(val: str):
    return f"`{val}`"


def sanitize(val: str, allow_markdown=False, escape_quotes=False):
    res = val.replace("\n", " ").replace("|", "\\|")

    if escape_quotes:
        res = res.replace("'", r"\'").replace('"', r"\"")

    if not allow_markdown:
        return res.replace("[", "\\[").replace("]", "\\]")

    return res


def convert_rst_link_to_md(rst):
    expr_pat = r"((:external(\+[a-zA-Z\._]+))?(:[a-zA-Z\._]+)?:[a-zA-Z\._]+:`~?[a-zA-Z\._]+`)"

    return re.sub(expr_pat, r"[](\1)", rst, flags=re.MULTILINE)


def _simple_table(rows, headers):
    """Simple markdown table without tabulate dependency."""
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def _has_attr_section(el: dc.Docstring | None):
    if el is None:
        return False

    return any([isinstance(x, ds.DocstringSectionAttributes) for x in el.parsed])


def _sanitize_title(title: str):
    return re.sub(r"[^a-zA-Z0-9-]+", "", title.replace(" ", "-"))


def _escape_dunders(name: str) -> str:
    """Escape ``__name__`` patterns so Pandoc does not interpret them as bold.

    ``__repr__`` → ``\\_\\_repr\\_\\_``
    """
    return re.sub(r"__(\w+)__", r"\_\_\1\_\_", name)


# Dataclass field introspection -----------------------------------------------
# Griffe's static analysis may miss some dataclass fields (e.g. str, list, dict
# fields).  This helper dynamically imports the class and uses
# dataclasses.fields() to discover ALL fields, then merges with descriptions
# from the docstring's Parameters section.


def _is_griffe_dataclass(obj: "dc.Object | dc.Alias") -> bool:
    """Check whether a griffe object is a dataclass."""
    try:
        return "dataclass" in obj.labels
    except Exception:
        return False


def _is_non_callable_class(obj: "dc.Object | dc.Alias") -> bool:
    """Check whether a griffe class is a non-callable type (Enum, TypedDict).

    Enums are accessed via members (e.g., ``Color.RED``), not called.
    TypedDicts are structural type definitions, not constructors.
    """
    try:
        labels = getattr(obj, "labels", set())
        if "enum" in labels:
            return True
    except Exception:
        pass
    try:
        bases = getattr(obj, "bases", [])
        base_names = {str(b).rsplit(".", 1)[-1] for b in bases}
        if base_names & {"TypedDict", "Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"}:
            return True
    except Exception:
        pass
    return False


def _get_dataclass_field_names(obj: "dc.Object | dc.Alias") -> list[str] | None:
    """Dynamically import a class and return its dataclass field names.

    Returns None if the class cannot be imported or is not a dataclass.
    """
    import dataclasses as _dc
    import importlib

    path = obj.canonical_path if hasattr(obj, "canonical_path") else obj.path

    parts = path.rsplit(".", 1)
    if len(parts) != 2:
        return None

    module_path, class_name = parts

    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name, None)
        if cls is None or not _dc.is_dataclass(cls):
            return None
        return [f.name for f in _dc.fields(cls)]
    except Exception:
        return None


def _get_param_descriptions(obj: "dc.Object | dc.Alias") -> dict[str, str]:
    """Extract {param_name: description} from the docstring's Parameters section."""
    if obj.docstring is None:
        return {}

    descs: dict[str, str] = {}
    for section in obj.docstring.parsed:
        if isinstance(section, ds.DocstringSectionParameters):
            for param in section.value:
                descs[param.name] = param.description or ""
    return descs


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


def _convert_rst_text(text: str) -> str:
    """Apply all RST → Markdown transforms to a docstring text section."""
    # RST ``::`` code blocks → fenced code blocks (includes ``.. math::``)
    text = _RST_CODE_BLOCK_RE.sub(_replace_rst_code_block, text)

    # RST inline math ``:math:`…``` → ``$…$``
    text = re.sub(r":math:`([^`]+)`", r"$\1$", text)

    # Sphinx cross-reference roles → markdown code spans
    text = _convert_sphinx_roles(text)

    # RST admonition / version directives → Quarto callout blocks
    text = _convert_rst_directives(text)

    # RST simple tables → Markdown pipe tables
    text = _convert_rst_simple_tables(text)

    # RST grid tables → Markdown pipe tables
    text = _convert_rst_grid_tables(text)

    # RST citation markers ``.. [1] Text`` → numbered list
    text = _convert_rst_citations(text)

    return text


# RST citation converter ------------------------------------------------------

# Match lines/paragraphs containing ``.. [N]`` citation markers.
_RST_CITATION_RE = re.compile(
    r"^([ \t]*)\.\.\s+\[(\d+)\]\s+",
    re.MULTILINE,
)


def _convert_rst_citations(text: str) -> str:
    """Convert RST ``.. [N] body`` citation markers to a numbered markdown list.

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
    """Convert RST simple tables (``=====`` delimited) to Markdown pipe tables."""
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
    """Convert RST grid tables (``+---+`` delimited) to Markdown pipe tables."""
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


# ParamRow -------------------------------------------------------------------


@dataclass
class ParamRow:
    name: str | None
    description: str
    annotation: str | None = None
    default: str | None = None

    def to_definition_list(self):
        name = self.name
        anno = self.annotation
        desc = sanitize(self.description, allow_markdown=True)
        default = sanitize(str(self.default), escape_quotes=True)

        part_name = Span(Strong(name), Attr(classes=["parameter-name"])) if name is not None else ""
        part_anno = Span(anno, Attr(classes=["parameter-annotation"])) if anno is not None else ""

        if self.default is not None:
            part_default_sep = Span(" = ", Attr(classes=["parameter-default-sep"]))
            part_default = Span(default, Attr(classes=["parameter-default"]))
        else:
            part_default_sep = ""
            part_default = ""

        part_desc = desc if desc is not None else ""

        anno_sep = Span(":", Attr(classes=["parameter-annotation-sep"]))

        param = Code(
            str(Inlines([part_name, anno_sep, part_anno, part_default_sep, part_default]))
        ).html
        return (param, part_desc)

    def to_tuple(self, style: Literal["parameters", "attributes", "returns"]):
        name = self.name
        description = sanitize(self.description, allow_markdown=True)

        if style == "parameters":
            default = "_required_" if self.default is None else escape(self.default)
            return (name, self.annotation, description, default)
        elif style == "attributes":
            return (name, self.annotation, description)
        elif style == "returns":
            return (name, self.annotation, description)

        raise NotImplementedError(f"Unsupported table style: {style}")


# Renderer base ---------------------------------------------------------------


class Renderer:
    """Base renderer class."""

    style: str
    _registry: "dict[str, Renderer]" = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "style") and cls.style in cls._registry:
            raise KeyError(f"A renderer for style {cls.style} already exists")

        if hasattr(cls, "style"):
            cls._registry[cls.style] = cls

    @classmethod
    def from_config(cls, cfg: "dict | Renderer | str"):
        if isinstance(cfg, Renderer):
            return cfg
        elif isinstance(cfg, str):
            style, cfg = cfg, {}
        elif isinstance(cfg, dict):
            style = cfg["style"]
            cfg = {k: v for k, v in cfg.items() if k != "style"}
        else:
            raise TypeError(type(cfg))

        if style.endswith(".py"):
            import importlib
            import os
            import sys

            sys.path.append(os.getcwd())

            try:
                mod = importlib.import_module(style.rsplit(".", 1)[0])
                return mod.Renderer(**cfg)
            finally:
                sys.path.pop()

        subclass = cls._registry[style]
        return subclass(**cfg)

    def render(self, el):
        raise NotImplementedError(f"render method does not support type: {type(el)}")

    def _pages_written(self, builder):
        """Called after all the qmd pages have been rendered and written to disk."""
        ...


# MdRenderer ------------------------------------------------------------------


class MdRenderer(Renderer):
    """Render docstrings to markdown."""

    style = "markdown"

    def __init__(
        self,
        header_level: int = 1,
        show_signature: bool = True,
        show_signature_annotations: bool = False,
        display_name: str = "relative",
        hook_pre=None,
        render_interlinks=False,
        table_style="table",
    ):
        self.header_level = header_level
        self.show_signature = show_signature
        self.show_signature_annotations = show_signature_annotations
        self.display_name = display_name
        self.hook_pre = hook_pre
        self.render_interlinks = render_interlinks
        self.table_style = table_style

        self.crnt_header_level = self.header_level

    @contextmanager
    def _increment_header(self, n=1):
        self.crnt_header_level += n
        try:
            yield
        finally:
            self.crnt_header_level -= n

    def _fetch_object_dispname(self, el: "dc.Alias | dc.Object"):
        if self.display_name in {"name", "short"}:
            return el.name
        elif self.display_name == "relative":
            return ".".join(el.path.split(".")[1:])
        elif self.display_name == "full":
            return el.path
        elif self.display_name == "canonical":
            return el.canonical_path

        raise ValueError(f"Unsupported display_name: `{self.display_name}`")

    def _fetch_method_parameters(self, el: dc.Function):
        if (el.is_class or (el.parent and el.parent.is_class)) and len(el.parameters) > 0:
            if el.parameters[0].name in {"self", "cls"}:
                return dc.Parameters(*list(el.parameters)[1:])

        return el.parameters

    def _render_table(
        self,
        rows,
        headers,
        style: Literal["parameters", "attributes", "returns"],
    ):
        if self.table_style == "description-list":
            return str(DefinitionList([row.to_definition_list() for row in rows]))
        else:
            row_tuples = [row.to_tuple(style) for row in rows]
            return _simple_table(row_tuples, headers)

    # render_annotation -------------------------------------------------------

    def render_annotation(self, el) -> str:
        """Render a type annotation."""
        if el is None:
            return ""
        elif isinstance(el, str):
            return sanitize(el, escape_quotes=True)
        elif isinstance(el, expr.ExprName):
            if self.render_interlinks:
                return f"[{sanitize(el.name)}](`{el.canonical_path}`)"
            return sanitize(el.name)
        elif isinstance(el, expr.Expr):
            return "".join(self.render_annotation(x) for x in el)
        else:
            return sanitize(str(el), escape_quotes=True)

    # signature ---------------------------------------------------------------

    def signature(self, el) -> str:
        """Return a string representation of an object's signature."""
        if isinstance(el, layout.Doc):
            return self._signature_doc(el)
        elif isinstance(el, dc.Alias):
            return self._signature_alias(el)
        elif isinstance(el, (dc.Class, dc.Function)):
            return self._signature_func_or_class(el)
        elif isinstance(el, (dc.Module, dc.Attribute)):
            return self._signature_module_or_attr(el)
        else:
            raise NotImplementedError(f"signature not supported for: {type(el)}")

    def _signature_doc(self, el: layout.Doc) -> str:
        orig = self.display_name
        self.display_name = el.signature_name
        res = self.signature(el.obj)
        self.display_name = orig
        return res

    def _signature_alias(self, el: dc.Alias, source=None) -> str:
        return self._signature_func_or_class(el.final_target, el)

    def _signature_func_or_class(self, el, source=None) -> str:
        name = self._fetch_object_dispname(source or el)

        # For non-callable class types (Enum, TypedDict), emit just the name
        # without parentheses — they are not constructed by calling.
        if isinstance(el, dc.Class) and _is_non_callable_class(el):
            return f"```python\n{name}\n```"

        # Check for @overload variants (only on griffe Function objects)
        overloads = None
        if isinstance(el, dc.Function) and hasattr(el, "overloads"):
            try:
                ov_list = el.overloads
                if ov_list and isinstance(ov_list, list):
                    overloads = ov_list
            except Exception:
                pass

        if overloads:
            return self._render_overload_signatures(name, overloads)

        pars = self._render_parameters(el) if hasattr(el, "parameters") else []

        flat_sig = f"{name}({', '.join(pars)})"
        if len(flat_sig) > 80:
            indented = [" " * 4 + par + "," for par in pars]
            sig = "\n".join([f"{name}(", *indented, ")"])
        else:
            sig = flat_sig

        return f"```python\n{sig}\n```"

    def _render_overload_signatures(self, name: str, overloads: list) -> str:
        """Render multiple ``@overload`` signatures as a single code block."""
        sig_lines = []
        for ov in overloads:
            if not hasattr(ov, "parameters"):
                continue
            params = []
            for p in ov.parameters:
                ann = str(p.annotation) if p.annotation else ""
                default = str(p.default) if p.default else ""
                if ann and default:
                    params.append(f"{p.name}: {ann} = {default}")
                elif ann:
                    params.append(f"{p.name}: {ann}")
                elif default:
                    params.append(f"{p.name}={default}")
                else:
                    params.append(p.name)
            ret = str(ov.returns) if ov.returns else ""
            sig = f"{name}({', '.join(params)})"
            if ret:
                sig += f" -> {ret}"
            sig_lines.append(sig)

        if not sig_lines:
            return f"```python\n{name}()\n```"

        return "```python\n" + "\n".join(sig_lines) + "\n```"

    def _signature_module_or_attr(self, el, source=None) -> str:
        name = self._fetch_object_dispname(source or el)

        # For constants/attributes, include type annotation and value when
        # available so the QMD signature reads ``NAME: type = value`` instead
        # of the bare ``NAME`` that the renderer emits by default.
        parts = [name]
        try:
            if hasattr(el, "annotation") and el.annotation is not None:
                parts.append(f": {el.annotation}")
        except Exception:
            pass
        try:
            if hasattr(el, "value") and el.value is not None:
                val = str(el.value)
                if len(val) <= 200:
                    parts.append(f" = {val}")
        except Exception:
            pass

        sig = "".join(parts)
        return f"`{sig}`"

    # render_header -----------------------------------------------------------

    def render_header(self, el) -> str:
        """Render the header of a docstring, including any anchors."""
        if isinstance(el, layout.Doc):
            _str_dispname = _escape_dunders(el.name)
            _anchor_id = f"#{el.obj.path}"

            # Add () suffix for callable objects (functions, methods)
            _callable_kinds = {"function"}
            obj = el.obj
            _is_callable = isinstance(el, layout.DocFunction) or (
                hasattr(obj, "kind") and obj.kind.value in _callable_kinds
            )
            if _is_callable and not _str_dispname.endswith("()"):
                _str_dispname += "()"

            # Determine the object-type CSS class for type-badge styling
            _type_class = ""
            if hasattr(obj, "kind"):
                kind_val = obj.kind.value
                _type_class = f" .doc-type-{kind_val}"
                # Refine for special class subtypes
                if kind_val == "class" and hasattr(obj, "labels"):
                    labels = obj.labels
                    if "dataclass" in labels:
                        _type_class = " .doc-type-class"
                    elif "enum" in labels:
                        _type_class = " .doc-type-enum"

            _attr_block = f"{{ {_anchor_id}{_type_class} }}"
            return f"{'#' * self.crnt_header_level} {_str_dispname} {_attr_block}"
        elif isinstance(el, ds.DocstringSection):
            title = el.title or el.kind.value.title()
            anchor_part = _sanitize_title(title.lower())
            _classes = [".doc-section", f".doc-section-{anchor_part}"]
            _str_classes = " ".join(_classes)
            return f"{'#' * self.crnt_header_level} {title} {{{_str_classes}}}"
        else:
            raise NotImplementedError(f"render_header not supported for: {type(el)}")

    # render ------------------------------------------------------------------

    def render(self, el) -> "str | ParamRow | list":
        """Return a string representation of an object, or layout element.

        Dispatches based on the type of el.
        """
        # Simple types
        if isinstance(el, str):
            return el

        # Layout types (most specific first)
        if isinstance(el, layout.Interlaced):
            return self._render_interlaced(el)
        if isinstance(el, (layout.DocClass, layout.DocModule)):
            return self._render_doc_class_module(el)
        if isinstance(el, (layout.DocFunction, layout.DocAttribute)):
            return self._render_doc_func_attr(el)
        if isinstance(el, layout.Doc):
            raise NotImplementedError(f"Unsupported Doc type: {type(el)}")
        if isinstance(el, layout.Page):
            return self._render_page(el)
        if isinstance(el, layout.Section):
            return self._render_section(el)

        # AST patched types (must come before docstring section types)
        if isinstance(el, DocstringSectionWarnings):
            return _convert_rst_text(el.value)
        if isinstance(el, DocstringSectionSeeAlso):
            return convert_rst_link_to_md(el.value)
        if isinstance(el, DocstringSectionNotes):
            return _convert_rst_text(el.value)
        if isinstance(el, ExampleCode):
            return f"```python\n{el.value}\n```"
        if isinstance(el, ExampleText):
            return _fence_doctest_blocks(el.value)

        # Docstring section types
        if isinstance(el, ds.DocstringSectionText):
            return self._render_section_text(el)
        if isinstance(el, ds.DocstringSectionParameters):
            return self._render_section_parameters(el)
        if isinstance(el, ds.DocstringSectionAttributes):
            return self._render_section_attributes(el)
        if isinstance(el, ds.DocstringSectionAdmonition):
            return self._render_section_admonition(el)
        if isinstance(el, ds.DocstringSectionExamples):
            return self._render_section_examples(el)
        if isinstance(el, (ds.DocstringSectionReturns, ds.DocstringSectionRaises)):
            return self._render_section_returns_or_raises(el)

        # Docstring element types (return ParamRow)
        if isinstance(el, ds.DocstringParameter):
            return self._render_docstring_parameter(el)
        if isinstance(el, ds.DocstringReturn):
            return self._render_docstring_return(el)
        if isinstance(el, ds.DocstringRaise):
            return self._render_docstring_raise(el)
        if isinstance(el, ds.DocstringAttribute):
            return self._render_docstring_attribute(el)

        # Griffe types
        if isinstance(el, dc.Docstring):
            return self._render_docstring(el)
        if isinstance(el, dc.Parameters):
            return self._render_parameters(el)
        if isinstance(el, dc.Parameter):
            return self._render_parameter(el)
        if isinstance(el, (dc.Object, dc.Alias)):
            return self._render_object(el)

        # Unsupported types that should raise
        if isinstance(
            el,
            (
                ds.DocstringAdmonition,
                ds.DocstringDeprecated,
                ds.DocstringWarn,
                ds.DocstringYield,
                ds.DocstringReceive,
            ),
        ):
            raise NotImplementedError(f"{type(el)}")

        raise NotImplementedError(f"Unsupported type: {type(el)}")

    # --- Render implementations ---

    def _render_page(self, el: layout.Page) -> str:
        if el.summary:
            sum_ = el.summary
            header = [f"{'#' * self.crnt_header_level} {sum_.name}\n\n{sum_.desc}"]
        else:
            header = []

        result = map(self.render, el.contents)
        return "\n\n".join([*header, *result])

    def _render_section(self, el: layout.Section) -> str:
        section_top = f"{'#' * self.crnt_header_level} {el.title}\n\n{el.desc}"

        with self._increment_header():
            body = list(map(self.render, el.contents))

        return "\n\n".join([section_top, *body])

    def _render_interlaced(self, el: layout.Interlaced) -> str:
        for doc in el.contents:
            if not isinstance(doc, (layout.DocFunction, layout.DocAttribute)):
                raise NotImplementedError(
                    "Can only render Interlaced elements if all content elements"
                    " are function or attribute docs."
                    f" Found an element of type {type(doc)}, with name {doc.name}"
                )

        first_doc = el.contents[0]
        objs = [doc.obj for doc in el.contents]

        if first_doc.obj.docstring is None:
            raise ValueError("The first element of Interlaced must have a docstring.")

        str_title = self.render_header(first_doc)
        str_sig = "\n\n".join(map(self.signature, objs))
        str_body = []

        for section in qast.transform(first_doc.obj.docstring.parsed):
            title = section.title or section.kind.value
            body = self.render(section)

            if title != "text":
                header = f"{'#' * (self.crnt_header_level + 1)} {title.title()}"
                str_body.append("\n\n".join([header, body]))
            else:
                str_body.append(body)

        if self.show_signature:
            parts = [str_title, str_sig, *str_body]
        else:
            parts = [str_title, *str_body]

        return "\n\n".join(parts)

    def _render_doc_class_module(self, el) -> str:
        title = self.render_header(el)

        attr_docs = []
        meth_docs = []
        class_docs = []

        if el.members:
            sub_header = "#" * (self.crnt_header_level + 1)
            raw_attrs = [x for x in el.members if x.obj.is_attribute]
            raw_meths = [x for x in el.members if x.obj.is_function]
            raw_classes = [x for x in el.members if x.obj.is_class]

            header = "| Name | Description |\n| --- | --- |"

            # For dataclasses, augment the member-based attribute list with any
            # fields that griffe missed during static analysis.
            if (
                isinstance(el, layout.DocClass)
                and _is_griffe_dataclass(el.obj)
                and not _has_attr_section(el.obj.docstring)
            ):
                dc_field_names = _get_dataclass_field_names(el.obj)
                if dc_field_names is not None:
                    known_attr_names = {x.obj.name for x in raw_attrs}
                    missing = [n for n in dc_field_names if n not in known_attr_names]

                    if missing:
                        param_descs = _get_param_descriptions(el.obj)
                        # Build summary rows for fields griffe missed
                        extra_rows = []
                        for fname in missing:
                            desc = sanitize(param_descs.get(fname, ""), allow_markdown=True)
                            link = f"[{fname}](#{el.obj.path}.{fname})"
                            extra_rows.append(self._summary_row(link, desc))

                        # Render: existing attrs + extra rows
                        existing_rows = list(map(self.summarize, raw_attrs))
                        all_rows = existing_rows + extra_rows

                        # Reorder to match the dataclass field order
                        row_map: dict[str, str] = {}
                        for row in all_rows:
                            # extract name from "| [name](...) | desc |"
                            m = re.search(r"\[(\w+)\]", row)
                            if m:
                                row_map[m.group(1)] = row
                            else:
                                row_map[row] = row

                        ordered = [row_map[n] for n in dc_field_names if n in row_map]
                        # Add any rows we couldn't match to field order
                        ordered_names = set(dc_field_names)
                        for name, row in row_map.items():
                            if name not in ordered_names:
                                ordered.append(row)

                        _attrs_table = "\n".join(ordered)
                        attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                        attr_docs.append(attrs)
                    else:
                        # All fields present — render normally
                        _attrs_table = "\n".join(map(self.summarize, raw_attrs))
                        attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                        attr_docs.append(attrs)
                elif raw_attrs:
                    # Dynamic import failed — fall back to griffe's attributes
                    _attrs_table = "\n".join(map(self.summarize, raw_attrs))
                    attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                    attr_docs.append(attrs)
            elif raw_attrs and not _has_attr_section(el.obj.docstring):
                _attrs_table = "\n".join(map(self.summarize, raw_attrs))
                attrs = f"{sub_header} Attributes\n\n{header}\n{_attrs_table}"
                attr_docs.append(attrs)

            if raw_classes:
                _summary_table = "\n".join(map(self.summarize, raw_classes))
                section_name = "Classes"
                objs = f"{sub_header} {section_name}\n\n{header}\n{_summary_table}"
                class_docs.append(objs)

                n_incr = 1 if el.flat else 2
                with self._increment_header(n_incr):
                    rendered = [self.render(x) for x in raw_classes if isinstance(x, layout.Doc)]
                    if rendered:
                        # Solid separator after summary table
                        class_docs.append("---")
                        # Dotted separators between member docs
                        class_docs.append("\n\n---\n\n".join(rendered))

            if raw_meths:
                _summary_table = "\n".join(map(self.summarize, raw_meths))
                section_name = "Methods" if isinstance(el, layout.DocClass) else "Functions"
                objs = f"{sub_header} {section_name}\n\n{header}\n{_summary_table}"
                meth_docs.append(objs)

                n_incr = 1 if el.flat else 2
                with self._increment_header(n_incr):
                    rendered = [self.render(x) for x in raw_meths if isinstance(x, layout.Doc)]
                    if rendered:
                        # Solid separator after summary table
                        meth_docs.append("---")
                        # Dotted separators between member docs
                        meth_docs.append("\n\n---\n\n".join(rendered))

        str_sig = self.signature(el)
        sig_part = [str_sig] if self.show_signature else []

        with self._increment_header():
            body = self.render(el.obj)

        return "\n\n".join([title, *sig_part, body, *attr_docs, *class_docs, *meth_docs])

    def _render_doc_func_attr(self, el) -> str:
        title = self.render_header(el)

        str_sig = self.signature(el)
        sig_part = [str_sig] if self.show_signature else []

        with self._increment_header():
            body = self.render(el.obj)

        return "\n\n".join([title, *sig_part, body])

    def _render_object(self, el) -> str:
        if el.docstring is None:
            return ""
        else:
            return self._render_docstring(el.docstring)

    def _render_docstring(self, el: dc.Docstring) -> str:
        str_body = []
        patched_sections = qast.transform(el.parsed)

        for section in patched_sections:
            title = section.title or section.kind.value
            body: str = self.render(section)

            if title != "text":
                header = self.render_header(section)
                str_body.append("\n\n".join([header, body]))
            else:
                str_body.append(body)

        parts = [*str_body]
        return "\n\n".join(parts)

    def _render_parameters(self, el) -> list:
        """Render dc.Parameters to list of strings."""
        if isinstance(el, dc.Parameters):
            params = el
        elif hasattr(el, "parameters"):
            params = self._fetch_method_parameters(el)
        else:
            return []

        try:
            kw_only = [par.kind for par in params].index(dc.ParameterKind.keyword_only)
        except ValueError:
            kw_only = None

        try:
            pos_only = max(
                [ii for ii, p in enumerate(params) if p.kind == dc.ParameterKind.positional_only]
            )
        except ValueError:
            pos_only = None

        pars = [self._render_parameter(p) for p in params]

        if (
            kw_only is not None
            and kw_only > 0
            and params[kw_only - 1].kind != dc.ParameterKind.var_positional
        ):
            pars.insert(kw_only, "*")

        if pos_only is not None:
            pars.insert(pos_only + 1, "/")

        return pars

    def _render_parameter(self, el: dc.Parameter) -> str:
        splats = {dc.ParameterKind.var_keyword, dc.ParameterKind.var_positional}
        has_default = el.default and el.kind not in splats

        if el.kind == dc.ParameterKind.var_keyword:
            glob = "**"
        elif el.kind == dc.ParameterKind.var_positional:
            glob = "*"
        else:
            glob = ""

        annotation = el.annotation
        name = el.name

        if self.show_signature_annotations:
            if annotation and has_default:
                res = f"{glob}{name}: {annotation} = {el.default}"
            elif annotation:
                res = f"{glob}{name}: {annotation}"
            else:
                res = f"{glob}{name}"
        elif has_default:
            res = f"{glob}{name}={el.default}"
        else:
            res = f"{glob}{name}"

        return res

    def _render_section_text(self, el: ds.DocstringSectionText) -> str:
        new_el = qast.transform(el)
        if isinstance(new_el, ds.DocstringSectionText):
            text = _convert_rst_text(el.value)
            # Fence unfenced >>> doctest blocks as ```python
            text = _fence_doctest_blocks(text)
            # Bold section headers (e.g. **Examples**::) → proper headings
            text = _convert_bold_section_headers(text, self.crnt_header_level)
            # Sphinx-style :param: / :returns: / :raises: → sections with tables
            text = _convert_sphinx_fields(text, self.crnt_header_level)
            # Google-style Args: / Returns: / Raises: → sections with tables
            text = _convert_google_sections(text, self.crnt_header_level)
            return text
        return self.render(new_el)

    def _render_section_parameters(self, el: ds.DocstringSectionParameters) -> str:
        rows: list[ParamRow] = [self._render_docstring_parameter(p) for p in el.value]
        header = ["Name", "Type", "Description", "Default"]
        return self._render_table(rows, header, "parameters")

    def _render_docstring_parameter(self, el: ds.DocstringParameter) -> ParamRow:
        annotation = self.render_annotation(el.annotation)
        return ParamRow(el.name, el.description, annotation=annotation, default=el.default)

    def _render_section_attributes(self, el: ds.DocstringSectionAttributes) -> str:
        header = ["Name", "Type", "Description"]
        rows = [self._render_docstring_attribute(a) for a in el.value]
        return self._render_table(rows, header, "attributes")

    def _render_docstring_attribute(self, el: ds.DocstringAttribute) -> ParamRow:
        return ParamRow(
            el.name,
            el.description or "",
            annotation=self.render_annotation(el.annotation),
        )

    def _render_section_admonition(self, el: ds.DocstringSectionAdmonition) -> str:
        kind = el.title.lower()
        if kind in ["notes", "warnings"]:
            return el.value.description
        elif kind == "see also":
            return convert_rst_link_to_md(el.value.description)
        return el.value.description

    def _render_section_examples(self, el: ds.DocstringSectionExamples) -> str:
        data = map(qast.transform, el.value)
        return "\n\n".join(list(map(self.render, data)))

    def _render_section_returns_or_raises(self, el) -> str:
        rows = []
        for item in el.value:
            if isinstance(item, ds.DocstringRaise):
                rows.append(self._render_docstring_raise(item))
            else:
                rows.append(self._render_docstring_return(item))
        header = ["Name", "Type", "Description"]
        return self._render_table(rows, header, "returns")

    def _render_docstring_return(self, el: ds.DocstringReturn) -> ParamRow:
        return ParamRow(
            el.name,
            el.description,
            annotation=self.render_annotation(el.annotation),
        )

    def _render_docstring_raise(self, el: ds.DocstringRaise) -> ParamRow:
        return ParamRow(
            None,
            el.description,
            annotation=self.render_annotation(el.annotation),
        )

    # Summarize ===============================================================

    @staticmethod
    def _summary_row(link, description):
        return f"| {link} | {sanitize(description, allow_markdown=True)} |"

    def summarize(self, el, *args, **kwargs) -> str:
        """Produce a summary table."""
        if isinstance(el, layout.Layout):
            rendered_sections = list(map(self.summarize, el.sections))
            return "\n\n".join(rendered_sections)

        if isinstance(el, layout.Section):
            desc = f"\n\n{el.desc}" if el.desc is not None else ""
            if el.title is not None:
                header = f"## {el.title}{desc}"
            elif el.subtitle is not None:
                header = f"### {el.subtitle}{desc}"
            else:
                header = ""

            if el.contents:
                thead = "| | |\n| --- | --- |"

                rendered = []
                for child in el.contents:
                    rendered.append(self.summarize(child))

                str_func_table = "\n".join([thead, *rendered])
                return f"{header}\n\n{str_func_table}"

            return header

        if isinstance(el, layout.MemberPage):
            return self.summarize(el.contents[0], el.path, shorten=True)

        if isinstance(el, layout.Page):
            if el.summary is not None:
                return self._summary_row(f"[{el.summary.name}]({el.path}.qmd)", el.summary.desc)

            if len(el.contents) > 1 and not el.flatten:
                raise ValueError(
                    "Cannot summarize Page. Either set its `summary` attribute with name "
                    "and description details, or set `flatten` to True."
                )

            else:
                rows = [self.summarize(entry, el.path) for entry in el.contents]
                return "\n".join(rows)

        if isinstance(el, layout.Interlaced):
            rows = [self.summarize(doc, *args, **kwargs) for doc in el.contents]
            return "\n".join(rows)

        if isinstance(el, layout.Link):
            description = self.summarize(el.obj)
            return self._summary_row(f"[](`~{el.name}`)", description)

        if isinstance(el, layout.Doc):
            path = args[0] if args else kwargs.get("path", None)

            if path is None:
                link = f"[{el.name}](#{el.anchor})"
            else:
                link = f"[{el.name}]({path}.qmd#{el.anchor})"

            description = self.summarize(el.obj)
            return self._summary_row(link, description)

        if isinstance(el, (dc.Object, dc.Alias)):
            doc = el.docstring
            if doc is None:
                docstring_parts = []
            else:
                docstring_parts = doc.parsed

            if len(docstring_parts) and isinstance(docstring_parts[0], ds.DocstringSectionText):
                description = docstring_parts[0].value
                short = description.split("\n")[0]
                return short

            return ""

        raise NotImplementedError(f"Unsupported type: {type(el)}")
