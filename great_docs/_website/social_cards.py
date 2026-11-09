"""
Open Graph and Twitter card metadata for shared links

Generate social card tags unless the site's header includes already contain
an Open Graph property. Quarto does not check for existing tags, so this
avoids duplicates. Configure Quarto's `open-graph` and `twitter-card` options
for most tags, and add the page type and preferred URL separately.

Use page front matter to match card titles and descriptions to the page's
`<title>` and meta description. Otherwise Quarto uses its own title format
and the page's first paragraph.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit, urlunsplit

from .._content import publish
from . import head
from .seo import description
from .seo import title as seo_title

if TYPE_CHECKING:
    from collections.abc import Callable

    from .._project.layout import Layout
    from .._yaml import YamlMapping
    from ..config import Config

PAGE_KEYS = ("open-graph", "twitter-card")
"""Front matter keys that set a page's own card options"""

OG_TYPE_TAG = '<meta property="og:type" content="website">'

OWN_CARDS_KEY = "gd-own-social-cards"
"""Front matter key marking a page whose own header includes declare its card tags"""

OG_TYPE_PARTIAL = f"$if({OWN_CARDS_KEY})$$else${OG_TYPE_TAG}$endif$"
"""The `og:type` tag for the metadata partial, left out of pages with their own tags"""
_OG_PROPERTY = re.compile(r"""property=["']?og:""")
_TITLE = re.compile(r"<title[^>]*>([^<]*)</title>", re.IGNORECASE)
_DESCRIPTION = re.compile(
    r"""<meta\s+name=["']?description["']?\s+content="([^"]*)\"""", re.IGNORECASE
)


def applies(quarto_config: dict[str, Any], config: Config, project_dir: Path) -> bool:
    """
    Check whether to generate social card tags for rendered pages

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`.
    config
        Project configuration.
    project_dir
        Base directory for relative header file paths.

    Returns
    -------
    :
        `True` when social cards are enabled and the site's header includes
        contain no Open Graph property.
    """
    return config.social_cards_enabled and not head.includes_match(
        quarto_config, project_dir, _OG_PROPERTY
    )


def twitter_handle(handle: str) -> str:
    """
    Normalise a Twitter/X handle to start with `@`

    Parameters
    ----------
    handle
        The handle, with or without its `@`.

    Returns
    -------
    :
        The handle, prefixed with `@` if needed.
    """
    return handle if handle.startswith("@") else f"@{handle}"


def register(
    quarto_config: dict[str, Any], config: Config, image_url: str | None, project_dir: Path
) -> None:
    """
    Enable Quarto's Open Graph and Twitter card tags for the whole site

    Without `image_url`, Quarto picks each page's preview image from its
    content.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    image_url
        The default card image address, or `None` to use page images.
    project_dir
        Base directory for relative header file paths.
    """
    if not applies(quarto_config, config, project_dir):
        return

    open_graph: dict[str, str] = {}
    twitter_card: dict[str, str] = {}
    if image_url:
        open_graph["image"] = image_url
        twitter_card["image"] = image_url
    if config.social_cards_twitter_card:
        twitter_card["card-style"] = config.social_cards_twitter_card
    if config.social_cards_twitter_site:
        twitter_card["site"] = twitter_handle(config.social_cards_twitter_site)

    website = quarto_config.setdefault("website", {})
    website["open-graph"] = open_graph or True
    website["twitter-card"] = twitter_card or True


def publish_image(
    config: Config,
    layout: Layout,
    base_url: str | None,
    *,
    report: Callable[[str], None],
) -> str | None:
    """
    Copy the configured card image into the site and return its address

    A configured image URL is returned unchanged. A local image is resolved
    relative to the source directory and copied to the build directory's root.

    Parameters
    ----------
    config
        Project configuration, whose `social_cards.image` names the image.
    layout
        Project directories for resolving the source image and copying it to the
        build directory.
    base_url
        The preferred site address with a trailing slash, or `None`.
    report
        Receives a warning when the local image does not exist.

    Returns
    -------
    :
        The configured URL or the copied image's address under `base_url`.
        Without `base_url`, the copied image has a site-relative path. The
        result is `None` when no image is configured or the local image is
        missing.
    """
    image_path = config.social_cards_image
    if not image_path:
        return None
    if urlsplit(image_path).scheme or image_path.startswith("//"):
        return image_path

    image_url = urlsplit(image_path)
    source = layout.source_dir / unquote(image_url.path)
    if not source.is_file():
        report(f"Social card image not found: {image_path}")
        return None

    # The image must be at the site root to match the returned address.
    _ = publish.copy_asset(layout, source, layout.build_dir / source.name)
    path = base_url + source.name if base_url else source.name
    return urlunsplit(("", "", path, image_url.query, image_url.fragment))


def page_title(title: str | None, site_name: str | None, config: Config) -> str | None:
    """
    Build the card title that matches a page's `<title>`

    Parameters
    ----------
    title
        The page title, or `None` when the `title` front matter value is
        absent or not a string.
    site_name
        The site's `website.title`.
    config
        Project configuration.

    Returns
    -------
    :
        The title as a metadata value, or `None` when Quarto's own title
        already matches `<title>`. Use the site name for an empty title to
        avoid Quarto's leading dash.
    """
    if title is None or not site_name:
        return None
    if not title.strip():
        return description.as_metadata(site_name)
    template = seo_title.template(config)
    if template is None:
        return None
    return seo_title.apply(
        template, title, description.as_metadata(site_name), escape=description.as_metadata
    )


def page_entries(
    front_matter: YamlMapping,
    body: str,
    page_dir: Path,
    site_name: str | None,
    config: Config,
    default: str | None,
    header_description: str | None = None,
) -> dict[str, Any]:
    """
    Choose the card options Python writes into a page's front matter

    Parameters
    ----------
    front_matter
        The page's parsed front matter, empty when it has none.
    body
        The page source after the front matter.
    page_dir
        Directory holding the page.
    site_name
        The site's `website.title`.
    config
        Project configuration.
    default
        The site's default description as plain text.
    header_description
        The description the site's header includes declare, as a metadata value.

    Returns
    -------
    :
        `open-graph` and `twitter-card` entries that each hold a `title`, a
        `description` or both. A page whose own header includes declare Open
        Graph tags instead gets entries that switch the generated tags off.
        Empty when the page sets either card key itself or there is nothing to
        write.
    """
    if any(key in front_matter for key in PAGE_KEYS):
        return {}
    if head.page_includes_match(front_matter, page_dir, _OG_PROPERTY):
        # Quarto would add its tags beside the page's own and overwrite its `og:title`
        entries: dict[str, Any] = {OWN_CARDS_KEY: True}
        if "website" not in front_matter:
            entries["website"] = {"open-graph": False, "twitter-card": False}
        return entries

    card: dict[str, str] = {}
    if value := page_title(front_matter.string("title"), site_name, config):
        card["title"] = value
    # A page's own `description` reaches its card unaided; `description-meta` does not
    own = front_matter.string("description-meta")
    if own is not None:
        value = own
    elif header_description and "description" not in front_matter:
        value = header_description
    else:
        value = description.page_description(
            front_matter,
            body,
            default,
            citations=description.resolves_citations(front_matter, config),
        )
    if value:
        card["description"] = value
    return {"open-graph": card, "twitter-card": dict(card)} if card else {}


def add_to_raw_page(
    page: str,
    config: Config,
    *,
    site_name: str | None,
    default: str | None,
    url: str | None,
    image_url: str | None,
) -> str:
    """
    Add social card tags to a raw custom page

    The card takes the page's `<title>` and meta description, falling back to
    the site name and the default description.

    Parameters
    ----------
    page
        The page source.
    config
        Project configuration.
    site_name
        The site's name.
    default
        The site's default description as plain text.
    url
        The page's address, or `None` when the site has no base address.
    image_url
        The default card image address, or `None` for no image.

    Returns
    -------
    :
        The page with the tags added, or unchanged when social cards are
        disabled, the page has an `og:title` already, or it has no `<head>`.
    """
    if not config.social_cards_enabled:
        return page

    head_html = page.split("</head>", 1)[0]
    found = _TITLE.search(head_html)
    title = html.unescape(found.group(1)).strip() if found else ""
    found = _DESCRIPTION.search(head_html)
    summary = html.unescape(found.group(1)) if found else ""
    title = title or site_name or ""
    summary = summary or default or ""

    handle = config.social_cards_twitter_site
    open_graph = {
        "type": "website",
        "title": title,
        "description": summary,
        "url": url,
        "site_name": site_name,
        "image": image_url,
    }
    twitter = {
        "card": config.social_cards_twitter_card
        or ("summary_large_image" if image_url else "summary"),
        "title": title,
        "description": summary,
        "image": image_url,
        "site": twitter_handle(handle) if handle else None,
    }
    tags = [
        f'<meta property="og:{key}" content="{html.escape(value)}">'
        for key, value in open_graph.items()
        if value
    ]
    tags += [
        f'<meta name="twitter:{key}" content="{html.escape(value)}">'
        for key, value in twitter.items()
        if value
    ]
    return head.insert(page, "\n".join(tags), unless='property="og:title"')
