from __future__ import annotations

import html
import re
from typing import Sequence


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
    Render rows as an HTML table.

    Styling is handled by the .gd-summary-table class in great-docs.scss,
    which overrides Bootstrap defaults for a cleaner appearance.

    Parameters
    ----------
    rows
        Sequence of (name, description) tuples. Name can contain markdown links.
    table_class
        CSS class to apply to the table for styling.

    Returns
    -------
    str
        HTML string with table markup.
    """
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

    # Assemble full HTML (no inline styles needed - SCSS handles styling)
    html_out = f"""<table class="{table_class}">
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

    return html_out
