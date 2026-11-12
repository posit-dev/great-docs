"""
The `llms.txt` and `llms-full.txt` files that describe the API reference to language models

`llms.txt` links to each documented object with a one-line summary and, when the site has
WebMCP tools, lists them. `llms-full.txt` contains each object's signature and docstring,
followed by command-line help and the user guide.
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from ..._build.steps import USER_CODE_ERRORS
from ..._project.manifest import Manifest
from ..._yaml import locate_front_matter
from .webmcp_manifest import MANIFEST_FILE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path
    from types import ModuleType

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
    Check whether the API reference names a package and contains sections

    Both writers and the availability check use this test, so a page advertises the files
    only when the build can write them. The availability check also requires the package
    to import.

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
    Check whether the build will write `llms.txt` and `llms-full.txt`

    The homepage checks availability before either file exists. Both files require an API
    reference configuration with an importable `package` and at least one section.

    Parameters
    ----------
    api_block
        The API reference configuration, or `None` when the site has none.

    Returns
    -------
    :
        Whether the build should write both files.
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

    Returns
    -------
    :
        The path written, or `None` when the project has no usable API reference
        configuration.
    """
    from ..._apiref import APIReference, SpecObject

    if not _describes_api(api_block):
        return None

    sections = api_block["sections"]
    package_name = api_block["package"]
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

    for section in APIReference({"api-reference": api_block}).sections:
        section_title = section.title or section.subtitle or ""
        section_desc = section.desc or ""

        if len(sections) > 1 and section_title:
            lines.append(f"#### {section_title}")
            if section_desc:
                lines.append(f"> {section_desc}")
            lines.append("")

        for entry in section.contents:
            if not isinstance(entry, SpecObject):
                continue
            item_name = entry.name
            item_desc = docstring_summary(package_name, item_name)
            url = f"{site_url}reference/{entry.page_path}.html"
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
) -> Path | None:
    """
    Write `llms-full.txt` with API documentation, command-line help and user guide pages

    The file groups each documented object's signature and docstring by reference section,
    followed by help text for visible commands and then user guide pages.

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

    Returns
    -------
    :
        The path written, or `None` when the project has no usable API reference
        configuration or importing the package raises `ImportError`.
    """
    if not _describes_api(api_block):
        return None

    sections = api_block["sections"]
    package_name = api_block["package"]

    try:
        module = importlib.import_module(package_name.replace("-", "_"))
    except ImportError as e:
        report(f"Could not import {package_name}: {e}")
        return None

    lines = [
        _SEPARATOR,
        f"This is the API documentation for the {package_name} library.",
        _SEPARATOR,
        "",
    ]

    for section in sections:
        section_title = section.get("title") or section.get("subtitle") or ""
        section_desc = section.get("desc", "")
        if section_title:
            lines.append(f"\n## {section_title}\n")
            if section_desc:
                lines.append(f"{section_desc}\n")
            lines.append("")

        for item in section.get("contents", []):
            if isinstance(item, str):
                item_name = item
            elif isinstance(item, dict):
                entry = cast("dict[str, Any]", item)
                item_name = entry.get("name", str(entry))
            else:
                continue
            api_text = _api_details(module, item_name, parser=str(api_block.get("parser", "numpy")))
            if api_text:
                lines += [api_text, ""]

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


def _api_details(module: ModuleType, item_name: str, *, parser: str = "numpy") -> str:
    """
    Return the signature and docstring of an object in a module

    Looking up the object can run the package's code. Import, syntax, attribute, runtime,
    OS and griffe errors produce an empty result; other errors propagate unless handled
    while reading the signature.

    Parameters
    ----------
    module
        The imported package.
    item_name
        The object's name in the module, dotted for a nested attribute such as
        `Class.method`.
    parser
        The docstring style used when exclusions require structured parameter filtering.

    Returns
    -------
    :
        The signature followed by a blank line and the dedented docstring, if present. The
        name alone replaces a signature that raises `ValueError` or `TypeError`.
        Objects with parameter exclusions use the rendered reference documentation. The result
        is `""` if the object is missing or a handled package error occurs.
    """
    try:
        obj: Any = module
        for part in item_name.split("."):
            obj = getattr(obj, part)

        docstrings = [getattr(obj, "__doc__", None) or ""]
        if inspect.isclass(obj):
            docstrings += [
                getattr(getattr(obj, name, None), "__doc__", None) or ""
                for name in ("__init__", "__new__")
            ]
        if any("%nodoc_param" in text for text in docstrings):
            from ..._apiref import APIReference
            from ..._apiref._parameter_docs import CallableDocumentation
            from ..._apiref._render import get_render_type
            from ..._apiref.content import Page

            reference = APIReference(
                {
                    "package": module.__name__,
                    "parser": parser,
                    "dynamic": True,
                    "sections": [{"contents": [item_name]}],
                }
            )
            docs = [
                doc
                for section in reference.resolved
                for page in section.contents
                if isinstance(page, Page)
                for doc in page.contents
            ]
            if any(CallableDocumentation.make(doc.obj).excluded_names for doc in docs):
                return "\n\n".join(
                    str(get_render_type(doc)(doc, settings=reference.settings)) for doc in docs
                )

        obj_name = getattr(obj, "__name__", item_name)
        try:
            sig_str = f"{obj_name}{inspect.signature(obj)}"
        except (ValueError, TypeError):
            # Some objects, including some built-ins, have no inspectable signature.
            sig_str = obj_name

        doc = getattr(obj, "__doc__", None) or ""
        if doc:
            doc = inspect.cleandoc(doc)
        return f"{sig_str}\n\n{doc}" if doc else sig_str
    except USER_CODE_ERRORS:
        return ""


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
