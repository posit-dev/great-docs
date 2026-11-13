"""
Build steps for publishing authored pages and assets

Publish the homepage, user guide, configured sections, custom pages and project assets into
the build directory, with their sidebars, navbar links and Quarto resources. In blended homepage
mode, the first user guide page becomes the homepage. Map source paths to published paths so
links between pages point to their published destinations.
"""

from __future__ import annotations

import shutil
from functools import partial
from typing import TYPE_CHECKING, Any

from .._content import custom_pages as authored_pages
from .._content import publish, walk
from .._content import sections as authored_sections
from .._content import user_guide as authored_guide
from .._content.pages import PageMap
from .._contribution import Contribution, NavbarLink, Sidebar
from .._website import page_dates, social_cards
from .._website.ai_agents import llms_txt as llms_files
from .._website.homepage import page as homepage_page
from .._content import homepage as homepage_source
from .._website.navigation import navbar as nav_navbar
from .._website.project_pages import citation, licence, package_info
from . import site
from .facts import source_ref
from .steps import Outcome, Skipped, print_warning

if TYPE_CHECKING:
    from .._content.user_guide import UserGuide
    from .._project import Project
    from .._project.layout import Layout
    from .._project.remote import Remote
    from .._website.identity import Identity
    from .._website.seo.structured_data import StructuredData
    from ..config import Config
    from .pipeline import Run

__all__ = ["assets", "custom_pages", "homepage", "page_map", "sections", "user_guide"]


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


def homepage(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
    remote: Remote,
    fallback: bool = False,
) -> None:
    """
    Write project pages and the homepage from authored content or package metadata

    Write licence, citation and package information pages when enabled and their sources are
    available. Recreate `index.qmd` from the project's index page or README, or generate a
    landing page from package metadata. With `homepage: user_guide`, leave the homepage to
    the user guide step unless `fallback` is `True`.

    Parameters
    ----------
    run
        The current build, including the package name and metadata, discovered user guide
        and API reference availability and configuration for homepage links.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to the written pages.
    remote
        The source of PyPI release dates for the package information page.
    fallback
        Whether to write a homepage from authored content or package metadata even with
        `homepage: user_guide`. Use when no guide pages can supply the homepage.

    Returns
    -------
    :
    """
    metadata = run.project.manifest

    _ = licence.write_page(config, layout, metadata["license"], page_authors, report=print)
    citation_ref = (
        source_ref(config, layout.package_root, warn=print_warning)
        if run.project.repository is not None and (layout.package_root / "CITATION.cff").is_file()
        else "main"
    )
    _ = citation.write_page(
        config,
        layout,
        run.project.name,
        page_authors,
        repository=run.project.repository,
        ref=citation_ref,
        report=print,
    )
    _ = package_info.write_page(config, layout, metadata, remote, report=print)

    if config.homepage == "user_guide" and not fallback:
        return

    guide = run.user_guide
    _ = homepage_page.write_readme(
        config,
        layout,
        metadata=metadata,
        repository=run.project.repository,
        package_name=run.project.name,
        pages=page_map(config, layout, guide),
        page_authors=page_authors,
        has_api_reference=run.has_api_reference,
        has_user_guide=lambda: guide is not None,
        has_llms_txt=llms_files.is_planned(run.api_block),
        report=print,
    )


def user_guide(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
    remote: Remote,
) -> Outcome:
    """
    Publish the user guide and record its sidebar and navbar link

    With `homepage: user_guide`, publish the guide's first page as the homepage. In that mode,
    warn and fall back to the project's index page, README or generated landing page if the
    guide has no pages.

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide and the project's name,
        metadata and API reference configuration for a blended homepage, and records the
        guide's navigation.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to published pages.
    remote
        The source of PyPI release dates for the package information page when writing the
        fallback homepage and project pages.

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
            homepage(run, config, layout, page_authors=page_authors, remote=remote, fallback=True)
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
            config,
            layout,
            run.project,
            guide,
            page_authors=page_authors,
            api_block=run.api_block,
        )

    run.contributions.append(_guide_navigation(config, guide, blended_first_page))

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
    api_block: dict[str, Any] | None,
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
    api_block
        The API reference configuration used to plan links to `llms.txt` and
        `llms-full.txt`, or `None` for a site without an API reference.

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
        first_ug_path.read_text(encoding="utf-8"),
        metadata=project.manifest,
        repository=project.repository,
        package_name=project.name,
        pages=page_map(config, layout, guide),
        page_authors=page_authors,
        has_llms_txt=llms_files.is_planned(api_block),
    )

    first_ug_path.unlink()

    print("   📄 Blended homepage: first UG page → index.qmd")
    return f"user-guide/{dest_rel}"


def _guide_navigation(
    config: Config, guide: UserGuide, blended_first_page: str | None = None
) -> Contribution:
    """
    Make the user guide's sidebar and navbar link

    Parameters
    ----------
    config
        The project's configuration.
    guide
        The user guide.
    blended_first_page
        The promoted page's former path under `user-guide/`, or `None` when no page was
        promoted.

    Returns
    -------
    :
        The sidebar and, unless the guide's first page became the homepage, a navbar
        link to that page.
    """
    sidebar = authored_guide.sidebar(guide)

    # The sidebar must link to the homepage after the first guide page moves there.
    if config.homepage == "user_guide" and blended_first_page:
        authored_guide.link_homepage(sidebar, blended_first_page)

    # In blended mode, the homepage replaces the guide's navbar link.
    navbar: tuple[NavbarLink, ...] = ()
    if config.homepage != "user_guide":
        label = nav_navbar.USER_GUIDE.label(config)
        navbar = (NavbarLink(label, authored_guide.entry(guide), kind="user_guide"),)
    return Contribution(navbar=navbar, sidebars=(_sidebar(sidebar),))


def _sidebar(entry: dict[str, Any]) -> Sidebar:
    """
    Make a sidebar from a `website.sidebar` entry

    Parameters
    ----------
    entry
        The entry, with its `id`, optional `title` and `contents`.

    Returns
    -------
    :
        The sidebar.
    """
    return Sidebar(entry["id"], entry.get("title"), tuple(entry["contents"]))


def sections(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    page_authors: list[dict[str, Any]],
) -> Outcome:
    """
    Publish the configured sections and record their sidebars and navbar links

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide for rewriting links and
        records the sections' navigation.
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

        link = published.navbar
        run.contributions.append(
            Contribution(
                navbar=(
                    NavbarLink(link.text, link.href, kind="authored", after=published.navbar_after),
                ),
                sidebars=(_sidebar(published.sidebar),) if published.sidebar is not None else (),
            )
        )

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
    Publish custom pages and record their navbar links, resources and render exclusions

    Parameters
    ----------
    run
        The current build, which holds the discovered user guide for rewriting links and
        records the pages' navbar links, resources and render exclusions.
    config
        The project's configuration.
    layout
        The project's directories.
    page_authors
        The site's authors, added to published pages.
    identity
        The site's name and addresses for the `<head>` of raw HTML pages.
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

    head = authored_pages.RawPageHead(
        base_url=identity.base_url,
        card_image_url=(
            social_cards.publish_image(config, layout, identity.base_url, report=report)
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
    run.contributions.append(
        Contribution(
            navbar=tuple(
                NavbarLink(link.text, link.href, kind="authored", after=after)
                for link, after in published.navbar
            ),
            resources=tuple(published.resources),
            render_excludes=tuple(published.render_excludes),
        )
    )
    if not published.pages:
        return Skipped("no custom pages")
    return f"{published.pages} custom page(s)"


def assets(run: Run, config: Config, layout: Layout, *, remote: Remote) -> Outcome:
    """
    Copy project assets and merge site settings into the build's Quarto configuration

    Merge settings even without an `assets/` directory so the configuration includes
    navigation and resources recorded by earlier build steps. Pages refer to copied assets
    under `assets/`.

    Parameters
    ----------
    run
        The current build, whose Quarto configuration is changed in place.
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of repository data for the Quarto configuration.

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

    site.update_quarto_config(run, config, layout, remote=remote)
    if not copied:
        return Skipped("no assets directory")
    return "Assets copied"
