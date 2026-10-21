from __future__ import annotations

import glob
import json
import os
import re
import sys


def _configure_stdio_for_unicode() -> None:
    """Use UTF-8 for console output when the platform default is narrow (e.g. cp1252)."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_stdio_for_unicode()

# Skip post-render processing during freeze-only renders
if os.environ.get("GD_FREEZE_ONLY"):
    print("Skipping post-render (freeze-only mode)")
    raise SystemExit(0)

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

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
    # Find the main signature code block: the first code block on the page
    # (id="cb1") *and* the one the renderer wrapped in a doc-signature div.
    # The enclosing div is what makes this a signature; without it the first
    # code block on a page is whatever ordinary block comes first, which on a
    # page whose signature is inline markup is usually an Examples doctest.
    cb1_pattern = re.compile(
        r'(<div class="doc-signature[^"]*">\s*'
        r'<div class="sourceCode" id="cb1">.*?<code class="sourceCode python">)'
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
        # Pattern: ClassName.method_name( or function_name( — or, for a TypedDict/Enum
        # page, just Name with nothing after it, since those never show call brackets.
        # The trailing group matches either the opening "(" of a call or the end of the
        # line, so a bare name is still caught without also matching a name that is
        # followed by anything else (which never happens: this block only ever holds a
        # signature line, and a signature line's leading name is always either called,
        # in which case "(" comes right after it, or not, in which case nothing does).
        # Uses re.MULTILINE so ^ matches each line (important for @overload signatures)
        sig_name_pattern = re.compile(
            r'^(<span class="va">)(\w+)(</span>)(<span class="op">\.</span>)?'
            r'(<span class="va">)?(\w+)?(</span>)?(\(|$)',
            re.MULTILINE,
        )

        def enhance_sig_name(m):
            # The final group is "(" for a call, or "" at the end of a bracket-less
            # TypedDict/Enum line; either way it belongs straight after the name.
            trailing = m.group(8)
            # If there's a dot, it's ClassName.method_name
            if m.group(4):  # Has dot
                class_name = m.group(2)
                method_name = m.group(6) or ""
                return (
                    f'<span class="sig-class">{class_name}</span>'
                    f'<span class="op">.</span>'
                    f'<span class="sig-name">{method_name}</span>{trailing}'
                )
            else:
                # Just function_name( or, bracket-less, just Name
                func_name = m.group(2)
                return f'<span class="sig-name">{func_name}</span>{trailing}'

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

    # Re-highlight the signature with Pygments for better syntax coloring
    content = highlight_signature_with_pygments(content)

    # Convert back to lines for line-by-line processing
    content = content.splitlines(keepends=True)

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

    content = content_str.splitlines(keepends=True)

    # Add separator lines between class details and individual members,
    # and between individual member sections.
    # - Thin solid line after the Methods/Attributes summary table (before first member section)
    # - Dotted line between each individual member section
    for i, line in enumerate(content):
        # Individual members render as `level3` sections.
        if "<section id=" in line and 'class="level3"' in line:
            # Check if the previous non-blank line ends a table (</table> in </section>)
            # or closes another member section
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

    with open(html_file, "w", encoding="utf-8") as file:
        file.writelines(content)


print("Finished processing all files")
print("##GD:PASS:Reference pages processed", flush=True)

all_html_files = glob.glob("_site/**/*.html", recursive=True)


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
print("##GD:PASS:Version badge injected", flush=True)


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
print("##GD:PASS:Sidebar collapse disabled", flush=True)


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

        # Fix version-selector.js path
        old_version_sel = '<script src="version-selector.js"></script>'
        new_version_sel = f'<script src="{prefix}version-selector.js"></script>'

        if old_version_sel in content:
            content = content.replace(old_version_sel, new_version_sel)
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

        # Fix details.js path
        old_details = '<script src="details.js"></script>'
        new_details = f'<script src="{prefix}details.js"></script>'

        if old_details in content:
            content = content.replace(old_details, new_details)
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
print("##GD:PASS:Script paths fixed", flush=True)


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
print("##GD:PASS:Sidebar body classes injected", flush=True)


def style_api_index_sidebar_item():
    """
    Apply inline styles to the 'API Index' / 'CLI Index' sidebar links so they visually separate
    from the monospace reference entries.

    Targets the `<a>` whose href ends with 'reference/index.html' (API index) or
    'reference/cli/index.html' (CLI index) and its parent `<div class="sidebar-item-container">`.
    """
    import re

    print("Styling reference index sidebar items...")
    count = 0
    font = (
        "&quot;Open Sans&quot;, -apple-system, BlinkMacSystemFont, "
        "&quot;Segoe UI&quot;, Roboto, &quot;Helvetica Neue&quot;, Arial, sans-serif"
    )
    # Match the API index link, or the CLI index link (the extra '/cli' segment is optional).
    href_pat = r'href="[^"]*reference/(?:cli/)?index\.html"'

    for html_file in all_html_files:
        rel_path = os.path.relpath(html_file, "_site")
        if not rel_path.startswith("reference" + os.sep) and rel_path != "reference":
            continue

        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the sidebar-item-container div immediately followed by the index link.
        match = re.search(
            r'(<div class="sidebar-item-container")(>\s*<a )([^>]*' + href_pat + r"[^>]*>)",
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

    print(f"Styled reference index sidebar items in {count} reference HTML files")


style_api_index_sidebar_item()
print("##GD:PASS:API Index sidebar styled", flush=True)
