"""
Build API reference section descriptions
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from .._contribution import Sidebar

if TYPE_CHECKING:
    from ..config import Config
    from .discovery import Categories


def from_reference_config(reference_config: Sequence[object] | None) -> list[dict[str, Any]] | None:
    """
    Build API sections from explicit configuration without checking exports

    Use these sections when export discovery fails. Preserve configured names
    even when they cannot be found in the package.

    Parameters
    ----------
    reference_config
        The reference configuration from `great-docs.yml`.

    Returns
    -------
    :
        Sections for configured entries, or `None` when none are usable.
    """
    if not reference_config:
        return None

    sections: list[dict[str, Any]] = []

    for section_config in reference_config:
        if not isinstance(section_config, dict):
            continue
        section_config = cast("dict[str, Any]", section_config)
        title = section_config.get("title")
        subtitle = section_config.get("subtitle")
        desc = section_config.get("desc", "")
        contents_config = section_config.get("contents", [])

        if not contents_config:
            continue

        section_contents: list[Any] = []

        for item in contents_config:
            if isinstance(item, str):
                section_contents.append(item)
            elif isinstance(item, dict):
                item = cast("dict[str, Any]", item)
                name = item.get("name", "")
                if not name:
                    continue

                members = item.get("members", True)
                include_inherited = item.get("include_inherited", None)

                if members is False:
                    section_contents.append({"name": name, "members": []})
                elif isinstance(members, list):
                    entry: dict[str, Any] = {"name": name, "members": members}
                    if include_inherited is not None:
                        entry["include_inherited"] = include_inherited
                    section_contents.append(entry)
                else:
                    if include_inherited is not None:
                        section_contents.append(
                            {"name": name, "include_inherited": include_inherited}
                        )
                    else:
                        section_contents.append(name)

        if section_contents:
            sections.append(
                {
                    **(
                        {"subtitle": subtitle}
                        if subtitle is not None
                        else {"title": title or "Untitled"}
                    ),
                    "desc": desc,
                    "contents": section_contents,
                }
            )

    return sections if sections else None


def from_categories(config: Config, categories: Categories) -> list[dict[str, Any]] | None:
    """
    Build sections from discovered export categories
    """
    sections: list[dict[str, Any]] = []

    from .._translations import get_translation

    lang = config.lang

    def _t(key: str, fallback: str) -> str:
        return get_translation(key, lang) if lang != "en" else fallback

    def _make_class_section(title: str, desc: str, class_names: list[str]) -> list[dict[str, Any]]:
        """
        Build class sections with separate method lists for large classes
        """
        if not class_names:
            return []

        class_contents: list[Any] = []
        separate_methods: list[str] = []

        for class_name in class_names:
            method_count = categories["class_methods"].get(class_name, 0)
            if config.should_split_methods(method_count):
                class_contents.append({"name": class_name, "members": []})
                separate_methods.append(class_name)
            else:
                class_contents.append(class_name)

        result: list[dict[str, Any]] = [{"title": title, "desc": desc, "contents": class_contents}]

        for class_name in separate_methods:
            method_names = categories["class_method_names"].get(class_name, [])
            method_count = len(method_names)
            method_contents = [f"{class_name}.{method}" for method in method_names]
            result.append(
                {
                    "title": f"{class_name} Methods",
                    "desc": f"Methods for the {class_name} class",
                    "contents": method_contents,
                }
            )
            print(f"  Created separate section for {class_name} with {method_count} methods")

        return result

    sections.extend(
        _make_class_section(
            _t("classes", "Classes"),
            _t("core_classes_desc", "Core classes"),
            categories["classes"],
        )
    )
    sections.extend(
        _make_class_section(
            _t("dataclasses", "Dataclasses"),
            _t("data_classes_desc", "Data-holding classes"),
            categories["dataclasses"],
        )
    )
    sections.extend(
        _make_class_section(
            _t("abstract_classes", "Abstract Classes"),
            _t("abstract_classes_desc", "Abstract base classes"),
            categories["abstract_classes"],
        )
    )
    sections.extend(
        _make_class_section(
            _t("protocols", "Protocols"),
            _t("protocols_desc", "Structural typing protocols"),
            categories["protocols"],
        )
    )

    if categories["enums"]:
        sections.append(
            {
                "title": _t("enumerations", "Enumerations"),
                "desc": _t("enum_types_desc", "Enum types"),
                "contents": categories["enums"],
            }
        )
    if categories["exceptions"]:
        sections.append(
            {
                "title": _t("exceptions", "Exceptions"),
                "desc": _t("exception_classes_desc", "Exception classes"),
                "contents": categories["exceptions"],
            }
        )
    if categories["namedtuples"]:
        sections.append(
            {
                "title": _t("named_tuples", "Named Tuples"),
                "desc": _t("namedtuple_types_desc", "NamedTuple types"),
                "contents": categories["namedtuples"],
            }
        )
    if categories["typeddicts"]:
        sections.append(
            {
                "title": _t("typed_dicts", "Typed Dicts"),
                "desc": _t("typeddict_types_desc", "TypedDict types"),
                "contents": categories["typeddicts"],
            }
        )

    if categories["functions"]:
        sections.append(
            {
                "title": _t("functions", "Functions"),
                "desc": _t("public_functions_desc", "Public functions"),
                "contents": categories["functions"],
            }
        )

    if categories["async_functions"]:
        sections.append(
            {
                "title": _t("async_functions", "Async Functions"),
                "desc": _t("async_functions_desc", "Asynchronous functions"),
                "contents": categories["async_functions"],
            }
        )

    if categories["constants"]:
        sections.append(
            {
                "title": _t("constants", "Constants"),
                "desc": _t("constants_desc", "Module-level constants and data"),
                "contents": categories["constants"],
            }
        )

    if categories["type_aliases"]:
        sections.append(
            {
                "title": _t("type_aliases", "Type Aliases"),
                "desc": _t("type_alias_desc", "Type alias definitions"),
                "contents": categories["type_aliases"],
            }
        )

    if categories["other"]:
        sections.append(
            {
                "title": _t("other", "Other"),
                "desc": _t("additional_exports_desc", "Additional exports"),
                "contents": categories["other"],
            }
        )

    return sections if sections else None


def from_explicit_config(
    config: Config, reference_config: Sequence[object], categories: Categories
) -> list[dict[str, Any]] | None:
    """
    Build sections from explicit reference entries and discovered categories
    """
    # A configured module name expands to the exports discovered within it.
    _MEMBER_CATS = [
        "classes",
        "dataclasses",
        "abstract_classes",
        "protocols",
        "enums",
        "exceptions",
        "namedtuples",
        "typeddicts",
        "functions",
        "async_functions",
        "constants",
        "type_aliases",
        "other",
    ]
    module_members: dict[str, list[str]] = {}
    for cat_key in _MEMBER_CATS:
        for qualified in categories.get(cat_key, []):
            if "." in qualified:
                mod_prefix = qualified.split(".")[0]
                module_members.setdefault(mod_prefix, []).append(qualified)

    sections: list[dict[str, Any]] = []

    for section_config in reference_config:
        if not isinstance(section_config, dict):
            continue
        section_config = cast("dict[str, Any]", section_config)  # pragma: no cover
        title = section_config.get("title")
        subtitle = section_config.get("subtitle")
        desc = section_config.get("desc", "")
        contents_config = section_config.get("contents", [])

        if not contents_config:
            continue  # pragma: no cover

        section_contents: list[Any] = []
        large_classes_in_section: list[str] = []

        for item in contents_config:
            if isinstance(item, str):
                if item in module_members:
                    for member in module_members[item]:
                        method_count = categories["class_methods"].get(member, 0)
                        if config.should_split_methods(method_count):
                            section_contents.append(
                                {"name": member, "members": []}
                            )  # pragma: no cover
                            large_classes_in_section.append(member)  # pragma: no cover
                        else:
                            section_contents.append(member)
                else:
                    method_count = categories["class_methods"].get(item, 0)
                    if config.should_split_methods(method_count):
                        section_contents.append({"name": item, "members": []})
                        large_classes_in_section.append(item)
                    else:
                        section_contents.append(item)
            elif isinstance(item, dict):
                item = cast("dict[str, Any]", item)
                name = item.get("name", "")
                if not name:
                    continue  # pragma: no cover

                members = item.get("members", True)
                include_inherited = item.get("include_inherited", None)

                if members is False:
                    section_contents.append({"name": name, "members": []})
                elif isinstance(members, list):
                    entry: dict[str, Any] = {"name": name, "members": members}
                    if include_inherited is not None:
                        entry["include_inherited"] = include_inherited
                    section_contents.append(entry)
                else:
                    if include_inherited is not None:
                        section_contents.append(
                            {"name": name, "include_inherited": include_inherited}
                        )
                    else:
                        section_contents.append(name)

        if section_contents:
            sections.append(
                {
                    **(
                        {"subtitle": subtitle}
                        if subtitle is not None
                        else {"title": title or "Untitled"}
                    ),
                    "desc": desc,
                    "contents": section_contents,
                }
            )

        for class_name in large_classes_in_section:
            method_names = categories["class_method_names"].get(class_name, [])
            if method_names:
                method_contents = [f"{class_name}.{m}" for m in method_names]
                sections.append(
                    {
                        "title": f"{class_name} Methods",
                        "desc": f"Methods for the {class_name} class",
                        "contents": method_contents,
                    }
                )
                print(
                    f"  Created separate section for {class_name} with {len(method_names)} methods"
                )

    if sections:
        print(f"Generated {len(sections)} section(s) from reference config")

    return sections if sections else None


def sidebar(site_config: Config, api_block: dict[str, Any]) -> Sidebar:
    """
    Make the API reference sidebar

    The sidebar has no title. It lists the reference index first, then groups links to
    generated object pages by API reference section.

    Parameters
    ----------
    site_config
        The project's configuration, which sets the language of the index link.
    api_block
        The API reference configuration whose sections the sidebar lists.

    Returns
    -------
    :
        The sidebar, with `reference` as its `id`.
    """
    from .._apiref import APIReference, SpecObject
    from .._translations import get_translation

    contents: list[dict[str, Any]] = [
        {"text": get_translation("api_index", site_config.lang), "href": "reference/index.qmd"}
    ]
    for section in APIReference({"api-reference": api_block}).sections:
        heading = section.title or section.subtitle or ""
        links = [
            {"text": entry.name, "href": f"reference/{entry.page_path}.qmd"}
            for entry in section.contents
            if isinstance(entry, SpecObject)
        ]
        contents.append({"section": heading, "contents": links})

    return Sidebar("reference", None, tuple(contents))
