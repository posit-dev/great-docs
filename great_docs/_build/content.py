"""
Build steps for publishing authored pages and assets

Publish the user guide, configured sections, custom pages and project assets into the build
directory, with their sidebars, navbar links and Quarto resources. In blended homepage mode,
the first user guide page becomes the homepage. Map source paths to published paths so links
between pages point to their published destinations.
"""

from __future__ import annotations

import shutil
from functools import partial
from typing import TYPE_CHECKING, Any, TypeGuard, cast

from .._content import custom_pages as authored_pages
from .._content import publish, walk
from .._content import sections as authored_sections
from .._content import user_guide as authored_guide
from .._content.pages import PageMap
from .._contribution import Contribution
from .._website import page_dates, quarto_yml, social_cards
from .._website.homepage import page as homepage_page
from .._website.homepage import source as homepage_source
from .._website.navigation import navbar as nav_navbar
from .steps import Outcome, Skipped, print_warning

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._content.user_guide import UserGuide
    from .._layout import Layout
    from .._project import Project
    from .._website.identity import Identity
    from .._website.seo.structured_data import StructuredData
    from ..config import Config
    from .pipeline import Run

__all__ = ["assets", "custom_pages", "page_map", "sections", "user_guide"]


def _is_mapping(value: object) -> TypeGuard[dict[str, Any]]:
    """
    Check whether a `_quarto.yml` entry is a mapping

    Parameters
    ----------
    value
        The entry.

    Returns
    -------
    :
        Whether `value` is a `dict`.
    """
    return isinstance(value, dict)


def page_map(config: Config, layout: Layout, guide: UserGuide | None) -> PageMap:
    """
    Map authored pages to their published paths for this build

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    guide
        The discovered user guide, or `None` when it has no pages.

    Returns
    -------
    :
        The page map for the current sources and configuration.
    """
    homepage = homepage_source.find(layout)[:1]
    if guide is not None and config.homepage == "user_guide":
        homepage.append(guide["files"][0]["path"])
    return PageMap.make(config, layout, guide, homepage)


def user_guide(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
    write_fallback_homepage: Callable[[], None],
) -> Outcome:
    """
    Publish the user guide and add its sidebar and navbar link

    With `homepage: user_guide`, publish the guide's first page as the homepage. In that mode,
    warn and call the fallback homepage writer if the guide has no pages.

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide and the project's name and
        metadata for a blended homepage.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to published pages.
    write_fallback_homepage
        Write the README homepage when `homepage: user_guide` finds no guide pages.

    Returns
    -------
    :
        The result line or skip reason.
    """
    guide = run.user_guide
    if not guide:
        if config.homepage == "user_guide":
            print(
                "   ⚠️  homepage: user_guide is set but no user guide pages found; "
                "falling back to index mode"
            )
            write_fallback_homepage()
        return Skipped("no user guide found")

    print("\n📖 Processing User Guide...")

    if guide.get("explicit", False):
        print("   Using explicit section ordering from great-docs.yml")

    print(f"   Found {len(guide['files'])} page(s)")

    copied_files = _publish_guide_pages(config, layout, guide, page_authors=page_authors)
    print(f"   Copied {len(copied_files)} file(s) to docs/user-guide/")

    blended_first_page = None
    if config.homepage == "user_guide":
        blended_first_page = _promote_first_page(
            config, layout, run.project, guide, page_authors=page_authors
        )

    _add_guide_navigation(config, layout, guide, blended_first_page)

    if guide["sections"]:
        print(f"   Sections: {', '.join(guide['sections'])}")

    print("✅ User Guide configured")
    return "User Guide configured"


def _publish_guide_pages(
    config: Config,
    layout: Layout,
    guide: UserGuide,
    *,
    page_authors: list[dict[str, Any]],
) -> list[str]:
    """
    Publish the user guide's pages, asset directories and directory metadata

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    guide
        The user guide.
    page_authors
        The site's authors, added to published pages.

    Returns
    -------
    :
        The copied page paths relative to the build directory, in reading order.
    """
    source_dir = guide["source_dir"]
    target_dir = layout.build_dir / authored_guide.SIDEBAR_ID
    strip_prefix = not guide.get("explicit", False)
    add_dates = partial(page_dates.add_to_page, config=config, authors=page_authors)
    copied_files = authored_guide.copy_pages(
        guide,
        target_dir,
        layout=layout,
        pages=page_map(config, layout, guide),
        add_dates=add_dates,
    )

    for item in source_dir.iterdir():
        if item.is_dir() and not layout.is_reserved_directory(item) and walk.is_asset_dir(item):
            dst_dir = target_dir / item.name
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            _ = shutil.copytree(item, dst_dir)

    publish.copy_directory_metadata(
        layout,
        (page["path"] for page in guide["files"]),
        source_dir,
        target_dir,
        strip_prefix=strip_prefix,
        report=print_warning,
    )

    return copied_files


def _promote_first_page(
    config: Config,
    layout: Layout,
    project: Project,
    guide: UserGuide,
    *,
    page_authors: list[dict[str, Any]],
) -> str | None:
    """
    Promote the first user guide page to `index.qmd` in blended homepage mode

    Remove the original page from `user-guide/` after writing the homepage.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    project
        The project's name and metadata for the homepage.
    guide
        The user guide.
    page_authors
        The site's authors, added to the homepage.

    Returns
    -------
    :
        The promoted page's former path under `user-guide/`, or `None` when no page was
        promoted.
    """
    if not guide["files"]:
        return None

    dest_rel = authored_guide.published(guide, guide["files"][0])
    first_ug_path = layout.build_dir / authored_guide.SIDEBAR_ID / dest_rel

    if not first_ug_path.exists():
        print(f"   ⚠️  First UG page '{first_ug_path}' not found for blended homepage")
        return None

    _ = homepage_page.write_blended(
        config,
        layout,
        layout.build_dir,
        first_ug_path.read_text(encoding="utf-8"),
        metadata=project.manifest,
        package_name=project.name,
        pages=page_map(config, layout, guide),
        page_authors=page_authors,
    )

    first_ug_path.unlink()

    print("   📄 Blended homepage: first UG page → index.qmd")
    return f"user-guide/{dest_rel}"


def _add_guide_navigation(
    config: Config,
    layout: Layout,
    guide: UserGuide,
    blended_first_page: str | None = None,
) -> None:
    """
    Add the user guide's sidebar and navbar link to `_quarto.yml`

    Leave the build directory unchanged if it has no `_quarto.yml`.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    guide
        The user guide.
    blended_first_page
        The promoted page's former path under `user-guide/`, or `None` when no page was
        promoted.

    Returns
    -------
    :
    """
    build_dir = layout.build_dir
    if not quarto_yml.path(build_dir).exists():
        return

    quarto_config = quarto_yml.read(build_dir)

    if "website" not in quarto_config:
        quarto_config["website"] = {}
    website = cast("dict[str, Any]", quarto_config["website"])

    sidebar_config = authored_guide.sidebar(guide)

    # The sidebar must link to the homepage after the first guide page moves there.
    if config.homepage == "user_guide" and blended_first_page:
        authored_guide.link_homepage(sidebar_config, blended_first_page)

    if "sidebar" not in website:
        website["sidebar"] = []

    sidebar = [
        entry
        for entry in cast("list[Any]", website["sidebar"])
        if not (_is_mapping(entry) and entry.get("id") == authored_guide.SIDEBAR_ID)
    ]
    sidebar.append(sidebar_config)
    website["sidebar"] = sidebar

    # In blended mode, the homepage replaces the guide's navbar link.
    if config.homepage != "user_guide" and "navbar" in website:
        navbar = cast("dict[str, Any]", website["navbar"])
        if "left" in navbar:
            items = cast("list[Any]", navbar["left"])
            href = authored_guide.entry(guide)
            # Match the destination; the label may already be translated.
            has_user_guide = any(_is_mapping(item) and item.get("href") == href for item in items)
            if not has_user_guide:
                # Place the guide before Reference, or first if Reference is absent.
                insert_idx = next(
                    (
                        i
                        for i, item in enumerate(items)
                        if _is_mapping(item) and nav_navbar.REFERENCE.owns(item.get("href"))
                    ),
                    0,
                )
                items.insert(
                    insert_idx,
                    {"text": nav_navbar.USER_GUIDE.label(config), "href": href},
                )

    quarto_yml.write(build_dir, quarto_config)


def sections(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
) -> Outcome:
    """
    Publish the configured sections and add their sidebars and navbar links

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide for rewriting links.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to published pages.

    Returns
    -------
    :
        The result line or skip reason.
    """
    if not config.sections:
        return Skipped("no sections configured")
    found = authored_sections.read(config, layout, report=print_warning)
    if not found:
        return "No sections to process"

    build_dir = layout.build_dir
    pages = page_map(config, layout, run.user_guide)
    add_dates = partial(page_dates.add_to_page, config=config, authors=page_authors)
    for section in found:
        section.destination.mkdir(parents=True, exist_ok=True)
        # Copy asset directories first so published pages replace their raw copies
        for item in section.source.iterdir():
            if item.is_dir() and not layout.is_reserved_directory(item) and walk.is_asset_dir(item):
                destination = section.destination / item.name
                if destination.exists():
                    shutil.rmtree(destination)
                _ = shutil.copytree(item, destination)

        published = authored_sections.publish(
            section, config=config, layout=layout, pages=pages, add_dates=add_dates
        )
        if not section.blog:
            publish.copy_directory_metadata(
                layout,
                section.files,
                section.source,
                section.destination,
                strip_prefix=True,
                report=print_warning,
            )

        quarto_config = quarto_yml.read(build_dir, seed_website=True)
        changed = published.sidebar is not None
        if published.sidebar is not None:
            sidebar_id = published.sidebar["id"]
            quarto_config["website"]["sidebar"] = [
                *(
                    entry
                    for entry in cast("list[Any]", quarto_config["website"]["sidebar"])
                    if not (_is_mapping(entry) and entry.get("id") == sidebar_id)
                ),
                published.sidebar,
            ]
        if nav_navbar.add_link(
            quarto_config, published.navbar, config, after=published.navbar_after
        ):
            changed = True
        if changed:
            quarto_yml.write(build_dir, quarto_config)

        label = "📰" if section.blog else "📂"
        print(f"   {label} {section.title}: {len(published.pages)} post(s) from {section.dir}/")

    return f"{len(found)} section(s) processed"


def custom_pages(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
    identity: Identity,
    structured_data: StructuredData | None,
    default_description: str | None,
) -> Outcome:
    """
    Publish the configured custom pages

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide for rewriting links.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to published pages.
    identity
        The site's name and addresses for the `<head>` of raw HTML pages. Earlier steps can
        change the title in `_quarto.yml`; resolve the identity when this step runs.
    structured_data
        The site's structured data for raw HTML pages, or `None` to omit it.
    default_description
        The search description for raw HTML pages without their own, or `None` for no default.

    Returns
    -------
    :
        The result line or skip reason.
    """
    report = print_warning
    sources = authored_pages.find_sources(config, layout, report=report)
    if not sources:
        return Skipped("no custom pages")

    build_dir = layout.build_dir
    head = authored_pages.RawPageHead(
        base_url=identity.base_url,
        card_image_url=(
            social_cards.publish_image(config, layout, build_dir, identity.base_url, report=report)
            if config.social_cards_enabled
            else None
        ),
        structured_data=structured_data,
        site_name=identity.name,
        default_description=default_description,
    )
    published = authored_pages.publish(
        sources,
        config=config,
        layout=layout,
        pages=page_map(config, layout, run.user_guide),
        head=head,
        add_dates=partial(page_dates.add_to_page, config=config, authors=page_authors),
        report=report,
    )
    # `navbar_after` refers to a label; contributions cannot express that placement.
    for link, after in published.navbar:
        quarto_config = quarto_yml.read(build_dir, seed_website=True)
        if nav_navbar.add_link(quarto_config, link, config, after=after):
            quarto_yml.write(build_dir, quarto_config)
    if published.resources or published.render_excludes:
        contribution = Contribution(
            resources=tuple(published.resources),
            render_excludes=tuple(published.render_excludes),
        )
        with quarto_yml.edit(build_dir, seed_website=True) as quarto_config:
            quarto_yml.apply(quarto_config, contribution)
    if not published.pages:
        return Skipped("no custom pages")
    return f"{published.pages} custom page(s)"


def assets(layout: Layout, *, update_quarto_config: Callable[[], None]) -> Outcome:
    """
    Copy the project's `assets/` directory and complete the Quarto configuration

    Pages refer to the copied files under `assets/`. Earlier steps also copy resources, such
    as user guide images. Refresh the Quarto configuration even when the project has no
    `assets/` directory so those resources are registered.

    Parameters
    ----------
    layout
        The project's directories.
    update_quarto_config
        Merge the site's settings and resources into `_quarto.yml`.

    Returns
    -------
    :
        The result line or skip reason.
    """
    source_assets = layout.source_dir / "assets"
    copied = source_assets.is_dir()
    if copied:
        dest_assets = layout.build_dir / "assets"
        # Replace the directory so files removed from the source do not survive a rebuild.
        if dest_assets.exists():
            shutil.rmtree(dest_assets)
        _ = shutil.copytree(source_assets, dest_assets)
        file_count = sum(1 for path in dest_assets.rglob("*") if path.is_file())
        print(f"\n📦 Copied {file_count} asset file(s) to great-docs/assets/")

    update_quarto_config()
    if not copied:
        return Skipped("no assets directory")
    return "Assets copied"
