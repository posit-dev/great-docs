from __future__ import annotations

import html
import re
import secrets
from typing import Sequence


def _generate_table_id() -> str:
    """Generate a unique 10-character alphanumeric ID for scoped CSS."""
    return secrets.token_hex(5)


def _md_link_to_html(text: str) -> str:
    """
    Convert markdown links to HTML anchor tags.

    Handles the pandoc-style link format: [content](url){.class1 .class2}
    """
    # Pattern: [content](url){.class1 .class2} or [content](url)
    pattern = r"\[([^\]]+)\]\(([^)]+)\)(?:\{([^}]+)\})?"

    def replace_link(match: re.Match) -> str:
        content = match.group(1)
        url = match.group(2)
        attr_str = match.group(3) or ""

        # Parse classes from attr string (e.g., ".doc-function .doc-label")
        classes = []
        for part in attr_str.split():
            if part.startswith("."):
                classes.append(part[1:])

        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        return f'<a href="{html.escape(url)}"{class_attr}>{content}</a>'

    return re.sub(pattern, replace_link, text)


def html_table(
    rows: Sequence[tuple[str, str | None]],
    *,
    table_class: str = "gd-summary-table",
) -> str:
    """
    Render rows as an HTML table with scoped CSS.

    Parameters
    ----------
    rows
        Sequence of (name, description) tuples. Name can contain markdown links.
    table_class
        CSS class to apply to the table for additional styling hooks.

    Returns
    -------
    str
        HTML string with scoped styles and table markup.
    """
    table_id = _generate_table_id()

    # Build scoped CSS
    css = f"""<style>
#{table_id} {{
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}}
#{table_id} thead {{
  display: none;
}}
#{table_id} td {{
  padding: 0.5em 0.75em;
  vertical-align: top;
  border-top: 1px solid var(--bs-border-color, #dee2e6);
}}
#{table_id} tr:first-child td {{
  border-top: none;
}}
#{table_id} td:first-child {{
  width: 40%;
  font-weight: 500;
}}
#{table_id} td:last-child {{
  color: var(--bs-secondary-color, #6c757d);
}}
</style>"""

    # Build table rows
    body_rows = []
    for name, desc in rows:
        # Convert markdown links to HTML
        name = _md_link_to_html(name)

        # Normalize description: join multi-line, strip excess whitespace
        if desc:
            desc = " ".join(line.strip() for line in desc.split("\n") if line.strip())
        else:
            desc = ""
        body_rows.append(f"  <tr>\n    <td>{name}</td>\n    <td>{desc}</td>\n  </tr>")

    table_body = "\n".join(body_rows)

    # Assemble full HTML
    html = f"""{css}
<table id="{table_id}" class="{table_class}">
<thead>
  <tr>
    <th>Name</th>
    <th>Description</th>
  </tr>
</thead>
<tbody>
{table_body}
</tbody>
</table>"""

    return html
