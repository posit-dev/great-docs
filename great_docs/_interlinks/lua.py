"""
Write the lookup table as a Lua chunk
"""

from __future__ import annotations

from pathlib import Path

from .._sphinx_inventory import ROLE_SYNONYMS
from .index import Index


def _quote_lua(value: str) -> str:
    """Quote a string for a Lua source chunk"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_index(index: Index, path: Path) -> None:
    """
    Write the index as a Lua chunk the filter loads

    A chunk is written rather than JSON because Quarto runs one pandoc process
    per file and each one loads the index; Lua reads its own syntax faster than
    it decodes JSON. A compiled index left over from an earlier build is
    removed, since it would otherwise be loaded in preference to this one.

    Parameters
    ----------
    index :
        The index to write.
    path :
        Where to write it.
    """
    lines = [
        "return {",
        f"  add_function_parentheses = {str(index.add_function_parentheses).lower()},",
        "  role_synonyms = {",
    ]
    for abbrev in sorted(ROLE_SYNONYMS):
        lines.append(f"    [{_quote_lua(abbrev)}] = {_quote_lua(ROLE_SYNONYMS[abbrev])},")
    lines.append("  },")
    lines.append("  prefixes = {")
    for alias in sorted(index.prefixes):
        roots = ", ".join(_quote_lua(r) for r in index.prefixes[alias])
        lines.append(f"    [{_quote_lua(alias)}] = {{{roots}}},")
    lines.append("  },")
    lines.append("  names = {")

    for name in sorted(index.names):
        parts = []
        for e in index.names[name]:
            fields = [
                f"uri = {_quote_lua(e.uri)}",
                f"domain = {_quote_lua(e.domain)}",
                f"role = {_quote_lua(e.role)}",
            ]
            if e.source:
                fields.append(f"source = {_quote_lua(e.source)}")
            if e.is_local:
                fields.append('["local"] = true')
            parts.append("{" + ", ".join(fields) + "}")
        lines.append(f"    [{_quote_lua(name)}] = {{{', '.join(parts)}}},")

    lines.append("  },")
    lines.append("}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # A compiled index the filter wrote for an earlier build would be loaded in
    # preference to this one.
    path.with_suffix(".luac").unlink(missing_ok=True)
