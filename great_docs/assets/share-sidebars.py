"""
Copy each shared sidebar into the pages that show it (Quarto post-render)

Before rendering, Great Docs trims each long reference sidebar and adds a
template page that shows it in full (see `shared_sidebar.py`). This script
takes the full sidebar from the template, then gives every page that shows
the trimmed sidebar the full one, with the page's own link marked as current
and the sections around it open, as Quarto would. It also restores the
search crumbs Quarto takes from the sidebar and, unless the site is being
previewed, removes the template.

During `quarto preview`, a re-render of one page doesn't render the
template again, so the full sidebar is cached in the project.
"""

import json
import os
import re
from pathlib import Path, PurePosixPath

build_dir = Path.cwd()
manifest_path = build_dir / "_gd_sidebars.json"
cache_dir = build_dir / "_gd_sidebars"

_NAV_OPEN = re.compile(r'<nav id="quarto-sidebar"[^>]*>')
_NAV_TAG = re.compile(r"<(/?)nav[\s>]")
_UL_TAG = re.compile(r"<(/?)ul(?:\s[^>]*)?>")
_UL_COLLAPSED = re.compile(
    r'<ul id="(?P<id>[^"]+)" class="collapse list-unstyled sidebar-section depth\d+ ">'
)


def _nav_bounds(html):
    """Return where the sidebar's contents start and end, or `None`"""
    opening = _NAV_OPEN.search(html)
    if opening is None:
        return None
    depth = 1
    for tag in _NAV_TAG.finditer(html, opening.end()):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return opening.end(), tag.start()
    return None


def _offset(page):
    """Return the prefix Quarto gives links on a page to reach the site root"""
    depth = len(PurePosixPath(page).parts) - 1
    return "../" * depth if depth else "./"


def _rebase(nav, source, target):
    """Point the links of a sidebar taken from page `source` at page `target`"""
    old, new = _offset(source), _offset(target)
    if old == new:
        return nav
    return re.sub(r'(\s(?:href|src)=")' + re.escape(old), lambda m: m.group(1) + new, nav)


def _expand(nav, section_id):
    """Open a collapsed sidebar section, as Quarto does around the current page"""
    sid = re.escape(section_id)
    nav = re.sub(
        r'(<ul id="' + sid + r'" class="collapse list-unstyled sidebar-section depth\d+ )">',
        r'\1show">',
        nav,
        count=1,
    )
    return re.sub(
        r'(class="[^"]*?) collapsed(" data-bs-toggle="collapse" data-bs-target="#'
        + sid
        + r'"\s+role="navigation" aria-expanded=)"false"',
        r'\1\2"true"',
        nav,
    )


def _for_page(nav, template, page):
    """Return the template's sidebar as Quarto renders it on `page`"""
    nav = _rebase(nav, template, page)
    offset = _offset(page)
    targets = [offset + page]
    if page.endswith("/index.html"):
        targets.append(offset + page[: -len("index.html")])
    link = re.search(
        r'<a href="(?:'
        + "|".join(re.escape(t) for t in targets)
        + r')" class="sidebar-item-text sidebar-link(?=")',
        nav,
    )
    if link is None:
        return nav

    # The sections that hold the link, and the link's own section if it has one
    open_sections = []
    for tag in _UL_TAG.finditer(nav, 0, link.start()):
        if tag.group(1):
            open_sections.pop()
        else:
            open_sections.append(tag.group(0))
    next_item = nav.find("<li", link.end())
    own = _UL_COLLAPSED.search(nav, link.end(), next_item if next_item != -1 else len(nav))

    nav = nav[: link.end()] + " active" + nav[link.end() :]
    collapsed = [m.group("id") for m in map(_UL_COLLAPSED.match, open_sections) if m]
    if own:
        collapsed.append(own.group("id"))
    for section_id in collapsed:
        nav = _expand(nav, section_id)
    return nav


def _rendered_pages(output_dir):
    """Return the pages this render wrote, relative to the output, or `None` for all"""
    if os.environ.get("QUARTO_PROJECT_RENDER_ALL"):
        return None
    listing = os.environ.get("QUARTO_USE_FILE_FOR_PROJECT_OUTPUT_FILES")
    if listing:
        text = Path(listing).read_text(encoding="utf-8")
    else:
        text = os.environ.get("QUARTO_PROJECT_OUTPUT_FILES", "")
    root = output_dir.resolve()
    pages = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        path = (build_dir / line.strip()).resolve()
        try:
            pages.add(path.relative_to(root).as_posix())
        except ValueError:
            continue
    return pages or None


def _share(sidebar, output_dir, rendered):
    template = sidebar["template"]
    template_html = output_dir / template
    cached = cache_dir / f"{sidebar['id']}.html"
    if template_html.is_file():
        html = template_html.read_text(encoding="utf-8")
        bounds = _nav_bounds(html)
        if bounds is None:
            return 0
        nav = html[bounds[0] : bounds[1]]
        cache_dir.mkdir(exist_ok=True)
        cached.write_text(nav, encoding="utf-8")
        # `quarto preview` reads every page it rendered once this script is
        # done, so the template stays while Great Docs previews the site
        if not os.environ.get("GREAT_DOCS_PREVIEW"):
            template_html.unlink()
            template_html.with_suffix(".md").unlink(missing_ok=True)
    elif cached.is_file():
        nav = cached.read_text(encoding="utf-8")
    else:
        return 0

    count = 0
    for page in sidebar["pages"]:
        if rendered is not None and page not in rendered:
            continue
        path = output_dir / page
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        bounds = _nav_bounds(html)
        if bounds is None:
            continue
        html = html[: bounds[0]] + _for_page(nav, template, page) + html[bounds[1] :]
        path.write_text(html, encoding="utf-8")
        count += 1
    return count


def _restore_crumbs(output_dir, sidebars):
    """Give search entries the crumbs Quarto takes from the full sidebar"""
    path = output_dir / "search.json"
    if not path.is_file():
        return
    crumbs = {}
    for sidebar in sidebars:
        crumbs.update(sidebar["crumbs"])
    entries = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for entry in entries:
        trail = crumbs.get(str(entry.get("href", "")).split("#", 1)[0])
        if trail is not None and entry.get("crumbs") != trail:
            entry["crumbs"] = trail
            changed = True
    if changed:
        path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _drop_from_sitemap(output_dir, sidebars):
    path = output_dir / "sitemap.xml"
    if not path.is_file():
        return
    xml = path.read_text(encoding="utf-8")
    for sidebar in sidebars:
        xml = re.sub(
            r"\s*<url>\s*<loc>[^<]*/" + re.escape(sidebar["template"]) + r"</loc>.*?</url>",
            "",
            xml,
            flags=re.S,
        )
    path.write_text(xml, encoding="utf-8")


def main():
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir = build_dir / manifest["output_dir"]
    rendered = _rendered_pages(output_dir)
    for sidebar in manifest["sidebars"]:
        count = _share(sidebar, output_dir, rendered)
        if count:
            print(f"[post-render] Shared the {sidebar['id']} sidebar with {count} page(s)")
    _restore_crumbs(output_dir, manifest["sidebars"])
    _drop_from_sitemap(output_dir, manifest["sidebars"])


if __name__ == "__main__":
    main()
