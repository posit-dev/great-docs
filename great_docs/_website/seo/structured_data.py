"""
JSON-LD package and page descriptions for search engines

The homepage and every reference page carry a Schema.org object describing the
package. Reference pages other than the reference index also carry a `WebPage`
object naming the page.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..._project.manifest import Manifest
from .. import head

if TYPE_CHECKING:
    from pathlib import Path

    from ...config import Config
    from ..page_metadata import Page

LICENSE_URLS: dict[str, str] = {
    # MIT variants
    "mit": "https://opensource.org/licenses/MIT",
    "mit license": "https://opensource.org/licenses/MIT",
    # Apache variants
    "apache-2.0": "https://opensource.org/licenses/Apache-2.0",
    "apache 2.0": "https://opensource.org/licenses/Apache-2.0",
    "apache license 2.0": "https://opensource.org/licenses/Apache-2.0",
    # GPL variants
    "gpl-3.0": "https://opensource.org/licenses/GPL-3.0",
    "gpl-3.0-only": "https://opensource.org/licenses/GPL-3.0",
    "gpl-3.0-or-later": "https://opensource.org/licenses/GPL-3.0",
    "gpl-2.0": "https://opensource.org/licenses/GPL-2.0",
    "gpl-2.0-only": "https://opensource.org/licenses/GPL-2.0",
    "lgpl-3.0": "https://opensource.org/licenses/LGPL-3.0",
    "lgpl-2.1": "https://opensource.org/licenses/LGPL-2.1",
    # BSD variants
    "bsd-3-clause": "https://opensource.org/licenses/BSD-3-Clause",
    "bsd-2-clause": "https://opensource.org/licenses/BSD-2-Clause",
    "bsd 3-clause": "https://opensource.org/licenses/BSD-3-Clause",
    "bsd 2-clause": "https://opensource.org/licenses/BSD-2-Clause",
    # ISC
    "isc": "https://opensource.org/licenses/ISC",
    # MPL
    "mpl-2.0": "https://opensource.org/licenses/MPL-2.0",
    # Unlicense
    "unlicense": "https://opensource.org/licenses/unlicense",
    # CC licences
    "cc0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "cc-by-sa-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}
"""Canonical licence URLs keyed by lower-case SPDX identifier or common name"""

_JSON_LD = re.compile(r"""type=["']?application/ld\+json""")

# Browsers end a script at `</script>` and do not decode HTML entities in
# its body. Use JSON escapes to preserve the text without closing the tag.
_SCRIPT_ESCAPES = str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})


def licence_url(value: str) -> str:
    """
    Resolve a licence identifier to its canonical URL

    Parameters
    ----------
    value
        A licence identifier, such as `MIT`, or a URL.

    Returns
    -------
    :
        A URL unchanged, the canonical URL of a known identifier matched
        case-insensitively, or `value` unchanged.
    """
    if value.startswith(("http://", "https://")):
        return value
    return LICENSE_URLS.get(value.lower().strip(), value)


@dataclass(frozen=True)
class StructuredData:
    """Package metadata shared by homepage and reference JSON-LD"""

    package: dict[str, Any]
    """The Schema.org object describing the package"""

    site_name: str
    """The site name, which `WebPage` objects use in their name"""

    base_url: str | None
    """The canonical site URL with a trailing slash, or `None` when unknown"""

    @classmethod
    def make(
        cls,
        config: Config,
        metadata: Manifest,
        site_name: str,
        base_url: str | None,
        *,
        repo_url: str | None,
    ) -> StructuredData | None:
        """
        Build the package description for search engines

        Parameters
        ----------
        config
            Project configuration, whose `seo.structured_data.type` is the
            Schema.org type of the package object.
        metadata
            Package metadata: `description` and `license`, either of
            which may be missing or empty.
        site_name
            The site name.
        base_url
            The canonical site URL with a trailing slash, or `None`.
        repo_url
            The selected repository URL, or `None` when unknown.

        Returns
        -------
        :
            The structured data, or `None` when it is disabled. Empty values
            are left out of the package object.
        """
        if not config.structured_data_enabled:
            return None
        site_url = base_url.rstrip("/") if base_url else None
        licence = metadata.get("license")
        optional_fields: dict[str, Any] = {
            "name": site_name,
            "description": metadata.get("description"),
            "codeRepository": repo_url,
            "license": licence_url(licence) if licence else None,
            "url": site_url,
            "documentation": site_url,
        }
        package: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": config.structured_data_type,
            **{key: value for key, value in optional_fields.items() if value},
            "programmingLanguage": {"@type": "ComputerLanguage", "name": "Python"},
        }
        return cls(package=package, site_name=site_name, base_url=base_url)

    def tag(self, page: Page) -> str | None:
        """
        Build the JSON-LD `<script>` element for a page that Quarto renders

        Parameters
        ----------
        page
            The page.

        Returns
        -------
        :
            The element as one line of HTML for the homepage and pages under
            `reference/`, or `None` for other pages and for pages that
            already supply JSON-LD.
        """
        if _has_own_json_ld(page):
            return None
        return self._element(page.output_path)

    def add_to_raw_page(self, html: str, output_path: str) -> str:
        """
        Add the JSON-LD `<script>` element to a raw custom page

        Parameters
        ----------
        html
            The page source.
        output_path
            The page relative to the site root, such as `reference/demo.html`.

        Returns
        -------
        :
            The page with the element added, or `html` unchanged when the
            page is neither the homepage nor under `reference/`, already
            contains JSON-LD, or has no `</head>`.
        """
        if (tag := self._element(output_path)) is None:
            return html
        return head.insert(html, tag, unless='type="application/ld+json"')

    def _element(self, output_path: str) -> str | None:
        """
        Build the JSON-LD `<script>` element for a page path

        Parameters
        ----------
        output_path
            The page relative to the site root.

        Returns
        -------
        :
            The element as one line of HTML for the homepage and pages under
            `reference/`, or `None` for other pages.
        """
        path = output_path
        if path != "index.html" and not path.startswith("reference/"):
            return None

        payload: dict[str, Any] | list[dict[str, Any]] = self.package
        if path.startswith("reference/") and path != "reference/index.html":
            web_page: dict[str, Any] = {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "name": f"{path.removeprefix('reference/').removesuffix('.html')} - {self.site_name}",
                "isPartOf": {"@type": "WebSite", "name": self.site_name},
            }
            if self.base_url:
                web_page["url"] = self.base_url + path
            payload = [self.package, web_page]

        body = json.dumps(payload, ensure_ascii=False).translate(_SCRIPT_ESCAPES)
        return f'<script type="application/ld+json">{body}</script>'

    @staticmethod
    def applies(quarto_config: dict[str, Any], project_dir: Path) -> bool:
        """
        Check whether the site header permits generated JSON-LD

        Parameters
        ----------
        quarto_config
            Contents of `_quarto.yml`.
        project_dir
            The Quarto project directory, the base for relative header file
            paths.

        Returns
        -------
        :
            `True` when the site's header includes contain no JSON-LD.
        """
        return not head.includes_match(quarto_config, project_dir, _JSON_LD)


def _has_own_json_ld(page: Page) -> bool:
    """
    Check whether a page already supplies JSON-LD

    Parameters
    ----------
    page
        The page.

    Returns
    -------
    :
        `True` when its source or its own header includes contain a JSON-LD
        `type` attribute. A code example that shows the attribute counts too.
    """
    return bool(_JSON_LD.search(page.content)) or head.page_includes_match(
        page.front_matter, page.path.parent, _JSON_LD
    )
