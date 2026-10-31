"""
Code files included in pages as fenced code blocks

Authors include files with Quarto's `include` shortcode. An include of a code file, or one
that sets `lang` or `lines`, becomes a fenced code block before Quarto reads the page. Quarto
handles every other include itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._layout import Layout

__all__ = ["expand"]

# `{{{< include ... >}}}` is Quarto's escape for showing a shortcode literally
_INCLUDE = re.compile(r"(?<!\{)\{\{<\s*include\s+(.*?)\s*>\}\}(?!\})")
_KEYWORD = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

_CONTENT_SUFFIXES = {".qmd", ".md"}

_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".r": "r",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".rb": "ruby",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".xml": "xml",
    ".lua": "lua",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".jl": "julia",
    ".m": "matlab",
    ".pl": "perl",
    ".php": "php",
}


def expand(content: str, page_dir: Path, layout: Layout) -> str:
    """
    Replace the code-file includes in a page with fenced code blocks

    An include is expanded when it names a file other than `.qmd` or `.md`, or when it sets
    `lang` or `lines`. `lang="text"` overrides the language taken from the file's suffix.
    `lines="5-10"` selects a 1-based, inclusive range; `lines="5"` selects one line. The
    fence is longer than any run of backticks in the included text.

    Parameters
    ----------
    content
        The page source.
    page_dir
        The directory of the page's source file.
    layout
        The project layout. An include path is looked up relative to `page_dir`, then to the
        documentation source directory, then to the package root.

    Returns
    -------
    :
        The page with code includes replaced by fenced blocks. An include that cannot be
        read becomes an HTML comment that states the error.
    """

    def _replace(m: re.Match[str]) -> str:
        file_path_str, lang, lines_spec = _parse_args(m.group(1))

        if not file_path_str:
            return m.group(0)

        ext = Path(file_path_str).suffix.lower()
        is_content_file = ext in _CONTENT_SUFFIXES

        if is_content_file and not lang and not lines_spec:
            return m.group(0)

        resolved = _resolve(file_path_str, page_dir, layout)
        if resolved is None:
            return f"<!-- include error: file not found: {file_path_str} -->"

        try:
            file_content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return f"<!-- include error: {e} -->"

        if lines_spec:
            file_content = _select_lines(file_content, lines_spec)

        if not lang:
            lang = _LANGUAGES.get(resolved.suffix.lower(), "")

        longest_run = 0
        current_run = 0
        for ch in file_content:
            if ch == "`":
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        fence = "`" * max(3, longest_run + 1)
        return f"{fence}{lang}\n{file_content.rstrip()}\n{fence}"

    return _INCLUDE.sub(_replace, content)


def _parse_args(raw: str) -> tuple[str, str, str]:
    """
    Split the arguments of an `include` shortcode

    Parameters
    ----------
    raw
        The text between `include` and `>}}`.

    Returns
    -------
    :
        The file path without surrounding quotes, the `lang` value and the `lines` value.
        Missing arguments are returned as empty strings.
    """
    lang = ""
    lines = ""
    for kw_match in _KEYWORD.finditer(raw):
        key, value = kw_match.group(1), kw_match.group(2)
        if key == "lang":
            lang = value
        elif key == "lines":
            lines = value

    file_path = _KEYWORD.sub("", raw).strip()
    if file_path and file_path[0] in ('"', "'") and file_path[-1] == file_path[0]:
        file_path = file_path[1:-1]

    return file_path, lang, lines


def _resolve(file_path_str: str, page_dir: Path, layout: Layout) -> Path | None:
    """
    Find an included file

    Parameters
    ----------
    file_path_str
        The path the include names.
    page_dir
        The directory of the including page.
    layout
        The project layout, for the documentation source directory and the package root.

    Returns
    -------
    :
        The first existing file, looking in `page_dir`, the documentation source directory
        and the package root in that order, or `None` when the file is absent from all three.
    """
    candidates = [
        page_dir / file_path_str,
        layout.source_dir / file_path_str,
        layout.package_root / file_path_str,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def _select_lines(content: str, lines_spec: str) -> str:
    """
    Select a range of lines

    Parameters
    ----------
    content
        The included text.
    lines_spec
        `"start-end"`, 1-based and inclusive, or `"N"` for one line. The range is clipped to
        the lines that exist.

    Returns
    -------
    :
        The selected lines with their line endings.
    """
    all_lines = content.splitlines(keepends=True)

    if "-" in lines_spec:
        parts = lines_spec.split("-", 1)
        start = int(parts[0]) - 1
        end = int(parts[1])
    else:
        start = int(lines_spec) - 1
        end = start + 1

    start = max(0, start)
    end = min(len(all_lines), end)
    return "".join(all_lines[start:end])
