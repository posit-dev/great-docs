import glob
import html
import json
import os
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

# Print the working directory
print("Current working directory:", os.getcwd())

# Get a list of all files in the working directory
files = os.listdir(".")
print("Files in working directory:", files)

site_files = os.listdir("_site")
print("Files in '_site' directory:", site_files)

# Load source links if available
source_links = {}
source_links_path = "_source_links.json"
if os.path.exists(source_links_path):
    print(f"Loading source links from {source_links_path}")
    with open(source_links_path, "r", encoding="utf-8") as f:
        source_links = json.load(f)
    print(f"Loaded {len(source_links)} source links")
else:
    print("No source links file found, skipping source link injection")

# Load object type metadata for accurate classification
# Keys are object names (e.g., "parser.ParserError"), values are type strings
# ("class", "namedtuple", "typeddict", "protocol", "abc", "exception", "function", "method", "constant", "enum", "type_alias", "other")
object_types = {}
object_types_path = "_object_types.json"
if os.path.exists(object_types_path):
    print(f"Loading object types from {object_types_path}")
    with open(object_types_path, "r", encoding="utf-8") as f:
        object_types = json.load(f)
    print(f"Loaded {len(object_types)} object type entries")
else:
    print("No object types file found, falling back to heuristic classification")

# Load constant value metadata for displaying values on constant reference pages.
# Keys are constant names, values are dicts with optional "value" and "annotation".
constant_values: dict[str, dict[str, str]] = {}
constant_values_path = "_constant_values.json"
if os.path.exists(constant_values_path):
    with open(constant_values_path, "r", encoding="utf-8") as f:
        constant_values = json.load(f)
    print(f"Loaded {len(constant_values)} constant value entries")

# Load dataclass attributes metadata for fixing incomplete Attributes tables.
# Written by great-docs core during build step 1.7.
# Keys are fully qualified object paths (e.g., "pkg.Config"), values are
# dicts mapping field name -> description.
dataclass_attrs_metadata: dict[str, dict[str, str]] = {}
dataclass_attrs_path = "_dataclass_attrs.json"
if os.path.exists(dataclass_attrs_path):
    with open(dataclass_attrs_path, "r", encoding="utf-8") as f:
        dataclass_attrs_metadata = json.load(f)
    if dataclass_attrs_metadata:
        print(f"Loaded dataclass attribute metadata for {len(dataclass_attrs_metadata)} class(es)")

# Load great-docs options (written by core.py during build)
_gd_options: dict[str, object] = {}
_gd_options_path = "_gd_options.json"
if os.path.exists(_gd_options_path):
    with open(_gd_options_path, "r", encoding="utf-8") as f:
        _gd_options = json.load(f)

# i18n helper — look up a translated string from _gd_options["i18n"]
_i18n_bundle: dict[str, str] = _gd_options.get("i18n", {})


def _t(key: str, fallback: str | None = None) -> str:
    """Look up a translated string, falling back to English default."""
    return _i18n_bundle.get(key, fallback if fallback is not None else key)


# Load objects.json inventory for resolving interlinks
# Maps qualified names -> {uri, dispname} for cross-reference resolution
_interlinks_inventory: dict[str, dict[str, str]] = {}
_objects_json_path = "objects.json"
if os.path.exists(_objects_json_path):
    with open(_objects_json_path, "r", encoding="utf-8") as f:
        _inv_data = json.load(f)
    for item in _inv_data.get("items", []):
        name = item.get("name", "")
        if name:
            _interlinks_inventory[name] = {
                "uri": item.get("uri", ""),
                "dispname": item.get("dispname", "-"),
                "role": item.get("role", ""),
            }
    print(f"Loaded {len(_interlinks_inventory)} interlinks inventory entries")
else:
    print("No objects.json found, interlinks resolution disabled")


# ══════════════════════════════════════════════════════════════════════════════
# SEO PROCESSING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


def inject_canonical_url(html_content: str, page_path: str) -> str:
    """
    Inject a canonical URL link tag into the HTML head.

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root (e.g., "reference/MyClass.html").

    Returns
    -------
    str
        The modified HTML with canonical URL injected.
    """
    if not _gd_options.get("canonical_enabled", False):
        return html_content

    base_url = _gd_options.get("canonical_base_url")
    if not base_url:
        return html_content

    # Build the canonical URL
    if page_path == "index.html":
        canonical_url = base_url
    elif page_path.endswith("/index.html"):
        canonical_url = base_url + page_path[:-10]  # Remove /index.html
    else:
        canonical_url = base_url + page_path

    # Check if canonical already exists
    if 'rel="canonical"' in html_content:
        return html_content

    # Inject canonical link before </head>
    canonical_tag = f'<link rel="canonical" href="{canonical_url}">'
    html_content = html_content.replace("</head>", f"  {canonical_tag}\n</head>", 1)

    return html_content


def inject_meta_description(html_content: str, page_path: str) -> str:
    """
    Inject or update meta description tag in the HTML head.

    Extracts description from:
    1. Existing description meta tag (if present)
    2. First paragraph of content
    3. Default description from config

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root.

    Returns
    -------
    str
        The modified HTML with meta description.
    """
    if not _gd_options.get("seo_enabled", False):
        return html_content

    # Check if description meta already exists
    if re.search(r'<meta\s+name="description"', html_content):
        return html_content

    # Try to extract a description from the page content
    description = None

    # Look for the first paragraph in main content
    main_match = re.search(r"<main[^>]*>(.*?)</main>", html_content, re.DOTALL)
    if main_match:
        main_content = main_match.group(1)
        # Find the first paragraph that has actual text (not just whitespace or code)
        p_match = re.search(r"<p[^>]*>([^<]+(?:<(?!/?p)[^>]*>[^<]*)*)</p>", main_content)
        if p_match:
            desc_text = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
            if len(desc_text) > 30:  # Only use if meaningful
                # Truncate to ~155 chars for optimal SEO
                if len(desc_text) > 155:
                    desc_text = desc_text[:152].rsplit(" ", 1)[0] + "..."
                description = desc_text

    # Fall back to default description
    if not description:
        description = _gd_options.get("default_description", "")

    if not description:
        return html_content

    # Escape HTML entities in description
    description = (
        description.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    # Inject meta description before </head>
    meta_tag = f'<meta name="description" content="{description}">'
    html_content = html_content.replace("</head>", f"  {meta_tag}\n</head>", 1)

    return html_content


# Mapping of common license identifiers to their canonical URLs
# Uses SPDX identifiers (https://spdx.org/licenses/) as keys
LICENSE_URL_MAP = {
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
    # CC licenses
    "cc0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "cc-by-sa-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}


def _get_license_url(license_value: str) -> str:
    """
    Convert a license identifier to its canonical URL.

    If the value is already a URL, return it as-is.
    If it's a known license identifier, return the canonical URL.
    Otherwise, return the original value.
    """
    if not license_value:
        return ""

    # If it's already a URL, use it directly
    if license_value.startswith(("http://", "https://")):
        return license_value

    # Look up in the mapping (case-insensitive)
    normalized = license_value.lower().strip()
    if normalized in LICENSE_URL_MAP:
        return LICENSE_URL_MAP[normalized]

    # Fallback: return original value (better than nothing)
    return license_value


def inject_json_ld(html_content: str, page_path: str) -> str:
    """
    Inject JSON-LD structured data into the HTML head.

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root.

    Returns
    -------
    str
        The modified HTML with JSON-LD structured data.
    """
    if not _gd_options.get("structured_data_enabled", False):
        return html_content

    # Only inject on the homepage and reference pages
    if page_path != "index.html" and not page_path.startswith("reference/"):
        return html_content

    # Check if JSON-LD already exists
    if 'type="application/ld+json"' in html_content:
        return html_content

    schema_type = _gd_options.get("structured_data_type", "SoftwareSourceCode")
    package_name = _gd_options.get("package_name", "")
    package_description = _gd_options.get("package_description", "")
    package_license = _gd_options.get("package_license", "")
    repo_url = _gd_options.get("repo_url", "")
    site_name = _gd_options.get("site_name", "")
    base_url = _gd_options.get("canonical_base_url", "")

    # Build JSON-LD schema
    json_ld = {
        "@context": "https://schema.org",
        "@type": schema_type,
    }

    if site_name:
        json_ld["name"] = site_name
    if package_description:
        json_ld["description"] = package_description
    if repo_url:
        json_ld["codeRepository"] = repo_url
    if package_license:
        json_ld["license"] = _get_license_url(package_license)
    if base_url:
        json_ld["url"] = base_url.rstrip("/")

    # Add documentation URL
    if base_url:
        json_ld["documentation"] = base_url.rstrip("/")

    # Add programming language
    json_ld["programmingLanguage"] = {
        "@type": "ComputerLanguage",
        "name": "Python",
    }

    # For reference pages, add WebPage type as well
    if page_path.startswith("reference/") and page_path != "reference/index.html":
        # Extract the item name from the path
        item_name = page_path.replace("reference/", "").replace(".html", "")
        page_json_ld = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": f"{item_name} - {site_name}",
            "isPartOf": {"@type": "WebSite", "name": site_name},
        }
        if base_url:
            page_json_ld["url"] = base_url + page_path

        # Use an array with both schemas
        json_ld = [json_ld, page_json_ld]

    # Serialize to JSON
    import json as json_module

    json_str = json_module.dumps(json_ld, indent=2, ensure_ascii=False)

    # Inject JSON-LD script before </head>
    script_tag = f'<script type="application/ld+json">\n{json_str}\n</script>'
    html_content = html_content.replace("</head>", f"  {script_tag}\n</head>", 1)

    return html_content


def apply_title_template(html_content: str, page_path: str) -> str:
    """
    Apply page title template for better SEO.

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root.

    Returns
    -------
    str
        The modified HTML with templated title.
    """
    if not _gd_options.get("seo_enabled", False):
        return html_content

    template = _gd_options.get("title_template", "{page_title} | {site_name}")
    site_name = _gd_options.get("site_name", "")

    if not site_name or not template:
        return html_content

    # Extract current page title
    title_match = re.search(r"<title>([^<]*)</title>", html_content)
    if not title_match:
        return html_content

    current_title = title_match.group(1).strip()

    # Skip if already has a pipe (already templated)
    if " | " in current_title or " - " in current_title:
        # Check if it ends with site name already
        if current_title.endswith(site_name):
            return html_content

    # Build new title from template
    new_title = template.replace("{page_title}", current_title).replace("{site_name}", site_name)

    # Replace title tag
    html_content = html_content.replace(
        f"<title>{title_match.group(1)}</title>", f"<title>{new_title}</title>"
    )

    return html_content


def inject_noindex_meta(html_content: str, page_path: str) -> str:
    """
    Inject noindex/nofollow meta tags for internal or draft pages.

    Pages that should be noindexed:
    - Any page with `noindex: true` in frontmatter (processed earlier)
    - Skill pages (internal/machine-readable)

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root.

    Returns
    -------
    str
        The modified HTML with noindex meta if applicable.
    """
    if not _gd_options.get("seo_enabled", False):
        return html_content

    # Check if noindex meta already exists
    if 'name="robots"' in html_content:
        return html_content

    # Pages that should be noindexed by default
    noindex_paths = ["skills.html"]

    should_noindex = any(page_path == p or page_path.endswith("/" + p) for p in noindex_paths)

    if should_noindex:
        meta_tag = '<meta name="robots" content="noindex, nofollow">'
        html_content = html_content.replace("</head>", f"  {meta_tag}\n</head>", 1)

    return html_content


def inject_social_cards(html_content: str, page_path: str) -> str:
    """
    Inject Open Graph and Twitter/X Card meta tags for social media previews.

    Generates per-page `og:title`, `og:description`, `og:url`, and `og:image` tags (plus Twitter
    Card equivalents) so that links shared on LinkedIn, Discord, Slack, Bluesky, Mastodon, X, and
    other platforms show rich previews.

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root (e.g., "reference/MyClass.html").

    Returns
    -------
    str
        The modified HTML with social card meta tags.
    """
    if not _gd_options.get("social_cards_enabled", False):
        return html_content

    # Skip if OG tags already exist (e.g., user added manually)
    if 'property="og:title"' in html_content:
        return html_content

    site_name = _gd_options.get("site_name", "")
    base_url = _gd_options.get("canonical_base_url", "")
    default_description = _gd_options.get("default_description", "")
    image_url = _gd_options.get("social_cards_image")
    twitter_site = _gd_options.get("social_cards_twitter_site")
    twitter_card_override = _gd_options.get("social_cards_twitter_card")

    # ── Extract page title ────────────────────────────────────────────────
    page_title = site_name
    title_match = re.search(r"<title>([^<]*)</title>", html_content)
    if title_match:
        page_title = title_match.group(1).strip()

    # ── Extract page description ──────────────────────────────────────────
    description = ""

    # First try existing meta description
    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html_content)
    if desc_match:
        description = desc_match.group(1)

    # Fall back to first meaningful paragraph
    if not description:
        main_match = re.search(r"<main[^>]*>(.*?)</main>", html_content, re.DOTALL)
        if main_match:
            p_match = re.search(
                r"<p[^>]*>([^<]+(?:<(?!/?p)[^>]*>[^<]*)*)</p>",
                main_match.group(1),
            )
            if p_match:
                desc_text = re.sub(r"<[^>]+>", "", p_match.group(1)).strip()
                if len(desc_text) > 30:
                    if len(desc_text) > 200:
                        desc_text = desc_text[:197].rsplit(" ", 1)[0] + "..."
                    description = desc_text

    # Fall back to site-level default
    if not description:
        description = default_description

    # HTML-escape attribute values
    def _esc(val: str) -> str:
        return (
            val.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # ── Build page URL ────────────────────────────────────────────────────
    page_url = ""
    if base_url:
        if page_path == "index.html":
            page_url = base_url.rstrip("/")
        elif page_path.endswith("/index.html"):
            page_url = base_url + page_path[:-10]  # Remove /index.html
        else:
            page_url = base_url + page_path

    # ── Assemble meta tags ────────────────────────────────────────────────
    tags: list[str] = []

    # Open Graph (works on LinkedIn, Discord, Slack, Bluesky, Mastodon, etc.)
    tags.append('<meta property="og:type" content="website">')
    tags.append(f'<meta property="og:title" content="{_esc(page_title)}">')
    if description:
        tags.append(f'<meta property="og:description" content="{_esc(description)}">')
    if page_url:
        tags.append(f'<meta property="og:url" content="{_esc(page_url)}">')
    if site_name:
        tags.append(f'<meta property="og:site_name" content="{_esc(site_name)}">')
    if image_url:
        tags.append(f'<meta property="og:image" content="{_esc(image_url)}">')

    # Twitter/X Card
    if twitter_card_override:
        card_type = twitter_card_override
    else:
        card_type = "summary_large_image" if image_url else "summary"
    tags.append(f'<meta name="twitter:card" content="{card_type}">')
    tags.append(f'<meta name="twitter:title" content="{_esc(page_title)}">')
    if description:
        tags.append(f'<meta name="twitter:description" content="{_esc(description)}">')
    if image_url:
        tags.append(f'<meta name="twitter:image" content="{_esc(image_url)}">')
    if twitter_site:
        handle = twitter_site if twitter_site.startswith("@") else f"@{twitter_site}"
        tags.append(f'<meta name="twitter:site" content="{_esc(handle)}">')

    # Inject all tags before </head>
    tag_block = "\n  ".join(tags)
    html_content = html_content.replace("</head>", f"  {tag_block}\n</head>", 1)

    return html_content


def apply_seo_processing(html_content: str, page_path: str) -> str:
    """
    Apply all SEO processing to an HTML page.

    Parameters
    ----------
    html_content
        The HTML content to modify.
    page_path
        The page path relative to the site root (e.g., "reference/MyClass.html").

    Returns
    -------
    str
        The modified HTML with all SEO enhancements.
    """
    html_content = inject_canonical_url(html_content, page_path)
    html_content = inject_meta_description(html_content, page_path)
    html_content = inject_json_ld(html_content, page_path)
    html_content = apply_title_template(html_content, page_path)
    html_content = inject_noindex_meta(html_content, page_path)
    html_content = inject_social_cards(html_content, page_path)
    return html_content


def get_source_link_html(item_name):
    """Generate HTML for a source link given an item name."""
    if item_name in source_links:
        url = source_links[item_name]["url"]
        return f'<a href="{url}" class="source-link" target="_blank" rel="noopener">SOURCE</a>'
    return ""


# Roles that represent callable objects and should display with trailing "()"
_CALLABLE_ROLES = {"function", "method"}


def _resolve_interlink_name(name):
    """Resolve a qualified name to its inventory entry.

    Tries exact match first, then looks for suffix matches (e.g., `DuckDBStore` matches
    `raghilda.store.DuckDBStore`).

    Returns (uri, short_name, role) or `None` if not found.
    """
    # Exact match
    if name in _interlinks_inventory:
        entry = _interlinks_inventory[name]
        short = name.rsplit(".", 1)[-1]
        return entry["uri"], short, entry.get("role", "")

    # Suffix match: find the shortest qualified name that ends with the given name
    candidates = []
    for full_name, entry in _interlinks_inventory.items():
        if full_name == name or full_name.endswith(f".{name}"):
            candidates.append((full_name, entry))

    if candidates:
        # Prefer shortest match (most specific)
        candidates.sort(key=lambda x: len(x[0]))
        full_name, entry = candidates[0]
        short = name.rsplit(".", 1)[-1]
        return entry["uri"], short, entry.get("role", "")

    return None


def resolve_interlinks(html_content):
    """Resolve interlink references in rendered HTML.

    Quarto renders interlink syntax as `<a>` tags with backtick-wrapped hrefs:

    - ``[](`~pkg.Name`)``  -> shortened display (`Name`)
    - ``[](`pkg.Name`)``   -> full qualified display (`pkg.Name`)
    - ``[custom text](`pkg.Name`)`` -> custom display text preserved
    - ``[custom text](`~pkg.Name`)`` -> custom display text preserved

    This function resolves those links against the objects.json inventory.
    """
    if not _interlinks_inventory:
        return html_content

    # Single-pass: match <a> tags with backtick-wrapped interlink hrefs.
    # The href may or may not have a ~ prefix. Captures:
    #   (1) optional ~ prefix
    #   (2) the qualified name
    #   (3) everything between > and </a> (link text, possibly empty)
    def _replace_full_interlink(m):
        tilde = m.group(1)
        name = m.group(2)
        link_text = m.group(3)
        result = _resolve_interlink_name(name)
        if result is None:
            return m.group(0)
        uri, short_name, role = result
        # URIs from objects.json are root-relative (e.g. "reference/Name.html#...")
        # but reference pages live inside reference/, so strip the prefix
        # to get a sibling-relative path.
        if uri.startswith("reference/"):
            uri = uri[len("reference/") :]
        # Determine display text:
        # 1. Custom text provided by user → keep it
        # 2. ~ prefix (shortened) → use short name
        # 3. No ~ prefix (default) → use full qualified name
        text = link_text.strip()
        if not text or re.match(r"^`~?[\w.]+`$", text):
            text = short_name if tilde else name
            # Append () for callable objects (functions, methods)
            if role in _CALLABLE_ROLES:
                text += "()"
            css = "gdls-link gdls-code"
        else:
            css = "gdls-link"
        return f'<a href="{uri}" class="{css}">{text}</a>'

    html_content = re.sub(
        r'<a href="`(~?)([\w.]+)`">(.*?)</a>',
        _replace_full_interlink,
        html_content,
    )

    return html_content


def autolink_code_references(html_content):
    """Auto-convert inline code matching API names into clickable links.

    Scans `<code>` tags (outside `<pre>` blocks) for text that matches an entry in the objects.json
    inventory. Matching code is wrapped in an `<a>` link to the corresponding reference page.

    Supported patterns inside inline code:

    - `Name` or `Name()` — exact/suffix match, display as-is
    - `pkg.Name` or `pkg.Name()` — qualified match, display as-is
    - `~~pkg.Name` or `~~pkg.Name()` — shortened display (`Name`)
    - `~~.pkg.Name` or `~~.pkg.Name()` — dot-prefixed short (`·Name`)

    Code with the `gd-no-link` class is never autolinked. Code inside `<pre>` blocks (fenced code)
    is never autolinked. Code containing spaces, operators, or arguments is never autolinked.
    """
    if not _interlinks_inventory:
        return html_content

    # Step 1: protect <pre>...</pre> blocks by replacing them with placeholders
    pre_blocks = []

    def _save_pre(m):
        pre_blocks.append(m.group(0))
        return f"\x00PRE{len(pre_blocks) - 1}\x00"

    html_content = re.sub(r"<pre[\s>].*?</pre>", _save_pre, html_content, flags=re.DOTALL)

    # Step 2: match <code> tags that might be autolink candidates
    # Pattern: <code> text </code> where text is a valid identifier path,
    # optionally prefixed with ~~ or ~~. and optionally suffixed with ()
    def _autolink_code(m):
        full_tag = m.group(0)
        class_attr = m.group(1) or ""
        text = m.group(2)

        # Skip if gd-no-link class is present
        if "gd-no-link" in class_attr:
            return full_tag

        # Skip if already inside an <a> tag (check preceding context)
        # This is handled by the negative lookbehind in the regex

        # Parse the code text for autolink patterns
        code_match = re.match(
            r"^(~~\.?)?(\w[\w.]*?)(\(\))?$",
            text,
        )
        if not code_match:
            return full_tag

        prefix = code_match.group(1) or ""  # "", "~~", or "~~."
        name = code_match.group(2)
        parens = code_match.group(3) or ""  # "" or "()"

        # Try to resolve the name
        result = _resolve_interlink_name(name)
        if result is None:
            # If unresolved but has ~~ prefix, strip it for display
            if prefix:
                if prefix == "~~.":
                    display = f".{name.rsplit('.', 1)[-1]}{parens}"
                else:
                    display = f"{name.rsplit('.', 1)[-1]}{parens}"
                return f"<code{class_attr}>{display}</code>"
            return full_tag

        uri, short_name, _role = result
        if uri.startswith("reference/"):
            uri = uri[len("reference/") :]

        # Determine display text based on prefix
        if prefix == "~~.":
            display = f".{short_name}{parens}"
        elif prefix == "~~":
            display = f"{short_name}{parens}"
        else:
            display = f"{name}{parens}"

        return f'<a href="{uri}" class="gdls-link gdls-code">{display}</a>'

    # Match <code> tags. We check if they're inside <a> tags during replacement.
    # Captures: (1) optional class attribute, (2) inner text
    def _autolink_code_with_context(m):
        # Skip if this <code> is inside an <a> tag
        start = m.start()
        preceding = html_content[max(0, start - 200) : start]
        # Check if there's an unclosed <a> tag before this <code>
        last_a_open = preceding.rfind("<a ")
        last_a_close = preceding.rfind("</a>")
        if last_a_open > last_a_close:
            return m.group(0)
        return _autolink_code(m)

    html_content = re.sub(
        r"<code(\s[^>]*)?>([^<]+)</code>",
        _autolink_code_with_context,
        html_content,
    )

    # Step 3: restore <pre> blocks
    for i, block in enumerate(pre_blocks):
        html_content = html_content.replace(f"\x00PRE{i}\x00", block)

    return html_content


# Pygments class to Quarto class mapping
# Quarto uses different class names than Pygments default
PYGMENTS_TO_QUARTO_CLASS = {
    "n": "va",  # Name -> variable (generic names)
    "nc": "fu",  # Name.Class -> function (we want class names highlighted)
    "nf": "fu",  # Name.Function -> function
    "fm": "fu",  # Name.Function.Magic -> function
    "nb": "bu",  # Name.Builtin -> builtin
    "bp": "bu",  # Name.Builtin.Pseudo -> builtin
    "k": "kw",  # Keyword -> keyword
    "kc": "cn",  # Keyword.Constant -> constant (None, True, False) - will be split further
    "kd": "kw",  # Keyword.Declaration -> keyword
    "kn": "kw",  # Keyword.Namespace -> keyword
    "kr": "kw",  # Keyword.Reserved -> keyword
    "o": "op",  # Operator -> operator
    "ow": "op",  # Operator.Word -> operator
    "p": "",  # Punctuation -> no special class
    "s": "st",  # String -> string
    "s1": "st",  # String.Single -> string
    "s2": "st",  # String.Double -> string
    "mi": "dv",  # Number.Integer -> decimal value
    "mf": "fl",  # Number.Float -> float
    "c": "co",  # Comment -> comment
    "c1": "co",  # Comment.Single -> comment
}


def highlight_signature_with_pygments(html_content):
    """
    Re-highlight the main signature block (cb1) with Pygments for better syntax coloring.

    This extracts the signature code, highlights it with Pygments, then maps the Pygments CSS
    classes to Quarto's highlighting classes for consistency.
    """
    # Find the main signature code block (id="cb1")
    cb1_pattern = re.compile(
        r'(<div class="sourceCode" id="cb1">.*?<code class="sourceCode python">)'
        r"(.*?)"
        r"(</code>.*?</div>)",
        re.DOTALL,
    )

    def replace_signature(match):
        prefix = match.group(1)
        code_content = match.group(2)
        suffix = match.group(3)

        # Extract plain text from the HTML spans
        # Remove HTML tags but preserve the text content
        plain_code = re.sub(r"<[^>]+>", "", code_content)
        # Clean up the text (unescape HTML entities)
        plain_code = plain_code.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

        # Highlight with Pygments
        lexer = PythonLexer()
        # Use a custom formatter that generates short class names
        formatter = HtmlFormatter(nowrap=True, classprefix="")

        highlighted = highlight(plain_code, lexer, formatter)

        # Map Pygments classes to Quarto classes
        for pg_class, quarto_class in PYGMENTS_TO_QUARTO_CLASS.items():
            if quarto_class:
                highlighted = highlighted.replace(f'class="{pg_class}"', f'class="{quarto_class}"')
            else:
                # Remove empty class attributes
                highlighted = re.sub(
                    rf'<span class="{pg_class}">([^<]*)</span>', r"\1", highlighted
                )

        # Special handling: make method/function name stand out on every signature line
        # Pattern: ClassName.method_name( or function_name(
        # Replace the name before ( with a function class for better highlighting
        # Uses re.MULTILINE so ^ matches each line (important for @overload signatures)
        sig_name_pattern = re.compile(
            r'^(<span class="va">)(\w+)(</span>)(<span class="op">\.</span>)?'
            r'(<span class="va">)?(\w+)?(</span>)?(\()',
            re.MULTILINE,
        )

        def enhance_sig_name(m):
            # If there's a dot, it's ClassName.method_name
            if m.group(4):  # Has dot
                class_name = m.group(2)
                method_name = m.group(6) or ""
                return (
                    f'<span class="sig-class">{class_name}</span>'
                    f'<span class="op">.</span>'
                    f'<span class="sig-name">{method_name}</span>('
                )
            else:
                # Just function_name(
                func_name = m.group(2)
                return f'<span class="sig-name">{func_name}</span>('

        highlighted = sig_name_pattern.sub(enhance_sig_name, highlighted)

        # Differentiate None from True/False
        # None gets 'cn-none' class, True/False get 'cn-bool' class
        highlighted = highlighted.replace(
            '<span class="cn">None</span>', '<span class="cn-none">None</span>'
        )
        highlighted = highlighted.replace(
            '<span class="cn">True</span>', '<span class="cn-bool">True</span>'
        )
        highlighted = highlighted.replace(
            '<span class="cn">False</span>', '<span class="cn-bool">False</span>'
        )

        # Convert single quotes to double quotes in string literals
        # Pygments outputs HTML entities: &#39; for single quote
        # Match both s1 (string single) and st (after class mapping) classes
        highlighted = re.sub(
            r'<span class="(st|s1)">&#39;([^&]*)&#39;</span>',
            r'<span class="\1">&quot;\2&quot;</span>',
            highlighted,
        )

        # Wrap each line in a span with proper id for line linking
        # For overloaded functions (multiple signature lines), insert a blank spacer
        # span between each signature for visual separation.
        lines = highlighted.split("\n")
        # Filter out empty trailing lines
        while lines and not lines[-1].strip():
            lines.pop()
        is_overloaded = len(lines) > 1 and all(line.strip() == "" or "(" in line for line in lines)
        wrapped_lines = []
        line_num = 1
        for idx, line in enumerate(lines):
            if not line and not is_overloaded:
                continue  # Skip empty lines for non-overloaded functions
            if not line:
                continue  # Skip blank lines; we insert spacers ourselves
            wrapped_lines.append(
                f'<span id="cb1-{line_num}"><a href="#cb1-{line_num}" aria-hidden="true" tabindex="-1"></a>{line}</span>'
            )
            line_num += 1
            # Add a blank spacer line between overload signatures (not after the last)
            if is_overloaded and idx < len(lines) - 1:
                wrapped_lines.append(f'<span id="cb1-{line_num}" class="overload-spacer"> </span>')
                line_num += 1

        new_code = "\n".join(wrapped_lines)

        return f"{prefix}{new_code}{suffix}"

    return cb1_pattern.sub(replace_signature, html_content)


def format_signature_multiline(html_content):
    """
    Format function/method signatures with multiple arguments onto separate lines.

    If a signature has more than one argument, format it as:
        FunctionName(
            arg1=default1,
            arg2=default2,
        )

    Signatures that are already multiline are skipped.
    """
    # Pattern to match the content inside signature spans
    # The signature is inside <span id="cbN-1">...(args)</span>
    # We need to handle HTML tags within the arguments

    def reformat_signature(match):
        full_match = match.group(0)
        span_start = match.group(1)
        anchor = match.group(2) or ""
        content = match.group(3)
        span_end = match.group(4)

        # Skip if signature is already multiline; this is detected by checking if content ends with
        # just "(" or has a newline
        if content.strip().endswith("(") or "\n" in content:
            return full_match

        # Find the opening paren position
        paren_pos = content.find("(")
        if paren_pos == -1:
            return full_match

        func_name = content[: paren_pos + 1]  # Include the (

        # Find the closing paren - it's the last ) in the content
        close_paren_pos = content.rfind(")")
        if close_paren_pos == -1:
            return full_match

        args_content = content[paren_pos + 1 : close_paren_pos]

        # Count arguments by looking for commas not inside HTML tags or nested parens
        # We need to track both HTML tag depth and paren depth
        arg_count = 1 if args_content.strip() else 0
        html_depth = 0
        paren_depth = 0
        i = 0
        while i < len(args_content):
            if args_content[i : i + 1] == "<":
                html_depth += 1
            elif args_content[i : i + 1] == ">":
                html_depth -= 1
            elif html_depth == 0:
                if args_content[i] in "([{":
                    paren_depth += 1
                elif args_content[i] in ")]}":
                    paren_depth -= 1
                elif args_content[i] == "," and paren_depth == 0:
                    arg_count += 1
            i += 1

        # Only reformat if more than 1 argument
        if arg_count <= 1:
            return full_match

        # Split arguments while preserving HTML
        args = []
        current_arg = ""
        html_depth = 0
        paren_depth = 0
        i = 0
        while i < len(args_content):
            char = args_content[i]
            if char == "<":
                html_depth += 1
                current_arg += char
            elif char == ">":
                html_depth -= 1
                current_arg += char
            elif html_depth == 0:
                if char in "([{":
                    paren_depth += 1
                    current_arg += char
                elif char in ")]}":
                    paren_depth -= 1
                    current_arg += char
                elif char == "," and paren_depth == 0:
                    args.append(current_arg.strip())
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char
            i += 1
        if current_arg.strip():
            args.append(current_arg.strip())

        # Build multi-line signature
        formatted_args = ",\n    ".join(args)
        new_content = f"{func_name}\n    {formatted_args},\n)"

        return f"{span_start}{anchor}{new_content}{span_end}"

    # Only match the FIRST code block (cb1) which is always the main signature
    # Other code blocks (cb2, cb3, etc.) are method signatures or examples
    signature_pattern = re.compile(
        r'(<span id="cb1-1"[^>]*>)'
        r"(<a[^>]*></a>)?"
        r"(.*?\))"
        r"(</span>)",
        re.DOTALL,
    )

    return signature_pattern.sub(reformat_signature, html_content)


def strip_directives_from_html(html_content):
    """
    Remove Great Docs %directive lines from rendered HTML.

    Directives like %seealso and %nodoc are used for organizing documentation but they should not
    appear in the final rendered output. This function removes them after rendering.
    """
    # Match directives wrapped in <p> tags
    # e.g., <p>%seealso func_a, func_b</p>
    p_directive_pattern = re.compile(
        r"<p>\s*%(?:seealso|nodoc)(?:\s+[^<]*)?\s*</p>\s*\n?",
        re.IGNORECASE,
    )

    # Match standalone directive lines (plain text)
    # e.g., %seealso func_a
    standalone_directive_pattern = re.compile(
        r"^\s*%(?:seealso|nodoc)(?:\s+.*)?\s*$\n?",
        re.MULTILINE | re.IGNORECASE,
    )

    # Match directives that might be inline within text
    inline_directive_pattern = re.compile(
        r"%(?:seealso|nodoc)(?:\s+[^\n<]*)?",
        re.IGNORECASE,
    )

    # Apply patterns in order of specificity
    cleaned = p_directive_pattern.sub("", html_content)
    cleaned = standalone_directive_pattern.sub("", cleaned)
    cleaned = inline_directive_pattern.sub("", cleaned)

    # Clean up any resulting empty paragraphs
    cleaned = re.sub(r"<p>\s*</p>\s*\n?", "", cleaned)

    return cleaned


def strip_colgroup_tags(html_content):
    """
    Remove `<colgroup>` tags from tables, preserving those inside GT tables.

    Quarto/Pandoc adds `<colgroup>` with fixed column widths, but we want the browser to determine
    column widths based on content. GT tables (Great Tables) rely on their `<colgroup>` for proper
    layout with `table-layout: fixed`, so those are left intact.
    """
    # Match the entire colgroup element including its contents
    colgroup_pattern = re.compile(
        r"<colgroup>.*?</colgroup>\s*",
        re.DOTALL,
    )

    def _replace_if_not_gt(match):
        # Find the nearest preceding <table tag to check if it's a GT table
        preceding = html_content[: match.start()]
        last_table = preceding.rfind("<table")
        if last_table >= 0:
            table_end = preceding.find(">", last_table)
            if table_end >= 0:
                table_tag = preceding[last_table : table_end + 1]
                if "gt_table" in table_tag:
                    return match.group(0)  # Preserve GT table colgroups
        return ""  # Strip non-GT colgroups

    return colgroup_pattern.sub(_replace_if_not_gt, html_content)


def translate_sphinx_fields(html_content):
    """
    Convert Sphinx field-list directives into structured doc sections.

    After rendering, Sphinx-style docstrings with `:param:`, `:type:`, `:returns:`, `:rtype:`, and
    `:raises:` fields end up mashed into a single `<p>` tag:

    ```html
    <p>:param x: Desc. :type x: int :returns: Desc. :rtype: str :raises ValueError: Desc.</p>
    ```

    This function parses those fields and emits the same `<section>` / `<dl>` / `<dt>` / `<dd>`
    structure that the renderer produces for NumPy-style Parameters / Returns / Raises sections.
    """

    # Regex for a <p> tag whose text contains Sphinx field markers.
    # Allow inline HTML (e.g. <code>...</code>) inside the field text, but
    # prevent matching across paragraph boundaries by refusing </p> in the body.
    _FIELD_P = re.compile(
        r"<p>((?:(?!</p>).)*?:(?:param|type|returns?|rtype|raises?)(?:(?!</p>).)*)</p>",
        re.DOTALL,
    )

    # Individual field markers within the text.
    # The body captures everything up to the next field marker or end of string,
    # including inline HTML tags like <code>.
    _FIELD_TOKEN = re.compile(
        r":(?P<directive>param|type|returns?|rtype|raises?)"
        r"(?:\s+(?P<name>[^:]*?))?:\s*(?P<body>(?:(?!:(?:param|type|returns?|rtype|raises?)\b).)*)",
        re.DOTALL,
    )

    def _build_sections(m):
        text = m.group(1)
        fields = list(_FIELD_TOKEN.finditer(text))

        if not fields:
            return m.group(0)

        # Collect structured data
        params = {}  # name -> {"desc": ..., "type": ...}
        returns = {}  # key -> {"desc": ..., "type": ...}
        raises = []  # [(exception, desc), ...]

        ret_idx = 0
        for field in fields:
            directive = field.group("directive")
            name = (field.group("name") or "").strip()
            body = (field.group("body") or "").strip()

            if directive == "param":
                params.setdefault(name, {"desc": "", "type": ""})
                params[name]["desc"] = body
            elif directive == "type":
                params.setdefault(name, {"desc": "", "type": ""})
                params[name]["type"] = body
            elif directive in ("returns", "return"):
                key = f"_ret_{ret_idx}"
                returns[key] = {"desc": body, "type": ""}
                ret_idx += 1
            elif directive == "rtype":
                # Assign to the last return entry, or create one
                if returns:
                    last_key = list(returns.keys())[-1]
                    returns[last_key]["type"] = body
                else:
                    returns["_ret_0"] = {"desc": "", "type": body}
            elif directive in ("raises", "raise"):
                raises.append((name, body))

        parts = []

        # ── Parameters section ───────────────────────────────────────────
        if params:
            items = []
            for pname, pinfo in params.items():
                ptype = pinfo["type"]
                pdesc = pinfo["desc"]
                if ptype:
                    dt = (
                        f'<dt><code><span class="parameter-name">'
                        f"<strong>{pname}</strong></span> "
                        f'<span class="parameter-annotation-sep">:</span> '
                        f'<span class="parameter-annotation">{ptype}</span>'
                        f"</code></dt>"
                    )
                else:
                    dt = (
                        f'<dt><code><span class="parameter-name">'
                        f"<strong>{pname}</strong></span></code></dt>"
                    )
                dd = f"<dd>\n<p>{pdesc}</p>\n</dd>" if pdesc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="parameters" class="level1 doc-section doc-section-parameters">\n'
                f'<h1 class="doc-section doc-section-parameters">{_t("parameters", "Parameters")}</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Returns section ──────────────────────────────────────────────
        if returns:
            items = []
            for _key, rinfo in returns.items():
                rtype = rinfo["type"]
                rdesc = rinfo["desc"]
                if rtype:
                    dt = (
                        f'<dt><code><span class="parameter-name"></span> '
                        f'<span class="parameter-annotation-sep" '
                        f'style="margin-left: -8px;"></span> '
                        f'<span class="parameter-annotation">{rtype}</span>'
                        f"</code></dt>"
                    )
                else:
                    dt = "<dt></dt>"
                dd = f"<dd>\n<p>{rdesc}</p>\n</dd>" if rdesc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="returns" class="level1 doc-section doc-section-returns">\n'
                f'<h1 class="doc-section doc-section-returns">{_t("returns", "Returns")}</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Raises section ───────────────────────────────────────────────
        if raises:
            items = []
            for exc, desc in raises:
                dt = f'<dt><code><span class="parameter-annotation">{exc}</span></code></dt>'
                dd = f"<dd>\n<p>{desc}</p>\n</dd>" if desc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="raises" class="level1 doc-section doc-section-raises">\n'
                f'<h1 class="doc-section doc-section-raises">{_t("raises", "Raises")}</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        return "\n".join(parts)

    html_content = _FIELD_P.sub(_build_sections, html_content)
    return html_content


def translate_google_fields(html_content):
    """
    Convert Google-style docstring sections into structured doc sections.

    After rendering, Google-style docstrings with sections like `Args:`, `Returns:`, `Raises:`,
    `Note:`, `Example:`, `Warning:`, `References:`, and `See Also:` end up as flat `<p>` tags:

        <p>Args: items: desc. strict: desc.</p>
        <p>Returns: A dict...</p><pre><code>details</code></pre>
        <p>Raises: ValueError: desc. TypeError: desc.</p>
        <p>Note: text</p>

    Indented continuation text renders as `<pre><code>` blocks adjacent to the section `<p>`.  This
    function detects both patterns and emits the same `<section>`/`<h1>`/`<dl>`/`<dt>`/`<dd>` markup
    that the renderer produces for NumPy-style sections.
    """

    _PARAM_SECTIONS = {"Args", "Arguments", "Parameters", "Params"}
    _RETURN_SECTIONS = {"Returns", "Return"}
    _RAISE_SECTIONS = {"Raises", "Raise"}
    _SECTION_MAP = {
        "Note": "notes",
        "Notes": "notes",
        "Example": "examples",
        "Examples": "examples",
        "Warning": "warnings",
        "Warnings": "warnings",
        "References": "references",
        "See Also": "see-also",
    }

    ALL_SECTIONS = _PARAM_SECTIONS | _RETURN_SECTIONS | _RAISE_SECTIONS | set(_SECTION_MAP)
    # Sort longest-first so "See Also" matches before "See"
    section_names = "|".join(re.escape(s) for s in sorted(ALL_SECTIONS, key=len, reverse=True))

    # Match <p>SectionName: body</p>, optionally followed by <pre><code>…</code></pre>
    _GOOGLE_P = re.compile(
        rf"<p>(?P<section>{section_names}):\s*(?P<body>(?:(?!</p>).)*)</p>"
        r"(?:\s*<pre><code>(?P<pre_body>.*?)</code></pre>)?",
        re.DOTALL,
    )

    # ── helpers ──────────────────────────────────────────────────────────

    def _dbl_bt(text):
        """Convert ``word`` → <code>word</code>."""
        return re.sub(r"``(.*?)``", r"<code>\1</code>", text)

    def _pre_to_html(pre_text):
        """Convert <pre> block text (bullet lists + backticks) to HTML."""
        lines = pre_text.split("\n")
        out, in_list = [], False
        for line in lines:
            line = _dbl_bt(line)
            stripped = line.strip()
            if stripped.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if stripped:
                    out.append(f"<p>{stripped}</p>")
        if in_list:
            out.append("</ul>")
        return "\n".join(out)

    def _parse_params(body):
        """Parse 'name: desc. name2: desc2.' into [(name, desc), …]."""
        hits = list(re.finditer(r"(?:^|(?<=\.\s))([a-z_]\w*)\s*:\s*", body))
        if not hits:
            return []
        params = []
        for i, hit in enumerate(hits):
            name = hit.group(1)
            start = hit.end()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
            desc = body[start:end].strip()
            params.append((name, desc))
        return params

    def _parse_raises(body):
        """Parse 'ExcType: desc. ExcType2: desc2.' into [(exc, desc), …]."""
        hits = list(re.finditer(r"(?:^|(?<=\.\s))([A-Z][a-zA-Z]+)\s*:\s*", body))
        if not hits:
            return []
        raises = []
        for i, hit in enumerate(hits):
            exc = hit.group(1)
            start = hit.end()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
            desc = body[start:end].strip()
            raises.append((exc, desc))
        return raises

    # ── main replacer ────────────────────────────────────────────────────

    def _replace(m):
        section = m.group("section")
        body = (m.group("body") or "").strip()
        pre_body = m.group("pre_body").strip() if m.group("pre_body") else None

        # ── Args / Parameters ─────────────────────────────────────────
        if section in _PARAM_SECTIONS:
            full = f"{body} {pre_body}" if pre_body and body else (body or pre_body or "")
            params = _parse_params(full)
            if not params:
                return m.group(0)
            items = []
            for pname, pdesc in params:
                pdesc = _dbl_bt(pdesc)
                dt = (
                    f'<dt><code><span class="parameter-name">'
                    f"<strong>{pname}</strong></span></code></dt>"
                )
                dd = f"<dd>\n<p>{pdesc}</p>\n</dd>" if pdesc else "<dd></dd>"
                items.append(f"{dt}\n{dd}")
            return (
                '<section id="parameters" class="level1 doc-section doc-section-parameters">\n'
                f'<h1 class="doc-section doc-section-parameters">{_t("parameters", "Parameters")}</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Returns ───────────────────────────────────────────────────
        if section in _RETURN_SECTIONS:
            parts = []
            if body:
                parts.append(f"<p>{_dbl_bt(body)}</p>")
            if pre_body:
                parts.append(_pre_to_html(pre_body))
            content = "\n".join(parts)
            return (
                '<section id="returns" class="level1 doc-section doc-section-returns">\n'
                f'<h1 class="doc-section doc-section-returns">{_t("returns", "Returns")}</h1>\n'
                f"{content}\n</section>"
            )

        # ── Raises ────────────────────────────────────────────────────
        if section in _RAISE_SECTIONS:
            full = f"{body} {pre_body}" if pre_body and body else (body or pre_body or "")
            raises = _parse_raises(full)
            if not raises:
                return m.group(0)
            items = []
            for exc, desc in raises:
                desc = _dbl_bt(desc)
                dt = f'<dt><code><span class="parameter-annotation">{exc}</span></code></dt>'
                dd = f"<dd>\n<p>{desc}</p>\n</dd>" if desc else "<dd></dd>"
                items.append(f"{dt}\n{dd}")
            return (
                '<section id="raises" class="level1 doc-section doc-section-raises">\n'
                f'<h1 class="doc-section doc-section-raises">{_t("raises", "Raises")}</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Example / Examples (code blocks) ──────────────────────────
        if section in {"Example", "Examples"}:
            code_parts = []
            if body:
                code_parts.append(body)
            if pre_body:
                code_parts.append(pre_body)
            code = "\n".join(code_parts)
            return (
                '<section id="examples" class="level1 doc-section doc-section-examples">\n'
                f'<h1 class="doc-section doc-section-examples">{_t("examples", "Examples")}</h1>\n'
                f"<pre><code>{code}</code></pre>\n</section>"
            )

        # ── Other sections (Note, Warning, References, See Also) ─────
        # Map English section names to i18n keys
        _section_i18n_key = {
            "Note": "notes",
            "Notes": "notes",
            "Warning": "warnings_section",
            "Warnings": "warnings_section",
            "References": "references_section",
            "See Also": "see_also",
        }
        slug = _SECTION_MAP.get(section, section.lower().replace(" ", "-"))
        i18n_key = _section_i18n_key.get(section)
        display = _t(i18n_key, section) if i18n_key else section
        full = body
        if pre_body:
            full = f"{body}\n{pre_body}" if body else pre_body
        full = _dbl_bt(full)
        content = f"<p>{full}</p>" if full else ""
        return (
            f'<section id="{slug}" class="level1 doc-section doc-section-{slug}">\n'
            f'<h1 class="doc-section doc-section-{slug}">{display}</h1>\n'
            f"{content}\n</section>"
        )

    html_content = _GOOGLE_P.sub(_replace, html_content)
    return html_content


def translate_sphinx_roles(html_content):
    """
    Convert Sphinx cross-reference roles into clean HTML.

    The renderer sometimes passes through Sphinx-style roles verbatim.  The most
    common rendered patterns are:

    * `:py:exc:<code>ValueError</code>` ->  `<code>ValueError</code>`
    * `:class:<code>Foo</code>`         ->  `<code>Foo</code>`
    * `:func:<code>bar</code>`          ->  `<code>bar()</code>`
    * `:func:`bar```  (inside `<pre>`)  ->  `<code>bar()</code>`

    For *function* and *method* roles the name gets trailing `()` so the reader can tell it is
    callable.
    """

    _CALLABLE_ROLES = {"func", "meth"}

    # Pattern 1 – role prefix followed by <code>…</code>
    # e.g.  :py:class:<code>datetime.datetime</code>
    #       :func:<code>get_object</code>
    def _replace_code_role(m):
        role = m.group("role")
        inner = m.group("inner")
        if role in _CALLABLE_ROLES and not inner.endswith("()"):
            inner += "()"
        return f"<code>{inner}</code>"

    html_content = re.sub(
        r":(?:py:)?(?P<role>exc|class|func|meth|attr|const|mod|obj|data|type):"
        r"<code>(?P<inner>[^<]+)</code>",
        _replace_code_role,
        html_content,
    )

    # Pattern 2 – role with backtick-delimited text (inside <pre><code> blocks
    # or other contexts where markdown didn't convert backticks to <code>)
    # e.g.  :func:`get_zonefile_instance`
    def _replace_backtick_role(m):
        role = m.group("role")
        inner = m.group("inner")
        if role in _CALLABLE_ROLES and not inner.endswith("()"):
            inner += "()"
        return f"<code>{inner}</code>"

    html_content = re.sub(
        r":(?:py:)?(?P<role>exc|class|func|meth|attr|const|mod|obj|data|type):"
        r"`(?P<inner>[^`]+)`",
        _replace_backtick_role,
        html_content,
    )

    return html_content


def translate_rst_directives(html_content):
    """
    Convert RST admonition / version directives into styled HTML callouts.

    Handles directives that appear as literal text in `<p>` tags after rendering, for example:

    * `<p>.. versionadded:: 2.8.1</p>`
    * `<p>.. deprecated:: 2.6 Use X instead.</p>`
    * `<p>.. note:: Some important note.</p>`
    * `<p>.. warning:: Be careful.</p>`

    Each directive type gets a distinct icon, colour and label.
    """

    _DIRECTIVE_STYLES = {
        # (icon, bg_color, border_color, i18n_key, english_fallback)
        "versionadded": ("🆕", "#ECFDF5", "#059669", "added_in_version", "Added in version"),
        "versionchanged": ("🔄", "#EFF6FF", "#3B82F6", "changed_in_version", "Changed in version"),
        "deprecated": (
            "⚠️",
            "#FEF2F2",
            "#DC2626",
            "deprecated_since_version",
            "Deprecated since version",
        ),
        "note": ("ℹ️", "#EFF6FF", "#3B82F6", "note_callout", "Note"),
        "warning": ("⚠️", "#FFFBEB", "#D97706", "warning_callout", "Warning"),
        "caution": ("⚠️", "#FFFBEB", "#D97706", "caution_callout", "Caution"),
        "danger": ("🚨", "#FEF2F2", "#DC2626", "danger_callout", "Danger"),
        "important": ("❗", "#FFF7ED", "#EA580C", "important_callout", "Important"),
        "tip": ("💡", "#ECFDF5", "#059669", "tip_callout", "Tip"),
        "hint": ("💡", "#ECFDF5", "#059669", "hint_callout", "Hint"),
    }

    # Version directives have the version number right after ::
    # e.g.  .. versionadded:: 2.8.1
    #       .. deprecated:: 2.6 Use X instead.
    _VERSION_DIRECTIVES = {"versionadded", "versionchanged", "deprecated"}

    directive_names = "|".join(_DIRECTIVE_STYLES.keys())

    def _replace_directive(m):
        directive = m.group("directive")
        body = (m.group("body") or "").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, i18n_key, fallback = style
        label = _t(i18n_key, fallback)

        if directive in _VERSION_DIRECTIVES:
            # Split version number from optional description
            parts = body.split(None, 1) if body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            if "{v}" in label and version:
                title = label.replace("{v}", version)
            elif version:
                title = f"{label} {version}"
            else:
                title = label.replace(" {v}", "").replace("{v}", "")
            content = desc
        else:
            title = label
            content = body

        # Build the callout HTML
        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    # Pattern 1 – directive <p> followed by a <pre><code> block body.
    # RST block directives like ``.. note::`` with indented body text
    # become: <p>.. note::</p>\n<pre><code>body text</code></pre>
    def _replace_block_directive(m):
        directive = m.group("directive")
        pre_body = m.group("pre_body").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, i18n_key, fallback = style
        label = _t(i18n_key, fallback)

        if directive in _VERSION_DIRECTIVES:
            parts = pre_body.split(None, 1) if pre_body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            title = f"{label} {version}" if version else label
            content = desc
        else:
            title = label
            content = pre_body

        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    html_content = re.sub(
        rf"<p>\s*\.\.\s+(?P<directive>{directive_names})::\s*</p>"
        r"\s*<pre><code>(?P<pre_body>.*?)</code></pre>",
        _replace_block_directive,
        html_content,
        flags=re.DOTALL,
    )

    # Pattern 2 – directive with inline body text in the same <p> tag.
    # e.g. <p>.. versionadded:: 2.8.1</p>
    # The body may contain inline HTML tags (e.g. <code>...</code>) produced
    # by the Sphinx-role translation step that runs before this function.
    html_content = re.sub(
        rf"<p>\s*\.\.\s+(?P<directive>{directive_names})::\s*(?P<body>.*?)\s*</p>",
        _replace_directive,
        html_content,
    )

    # Pattern 3 – directive misinterpreted as a return-type annotation in a
    # <dt>/<dd> pair.  the renderer's numpy parser sometimes treats directives
    # like ``.. versionadded:: 2.0`` at the end of a docstring as an extra
    # return entry, producing:
    #   <dt><code>...<span class="parameter-annotation">.. versionadded:: 2.0
    #   </span></code></dt>
    #   <dd><p>Optional description.</p></dd>
    def _replace_dt_directive(m):
        directive = m.group("directive")
        body = (m.group("body") or "").strip()
        dd_body = (m.group("dd_body") or "").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, i18n_key, fallback = style
        label = _t(i18n_key, fallback)

        if directive in _VERSION_DIRECTIVES:
            parts = body.split(None, 1) if body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            if dd_body and not desc:
                desc = dd_body
            elif dd_body:
                desc = f"{desc} {dd_body}"
            title = f"{label} {version}" if version else label
            content = desc
        else:
            title = label
            content = dd_body if dd_body else body

        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    _dt_pattern = re.compile(
        rf'<dt><code><span class="parameter-name">[^<]*</span>\s*'
        rf'<span class="parameter-annotation-sep"[^>]*>[^<]*</span>\s*'
        rf'<span class="parameter-annotation">'
        rf"\.\.\s+(?P<directive>{directive_names})::\s*(?P<body>[^<]*?)"
        rf"</span></code></dt>"
        rf"\s*<dd>\s*(?:<p>(?P<dd_body>.*?)</p>\s*)?</dd>",
        re.DOTALL,
    )
    _dt_count = len(_dt_pattern.findall(html_content))
    html_content = _dt_pattern.sub(_replace_dt_directive, html_content)

    return html_content


def translate_bold_section_headers(html_content):
    """
    Convert bold-text section headings into proper doc-section markup.

    Sphinx-format docstrings sometimes use `**Examples**::` to introduce
    a section.  After rendering this becomes:

        <p><strong>Examples</strong>:</p>

    This function converts those into the same `<section>`/`<h1>` structure that the renderer uses
    for NumPy-style sections so the page has a consistent look.
    """

    # Map of recognized section names → CSS id / class suffix
    _SECTION_NAMES = {
        "Examples": "examples",
        "Example": "examples",
        "Notes": "notes",
        "Note": "notes",
        "References": "references",
        "Warnings": "warnings",
        "Warning": "warnings",
        "See Also": "see-also",
    }

    # Map English section names to i18n keys for translation
    _BOLD_I18N_KEY = {
        "Examples": "examples",
        "Example": "examples",
        "Notes": "notes",
        "Note": "notes",
        "References": "references_section",
        "Warnings": "warnings_section",
        "Warning": "warnings_section",
        "See Also": "see_also",
    }

    section_pattern = "|".join(re.escape(n) for n in _SECTION_NAMES)

    def _replace_header(m):
        name = m.group("name")
        slug = _SECTION_NAMES.get(name, name.lower().replace(" ", "-"))
        i18n_key = _BOLD_I18N_KEY.get(name)
        display = _t(i18n_key, name) if i18n_key else name
        return (
            f'<section id="{slug}" class="level1 doc-section doc-section-{slug}">\n'
            f'<h1 class="doc-section doc-section-{slug}">{display}</h1>'
        )

    html_content = re.sub(
        rf"<p><strong>(?P<name>{section_pattern})</strong>::</p>",
        _replace_header,
        html_content,
    )

    return html_content


def translate_qrenderer_headings(html_content):
    """
    Translate section headings and labels produced by the qrenderer.

    The qrenderer emits headings with `doc-*` CSS classes (e.g.
    `<h2 class="doc-parameters">Parameters</h2>`) and a `Usage` label inside
    `<div class="doc-usage-source">`.  These are rendered at Quarto build time and pass through
    untranslated.

    This function replaces the English heading text with the corresponding i18n translation, and
    also updates matching TOC sidebar links so the table-of-contents stays in sync.
    """

    # Map CSS class suffix → (i18n key, English fallback)
    _HEADING_MAP = {
        "parameters": ("parameters", "Parameters"),
        "returns": ("returns", "Returns"),
        "raises": ("raises", "Raises"),
        "examples": ("examples", "Examples"),
        "notes": ("notes", "Notes"),
        "attributes": ("attributes", "Attributes"),
        "methods": ("methods", "Methods"),
        "see-also": ("see_also", "See Also"),
        "warnings": ("warnings_section", "Warnings"),
        "references": ("references_section", "References"),
    }

    # Map group heading text → i18n key
    _GROUP_MAP = {
        "Classes": "classes",
        "Functions": "functions",
        "Methods": "methods",
    }

    # ── Translate doc-section / doc-* headings ──────────────────────────
    # Matches:  <h2 class="doc-parameters">Parameters</h2>
    #           <h5 class="doc-returns anchored" ...>Returns</h5>
    def _replace_heading(m):
        prefix = m.group("prefix")
        css_class = m.group("cls")
        _english = m.group("text")
        tag = m.group("tag")
        entry = _HEADING_MAP.get(css_class)
        if entry:
            key, fallback = entry
            translated = _t(key, fallback)
        else:
            translated = _english
        return f"{prefix}{translated}</{tag}>"

    html_content = re.sub(
        r'(?P<prefix><(?P<tag>h[1-6])\s+class="doc-(?P<cls>[a-z-]+)[^"]*"[^>]*>)'
        r"(?P<text>[^<]+)"
        r"</(?P=tag)>",
        _replace_heading,
        html_content,
    )

    # ── Translate doc-group headings ────────────────────────────────────
    # Matches:  <h2 class="doc-group">Classes</h2>
    def _replace_group(m):
        prefix = m.group("prefix")
        text = m.group("text")
        tag = m.group("tag")
        key = _GROUP_MAP.get(text)
        translated = _t(key, text) if key else text
        return f"{prefix}{translated}</{tag}>"

    html_content = re.sub(
        r'(?P<prefix><(?P<tag>h[1-6])\s+class="doc-group"[^>]*>)'
        r"(?P<text>[^<]+)"
        r"</(?P=tag)>",
        _replace_group,
        html_content,
    )

    # ── Translate "Usage" label ─────────────────────────────────────────
    # Matches:  <div class="doc-usage-source">\n<p>Usage</p>
    html_content = re.sub(
        r'(<div\s+class="doc-usage-source">\s*<p>)Usage(</p>)',
        lambda m: f"{m.group(1)}{_t('usage', 'Usage')}{m.group(2)}",
        html_content,
    )

    # ── Translate "Source" link text ─────────────────────────────────────
    # Matches:  <a class="doc-source" ...>Source</a>
    html_content = re.sub(
        r'(<a\s[^>]*class="doc-source"[^>]*>)Source(</a>)',
        lambda m: f"{m.group(1)}{_t('source', 'Source')}{m.group(2)}",
        html_content,
    )

    # ── Update TOC sidebar links to match translated headings ───────────
    # Matches:  <a href="#parameters" id="toc-parameters" ...>Parameters</a>
    _TOC_SECTIONS = {
        "parameters": ("parameters", "Parameters"),
        "returns": ("returns", "Returns"),
        "raises": ("raises", "Raises"),
        "examples": ("examples", "Examples"),
        "notes": ("notes", "Notes"),
        "attributes": ("attributes", "Attributes"),
        "methods": ("methods", "Methods"),
        "see-also": ("see_also", "See Also"),
        "warnings": ("warnings_section", "Warnings"),
        "references": ("references_section", "References"),
    }

    def _replace_toc(m):
        prefix = m.group("prefix")
        slug = m.group("slug")
        entry = _TOC_SECTIONS.get(slug)
        if entry:
            key, fallback = entry
            translated = _t(key, fallback)
        else:
            translated = m.group("text")
        return f"{prefix}{translated}</a>"

    html_content = re.sub(
        r'(?P<prefix><a\s[^>]*id="toc-(?P<slug>[a-z-]+)"[^>]*>)'
        r"(?P<text>[^<]+)"
        r"</a>",
        _replace_toc,
        html_content,
    )

    # ── Translate <div class="see-also"> headings ───────────────────────
    # q renders See Also sections as:
    #   <div class="see-also" ...><h3/h4 ...>See Also</h3/h4>
    html_content = re.sub(
        r'(<div\s[^>]*class="see-also"[^>]*>\s*<(?:h[1-6])[^>]*>)See Also(</(?:h[1-6])>)',
        lambda m: f"{m.group(1)}{_t('see_also', 'See Also')}{m.group(2)}",
        html_content,
    )

    # ── Translate Quarto callout titles ────────────────────────────────
    # Quarto renders callouts with titles like:
    #   <div class="callout ... callout-titled" title="Added in version 2.0">
    #   <span class="screen-reader-only">Note</span>Added in version 2.0
    #   or a standalone:
    #   <div class="callout-title-container ...">Note</div>

    # Version-related callout titles (versionadded, versionchanged, deprecated)
    _CALLOUT_VERSION_MAP = {
        "Added in version": "added_in_version",
        "Changed in version": "changed_in_version",
        "Deprecated since version": "deprecated_since_version",
    }

    for eng_label, i18n_key in _CALLOUT_VERSION_MAP.items():
        translated = _t(i18n_key, eng_label)
        if translated != eng_label:
            if "{v}" in translated:
                # Handle translations with {v} placeholder (e.g. ja, ko, zh)
                # Match "Added in version 0.1.0" and insert version into {v}
                _ver_pat = re.compile(re.escape(eng_label) + r"(\s+[\d][\d.]*)")
                html_content = _ver_pat.sub(
                    lambda m: translated.replace("{v}", m.group(1).strip()),
                    html_content,
                )
                # Replace any remaining standalone label (no version)
                html_content = html_content.replace(
                    eng_label,
                    translated.replace(" {v}", "").replace("{v}", ""),
                )
            else:
                html_content = html_content.replace(eng_label, translated)

    # Standalone callout type labels (Note, Warning, etc.)
    _CALLOUT_LABEL_MAP = {
        "Note": "note_callout",
        "Warning": "warning_callout",
        "Caution": "caution_callout",
        "Danger": "danger_callout",
        "Important": "important_callout",
        "Tip": "tip_callout",
        "Hint": "hint_callout",
    }

    for eng_label, i18n_key in _CALLOUT_LABEL_MAP.items():
        translated = _t(i18n_key, eng_label)
        if translated != eng_label:
            # Only replace inside callout title containers and screen-reader spans
            # to avoid affecting other content
            html_content = re.sub(
                rf'(<span\s+class="screen-reader-only">){re.escape(eng_label)}(</span>)',
                rf"\g<1>{translated}\g<2>",
                html_content,
            )
            html_content = re.sub(
                rf'(<div\s+class="callout-title-container[^"]*">\s*){re.escape(eng_label)}(\s*</div>)',
                rf"\g<1>{translated}\g<2>",
                html_content,
            )

    return html_content


def fix_doctest_blockquotes(html_content):
    """
    Convert nested blockquotes from doctest `>>>` lines into code blocks.

    When the renderer produces an Example section with raw `>>>` lines in the `.qmd` file,
    Quarto/Pandoc interprets the leading `>` characters as Markdown blockquote markers.  A `>>>`
    line becomes triple-nested `<blockquote>` elements:

    ```html
    <blockquote class="blockquote">
    <blockquote class="blockquote">
    <blockquote class="blockquote">
    <p>func(x) 'result'</p>
    </blockquote>
    </blockquote>
    </blockquote>
    ```

    This function detects that pattern inside Example/Examples doc-sections and replaces it with a
    proper `<pre><code>` block so the content renders in monospace as code.
    """
    # Match one or more triple-nested blockquote clusters inside an
    # Example or Examples doc-section.
    _SECTION_RE = re.compile(
        r'(<section\s[^>]*class="[^"]*doc-section-examples?[^"]*"[^>]*>\s*'
        r"<h1[^>]*>.*?</h1>\s*)"
        r"((?:\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>"
        r"\s*<p>.*?</p>\s*</blockquote>\s*</blockquote>\s*</blockquote>\s*)+)",
        re.DOTALL,
    )

    # Extract individual <p> content from triple-nested blockquotes
    _BQ_TEXT_RE = re.compile(
        r"<blockquote\s[^>]*>\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>"
        r"\s*<p>(.*?)</p>\s*</blockquote>\s*</blockquote>\s*</blockquote>",
        re.DOTALL,
    )

    def _replace_section(m):
        header = m.group(1)
        bq_block = m.group(2)
        lines = []
        for bq in _BQ_TEXT_RE.finditer(bq_block):
            text = bq.group(1).strip()
            # Reconstruct the doctest line with >>> prefix
            lines.append(f"&gt;&gt;&gt; {text}")
        code = "\n".join(lines)
        return f"{header}<pre><code>{code}</code></pre>\n"

    return _SECTION_RE.sub(_replace_section, html_content)


def fix_plain_doctest_code_blocks(html_content):
    """
    Convert plain `<pre><code>` blocks containing doctest `>>>` lines into properly highlighted
    Python code blocks.

    When the renderer renders consecutive doctest examples separated by blank lines, only the first
    block gets a proper ```` ```python ```` fence. Subsequent blocks become 4-space-indented text in
    the `.qmd` file, which Quarto renders as plain ``<pre><code>`` without syntax highlighting.

    This function finds those plain code blocks, re-highlights them with Pygments, and wraps them in
    the same `sourceCode python` structure that Quarto uses for fenced code blocks.
    """
    # Match <pre><code> blocks that contain &gt;&gt;&gt; (i.e. >>>) but
    # are NOT already inside a sourceCode div.  We look for <pre><code>
    # (no class) immediately, which distinguishes them from Quarto's
    # <pre class="sourceCode ..."><code class="sourceCode ..."> blocks.
    _PLAIN_DOCTEST_RE = re.compile(
        r"<pre><code>(.*?)</code></pre>",
        re.DOTALL,
    )

    # Track a counter for generating unique cb IDs
    _cb_counter = [0]

    def _find_max_cb_id(html):
        """Find the highest existing cb ID to avoid collisions."""
        ids = re.findall(r'id="cb(\d+)"', html)
        return max(int(i) for i in ids) if ids else 0

    _cb_counter[0] = _find_max_cb_id(html_content)

    def _replace_plain_doctest(m):
        code_html = m.group(1)

        # Only process blocks that contain doctest >>> markers
        if "&gt;&gt;&gt;" not in code_html:
            return m.group(0)

        # Decode HTML entities to get plain text for Pygments
        plain_text = code_html
        plain_text = plain_text.replace("&lt;", "<")
        plain_text = plain_text.replace("&gt;", ">")
        plain_text = plain_text.replace("&amp;", "&")
        plain_text = plain_text.replace("&quot;", '"')
        plain_text = plain_text.replace("&#39;", "'")
        # Strip any existing HTML tags (unlikely but safe)
        plain_text = re.sub(r"<[^>]+>", "", plain_text)

        # Highlight with Pygments
        lexer = PythonLexer()
        formatter = HtmlFormatter(nowrap=True, classprefix="")
        highlighted = highlight(plain_text, lexer, formatter)

        # Map Pygments CSS classes to Quarto CSS classes
        for pg_class, quarto_class in PYGMENTS_TO_QUARTO_CLASS.items():
            if quarto_class:
                highlighted = highlighted.replace(f'class="{pg_class}"', f'class="{quarto_class}"')
            else:
                highlighted = re.sub(
                    rf'<span class="{pg_class}">([^<]*)</span>',
                    r"\1",
                    highlighted,
                )

        # Assign a unique cb ID
        _cb_counter[0] += 1
        cb_id = f"cb{_cb_counter[0]}"

        # Wrap each line in a span with proper id for line linking
        lines = highlighted.rstrip("\n").split("\n")
        wrapped_lines = []
        for j, line in enumerate(lines, 1):
            span_id = f"{cb_id}-{j}"
            wrapped_lines.append(
                f'<span id="{span_id}">'
                f'<a href="#{span_id}" aria-hidden="true" tabindex="-1"></a>'
                f"{line}</span>"
            )
        highlighted = "\n".join(wrapped_lines)

        return (
            f'<div class="code-copy-outer-scaffold">'
            f'<nav class="gd-code-nav">'
            f'<button class="gd-code-copy" title="Copy to clipboard"></button>'
            f"</nav>"
            f'<div class="sourceCode" id="{cb_id}">'
            f'<pre class="sourceCode python">'
            f'<code class="sourceCode python">'
            f"{highlighted}"
            f"</code></pre></div></div>"
        )

    return _PLAIN_DOCTEST_RE.sub(_replace_plain_doctest, html_content)


def translate_rst_math(html_content):
    """
    Convert RST `.. math::` directives into display-math blocks.

    After rendering, a `.. math::` block in a docstring becomes literal HTML of the form:

    ```html
    <p>.. math::</p>
    <pre><code>LATEX EXPRESSION</code></pre>
    ```

    This function converts that pattern into a proper KaTeX display math block and injects the KaTeX
    CSS/JS from a CDN so the browser can render the equations.
    """
    _KATEX_VERSION = "0.16.11"
    _KATEX_CDN = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VERSION}/dist"

    _KATEX_HEAD = (
        f'<link rel="stylesheet" href="{_KATEX_CDN}/katex.min.css"'
        ' crossorigin="anonymous">\n'
        f'<script defer src="{_KATEX_CDN}/katex.min.js"'
        ' crossorigin="anonymous"></script>\n'
        f'<script defer src="{_KATEX_CDN}/contrib/auto-render.min.js"'
        ' crossorigin="anonymous"'
        ' onload="renderMathInElement(document.body, {'
        "delimiters: ["
        "{left: '\\\\[', right: '\\\\]', display: true},"
        "{left: '\\\\(', right: '\\\\)', display: false}"
        "]"
        '});"></script>\n'
    )

    # Replace <p>.. math::</p><pre><code>...</code></pre>  →  display math
    # (original two-colon pattern from RST)
    new_content, count = re.subn(
        r"<p>\s*\.\.\s*math::\s*</p>\s*<pre><code>(.*?)</code></pre>",
        lambda m: ('<p><span class="math display">\\[' + m.group(1).strip() + "\\]</span></p>"),
        html_content,
        flags=re.DOTALL,
    )

    # Also handle the single-colon variant produced when Pandoc reduces
    # trailing :: to : (e.g. <p>.. math:</p> followed by a sourceCode block)
    new_content, count2 = re.subn(
        r"<p>\s*\.\.\s*math:\s*</p>\s*"
        r"(?:<div[^>]*>\s*)?"  # optional wrapper div
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>"
        r"(?:\s*</div>)?",  # optional closing wrapper div
        lambda m: (
            '<p><span class="math display">\\['
            + re.sub(r"</?span[^>]*>", "", m.group(1)).strip()
            + "\\]</span></p>"
        ),
        new_content,
        flags=re.DOTALL,
    )
    count += count2

    # Only inject KaTeX CDN if we actually converted any math blocks
    if count > 0 and _KATEX_CDN not in new_content:
        new_content = new_content.replace("</head>", _KATEX_HEAD + "</head>", 1)

    return new_content


def translate_rst_references(html_content):
    """
    Convert RST citation references into a styled numbered list.

    After rendering, RST citations like:

        .. [1] Author (Year). "Title."
        .. [2] https://example.com

    end up as a single `<p>` tag with the markers run together::

        <p>.. [1] First ref. .. [2] Second ref.</p>

    This function splits them apart and renders each as a styled list item with the citation number
    as a label.
    """

    def _format_refs(m):
        text = m.group(1)
        # Split on citation markers: .. [N]
        parts = re.split(r"\.\.\s*\[(\d+)\]", text)
        # parts = ['', '1', ' First ref. ', '2', ' Second ref.', ...]
        if len(parts) < 3:
            return m.group(0)  # No valid citations found

        items = []
        # parts[0] is text before first marker (usually empty), then pairs of (number, text)
        for i in range(1, len(parts), 2):
            num = parts[i]
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not body:
                continue
            # Auto-link bare URLs in the body
            body = re.sub(
                r"(https?://\S+)",
                r'<a href="\1" target="_blank" rel="noopener">\1</a>',
                body,
            )
            items.append(
                f'<li style="margin-bottom: 0.25rem;">'
                f'<span style="font-weight: 600; color: #6c757d;">[{num}]</span> '
                f"{body}</li>"
            )

        if not items:
            return m.group(0)

        return (
            '<ol style="list-style: none; padding-left: 0; margin: 0;">'
            + "\n".join(items)
            + "</ol>"
        )

    # Match <p> tags containing at least one .. [N] citation marker.
    # Use [^<]* instead of .*? to prevent matching across HTML tag boundaries,
    # and omit re.DOTALL so the match stays within a single line.
    html_content = re.sub(
        r"<p>((?:[^<]*\.\.\s*\[\d+\][^<]*)+)</p>",
        _format_refs,
        html_content,
    )
    return html_content


def extract_seealso_from_html(html_content):
    """
    Extract %seealso values from HTML content before stripping.

    Returns a list of `(name, description)` tuples. The description is an empty string when no
    `: description` suffix was provided.
    """
    # Match %seealso in <p> tags (most common after markdown rendering)
    # This handles both standalone %seealso and when it follows other directives
    p_pattern = re.compile(
        r"<p>[^<]*%seealso\s+([^<%]+?)(?:%|</p>)",
        re.IGNORECASE,
    )

    # Match standalone %seealso lines (not in HTML tags)
    standalone_pattern = re.compile(
        r"%seealso\s+([^\n%<]+)",
        re.IGNORECASE,
    )

    # Try <p> pattern first
    match = p_pattern.search(html_content)
    if not match:
        match = standalone_pattern.search(html_content)

    if match:
        # Parse comma-separated list, each entry may have ": description"
        items_str = match.group(1).strip()
        items = []
        for entry in items_str.split(","):
            entry = entry.strip()
            if not entry:
                continue
            # Split on first " : " or ": " to separate name from description
            parts = re.split(r"\s*:\s*", entry, maxsplit=1)
            name = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            if name:
                items.append((name, desc))
        return items

    return []


def extract_seealso_from_doc_section(html_content):
    """
    Extract See Also items from rendered doc-section `<section>` blocks.

    NumPy-style and Google-style docstrings produce sections like:

        <section id="see-also" class="level1 doc-section doc-section-see-also">
        <h1 ...>See Also</h1>
        <p>transform : Transform data before analysis.</p>
        </section>

    Returns a list of `(name, description)` tuples.
    """
    # Match <section id="see-also" ...> ... </section> blocks
    section_pat = re.compile(
        r'<section[^>]*\bid=["\']see-also["\'][^>]*>'
        r"(.*?)"
        r"</section>",
        re.DOTALL,
    )
    items = []
    for m in section_pat.finditer(html_content):
        body = m.group(1)
        # Remove the heading tags
        body = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", "", body, flags=re.DOTALL)

        # Q renderer: names live in href attributes like href="`~Name`"
        # Also look for description text in <dd> or after the link
        interlink_names = re.findall(r'href="`~([\w.]+)`"', body)
        if interlink_names:
            # Try to extract descriptions from definition list structure
            # Pattern: <dt>...<a href="`~Name`">...</a>...</dt><dd>description</dd>
            dt_dd_pairs = re.findall(
                r'<dt[^>]*>.*?href="`~([\w.]+)`".*?</dt>\s*<dd[^>]*>(.*?)</dd>',
                body,
                re.DOTALL,
            )
            if dt_dd_pairs:
                for name, desc_html in dt_dd_pairs:
                    desc = re.sub(r"<[^>]+>", "", desc_html).strip()
                    items.append((name, desc))
            else:
                items.extend((name, "") for name in interlink_names)
            continue

        # Classic renderer: names appear as plain text
        plain = re.sub(r"<[^>]+>", "", body).strip()
        if not plain:
            continue
        # Parse entries: each may be "name : description" or "name: description"
        # or multiple comma-separated or newline-separated entries
        for line in plain.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Handle comma-separated items on a single line
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # Extract the name and description
                # e.g., "transform : Transform data before analysis."
                # e.g., "``validate``: Validate a schema before processing."
                # Strip backticks first
                part = part.replace("``", "").replace("`", "")
                name_match = re.match(r"^([\w.]+)(?:\s*:\s*(.*))?$", part)
                if name_match:
                    name = name_match.group(1)
                    desc = (name_match.group(2) or "").strip()
                    items.append((name, desc))
    return items


def remove_seealso_doc_section(html_content):
    """
    Remove `<section id="see-also" ...>` blocks from the HTML.

    Also removes the corresponding TOC entry.
    """
    # Remove the section block
    html_content = re.sub(
        r'<section[^>]*\bid=["\']see-also["\'][^>]*>'
        r".*?"
        r"</section>",
        "",
        html_content,
        flags=re.DOTALL,
    )
    # Remove the TOC entry for See Also
    html_content = re.sub(
        r'\s*<li><a[^>]*href=["\']#see-also["\'][^>]*>See Also</a></li>',
        "",
        html_content,
    )
    return html_content


def generate_seealso_html(seealso_items):
    """
    Generate HTML for a "See Also" section with links to other reference pages.

    Each item is a `(name, description)` tuple. When description is non-empty, it is rendered after
    the link.
    """
    if not seealso_items:
        return ""

    links = []
    for item in seealso_items:
        if isinstance(item, tuple):
            name, desc = item
        else:
            name, desc = item, ""
        # Generate link to the reference page
        # Item could be "Graph.add_edge" or just "add_edge"
        html_filename = f"{name}.html"
        # Append () for callable objects (functions, methods)
        display = name
        sa_result = _resolve_interlink_name(name)
        if sa_result and sa_result[2] in _CALLABLE_ROLES:
            display += "()"
        link = f'<a href="{html_filename}" class="gdls-link gdls-code">{display}</a>'
        if desc:
            link = f"{link}: {desc}"
        links.append(link)

    # Use a list layout when any item has a description, otherwise comma-separated
    has_descriptions = any((item[1] if isinstance(item, tuple) else "") for item in seealso_items)
    if has_descriptions:
        items_html = "\n".join(f'<li style="margin-bottom: 0.25rem;">{link}</li>' for link in links)
        body = f'<ul style="list-style: none; padding-left: 0; margin: 0;">{items_html}</ul>'
    else:
        body = f'<p style="margin: 0;">{", ".join(links)}</p>'

    _see_also_label = _t("see_also", "See Also")

    return f"""
<div class="see-also" style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #dee2e6;">
<h3 style="font-size: 0.9rem; font-weight: 600; color: #6c757d; margin-bottom: 0.5rem;">{_see_also_label}</h3>
{body}
</div>
"""


def fix_dataclass_attributes(content_str):
    """Rebuild the Attributes table for dataclass pages using *_dataclass_attrs.json* metadata.

    The renderer may only discover a subset of dataclass fields. This function replaces the
    `<tbody>` of the Attributes `<table>` with the complete set of fields recorded in the metadata
    file.
    """
    if not dataclass_attrs_metadata:
        return content_str

    # Locate the Attributes <section> (Quarto wraps each ## heading in a section)
    attrs_match = re.search(r'<section[^>]*\bid="attributes"[^>]*>', content_str)
    if not attrs_match:
        return content_str

    # Determine the object path by inspecting existing <a href="#obj.field">
    # anchors inside the Attributes table.
    attrs_section_start = attrs_match.start()
    attrs_section_end = content_str.find("</section>", attrs_section_start)
    if attrs_section_end < 0:
        return content_str

    attrs_section = content_str[attrs_section_start : attrs_section_end + len("</section>")]

    # Extract obj_path from an existing anchor (e.g., href="#pkg.Cls.field" -> "pkg.Cls")
    anchor_re = re.search(r'href="#([^"]+)\.(\w+)"', attrs_section)
    if not anchor_re:
        return content_str

    obj_path = anchor_re.group(1)

    if obj_path not in dataclass_attrs_metadata:
        return content_str

    fields = dataclass_attrs_metadata[obj_path]

    # Build new table rows
    rows = []
    for i, (fname, desc) in enumerate(fields.items()):
        row_class = "odd" if i % 2 == 0 else "even"
        anchor = f"{obj_path}.{fname}"
        rows.append(
            f'<tr class="{row_class}">\n'
            f'<td><a href="#{anchor}">{fname}</a></td>\n'
            f"<td>{desc}</td>\n"
            f"</tr>"
        )

    new_tbody = "<tbody>\n" + "\n".join(rows) + "\n</tbody>"

    # Replace the <tbody> inside the Attributes section
    new_attrs_section = re.sub(r"<tbody>.*?</tbody>", new_tbody, attrs_section, flags=re.DOTALL)

    content_str = (
        content_str[:attrs_section_start]
        + new_attrs_section
        + content_str[attrs_section_end + len("</section>") :]
    )
    return content_str


# Process all HTML files in the `_site/reference/` directory (except `index.html`)
# and apply the specified transformations
html_files = [f for f in glob.glob("_site/reference/*.html") if os.path.basename(f) != "index.html"]

print(f"Found {len(html_files)} HTML files to process")

for html_file in html_files:
    print(f"Processing: {html_file}")

    # Extract the item name from the filename (e.g., "GreatDocs.html" -> "GreatDocs")
    item_name_from_file = os.path.basename(html_file).replace(".html", "")

    with open(html_file, "r", encoding="utf-8") as file:
        content = file.read()

    # Extract %seealso before stripping directives
    seealso_items = extract_seealso_from_html(content)

    # Strip %directive lines from rendered HTML (safety net for docstring directives)
    content = strip_directives_from_html(content)

    # Translate Sphinx field lists (:param, :type, :returns, :rtype, :raises)
    content = translate_sphinx_fields(content)

    # Translate Google-style field sections (Args:, Returns:, Raises:, etc.)
    content = translate_google_fields(content)

    # Translate Sphinx cross-reference roles (e.g. :py:exc:`ValueError`)
    content = translate_sphinx_roles(content)

    # Translate RST directives (e.g. .. versionadded:: 2.8.1)
    content = translate_rst_directives(content)

    # Translate bold section headers (e.g. **Examples**::) into doc-sections
    content = translate_bold_section_headers(content)

    # Translate qrenderer-rendered headings and Usage/Source labels
    content = translate_qrenderer_headings(content)

    # Fix doctest >>> lines that Quarto rendered as nested blockquotes
    content = fix_doctest_blockquotes(content)

    # Fix plain <pre><code> blocks containing >>> doctest lines
    # (consecutive examples where only the first got a proper code fence)
    content = fix_plain_doctest_code_blocks(content)

    # Translate RST .. math:: blocks into display math
    content = translate_rst_math(content)

    # Translate RST citation references (.. [1] ...)
    content = translate_rst_references(content)

    # Re-highlight the signature with Pygments for better syntax coloring
    content = highlight_signature_with_pygments(content)

    # Format signatures with multiple arguments onto separate lines
    content = format_signature_multiline(content)

    # For non-callable types (e.g., TypedDict, Enum), strip empty () from the signature
    # TypedDicts are structural type definitions, not constructors
    # Enums are accessed via members (e.g., Color.RED), not called
    _NON_CALLABLE_SIGNATURE_TYPES = {"typeddict", "enum"}
    obj_type_for_sig = object_types.get(item_name_from_file)
    if obj_type_for_sig and obj_type_for_sig in _NON_CALLABLE_SIGNATURE_TYPES:
        content = re.sub(
            r'(<span class="sig-name">[^<]+</span>)\(\)',
            r"\1",
            content,
        )

    # Convert back to lines for line-by-line processing
    content = content.splitlines(keepends=True)

    # Determine the classification of each h1 tag based on its content
    # Remove the literal text `Validate.` from the h1 tag
    # TODO: Add line below stating the class name for the method
    content = [
        line.replace(
            '<h1 class="title">Validate.',
            '<h1 class="title">',
        )
        for line in content
    ]

    # Add `()` only to functions and methods in the h1 title
    # Uses object_types metadata when available, otherwise falls back to heuristics
    _CALLABLE_TYPES = {"function", "method"}

    for i, line in enumerate(content):
        # Use regex to find h1 tags (both class="title" and styled versions)
        h1_match = re.search(r'<h1\s+class="title">', line)

        if not h1_match:
            h1_match = re.search(r'<h1\s+style="[^"]*">', line)

        if h1_match:
            # Extract the content of the h1 tag
            start = h1_match.end()
            end = line.find("</h1>", start)
            h1_content = line[start:end].strip()

            # Determine whether this item should get ()
            obj_type = object_types.get(item_name_from_file)

            # Replace the h1 tag with the modified content
            content[i] = line[:start] + h1_content + line[end:]

    # Wrap bare h1 tags (those with style attribute but no quarto-title wrapper) in proper structure
    for i, line in enumerate(content):
        # Look for h1 tags with style attribute that aren't already wrapped
        if "<h1 style=" in line and "SFMono-Regular" in line:
            # Check if this h1 is already wrapped in quarto-title div
            # Look at previous lines to see if there's a quarto-title div
            is_wrapped = False
            for j in range(max(0, i - 5), i):
                if 'class="quarto-title"' in content[j]:
                    is_wrapped = True
                    break

            # If not wrapped, wrap it
            if not is_wrapped:
                # Extract the h1 content
                h1_content = line.strip()

                # Replace the line with the wrapped version
                wrapped_h1 = f'<div class="quarto-title">\n{h1_content}\n</div>\n'
                content[i] = wrapped_h1

    # Add a style attribute to the h1 tag to use a monospace font for code-like appearance
    content = [
        line.replace(
            '<h1 class="title">',
            "<h1 class=\"title\" style=\"font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.25rem;\">",
        )
        for line in content
    ]

    # Some h1 tags may not have a class attribute, so we handle that case too
    # But skip "Attributes" and "Methods" section headings — they should look like
    # the Parameters section label (doc-section style), not code font.
    _SECTION_HEADINGS = {"Attributes", "Methods"}
    new_content = []
    for line in content:
        if "<h1>" in line:
            # Check if this is a section heading like Attributes or Methods
            h1_text_match = re.search(r"<h1>(.*?)</h1>", line)
            if h1_text_match and h1_text_match.group(1).strip() in _SECTION_HEADINGS:
                # Style like Parameters: use doc-section class instead of code font
                line = line.replace(
                    "<h1>",
                    '<h1 class="doc-section">',
                )
            else:
                line = line.replace(
                    "<h1>",
                    "<h1 style=\"font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.25rem;\">",
                )
        new_content.append(line)
    content = new_content

    # Fix return value formatting in individual function pages, removing the `:` before the
    # return value and adjusting the style of the parameter annotation separator
    content_str = "".join(content)

    # Inject constant value/annotation into constant reference pages.
    # Replaces the bare ``<p><code>NAME</code></p>`` that the renderer emits with a
    # styled display showing the type annotation and assigned value.
    obj_type_for_value = object_types.get(item_name_from_file)
    if obj_type_for_value == "constant" and item_name_from_file in constant_values:
        meta = constant_values[item_name_from_file]
        annotation = meta.get("annotation", "")
        value = meta.get("value", "")

        # Build the display string:  NAME: type = value
        parts = [f"<code>{item_name_from_file}</code>"]
        if annotation:
            parts.append(f'<code style="color: #6b7280;">: {annotation}</code>')
        if value:
            parts.append(f'<code style="color: #6b7280;"> = {value}</code>')
        replacement_html = "<p>" + "".join(parts) + "</p>"

        # Replace the original bare name paragraph
        bare_name_html = f"<p><code>{item_name_from_file}</code></p>"
        if bare_name_html in content_str:
            content_str = content_str.replace(bare_name_html, replacement_html, 1)

    return_value_pattern = (
        r'<span class="parameter-name"></span> <span class="parameter-annotation-sep">:</span>'
    )
    return_value_replacement = r'<span class="parameter-name"></span> <span class="parameter-annotation-sep" style="margin-left: -8px;"></span>'
    content_str = re.sub(return_value_pattern, return_value_replacement, content_str)

    # Remove empty annotation separator + annotation (e.g., Attributes with no type)
    # Pattern: ` <span class="parameter-annotation-sep">:</span> <span class="parameter-annotation"></span>`
    # This leaves just the parameter name without a trailing colon and space.
    content_str = re.sub(
        r' <span class="parameter-annotation-sep"[^>]*>:</span>\s*<span class="parameter-annotation"></span>',
        "",
        content_str,
    )

    # Normalize single quotes to double quotes in parameter default values
    content_str = re.sub(
        r'<span class="parameter-default">&#39;([^&]*)&#39;</span>',
        r'<span class="parameter-default">&quot;\1&quot;</span>',
        content_str,
    )
    content_str = re.sub(
        r"""<span class="parameter-default">'([^']*)'</span>""",
        r'<span class="parameter-default">"\1"</span>',
        content_str,
    )

    # Fix incomplete Attributes tables for dataclass pages
    content_str = fix_dataclass_attributes(content_str)

    # Fix double asterisks in **kwargs and **attributes style parameters
    # Pattern: ****name** -> **name (with proper styling)
    content_str = re.sub(r"\*\*\*\*(\w+)\*\*", r"**<strong>\1</strong>", content_str)

    # Fix leading colon in Raises/Returns sections (e.g., ": ValueError" -> "ValueError")
    # This handles cases like: <dt><code><span class="parameter-annotation-sep">:</span> <span class="parameter-annotation">ValueError</span></code></dt>
    content_str = re.sub(
        r'<dt><code><span class="parameter-annotation-sep">:</span>\s*<span class="parameter-annotation">([^<]+)</span></code></dt>',
        r'<dt><code><span class="parameter-annotation">\1</span></code></dt>',
        content_str,
    )

    content = content_str.splitlines(keepends=True)

    # Turn all h3 tags into h4 tags
    content = [line.replace("<h3", "<h4").replace("</h3>", "</h4>") for line in content]

    # Turn all h2 tags into h3 tags
    content = [line.replace("<h2", "<h3").replace("</h2>", "</h3>") for line in content]

    # Add separator lines between class details and individual members,
    # and between individual member sections.
    # - Thin solid line after the Methods/Attributes summary table (before first member section)
    # - Dotted line between each individual member section
    for i, line in enumerate(content):
        # Detect <section class="level2"> — these are individual member sections
        if "<section id=" in line and 'class="level2"' in line:
            # Check if the previous non-blank line ends a table (</table> in </section>)
            # or is another level2 section close
            for j in range(i - 1, max(0, i - 5), -1):
                prev = content[j].strip()
                if not prev:
                    continue
                if "</table>" in prev:
                    # First member section after a summary table — solid line
                    content[i] = (
                        '<hr style="border: none; border-top: 2px solid #c5c8cd; margin: 1.5rem 0 1rem 0;">\n'
                        + content[i]
                    )
                elif "</section>" in prev:
                    # Between member sections — dotted line
                    content[i] = (
                        '<hr style="border: none; border-top: 2px dotted #b0b4ba; margin: 1.5rem 0 1rem 0;">\n'
                        + content[i]
                    )
                break

    # Merge See Also items from %seealso directives and doc-section blocks
    content_str = "".join(content)
    doc_section_seealso = extract_seealso_from_doc_section(content_str)
    if doc_section_seealso:
        content_str = remove_seealso_doc_section(content_str)
        # Merge with %seealso items (deduplicate by name, preserving order)
        seen = {name for name, _ in seealso_items}
        for name, desc in doc_section_seealso:
            if name not in seen:
                seealso_items.append((name, desc))
                seen.add(name)

    # Resolve interlinks (`~Name` references) throughout the page
    content_str = resolve_interlinks(content_str)

    # Auto-convert inline code matching API names into clickable links
    content_str = autolink_code_references(content_str)

    # Inject unified "See Also" section at the bottom
    if seealso_items:
        seealso_html = generate_seealso_html(seealso_items)
        # Insert before </main>
        content_str = content_str.replace("</main>", f"{seealso_html}</main>")

    # Place a horizontal rule at the end of each reference page
    main_end_pattern = r"</main>"
    main_end_replacement = '</main>\n<hr style="padding: 0; margin: 0;">\n'
    content_str = re.sub(main_end_pattern, main_end_replacement, content_str)

    # Remove breadcrumb navigation (redundant with sidebar)
    breadcrumb_pattern = r'<nav class="quarto-page-breadcrumbs[^"]*"[^>]*>.*?</nav>'
    content_str = re.sub(breadcrumb_pattern, "", content_str, flags=re.DOTALL)

    # Shift all heading levels down by 1 within <main> content so that
    # reference page titles use <h2> instead of <h1>, differentiating them
    # from the top-level "Reference" heading on the index page.
    main_start = content_str.find("<main")
    main_end = content_str.find("</main>")
    if main_start != -1 and main_end != -1:
        before = content_str[:main_start]
        main_content = content_str[main_start : main_end + len("</main>")]
        after = content_str[main_end + len("</main>") :]

        # Shift in reverse order (h5→h6, h4→h5, ..., h1→h2) to avoid
        # double-shifting (e.g. h1→h2→h3).
        for level in range(5, 0, -1):
            main_content = main_content.replace(f"<h{level}", f"<h{level + 1}")
            main_content = main_content.replace(f"</h{level}>", f"</h{level + 1}>")
            main_content = re.sub(
                rf'\bclass="level{level}\b',
                f'class="level{level + 1}',
                main_content,
            )

        content_str = before + main_content + after

    content = content_str.splitlines(keepends=True)

    with open(html_file, "w", encoding="utf-8") as file:
        file.writelines(content)


# Modify the `index.html` file in the `_site/reference/` directory
index_file = "_site/reference/index.html"

if os.path.exists(index_file):
    print(f"Processing index file: {index_file}")

    with open(index_file, "r", encoding="utf-8") as file:
        content = file.read()

    # Convert tables to dl/dt/dd format
    def convert_table_to_dl(match):
        table_content = match.group(1)

        # Extract all table rows
        row_pattern = r"<tr[^>]*>(.*?)</tr>"
        rows = re.findall(row_pattern, table_content, re.DOTALL)

        dl_items = []
        for row in rows:
            # Extract the two td elements
            td_pattern = r"<td[^>]*>(.*?)</td>"
            tds = re.findall(td_pattern, row, re.DOTALL)

            if len(tds) == 2:
                link_content = tds[0].strip()
                description = tds[1].strip()

                dt = f"<dt>{link_content}</dt>"
                dd = f'<dd style="margin-top: -3px;">{description}</dd>'
                dl_items.append(f"{dt}\n{dd}")

        dl_content = "\n\n".join(dl_items)
        return f'<div class="caption-top table" style="border-top-style: dashed; border-bottom-style: dashed;">\n<dl style="margin-top: 10px;">\n\n{dl_content}\n\n</dl>\n</div>'

    # Replace all table structures with dl/dt/dd
    table_pattern = r'<table class="caption-top table">\s*<tbody>(.*?)</tbody>\s*</table>'
    content = re.sub(table_pattern, convert_table_to_dl, content, flags=re.DOTALL)

    # Remove redundant "API Reference" top-level nav item
    # Find the nav structure and flatten it by removing the top-level wrapper
    nav_pattern = r'(<nav[^>]*>.*?<h2[^>]*>.*?</h2>\s*<ul>\s*)<li><a[^>]*href="[^"]*#api-reference"[^>]*>API Reference</a>\s*<ul[^>]*>(.*?)</ul></li>\s*(</ul>\s*</nav>)'
    nav_replacement = r"\1\2\3"
    content = re.sub(nav_pattern, nav_replacement, content, flags=re.DOTALL)

    # Clean up Sphinx cross-reference roles in index descriptions
    content = translate_sphinx_roles(content)

    # Shift section headings down by 1 within <main> so that category headings
    # (Classes, Methods, etc.) render as <h2>, visually subordinate to the
    # <h1> "Reference" page title.  Skip the page title itself (class="title").
    main_start = content.find("<main")
    main_end = content.find("</main>")
    if main_start != -1 and main_end != -1:
        before = content[:main_start]
        main_content = content[main_start : main_end + len("</main>")]
        after = content[main_end + len("</main>") :]

        # Protect the title heading from being shifted by replacing it with a
        # temporary placeholder, then shifting everything else, then restoring.
        title_pattern = re.compile(r'(<h1\s+class="title"[^>]*>.*?</h1>)', re.DOTALL)
        title_placeholder = "<!--TITLE_PLACEHOLDER-->"
        title_match = title_pattern.search(main_content)
        if title_match:
            saved_title = title_match.group(1)
            main_content = main_content.replace(saved_title, title_placeholder, 1)

        for level in range(5, 0, -1):
            main_content = main_content.replace(f"<h{level}", f"<h{level + 1}")
            main_content = main_content.replace(f"</h{level}>", f"</h{level + 1}>")
            main_content = re.sub(
                rf'\bclass="level{level}\b',
                f'class="level{level + 1}',
                main_content,
            )

        # Restore the title heading
        if title_match:
            main_content = main_content.replace(title_placeholder, saved_title, 1)

        content = before + main_content + after

    # Translate qrenderer-rendered headings, TOC, and sidebar on the index page
    content = translate_qrenderer_headings(content)

    with open(index_file, "w", encoding="utf-8") as file:
        file.write(content)

    print("Index file processing complete")
else:
    print(f"Index file not found: {index_file}")


# Update quarto-secondary-nav-title to display "User Guide" text
# This improves the mobile navigation by making it clear what the sidebar toggle reveals
all_html_files = glob.glob("_site/**/*.html", recursive=True)
print(f"Found {len(all_html_files)} HTML files to check for secondary nav title")

# Use translated label for secondary nav if i18n is configured
_user_guide_label = (_gd_options.get("i18n") or {}).get("user_guide", "User Guide")

for html_file in all_html_files:
    with open(html_file, "r", encoding="utf-8") as file:
        content = file.read()

    modified = False

    # Replace empty h1.quarto-secondary-nav-title with h5 containing "User Guide"
    original_pattern = r'<h1 class="quarto-secondary-nav-title"></h1>'
    replacement = f'<h5 class="quarto-secondary-nav-title">{_user_guide_label}</h5>'

    if original_pattern in content:
        print(f"Updating secondary nav title in: {html_file}")
        content = content.replace(original_pattern, replacement)
        modified = True

    # Remove the title attribute from #quarto-search to prevent a duplicate
    # tooltip: Quarto sets title="<search-label>" on the parent div, but the
    # autocomplete library also creates a child button with its own title.
    # Stripping the parent avoids two tooltips stacking on hover.
    _search_title_pat = r'(<div\s+id="quarto-search"\s+class="[^"]*")\s+title="[^"]*"'
    new_content = re.sub(_search_title_pat, r"\1", content)
    if new_content != content:
        content = new_content
        modified = True

    if modified:
        with open(html_file, "w", encoding="utf-8") as file:
            file.write(content)

print("Finished processing all files")

# ── Translate autocomplete search-button title ──────────────────────────────
# The Algolia autocomplete library (autocomplete.umd.js) ships with a
# hardcoded default  detachedSearchButtonTitle:"Search".  Quarto's search JS
# passes  clearButtonTitle / submitButtonTitle / detachedCancelButtonText  to
# the library but omits  detachedSearchButtonTitle, so the button always
# shows "Search".  If the site language is not English, patch the bundled JS
# to use the correct search-label translation instead.
_autocomplete_js = glob.glob("_site/**/autocomplete.umd.js", recursive=True)
if _autocomplete_js:
    _search_label = None
    # Read the search-label from any HTML page's search-options JSON
    for _hf in all_html_files[:5]:
        with open(_hf, "r", encoding="utf-8") as f:
            _hcontent = f.read()
        _sl_m = re.search(r'"search-label"\s*:\s*"([^"]+)"', _hcontent)
        if _sl_m:
            _search_label = _sl_m.group(1)
            break
    if _search_label and _search_label != "Search":
        for _acjs in _autocomplete_js:
            with open(_acjs, "r", encoding="utf-8") as f:
                _ac_content = f.read()
            _old = 'detachedSearchButtonTitle:"Search"'
            if _old in _ac_content:
                _ac_content = _ac_content.replace(
                    _old, f'detachedSearchButtonTitle:"{_search_label}"'
                )
                with open(_acjs, "w", encoding="utf-8") as f:
                    f.write(_ac_content)
                print(f"Patched search button title to '{_search_label}' in {_acjs}")


# ============================================================================
# GitHub Widget Injection
# ============================================================================
# Replace escaped GitHub widget placeholder with actual HTML
# This handles cases where Quarto escapes the HTML in navbar text items


def inject_github_widget():
    """
    Find and replace escaped GitHub widget placeholders with actual widget HTML.

    Quarto escapes HTML in navbar text items, so we need to post-process to inject the actual widget
    div.
    """
    print("Checking for GitHub widget placeholders...")

    widget_escaped_pattern = re.compile(
        r'<span class="menu-text">&lt;div id="github-widget" '
        r'data-owner="([^"]*)" data-repo="([^"]*)"&gt;&lt;/div&gt;</span>'
    )

    widget_count = 0

    for html_file in all_html_files:
        with open(html_file, "r", encoding="utf-8") as file:
            content = file.read()

        # Check if this file has an escaped widget placeholder
        match = widget_escaped_pattern.search(content)
        if match:
            owner = match.group(1)
            repo = match.group(2)

            # Replace with actual widget HTML
            replacement = f'<div id="github-widget" data-owner="{owner}" data-repo="{repo}"></div>'
            content = widget_escaped_pattern.sub(replacement, content)

            with open(html_file, "w", encoding="utf-8") as file:
                file.write(content)

            widget_count += 1

    if widget_count > 0:
        print(f"Injected GitHub widget into {widget_count} HTML files")
    else:
        print("No GitHub widget placeholders found")


inject_github_widget()


# ============================================================================
# Version Badge Injection
# ============================================================================
# Insert a version badge into the navbar title from _package_meta.json


def inject_version_badge():
    """
    Inject a version badge next to the package name in the navbar.

    Reads package version (and optional release date) from `_package_meta.json` (written by the
    build) and inserts a small badge span inside each `<span class="navbar-title">` element across
    all rendered HTML files.  When a `published_at` date is present the badge receives a `title`
    attribute so the release date appears as a native browser tooltip on hover.
    """
    meta_path = "_package_meta.json"
    if not os.path.exists(meta_path):
        print("No _package_meta.json found, skipping version badge injection")
        return

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    version = meta.get("version", "")
    if not version:
        print("No version in _package_meta.json, skipping version badge injection")
        return

    # Build an optional title attribute with the release date
    published_at = meta.get("published_at", "")
    title_attr = ""
    if published_at:
        # published_at is ISO-8601 e.g. "2025-06-15T12:00:00Z"
        date_str = published_at[:10]  # "2025-06-15"
        title_attr = f' title="Released {date_str}"'

    print(f"Injecting version badge v{version} into navbar...")

    # Match <span class="navbar-title">PackageName</span>
    navbar_title_pattern = re.compile(r'(<span class="navbar-title">)(.*?)(</span>)')

    badge_html = f'<span class="version-badge"{title_attr}>v{version}</span>'

    # Build a Tippy.js tooltip for the logo (used when navbar has a logo
    # instead of a text title).  The tooltip shows version tag + release date.
    # Uses HTML content: <code> for the version, <br> for the line break.
    import html as _html_esc

    version_html = f"<code>v{_html_esc.escape(version)}</code>"
    if published_at:
        date_str = published_at[:10]
        released_line = _t("logo_tooltip_released", "Released {date}").replace(
            "{date}", _html_esc.escape(date_str)
        )
        logo_tooltip_html = f"{version_html}<br>{_html_esc.escape(released_line)}"
    else:
        logo_tooltip_html = version_html

    # Pattern to match the <a> navbar-brand-logo link wrapping logo images
    logo_brand_pattern = re.compile(r'(<a\b[^>]*class="navbar-brand navbar-brand-logo"[^>]*)>')

    badge_count = 0
    logo_count = 0

    for html_file in all_html_files:
        with open(html_file, "r", encoding="utf-8") as file:
            content = file.read()

        modified = False

        match = navbar_title_pattern.search(content)
        if match:
            # Only inject if badge not already present
            if "version-badge" not in content:
                replacement = f"{match.group(1)}{match.group(2)} {badge_html}{match.group(3)}"
                content = navbar_title_pattern.sub(replacement, content)
                modified = True
                badge_count += 1

        # When there's a logo but no text title, add a tooltip to the logo link
        if not match:
            logo_match = logo_brand_pattern.search(content)
            if logo_match and 'data-tippy-content="' not in logo_match.group(0):
                escaped_tooltip = logo_tooltip_html.replace('"', "&quot;")
                replacement = f'{logo_match.group(1)} data-tippy-content="{escaped_tooltip}">'
                content = logo_brand_pattern.sub(replacement, content, count=1)
                modified = True
                logo_count += 1

        if modified:
            with open(html_file, "w", encoding="utf-8") as file:
                file.write(content)

    if badge_count > 0:
        print(f"Injected version badge into {badge_count} HTML files")
    if logo_count > 0:
        print(f"Added version tooltip to navbar logo in {logo_count} HTML files")
    if badge_count == 0 and logo_count == 0:
        print("No navbar titles or logos found for version badge injection")


inject_version_badge()


# ============================================================================
# Process CLI reference pages to style titles like API reference pages


def process_cli_reference_pages():
    """
    Process CLI reference pages to add consistent styling.

    This adds the 'cli-title' class to h1 elements in CLI reference pages so they match the
    monospaced font style of API reference pages.
    """
    cli_html_files = glob.glob("_site/reference/cli/*.html")

    if not cli_html_files:
        return

    print(f"Processing {len(cli_html_files)} CLI reference pages...")

    for html_file in cli_html_files:
        with open(html_file, "r", encoding="utf-8") as file:
            content = file.read()

        # Add 'cli-title' class to h1.title elements
        # This matches the pattern: <h1 class="title">
        content = content.replace('<h1 class="title">', '<h1 class="title cli-title">')

        with open(html_file, "w", encoding="utf-8") as file:
            file.write(content)

    print(f"Styled {len(cli_html_files)} CLI reference page titles")


process_cli_reference_pages()


def disable_sidebar_collapse():
    """
    Strip Bootstrap collapse attributes from sidebar section toggles and ensure all sidebar sections
    remain permanently expanded.

    Removes data-bs-toggle, data-bs-target, aria-expanded, and role attributes from sidebar collapse
    triggers. Also removes the collapse class from sidebar section `<ul>` elements and removes the
    chevron toggle `<a>` elements entirely.
    """
    html_files = glob.glob("_site/**/*.html", recursive=True)
    modified_count = 0

    for html_file in html_files:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        original = content

        # Remove the chevron toggle <a> elements entirely
        content = re.sub(
            r'\s*<a class="sidebar-item-toggle text-start"[^>]*>.*?</a>\s*',
            "\n",
            content,
            flags=re.DOTALL,
        )

        # Strip data-bs-toggle="collapse" and data-bs-target from section heading links
        content = re.sub(
            r'(<a class="sidebar-item-text sidebar-link text-start")'
            r'\s+data-bs-toggle="collapse"'
            r'\s+data-bs-target="#[^"]*"'
            r'\s+role="navigation"'
            r'\s+aria-expanded="[^"]*"',
            r"\1",
            content,
        )

        # Remove 'collapse' class from sidebar section <ul> elements
        # e.g. class="collapse list-unstyled sidebar-section depth1 show"
        # becomes class="list-unstyled sidebar-section depth1 show"
        content = re.sub(
            r'(<ul id="quarto-sidebar-section-\d+" class=")collapse\s+',
            r"\1",
            content,
        )

        if content != original:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(content)
            modified_count += 1

    print(f"Disabled sidebar collapse in {modified_count} HTML files")


disable_sidebar_collapse()


def remove_empty_footer_divs():
    """
    Remove empty nav-footer divs that contain only whitespace or &nbsp;.

    Quarto always renders all three footer sections (left, center, right) even when only one has
    content. The empty divs cause excess vertical spacing on mobile viewports due to flex-wrap
    margins.
    """
    html_files = glob.glob("_site/**/*.html", recursive=True)
    modified_count = 0

    empty_div_pattern = re.compile(
        r'\s*<div class="nav-footer-(left|center|right)">\s*'
        r"(?:&nbsp;|\s)*"
        r"</div>\s*",
        re.DOTALL,
    )

    for html_file in html_files:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        original = content
        content = empty_div_pattern.sub("\n", content)

        if content != original:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(content)
            modified_count += 1

    print(f"Removed empty footer divs from {modified_count} HTML files")


remove_empty_footer_divs()


def fix_script_paths():
    """
    Fix relative script paths for HTML files in subdirectories.

    Quarto's include-after-body with text doesn't resolve paths relative to the output file's
    location. This function finds script tags with relative paths and adjusts them based on the
    file's depth in the directory structure.
    """
    print("Fixing script paths for subdirectory pages...")

    fixed_count = 0

    for html_file in all_html_files:
        # Calculate depth relative to _site directory
        rel_path = os.path.relpath(html_file, "_site")
        depth = rel_path.count(os.sep)

        # Skip files at root level (depth 0)
        if depth == 0:
            continue

        with open(html_file, "r", encoding="utf-8") as file:
            content = file.read()

        # Build the relative path prefix (e.g., "../" for depth 1, "../../" for depth 2)
        prefix = "../" * depth

        modified = False

        # Fix github-widget.js path
        old_gh_script = '<script src="github-widget.js"></script>'
        new_gh_script = f'<script src="{prefix}github-widget.js"></script>'

        if old_gh_script in content:
            content = content.replace(old_gh_script, new_gh_script)
            modified = True

        # Fix sidebar-filter.js path
        old_filter_script = '<script src="sidebar-filter.js"></script>'
        new_filter_script = f'<script src="{prefix}sidebar-filter.js"></script>'

        if old_filter_script in content:
            content = content.replace(old_filter_script, new_filter_script)
            modified = True

        # Fix sidebar-wrap.js path
        old_wrap_script = '<script src="sidebar-wrap.js"></script>'
        new_wrap_script = f'<script src="{prefix}sidebar-wrap.js"></script>'

        if old_wrap_script in content:
            content = content.replace(old_wrap_script, new_wrap_script)
            modified = True

        # Fix reference-switcher.js path
        old_ref_switcher = '<script src="reference-switcher.js"></script>'
        new_ref_switcher = f'<script src="{prefix}reference-switcher.js"></script>'

        if old_ref_switcher in content:
            content = content.replace(old_ref_switcher, new_ref_switcher)
            modified = True

        # Fix dark-mode-toggle.js path
        old_dark_mode = '<script src="dark-mode-toggle.js"></script>'
        new_dark_mode = f'<script src="{prefix}dark-mode-toggle.js"></script>'

        if old_dark_mode in content:
            content = content.replace(old_dark_mode, new_dark_mode)
            modified = True

        # Fix theme-init.js path
        old_theme_init = '<script src="theme-init.js"></script>'
        new_theme_init = f'<script src="{prefix}theme-init.js"></script>'

        if old_theme_init in content:
            content = content.replace(old_theme_init, new_theme_init)
            modified = True

        # Fix copy-page.js path
        old_copy_page = '<script src="copy-page.js"></script>'
        new_copy_page = f'<script src="{prefix}copy-page.js"></script>'

        if old_copy_page in content:
            content = content.replace(old_copy_page, new_copy_page)
            modified = True

        # Fix announcement-banner.js path
        old_ann_banner = '<script src="announcement-banner.js"></script>'
        new_ann_banner = f'<script src="{prefix}announcement-banner.js"></script>'

        if old_ann_banner in content:
            content = content.replace(old_ann_banner, new_ann_banner)
            modified = True

        # Fix navbar-style.js path
        old_nb_style = '<script src="navbar-style.js"></script>'
        new_nb_style = f'<script src="{prefix}navbar-style.js"></script>'

        if old_nb_style in content:
            content = content.replace(old_nb_style, new_nb_style)
            modified = True

        # Fix content-style.js path
        old_cs_style = '<script src="content-style.js"></script>'
        new_cs_style = f'<script src="{prefix}content-style.js"></script>'

        if old_cs_style in content:
            content = content.replace(old_cs_style, new_cs_style)
            modified = True

        # Fix copy-code.js path
        old_copy_code = '<script src="copy-code.js"></script>'
        new_copy_code = f'<script src="{prefix}copy-code.js"></script>'

        if old_copy_code in content:
            content = content.replace(old_copy_code, new_copy_code)
            modified = True

        # Fix page-metadata.js path
        old_page_meta = '<script src="page-metadata.js"></script>'
        new_page_meta = f'<script src="{prefix}page-metadata.js"></script>'

        if old_page_meta in content:
            content = content.replace(old_page_meta, new_page_meta)
            modified = True

        # Fix tooltips.js path
        old_tooltips = '<script src="tooltips.js"></script>'
        new_tooltips = f'<script src="{prefix}tooltips.js"></script>'

        if old_tooltips in content:
            content = content.replace(old_tooltips, new_tooltips)
            modified = True

        # Fix responsive-tables.js path
        old_resp_tables = '<script src="responsive-tables.js"></script>'
        new_resp_tables = f'<script src="{prefix}responsive-tables.js"></script>'

        if old_resp_tables in content:
            content = content.replace(old_resp_tables, new_resp_tables)
            modified = True

        # Fix back-to-top.js path
        old_back_to_top = '<script src="back-to-top.js"></script>'
        new_back_to_top = f'<script src="{prefix}back-to-top.js"></script>'

        if old_back_to_top in content:
            content = content.replace(old_back_to_top, new_back_to_top)
            modified = True

        # Fix keyboard-nav.js path
        old_keyboard_nav = '<script src="keyboard-nav.js"></script>'
        new_keyboard_nav = f'<script src="{prefix}keyboard-nav.js"></script>'

        if old_keyboard_nav in content:
            content = content.replace(old_keyboard_nav, new_keyboard_nav)
            modified = True

        # Fix navbar-widgets.js path
        old_navbar_widgets = '<script src="navbar-widgets.js"></script>'
        new_navbar_widgets = f'<script src="{prefix}navbar-widgets.js"></script>'

        if old_navbar_widgets in content:
            content = content.replace(old_navbar_widgets, new_navbar_widgets)
            modified = True

        # Fix mermaid-renderer.js path
        old_mermaid = '<script src="mermaid-renderer.js"></script>'
        new_mermaid = f'<script src="{prefix}mermaid-renderer.js"></script>'

        if old_mermaid in content:
            content = content.replace(old_mermaid, new_mermaid)
            modified = True

        # Fix page-tags.js path
        old_page_tags = '<script src="page-tags.js"></script>'
        new_page_tags = f'<script src="{prefix}page-tags.js"></script>'

        if old_page_tags in content:
            content = content.replace(old_page_tags, new_page_tags)
            modified = True

        if modified:
            with open(html_file, "w", encoding="utf-8") as file:
                file.write(content)
            fixed_count += 1

    if fixed_count > 0:
        print(f"Fixed script paths in {fixed_count} HTML files in subdirectories")
    else:
        print("No script path fixes needed")


fix_script_paths()


# Remove copy-page widget from the root index page (homepage) and the
# reference index page.  Neither is a regular documentation page so the
# Copy / View-as-Markdown buttons are not useful.
for _idx_label, _idx_path in [
    ("homepage", os.path.join("_site", "index.html")),
    ("reference index", os.path.join("_site", "reference", "index.html")),
]:
    if os.path.isfile(_idx_path):
        with open(_idx_path, "r", encoding="utf-8") as f:
            _idx_html = f.read()
        _idx_cleaned = re.sub(
            r'<script src="([./ ]*?)copy-page\.js"></script>\n?',
            "",
            _idx_html,
        )
        if _idx_cleaned != _idx_html:
            with open(_idx_path, "w", encoding="utf-8") as f:
                f.write(_idx_cleaned)
            print(f"Removed copy-page widget from {_idx_label}")


def inject_sidebar_body_classes():
    """
    Inject a `gd-ref-sidebar` class on the `<body>` tag for API/CLI reference pages.

    This allows CSS to scope monospace sidebar fonts to reference pages while keeping the default
    sans-serif font for user-guide, recipe, and other pages.
    """
    print("Injecting sidebar body classes...")
    count = 0

    for html_file in all_html_files:
        rel_path = os.path.relpath(html_file, "_site")
        # Match pages under reference/ (covers both API and CLI reference)
        if not rel_path.startswith("reference" + os.sep) and rel_path != "reference":
            continue

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = content.replace('<body class="', '<body class="gd-ref-sidebar ', 1)
        if new_content != content:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1

    print(f"Injected gd-ref-sidebar class in {count} reference HTML files")


inject_sidebar_body_classes()


def style_api_index_sidebar_item():
    """
    Apply inline styles to the 'API Index' sidebar link so it visually separates from the monospace
    reference entries.

    Targets the `<a>` whose href ends with 'reference/index.html' and its parent
    `<div class="sidebar-item-container">`.
    """
    import re

    print("Styling API Index sidebar item...")
    count = 0
    font = (
        "&quot;Open Sans&quot;, -apple-system, BlinkMacSystemFont, "
        "&quot;Segoe UI&quot;, Roboto, &quot;Helvetica Neue&quot;, Arial, sans-serif"
    )

    for html_file in all_html_files:
        rel_path = os.path.relpath(html_file, "_site")
        if not rel_path.startswith("reference" + os.sep) and rel_path != "reference":
            continue

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the sidebar-item-container div immediately followed by the
        # API Index link (href ending in reference/index.html)
        match = re.search(
            r'(<div class="sidebar-item-container")(>\s*'
            r'<a )([^>]*href="[^"]*reference/index\.html"[^>]*>)',
            content,
        )
        if not match:
            continue

        div_open = match.group(1)
        between = match.group(2)
        a_tag = match.group(3)

        styled_div = div_open + ' style="padding-bottom: 0.5rem; padding-top: 0.25rem;"'
        styled_a = a_tag.replace(
            'class="',
            f'style="font-family: {font};" class="',
            1,
        )

        new_content = content.replace(
            match.group(0),
            styled_div + between + styled_a,
        )

        if new_content != content:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            count += 1

    print(f"Styled API Index sidebar item in {count} reference HTML files")


style_api_index_sidebar_item()


# ============================================================================
# Inject Page Metadata (timestamps and author information)
# ============================================================================
# Adds <meta> tags with page creation/modification dates and author info
# for consumption by page-metadata.js.


def inject_page_metadata():
    """
    Inject page metadata `<meta>` tags into HTML files.

    Adds timestamps and author information for the page-metadata.js script to render in the page
    footer. Auto-generated pages (API reference, changelog) get "Refreshed on" with the build
    timestamp. Authored pages get dates from the original source file's git history.
    """
    if not _gd_options.get("show_dates", False):
        return

    print("Injecting page metadata...")

    build_timestamp = _gd_options.get("build_timestamp", "")
    authors_config = _gd_options.get("authors", [])
    team_author = _gd_options.get("team_author")
    show_author = _gd_options.get("show_author", True)

    # Project root is one directory up from great-docs/
    project_root = os.path.abspath(os.path.join(os.getcwd(), ".."))

    # Build author lookup by name for resolving page authors
    author_lookup: dict[str, dict] = {}
    for author in authors_config:
        if isinstance(author, dict) and author.get("name"):
            author_lookup[author["name"]] = author

    # Identify auto-generated paths (reference, changelog, CLI)
    auto_generated_prefixes = ("reference" + os.sep, "changelog")

    def find_original_source(rel_path: str) -> str | None:
        """Map a page path back to its original source file in project root.

        Examples:
            roadmap.html -> ROADMAP.md
            user-guide/intro.html -> user_guide/01-intro.qmd (with numeric prefix)
            recipes/foo.html -> recipes/foo.qmd
        """
        # Strip .html extension
        base = rel_path.replace(".html", "")

        # Special case: roadmap -> ROADMAP.md
        if base == "roadmap":
            path = os.path.join(project_root, "ROADMAP.md")
            if os.path.exists(path):
                return path

        # Special case: contributing -> CONTRIBUTING.md
        if base == "contributing":
            path = os.path.join(project_root, "CONTRIBUTING.md")
            if os.path.exists(path):
                return path

        # Special case: code-of-conduct -> CODE_OF_CONDUCT.md
        if base == "code-of-conduct":
            path = os.path.join(project_root, "CODE_OF_CONDUCT.md")
            if os.path.exists(path):
                return path

        # Special case: license -> LICENSE or LICENSE.md
        if base == "license":
            for name in ["LICENSE.md", "LICENSE"]:
                path = os.path.join(project_root, name)
                if os.path.exists(path):
                    return path

        # Special case: citation -> CITATION.cff
        if base == "citation":
            path = os.path.join(project_root, "CITATION.cff")
            if os.path.exists(path):
                return path

        # Special case: security -> SECURITY.md
        if base == "security":
            path = os.path.join(project_root, "SECURITY.md")
            if os.path.exists(path):
                return path
            path = os.path.join(project_root, ".github", "SECURITY.md")
            if os.path.exists(path):
                return path

        # user-guide/ pages -> user_guide/ with potential numeric prefixes
        if base.startswith("user-guide/"):
            page_name = base.replace("user-guide/", "")
            user_guide_dir = os.path.join(project_root, "user_guide")
            if os.path.isdir(user_guide_dir):
                # Look for file with or without numeric prefix
                for filename in os.listdir(user_guide_dir):
                    if filename.endswith(".qmd"):
                        # Strip numeric prefix (e.g., "01-intro.qmd" -> "intro")
                        name_part = filename[:-4]  # Remove .qmd
                        if "-" in name_part and name_part.split("-", 1)[0].isdigit():
                            name_part = name_part.split("-", 1)[1]
                        if name_part == page_name:
                            return os.path.join(user_guide_dir, filename)

        # recipes/ pages -> recipes/ in project root
        if base.startswith("recipes/"):
            page_name = base.replace("recipes/", "")
            recipes_dir = os.path.join(project_root, "recipes")
            if os.path.isdir(recipes_dir):
                # Look for file with or without numeric prefix
                for filename in os.listdir(recipes_dir):
                    if filename.endswith(".qmd"):
                        name_part = filename[:-4]
                        if "-" in name_part and name_part.split("-", 1)[0].isdigit():
                            name_part = name_part.split("-", 1)[1]
                        if name_part == page_name:
                            return os.path.join(recipes_dir, filename)

        # index.html -> README.md
        if base == "index":
            path = os.path.join(project_root, "README.md")
            if os.path.exists(path):
                return path

        return None

    modified_count = 0

    for html_file in all_html_files:
        rel_path = os.path.relpath(html_file, "_site")

        # Skip homepage - no metadata display needed
        if rel_path == "index.html":
            continue

        # Determine if this is an auto-generated page
        is_auto_generated = any(
            rel_path.startswith(prefix) for prefix in auto_generated_prefixes
        ) or rel_path in ("changelog.html", "skills.html")

        # Find the original source file in project root
        source_file = None
        if not is_auto_generated:
            source_file = find_original_source(rel_path)

        # Get file dates
        modified_date = ""
        created_date = ""

        # Parse frontmatter once (used for dates and author)
        frontmatter = {}
        if source_file and os.path.exists(source_file):
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        import yaml

                        try:
                            frontmatter = yaml.safe_load(parts[1]) or {}
                        except Exception:
                            pass
            except Exception:
                pass

        if is_auto_generated:
            # Auto-generated: use build timestamp
            modified_date = build_timestamp
        elif source_file and os.path.exists(source_file):
            # Check frontmatter for last_update override (like Docusaurus)
            # Format: last_update: {date: "2024-01-15", author: "Name"}
            # Or: last_update: {date: "2024-01-15T10:30:00Z"}
            last_update = frontmatter.get("last_update", {})
            if isinstance(last_update, dict) and last_update.get("date"):
                from datetime import datetime

                date_str = str(last_update["date"])
                try:
                    # Try ISO format first
                    if "T" in date_str:
                        modified_date = date_str
                    else:
                        # Parse date-only and add time
                        dt = datetime.fromisoformat(date_str)
                        modified_date = dt.isoformat()
                except Exception:
                    pass

            # Check frontmatter for date_created override
            date_created = frontmatter.get("date_created")
            if date_created:
                from datetime import datetime

                date_str = str(date_created)
                try:
                    if "T" in date_str:
                        created_date = date_str
                    else:
                        dt = datetime.fromisoformat(date_str)
                        created_date = dt.isoformat()
                except Exception:
                    pass

            # Fall back to git dates if not in frontmatter
            if not modified_date or not created_date:
                try:
                    import subprocess

                    if not modified_date:
                        # Run git from project root
                        result = subprocess.run(
                            ["git", "log", "-1", "--format=%aI", "--", source_file],
                            cwd=project_root,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            modified_date = result.stdout.strip()

                    if not created_date:
                        # Creation date (first commit)
                        result = subprocess.run(
                            [
                                "git",
                                "log",
                                "--diff-filter=A",
                                "--follow",
                                "--format=%aI",
                                "--",
                                source_file,
                            ],
                            cwd=project_root,
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            lines = result.stdout.strip().split("\n")
                            created_date = lines[-1].strip()
                except Exception:
                    pass

            # Fallback to mtime
            if not modified_date:
                from datetime import datetime

                mtime = os.path.getmtime(source_file)
                modified_date = datetime.fromtimestamp(mtime).isoformat()
        else:
            # No source file found - skip metadata for this page
            continue

        # Parse author from frontmatter (already loaded above)
        author_name = ""
        author_image = ""
        author_url = ""

        if show_author and not is_auto_generated and source_file:
            # Check last_update for author override
            last_update = frontmatter.get("last_update", {})
            if isinstance(last_update, dict) and last_update.get("author"):
                author_name = str(last_update["author"])

            # Fall back to regular author field
            if not author_name:
                author = frontmatter.get("author")
                if isinstance(author, str):
                    author_name = author
                elif isinstance(author, dict):
                    author_name = author.get("name", "")
                    author_image = author.get("image", "")
                    author_url = author.get("url", "")

            # Look up author details from config if not in frontmatter
            if author_name and not author_image:
                config_author = author_lookup.get(author_name, {})
                if not author_image:
                    author_image = config_author.get("image", "")
                    # Try GitHub avatar if homepage is GitHub
                    if not author_image:
                        github = config_author.get("github", "")
                        if github:
                            author_image = f"https://github.com/{github}.png"
                        elif "github.com" in config_author.get("homepage", ""):
                            # Extract username from GitHub URL
                            hp = config_author.get("homepage", "")
                            match = re.search(r"github\.com/([^/]+)", hp)
                            if match:
                                author_image = f"https://github.com/{match.group(1)}.png"
                if not author_url:
                    author_url = config_author.get("homepage", "")

        # Build meta tags
        meta_tags = []
        if modified_date:
            meta_tags.append(f'<meta name="gd-page-modified" content="{modified_date}">')
        if created_date:
            meta_tags.append(f'<meta name="gd-page-created" content="{created_date}">')
        if is_auto_generated:
            meta_tags.append('<meta name="gd-auto-generated" content="true">')
        if author_name:
            meta_tags.append(f'<meta name="gd-page-author" content="{author_name}">')
        if author_image:
            meta_tags.append(f'<meta name="gd-page-author-image" content="{author_image}">')
        if author_url:
            meta_tags.append(f'<meta name="gd-page-author-url" content="{author_url}">')

        if not meta_tags:
            continue

        # Inject meta tags in <head>
        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Insert after <head> opening tag
        meta_block = "\n".join(meta_tags)
        new_content = html_content.replace("<head>", f"<head>\n{meta_block}", 1)

        if new_content != html_content:
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            modified_count += 1

    print(f"Injected page metadata in {modified_count} HTML files")


inject_page_metadata()


# Fix page-metadata.js script paths for subdirectory pages
# (This runs after injection because inject_page_metadata runs after fix_script_paths)
def fix_page_metadata_script_paths():
    """Fix page-metadata.js paths in subdirectory HTML files."""
    fixed_count = 0

    for html_file in all_html_files:
        rel_path = os.path.relpath(html_file, "_site")
        depth = rel_path.count(os.sep)

        if depth == 0:
            continue

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        prefix = "../" * depth
        old_script = '<script src="page-metadata.js"></script>'
        new_script = f'<script src="{prefix}page-metadata.js"></script>'

        if old_script in content:
            content = content.replace(old_script, new_script)
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(content)
            fixed_count += 1

    if fixed_count > 0:
        print(f"Fixed page-metadata.js paths in {fixed_count} subdirectory pages")


fix_page_metadata_script_paths()


# ============================================================================
# Generate Markdown (.md) versions of each page
# ============================================================================
# Uses Quarto's bundled pandoc to convert the main content area of each
# rendered HTML page to GitHub-Flavored Markdown.  The resulting .md files
# live alongside the .html files in _site/ and are used by the copy-page
# widget (copy to clipboard / view as plain Markdown).


def _postprocess_markdown_content(md_content: str, rel: str) -> str:
    """Apply markdown cleanup and link normalization after pandoc conversion."""

    # Decode HTML entities that may have been double-encoded or improperly handled.
    # This fixes issues like: &rsquo; -> ', &ldquo; -> ", etc.
    md_content = html.unescape(md_content)

    # Fix common UTF-8 mojibake sequences (UTF-8 bytes interpreted as Latin-1).
    # When UTF-8 bytes are incorrectly decoded as Latin-1, we get mojibake patterns.
    # E.g., U+2019 (') is bytes E2 80 99 in UTF-8, but decoded as Latin-1 becomes
    # the three characters U+00E2 U+20AC U+2122, which looks like: â€™
    mojibake_fixes = {
        "\u00e2\u20ac\u2122": "\u2019",  # Right single quotation mark
        "\u00e2\u20ac\u009c": "\u201c",  # Left double quotation mark
        "\u00e2\u20ac\u009d": "\u201d",  # Right double quotation mark
        "\u00e2\u20ac\u0093": "\u2013",  # En dash
        "\u00e2\u20ac\u0094": "\u2014",  # Em dash
        # Alternate mojibake form with C1 control characters.
        "\u00e2\u0080\u0099": "\u2019",
        "\u00e2\u0080\u009c": "\u201c",
        "\u00e2\u0080\u009d": "\u201d",
        "\u00e2\u0080\u0093": "\u2013",
        "\u00e2\u0080\u0094": "\u2014",
    }
    for mojibake, correct in mojibake_fixes.items():
        md_content = md_content.replace(mojibake, correct)

    # Normalize typography to plain ASCII for robust display/copy across
    # environments that may not preserve UTF-8 metadata for raw .md files.
    typography_fixes = {
        "\u2018": "'",  # Left single quotation mark
        "\u2019": "'",  # Right single quotation mark
        "\u201c": '"',  # Left double quotation mark
        "\u201d": '"',  # Right double quotation mark
        "\u2013": "-",  # En dash
        "\u2014": "--",  # Em dash
    }
    for src, dst in typography_fixes.items():
        md_content = md_content.replace(src, dst)

    # Remove standalone Source links (HTML and markdown forms).
    md_content = re.sub(
        r"^\s*<a\s+[^>]*>\s*source\s*</a>\s*\n?",
        "",
        md_content,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    md_content = re.sub(
        r"^\s*\[source\]\([^\n)]+\)\s*\n?",
        "",
        md_content,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Convert simple HTML anchors to markdown links.
    # Keep this conservative: only convert when anchor text has no nested tags.
    def _anchor_to_md(m):
        href = m.group("href").strip()
        text = m.group("text")
        if "<" in text or ">" in text:
            return m.group(0)
        text = html.unescape(text).strip()
        if not text:
            return m.group(0)
        return f"[{text}]({href})"

    md_content = re.sub(
        r'<a\s+[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>',
        _anchor_to_md,
        md_content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Normalize parameter signature artifacts created by adjacent code spans.
    # These can appear in various formats depending on how pandoc combined the spans.
    # Pattern 1: `name``:`` ``type`` ``=`` ``default`` - full three-part with optional closing backtick
    md_content = re.sub(
        r"`([^`\n]+)``:``\s*``([^`\n]+)``\s*``=``\s*``([^`]+?)``?",
        r"`\1`: `\2` = `\3`",
        md_content,
    )
    # Pattern 2: `name``:`` ``type`` - just name and type
    md_content = re.sub(
        r"`([^`\n]+)``:``\s*``([^`\n]+)``",
        r"`\1`: `\2`",
        md_content,
    )

    # Remove leftover HTML div wrappers that pandoc preserved.
    md_content = re.sub(
        r"^<div[^>]*>\s*$",
        "",
        md_content,
        flags=re.MULTILINE,
    )
    md_content = re.sub(
        r"^</div>\s*$",
        "",
        md_content,
        flags=re.MULTILINE,
    )

    # Remove leftover <span> tags with parameter/annotation classes.
    md_content = re.sub(
        r'<span\s+class="parameter-[^"]*"[^>]*>(.*?)</span>',
        r"\1",
        md_content,
    )

    # Rewrite internal .html links to .md (relative paths only).
    md_content = re.sub(
        r"\]\((\.\./[^)]*?)\.html(\)?)",
        r"](\1.md\2",
        md_content,
    )
    # Also in the same directory.
    md_content = re.sub(
        r"\]\(([A-Za-z0-9_][^):/]*?)\.html(\)?)",
        r"](\1.md\2",
        md_content,
    )

    # Simplify redundant ../current_dir/ paths to ./
    file_dir = os.path.dirname(rel)
    if file_dir:
        escaped = re.escape("../" + file_dir + "/")
        md_content = re.sub(
            r"\]\(" + escaped + r"([^)]+)\)",
            r"](\1)",
            md_content,
        )

    # Remove leftover <span> tags (screen-reader, callout-icon, etc.)
    md_content = re.sub(
        r'<span\s+class="[^"]*">(.*?)</span>',
        r"\1",
        md_content,
    )
    # Remove empty <i> tags (callout icons)
    md_content = re.sub(r"<i[^>]*></i>", "", md_content)

    # Clean up excessive blank lines (3+ → 2)
    md_content = re.sub(r"\n{4,}", "\n\n\n", md_content)

    # Strip trailing whitespace
    md_content = md_content.strip() + "\n"

    return md_content


def generate_markdown_pages():
    """
    Create a .md companion for every .html page in _site/.

    Steps for each page:
      1. Extract the <main id="quarto-document-content"> inner HTML.
      2. Strip navigation-only elements (prev/next links, breadcrumbs).
      3. Replace _repr_html_ output blocks with a text placeholder.
      4. Pipe the HTML fragment through ``quarto pandoc -f html -t gfm``.
      5. Write the result as a .md file next to the original .html.
    """
    import shutil
    import subprocess

    # Verify quarto pandoc is available
    pandoc_cmd = shutil.which("quarto")
    if pandoc_cmd is None:
        print("Warning: 'quarto' not found on PATH; skipping .md generation")
        return

    print("Generating Markdown (.md) pages...")
    generated = 0
    errors = 0

    for html_file in all_html_files:
        rel = os.path.relpath(html_file, "_site")

        # Skip search.json and other non-page files
        if not html_file.endswith(".html"):
            continue

        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()

            # ── 1. Extract main content ──────────────────────────────────
            main_match = re.search(
                r'<main\s+class="content"[^>]*>(.*?)</main>',
                content,
                re.DOTALL,
            )
            if not main_match:
                continue  # No main content (e.g., search page)

            main_html = main_match.group(1)

            # ── 2. Strip nav elements & boilerplate ──────────────────────
            # Remove page-navigation (prev/next links)
            main_html = re.sub(
                r'<nav\s+class="page-navigation".*?</nav>',
                "",
                main_html,
                flags=re.DOTALL,
            )
            # Remove quarto-title-meta block (empty metadata div)
            main_html = re.sub(
                r'<div\s+class="quarto-title-meta">.*?</div>\s*',
                "",
                main_html,
                flags=re.DOTALL,
            )

            # Unwrap the title-block-header: extract just the title heading
            title_match = re.search(
                r'<header[^>]*class="quarto-title-block[^"]*"[^>]*>'
                r'.*?<div\s+class="quarto-title">\s*'
                r"(<h[12][^>]*>)(.*?)(</h[12]>)"
                r".*?</header>",
                main_html,
                re.DOTALL,
            )
            if title_match:
                # Extract the heading text (strip inline HTML styling like type badges)
                heading_tag_open = title_match.group(1)
                heading_inner = title_match.group(2)
                heading_tag_close = title_match.group(3)
                # Remove inline <span> badges (class/method/function type labels)
                heading_inner = re.sub(
                    r'<span\s+style="[^"]*border-style:\s*solid[^"]*">.*?</span>',
                    "",
                    heading_inner,
                    flags=re.DOTALL,
                )
                clean_title = f"{heading_tag_open}{heading_inner.strip()}{heading_tag_close}"
                main_html = (
                    main_html[: title_match.start()] + clean_title + main_html[title_match.end() :]
                )

            # Unwrap Quarto code-with-filename wrappers — extract the actual code block
            main_html = re.sub(
                r'<div\s+class="code-with-filename">\s*'
                r'<div\s+class="code-with-filename-file">\s*<pre><strong>(.*?)</strong></pre>\s*</div>\s*'
                r'<div\s+class="code-copy-outer-scaffold">\s*',
                r"<p><strong>\1</strong></p>\n",
                main_html,
                flags=re.DOTALL,
            )

            # Strip code-copy-outer-scaffold wrappers (keep inner code block)
            main_html = re.sub(
                r'<div\s+class="code-copy-outer-scaffold">\s*',
                "",
                main_html,
            )
            # Remove the copy nav + buttons (gd-code-nav and legacy code-copy-button)
            main_html = re.sub(
                r'<nav\s+class="gd-code-nav">.*?</nav>',
                "",
                main_html,
                flags=re.DOTALL,
            )
            main_html = re.sub(
                r'<button\s+title="Copy to [Cc]lipboard"[^>]*>.*?</button>',
                "",
                main_html,
                flags=re.DOTALL,
            )

            # Strip USAGE/SOURCE row div (API reference pages)
            main_html = re.sub(
                r'<div\s+class="usage-source-row"[^>]*>.*?</div>',
                "",
                main_html,
                flags=re.DOTALL,
            )

            # Remove source-link anchors
            main_html = re.sub(
                r'<a[^>]*class="source-link"[^>]*>.*?</a>',
                "",
                main_html,
                flags=re.DOTALL,
            )

            # Add language hint to sourceCode blocks for pandoc
            # Quarto renders `class="sourceCode python"` on the pre/code and
            # `data-filename="..."` on the wrapper div.  We extract the language
            # and rewrite to `<pre><code class="language-python">` so pandoc
            # emits ``` python fences.
            def _rewrite_code_block(m):
                full = m.group(0)
                # Try extracting lang from <pre class="sourceCode yaml ...">
                lang_m = re.search(r'<pre\s+class="sourceCode\s+(\w+)', full)
                lang = lang_m.group(1) if lang_m else ""
                # Extract the inner <code>...</code>
                code_m = re.search(r"(<code[^>]*>)(.*?)(</code>)", full, re.DOTALL)
                if not code_m:
                    return full
                code_content = code_m.group(2)
                if lang:
                    return f'<pre><code class="language-{lang}">{code_content}</code></pre>'
                return f"<pre><code>{code_content}</code></pre>"

            main_html = re.sub(
                r'<div\s+[^>]*class="sourceCode[^"]*"[^>]*>\s*<pre[^>]*>.*?</pre>\s*</div>',
                _rewrite_code_block,
                main_html,
                flags=re.DOTALL,
            )

            # Clean up trailing </div> from code-with-filename and scaffold wrappers
            # These are orphaned closing divs after we stripped the opening wrappers.
            # Count and fix: each code-with-filename wrapper contributes 2 extra </div>
            # This is tricky with regex, so we do a simpler approach: just close the
            # remaining unmatched divs by stripping excess </div> at the end of sections.

            # ── 3. Handle _repr_html_ blocks ────────────────────────────
            # These are typically wrapped in a div with class "cell-output-display"
            # containing complex HTML tables/widgets that don't convert to Markdown.
            main_html = re.sub(
                r'<div\s+class="cell-output-display"[^>]*>.*?</div>\s*(?=</div>|<div|<section|<h[1-6]|$)',
                "<p><em>[Rich HTML output — view on the documentation site]</em></p>\n",
                main_html,
                flags=re.DOTALL,
            )

            # Strip section wrapper divs (pandoc passes them through as raw HTML)
            main_html = re.sub(
                r'<section\s+id="[^"]*"\s+class="[^"]*doc-section[^"]*">\s*',
                "",
                main_html,
            )
            main_html = re.sub(r"</section>\s*", "", main_html)

            # Convert Quarto callout divs to Markdown-friendly blockquotes.
            # The callout structure nests 5 divs deep, so we use a helper that
            # tracks div depth to find the correct closing tag.
            def _convert_callouts(html):
                result = []
                pos = 0
                while True:
                    start = html.find('<div class="callout ', pos)
                    if start == -1:
                        result.append(html[pos:])
                        break
                    result.append(html[pos:start])
                    # Walk forward from start, tracking div depth to find the outer close
                    depth = 0
                    i = start
                    end = len(html)
                    while i < end:
                        open_m = re.match(r"<div[\s>]", html[i:])
                        close_m = re.match(r"</div>", html[i:])
                        if open_m:
                            depth += 1
                            i += open_m.end()
                        elif close_m:
                            depth -= 1
                            i += close_m.end()
                            if depth == 0:
                                break
                        else:
                            i += 1
                    callout_html = html[start:i]
                    # Extract type
                    type_m = re.search(
                        r"callout-(tip|note|warning|important|caution)", callout_html
                    )
                    callout_type = type_m.group(1).capitalize() if type_m else "Note"
                    # Extract title text
                    title_m = re.search(
                        r'<div\s+class="callout-title-container[^"]*">\s*'
                        r"(?:<span[^>]*>[^<]*</span>)?\s*(.*?)\s*</div>",
                        callout_html,
                        re.DOTALL,
                    )
                    title_text = title_m.group(1).strip() if title_m else ""
                    # Extract body HTML
                    body_m = re.search(
                        r'<div\s+class="callout-body-container[^"]*">\s*(.*?)\s*</div>',
                        callout_html,
                        re.DOTALL,
                    )
                    body_html = body_m.group(1).strip() if body_m else ""
                    if title_text:
                        header = f"<p><strong>{callout_type}: {title_text}</strong></p>"
                    else:
                        header = f"<p><strong>{callout_type}</strong></p>"
                    result.append(f"<blockquote>{header}\n{body_html}</blockquote>")
                    pos = i
                return "".join(result)

            main_html = _convert_callouts(main_html)

            # Convert parameter definition lists to cleaner HTML before pandoc
            # Replace <dl><dt>...<dd> parameter markup with simple paragraph lists
            # that pandoc can convert to clean Markdown.
            def _param_dl_to_html(m):
                """Convert a <dl> block of parameters to simple HTML paragraphs."""
                dl_html = m.group(0)
                items = []
                dt_dd_pattern = re.compile(
                    r'<dt>.*?<span class="(?:parameter-name|doc-parameter-name)">\s*<strong>(.*?)</strong>\s*</span>'
                    r'(?:.*?<span class="(?:parameter-annotation|doc-parameter-annotation)">(.*?)</span>)?'
                    r'(?:.*?<span class="(?:parameter-default|doc-parameter-default)">(.*?)</span>)?'
                    r".*?</dt>\s*<dd>\s*(.*?)\s*</dd>",
                    re.DOTALL,
                )
                for dt_dd in dt_dd_pattern.finditer(dl_html):
                    name = dt_dd.group(1).strip().strip("`")
                    annotation = dt_dd.group(2) or ""
                    default = dt_dd.group(3) or ""
                    desc = dt_dd.group(4) or ""
                    # Clean HTML from description
                    desc = re.sub(r"</?p>", "", desc).strip()

                    sig = f"<strong>{name}</strong>"
                    if annotation:
                        sig += f" : <code>{annotation.strip()}</code>"
                    if default:
                        sig += f" = <code>{default.strip()}</code>"

                    line = f"<li>{sig}"
                    if desc:
                        line += f" &mdash; {desc}"
                    line += "</li>"
                    items.append(line)

                if items:
                    return "<ul>\n" + "\n".join(items) + "\n</ul>"
                return dl_html

            main_html = re.sub(
                r"<dl>.*?</dl>",
                _param_dl_to_html,
                main_html,
                flags=re.DOTALL,
            )

            # Remove remaining doc-description paragraphs' inline styles
            main_html = re.sub(
                r'<p\s+class="doc-description"[^>]*>',
                "<p><em>",
                main_html,
            )

            # Strip remaining anchor tags within code block spans (line links)
            main_html = re.sub(
                r'<a\s+href="#cb\d+-\d+"[^>]*></a>',
                "",
                main_html,
            )

            # Remove signature highlighting span classes (sig-name, sig-class etc.)
            main_html = re.sub(
                r'<span\s+class="(?:sig-name|sig-class|cn-none|cn-bool)">(.*?)</span>',
                r"\1",
                main_html,
            )

            # Remove parameter-* spans (parameter-name, doc-parameter-name, parameter-annotation, etc.)
            # Note: The HTML may have either 'parameter-*' or 'doc-parameter-*' class names
            main_html = re.sub(
                r'<span\s+class="(?:parameter-|doc-parameter-)[^"]*"[^>]*>(.*?)</span>',
                r"\1",
                main_html,
            )

            # Trim leading/trailing whitespace inside <code> tags (left by span removal)
            main_html = re.sub(
                r"<code>\s*(.*?)\s*</code>",
                r"<code>\1</code>",
                main_html,
            )

            # ── 4. Convert with pandoc ───────────────────────────────────
            result = subprocess.run(
                ["quarto", "pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
                input=main_html,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                print(f"  pandoc error for {rel}: {result.stderr.strip()[:200]}")
                errors += 1
                continue

            md_content = result.stdout
            # Debug: Check if post-processing is needed
            found_artifact = False
            if "``:``" in md_content:
                # Find the context around the artifact
                lines = md_content.split("\n")
                for i, line in enumerate(lines):
                    if "``:``" in line:
                        print(f"  DEBUG [{rel}:{i}]: Line with artifact = {repr(line[:150])}")
                        found_artifact = True
                        break
            md_content = _postprocess_markdown_content(md_content, rel)
            # Debug: Verify post-processing worked
            if "``:``" in md_content and found_artifact:
                lines = md_content.split("\n")
                for i, line in enumerate(lines):
                    if "``:``" in line:
                        print(f"  WARNING [{rel}:{i}]: After post-processing = {repr(line[:150])}")
                        break

            # ── 5. Write .md file ────────────────────────────────────────
            md_file = html_file.rsplit(".", 1)[0] + ".md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            generated += 1

        except subprocess.TimeoutExpired:
            print(f"  pandoc timeout for {rel}")
            errors += 1
        except Exception as e:
            print(f"  error processing {rel}: {e}")
            errors += 1

    print(f"Generated {generated} Markdown page(s) ({errors} error(s))")


if _gd_options.get("markdown_pages", True):
    generate_markdown_pages()


# ── Clean up skill.html ──────────────────────────────────────────────────────
# Quarto renders skill.md → skill.html despite the !skill.md exclusion in
# project.render when skill.md is also in project.resources.  The raw skill.md
# is served as-is; the rendered skills.html page is the intended viewer.
# Delete the spurious skill.html so it doesn't confuse users or agents.
_skill_html = os.path.join("_site", "skill.html")
if os.path.exists(_skill_html):
    os.remove(_skill_html)
    print("Removed spurious _site/skill.html (raw skill.md is served directly)")

# Fix links in skills.html that Quarto rewrote from skill.md → skill.html
_skills_page = os.path.join("_site", "skills.html")
if os.path.exists(_skills_page):
    with open(_skills_page, "r", encoding="utf-8") as f:
        _skills_content = f.read()
    _fixed = _skills_content.replace('href="./skill.html"', 'href="skill.md"')
    if _fixed != _skills_content:
        with open(_skills_page, "w", encoding="utf-8") as f:
            f.write(_fixed)
        print("Fixed skill.md link in skills.html")


# ══════════════════════════════════════════════════════════════════════════════
# STRIP COLGROUP TAGS FROM TABLES
# ══════════════════════════════════════════════════════════════════════════════
# Remove <colgroup> tags so browsers determine column widths based on content.

print("\nStripping <colgroup> tags from tables...")
colgroup_stripped = 0
for html_file in glob.glob("_site/**/*.html", recursive=True):
    try:
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        if "<colgroup>" in content:
            modified = strip_colgroup_tags(content)
            if modified != content:
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(modified)
                colgroup_stripped += 1
    except Exception as e:
        print(f"  Error processing {html_file}: {e}")

if colgroup_stripped > 0:
    print(f"   Stripped colgroup from {colgroup_stripped} file(s)")


# ══════════════════════════════════════════════════════════════════════════════
# SEO PROCESSING
# ══════════════════════════════════════════════════════════════════════════════
# Apply SEO enhancements to all HTML files (canonical URLs, meta descriptions,
# JSON-LD structured data, title templates, noindex for internal pages)

if _gd_options.get("seo_enabled", False):
    print("\n🔍 Applying SEO enhancements to HTML files...")
    seo_processed = 0
    seo_errors = 0

    for html_file in glob.glob("_site/**/*.html", recursive=True):
        try:
            # Get relative path from _site
            rel_path = os.path.relpath(html_file, "_site")

            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Apply all SEO processing
            modified_content = apply_seo_processing(content, rel_path)

            # Only write if content changed
            if modified_content != content:
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(modified_content)
                seo_processed += 1

        except Exception as e:
            print(f"  SEO error for {html_file}: {e}")
            seo_errors += 1

    print(f"   SEO enhancements applied to {seo_processed} page(s) ({seo_errors} errors)")
else:
    print("\n🔍 SEO processing: disabled")


# ══════════════════════════════════════════════════════════════════════════════
# I18N — INJECT TRANSLATION BUNDLE
# ══════════════════════════════════════════════════════════════════════════════
# Inject a <meta name="gd-i18n"> tag containing the JSON translations bundle
# and, for RTL languages, set dir="rtl" on the <html> element.

_i18n_bundle = _gd_options.get("i18n")
_i18n_rtl = _gd_options.get("rtl", False)
_i18n_language = _gd_options.get("language", "en")

if _i18n_bundle and _i18n_language != "en":
    import html as _html_mod

    _i18n_json = json.dumps(_i18n_bundle, ensure_ascii=False, separators=(",", ":"))
    # Escape for safe embedding in an HTML attribute
    _i18n_escaped = _html_mod.escape(_i18n_json, quote=True)
    _i18n_meta = f'<meta name="gd-i18n" content="{_i18n_escaped}">'
    if _i18n_rtl:
        _i18n_meta += '\n<meta name="gd-rtl" content="true">'

    print(f"\n🌐 Injecting i18n translations (language={_i18n_language}, rtl={_i18n_rtl})...")
    _i18n_count = 0
    for html_file in glob.glob("_site/**/*.html", recursive=True):
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                content = f.read()

            modified = content.replace("<head>", f"<head>\n{_i18n_meta}", 1)

            # Set dir="rtl" on <html> element for RTL languages
            if _i18n_rtl:
                modified = re.sub(
                    r"<html\b([^>]*)>",
                    r'<html\1 dir="rtl">',
                    modified,
                    count=1,
                )

            if modified != content:
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(modified)
                _i18n_count += 1
        except Exception as e:
            print(f"  i18n error for {html_file}: {e}")

    print(f"   Injected i18n meta in {_i18n_count} page(s)")
else:
    if _i18n_language != "en":
        print(f"\n🌐 i18n: language={_i18n_language} but no translation bundle found")
    else:
        print("\n🌐 i18n: using default language (en)")
