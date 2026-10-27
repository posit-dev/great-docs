"""
Reference sidebars rendered once and shared by their pages

Quarto rebuilds a page's whole sidebar on every page that shows it, so a
reference sidebar with a thousand links costs a thousand links per page.
Before rendering, each long sidebar is copied to a `gd-full-<id>` sidebar
that only a one-page template shows, and the original keeps just the links
the navbar needs. The pages keep naming the original sidebar, so Quarto
renders a short one. After rendering, `share-sidebars.py` copies the
template's sidebar into each page, marks the page's link as current, opens
the sections around it, and restores the search crumbs Quarto takes from
the sidebar. The result matches what Quarto renders on its own.

A sidebar is left alone when sharing could change a page, for instance when
its pages show breadcrumbs or previous and next links, which Quarto also
builds from the sidebar.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, cast

from yaml12 import format_yaml, parse_yaml, write_yaml

from ..._utils import QUARTO_YML_HEADER
from ..._yaml import YamlValue, split_front_matter
from ..page_metadata import rendered_pages

SIDEBAR_IDS = ("reference", "cli-reference", "mcp-reference")
"""The sidebars Great Docs generates for its reference sections"""

SCRIPT = "share-sidebars.py"
"""The post-render script, copied from the package assets into `scripts/`"""

MANIFEST = "_gd_sidebars.json"
"""What the post-render script needs, written to the build directory"""

FULL_PREFIX = "gd-full-"
"""Prefix of the id of the full copy of a shared sidebar"""

TEMPLATE_PREFIX = "gd-sidebar-"
"""Prefix of the name of the page that renders the full sidebar"""

PREVIEW_ENV = "GREAT_DOCS_PREVIEW"
"""Set for `quarto preview`, which needs the template page to stay in place"""

# Quarto's input formats, each of which renders to `<stem>.html`
_INPUT_SUFFIXES = (".qmd", ".md", ".markdown", ".rmd", ".Rmd", ".rmarkdown", ".ipynb")


def prepare(build_dir: Path) -> list[str]:
    """
    Arrange for each long reference sidebar to be rendered once

    Run this after every other change to the project, just before Quarto
    renders it.

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        The ids of the shared sidebars, empty when none is shared.
    """
    quarto_yml = build_dir / "_quarto.yml"
    if not quarto_yml.is_file():
        return []
    text = quarto_yml.read_text(encoding="utf-8")
    config = cast("dict[str, Any]", parse_yaml(text) or {})
    website: YamlValue = config.get("website")
    sidebars = website.get("sidebar") if isinstance(website, dict) else None
    if not isinstance(sidebars, list):
        return []

    project = _Project(build_dir, config)
    plans = [plan for sidebar in project.sidebars if (plan := project.plan(sidebar))]
    plans = project.settle(plans)
    if not plans:
        return []

    # Work out the crumbs from the full sidebars before trimming them
    manifest = {
        "output_dir": str(config.get("project", {}).get("output-dir", "_site")),
        "sidebars": [project.manifest_entry(plan) for plan in plans],
    }

    for plan in plans:
        sidebars.append({**copy.deepcopy(plan.sidebar), "id": FULL_PREFIX + plan.id})
        plan.sidebar["contents"] = project.navbar_items(plan.sidebar)
        for directory in plan.tag_dirs:
            _tag_directory(build_dir / directory, plan.id)
        _write_template(build_dir / plan.template, plan)

    project_config = config.setdefault("project", {})
    entry = f"scripts/{SCRIPT}"
    post_render: YamlValue = project_config.get("post-render")
    if post_render is None:
        project_config["post-render"] = entry
    else:
        scripts: list[YamlValue] = post_render if isinstance(post_render, list) else [post_render]
        if entry not in scripts:
            project_config["post-render"] = [*scripts, entry]

    (build_dir / "scripts").mkdir(exist_ok=True)
    _ = shutil.copy2(Path(__file__).parents[2] / "assets" / SCRIPT, build_dir / "scripts" / SCRIPT)

    _ = (build_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with open(quarto_yml, "w", encoding="utf-8") as f:
        if text.startswith(QUARTO_YML_HEADER):
            _ = f.write(QUARTO_YML_HEADER)
        write_yaml(config, f)
    return [plan.id for plan in plans]


@dataclass
class _Plan:
    """How one sidebar is shared"""

    sidebar: dict[str, Any]
    """The sidebar's entry in `_quarto.yml`, trimmed in place when shared"""

    pages: list[str]
    """Inputs that show the sidebar, relative to the project"""

    implicit: set[str] = field(default_factory=set[str])
    """Pages that show the sidebar only because they are listed in it"""

    tag_dirs: list[str] = field(default_factory=list[str])
    """Directories whose metadata names the sidebar for its implicit pages"""

    @property
    def id(self) -> str:
        return str(self.sidebar["id"])

    @property
    def template(self) -> str:
        """The input of the page that renders the full sidebar"""
        parent = _common_dir(self.pages)
        return str(PurePosixPath(parent, f"{TEMPLATE_PREFIX}{self.id}.qmd"))


class _Project:
    """The parts of a Quarto project that decide which sidebar a page shows"""

    def __init__(self, build_dir: Path, config: dict[str, Any]):
        self.build_dir = build_dir
        self.config = config
        website = config.get("website", {})
        self.sidebars: list[dict[str, Any]] = [
            s for s in website.get("sidebar", []) if isinstance(s, dict)
        ]
        navbar: dict[str, Any] = (
            website.get("navbar") if isinstance(website.get("navbar"), dict) else {}
        )
        self.navbar: list[YamlValue] = [*(navbar.get("left") or []), *(navbar.get("right") or [])]
        self.page_navigation = bool(website.get("page-navigation"))
        self.bread_crumbs = website.get("bread-crumbs", True) is not False
        search: YamlValue = website.get("search")
        self.merge_navbar_crumbs = not (
            isinstance(search, dict) and search.get("merge-navbar-crumbs") is False
        )
        self._pages = sorted(
            path.relative_to(build_dir).as_posix() for path in rendered_pages(build_dir, config)
        )
        # The first sidebar listing each page, read before any is trimmed
        self._listed_in: dict[str, str] = {}
        for sidebar in reversed(self.sidebars):
            for href in _hrefs(sidebar.get("contents")):
                self._listed_in[href] = str(sidebar.get("id"))
        self._unnamed = any(s.get("id") is None for s in self.sidebars)
        self._meta: dict[str, dict[str, Any]] = {}
        self._dir_meta: dict[str, dict[str, Any]] = {}

    # ── Reading the project ──────────────────────────────────────────────────

    def page_meta(self, page: str) -> dict[str, Any]:
        """Return a page's front matter, or `{}` when it has none"""
        if page not in self._meta:
            try:
                content = (self.build_dir / page).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                content = ""
            self._meta[page] = dict(split_front_matter(content)[0].data)
        return self._meta[page]

    def dir_meta(self, directory: str) -> dict[str, Any]:
        """Return a directory's `_metadata.yml`, or `{}` when it has none"""
        if directory not in self._dir_meta:
            meta: Any = None
            for name in ("_metadata.yml", "_metadata.yaml"):
                path = self.build_dir / directory / name
                if path.is_file():
                    try:
                        meta = parse_yaml(path.read_text(encoding="utf-8"))
                    except Exception:
                        meta = None
                    break
            self._dir_meta[directory] = meta if isinstance(meta, dict) else {}
        return self._dir_meta[directory]

    def option(self, page: str, key: str) -> Any:
        """Return a page option from its front matter or directory metadata"""
        meta = self.page_meta(page)
        if key in meta:
            return meta[key]
        for directory in _ancestors(page):
            if key in self.dir_meta(directory):
                return self.dir_meta(directory)[key]
        return None

    def shown_sidebar(self, page: str, tags: dict[str, str] | None = None) -> str | None:
        """
        Return the id of the sidebar Quarto shows on a page

        Parameters
        ----------
        page
            The page's input, relative to the project.
        tags
            Directory metadata added for sharing, mapping a directory to the
            sidebar it names.

        Returns
        -------
        :
            The sidebar's id, `""` for a sidebar without one, or `None` when
            the page shows no sidebar.
        """
        explicit = self.page_meta(page).get("sidebar")
        if explicit is None:
            for directory in _ancestors(page):
                if tags and directory in tags:
                    explicit = tags[directory]
                    break
                if "sidebar" in self.dir_meta(directory):
                    explicit = self.dir_meta(directory)["sidebar"]
                    break
        if explicit is False:
            return None
        if explicit is not None:
            if any(s.get("id") == explicit for s in self.sidebars):
                return str(explicit)
        return self.containing_sidebar(_output(page))

    def containing_sidebar(self, href: str) -> str | None:
        """Return the sidebar Quarto picks for a page that names none"""
        # Quarto matches a missing page option against a sidebar without an
        # id, so such a sidebar shows on every page that names none
        if self._unnamed:
            return ""
        return self._listed_in.get(href)

    # ── Planning ─────────────────────────────────────────────────────────────

    def plan(self, sidebar: dict[str, Any]) -> _Plan | None:
        """Plan the sharing of a sidebar, or return `None` when it can't be shared"""
        sidebar_id = sidebar.get("id")
        if sidebar_id not in SIDEBAR_IDS or not _shareable(sidebar.get("contents")):
            return None
        if len(_hrefs(sidebar["contents"])) <= len(self.navbar_items(sidebar)):
            return None
        if any(str(s.get("id", "")).startswith(FULL_PREFIX) for s in self.sidebars):
            return None

        pages: list[str] = []
        implicit: set[str] = set()
        for page in self._pages:
            if self.shown_sidebar(page) != sidebar_id:
                continue
            if self.option(page, "sidebar") is None:
                implicit.add(page)
            pages.append(page)
        # Listed pages Quarto can't read the options of
        for href in _input_hrefs(sidebar["contents"]):
            if href.endswith(".ipynb") and (self.build_dir / href).is_file():
                return None
        if not pages:
            return None
        for page in pages:
            # Quarto builds breadcrumbs and previous/next links from the sidebar
            navigation = self.option(page, "page-navigation")
            if navigation is True or (self.page_navigation and navigation is not False):
                return None
            if self.bread_crumbs and self.option(page, "bread-crumbs") is not False:
                return None

        plan = _Plan(sidebar=sidebar, pages=pages, implicit=implicit)
        if implicit:
            root = _common_dir(implicit)
            if root in ("", "."):
                return None
            plan.tag_dirs = [root]
        if (self.build_dir / plan.template).exists():
            return None
        return plan

    def settle(self, plans: list[_Plan]) -> list[_Plan]:
        """
        Drop plans whose directory metadata would move another page

        A directory's metadata names the sidebar for every page below it
        that names none, so it may only cover pages that already show it.
        """
        plans = list(plans)
        while plans:
            tags = {d: plan.id for plan in plans for d in plan.tag_dirs}
            bad = None
            for plan in plans:
                for directory in plan.tag_dirs:
                    for page in self._below(directory):
                        if self.shown_sidebar(page, tags) != self.shown_sidebar(page):
                            bad = plan
                            break
                    # The options of notebooks aren't read here
                    if bad is None and any(self._notebooks(directory)):
                        bad = plan
                    if bad:
                        break
                if bad:
                    break
            if bad is None:
                return plans
            plans.remove(bad)
        return plans

    def _below(self, directory: str) -> Iterator[str]:
        prefix = directory.rstrip("/") + "/"
        return (page for page in self._pages if page.startswith(prefix))

    def _notebooks(self, directory: str) -> Iterator[Path]:
        for path in (self.build_dir / directory).rglob("*.ipynb"):
            rel = path.relative_to(self.build_dir)
            if not any(part.startswith(("_", ".")) for part in rel.parts):
                yield path

    def navbar_items(self, sidebar: dict[str, Any]) -> list[YamlValue]:
        """
        Return the sidebar links that a short sidebar keeps

        Quarto marks the navbar link whose target the sidebar links to as
        current, so the short sidebar keeps those links (or its first link
        when the navbar links to none of them).
        """
        targets = {_output(_href(item)) for item in self.navbar if _href(item)}
        kept = [
            item for item in _leaves(sidebar.get("contents")) if _output(_href(item)) in targets
        ]
        if not kept:
            kept = list(_leaves(sidebar.get("contents")))[:1]
        short: list[YamlValue] = []
        for item in kept:
            if isinstance(item, dict):
                text, href = _text(item), _href(item)
                short.append({"text": text, "href": href} if text else {"href": href})
            else:
                short.append(item)
        return short

    # ── Manifest ─────────────────────────────────────────────────────────────

    def manifest_entry(self, plan: _Plan) -> dict[str, Any]:
        """Describe a shared sidebar for the post-render script"""
        crumbs: dict[str, list[str | None]] = {}
        for page in plan.pages:
            trail = self.crumbs(plan, page)
            if trail is not None:
                crumbs[_output(page)] = trail
        return {
            "id": plan.id,
            "template": _output(plan.template),
            "pages": [_output(page) for page in plan.pages],
            "crumbs": crumbs,
        }

    def crumbs(self, plan: _Plan, page: str) -> list[str | None] | None:
        """
        Return the search crumbs Quarto gives a page from the full sidebar

        These are the sections around the page's link and the link itself,
        after the navbar item that opens the sidebar.

        Returns
        -------
        :
            The crumbs, or `None` when the page has none or they can't be
            worked out (such as a link without text to a page without a title).
        """
        href = _output(page)
        trail = _trail(plan.sidebar.get("contents"), href)
        if not trail:
            return None
        texts: list[str | None] = []
        for item in trail:
            text = _text(item)
            if text is None and _href(item):
                target = _href(item)
                if target in self._pages:
                    title = self.page_meta(target).get("title")
                    text = title if isinstance(title, str) else None
                if text is None:
                    return None
            texts.append(text)
        if self.merge_navbar_crumbs:
            nav_item = self._navbar_item(plan, page)
            if isinstance(nav_item, dict):
                text = nav_item.get("text")
                if isinstance(text, str) and text and texts[0] != text:
                    texts.insert(0, text)
        return texts

    def _navbar_item(self, plan: _Plan, page: str) -> YamlValue:
        """Return the navbar item Quarto pairs with a page's sidebar"""
        named = page not in plan.implicit
        for item in self.navbar:
            href = _href(item)
            if not href:
                continue
            # A page that names its sidebar pairs it with any navbar link
            if named or self.containing_sidebar(_output(href)) == plan.id:
                return item
        return None


# ── Sidebar contents ─────────────────────────────────────────────────────────


def _shareable(contents: YamlValue) -> bool:
    """Check that sidebar contents are plain links and sections"""
    if not isinstance(contents, list):
        return False
    for item in contents:
        if isinstance(item, str):
            if "*" in item or item == "auto":
                return False
        elif isinstance(item, dict):
            if "auto" in item:
                return False
            if "contents" in item and not _shareable(item["contents"]):
                return False
        else:
            return False
    return True


def _leaves(contents: Iterable[YamlValue] | None) -> Iterator[YamlValue]:
    """Yield the sidebar's links in order, sections with links included"""
    for item in contents or []:
        if _href(item):
            yield item
        if isinstance(item, dict) and isinstance(inner := item.get("contents"), list):
            yield from _leaves(inner)


def _hrefs(contents: Iterable[YamlValue] | None) -> set[str]:
    return {_output(_href(item)) for item in _leaves(contents)}


def _input_hrefs(contents: Iterable[YamlValue] | None) -> Iterable[str]:
    return (_href(item) for item in _leaves(contents))


def _trail(contents: Iterable[YamlValue] | None, href: str) -> list[YamlValue]:
    """Return the sections around a sidebar link and the link, as Quarto finds them"""
    for item in contents or []:
        if _output(_href(item)) == href:
            return [item]
        if isinstance(item, dict) and isinstance(section := item.get("contents"), list):
            inner = _trail(section, href)
            if inner:
                return [item, *inner]
    return []


def _href(item: YamlValue) -> str:
    """Return a sidebar or navbar item's target as a project path, or `""`"""
    if isinstance(item, str):
        href = item
    elif isinstance(item, dict) and isinstance(target := item.get("href"), str):
        href = target
    else:
        return ""
    href = href.strip()
    while href.startswith("./"):
        href = href[2:]
    return href.lstrip("/")


def _text(item: YamlValue) -> str | None:
    if isinstance(item, dict):
        for key in ("text", "section"):
            if isinstance(text := item.get(key), str):
                return text
    return None


def _output(href: str) -> str:
    """Return the output page of a project input, or the target unchanged"""
    path = PurePosixPath(href)
    if path.suffix in _INPUT_SUFFIXES:
        return str(path.with_suffix(".html"))
    return href


def _ancestors(page: str) -> Iterator[str]:
    """Yield a page's directories, innermost first, ending with the project"""
    parent = PurePosixPath(page).parent
    while True:
        yield "" if str(parent) == "." else str(parent)
        if str(parent) in (".", ""):
            return
        parent = parent.parent


def _common_dir(pages: Iterable[str]) -> str:
    parents = [str(PurePosixPath(page).parent) for page in pages]
    common = os.path.commonpath(parents) if parents else ""
    return "" if common == "." else common


# ── Writing ──────────────────────────────────────────────────────────────────


def _tag_directory(directory: Path, sidebar_id: str) -> None:
    """Name a sidebar in a directory's metadata, keeping what is there"""
    path = directory / "_metadata.yaml"
    if not path.is_file():
        path = directory / "_metadata.yml"
    meta: Any = {}
    if path.is_file():
        meta = parse_yaml(path.read_text(encoding="utf-8")) or {}
    meta = {**meta, "sidebar": sidebar_id}
    _ = path.write_text(format_yaml(meta) + "\n", encoding="utf-8")


def _write_template(path: Path, plan: _Plan) -> None:
    title = plan.sidebar.get("title")
    meta = {
        "title": title if isinstance(title, str) and title else plan.id,
        "sidebar": FULL_PREFIX + plan.id,
        "search": False,
        "page-navigation": False,
        "bread-crumbs": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(f"---\n{format_yaml(meta)}\n---\n", encoding="utf-8")
