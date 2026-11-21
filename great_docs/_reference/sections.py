"""
Build API reference section descriptions
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import closing
from typing import TYPE_CHECKING, Any, cast

from .._contribution import Contribution, NavbarLink, Sidebar

if TYPE_CHECKING:
    from .._apiref.api_reference import APIReference
    from .._apiref.spec import ReferenceSpec
    from ..config import Config
    from .discovery import Categories


def _configured_entry(item: dict[str, Any]) -> str | dict[str, Any]:
    """
    Preserve member selection and page placement for a reference entry
    """
    if "inline_methods" in item:
        raise ValueError(
            "Per-entry `inline_methods` is unsupported. Use `members_on_same_page` "
            "to choose member placement."
        )
    if "children" in item:
        raise ValueError(
            "`children` is no longer supported. Set `members_on_same_page: false` "
            "to give each member a page, or use `members` to select which members to document."
        )
    name = item["name"]
    members = item.get("members", True)
    entry: dict[str, Any] = {"name": name}
    if members is False:
        entry["members"] = []
    elif isinstance(members, list):
        entry["members"] = members
    if members is not False and item.get("include_inherited") is not None:
        entry["include_inherited"] = item["include_inherited"]
    if "members_on_same_page" in item:
        if not isinstance(item["members_on_same_page"], bool):
            raise ValueError("Per-entry `members_on_same_page` must be true or false.")
        entry["members_on_same_page"] = item["members_on_same_page"]
    return entry if len(entry) > 1 else name


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

                section_contents.append(_configured_entry(item))

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

    from .._translations import translate

    lang = config.lang

    def _t(key: str, fallback: str) -> str:
        return translate(key, lang) if lang != "en" else fallback

    def _make_class_section(title: str, desc: str, class_names: list[str]) -> list[dict[str, Any]]:
        """
        Keep documented classes in their API reference category
        """
        if not class_names:
            return []
        return [{"title": title, "desc": desc, "contents": list(class_names)}]

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
    reference_config: Sequence[object], categories: Categories
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
                section_contents.extend(module_members.get(item, [item]))
            elif isinstance(item, dict):
                item = cast("dict[str, Any]", item)
                name = item.get("name", "")
                if not name:
                    continue

                section_contents.append(_configured_entry(item))

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

    if sections:
        print(f"Generated {len(sections)} section(s) from reference config")

    return sections if sections else None


def sidebar(config: Config, spec: ReferenceSpec) -> Sidebar:
    """
    Make the API reference sidebar

    The sidebar has no title. It lists the reference index first, then groups links to
    generated object pages by API reference section.

    Parameters
    ----------
    config
        The project's configuration, which sets the language of the index link.
    spec
        The package and sections to list in the sidebar.

    Returns
    -------
    :
        The sidebar, with `reference` as its `id`.
    """
    from .._apiref import APIReference, SpecObject
    from .._translations import translate

    contents: list[dict[str, Any]] = [
        {"text": translate("api_index", config.lang), "href": "reference/index.qmd"}
    ]
    with closing(APIReference(config, spec)) as reference:
        sections = reference.sections

    for section in sections:
        heading = section.title or section.subtitle or ""
        links = [
            {"text": entry.name, "href": _page_href(entry.page_path)}
            for entry in section.contents
            if isinstance(entry, SpecObject)
        ]
        contents.append({"section": heading, "contents": links})

    return Sidebar("reference", None, tuple(contents))


def _page_href(page_path: str) -> str:
    """
    Make the sidebar link target of a reference page

    Parameters
    ----------
    page_path
        The page's path in the reference directory, without a suffix.

    Returns
    -------
    :
        The page's path relative to the Quarto project.
    """
    return f"reference/{page_path}.qmd"


def prune_sidebar(quarto_config: dict[str, Any], api_reference: APIReference) -> None:
    """
    Remove reference sidebar links to pages that the API reference did not generate

    The sidebar lists the configured objects before the extension runs, so it still
    links to objects that an object hook excludes. Remove those links, and any section
    that loses all of its links.

    Parameters
    ----------
    quarto_config
        The Quarto configuration whose `reference` sidebar to update in place.
    api_reference
        The generated API reference.

    Returns
    -------
    :
    """
    website = cast("dict[str, Any]", quarto_config.get("website", {}))
    sidebars = cast("list[dict[str, Any]]", website.get("sidebar", []))
    reference = next((s for s in sidebars if s.get("id") == "reference"), None)
    if reference is None:
        return

    generated = {_page_href(page.path) for page in api_reference.manifest.pages}
    contents: list[Any] = []
    for item in cast("list[Any]", reference["contents"]):
        if isinstance(item, dict) and "section" in item:
            section = cast("dict[str, Any]", item)
            links = cast("list[dict[str, str]]", section["contents"])
            kept = [link for link in links if link["href"] in generated]
            if links and not kept:
                continue
            item = {**section, "contents": kept}
        contents.append(item)
    reference["contents"] = contents


def contribution(config: Config, spec: ReferenceSpec) -> Contribution:
    """
    Build the API reference sidebar and navbar link

    Parameters
    ----------
    config
        The project's configuration, including the navbar label and the language of
        the navbar and sidebar links.
    spec
        The package and sections to list in the sidebar.

    Returns
    -------
    :
        The `reference` sidebar and a navbar link to `reference/index.qmd`. The navbar
        label is `reference.title` when set, otherwise "Reference" in the site's language.
    """
    from .._translations import translate

    label = config.reference_title or translate("reference", config.lang)
    return Contribution(
        navbar=(NavbarLink(text=label, href="reference/index.qmd"),),
        sidebars=(sidebar(config, spec),),
    )
