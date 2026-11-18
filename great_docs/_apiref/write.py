"""
The API-reference files produced from a resolved content tree

Render the reference index, one page per documented object and the typing pages without
writing them, so a reference can fingerprint its extension's inputs before writing any
page. Write the sidebar YAML directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from yaml12 import format_yaml, write_yaml

from .._yaml import locate_front_matter
from .content import Page, Section

if TYPE_CHECKING:
    from ._customisation import Extension
    from .api_reference import APIReference

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedPage:
    """
    A rendered Quarto page and the path to write it to

    Rendering a page does not write it, so a reference can render every page, importing
    the helpers they need, before it computes one fingerprint of its inputs.
    """

    page_path: Path
    """The path to write to, relative to the working directory unless absolute"""
    content: str
    """The page's Quarto Markdown, without the input fingerprint"""

    def write(self, *, fingerprint: str | None = None, rewrite_unchanged: bool = True) -> None:
        """
        Write the page, appending the input fingerprint when one is given

        Parameters
        ----------
        fingerprint :
            The digest of the reference's extension inputs, appended as an HTML comment,
            or `None` to write the page alone. A reference computes it only after
            rendering every page, so it covers helpers imported during rendering.
        rewrite_unchanged :
            Whether to rewrite a file whose content already matches.
        """
        content = self.content
        if fingerprint is not None:
            content += f"\n\n<!-- great-docs-api-reference-inputs: {fingerprint} -->\n"
        self.page_path.parent.mkdir(exist_ok=True, parents=True)
        if (
            rewrite_unchanged
            or not self.page_path.exists()
            or self.page_path.read_text(encoding="utf-8") != content
        ):
            _ = self.page_path.write_text(content, encoding="utf-8")
        else:
            _log.info("Skipping write (content unchanged)")


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def merge_frontmatter(content: str, extra: dict[str, Any]) -> str:
    """
    Merge extra keys into a source's YAML front matter

    If `content` already has a frontmatter block (`---` header), the
    extra keys are inserted into that block. Otherwise a new block is
    prepended.

    Parameters
    ----------
    content :
        Full document text, optionally starting with a `---` frontmatter block.
    extra :
        YAML key-value pairs to add or overwrite in the frontmatter.

    Returns
    -------
    :
        The document with the merged front matter.

    Raises
    ------
    ValueError
        If `content` opens a front matter block that it never closes.
    """
    if content.startswith("---\n"):
        block = locate_front_matter(content)
        if block is None:
            raise ValueError("Frontmatter block opened with `---` is never closed")
        new_yaml = format_yaml({**block.mapping.data, **extra})
        return f"---\n{new_yaml}\n---\n{content[block.end :]}"
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
    """
    Insert contents at a sidebar sentinel and report whether it was found

    Recursively searches the structure for the sentinel string and replaces it
    with the items in `contents`, changing `x` in place.

    Parameters
    ----------
    x :
        A nested dict/list structure (e.g. a parsed YAML sidebar config).
    contents :
        Items to splice in at the sentinel position.
    sentinel :
        The placeholder string to search for.

    Returns
    -------
    :
        `True` if the sentinel was found and replaced, `False` otherwise.
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


def _page_sidebar_text(page: Page) -> str:
    """
    Choose a page's sidebar label: its summary name, its only object's name, or its filename

    Parameters
    ----------
    page
        The resolved page.

    Returns
    -------
    :
        The label, with `()` after the name of a page's only object when it is a function.
    """
    if page.summary is not None:
        return page.summary.name
    if len(page.contents) == 1:
        doc = page.contents[0]
        name = doc.name
        if doc.kind == "function":
            name += "()"
        return name
    return Path(page.path).name


def _generate_sidebar(
    sections: list[Section],
    *,
    dir: str,
    out_page_suffix: str,
    sidebar: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Generate the Quarto sidebar YAML structure for the given resolved sections

    Parameters
    ----------
    sections :
        Resolved sections to derive the sidebar structure from.
    dir :
        Output directory name (e.g. `"reference"`).
    out_page_suffix :
        File suffix for rendered pages (e.g. `".qmd"`).
    sidebar :
        Raw sidebar configuration from the settings (may include `"file"`,
        `"id"`, `"contents"`, and other Quarto keys).

    Returns
    -------
    :
        A `{"website": {"sidebar": [...]}}` dict suitable for writing directly to a
        `.yml` file.

    Raises
    ------
    TypeError
        If the configured `contents` is not a list.
    """
    contents: list[Any] = [f"{dir}/index{out_page_suffix}"]
    in_subsection = False
    current_entry: dict[str, Any] | None = None

    for section in sections:
        if section.title:
            if current_entry is not None:
                contents.append(current_entry)

            in_subsection = False
            current_entry = {"section": section.title, "contents": []}
        else:
            in_subsection = bool(section.subtitle)

        links: list[dict[str, str]] = []
        for entry in section.contents:
            if isinstance(entry, Page):
                links.append(
                    {
                        "text": _page_sidebar_text(entry),
                        "href": f"{dir}/{entry.path}{out_page_suffix}",
                    }
                )

        # A section that precedes any titled section attaches at the top level.
        dest: list[Any] = contents if current_entry is None else current_entry["contents"]
        if in_subsection:
            dest.append({"section": section.subtitle, "contents": links})
        else:
            dest.extend(links)

    if current_entry is not None:
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


def collect_index(
    api_ref: APIReference,
    sections: list[Section],
    *,
    dir: str,
    out_index: str,
    header_level: int,
) -> RenderedPage:
    """
    Render the API index page without writing it

    Render the reference summary from the resolved sections, for writing to
    `<dir>/<out_index>`.

    Parameters
    ----------
    api_ref :
        The API reference whose title, description, package, and options head
        the index page.
    sections :
        Resolved sections to render in the page body.
    dir :
        Output directory that the page's path starts with.
    out_index :
        Filename for the index file, such as `index.qmd`.
    header_level :
        Heading depth used for section titles in the rendered output.

    Returns
    -------
    :
        The rendered index and the path to write it to.
    """
    _log.info("Summarising docs for index page.")
    extension = api_ref.extension
    with extension.error_context("render", str(Path(dir) / out_index)):
        content = str(api_ref.renderers.make(api_ref, header_level, sections=sections))
    _log.info(f"Collected index for directory: {dir}")

    return RenderedPage(Path(dir) / out_index, content)


def write_sidebar(
    api_ref: APIReference,
    sections: list[Section],
    *,
    dir: str,
    out_page_suffix: str,
) -> None:
    """
    Write the sidebar YAML file to the configured `sidebar["file"]`

    Generates a Quarto sidebar configuration from the resolved `sections` and
    writes it to the path in `api_ref.settings.sidebar["file"]`.

    Parameters
    ----------
    api_ref :
        The API reference whose `settings.sidebar` supplies the output path
        and any Quarto sidebar overrides.
    sections :
        Resolved sections to derive the sidebar structure from.
    dir :
        Output directory name (e.g. `"reference"`).
    out_page_suffix :
        File suffix for rendered pages (e.g. `".qmd"`).
    """
    sidebar = api_ref.settings.sidebar
    assert sidebar is not None
    d_sidebar = _generate_sidebar(
        sections, dir=dir, out_page_suffix=out_page_suffix, sidebar=sidebar
    )
    write_yaml(d_sidebar, sidebar["file"])


def collect_typing_information(
    typing_module_paths: list[str], api_ref: APIReference
) -> list[RenderedPage]:
    """
    Render the typing pages without writing them, adding their objects to the inventory

    Rendering every page first lets the reference fingerprint helpers imported while
    rendering.

    Parameters
    ----------
    typing_module_paths :
        Import paths of modules, each documented on one page with the typing objects it
        defines.
    api_ref :
        The reference that loads, prepares and renders the objects. Objects that hooks
        do not exclude are added to its inventory.

    Returns
    -------
    :
        The rendered pages, in module order.
    """
    from .typing_information import TypeInformation

    return [TypeInformation(module_path, api_ref).collect() for module_path in typing_module_paths]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def collect_pages(
    pages: list[Page],
    extension: Extension,
    *,
    site_toc_depth: int,
) -> list[RenderedPage]:
    """
    Render API reference pages without writing them

    Each page's path is its path under the settings' `dir`, with their `out_page_suffix`
    appended. Each page is Quarto Markdown with navigation and table-processing
    directives in its front matter.

    Parameters
    ----------
    pages :
        Resolved page nodes to render.
    extension :
        The reference's extension, which supplies the settings, renderers and body
        callbacks, and names the page in a rendering failure. Object headings start at
        the settings' `header_level`.
    site_toc_depth :
        Merged site table-of-contents depth. A page overrides it only when
        member headings require a greater depth.

    Returns
    -------
    :
        The rendered pages, in the order given.
    """
    settings = extension.settings
    collected: list[RenderedPage] = []

    for page in pages:
        _log.info(f"Rendering {page.path}")
        page_path = str(Path(settings.dir) / (page.path + settings.out_page_suffix))
        with extension.error_context("render", page_path):
            rendered = str(
                extension.renderers.make(
                    page, settings.header_level, extension=extension, toc_depth=site_toc_depth
                )
            )

        rendered = merge_frontmatter(
            rendered, {"page-navigation": False, "html-table-processing": "none"}
        )

        collected.append(RenderedPage(Path(page_path), rendered))
    return collected
