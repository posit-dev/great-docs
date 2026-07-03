"""
The API-reference files produced from a resolved content tree

The reference index, one page per documented object, the sidebar YAML, and
the typing pages — written to disk by `write_index`, `write_pages`,
`write_sidebar`, and `write_typing_information`.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yaml12 import format_yaml, parse_yaml, write_yaml

from .content import Page, Section

if TYPE_CHECKING:
    from .api_reference import APIReference

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def merge_frontmatter(content: str, extra: dict[str, Any]) -> str:
    """Merge `extra` keys into a content string's YAML frontmatter.

    If `content` already has a frontmatter block (``---`` header), the
    extra keys are inserted into that block. Otherwise a new block is
    prepended.

    Parameters
    ----------
    content :
        Full document text, optionally starting with a ``---`` frontmatter block.
    extra :
        YAML key-value pairs to add or overwrite in the frontmatter.
    """
    if content.startswith("---\n"):
        end = content.find("\n---", 4)
        if end == -1:
            raise ValueError("Frontmatter block opened with `---` is never closed")
        existing_yaml = content[4 : end + 1]  # noqa: E203
        rest = content[end + 4 :]  # after closing ---
        raw = parse_yaml(existing_yaml)
        existing: dict[str, Any] = cast("dict[str, Any]", raw) if isinstance(raw, dict) else {}
        existing.update(extra)
        new_yaml = format_yaml(existing)
        return f"---\n{new_yaml}\n---{rest}"
    else:
        new_yaml = format_yaml(extra)
        return f"---\n{new_yaml}\n---\n\n{content}"


# ---------------------------------------------------------------------------
# Sidebar helpers
# ---------------------------------------------------------------------------


def _insert_contents(
    x: dict[str, Any] | list[Any],
    contents: list[Any],
    sentinel: str = "{{ contents }}",
) -> bool:
    """Whether `contents` was spliced into `x` at the ``{{ contents }}`` sentinel.

    Recursively searches the structure for the sentinel string and replaces it
    with the items in `contents`. Returns `True` if the sentinel was found and
    replaced, `False` otherwise.

    Parameters
    ----------
    x :
        A nested dict/list structure (e.g. a parsed YAML sidebar config).
    contents :
        Items to splice in at the sentinel position.
    sentinel :
        The placeholder string to search for.
    """
    if isinstance(x, dict):
        for value in x.values():
            if isinstance(value, dict):
                if _insert_contents(cast("dict[str, Any]", value), contents):
                    return True
            elif isinstance(value, list):
                if _insert_contents(cast("list[Any]", value), contents):
                    return True
    else:
        for i, item in enumerate(x):
            if item == sentinel:
                x[i : i + 1] = contents  # noqa: E203
                return True
            elif isinstance(item, dict):
                if _insert_contents(cast("dict[str, Any]", item), contents):
                    return True
            elif isinstance(item, list):
                if _insert_contents(cast("list[Any]", item), contents):
                    return True
    return False


def _generate_sidebar(
    sections: list[Section],
    *,
    dir: str,
    out_page_suffix: str,
    sidebar: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generate the Quarto sidebar YAML structure for the given resolved sections.

    Produces a ``{"website": {"sidebar": [...]}}`` dict suitable for writing
    directly to a ``.yml`` file.

    Parameters
    ----------
    sections :
        Resolved sections to derive the sidebar structure from.
    dir :
        Output directory name (e.g. ``"reference"``).
    out_page_suffix :
        File suffix for rendered pages (e.g. ``".qmd"``).
    sidebar :
        Raw sidebar configuration from the settings (may include ``"file"``,
        ``"id"``, ``"contents"``, and other Quarto keys).
    """
    contents: list[Any] = [f"{dir}/index{out_page_suffix}"]
    in_subsection = False
    current_entry: dict[str, Any] = {}

    for section in sections:
        if section.title:
            if current_entry:
                contents.append(current_entry)

            in_subsection = False
            current_entry = {"section": section.title, "contents": []}
        elif section.subtitle:
            in_subsection = True

        links: list[str] = []
        for entry in section.contents:
            if isinstance(entry, Page):
                links.append(f"{dir}/{entry.path}{out_page_suffix}")

        if in_subsection:
            sub_entry: dict[str, Any] = {"section": section.subtitle, "contents": links}
            current_entry["contents"].append(sub_entry)
        else:
            current_entry["contents"].extend(links)

    if current_entry:
        contents.append(current_entry)

    if sidebar is None:
        sidebar_cfg: dict[str, Any] = {}
    else:
        sidebar_cfg = {k: v for k, v in sidebar.items() if k != "file"}

    if "id" not in sidebar_cfg:
        sidebar_cfg["id"] = dir

    if "contents" not in sidebar_cfg:
        sidebar_cfg["contents"] = contents
    else:
        existing_contents = sidebar_cfg["contents"]
        if not isinstance(existing_contents, list):
            raise TypeError("`sidebar.contents` must be a list")

        typed_contents = cast("list[Any]", existing_contents)
        if not _insert_contents(typed_contents, contents):
            typed_contents.extend(contents)

    entries: list[Any] = [sidebar_cfg, {"id": "dummy-sidebar"}]
    return {"website": {"sidebar": entries}}


# ---------------------------------------------------------------------------
# Public write functions
# ---------------------------------------------------------------------------


def write_index(
    api_ref: APIReference,
    sections: list[Section],
    *,
    dir: str,
    out_index: str,
    header_level: int,
) -> str:
    """Write the API index page, returning its path.

    Renders the reference summary page from `api_ref` plus its resolved
    `sections` and writes it to ``<dir>/<out_index>``.

    Parameters
    ----------
    api_ref :
        The API reference whose title, description, package, and options head
        the index page.
    sections :
        Resolved sections to render in the page body.
    dir :
        Output directory (created if absent).
    out_index :
        Filename for the index file (e.g. ``"index.qmd"``).
    header_level :
        Heading depth used for section titles in the rendered output.
    """
    from ._render.reference_page import RenderReferencePage

    _log.info("Summarizing docs for index page.")
    content = str(RenderReferencePage(api_ref, sections, header_level))
    _log.info(f"Writing index to directory: {dir}")

    p_index = Path(dir) / out_index
    p_index.parent.mkdir(exist_ok=True, parents=True)
    _ = p_index.write_text(content)

    return str(p_index)


def write_sidebar(
    api_ref: APIReference,
    sections: list[Section],
    *,
    dir: str,
    out_page_suffix: str,
) -> None:
    """Write the sidebar YAML file to the configured ``sidebar["file"]``.

    Generates a Quarto sidebar configuration from the resolved `sections` and
    writes it to the path in ``api_ref.settings.sidebar["file"]``.

    Parameters
    ----------
    api_ref :
        The API reference whose ``settings.sidebar`` supplies the output path
        and any Quarto sidebar overrides.
    sections :
        Resolved sections to derive the sidebar structure from.
    dir :
        Output directory name (e.g. ``"reference"``).
    out_page_suffix :
        File suffix for rendered pages (e.g. ``".qmd"``).
    """
    sidebar = api_ref.settings.sidebar
    assert sidebar is not None
    d_sidebar = _generate_sidebar(
        sections, dir=dir, out_page_suffix=out_page_suffix, sidebar=sidebar
    )
    write_yaml(d_sidebar, sidebar["file"])


def write_typing_information(
    typing_module_paths: list[str],
    api_ref: APIReference,
) -> None:
    """Write the API reference pages for protocols, type variables, and type aliases.

    One ``.qmd`` page per entry in `typing_module_paths`, written alongside
    the rest of the reference output and registered in the reference's inventory.

    Parameters
    ----------
    typing_module_paths :
        Fully-qualified module paths whose typing objects should be documented.
    api_ref :
        Active API reference; provides package name, output directory, and the
        items list that receives the generated inventory entries.
    """
    from .typing_information import TypeInformation

    for module_path in typing_module_paths:
        TypeInformation(module_path, api_ref).write()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def write_pages(
    pages: list[Page],
    *,
    dir: str,
    out_page_suffix: str,
    rewrite_all_pages: bool,
    header_level: int,
    filter: str,
) -> None:
    """Write API doc pages to `<dir>/<page.path><out_page_suffix>`

    Each page is Quarto Markdown whose frontmatter carries navigation and
    table-processing directives. A file whose content has not changed is
    left untouched (unless `rewrite_all_pages` is `True`).

    Parameters
    ----------
    pages :
        Resolved page nodes to render and write.
    dir :
        Output directory (created per-page if absent).
    out_page_suffix :
        File suffix appended to each page path (e.g. `".qmd"`).
    rewrite_all_pages :
        When `True`, overwrite every file regardless of whether content
        changed.
    header_level :
        Heading depth for the rendered page content.
    filter :
        Glob pattern; pages whose path does not match are neither rendered
        nor written. `"*"` writes all pages.
    """
    from ._render.api_page import RenderAPIPage

    for page in pages:
        if filter != "*" and not fnmatchcase(page.path, filter):
            _log.info(f"Skipping {page.path} (no filter match)")
            continue

        _log.info(f"Rendering {page.path}")
        rendered = str(RenderAPIPage(page, header_level))

        rendered = merge_frontmatter(
            rendered, {"page-navigation": False, "html-table-processing": "none"}
        )

        html_path = Path(dir) / (page.path + out_page_suffix)
        html_path.parent.mkdir(exist_ok=True, parents=True)

        if rewrite_all_pages or (not html_path.exists()) or (html_path.read_text() != rendered):
            _log.info(f"Writing: {page.path}")
            _ = html_path.write_text(rendered)
        else:
            _log.info("Skipping write (content unchanged)")
