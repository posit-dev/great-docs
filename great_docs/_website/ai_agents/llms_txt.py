"""
The `llms.txt` and `llms-full.txt` files that describe the API reference to language models

`llms.txt` links to each reference page with the summary (the first paragraph) of each
object's prepared docstring and, when the site has WebMCP tools, lists them.
`llms-full.txt` contains the prepared API documentation, followed by command-line help
and the user guide. Both files come from the build's prepared reference. The homepage
decides from the configuration whether to link to them, before that reference exists.
"""

from __future__ import annotations

import importlib

import inspect
from typing import TYPE_CHECKING, Any

from ..._build.steps import USER_CODE_ERRORS
from ..._project.manifest import Manifest
from ..._yaml import locate_front_matter
from .webmcp_manifest import MANIFEST_FILE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from ..._apiref.api_reference import APIReference
    from ..._apiref.spec import ReferenceSpec
    from ..._project.layout import Layout
    from .webmcp_tools import WebMCPTool

__all__ = ["docstring_summary", "is_planned", "write_full", "write_index"]

_SEPARATOR = "-" * 70

# Inputs for the example call in the WebMCP section; the first listed tool is used.
_WEBMCP_EXAMPLES = (
    ("search_docs", '{ query: "install" }'),
    ("get_site_overview", "{}"),
    ("list_pages", "{}"),
    ("get_current_page", "{}"),
)


def is_planned(spec: ReferenceSpec | None) -> bool:
    """
    Check whether the homepage should link to `llms.txt` and `llms-full.txt`

    The homepage checks before either file exists and before the extension's `setup`
    runs. Both files require an importable package and at least one reference section.

    Parameters
    ----------
    spec
        The package and sections, or `None` when the site has no API reference.

    Returns
    -------
    :
        Whether the site can link to both files.
    """
    if spec is None or not spec.package or not spec.sections:
        return False
    try:
        _ = importlib.import_module(spec.package.replace("-", "_"))
    except ImportError:
        return False
    return True


def write_index(
    layout: Layout,
    reference: APIReference,
    metadata: Manifest,
    *,
    site_url: str | None,
    report: Callable[[str], None],
    webmcp_tools: Sequence[WebMCPTool] = (),
    webmcp_js_api: bool = False,
) -> Path:
    """
    Write `llms.txt` with a link and one-line summary for each API reference page

    The file follows the llms.txt format: the package name, its description, and a list of
    links grouped by reference section. Links are absolute when the project has a
    documentation URL or a site URL. A "WebMCP tools" section follows when the site
    registers tools, so that an agent reading the file learns what a browser agent on the
    site can call.

    Parameters
    ----------
    layout
        Project directories, including the build directory for `llms.txt`.
    reference
        The build's prepared reference. Its exclusions, prepared docstrings and page
        destinations apply.
    metadata
        The package metadata, including `description` and the `Documentation` entry of `urls`.
    site_url
        The configured address of the site, or `None`.
    report
        A callback that receives the line announcing the written file.
    webmcp_tools
        The WebMCP tools the site registers, in registration order, or none.
    webmcp_js_api
        Whether pages expose the tools to scripts through `window.greatDocs.tools`.

    Returns
    -------
    :
        The path written.

    Raises
    ------
    ExtensionError
        If the extension's `setup` or an object or docstring hook fails while the
        reference resolves.
    """
    from ..._apiref._export import summary
    from ..._apiref.content import Page

    sections = reference.resolved
    description = metadata.get("description", "")

    # The `Documentation` URL from `pyproject.toml` takes precedence over the site URL.
    urls = metadata.get("urls", {})
    site_url = urls.get("Documentation", "") or site_url or ""
    if site_url:
        # Drop an anchor such as `#readme`; links are appended to the base URL.
        if "#" in site_url:
            site_url = site_url.split("#")[0]
        if not site_url.endswith("/"):
            site_url += "/"

    lines = [f"# {reference.package}", ""]
    if description:
        lines += [f"> {description}", ""]
    lines += ["## Docs", "", "### API Reference", ""]

    for section in sections:
        section_title = section.title or section.subtitle or ""
        section_desc = section.desc or ""

        if len(sections) > 1 and section_title:
            lines.append(f"#### {section_title}")
            if section_desc:
                lines.append(f"> {section_desc}")
            lines.append("")

        for entry in section.contents:
            if not isinstance(entry, Page):
                continue
            rows = (
                [(entry.summary.name, entry.summary.desc)]
                if entry.summary is not None
                else [(doc.name, summary(doc.obj)) for doc in entry.contents]
            )
            url = f"{site_url}{reference.settings.dir}/{entry.path}.html"
            for item_name, item_desc in rows:
                if item_desc:
                    lines.append(f"- [{item_name}]({url}): {item_desc}")
                else:
                    lines.append(f"- [{item_name}]({url})")

        lines.append("")

    if webmcp_tools:
        lines += _webmcp_lines(webmcp_tools, site_url, js_api=webmcp_js_api)

    path = layout.build_dir / "llms.txt"
    _ = path.write_text("\n".join(lines), encoding="utf-8")
    report(f"Created {path}")
    return path


def _webmcp_lines(tools: Sequence[WebMCPTool], site_url: str, *, js_api: bool) -> list[str]:
    """
    Describe the site's WebMCP tools for `llms.txt`

    Parameters
    ----------
    tools
        The tools the site registers, in registration order.
    site_url
        The base of the site's links, ending in `/`, or `""` for relative links.
    js_api
        Whether to show how page scripts call the tools.

    Returns
    -------
    :
        The section's lines, ending with a blank line.
    """
    lines = [
        "## WebMCP tools",
        "",
        "An AI agent in a browser that supports WebMCP can call these tools on this site's "
        "pages. Results are JSON objects with absolute URLs.",
        "",
        f"- [WebMCP manifest]({site_url}{MANIFEST_FILE}): The site's sections, pages and API "
        "names, which the tools read",
        "",
    ]
    lines += [f"- `{tool.name}`: {tool.purpose}" for tool in tools]
    lines.append("")
    if js_api:
        names = {tool.name for tool in tools}
        call = next(
            (
                f'await window.greatDocs.tools.call("{name}", {example});'
                for name, example in _WEBMCP_EXAMPLES
                if name in names
            ),
            None,
        )
        lines += [
            "Scripts on the site's pages can call the same tools:",
            "",
            "```js",
            "window.greatDocs.tools.list();",
            *([call] if call else []),
            "```",
            "",
        ]
    return lines


def docstring_summary(package_name: str, item_name: str) -> str:
    """
    Return the docstring summary of an object in a package's top-level namespace

    The summary is the docstring's first paragraph, joined into one line. Importing the
    package runs its code. Import, syntax, attribute, runtime, OS and griffe errors produce
    an empty summary; other errors propagate.

    Parameters
    ----------
    package_name
        The name of the package; hyphens are read as underscores.
    item_name
        The name of the object in the package's top-level namespace.

    Returns
    -------
    :
        The summary without trailing periods, or `""` when the object is missing or
        undocumented, or a handled error occurs.
    """
    from ..._apiref._docstring_summary import summary_text

    try:
        module = importlib.import_module(package_name.replace("-", "_"))
        obj = getattr(module, item_name, None)
        if obj is None:
            return ""
        docstring = getattr(obj, "__doc__", None)
        if not docstring:
            return ""
        return summary_text(inspect.cleandoc(docstring)).rstrip(".")
    except USER_CODE_ERRORS:
        return ""


def write_full(
    layout: Layout,
    reference: APIReference,
    *,
    cli: Mapping[str, Any] | None,
    user_guide: Mapping[str, Any] | None,
    report: Callable[[str], None],
) -> Path:
    """
    Write `llms-full.txt` with API documentation, command-line help and user guide pages

    Group each documented object's prepared signatures and docstring sections by
    reference section, followed by help text for visible commands and then user guide
    pages. The export formats the prepared docstrings with the built-in renderers and
    keeps their markup as text.

    Parameters
    ----------
    layout
        Project directories, including the build directory for `llms-full.txt`.
    reference
        The build's prepared reference, reused without running `setup` or the object and
        docstring hooks again. The caller closes it.
    cli
        The package's Click interface, discovered for the CLI reference, or `None` to omit
        the command-line section.
    user_guide
        The discovered user guide pages, or `None` to omit the user guide section.
    report
        A callback that receives the line announcing the written file.

    Returns
    -------
    :
        The path written.

    Raises
    ------
    ExtensionError
        If the extension's `setup` or an object or docstring hook fails while the
        reference resolves.
    """
    from ..._apiref._export import reference_text

    lines = [
        _SEPARATOR,
        f"This is the API documentation for the {reference.package} library.",
        _SEPARATOR,
        "",
        reference_text(reference),
        "",
    ]

    cli_text = _cli_text(cli) if cli else ""
    if cli_text:
        lines += [
            "",
            _SEPARATOR,
            "This is the CLI documentation for the package.",
            _SEPARATOR,
            "",
            cli_text,
        ]

    user_guide_text = _user_guide_text(user_guide) if user_guide else ""
    if user_guide_text:
        lines += [
            "",
            _SEPARATOR,
            "This is the User Guide documentation for the package.",
            _SEPARATOR,
            "",
            user_guide_text,
        ]

    path = layout.build_dir / "llms-full.txt"
    _ = path.write_text("\n".join(lines), encoding="utf-8")
    report(f"Created {path}")
    return path


def _cli_text(cli: Mapping[str, Any]) -> str:
    """
    Format command-line help for the interface and its visible subcommands as Markdown

    Parameters
    ----------
    cli
        The discovered Click interface, with its `entry_point_name`, `help_text` and nested
        `commands`.

    Returns
    -------
    :
        A section for the interface and each visible subcommand, with help text in code
        blocks.
    """
    lines = [
        f"## CLI: {cli['entry_point_name']}",
        "",
        "```",
        cli.get("help_text", ""),
        "```",
        "",
    ]

    def add_subcommands(command: Mapping[str, Any]) -> None:
        """
        Append help sections for visible subcommands, including nested commands

        Parameters
        ----------
        command
            The discovered Click command and its nested `commands`.

        Returns
        -------
        :
            Nothing; sections are appended to the enclosing list of lines.
        """
        for sub in command.get("commands", []):
            if sub.get("hidden"):
                continue
            lines.extend(
                [
                    f"### {sub.get('full_path', sub.get('name', ''))}",
                    "",
                    "```",
                    sub.get("help_text", ""),
                    "```",
                    "",
                ]
            )
            if sub.get("commands"):
                add_subcommands(sub)

    add_subcommands(cli)
    return "\n".join(lines)


def _user_guide_text(user_guide: Mapping[str, Any]) -> str:
    """
    Join user guide page sources in reading order, omitting closed front matter

    Parameters
    ----------
    user_guide
        The discovered user guide, with `files` that each have a `path`, a `title` and an
        optional `section`.

    Returns
    -------
    :
        The combined page text, with a heading for each new section and a title heading for
        each page that does not start with a heading. Missing pages and pages that cannot
        be read or decoded are omitted. A page without a closed front matter block
        retains its full source.
    """
    lines: list[str] = []
    current_section = None

    for file_info in user_guide.get("files", []):
        file_path: Path | None = file_info.get("path")
        title = file_info.get("title", "")
        section = file_info.get("section")

        if not file_path or not file_path.exists():
            continue

        if section and section != current_section:
            lines.append(f"\n## {section}\n")
            current_section = section

        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        front_matter = locate_front_matter(content)
        if front_matter is not None:
            content = content[front_matter.end :].lstrip()
        if not content.strip().startswith("#"):
            lines.append(f"### {title}\n")
        lines += [content, ""]

    return "\n".join(lines)
