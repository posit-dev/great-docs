from __future__ import annotations

import re
from pathlib import Path

# Matches the opening fence of an executable code block:
#   ```{python}  or  ```{python}   (with trailing whitespace)
_EXEC_FENCE_RE = re.compile(r"^```\{python\}\s*$")

# Matches the closing fence:
#   ```
_CLOSE_FENCE_RE = re.compile(r"^```\s*$")

# Matches a hash-pipe option line:
#   #| key: value
_HASHPIPE_RE = re.compile(r"^#\|\s*(\S+?):\s*(.*)$")

# The delimiter that separates display code from eval code:
_DELIMITER = "# ---"


def expand_mock_cells(text: str) -> str:
    """Rewrite `source-code: mock` cells in *text* into two-cell pairs.

    Parameters
    ----------
    text
        The full content of a `.qmd` file.

    Returns
    -------
    str
        The rewritten content. Unchanged if no mock cells are found.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for an opening executable fence
        if not _EXEC_FENCE_RE.match(line):
            out.append(line)
            i += 1
            continue

        # Collect the entire cell (fence-to-fence)
        cell_start = i
        i += 1
        cell_body: list[str] = []
        found_close = False
        while i < len(lines):
            if _CLOSE_FENCE_RE.match(lines[i]):
                found_close = True
                i += 1
                break
            cell_body.append(lines[i])
            i += 1

        if not found_close:
            # Malformed cell — emit as-is
            out.append(lines[cell_start])
            out.extend(cell_body)
            continue

        # Parse hash-pipe options from the top of the cell body
        options: dict[str, str] = {}
        option_lines: list[str] = []
        body_start = 0
        for j, bline in enumerate(cell_body):
            m = _HASHPIPE_RE.match(bline)
            if m:
                options[m.group(1)] = m.group(2).strip()
                option_lines.append(bline)
                body_start = j + 1
            else:
                break

        # Not a mock cell — emit unchanged
        if options.get("source-code") != "mock":
            out.append(lines[cell_start])
            out.extend(cell_body)
            out.append("```")
            continue

        # Split the remaining body at the delimiter
        raw_body = cell_body[body_start:]
        display_lines: list[str] = []
        eval_lines: list[str] = []
        found_delim = False
        for bline in raw_body:
            if not found_delim and bline.strip() == _DELIMITER:
                found_delim = True
                continue
            if found_delim:
                eval_lines.append(bline)
            else:
                display_lines.append(bline)

        # Collect options to forward (everything except source-code)
        # output-title and output-frame are forwarded to the eval cell only
        output_title = options.pop("output-title", None)
        output_frame = options.pop("output-frame", None)
        # Remove source-code from forwarded options
        options.pop("source-code", None)

        # Build forwarded option lines for both cells
        forwarded = []
        for key, val in options.items():
            forwarded.append(f"#| {key}: {val}")

        # --- Emit the display cell (eval: false) ---
        out.append("```{python}")
        out.append("#| eval: false")
        for fwd in forwarded:
            # Don't forward echo/output overrides to display cell
            if not fwd.startswith("#| echo:") and not fwd.startswith("#| output:"):
                out.append(fwd)
        out.extend(display_lines)
        out.append("```")

        # --- Emit the eval cell (echo: false) ---
        if found_delim and eval_lines:
            out.append("")
            out.append("```{python}")
            out.append("#| echo: false")
            if output_title:
                out.append(f"#| output-title: {output_title}")
            if output_frame:
                out.append(f"#| output-frame: {output_frame}")
            for fwd in forwarded:
                # Don't forward eval overrides to eval cell
                if not fwd.startswith("#| eval:"):
                    out.append(fwd)
            out.extend(eval_lines)
            out.append("```")
        elif not found_delim:
            # No delimiter found — the entire body is display-only (eval: false).
            # This is a valid use case (equivalent to just eval: false).
            pass

    return "\n".join(out)


def process_qmd_file(path: Path) -> bool:
    """Process a single `.qmd` file, rewriting mock cells in place.

    Parameters
    ----------
    path
        Path to the `.qmd` file.

    Returns
    -------
    bool
        `True` if the file was modified, `False` otherwise.
    """
    content = path.read_text(encoding="utf-8")
    if "#| source-code: mock" not in content:
        return False

    rewritten = expand_mock_cells(content)
    if rewritten == content:
        return False

    path.write_text(rewritten, encoding="utf-8")
    return True


def process_directory(directory: Path) -> list[str]:
    """Process all `.qmd` files under *directory*.

    Parameters
    ----------
    directory
        Root directory to scan recursively.

    Returns
    -------
    list[str]
        Relative paths of files that were modified.
    """
    modified: list[str] = []
    for qmd in sorted(directory.rglob("*.qmd")):
        if process_qmd_file(qmd):
            try:
                rel = str(qmd.relative_to(directory))
            except ValueError:
                rel = str(qmd)
            modified.append(rel)
    return modified
