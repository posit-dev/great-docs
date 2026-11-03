"""
Build API reference configuration and navigation
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .._website import quarto_yml
from . import sections as reference_sections

if TYPE_CHECKING:
    from ..config import Config
    from .discovery import Categories


def reference_yaml(config: Config, categories: Categories) -> str:
    """
    Build the `reference:` YAML block from categorised exports

    Parameters
    ----------
    config
        The documentation configuration.
    categories
        The package's exports sorted into the groups of the API reference.

    Returns
    -------
    :
        A YAML block beginning with `reference:`; bare `reference:` when no
        category has items.
    """
    lines = ["reference:"]

    class_methods = categories.get("class_methods", {})
    class_method_names = categories.get("class_method_names", {})
    large_classes: list[str] = []
    has_prev_section = False

    _class_like_sections = [
        ("classes", "Classes", "Main classes provided by the package"),
        ("dataclasses", "Dataclasses", "Dataclass definitions"),
        ("abstract_classes", "Abstract Classes", "Abstract base classes"),
        ("protocols", "Protocols", "Protocol / structural-typing interfaces"),
    ]

    for cat_key, title, desc in _class_like_sections:
        items = categories.get(cat_key, [])
        if not items:
            continue
        if has_prev_section:  # pragma: no cover
            lines.append("")  # pragma: no cover
        lines.append(f"  - title: {title}")
        lines.append(f"    desc: {desc}")
        lines.append("    contents:")
        for class_name in sorted(items):
            method_count = class_methods.get(class_name, 0)
            if config.should_split_methods(method_count):
                lines.append(f"      - name: {class_name}")
                lines.append(f"        members: false  # {method_count} methods listed below")
                large_classes.append(class_name)
            elif method_count > 0:  # pragma: no cover
                lines.append(
                    f"      - {class_name}  # {method_count} method(s)"
                )  # pragma: no cover
            else:
                lines.append(f"      - {class_name}")
        has_prev_section = True

    for class_name in large_classes:
        method_names = class_method_names.get(class_name, [])
        if method_names:
            lines.append("")
            lines.append(f"  - title: {class_name} Methods")
            lines.append(f"    desc: Methods for the {class_name} class")
            lines.append("    contents:")
            for method_name in method_names:
                lines.append(f"      - {class_name}.{method_name}")

    _flat_sections = [
        ("enums", "Enumerations", "Enumeration types"),
        ("exceptions", "Exceptions", "Exception classes"),
        ("namedtuples", "Named Tuples", "Named tuple definitions"),
        ("typeddicts", "Typed Dicts", "TypedDict definitions"),
        ("functions", "Functions", "Utility functions"),
        ("async_functions", "Async Functions", "Asynchronous functions"),
        ("constants", "Constants", "Module-level constants and data"),
        ("type_aliases", "Type Aliases", "Type alias definitions"),
        ("other", "Other", "Additional exports"),
    ]

    for cat_key, title, desc in _flat_sections:
        items = categories.get(cat_key, [])
        if not items:
            continue
        if has_prev_section:
            lines.append("")
        lines.append(f"  - title: {title}")
        lines.append(f"    desc: {desc}")
        lines.append("    contents:")
        for name in sorted(items):
            lines.append(f"      - {name}")
        has_prev_section = True

    return "\n".join(lines)


def refresh(
    site_config: Config,
    build_dir: Path,
    create_sections: Callable[[str], list[dict[str, Any]] | None],
) -> None:
    """
    Refresh API sections and related settings in `_quarto.yml`

    Rediscover package exports. Preserve unrelated Quarto configuration and
    apply an explicit reference configuration if discovery yields no sections.
    """
    if not quarto_yml.path(build_dir).exists():
        print("Error: _quarto.yml not found. Run 'great-docs init' first.")
        return

    quarto_config = quarto_yml.read(build_dir)

    if "api-reference" not in quarto_config:
        print("Error: No API reference configuration found. Run 'great-docs init' first.")
        return

    package_name = quarto_config["api-reference"].get("package")
    if not package_name:
        print("Error: No package name in API reference config.")
        return

    print(f"Re-discovering exports for package: {package_name}")

    sections = create_sections(package_name)

    parser = site_config.parser
    if parser:
        quarto_config["api-reference"]["parser"] = parser

    dynamic = site_config.dynamic
    quarto_config["api-reference"]["dynamic"] = dynamic

    ref_title = site_config.reference_title
    if ref_title:
        quarto_config["api-reference"]["title"] = ref_title  # pragma: no cover
    ref_desc = site_config.reference_desc
    if ref_desc:
        quarto_config["api-reference"]["desc"] = ref_desc  # pragma: no cover
    elif "desc" in quarto_config["api-reference"]:
        del quarto_config["api-reference"]["desc"]  # pragma: no cover

    jupyter_kernel = site_config.jupyter
    if jupyter_kernel:
        quarto_config["jupyter"] = jupyter_kernel

    if sections:
        quarto_config["api-reference"]["sections"] = sections
        print(f"Updated API reference config with {len(sections)} section(s)")

        # The sidebar reads the saved sections from `_quarto.yml`.
        quarto_yml.write(build_dir, quarto_config, site_config)

        reference_sections.update_sidebar(site_config, build_dir)

        print(f"✅ Refreshed API reference configuration in {quarto_yml.path(build_dir)}")
    else:
        reference_config = site_config.reference
        if reference_config:
            print(
                "Auto-discovery failed, but applying explicit reference config from great-docs.yml"
            )
            user_sections = reference_sections.from_reference_config(reference_config)
            if user_sections:
                quarto_config["api-reference"]["sections"] = user_sections
                quarto_yml.write(build_dir, quarto_config, site_config)
                reference_sections.update_sidebar(site_config, build_dir)
                print(f"✅ Applied {len(user_sections)} section(s) from great-docs.yml")
            else:
                print(
                    "Warning: reference config in great-docs.yml produced no sections"
                )  # pragma: no cover
        else:
            print(
                "Warning: Could not discover package exports. Config unchanged."
            )  # pragma: no cover
            print(  # pragma: no cover
                "Tip: Add a 'reference' section to great-docs.yml to manually specify your API structure."
            )


def configure(
    site_config: Config,
    quarto_config: dict[str, Any],
    importable_name: str,
    sections: list[dict[str, Any]],
) -> None:
    """
    Add reference settings and navigation to a Quarto mapping
    """
    # The index title names the API; the navbar label covers API, CLI and MCP references.
    ref_title = site_config.reference_title or "API Reference"
    nav_title = site_config.reference_title or "Reference"
    ref_desc = site_config.reference_desc

    if not site_config.reference_title and site_config.lang != "en":
        from .._translations import get_translation  # pragma: no cover

        ref_title = get_translation("api_reference", site_config.lang)  # pragma: no cover
        nav_title = get_translation("reference", site_config.lang)  # pragma: no cover

    api_ref_config: dict[str, Any] = {
        "package": importable_name,
        "dir": "reference",
        "title": ref_title,
    }
    if ref_desc:
        api_ref_config["desc"] = ref_desc  # pragma: no cover

    dynamic = site_config.dynamic
    api_ref_config["dynamic"] = dynamic
    if not dynamic:
        print("Using static introspection mode (dynamic: false)")  # pragma: no cover

    parser = site_config.parser
    if parser and parser != "numpy":
        api_ref_config["parser"] = parser  # pragma: no cover
        print(f"Using '{parser}' docstring parser")  # pragma: no cover
    else:
        api_ref_config["parser"] = "numpy"

    api_ref_config["callable_signatures"] = {
        "style": site_config.callable_signatures_style,
        "wrap": site_config.callable_signatures_wrap,
    }

    jupyter_kernel = site_config.jupyter
    if jupyter_kernel:
        quarto_config["jupyter"] = jupyter_kernel
        print(f"Using '{jupyter_kernel}' Jupyter kernel")

    api_ref_config["sections"] = sections
    print(f"Auto-generated {len(sections)} section(s) from package exports")

    quarto_config["api-reference"] = api_ref_config

    if "website" in quarto_config and "navbar" in quarto_config["website"]:
        navbar = quarto_config["website"]["navbar"]
        left = navbar.get("left", [])
        has_ref = any(
            isinstance(item, dict)
            and cast("dict[str, Any]", item).get("href") == "reference/index.qmd"
            for item in left
        )
        if not has_ref:
            left.append({"text": nav_title, "href": "reference/index.qmd"})
            navbar["left"] = left

    if "website" in quarto_config and "sidebar" in quarto_config["website"]:
        sidebars = quarto_config["website"]["sidebar"]
        has_ref_sidebar = any(
            isinstance(s, dict) and cast("dict[str, Any]", s).get("id") == "reference"
            for s in sidebars
        )
        if not has_ref_sidebar:
            sidebars.append({"id": "reference", "contents": "reference/"})
