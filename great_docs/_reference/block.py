"""
Build API reference configuration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._build import quarto

if TYPE_CHECKING:
    from ..config import Config
    from .discovery import Categories


def reference_yaml(categories: Categories) -> str:
    """
    Build the `reference:` YAML block from categorised exports

    Parameters
    ----------
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
        if has_prev_section:
            lines.append("")
        lines.append(f"  - title: {title}")
        lines.append(f"    desc: {desc}")
        lines.append("    contents:")
        for class_name in sorted(items):
            method_count = class_methods.get(class_name, 0)
            if method_count > 0:
                lines.append(f"      - {class_name}  # {method_count} method(s)")
            else:
                lines.append(f"      - {class_name}")
        has_prev_section = True

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


def configure(
    site_config: Config,
    quarto_config: dict[str, Any],
    importable_name: str,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Add the API reference settings to a Quarto mapping

    Parameters
    ----------
    site_config
        The project's configuration.
    quarto_config
        The Quarto configuration, updated in place.
    importable_name
        The name under which the documented package is imported.
    sections
        The API reference sections.

    Returns
    -------
    :
        The `api-reference` block added to the Quarto configuration.
    """
    ref_title = site_config.reference_title or "API Reference"
    ref_desc = site_config.reference_desc

    if not site_config.reference_title and site_config.lang != "en":
        from .._translations import translate

        ref_title = translate("api_reference", site_config.lang)

    api_ref_config: dict[str, Any] = {
        "package": importable_name,
        "dir": "reference",
        "title": ref_title,
    }
    if ref_desc:
        api_ref_config["desc"] = ref_desc
    if site_config.members_on_same_page is not None:
        api_ref_config["members_on_same_page"] = site_config.members_on_same_page
    api_ref_config["max_members_on_same_page"] = site_config.max_members_on_same_page

    dynamic = site_config.dynamic
    api_ref_config["dynamic"] = dynamic
    if not dynamic:
        print("Using static introspection mode (dynamic: false)")

    parser = site_config.parser
    if parser and parser != "numpy":
        api_ref_config["parser"] = parser
        print(f"Using '{parser}' docstring parser")
    else:
        api_ref_config["parser"] = "numpy"

    # Quarto 2 has no `syntax-definitions`, so it can't highlight `pythonsignature` blocks
    signature_style = "plain" if quarto.is_q2() else site_config.callable_signatures_style
    api_ref_config["callable_signatures"] = {
        "style": signature_style,
        "wrap": site_config.callable_signatures_wrap,
    }

    jupyter_kernel = site_config.jupyter
    if jupyter_kernel:
        quarto_config["jupyter"] = jupyter_kernel
        print(f"Using '{jupyter_kernel}' Jupyter kernel")

    api_ref_config["sections"] = sections
    print(f"Auto-generated {len(sections)} section(s) from package exports")

    quarto_config["api-reference"] = api_ref_config

    return api_ref_config
