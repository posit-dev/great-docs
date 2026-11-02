"""
The `llms.txt` and `llms-full.txt` files that describe the API reference to language models

`llms.txt` links to each documented object with a one-line summary. `llms-full.txt` contains
each object's signature and docstring, followed by command-line help and the user guide.
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING, Any, cast

from ..._build.steps import USER_CODE_ERRORS
from .. import quarto_yml

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path
    from types import ModuleType

__all__ = ["docstring_summary", "is_planned", "write_full", "write_index"]

_SEPARATOR = "-" * 70


def _api_reference_config(build_dir: Path) -> dict[str, Any] | None:
    """
    Read the Quarto configuration used to generate both files

    The writers and the availability check share this guard, so a page never advertises a
    file the build does not write, and no file is written without being advertised.

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        The parsed `_quarto.yml`, with an `api-reference` block that names a `package` and
        has at least one section, or `None` when the project has no such configuration.
    """
    if not quarto_yml.path(build_dir).exists():
        return None
    try:
        # Parsing can succeed even when the YAML root is not a mapping.
        parsed = cast("object", quarto_yml.read(build_dir))
    except (OSError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    config = cast("dict[str, Any]", parsed)
    api_ref_config = config.get("api-reference")
    if not isinstance(api_ref_config, dict):
        return None
    api_ref_config = cast("dict[str, Any]", api_ref_config)
    if not api_ref_config.get("package") or not api_ref_config.get("sections"):
        return None
    return config


def is_planned(build_dir: Path) -> bool:
    """
    Check whether the build will write `llms.txt` and `llms-full.txt`

    The homepage checks availability before either file exists. Both files require an
    `api-reference` block in `_quarto.yml` with an importable `package` and at least one
    section.

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        Whether the build should write both files.
    """
    config = _api_reference_config(build_dir)
    if config is None:
        return False
    package_name = config["api-reference"]["package"]
    try:
        _ = importlib.import_module(str(package_name).replace("-", "_"))
    except ImportError:
        return False
    return True


def write_index(
    build_dir: Path,
    metadata: Mapping[str, Any],
    *,
    report: Callable[[str], None],
) -> Path | None:
    """
    Write `llms.txt` with a link and one-line summary for each API reference page

    The file follows the llms.txt format: the package name, its description, and a list of
    links grouped by reference section. Links are absolute when the project has a
    documentation URL or a `site-url`.

    Parameters
    ----------
    build_dir
        The Quarto project directory where the file will be written.
    metadata
        The package metadata, including `description` and the `Documentation` entry of `urls`.
    report
        A callback that receives the line announcing the written file.

    Returns
    -------
    :
        The path written, or `None` when the project has no usable API reference
        configuration.
    """
    from ..._apiref import APIReference, SpecObject

    config = _api_reference_config(build_dir)
    if config is None:
        return None

    api_ref_config = config["api-reference"]
    sections = api_ref_config["sections"]
    package_name = api_ref_config["package"]
    description = metadata.get("description", "")

    # The `Documentation` URL from `pyproject.toml` takes precedence over Quarto
    # `site-url`.
    urls = metadata.get("urls", {})
    site_url = urls.get("Documentation", "") or config.get("website", {}).get("site-url", "")
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

    for section in APIReference(config).sections:
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

    path = build_dir / "llms.txt"
    _ = path.write_text("\n".join(lines), encoding="utf-8")
    report(f"Created {path}")
    return path


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
    build_dir: Path,
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
    build_dir
        The Quarto project directory where the file will be written.
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
    config = _api_reference_config(build_dir)
    if config is None:
        return None

    api_ref_config = config["api-reference"]
    sections = api_ref_config["sections"]
    package_name = api_ref_config["package"]

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
            api_text = _api_details(module, item_name)
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

    path = build_dir / "llms-full.txt"
    _ = path.write_text("\n".join(lines), encoding="utf-8")
    report(f"Created {path}")
    return path


def _api_details(module: ModuleType, item_name: str) -> str:
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

    Returns
    -------
    :
        The signature followed by a blank line and the dedented docstring, if present. The
        name alone replaces a signature that raises `ValueError` or `TypeError`. The result
        is `""` if the object is missing or a handled package error occurs.
    """
    try:
        obj: Any = module
        for part in item_name.split("."):
            obj = getattr(obj, part)

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
    Join user guide page sources in reading order, omitting their front matter

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
        be read or decoded are omitted.
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

        content = _strip_front_matter(content)
        if not content.strip().startswith("#"):
            lines.append(f"### {title}\n")
        lines += [content, ""]

    return "\n".join(lines)


def _strip_front_matter(content: str) -> str:
    """
    Remove a page's leading YAML front matter

    Parameters
    ----------
    content
        The page source.

    Returns
    -------
    :
        The text after the second `---`, with leading whitespace removed. The source is
        returned unchanged if it does not start with `---` or contains no second `---`.
    """
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return content
