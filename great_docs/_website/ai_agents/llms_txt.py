"""
The `llms.txt` and `llms-full.txt` files that describe the API reference to language models

`llms.txt` links to documented pages with semantic summaries and optional WebMCP
tools. `llms-full.txt` assembles prepared API text, command-line help and user
guide sources. Builds supply one prepared reference; standalone full exports
own their configuration, missing-entry policy and reference cleanup.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from ..._build.steps import USER_CODE_ERRORS
from ..._project.manifest import Manifest
from ..._yaml import locate_front_matter
from .webmcp_manifest import MANIFEST_FILE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from ..._apiref.api_reference import APIReference
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


def _describes_api(api_block: Mapping[str, Any] | None) -> TypeGuard[Mapping[str, Any]]:
    """
    Check whether standalone configuration names a package and contains sections

    This guard applies to authored configuration before a reference is prepared.
    Writers supplied with a prepared reference use its resolved documentation
    directly. Planning homepage links also requires the package to import.

    Parameters
    ----------
    api_block
        The API reference configuration, or `None` when the site has none.

    Returns
    -------
    :
        Whether the configuration names a `package` and has at least one section.
    """
    return api_block is not None and bool(api_block.get("package") and api_block.get("sections"))


def is_planned(api_block: Mapping[str, Any] | None) -> bool:
    """
    Check whether the homepage should link to `llms.txt` and `llms-full.txt`

    The homepage checks availability before either file exists or configured
    extension setup runs. Require a package that imports and at least one
    authored section. Writers with a supplied prepared reference do not repeat
    this import check.

    Parameters
    ----------
    api_block
        The API reference configuration, or `None` when the site has none.

    Returns
    -------
    :
        Whether the configuration supports linking to both files.
    """
    if not _describes_api(api_block):
        return False
    package_name = api_block["package"]
    try:
        _ = importlib.import_module(str(package_name).replace("-", "_"))
    except ImportError:
        return False
    return True


def write_index(
    layout: Layout,
    api_block: Mapping[str, Any] | None,
    metadata: Manifest,
    *,
    site_url: str | None,
    report: Callable[[str], None],
    webmcp_tools: Sequence[WebMCPTool] = (),
    webmcp_js_api: bool = False,
    reference: APIReference | None = None,
) -> Path | None:
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
    api_block
        The API reference configuration, or `None` when the site has none.
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
    reference
        The build's prepared reference, or `None` to retain standalone planned
        links and runtime summaries. A supplied reference shares exclusions,
        semantic summaries and authored destinations.

    Returns
    -------
    :
        The path written, or `None` without a supplied reference or usable
        authored API configuration.

    Raises
    ------
    ExtensionError
        If resolving a supplied reference fails in configured setup or semantic hooks.
    """
    from ..._apiref import APIReference, SpecObject
    from ..._apiref._export import summary
    from ..._apiref.content import Page

    if reference is None and not _describes_api(api_block):
        return None

    sections = (
        reference.resolved
        if reference is not None
        else APIReference({"api-reference": api_block}).sections
    )
    package_name = (
        reference.package
        if reference is not None
        else str(cast("Mapping[str, Any]", api_block)["package"])
    )
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

    lines = [f"# {package_name}", ""]
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
            if isinstance(entry, Page) and reference is not None:
                rows = (
                    [(entry.summary.name, entry.summary.desc)]
                    if entry.summary is not None
                    else [(doc.name, summary(doc.obj)) for doc in entry.contents]
                )
                page_path = f"{reference.settings.dir}/{entry.path}"
            elif isinstance(entry, SpecObject):
                rows = [(entry.name, docstring_summary(package_name, entry.name))]
                page_path = f"reference/{entry.page_path}"
            else:
                continue
            url = f"{site_url}{page_path}.html"
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
    Return the first docstring line of an object in a package's top-level namespace

    Importing the package runs its code. Import, syntax, attribute, runtime, OS and griffe
    errors produce an empty summary; other errors propagate.

    Parameters
    ----------
    package_name
        The name of the package; hyphens are read as underscores.
    item_name
        The name of the object in the package's top-level namespace.

    Returns
    -------
    :
        The first docstring line without trailing periods, or `""` when the object is missing
        or undocumented, or a handled error occurs.
    """
    try:
        module = importlib.import_module(package_name.replace("-", "_"))
        obj = getattr(module, item_name, None)
        if obj is None:
            return ""
        docstring = getattr(obj, "__doc__", None)
        if not docstring:
            return ""
        return docstring.strip().split("\n")[0].strip().rstrip(".")
    except USER_CODE_ERRORS:
        return ""


def write_full(
    layout: Layout,
    api_block: Mapping[str, Any] | None,
    *,
    cli: Mapping[str, Any] | None,
    user_guide: Mapping[str, Any] | None,
    report: Callable[[str], None],
    reference: APIReference | None = None,
) -> Path | None:
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
    api_block
        The API reference configuration, or `None` when the site has none.
    cli
        The package's Click interface, discovered for the CLI reference, or `None` to omit
        the command-line section.
    user_guide
        The discovered user guide pages, or `None` to omit the user guide section.
    report
        A callback that receives the line announcing the written file, or the reason the
        package could not be imported.
    reference
        The build's prepared reference, reused without repeating setup or early
        hooks. `None` owns a fresh operation from the selected layout and skips
        missing entries. Explicit API-block parser/dynamic settings override the
        selected configuration. Configured failures propagate in either mode.

    Returns
    -------
    :
        The path written, or `None` when the project has no usable API reference
        configuration and no supplied reference, or when a standalone package
        import raises `ImportError`.

    Raises
    ------
    ExtensionError
        If configured loading, setup or semantic hooks fail. A supplied reference
        retains its caller-owned lifetime; an owned standalone reference closes.
    """
    if reference is None and not _describes_api(api_block):
        return None

    package_name = (
        reference.package
        if reference is not None
        else str(cast("Mapping[str, Any]", api_block)["package"])
    )
    api_text = _full_api_text(layout, api_block, reference, report)
    if api_text is None:
        return None
    lines = [
        _SEPARATOR,
        f"This is the API documentation for the {package_name} library.",
        _SEPARATOR,
        "",
        api_text,
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


def _full_api_text(
    layout: Layout,
    api_block: Mapping[str, Any] | None,
    reference: APIReference | None,
    report: Callable[[str], None],
) -> str | None:
    """
    Export a supplied prepared reference or own a tolerant standalone operation

    Preserve the standalone import diagnostic and missing-entry tolerance. Read
    configured setup and semantic defaults from the selected layout's original
    configuration, then apply explicit API-block settings. Close the owned
    reference on success or failure. A supplied reference stays strict and
    retains its caller-owned lifetime.
    """
    from ..._apiref._export import reference_text, tolerant_sections
    from ..._apiref._extension_loading import _ExtensionSource
    from ..._apiref.api_reference import APIReference

    if reference is not None:
        return reference_text(reference)
    assert api_block is not None
    package_name = str(api_block["package"])
    import_name = package_name.replace("-", "_")
    try:
        _ = importlib.import_module(import_name)
    except ImportError as error:
        report(f"Could not import {package_name}: {error}")
        return None
    config = layout.load_config()
    block = {
        "dynamic": config.dynamic,
        "parser": config.parser or "numpy",
        **api_block,
        "package": import_name,
    }
    owned = APIReference(
        {"api-reference": block, "format": {"html": {"lang": config.lang}}},
        extension_source=_ExtensionSource.make(config, layout.source_dir),
        output_root=layout.build_dir,
    )
    try:
        return reference_text(owned, tolerant_sections(owned))
    finally:
        owned.close()


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
