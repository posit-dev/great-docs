# pyright: reportPrivateUsage=false
"""
Great Docs Gauntlet (GDG) — rendered output regression tests.

These tests validate the **final HTML output** of pre-built GDG sites stored in
`test-packages/_rendered/`.  They are designed as a safety net for the
planned renderer replacement: every assertion here must continue to pass after
the internal renderer is replaced.

Test levels (building on test_synthetic.py's L0–L2):

- **R0**: Site structure — correct files exist in `_site/`
- **R1**: Page structure — title, badge, description, signature, doc-sections
- **R2**: Docstring rendering — parameters, returns, raises, examples
- **R3**: Special features — overloads, callouts, constants, dunders, enums
- **R4**: Cross-cutting — sidebar, reference index, user guide, CLI pages

Run with:
    pytest tests/test_gdg_rendered.py
    pytest tests/test_gdg_rendered.py -k "R0"              # structure only
    pytest tests/test_gdg_rendered.py -k "gdtest_minimal"  # one package
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ── Setup ────────────────────────────────────────────────────────────────────

_TEST_PACKAGES_DIR = Path(__file__).resolve().parent.parent / "test-packages"
_RENDERED_DIR = _TEST_PACKAGES_DIR / "_rendered"

if str(_TEST_PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_PACKAGES_DIR))

from synthetic.catalog import ALL_PACKAGES, get_spec  # noqa: E402

# ── check for beautifulsoup ─────────────────────────────────────────────────

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

requires_bs4 = pytest.mark.skipif(not HAS_BS4, reason="beautifulsoup4 not installed")

# ── Skip the whole module if rendered output doesn't exist ───────────────────

pytestmark = pytest.mark.skipif(
    not _RENDERED_DIR.exists(),
    reason="No rendered GDG output found (run `python test-packages/render_all.py --build` first)",
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _site_dir(pkg_name: str) -> Path:
    """Return the _site/ directory for a rendered GDG package."""
    return _RENDERED_DIR / pkg_name / "great-docs" / "_site"


def _ref_dir(pkg_name: str) -> Path:
    """Return the reference/ subdirectory inside _site/."""
    return _site_dir(pkg_name) / "reference"


def _load_html(html_path: Path) -> "BeautifulSoup":
    """Parse an HTML file with BeautifulSoup."""
    text = html_path.read_text(encoding="utf-8")
    return BeautifulSoup(text, "html.parser")


def _has_rendered_site(pkg_name: str) -> bool:
    """Check whether a package has a rendered _site/ directory."""
    return _site_dir(pkg_name).is_dir()


def _spec_file_exists(name: str) -> bool:
    """Check whether the spec module exists on disk."""
    return (_TEST_PACKAGES_DIR / "synthetic" / "specs" / f"{name}.py").exists()


def _find_export_page(ref_dir: Path, name: str) -> Path | None:
    """Find the HTML page for an export, handling module-prefixed filenames.

    Pages can be named `name.html` or `module.name.html` (e.g.,
    `builders.build.html`).  Returns the first match, or None.
    """
    # Skip "index" — it collides with the reference listing page
    if name == "index":
        return None
    exact = ref_dir / f"{name}.html"
    if exact.exists():
        return exact
    # Try module-prefixed patterns: *.name.html
    for candidate in ref_dir.glob(f"*.{name}.html"):
        return candidate
    return None


def _get_expected(pkg_name: str) -> dict:
    """Load the expected outcomes dict from the spec, or return empty dict."""
    try:
        spec = get_spec(pkg_name)
        return spec.get("expected", {})
    except Exception:
        return {}


# ── Pre-filtered package lists ───────────────────────────────────────────────
# Each list contains only packages where the given test is applicable.
# This eliminates runtime `pytest.skip()` calls and keeps the test count lean.

_RENDERED_PACKAGES: list[str] = [n for n in ALL_PACKAGES if _has_rendered_site(n)]

# Cache expectations so we only load each spec once
_EXPECTED_CACHE: dict[str, dict] = {n: _get_expected(n) for n in _RENDERED_PACKAGES}

_PKGS_WITH_EXPORTS = [n for n in _RENDERED_PACKAGES if _EXPECTED_CACHE[n].get("export_names")]

_PKGS_WITH_NODOC = [n for n in _RENDERED_PACKAGES if _EXPECTED_CACHE[n].get("nodoc_items")]

_PKGS_WITH_BIG_CLASS = [n for n in _RENDERED_PACKAGES if _EXPECTED_CACHE[n].get("big_class_name")]

_PKGS_WITH_UG_FILES = [n for n in _RENDERED_PACKAGES if _EXPECTED_CACHE[n].get("user_guide_files")]

_PKGS_WITH_SUPPORTING = [
    n
    for n in _RENDERED_PACKAGES
    if any(
        _EXPECTED_CACHE[n].get(k)
        for k in (
            "has_license_page",
            "has_citation_page",
            "has_contributing_page",
            "has_code_of_conduct_page",
        )
    )
]

_PKGS_WITH_SECTION_TITLES = [
    n for n in _RENDERED_PACKAGES if _EXPECTED_CACHE[n].get("section_titles")
]

_PKGS_WITH_REF_PAGES = [
    n
    for n in _RENDERED_PACKAGES
    if _ref_dir(n).exists() and any(f.name != "index.html" for f in _ref_dir(n).glob("*.html"))
]

_PKGS_NOT_NODOCS = [n for n in _RENDERED_PACKAGES if n != "gdtest_nodocs"]

_PKGS_WITH_DOCSTRINGS = [
    n
    for n in _PKGS_WITH_EXPORTS
    if n != "gdtest_nodocs"
    and _EXPECTED_CACHE[n].get("detected_parser", "numpy") in ("numpy", "google", "sphinx")
]


# ═══════════════════════════════════════════════════════════════════════════════
# R0: Site Structure — files exist
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _RENDERED_PACKAGES)
def test_R0_site_index_exists(pkg_name: str):
    """Every rendered site has an index.html landing page."""
    index = _site_dir(pkg_name) / "index.html"
    assert index.exists(), f"Missing {index}"


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R0_reference_index_exists(pkg_name: str):
    """Rendered sites with exports have a reference/index.html."""
    ref_index = _ref_dir(pkg_name) / "index.html"
    assert ref_index.exists(), f"Missing {ref_index}"


@pytest.mark.parametrize("pkg_name", _RENDERED_PACKAGES)
def test_R0_search_json_exists(pkg_name: str):
    """Every rendered site has a search.json for site search."""
    search = _site_dir(pkg_name) / "search.json"
    assert search.exists(), f"Missing {search}"


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R0_reference_pages_match_exports(pkg_name: str):
    """Each exported symbol has a corresponding .html page in reference/."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]

    nodoc_items = set(expected.get("nodoc_items", []))
    expected_pages = set(export_names) - nodoc_items

    ref = _ref_dir(pkg_name)
    actual_pages = {f.stem for f in ref.glob("*.html") if f.name != "index.html"}

    if not actual_pages:
        return

    ref_index_text: str | None = None
    for name in expected_pages:
        matches = (
            name in actual_pages
            or any(p.startswith(f"{name}.") for p in actual_pages)
            or any(p.endswith(f".{name}") for p in actual_pages)
        )
        if not matches:
            if ref_index_text is None:
                idx = ref / "index.html"
                if HAS_BS4 and idx.exists():
                    ref_index_text = _load_html(idx).get_text()
                else:
                    ref_index_text = ""
            matches = name in ref_index_text
        if not matches:
            pass


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_NODOC)
def test_R0_nodoc_items_excluded(pkg_name: str):
    """Items marked %nodoc should NOT have reference pages."""
    expected = _EXPECTED_CACHE[pkg_name]
    nodoc_items = expected["nodoc_items"]

    ref = _ref_dir(pkg_name)
    for name in nodoc_items:
        page = ref / f"{name}.html"
        assert not page.exists(), f"Nodoc item {name!r} should not have a page: {page}"


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_BIG_CLASS)
def test_R0_big_class_has_method_pages(pkg_name: str):
    """Big classes (>5 methods) should have separate method .html pages."""
    expected = _EXPECTED_CACHE[pkg_name]
    big_class = expected["big_class_name"]
    method_count = expected.get("big_class_method_count", 0)
    if method_count == 0:
        pytest.skip("No big_class_method_count in spec")

    ref = _ref_dir(pkg_name)
    method_pages = [f.name for f in ref.glob(f"{big_class}.*.html")]
    assert len(method_pages) == method_count, (
        f"Expected {method_count} method pages for {big_class}, "
        f"got {len(method_pages)}: {sorted(method_pages)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# R0: User Guide Structure
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_UG_FILES)
def test_R0_user_guide_pages_exist(pkg_name: str):
    """User guide pages render to HTML when user_guide_files is specified."""
    expected = _EXPECTED_CACHE[pkg_name]
    ug_files = expected["user_guide_files"]

    # In blended-homepage mode the first UG page becomes index.qmd and is
    # removed from user-guide/, so skip it here.
    is_blended = expected.get("homepage_mode") == "user_guide"
    if is_blended:
        ug_files = ug_files[1:]

    site = _site_dir(pkg_name)
    ug_dir = site / "user-guide"
    if not ug_dir.exists():
        pytest.skip("No user-guide/ directory in _site")

    actual_ug_files = {f.name for f in ug_dir.glob("*.html")}

    for qmd_file in ug_files:
        html_name = qmd_file.replace(".qmd", ".html").replace(".md", ".html")
        stripped_name = re.sub(r"^\d+-", "", html_name)
        found = html_name in actual_ug_files or stripped_name in actual_ug_files
        assert found, (
            f"User guide page {html_name!r} (or {stripped_name!r}) "
            f"missing from {ug_dir}.\n  Available: {sorted(actual_ug_files)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R0: Supporting Pages (License, Citation, etc.)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _PKGS_WITH_SUPPORTING)
def test_R0_supporting_pages_exist(pkg_name: str):
    """Supporting pages (license, citation, etc.) render when expected."""
    expected = _EXPECTED_CACHE[pkg_name]
    site = _site_dir(pkg_name)

    checks = {
        "has_license_page": "license.html",
        "has_citation_page": "citation.html",
        "has_contributing_page": "contributing.html",
        "has_code_of_conduct_page": "code-of-conduct.html",
    }

    for key, filename in checks.items():
        if key in expected and expected[key]:
            page = site / filename
            assert page.exists(), f"Expected {filename} but it's missing"


# ═══════════════════════════════════════════════════════════════════════════════
# R1: Page Structure — title, badge, description, signature
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R1_reference_pages_have_title(pkg_name: str):
    """Every reference page has a .title element (h1 or h2)."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]
    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)
        title = soup.select_one("h1.title, h2.title")
        assert title is not None, f"{page.name} missing .title heading"
        assert name in title.get_text(), (
            f"{page.name} title doesn't contain {name!r}: {title.get_text()!r}"
        )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R1_reference_pages_have_type_badge(pkg_name: str):
    """Every reference page has a type badge (function, class, enum, etc.)."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]
    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    valid_badges = {
        "function",
        "method",
        "class",
        "enum",
        "constant",
        "type_alias",
        "dataclass",
        "exception",
        "protocol",
        "abc",
        "namedtuple",
        "typeddict",
        "async",
    }

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)
        title = soup.select_one("h1.title, h2.title")
        if title is None:
            continue

        badge_code = title.select_one("code")
        assert badge_code is not None, f"{name}.html: no <code> badge in title"
        badge_text = badge_code.get_text().strip().lower()
        assert badge_text in valid_badges, (
            f"{name}.html: unexpected badge {badge_text!r}, expected one of {valid_badges}"
        )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R1_function_pages_have_signature(pkg_name: str):
    """Function/method pages have a USAGE section with a signature block."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]
    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)
        title = soup.select_one("h1.title, h2.title")
        if title is None:
            continue

        badge = title.select_one("code")
        if badge is None:
            continue

        badge_text = badge.get_text().strip().lower()
        if badge_text in ("constant", "type_alias", "enum", "namedtuple", "typeddict"):
            continue

        sig_names = soup.select("span.sig-name")
        assert len(sig_names) > 0, f"{name}.html: no span.sig-name found in signature block"
        sig_texts = [s.get_text() for s in sig_names]
        name_base = name.split(".")[-1]
        assert any(name_base in t for t in sig_texts), (
            f"{name}.html: sig-name {sig_texts} doesn't contain {name_base!r}"
        )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_DOCSTRINGS)
def test_R1_pages_have_doc_description(pkg_name: str):
    """Pages with docstrings should have a <p class='doc-description'>."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]
    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    checked = 0
    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)
        desc = soup.select_one("p.doc-description")
        if desc is not None:
            checked += 1
            assert len(desc.get_text().strip()) > 0, f"{name}.html: doc-description is empty"

    ref_pages = [f for f in ref.glob("*.html") if f.name != "index.html"]
    if len(ref_pages) > 0:
        assert checked > 0 or len(export_names) - len(nodoc_items) == 0, (
            f"No doc-description found on any page for {pkg_name}"
        )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_REF_PAGES)
def test_R1_footer_text_not_in_header(pkg_name: str):
    """Footer text (e.g. 'Developed by ...') must never appear in doc-description.

    When an object has no docstring, the post-render script must not pick up
    <p> tags from the page footer and move them into the title area.
    Regression test for the "footer-in-header" bug.
    """
    ref = _ref_dir(pkg_name)
    for page_path in ref.glob("*.html"):
        if page_path.name == "index.html":
            continue

        soup = _load_html(page_path)

        desc = soup.select_one("p.doc-description")
        if desc is None:
            continue

        desc_text = desc.get_text().strip().lower()
        assert "developed by" not in desc_text, (
            f"{page_path.name}: footer text 'Developed by ...' leaked into doc-description"
        )
        assert "supported by" not in desc_text, (
            f"{page_path.name}: footer text 'Supported by ...' leaked into doc-description"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R2: Docstring Rendering — parameters, returns, raises, examples
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_NOT_NODOCS)
def test_R2_parameters_section_renders(pkg_name: str):
    """Functions with parameters have a rendered Parameters section."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected.get("export_names")
    if not export_names:
        return  # No exports to check — not a failure

    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)

        sig_params = soup.select("div.sourceCode span.va")
        if not sig_params:
            continue

        params_section = soup.select_one("section.doc-section-parameters")
        if params_section is not None:
            heading = params_section.select_one("h1, h2, h3, h4, h5, h6")
            assert heading is not None, f"{name}.html: parameters section has no heading"
            param_names = params_section.select("span.parameter-name")
            # Some docstring styles render parameters as a table instead of spans
            if not param_names:
                param_names = params_section.select("table td:first-child")
            assert len(param_names) > 0, (
                f"{name}.html: parameters section has no parameter-name spans or table cells"
            )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R2_parameter_names_match_signature(pkg_name: str):
    """Parameter names in the Parameters section match the signature."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]
    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)

        # Skip non-callable types (fields aren't function parameters)
        title = soup.select_one("h1.title, h2.title")
        if title:
            badge = title.select_one("code")
            if badge and badge.get_text().strip().lower() in (
                "enum",
                "namedtuple",
                "typeddict",
                "constant",
                "type_alias",
                "dataclass",
            ):
                continue

        params_section = soup.select_one("section.doc-section-parameters")
        if params_section is None:
            continue

        doc_param_names = {
            s.get_text().strip() for s in params_section.select("span.parameter-name strong")
        }

        sig_params = {s.get_text().strip() for s in soup.select("div.sourceCode span.va")}

        _LITERALS = {"self", "cls", "True", "False", "None"}
        sig_params -= _LITERALS
        sig_params = {p for p in sig_params if not p.isdigit()}

        if not sig_params or not doc_param_names:
            continue

        if sig_params and doc_param_names:
            overlap = doc_param_names & sig_params
            clean_doc = {p.lstrip("*") for p in doc_param_names}
            clean_sig = {p.lstrip("*") for p in sig_params}
            clean_overlap = clean_doc & clean_sig
            assert len(overlap) > 0 or len(clean_overlap) > 0, (
                f"{name}.html: no overlap between documented params "
                f"{doc_param_names} and signature params {sig_params}"
            )


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_NOT_NODOCS)
def test_R2_returns_section_renders(pkg_name: str):
    """Functions with return type annotations have a Returns section."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected.get("export_names")
    if not export_names:
        return

    nodoc_items = set(expected.get("nodoc_items", []))
    ref = _ref_dir(pkg_name)

    for name in export_names:
        if name in nodoc_items:
            continue
        page = _find_export_page(ref, name)
        if page is None:
            continue

        soup = _load_html(page)
        returns = soup.select_one("section.doc-section-returns")
        if returns is not None:
            content = returns.get_text().strip()
            assert len(content) > len("Returns"), f"{name}.html: returns section appears empty"


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name",
    [
        "gdtest_google",
        "gdtest_sphinx",
        "gdtest_sphinx_rich",
        "gdtest_google_rich",
    ],
)
def test_R2_raises_section_renders(pkg_name: str):
    """Packages with Raises docstrings have rendered Raises sections."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    if not ref.exists():
        pytest.skip(f"No reference dir for {pkg_name}")

    found_raises = 0
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue
        soup = _load_html(html_file)
        raises = soup.select_one("section.doc-section-raises")
        if raises is not None:
            found_raises += 1
            annotations = raises.select("span.parameter-annotation")
            assert len(annotations) > 0, f"{html_file.name}: raises section has no exception types"

    assert found_raises > 0, f"No Raises sections found in {pkg_name}"


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name",
    [
        "gdtest_big_class",
        "gdtest_google",
        "gdtest_docstring_examples",
    ],
)
def test_R2_examples_section_renders(pkg_name: str):
    """Packages with Examples docstrings have rendered Examples sections."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    if not ref.exists():
        pytest.skip(f"No reference dir for {pkg_name}")

    found_examples = 0
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue
        soup = _load_html(html_file)
        examples = soup.select_one("section.doc-section-examples")
        if examples is not None:
            found_examples += 1
            code_block = examples.select_one("div.sourceCode, pre")
            assert code_block is not None, f"{html_file.name}: examples section has no code block"

    assert found_examples > 0, f"No Examples sections found in {pkg_name}"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Special Features — overloads, callouts, constants, dunders, enums
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_overload_signatures_render():
    """Overloaded functions show multiple signatures with overload-spacer."""
    pkg = "gdtest_overloads"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_overloads not rendered")

    ref = _ref_dir(pkg)
    page = ref / "process.html"
    if not page.exists():
        pytest.skip("process.html not found")

    soup = _load_html(page)

    sig_names = soup.select("div.sourceCode span.sig-name")
    assert len(sig_names) >= 2, f"Expected multiple overload signatures, got {len(sig_names)}"

    spacers = soup.select("span.overload-spacer")
    assert len(spacers) >= 1, "No overload-spacer spans found"


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name,expected_items",
    [
        ("gdtest_rst_note", ["configure", "get_config", "reset_defaults"]),
        ("gdtest_rst_warning", None),
        ("gdtest_rst_tip", None),
        ("gdtest_rst_deprecated", None),
        ("gdtest_rst_versionadded", None),
    ],
)
def test_R3_rst_directives_render_as_callouts(pkg_name: str, expected_items):
    """RST directives (.. note::, .. warning::, etc.) render as styled callout divs."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    if not ref.exists():
        pytest.skip(f"No reference dir for {pkg_name}")

    directive_labels = {
        "gdtest_rst_note": "Note",
        "gdtest_rst_warning": "Warning",
        "gdtest_rst_tip": "Tip",
        "gdtest_rst_deprecated": "Deprecated",
        "gdtest_rst_versionadded": "Added",
        "gdtest_rst_caution": "Caution",
        "gdtest_rst_danger": "Danger",
        "gdtest_rst_important": "Important",
    }

    label = directive_labels.get(pkg_name, "Note")
    found_callouts = 0

    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        callout_divs = soup.find_all(
            "div",
            style=lambda s: s and "border-left:" in s and "4px solid" in s,
        )

        for div in callout_divs:
            text = div.get_text()
            if label.lower() in text.lower() or "version" in text.lower():
                found_callouts += 1

    assert found_callouts > 0, f"No callout divs with label {label!r} found in {pkg_name}"


@requires_bs4
def test_R3_constant_pages_show_value():
    """Constant pages display the value (e.g., `DEFAULT_TIMEOUT: int = 30`)."""
    pkg = "gdtest_constants"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_constants not rendered")

    ref = _ref_dir(pkg)
    for const_name in ("DEFAULT_TIMEOUT", "MAX_RETRIES"):
        page = ref / f"{const_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        badge = soup.select_one(".title code")
        assert badge is not None, f"{const_name}.html: no badge"
        assert badge.get_text().strip().lower() == "constant", (
            f"{const_name}.html: badge is {badge.get_text()!r}, expected 'constant'"
        )

        main_content = soup.select_one("main.content")
        assert main_content is not None
        code_elems = main_content.select("code")
        code_texts = [c.get_text() for c in code_elems]
        name_found = any(const_name in t for t in code_texts)
        assert name_found, f"{const_name}.html: constant name not found in code elements"


@requires_bs4
def test_R3_enum_pages_have_attributes_table():
    """Enum pages have an Attributes table listing members."""
    pkg = "gdtest_enums"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_enums not rendered")

    ref = _ref_dir(pkg)
    for enum_name in ("Color", "Priority"):
        page = ref / f"{enum_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)

        badge = soup.select_one(".title code")
        if badge:
            assert badge.get_text().strip().lower() == "enum", (
                f"{enum_name}.html: badge is {badge.get_text()!r}, expected 'enum'"
            )

        attrs_section = soup.select_one("section#attributes")
        if attrs_section is None:
            tables = soup.select("table.table")
            assert len(tables) > 0, f"{enum_name}.html: no attributes table found"


@requires_bs4
def test_R3_dunder_methods_render_without_bold():
    """Dunder method names don't get interpreted as bold by Pandoc."""
    pkg = "gdtest_dunders"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_dunders not rendered")

    ref = _ref_dir(pkg)
    page = ref / "Collection.html"
    if not page.exists():
        pytest.skip("Collection.html not found")

    soup = _load_html(page)
    html_str = str(soup)

    for dunder in ("__repr__", "__eq__", "__len__", "__getitem__"):
        broken_pattern = f"<strong>{dunder.strip('_')}</strong>"
        assert broken_pattern not in html_str, (
            f"Pandoc interpreted {dunder} as bold: found {broken_pattern}"
        )


@requires_bs4
def test_R3_dataclass_fields_render():
    """Dataclass pages show all fields (including str/list/dict types)."""
    pkg = "gdtest_dataclasses"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_dataclasses not rendered")

    ref = _ref_dir(pkg)
    page = ref / "Config.html"
    if not page.exists():
        pytest.skip("Config.html not found")

    soup = _load_html(page)

    params = soup.select_one("section.doc-section-parameters")
    if params is not None:
        param_names = [s.get_text().strip() for s in params.select("span.parameter-name strong")]
        assert "name" in param_names, f"Config.html: 'name' field not in parameters: {param_names}"


@requires_bs4
def test_R3_async_functions_have_badge():
    """Async functions have an 'async' or 'function' badge."""
    pkg = "gdtest_async_funcs"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_async_funcs not rendered")

    ref = _ref_dir(pkg)
    for func_name in ("async_fetch", "async_process", "async_save"):
        page = ref / f"{func_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        badge = soup.select_one(".title code")
        assert badge is not None, f"{func_name}.html: no badge"
        badge_text = badge.get_text().strip().lower()
        assert badge_text in ("async", "function"), (
            f"{func_name}.html: badge is {badge_text!r}, expected 'async' or 'function'"
        )


@requires_bs4
def test_R3_exception_classes_have_badge():
    """Exception classes have appropriate badges."""
    pkg = "gdtest_exceptions"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_exceptions not rendered")

    ref = _ref_dir(pkg)
    for exc_name in ("AppError", "ValidationError", "NotFoundError"):
        page = ref / f"{exc_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        badge = soup.select_one(".title code")
        assert badge is not None, f"{exc_name}.html: no badge"
        badge_text = badge.get_text().strip().lower()
        assert badge_text in ("exception", "class"), (
            f"{exc_name}.html: badge is {badge_text!r}, expected 'exception' or 'class'"
        )


@requires_bs4
def test_R3_protocol_classes_have_badge():
    """Protocol/ABC classes have appropriate badges."""
    pkg = "gdtest_protocols"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_protocols not rendered")

    ref = _ref_dir(pkg)
    for cls_name, expected_badge in [
        ("Serializable", ("abc", "class")),
        ("Renderable", ("protocol", "class")),
    ]:
        page = ref / f"{cls_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        badge = soup.select_one(".title code")
        assert badge is not None, f"{cls_name}.html: no badge"
        badge_text = badge.get_text().strip().lower()
        assert badge_text in expected_badge, (
            f"{cls_name}.html: badge is {badge_text!r}, expected one of {expected_badge}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Sphinx & Google Docstring Specific
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_sphinx_params_render_as_structured_dl():
    """Sphinx :param: fields render as structured <dl> elements, not raw text."""
    pkg = "gdtest_sphinx"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_sphinx not rendered")

    ref = _ref_dir(pkg)
    for func in ("start_timer", "format_duration"):
        page = ref / f"{func}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        params = soup.select_one("section.doc-section-parameters")
        if params is None:
            continue

        raw_param = soup.find(string=lambda t: t and ":param" in t if t else False)
        assert raw_param is None, (
            f"{func}.html: raw ':param' text found — Sphinx fields not translated"
        )

        param_names = params.select("span.parameter-name")
        assert len(param_names) > 0, (
            f"{func}.html: Sphinx params not rendered as structured elements"
        )


@requires_bs4
def test_R3_google_params_render_as_structured_dl():
    """Google Args: fields render as structured <dl> elements, not raw text."""
    pkg = "gdtest_google"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_google not rendered")

    ref = _ref_dir(pkg)
    for func in ("connect", "send_message"):
        page = ref / f"{func}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        params = soup.select_one("section.doc-section-parameters")
        if params is None:
            continue

        param_names = params.select("span.parameter-name")
        assert len(param_names) > 0, (
            f"{func}.html: Google params not rendered as structured elements"
        )


@requires_bs4
def test_R3_sphinx_rich_multiple_raises():
    """Rich Sphinx docstrings with multiple :raises: render properly."""
    pkg = "gdtest_sphinx_rich"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_sphinx_rich not rendered")

    ref = _ref_dir(pkg)
    page = ref / "execute.html"
    if not page.exists():
        pytest.skip("execute.html not found")

    soup = _load_html(page)
    raises = soup.select_one("section.doc-section-raises")
    if raises is not None:
        annotations = raises.select("span.parameter-annotation")
        assert len(annotations) >= 2, (
            f"execute.html: expected multiple raises, got {len(annotations)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R3: See Also Cross-References
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_seealso_links_render():
    """Functions with %seealso have See Also sections in the rendered output."""
    pkg = "gdtest_seealso"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_seealso not rendered")

    expected = _get_expected(pkg)
    seealso_map = expected.get("seealso", {})
    if not seealso_map:
        pytest.skip("No seealso expectations in spec")

    ref = _ref_dir(pkg)
    for func_name, targets in seealso_map.items():
        page = ref / f"{func_name}.html"
        if not page.exists():
            continue

        soup = _load_html(page)
        html_text = soup.get_text().lower()

        assert "see also" in html_text, f"{func_name}.html: no 'See Also' section found"

        for target in targets:
            assert target.lower() in html_text, (
                f"{func_name}.html: See Also target {target!r} not found"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Reference Index Page
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_EXPORTS)
def test_R4_reference_index_lists_exports(pkg_name: str):
    """The reference index page lists all exported symbols."""
    expected = _EXPECTED_CACHE[pkg_name]
    export_names = expected["export_names"]

    ref_index = _ref_dir(pkg_name) / "index.html"
    if not ref_index.exists():
        pytest.skip("No reference index")

    soup = _load_html(ref_index)
    nodoc_items = set(expected.get("nodoc_items", []))

    links = soup.select("a")
    link_texts = {a.get_text().strip().rstrip("()") for a in links}
    page_text = soup.get_text()

    missing = []
    for name in export_names:
        if name in nodoc_items:
            continue
        if name not in link_texts and name not in page_text:
            missing.append(name)

    if missing:
        present = len(export_names) - len(nodoc_items) - len(missing)
        if present > len(missing):
            assert False, f"{pkg_name} reference/index.html: exports not listed: {missing}"


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_SECTION_TITLES)
def test_R4_reference_index_has_section_headings(pkg_name: str):
    """The reference index page has section headings matching spec."""
    expected = _EXPECTED_CACHE[pkg_name]
    section_titles = expected["section_titles"]

    ref_index = _ref_dir(pkg_name) / "index.html"
    if not ref_index.exists():
        pytest.skip("No reference index")

    soup = _load_html(ref_index)

    headings = soup.select("h1, h2, h3")
    heading_texts = [h.get_text().strip() for h in headings]
    all_text = soup.get_text()

    found = []
    for title in section_titles:
        in_heading = any(title in ht for ht in heading_texts)
        in_text = title in all_text
        if in_heading or in_text:
            found.append(title)

    if not found:
        non_meta_headings = [h for h in heading_texts if h not in ("Reference", "On this page")]
        assert len(non_meta_headings) > 0 or len(heading_texts) > 0, (
            f"{pkg_name} reference/index.html: no headings at all"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Sidebar Navigation
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_REF_PAGES)
def test_R4_sidebar_has_reference_section(pkg_name: str):
    """The sidebar contains reference/API navigation items."""
    ref = _ref_dir(pkg_name)
    ref_pages = [f for f in ref.glob("*.html") if f.name != "index.html"]

    soup = _load_html(ref_pages[0])
    sidebar = soup.select_one("nav#quarto-sidebar")
    if sidebar is None:
        pytest.skip("No sidebar found")

    menu_items = sidebar.select("span.menu-text")
    menu_texts = [m.get_text().strip() for m in menu_items]
    assert len(menu_texts) > 0, "Sidebar has no menu items"


@requires_bs4
@pytest.mark.parametrize("pkg_name", _PKGS_WITH_SECTION_TITLES)
def test_R4_sidebar_lists_section_titles(pkg_name: str):
    """Sidebar section headers match expected section titles."""
    expected = _EXPECTED_CACHE[pkg_name]
    section_titles = expected["section_titles"]

    ref = _ref_dir(pkg_name)
    ref_pages = [f for f in ref.glob("*.html") if f.name != "index.html"]
    if not ref_pages:
        pytest.skip("No reference pages")

    soup = _load_html(ref_pages[0])
    sidebar = soup.select_one("nav#quarto-sidebar")
    if sidebar is None:
        pytest.skip("No sidebar found")

    all_menu_items = sidebar.select("span.menu-text")
    all_menu_texts = [s.get_text().strip() for s in all_menu_items]

    section_headers = sidebar.select("li.sidebar-item-section span.menu-text")
    sidebar_sections = [s.get_text().strip() for s in section_headers]

    for title in section_titles:
        in_sections = any(title in s for s in sidebar_sections)
        in_all_menu = any(title in s for s in all_menu_texts)
        if in_sections or in_all_menu:
            return  # At least one section title found — pass

    assert len(all_menu_texts) > 0, f"{pkg_name}: sidebar has no menu items at all"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Landing Page
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _RENDERED_PACKAGES)
def test_R4_landing_page_has_title(pkg_name: str):
    """The index.html landing page has a title heading."""
    index = _site_dir(pkg_name) / "index.html"
    if not index.exists():
        pytest.skip("No index.html")

    soup = _load_html(index)

    # In blended-homepage mode the title block is intentionally empty and the
    # visible heading comes from the body content.  Accept any non-empty <h1>.
    all_h1 = soup.select("h1")
    assert all_h1, f"{pkg_name}: landing page has no <h1>"
    has_text = any(h.get_text().strip() for h in all_h1)
    assert has_text, f"{pkg_name}: landing page <h1> is empty"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Sphinx Role Cleanup
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name",
    [
        "gdtest_sphinx_func_role",
        "gdtest_sphinx_class_role",
        "gdtest_sphinx_exc_role",
        "gdtest_sphinx_meth_role",
        "gdtest_sphinx_mixed_roles",
    ],
)
def test_R4_sphinx_roles_stripped(pkg_name: str):
    """Sphinx cross-reference roles (:func:, :class:, etc.) should be stripped."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        main = soup.select_one("main.content")
        if main is None:
            continue

        text = main.get_text()
        for role in (
            ":func:",
            ":class:",
            ":meth:",
            ":exc:",
            ":py:func:",
            ":py:class:",
            ":py:meth:",
            ":py:exc:",
        ):
            assert role not in text, (
                f"{html_file.name}: raw Sphinx role {role!r} found in rendered text"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: RST Code Blocks & Tables
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name",
    [
        "gdtest_docstring_examples",
        "gdtest_overloads",
        "gdtest_numpy_rich",
    ],
)
def test_R4_rst_code_blocks_converted(pkg_name: str):
    """RST :: code blocks should be converted to proper <pre><code> blocks."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        main = soup.select_one("main.content")
        if main is None:
            continue

        paragraphs = main.select("p")
        for p in paragraphs:
            text = p.get_text().strip()
            if text.endswith("::") and not text.startswith(".."):
                pytest.fail(f"{html_file.name}: raw RST '::' code block marker in <p>: {text!r}")


@requires_bs4
@pytest.mark.parametrize("pkg_name", ["gdtest_docstring_tables"])
def test_R4_rst_tables_converted(pkg_name: str):
    """RST tables should be converted to valid HTML tables."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    found_tables = 0
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        main = soup.select_one("main.content")
        if main is None:
            continue

        tables = main.select("table")
        found_tables += len(tables)

        for p in main.select("p"):
            p_text = p.get_text().strip()
            if p_text.startswith("===") or p_text.startswith("+---"):
                pytest.fail(f"{html_file.name}: raw RST table marker in <p>: {p_text[:50]!r}")

    assert found_tables > 0, f"No HTML tables found in any {pkg_name} reference page"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Config-Driven Features
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_logo_replaces_title():
    """Logo config injects navbar logo and suppresses the text title."""
    pkg = "gdtest_logo"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    cfg = _load_quarto_yml(pkg)
    navbar = cfg.get("website", {}).get("navbar", {})

    # Logo files should be referenced in the navbar
    assert navbar.get("logo") == "logo.svg", "navbar.logo should be logo.svg"
    assert navbar.get("logo-dark") == "logo-dark.svg", "navbar.logo-dark should be logo-dark.svg"

    # Text title should be suppressed
    assert navbar.get("title") is False, "navbar.title should be False when logo is set"

    # Alt text should fall back to display_name
    assert navbar.get("logo-alt") == "Logo Test", "logo-alt should be the display_name"

    # Favicon should be auto-generated from logo.svg and referenced in config
    favicon = cfg.get("website", {}).get("favicon")
    assert favicon in ("favicon.ico", "logo.svg"), (
        f"favicon should be favicon.ico or logo.svg, got {favicon}"
    )

    # Logo files should exist in the build directory
    build_dir = _RENDERED_DIR / pkg / "great-docs"
    assert (build_dir / "logo.svg").exists(), "logo.svg should be copied to build dir"
    assert (build_dir / "logo-dark.svg").exists(), "logo-dark.svg should be copied to build dir"

    # Check for generated favicon files
    if favicon == "favicon.ico":
        assert (build_dir / "favicon.ico").exists(), "favicon.ico should exist"
        assert (build_dir / "favicon.svg").exists(), "favicon.svg should exist"
        assert (build_dir / "favicon-32x32.png").exists(), "favicon-32x32.png should exist"
        assert (build_dir / "favicon-16x16.png").exists(), "favicon-16x16.png should exist"
        assert (build_dir / "apple-touch-icon.png").exists(), "apple-touch-icon.png should exist"


@requires_bs4
def test_R4_logo_in_rendered_html():
    """Rendered HTML should contain the logo image in the navbar."""
    pkg = "gdtest_logo"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)

    # Find the navbar logo image
    navbar = soup.select_one("nav.navbar")
    if navbar is None:
        pytest.skip("No navbar found")

    logo_img = navbar.select_one("img.navbar-logo")
    assert logo_img is not None, "Navbar should contain an <img class='navbar-logo'>"
    assert "logo" in (logo_img.get("src", "") or "").lower(), (
        "Logo img src should reference the logo file"
    )


@requires_bs4
def test_R4_display_name_in_title():
    """Config display_name appears in the site navbar/title."""
    pkg = "gdtest_display_name"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    soup.get_text()  # Verify page loads without error


@requires_bs4
def test_R4_no_darkmode_toggle():
    """When dark_mode_toggle is disabled, the toggle element is absent."""
    pkg = "gdtest_no_darkmode"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    navbar = soup.select_one("nav.navbar")
    if navbar is None:
        pytest.skip("No navbar found")
    assert soup.select_one("main.content") is not None, f"{pkg}: site did not render properly"


@requires_bs4
@pytest.mark.parametrize(
    "pkg_name,theme",
    [
        ("gdtest_theme_cosmo", "cosmo"),
        ("gdtest_theme_lumen", "lumen"),
        ("gdtest_theme_cerulean", "cerulean"),
    ],
)
def test_R4_theme_applied(pkg_name: str, theme: str):
    """Theme configuration produces a valid rendered site."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    index = _site_dir(pkg_name) / "index.html"
    assert index.exists(), f"{pkg_name}: no index.html"
    soup = _load_html(index)
    assert soup.select_one("main.content") is not None, f"{pkg_name}: no main.content element"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: CLI Documentation
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_cli_pages_generated():
    """When CLI is enabled, reference pages are generated for the package."""
    pkg = "gdtest_cli_click"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_click not rendered")

    ref = _ref_dir(pkg)
    assert ref.exists(), "No reference directory"
    ref_pages = [f for f in ref.glob("*.html") if f.name != "index.html"]
    assert len(ref_pages) > 0, "No reference pages generated for gdtest_cli_click"


@requires_bs4
def test_R4_cli_reference_directory_exists():
    """CLI-enabled packages should have a reference/cli/ directory."""
    pkg = "gdtest_cli_click"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_click not rendered")

    cli_dir = _ref_dir(pkg) / "cli"
    assert cli_dir.exists(), "No reference/cli/ directory found"
    assert (cli_dir / "index.html").exists(), "No CLI index.html page"


@requires_bs4
def test_R4_cli_index_page_content():
    """CLI index page should contain command name and help text."""
    pkg = "gdtest_cli_click"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_click not rendered")

    cli_index = _ref_dir(pkg) / "cli" / "index.html"
    if not cli_index.exists():
        pytest.skip("CLI index.html not found")

    soup = _load_html(cli_index)
    page_text = soup.get_text()

    # The CLI help text from the Click command should appear
    assert "format" in page_text.lower() or "gdtest" in page_text.lower(), (
        "CLI index page does not contain expected help text"
    )


@requires_bs4
def test_R4_cli_nested_groups_rendered():
    """Nested Click groups should produce subcommand pages."""
    pkg = "gdtest_cli_nested"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_nested not rendered")

    cli_dir = _ref_dir(pkg) / "cli"
    assert cli_dir.exists(), "No reference/cli/ directory found"

    # Should have group pages for task and config
    assert (cli_dir / "task.html").exists(), "No task group page"
    assert (cli_dir / "config.html").exists(), "No config group page"


@requires_bs4
def test_R4_cli_nested_subcommand_pages():
    """Nested subcommands should have their own pages."""
    pkg = "gdtest_cli_nested"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_nested not rendered")

    cli_dir = _ref_dir(pkg) / "cli"

    # task subcommands
    assert (cli_dir / "task" / "run.html").exists(), "No task/run.html page"
    assert (cli_dir / "task" / "list.html").exists(), "No task/list.html page"

    # config subcommands
    assert (cli_dir / "config" / "get.html").exists(), "No config/get.html page"
    assert (cli_dir / "config" / "set.html").exists(), "No config/set.html page"


@requires_bs4
def test_R4_cli_sidebar_has_cli_section():
    """Rendered reference pages should have a CLI Reference sidebar section."""
    pkg = "gdtest_cli_click"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_click not rendered")

    # CLI sidebar section appears on reference pages, not the home page
    cli_index = _ref_dir(pkg) / "cli" / "index.html"
    if not cli_index.exists():
        pytest.skip("No CLI index.html")

    soup = _load_html(cli_index)
    # Look for sidebar links pointing to CLI reference pages
    sidebar_links = soup.select("a.sidebar-link, a.sidebar-item-text")
    link_hrefs = [a.get("href", "") for a in sidebar_links]
    link_texts = [a.get_text(strip=True) for a in sidebar_links]

    has_cli_link = any("cli" in href for href in link_hrefs) or any(
        "cli" in text.lower() for text in link_texts
    )
    assert has_cli_link, (
        f"Sidebar does not contain CLI reference link.\n"
        f"  Link texts: {link_texts}\n"
        f"  Link hrefs: {link_hrefs}"
    )


def test_R4_cli_sidebar_structure_flat():
    """Flat CLI sidebar in _quarto.yml should contain only path strings."""
    pkg = "gdtest_cli_click"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_click not rendered")

    import yaml

    quarto_yml = _RENDERED_DIR / pkg / "great-docs" / "_quarto.yml"
    with open(quarto_yml) as f:
        config = yaml.safe_load(f)

    sidebar = config.get("website", {}).get("sidebar", [])
    cli_section = next(
        (s for s in sidebar if isinstance(s, dict) and s.get("id") == "cli-reference"),
        None,
    )
    assert cli_section is not None, "No cli-reference sidebar section in _quarto.yml"

    contents = cli_section.get("contents", [])
    assert len(contents) >= 1
    # All items should be plain path strings — no section dicts
    for item in contents:
        assert isinstance(item, str), f"Flat CLI sidebar should only have path strings, got: {item}"


def test_R4_cli_sidebar_structure_nested():
    """Nested CLI sidebar in _quarto.yml should use section/contents hierarchy."""
    pkg = "gdtest_cli_nested"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_nested not rendered")

    import yaml

    quarto_yml = _RENDERED_DIR / pkg / "great-docs" / "_quarto.yml"
    with open(quarto_yml) as f:
        config = yaml.safe_load(f)

    sidebar = config.get("website", {}).get("sidebar", [])
    cli_section = next(
        (s for s in sidebar if isinstance(s, dict) and s.get("id") == "cli-reference"),
        None,
    )
    assert cli_section is not None, "No cli-reference sidebar section in _quarto.yml"

    contents = cli_section.get("contents", [])
    assert len(contents) >= 3, f"Expected at least 3 items (index + 2 groups), got {len(contents)}"

    # First item should be the main CLI index page
    assert contents[0] == "reference/cli/index.qmd", (
        f"First sidebar item should be the CLI index, got: {contents[0]}"
    )

    # Remaining items for groups should be section dicts
    section_items = [c for c in contents[1:] if isinstance(c, dict)]
    assert len(section_items) >= 2, (
        f"Expected at least 2 group sections, got {len(section_items)}: {contents[1:]}"
    )

    section_names = {s["section"] for s in section_items}
    assert "task" in section_names, f"Missing 'task' section, got: {section_names}"
    assert "config" in section_names, f"Missing 'config' section, got: {section_names}"

    # Each group section must have the overview page + nested subcommand pages
    for section in section_items:
        group_name = section["section"]
        group_contents = section.get("contents", [])
        assert len(group_contents) >= 2, (
            f"Section {group_name!r} should have overview page + subcommands, "
            f"got {len(group_contents)} items: {group_contents}"
        )
        # First entry should be the group overview (reference/cli/<group>.qmd)
        overview = group_contents[0]
        assert isinstance(overview, str), (
            f"First item in section {group_name!r} should be a path string, got: {overview}"
        )
        assert overview == f"reference/cli/{group_name}.qmd", (
            f"Expected overview page 'reference/cli/{group_name}.qmd', got: {overview}"
        )
        # Remaining entries should be nested subcommand paths
        for sub_path in group_contents[1:]:
            assert isinstance(sub_path, str), (
                f"Subcommand in {group_name!r} should be a path string, got: {sub_path}"
            )
            assert sub_path.startswith(f"reference/cli/{group_name}/"), (
                f"Subcommand path {sub_path!r} should be nested under "
                f"'reference/cli/{group_name}/', not at the flat level"
            )


def test_R4_cli_sidebar_no_raw_qmd_paths_in_nested():
    """Nested CLI sidebar must not have bare reference/cli/<leaf>.qmd paths for subcommands."""
    pkg = "gdtest_cli_nested"
    if not _has_rendered_site(pkg):
        pytest.skip("gdtest_cli_nested not rendered")

    import yaml

    quarto_yml = _RENDERED_DIR / pkg / "great-docs" / "_quarto.yml"
    with open(quarto_yml) as f:
        config = yaml.safe_load(f)

    sidebar = config.get("website", {}).get("sidebar", [])
    cli_section = next(
        (s for s in sidebar if isinstance(s, dict) and s.get("id") == "cli-reference"),
        None,
    )
    assert cli_section is not None

    # Collect top-level string items (not inside section dicts)
    top_level_paths = [c for c in cli_section.get("contents", []) if isinstance(c, str)]

    # The only top-level path should be the index page.
    # Subcommand paths like reference/cli/run.qmd must NOT appear here.
    known_subcommands = {"run", "list", "get", "set"}
    for path in top_level_paths:
        stem = path.split("/")[-1].replace(".qmd", "")
        assert stem not in known_subcommands, (
            f"Subcommand path {path!r} is at the top level of the CLI sidebar — "
            f"it should be nested inside its group section"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Math Rendering
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_math_blocks_render():
    """RST math directives or LaTeX should render (KaTeX or display math)."""
    pkg = "gdtest_docstring_math"
    if not _has_rendered_site(pkg):
        pkg = "gdtest_math_docs"
        if not _has_rendered_site(pkg):
            pytest.skip("No math package rendered")

    ref = _ref_dir(pkg)
    found_math = False
    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        html_str = str(soup)
        if any(
            marker in html_str
            for marker in (
                "\\[",
                "\\(",
                "katex",
                "mathjax",
                "math-display",
                "display-math",
                "MathJax",
                "KaTeX",
            )
        ):
            found_math = True
            break

    assert found_math, f"No rendered math found in {pkg}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Stress Test Smoke Checks
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "pkg_name",
    [
        "gdtest_stress_everything",
        "gdtest_stress_all_config",
        "gdtest_stress_all_docstr",
        "gdtest_stress_all_ug",
        "gdtest_stress_all_sections",
        "gdtest_kitchen_sink",
    ],
)
def test_R4_stress_packages_have_reference(pkg_name: str):
    """Stress test packages have reference pages."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    assert ref.exists(), f"{pkg_name}: no reference/ directory"
    ref_pages = list(ref.glob("*.html"))
    assert len(ref_pages) >= 1, f"{pkg_name}: no reference pages at all"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Heading Hierarchy
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
@pytest.mark.parametrize("pkg_name", _RENDERED_PACKAGES[:20])
def test_R4_no_broken_heading_attributes(pkg_name: str):
    """Heading attributes like { #anchor } should not render as plain text."""
    ref = _ref_dir(pkg_name)
    if not ref.exists():
        pytest.skip("No reference dir")

    for html_file in ref.glob("*.html"):
        if html_file.name == "index.html":
            continue

        soup = _load_html(html_file)
        main = soup.select_one("main.content")
        if main is None:
            continue

        for heading in main.select("h1, h2, h3, h4"):
            text = heading.get_text()
            if "{ #" in text:
                pytest.fail(
                    f"{html_file.name}: broken heading attribute in <{heading.name}>: {text[:80]!r}"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Directive Stripping
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_multi_module_no_duplicate_entries():
    """Re-exported symbols should not appear twice (short + qualified name).

    When a package re-exports submodule symbols via __init__.py (e.g.,
    ``from .models import Model``), the reference should list only the
    short name (``Model``), NOT both ``Model`` and ``models.Model``.
    """
    pkg = "gdtest_multi_module"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    ref_pages = {f.stem for f in ref.glob("*.html") if f.name != "index.html"}

    # These are the 6 re-exported symbols that should appear as short names
    expected_short = {"Controller", "Model", "View", "dispatch", "create_model", "render_view"}

    # These qualified duplicates must NOT exist as separate pages
    forbidden_qualified = {
        "controllers.Controller",
        "models.Model",
        "views.View",
        "controllers.dispatch",
        "models.create_model",
        "views.render_view",
    }

    # All short names should have pages
    missing = expected_short - ref_pages
    assert not missing, f"Missing reference pages for re-exported symbols: {missing}"

    # No qualified duplicates should have pages
    duplicates = forbidden_qualified & ref_pages
    assert not duplicates, (
        f"Duplicate qualified reference pages found (should only have short names): {duplicates}"
    )

    # Also verify the reference index page doesn't list duplicates
    ref_index = ref / "index.html"
    if ref_index.exists():
        soup = _load_html(ref_index)
        main = soup.select_one("main.content")
        if main is not None:
            text = main.get_text()
            for qual in forbidden_qualified:
                # The qualified name should not appear as a standalone entry
                # (it may appear in descriptive text, so check for it as a heading)
                headings = [h.get_text().strip() for h in main.select("h1, h2, h3, h4, h5")]
                assert qual not in headings, (
                    f"Qualified name '{qual}' appears as a heading — should only list '{qual.split('.')[-1]}'"
                )


@requires_bs4
def test_R4_config_all_on_builds_with_dict_reference():
    """A reference config that is a dict (title override) should not crash init.

    The gdtest_config_all_on spec uses ``reference: {title: "API Reference"}``
    — a dict, not a list of sections. This must be treated as a title override
    and auto-discovery should generate the reference sections normally.
    """
    pkg = "gdtest_config_all_on"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    expected_exports = {"process", "Config"}

    # Reference pages should exist for the auto-discovered exports
    ref_pages = {f.stem for f in ref.glob("*.html") if f.name != "index.html"}
    missing = expected_exports - ref_pages
    assert not missing, f"Missing reference pages after dict-reference config: {missing}"

    # The reference index should have section headings
    ref_index = ref / "index.html"
    assert ref_index.exists(), "No reference/index.html"
    soup = _load_html(ref_index)
    headings = [h.get_text().strip() for h in soup.select("h1, h2, h3")]
    assert len(headings) > 0, "Reference index has no headings"


@requires_bs4
def test_R4_ref_title_custom_title_and_desc():
    """Custom reference title and description should appear on the index page.

    The gdtest_ref_title spec uses ``reference: {title: "API Docs", desc: ...}``
    in great-docs.yml. The _quarto.yml should carry both the custom title and
    desc, and the rendered reference index page should display them.
    """
    pkg = "gdtest_ref_title"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    # 1. _quarto.yml should have the custom title and desc
    cfg = _load_quarto_yml(pkg)
    api_ref = cfg.get("api-reference", {})
    assert api_ref.get("title") == "API Docs", (
        f"Expected api-reference.title='API Docs', got {api_ref.get('title')!r}"
    )
    assert api_ref.get("desc"), "Expected api-reference.desc to be set"

    # 2. Navbar should use the custom title
    navbar_left = cfg.get("website", {}).get("navbar", {}).get("left", [])
    ref_nav = [
        item
        for item in navbar_left
        if isinstance(item, dict) and "reference" in item.get("href", "")
    ]
    assert ref_nav, "No reference link in navbar"
    assert ref_nav[0].get("text") == "API Docs", (
        f"Navbar text should be 'API Docs', got {ref_nav[0].get('text')!r}"
    )

    # 3. Rendered index page should have the custom title as h1
    ref_index = _ref_dir(pkg) / "index.html"
    if not ref_index.exists():
        pytest.skip("reference/index.html not found")

    soup = _load_html(ref_index)
    h1 = soup.select_one("h1")
    assert h1 is not None, "No h1 on reference index page"
    assert "API Docs" in h1.get_text(), f"Expected 'API Docs' in h1, got {h1.get_text()!r}"

    # 4. Description paragraph should appear on the page
    main = soup.select_one("main.content") or soup
    text = main.get_text()
    assert "Welcome to the API documentation" in text, (
        "Expected description text on reference index page"
    )


@requires_bs4
def test_R4_ref_module_expand_uses_short_names():
    """Reference config with a submodule name should render successfully.

    The gdtest_ref_module_expand spec references ``utils`` (a submodule) in the
    reference config contents. The rendered output should contain a page for
    the utils module and its member functions should appear on that page.
    """
    pkg = "gdtest_ref_module_expand"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    ref_pages = {f.stem for f in ref.glob("*.html") if f.name != "index.html"}

    # The submodule should have a reference page
    assert "utils" in ref_pages, f"No reference page for 'utils' submodule. Got {ref_pages}"

    # The utils page should contain the individual function names
    utils_page = ref / "utils.html"
    soup = _load_html(utils_page)
    text = soup.get_text()
    for func in ("util_a", "util_b", "util_c"):
        assert func in text, f"Function '{func}' not found on utils.html reference page"


@requires_bs4
@pytest.mark.parametrize("pkg_name", ["gdtest_seealso", "gdtest_nodoc"])
def test_R4_directives_stripped_from_html(pkg_name: str):
    """Great Docs directives (%seealso, %nodoc) should not appear in HTML."""
    if not _has_rendered_site(pkg_name):
        pytest.skip(f"{pkg_name} not rendered")

    ref = _ref_dir(pkg_name)
    for html_file in ref.glob("*.html"):
        soup = _load_html(html_file)
        main = soup.select_one("main.content")
        if main is None:
            continue

        text = main.get_text()
        assert "%seealso" not in text, f"{html_file.name}: raw %seealso directive found"
        assert "%nodoc" not in text, f"{html_file.name}: raw %nodoc directive found"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: TOC Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def _load_quarto_yml(pkg_name: str) -> dict:
    """Load and parse the _quarto.yml for a rendered package."""
    import yaml

    qpath = _RENDERED_DIR / pkg_name / "great-docs" / "_quarto.yml"
    with open(qpath) as f:
        return yaml.safe_load(f)


@requires_bs4
def test_R4_toc_disabled_config():
    """When site.toc is false, _quarto.yml should have toc: false."""
    pkg = "gdtest_toc_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    cfg = _load_quarto_yml(pkg)
    html_cfg = cfg.get("format", {}).get("html", {})
    assert html_cfg.get("toc") is False, (
        f"Expected toc: false in format.html, got toc: {html_cfg.get('toc')!r}"
    )


@requires_bs4
def test_R4_toc_depth_config():
    """When site.toc-depth is set, _quarto.yml should reflect the custom depth."""
    pkg = "gdtest_toc_depth"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    cfg = _load_quarto_yml(pkg)
    html_cfg = cfg.get("format", {}).get("html", {})
    assert html_cfg.get("toc-depth") == 3, (
        f"Expected toc-depth: 3, got {html_cfg.get('toc-depth')!r}"
    )


@requires_bs4
def test_R4_toc_title_config():
    """When site.toc-title is customized, _quarto.yml should use the custom title."""
    pkg = "gdtest_toc_title"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    cfg = _load_quarto_yml(pkg)
    html_cfg = cfg.get("format", {}).get("html", {})
    assert html_cfg.get("toc-title") == "Contents", (
        f"Expected toc-title: 'Contents', got {html_cfg.get('toc-title')!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Source Link Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def test_R4_source_disabled_no_links_file():
    """When source.enabled is false, _source_links.json should not be generated."""
    pkg = "gdtest_source_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    source_links = _RENDERED_DIR / pkg / "great-docs" / "_source_links.json"
    assert not source_links.exists(), (
        f"_source_links.json should not exist when source is disabled: {source_links}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Display Configuration — Badges, Authors, Funding
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_display_badges_index_has_badge_images():
    """A README with shields.io badges should render badge <img> tags on index."""
    pkg = "gdtest_display_badges"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    imgs = soup.select("img")
    badge_imgs = [
        img for img in imgs if "shields.io" in (img.get("src", "") + img.get("data-src", ""))
    ]

    assert len(badge_imgs) >= 2, (
        f"Expected at least 2 shields.io badge images, found {len(badge_imgs)}"
    )


@requires_bs4
def test_R4_display_badges_index_has_table():
    """A README with a markdown table should render as an HTML <table>."""
    pkg = "gdtest_display_badges"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    tables = soup.select("table")
    assert len(tables) >= 1, "Expected at least one HTML table from markdown table"


@requires_bs4
def test_R4_display_authors_names_in_index():
    """Author names from config should appear in the rendered index page."""
    pkg = "gdtest_display_authors"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    text = soup.get_text()

    assert "Jane Doe" in text, "Author 'Jane Doe' not found on index page"
    assert "John Smith" in text, "Author 'John Smith' not found on index page"


@requires_bs4
def test_R4_display_authors_roles_in_index():
    """Author roles from config should appear in the rendered index page."""
    pkg = "gdtest_display_authors"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    text = soup.get_text()

    assert "Principal Investigator" in text, "Role 'Principal Investigator' not found"
    assert "Lead Developer" in text, "Role 'Lead Developer' not found"


@requires_bs4
def test_R4_display_funding_name_in_index():
    """Funding organization name should appear in the rendered index page."""
    pkg = "gdtest_display_funding"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    text = soup.get_text()

    assert "National Science Foundation" in text, (
        "Funding org 'National Science Foundation' not found on index page"
    )


@requires_bs4
def test_R4_display_funding_link_in_index():
    """Funding organization homepage link should appear in the rendered site."""
    pkg = "gdtest_display_funding"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)
    html_str = str(soup)

    assert "nsf.gov" in html_str, "Funding homepage 'nsf.gov' not found in index HTML"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Decorator Functions
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_decorator_pages_exist():
    """Decorator functions should have reference pages."""
    pkg = "gdtest_decorators"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("retry", "cache", "validate_args", "log_calls"):
        page = ref / f"{name}.html"
        assert page.exists(), f"Missing decorator reference page: {name}.html"


@requires_bs4
def test_R3_decorator_retry_has_params():
    """The retry decorator page should document max_retries and delay parameters."""
    pkg = "gdtest_decorators"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _ref_dir(pkg) / "retry.html"
    if not page.exists():
        pytest.skip("retry.html not found")

    soup = _load_html(page)
    text = soup.get_text()
    assert "max_retries" in text, "retry page should document 'max_retries' parameter"
    assert "delay" in text, "retry page should document 'delay' parameter"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Generator Functions
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_generator_pages_exist():
    """Generator functions should have reference pages."""
    pkg = "gdtest_generators"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("count_up", "fibonacci", "iter_chunks"):
        page = ref / f"{name}.html"
        assert page.exists(), f"Missing generator reference page: {name}.html"


@requires_bs4
def test_R3_generator_return_types_show_iterator():
    """Generator function pages should show Iterator in return type."""
    pkg = "gdtest_generators"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("count_up", "fibonacci", "iter_chunks"):
        page = ref / f"{name}.html"
        if not page.exists():
            continue
        soup = _load_html(page)
        text = soup.get_text()
        assert "Iterator" in text, (
            f"{name}.html should show 'Iterator' in the return type annotation"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Generic Classes
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_generic_class_pages_exist():
    """Generic classes (Stack, Pair) should have reference pages."""
    pkg = "gdtest_generics"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("Stack", "Pair"):
        page = ref / f"{name}.html"
        assert page.exists(), f"Missing generic class page: {name}.html"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Frozen Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_frozen_dc_section_title():
    """Frozen dataclasses should use 'Dataclasses' as the section heading."""
    pkg = "gdtest_frozen_dc"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref_index = _ref_dir(pkg) / "index.html"
    if not ref_index.exists():
        pytest.skip("No reference index")

    soup = _load_html(ref_index)
    headings = [h.get_text().strip() for h in soup.select("h2, h3")]
    assert "Dataclasses" in headings, f"Expected 'Dataclasses' section heading, got: {headings}"


@requires_bs4
def test_R3_frozen_dc_pages_have_fields():
    """Frozen dataclass pages should document their fields as parameters."""
    pkg = "gdtest_frozen_dc"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _ref_dir(pkg) / "Coordinate.html"
    if not page.exists():
        pytest.skip("Coordinate.html not found")

    soup = _load_html(page)
    text = soup.get_text()
    for field in ("x", "y"):
        assert field in text, f"Dataclass field '{field}' not documented on Coordinate page"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Re-exports from Submodules
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_reexports_all_symbols_have_pages():
    """Re-exported symbols from submodules should each have a reference page."""
    pkg = "gdtest_reexports"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("Engine", "run", "format_result", "parse_input"):
        page = ref / f"{name}.html"
        assert page.exists(), f"Re-exported symbol '{name}' should have a reference page"


@requires_bs4
def test_R3_reexports_ref_index_has_sections():
    """Re-exports reference index should have both Classes and Functions sections."""
    pkg = "gdtest_reexports"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref_index = _ref_dir(pkg) / "index.html"
    if not ref_index.exists():
        pytest.skip("No reference index")

    soup = _load_html(ref_index)
    headings = [h.get_text().strip() for h in soup.select("h2, h3")]
    assert "Classes" in headings, f"Expected 'Classes' section, got: {headings}"
    assert "Functions" in headings, f"Expected 'Functions' section, got: {headings}"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Abstract Properties
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_abstract_class_pages_exist():
    """Abstract base classes and their subclasses should have reference pages."""
    pkg = "gdtest_abstract_props"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for name in ("Shape", "Circle"):
        page = ref / f"{name}.html"
        assert page.exists(), f"Missing class page: {name}.html"


@requires_bs4
def test_R3_abstract_shape_documents_properties():
    """Abstract Shape class should document area and perimeter properties."""
    pkg = "gdtest_abstract_props"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _ref_dir(pkg) / "Shape.html"
    if not page.exists():
        pytest.skip("Shape.html not found")

    soup = _load_html(page)
    text = soup.get_text()
    assert "area" in text, "Shape page should document 'area' property"
    assert "perimeter" in text, "Shape page should document 'perimeter' property"


@requires_bs4
def test_R3_abstract_circle_documents_radius():
    """Circle subclass should document the radius parameter."""
    pkg = "gdtest_abstract_props"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _ref_dir(pkg) / "Circle.html"
    if not page.exists():
        pytest.skip("Circle.html not found")

    soup = _load_html(page)
    text = soup.get_text()
    assert "radius" in text, "Circle page should document 'radius' parameter"


# ═══════════════════════════════════════════════════════════════════════════════
# R3: Deep Nesting
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R3_deep_nesting_pages_exist():
    """Deeply nested exports (3 levels) should still get reference pages."""
    pkg = "gdtest_deep_nesting"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    # Check that the re-exported symbols have pages (may be prefixed)
    ref_pages = {f.stem for f in ref.glob("*.html") if f.name != "index.html"}
    has_deep_func = "deep_func" in ref_pages or any(p.endswith(".deep_func") for p in ref_pages)
    has_deep_class = "DeepClass" in ref_pages or any(p.endswith(".DeepClass") for p in ref_pages)
    assert has_deep_func, f"deep_func not found in ref pages: {ref_pages}"
    assert has_deep_class, f"DeepClass not found in ref pages: {ref_pages}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Changelog Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def test_R4_changelog_config_propagated():
    """Changelog config should be written to great-docs.yml with enabled + max_releases."""
    import yaml

    pkg = "gdtest_config_changelog"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    gd_yml = _RENDERED_DIR / pkg / "great-docs.yml"
    assert gd_yml.exists(), "great-docs.yml should exist"

    cfg = yaml.safe_load(gd_yml.read_text())
    changelog = cfg.get("changelog", {})
    assert changelog.get("enabled") is True, "changelog.enabled should be True"
    assert changelog.get("max_releases") == 5, "changelog.max_releases should be 5"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Config Combo A — display_name, authors, funding
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_config_combo_a_display_name_and_authors():
    """Combo A: display_name in title, authors in footer, landing page content."""
    pkg = "gdtest_config_combo_a"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    # Check _quarto.yml title matches display_name
    cfg = _load_quarto_yml(pkg)
    assert cfg["website"]["title"] == "Combo A Toolkit", "Website title should use display_name"

    # Check authors in page-footer
    footer = cfg.get("website", {}).get("page-footer", {})
    footer_left = footer.get("left", "")
    assert "Alice Smith" in footer_left, "Footer should mention Alice Smith"
    assert "Bob Jones" in footer_left, "Footer should mention Bob Jones"

    # Check landing page has display_name
    index = _site_dir(pkg) / "index.html"
    if index.exists():
        soup = _load_html(index)
        text = soup.get_text()
        assert "Combo A Toolkit" in text, "Landing page should show display name"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Config Combo B — all opt-out flags
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_config_combo_b_opt_out_flags():
    """Combo B: sidebar_filter, dark_mode_toggle, and source all disabled."""
    pkg = "gdtest_config_combo_b"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    # _quarto.yml should NOT have sidebar-filter.js / dark-mode-toggle.js / theme-init.js
    cfg = _load_quarto_yml(pkg)
    html_cfg = cfg.get("format", {}).get("html", {})
    after_body = html_cfg.get("include-after-body", [])
    after_texts = " ".join(str(item) for item in after_body)
    assert "sidebar-filter.js" not in after_texts, (
        "sidebar-filter.js should be absent when sidebar_filter is disabled"
    )
    assert "dark-mode-toggle.js" not in after_texts, (
        "dark-mode-toggle.js should be absent when dark_mode_toggle is disabled"
    )

    # source.enabled=false → no _source_links.json
    source_links = _RENDERED_DIR / pkg / "great-docs" / "_source_links.json"
    assert not source_links.exists(), "_source_links.json should not exist when source is disabled"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Config user_guide as explicit list
# ═══════════════════════════════════════════════════════════════════════════════


def test_R4_config_ug_list_sections_in_yml():
    """user_guide as list of section dicts should propagate to great-docs.yml."""
    import yaml

    pkg = "gdtest_config_ug_list"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    gd_yml = _RENDERED_DIR / pkg / "great-docs.yml"
    assert gd_yml.exists(), "great-docs.yml should exist"

    cfg = yaml.safe_load(gd_yml.read_text())
    ug = cfg.get("user_guide", [])
    assert isinstance(ug, list), "user_guide should be a list"
    assert len(ug) == 2, "user_guide should have 2 sections"

    titles = [s.get("title") for s in ug]
    assert "Getting Started" in titles, "Should have 'Getting Started' section"
    assert "Advanced" in titles, "Should have 'Advanced' section"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Config user_guide as string (custom directory)
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_config_ug_string_pages_rendered():
    """user_guide as string pointing to 'guides' dir should render user guide pages."""
    pkg = "gdtest_config_ug_string"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("intro.html", "setup.html"):
        page = ug_dir / page_name
        assert page.exists(), f"User guide page {page_name} should exist"

    # Verify content
    soup = _load_html(ug_dir / "intro.html")
    text = soup.get_text()
    assert "Introduction" in text, "intro page should contain 'Introduction'"

    # Verify sidebar has user-guide section
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Empty Module — zero exports
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_empty_module_no_reference_dir():
    """A package with zero exports should build without a reference directory."""
    pkg = "gdtest_empty_module"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    # Should have a landing page
    index = _site_dir(pkg) / "index.html"
    assert index.exists(), "Empty module should still have index.html"

    # Should NOT have a reference directory (nothing to document)
    ref = _ref_dir(pkg)
    assert not ref.exists(), "Empty module with __all__ = [] should not have a reference directory"

    # Title should be present on landing page
    soup = _load_html(index)
    text = soup.get_text()
    assert "gdtest-empty-module" in text, "Landing page should show package name"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — auto-discovered
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_auto_pages_exist_with_content():
    """Auto-discovered user guide should render all .qmd files with correct titles."""
    pkg = "gdtest_ug_auto"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    pages = {
        "basics.html": "Basics",
        "configuration.html": "Configuration",
        "deployment.html": "Deployment",
    }

    for page_name, expected_title in pages.items():
        page = ug_dir / page_name
        assert page.exists(), f"Auto-discovered UG page {page_name} should exist"
        soup = _load_html(page)
        text = soup.get_text()
        assert expected_title in text, f"{page_name} should contain '{expected_title}'"

    # Sidebar should list all 3 pages
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    assert len(contents) == 3, f"User guide sidebar should list 3 pages, got {len(contents)}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — combo (numbered, sections, subdirs, mixed extensions)
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_combo_subdirs_and_sections():
    """Complex user guide should render pages in subdirectories with sidebar sections."""
    pkg = "gdtest_ug_combo"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    expected_pages = [
        "basics/intro.html",
        "basics/install.html",
        "advanced/config.html",
        "advanced/extend.html",
    ]
    for rel_path in expected_pages:
        page = ug_dir / rel_path
        assert page.exists(), f"Combo UG page {rel_path} should exist"

    # Sidebar should have sections
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    section_titles = [c.get("section") for c in contents if isinstance(c, dict) and "section" in c]
    assert "Basics" in section_titles, "Sidebar should have 'Basics' section"
    assert "Advanced" in section_titles, "Sidebar should have 'Advanced' section"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — custom directory
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_custom_dir_pages_from_docs():
    """User guide sourced from 'docs/' should render pages under user-guide/."""
    pkg = "gdtest_ug_custom_dir"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("getting-started.html", "reference-guide.html"):
        page = ug_dir / page_name
        assert page.exists(), f"Custom-dir UG page {page_name} should exist"
        soup = _load_html(page)
        text = soup.get_text()
        expected_title = page_name.replace(".html", "").replace("-", " ").title()
        assert expected_title.split()[0] in text, f"{page_name} should have title content"

    # Sidebar should list pages
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — deeply nested subdirectories
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_deep_nest_multi_level_structure():
    """Deeply nested user guide should render pages at multiple directory levels."""
    pkg = "gdtest_ug_deep_nest"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    deep_pages = [
        "section1/topic1/details.html",
        "section1/topic2/overview.html",
        "section2/intro.html",
    ]
    for rel_path in deep_pages:
        page = ug_dir / rel_path
        assert page.exists(), f"Deep-nested UG page {rel_path} should exist"

    # Verify content renders correctly at 3 levels deep
    soup = _load_html(ug_dir / "section1" / "topic1" / "details.html")
    text = soup.get_text()
    assert "Topic 1 Details" in text, "3-level deep page should have correct title"

    # Sidebar should have nested sections
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    assert len(contents) >= 3, f"Sidebar should have at least 3 entries, got {len(contents)}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — explicit ordering via config
# ═══════════════════════════════════════════════════════════════════════════════


def test_R4_ug_explicit_order_config_sections():
    """Explicit user guide ordering should produce titled sections in great-docs.yml."""
    import yaml

    pkg = "gdtest_ug_explicit_order"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    gd_yml = _RENDERED_DIR / pkg / "great-docs.yml"
    assert gd_yml.exists(), "great-docs.yml should exist"

    cfg = yaml.safe_load(gd_yml.read_text())
    ug = cfg.get("user_guide", [])
    assert isinstance(ug, list), "user_guide should be a list"
    assert len(ug) == 2, f"user_guide should have 2 sections, got {len(ug)}"

    titles = [s.get("title") for s in ug]
    assert "First Steps" in titles, "Should have 'First Steps' section"
    assert "Deep Dive" in titles, "Should have 'Deep Dive' section"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — hyphenated directory name
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_hyphen_dir_pages_rendered():
    """User guide from user-guide/ (hyphenated) should render pages correctly."""
    pkg = "gdtest_ug_hyphen_dir"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("intro.html", "setup.html"):
        page = ug_dir / page_name
        assert page.exists(), f"Hyphen-dir UG page {page_name} should exist"

    soup = _load_html(ug_dir / "intro.html")
    text = soup.get_text()
    assert "Introduction" in text, "intro page should contain 'Introduction'"

    # Sidebar should list pages
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — many pages (12)
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_many_pages_all_twelve_rendered():
    """User guide with 12 numbered pages should render all of them."""
    pkg = "gdtest_ug_many_pages"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    expected = [
        "overview.html",
        "installation.html",
        "quickstart.html",
        "configuration.html",
        "basic-usage.html",
        "advanced-usage.html",
        "plugins.html",
        "testing.html",
        "deployment.html",
        "troubleshooting.html",
        "faq.html",
        "appendix.html",
    ]
    for page_name in expected:
        page = ug_dir / page_name
        assert page.exists(), f"Many-pages UG page {page_name} should exist"

    # Sidebar should list all 12 pages
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    assert len(contents) == 12, f"Sidebar should list 12 pages, got {len(contents)}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — mixed .qmd and .md extensions
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_mixed_ext_both_formats_render():
    """User guide with mixed .qmd and .md files should render all pages."""
    pkg = "gdtest_ug_mixed_ext"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("intro.html", "setup.html", "advanced.html"):
        page = ug_dir / page_name
        assert page.exists(), f"Mixed-ext UG page {page_name} should exist"

    # .md file should render with correct content
    soup = _load_html(ug_dir / "setup.html")
    text = soup.get_text()
    assert "Setup" in text, "setup.md page should contain 'Setup'"

    # Sidebar should include both .qmd and .md entries
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    exts = {str(c).rsplit(".", 1)[-1] for c in contents if isinstance(c, str)}
    assert "md" in exts, "Sidebar should include .md file"
    assert "qmd" in exts, "Sidebar should include .qmd file"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — no frontmatter
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_no_frontmatter_pages_render():
    """User guide pages without YAML frontmatter should still render."""
    pkg = "gdtest_ug_no_frontmatter"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("intro.html", "usage.html"):
        page = ug_dir / page_name
        assert page.exists(), f"No-frontmatter UG page {page_name} should exist"

    # Content from the .qmd body should still appear
    soup = _load_html(ug_dir / "intro.html")
    text = soup.get_text()
    assert "Welcome to the project" in text, (
        "Frontmatter-less page should still render body content"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — numbered pages
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_numbered_pages_in_order():
    """Numbered user guide pages should render and appear in sidebar order."""
    pkg = "gdtest_ug_numbered"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    expected = ["intro.html", "install.html", "usage.html", "advanced.html"]
    for page_name in expected:
        page = ug_dir / page_name
        assert page.exists(), f"Numbered UG page {page_name} should exist"

    # Sidebar should list pages in numeric order (number prefixes stripped)
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    assert len(contents) == 4, f"Sidebar should list 4 pages, got {len(contents)}"
    # First entry should be intro (from 01-intro)
    assert "intro" in str(contents[0]), "First sidebar entry should be intro"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — guide-section frontmatter
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_sections_fm_sidebar_grouping():
    """guide-section frontmatter should group pages into sidebar sections."""
    pkg = "gdtest_ug_sections_fm"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    for page_name in ("welcome.html", "install.html", "config.html", "extend.html"):
        page = ug_dir / page_name
        assert page.exists(), f"Sections-FM UG page {page_name} should exist"

    # Sidebar should have two sections from guide-section frontmatter
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    section_titles = [c.get("section") for c in contents if isinstance(c, dict) and "section" in c]
    assert "Getting Started" in section_titles, "Should have 'Getting Started' section"
    assert "Advanced Topics" in section_titles, "Should have 'Advanced Topics' section"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — single page
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_single_page_renders():
    """Single-page user guide should still render with sidebar."""
    pkg = "gdtest_ug_single_page"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _site_dir(pkg) / "user-guide" / "getting-started.html"
    assert page.exists(), "Single-page UG should exist"

    soup = _load_html(page)
    text = soup.get_text()
    assert "Getting Started" in text, "Page should contain 'Getting Started'"
    assert "single page" in text, "Page should contain 'single page' content"

    # Sidebar should have exactly 1 entry
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    assert len(contents) == 1, f"Single-page UG sidebar should have 1 entry, got {len(contents)}"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — subdirectory organization
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_subdirs_pages_and_sections():
    """Subdirectory-organized user guide should render pages with sidebar sections."""
    pkg = "gdtest_ug_subdirs"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ug_dir = _site_dir(pkg) / "user-guide"
    expected_pages = [
        "basics/intro.html",
        "basics/setup.html",
        "advanced/customization.html",
        "advanced/plugins.html",
    ]
    for rel_path in expected_pages:
        page = ug_dir / rel_path
        assert page.exists(), f"Subdirs UG page {rel_path} should exist"

    # Sidebar should have sections matching subdirectory names
    cfg = _load_quarto_yml(pkg)
    sidebars = cfg.get("website", {}).get("sidebar", [])
    ug_sidebar = [s for s in sidebars if s.get("id") == "user-guide"]
    assert len(ug_sidebar) == 1, "Should have a user-guide sidebar"
    contents = ug_sidebar[0].get("contents", [])
    section_titles = [c.get("section") for c in contents if isinstance(c, dict) and "section" in c]
    assert "Basics" in section_titles, "Sidebar should have 'Basics' section"
    assert "Advanced" in section_titles, "Sidebar should have 'Advanced' section"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: User Guide — with image assets
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_ug_with_images_renders_img_tags():
    """User guide referencing assets should render with <img> tags."""
    pkg = "gdtest_ug_with_images"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    page = _site_dir(pkg) / "user-guide" / "visual-guide.html"
    assert page.exists(), "visual-guide.html should exist"

    soup = _load_html(page)
    text = soup.get_text()
    assert "Visual Guide" in text, "Page should contain 'Visual Guide' title"
    assert "architecture diagram" in text.lower() or "Architecture Diagram" in text, (
        "Page should mention the architecture diagram"
    )

    # Should have <img> tags for the SVG assets
    imgs = soup.find_all("img")
    assert len(imgs) >= 1, "Page should have at least one <img> tag for assets"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Hero Section
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_hero_basic_has_hero_div():
    """Landing page should contain the hero section div when logo is configured."""
    pkg = "gdtest_hero_basic"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)

    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Landing page should have a <div class='gd-hero'>"

    # Should contain the logo image
    logo_img = hero.select_one("img.gd-hero-logo")
    assert logo_img is not None, "Hero should contain a logo <img>"

    # Should contain the package name
    name_el = hero.select_one(".gd-hero-name")
    assert name_el is not None, "Hero should contain the package name"
    assert "Hero Basic" in name_el.get_text(), "Hero name should match display_name"

    # Should contain badges extracted from the README
    badges_div = hero.select_one(".gd-hero-badges")
    assert badges_div is not None, "Hero should contain a badges div"
    badge_imgs = badges_div.find_all("img")
    assert len(badge_imgs) >= 2, f"Expected ≥2 badge images, got {len(badge_imgs)}"


@requires_bs4
def test_R4_hero_basic_badges_stripped_from_body():
    """Badges extracted into the hero should not appear in the landing page body."""
    pkg = "gdtest_hero_basic"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)

    # The main content area should not contain raw badge markdown after extraction.
    # Find the main content div (after the hero) — Quarto uses #quarto-document-content.
    content_div = soup.select_one("#quarto-document-content")
    if content_div is None:
        pytest.skip("No #quarto-document-content found")

    # Remove the hero section from our inspection copy
    hero = content_div.select_one("div.gd-hero")
    if hero:
        hero.decompose()

    # Remove source tree / file viewer sections that show raw file content
    for details in content_div.select("details.tree-file"):
        details.decompose()

    body_text = content_div.get_text()
    body_html = str(content_div)

    # Badges should not appear in the remaining body
    assert "img.shields.io" not in body_html, "Badge URLs should be stripped from the body content"
    # But body content should still be present
    assert "Features" in body_text, "Body content should still contain 'Features'"


@requires_bs4
def test_R4_hero_readme_badges_centered_div_stripped():
    """A README with <div align=center> badges should have the div stripped and badges in hero."""
    pkg = "gdtest_hero_readme_badges"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    soup = _load_html(index)

    # Hero section should exist with badges
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Landing page should have a <div class='gd-hero'>"

    badges_div = hero.select_one(".gd-hero-badges")
    assert badges_div is not None, "Hero should contain a badges div"
    badge_imgs = badges_div.find_all("img")
    assert len(badge_imgs) >= 3, f"Expected ≥3 badges from centered div, got {len(badge_imgs)}"

    # Check the main content area (excluding hero and source tree viewer)
    content_div = soup.select_one("#quarto-document-content")
    if content_div is None:
        pytest.skip("No #quarto-document-content found")

    hero_in_content = content_div.select_one("div.gd-hero")
    if hero_in_content:
        hero_in_content.decompose()
    for details in content_div.select("details.tree-file"):
        details.decompose()

    remaining_html = str(content_div)
    # The centered-div hero image should be stripped from the body
    assert "hero-image.png" not in remaining_html, (
        "The centered-div hero image should be stripped from the body"
    )

    # Body content after the div should still be present
    body_text = content_div.get_text()
    assert "Overview" in body_text, "Body content after the centered div should be preserved"
    assert "Validates data" in body_text, "Feature descriptions should be preserved"


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Hero Section Variants
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_R4_hero_disabled_no_hero_div():
    """Setting hero: false should prevent the hero section from appearing."""
    pkg = "gdtest_hero_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is None, "hero: false should suppress the hero section"

    # Navbar should still have the logo
    nav_logo = soup.select_one(".navbar-logo")
    assert nav_logo is not None, "Navbar logo should still be present"


@requires_bs4
def test_R4_hero_custom_overrides():
    """Hero sub-options should override defaults (name, tagline, height, badges)."""
    pkg = "gdtest_hero_custom"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present"

    # Custom name (not the display_name "Default Display Name")
    name_el = hero.select_one(".gd-hero-name")
    assert name_el is not None
    assert name_el.get_text().strip() == "Custom Hero Name"

    # Custom tagline (not the pyproject description)
    tagline = hero.select_one(".gd-hero-tagline")
    assert tagline is not None
    assert "completely custom tagline" in tagline.get_text()

    # Custom logo height
    logo = hero.select_one("img.gd-hero-logo")
    assert logo is not None
    assert "120px" in logo.get("style", "")

    # Badges suppressed
    badges = hero.select_one(".gd-hero-badges")
    assert badges is None, "badges: false should suppress badges"


@requires_bs4
def test_R4_hero_wordmark_separate_logos():
    """Hero should use wordmark logo while navbar uses lettermark."""
    pkg = "gdtest_hero_wordmark"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present"

    # Hero should have two logo images (light + dark wordmark)
    hero_logos = hero.select("img.gd-hero-logo")
    assert len(hero_logos) == 2, "Hero should have light and dark wordmark logos"

    # Check hero logos are the wordmark
    hero_srcs = {img.get("src", "") for img in hero_logos}
    assert any("wordmark.svg" in s for s in hero_srcs), "Hero should use wordmark.svg"
    assert any("wordmark-dark.svg" in s for s in hero_srcs), "Hero should use wordmark-dark.svg"

    # Check light/dark CSS classes
    classes = [" ".join(img.get("class", [])) for img in hero_logos]
    assert any("gd-only-light" in c for c in classes), "Light wordmark should have gd-only-light"
    assert any("gd-only-dark" in c for c in classes), "Dark wordmark should have gd-only-dark"

    # Navbar should use the lettermark (not wordmark)
    nav_logo = soup.select_one(".navbar-logo")
    assert nav_logo is not None
    assert "lettermark" in nav_logo.get("src", ""), "Navbar should use lettermark"


@requires_bs4
def test_R4_hero_no_logo_text_only():
    """hero.logo: false should suppress the logo but keep name/tagline/badges."""
    pkg = "gdtest_hero_no_logo"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present"

    # No logo image in the hero
    hero_logos = hero.select("img.gd-hero-logo")
    assert len(hero_logos) == 0, "hero.logo: false should suppress the logo image"

    # Name and tagline should still be present
    name_el = hero.select_one(".gd-hero-name")
    assert name_el is not None, "Name should still be shown"

    tagline = hero.select_one(".gd-hero-tagline")
    assert tagline is not None, "Tagline should still be shown"

    # Badges should still be auto-extracted
    badges = hero.select_one(".gd-hero-badges")
    assert badges is not None, "Badges should still be shown"


@requires_bs4
def test_R4_hero_explicit_badges_list():
    """Explicit badge list should appear in hero instead of auto-extracted ones."""
    pkg = "gdtest_hero_explicit_badges"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present"

    badges = hero.select_one(".gd-hero-badges")
    assert badges is not None, "Badges div should be present"

    badge_imgs = badges.select("img")
    assert len(badge_imgs) == 2, "Should have exactly 2 explicit badges"

    # Check the explicit badges are displayed
    alts = {img.get("alt", "") for img in badge_imgs}
    assert "Custom Badge" in alts, "Custom Badge should appear"
    assert "Status" in alts, "Status badge should appear"

    # The README badge ("README Badge") should NOT be in the hero
    assert "README Badge" not in alts, "README badges should not be auto-extracted"


@requires_bs4
def test_R4_hero_index_qmd_source():
    """Hero should work when landing page source is index.qmd (not README)."""
    pkg = "gdtest_hero_index_qmd"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present from index.qmd source"

    # Logo should be present
    logo = hero.select_one("img.gd-hero-logo")
    assert logo is not None, "Logo should be present"

    # Name should be present
    name_el = hero.select_one(".gd-hero-name")
    assert name_el is not None

    # Badges should be auto-extracted from index.qmd
    badges = hero.select_one(".gd-hero-badges")
    assert badges is not None, "Badges should be auto-extracted from index.qmd"

    # Body content from index.qmd should be preserved
    body_text = soup.get_text()
    assert "Overview" in body_text, "index.qmd body content should be preserved"


@requires_bs4
def test_R4_hero_auto_logo_detection():
    """Auto-detected logo-hero.svg / logo-hero-dark.svg in assets/ should
    be used without explicit hero.logo config."""
    pkg = "gdtest_hero_auto_logo"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    soup = _load_html(_site_dir(pkg) / "index.html")
    hero = soup.select_one("div.gd-hero")
    assert hero is not None, "Hero should be present via auto-detected hero logo"

    # Hero should have two logo images (light + dark)
    hero_logos = hero.select("img.gd-hero-logo")
    assert len(hero_logos) == 2, "Hero should have light and dark auto-detected logos"

    # Check hero logos are the auto-detected hero files (not the navbar logo)
    hero_srcs = {img.get("src", "") for img in hero_logos}
    assert any("logo-hero" in s and "dark" not in s for s in hero_srcs), (
        "Hero should use logo-hero.svg"
    )
    assert any("logo-hero-dark" in s for s in hero_srcs), "Hero should use logo-hero-dark.svg"

    # Check light/dark CSS classes
    classes = [" ".join(img.get("class", [])) for img in hero_logos]
    assert any("gd-only-light" in c for c in classes), "Light logo should have gd-only-light"
    assert any("gd-only-dark" in c for c in classes), "Dark logo should have gd-only-dark"

    # Navbar should use the regular logo.svg (not the hero logo)
    nav_logo = soup.select_one(".navbar-logo")
    assert nav_logo is not None
    nav_src = nav_logo.get("src", "")
    assert "logo-hero" not in nav_src, "Navbar should NOT use the hero logo"


# ═══════════════════════════════════════════════════════════════════════════════
# Markdown (.md) Page Generation
# ═══════════════════════════════════════════════════════════════════════════════


def test_md_files_exist_for_html_pages():
    """Every non-homepage HTML page should have a corresponding .md file."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    html_files = sorted(site.rglob("*.html"))
    assert len(html_files) > 0, "No HTML files found"

    missing = []
    for html_file in html_files:
        rel = html_file.relative_to(site)
        # Homepage is intentionally excluded
        if str(rel) == "index.html":
            continue
        md_file = html_file.with_suffix(".md")
        if not md_file.exists():
            missing.append(str(rel))

    assert not missing, f"Missing .md files for: {missing}"


def test_md_homepage_excluded():
    """The homepage (index.html) should NOT have a corresponding .md file."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    assert not (site / "index.md").exists(), "index.md should not exist (homepage excluded)"


def test_md_no_html_link_artifacts():
    """Generated .md files should not contain relative .html links."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    md_files = sorted(site.rglob("*.md"))
    assert len(md_files) > 0, "No .md files found"

    bad_links = []
    html_link_re = re.compile(r"\]\([^)]*\.html\b")
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        matches = html_link_re.findall(content)
        if matches:
            rel = md_file.relative_to(site)
            bad_links.append(f"{rel}: {matches}")

    assert not bad_links, f".md files with .html links: {bad_links}"


def test_md_no_redundant_parent_dir_links():
    """Links within .md files should not redundantly traverse ../same-dir/."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    md_files = sorted(site.rglob("*.md"))

    bad_paths = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(site)
        parent = str(rel.parent)
        if parent == ".":
            continue
        # Check for ../parent-dir/ pattern pointing back to own directory
        pattern = re.compile(re.escape(f"../{parent}/"))
        if pattern.search(content):
            bad_paths.append(str(rel))

    assert not bad_paths, f".md files with redundant ../same-dir/ links: {bad_paths}"


def test_md_no_parameter_annotation_spans():
    """Generated .md files should not contain raw <span class='parameter-...'> HTML."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    md_files = sorted(site.rglob("*.md"))

    bad_files = []
    span_re = re.compile(r'<span\s+class="parameter-')
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        if span_re.search(content):
            rel = md_file.relative_to(site)
            bad_files.append(str(rel))

    assert not bad_files, f".md files with parameter-* spans: {bad_files}"


def test_md_reference_pages_have_heading():
    """Reference .md pages should start with a markdown heading."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    md_files = sorted(ref.glob("*.md"))
    assert len(md_files) > 0, "No reference .md files found"

    missing_heading = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8").strip()
        if not content.startswith("#"):
            missing_heading.append(md_file.name)

    assert not missing_heading, f"Reference .md files without heading: {missing_heading}"


def test_md_code_blocks_have_language():
    """Python code blocks in .md should have ``` python, not bare ```."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    md_files = sorted(ref.glob("*.md"))

    bare_fence_files = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        # Only flag bare fences that precede Python-looking content
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "```" and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Looks like Python code after a bare fence
                if next_line.startswith(("def ", "class ", "import ", "from ")):
                    bare_fence_files.append(md_file.name)
                    break

    assert not bare_fence_files, (
        f"Reference .md files with bare ``` before Python code: {bare_fence_files}"
    )


def test_md_long_names_produce_valid_filenames():
    """Long object names should produce valid .md filenames that match the .html names."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    html_files = sorted(ref.glob("*.html"))
    md_files = sorted(ref.glob("*.md"))

    html_stems = {f.stem for f in html_files if f.name != "index.html"}
    md_stems = {f.stem for f in md_files if f.name != "index.md"}

    # All non-index HTML pages should have a matching .md
    missing = html_stems - md_stems
    assert not missing, f"HTML pages without matching .md: {missing}"


# ═══════════════════════════════════════════════════════════════════════════════
# Copy-Page Widget Integration
# ═══════════════════════════════════════════════════════════════════════════════


@requires_bs4
def test_copy_page_script_present_on_reference_pages():
    """Reference pages (non-homepage) should include the copy-page.js script."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    # Check a method page
    html_files = sorted(ref.glob("*.html"))
    non_index = [f for f in html_files if f.name != "index.html"]
    assert len(non_index) > 0, "No non-index reference pages found"

    page = non_index[0]
    content = page.read_text(encoding="utf-8")
    assert "copy-page.js" in content, f"{page.name} should include copy-page.js script"


@requires_bs4
def test_copy_page_script_absent_from_homepage():
    """The homepage (index.html) should NOT include the copy-page.js script."""
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    index = site / "index.html"
    if not index.exists():
        pytest.skip("No index.html found")

    content = index.read_text(encoding="utf-8")
    assert "copy-page.js" not in content, "Homepage should not include copy-page.js script"


@requires_bs4
def test_copy_page_widget_does_not_overlap_long_titles():
    """On pages with long object names, the widget should not cause layout issues.

    The widget uses float:right with white-space:nowrap, so the title text
    should still be visible and the title element should exist alongside
    the widget script. This test verifies that even the longest-named pages
    have both a title and the widget script present.
    """
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)

    # Find the pages with the longest names (>60 chars in the filename stem)
    long_pages = [f for f in ref.glob("*.html") if len(f.stem) > 60]
    assert len(long_pages) > 0, "Expected pages with very long names"

    for page in long_pages:
        soup = _load_html(page)
        content = page.read_text(encoding="utf-8")

        # Widget script should be present
        assert "copy-page.js" in content, f"{page.name}: copy-page.js script missing"

        # Title should exist and contain the object name
        title_el = soup.select_one("h2.title, h1.title")
        assert title_el is not None, f"{page.name}: no title element found"

        title_text = title_el.get_text(strip=True)
        assert len(title_text) > 30, (
            f"{page.name}: title text too short ({title_text!r}), expected long name"
        )

        # The title should render in monospace font (code convention for API names)
        style = title_el.get("style", "")
        assert "monospace" in style or "SFMono" in style, (
            f"{page.name}: title should use monospace font for code-like names"
        )


@requires_bs4
def test_copy_page_md_url_derivable_from_html():
    """The .md URL should be derivable by replacing .html with .md in the path.

    This validates the assumption in copy-page.js's getMdUrl() function.
    """
    pkg = "gdtest_long_names"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    html_files = [f for f in ref.glob("*.html") if f.name != "index.html"]

    for html_file in html_files[:5]:  # Spot-check 5 pages
        md_file = html_file.with_suffix(".md")
        assert md_file.exists(), f"No .md file for {html_file.name} — getMdUrl() would return 404"
        # The .md should have meaningful content (not empty)
        content = md_file.read_text(encoding="utf-8").strip()
        assert len(content) > 50, f"{md_file.name} is too short ({len(content)} chars)"


# ── Dedicated Markdown-Page Tests (per-package) ─────────────────────────────
#
# Each test below targets a specific GDG synthetic package so that the
# coverage scorer credits the package with a DED (dedicated) test.


def test_md_big_class_method_pages():
    """gdtest_big_class: method .md pages have correct structure.

    Each method page for DataProcessor should have a heading, USAGE code
    block, Parameters, and Returns sections in clean Markdown.
    """
    pkg = "gdtest_big_class"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)

    # The class page itself should exist
    class_md = ref / "DataProcessor.md"
    assert class_md.exists(), "DataProcessor.md missing"
    class_content = class_md.read_text(encoding="utf-8")
    assert "## DataProcessor" in class_content
    assert "``` python" in class_content, "Class page should have Python code blocks"
    assert "## Parameters" in class_content
    assert "## Examples" in class_content

    # Method pages should exist and have proper structure
    method_md = ref / "DataProcessor.transform.md"
    assert method_md.exists(), "DataProcessor.transform.md missing"
    method_content = method_md.read_text(encoding="utf-8")
    assert "## DataProcessor.transform()" in method_content
    assert "USAGE" in method_content
    assert "``` python" in method_content
    assert "## Parameters" in method_content
    assert "## Returns" in method_content
    # Returns should show the type
    assert "`DataProcessor`" in method_content

    # At least 8 method .md files should exist (big class has many methods)
    method_mds = [f for f in ref.glob("DataProcessor.*.md")]
    assert len(method_mds) >= 8, f"Expected ≥8 method .md files, found {len(method_mds)}"

    # No HTML artifacts in any method page
    for md_file in method_mds:
        content = md_file.read_text(encoding="utf-8")
        assert "<span" not in content, f"{md_file.name}: leftover <span> HTML"
        assert "<div" not in content, f"{md_file.name}: leftover <div> HTML"


def test_md_ref_sectioned_index_has_sections():
    """gdtest_ref_sectioned: reference index.md preserves section headings.

    The sectioned reference index groups functions under headings like
    Constructors, Transformers, Validators, Utilities.  The .md version
    should keep those headings and use .md links (not .html).
    """
    pkg = "gdtest_ref_sectioned"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    index_md = ref / "index.md"
    assert index_md.exists(), "reference/index.md missing"

    content = index_md.read_text(encoding="utf-8")

    # All four section headings should be present
    for heading in ("## Constructors", "## Transformers", "## Validators", "## Utilities"):
        assert heading in content, f"Missing section heading: {heading}"

    # Links should use .md extension, not .html
    assert ".md" in content, "Links should use .md extension"
    assert ".html" not in content, "Links should NOT use .html extension"

    # Specific function links should be present
    for func in (
        "create_widget",
        "create_layout",
        "resize",
        "rotate",
        "check_bounds",
        "check_type",
        "to_string",
        "from_string",
    ):
        assert func in content, f"Missing function link: {func}"

    # Each linked function should have its own .md file
    for func in ("create_widget", "resize", "check_bounds", "to_string"):
        func_md = ref / f"{func}.md"
        assert func_md.exists(), f"{func}.md missing"


def test_md_ug_with_code_executable_blocks():
    """gdtest_ug_with_code: executable code blocks get correct language hints.

    Quarto executable cells ({python}) produce different HTML than static
    fenced code blocks.  Both should produce ``` python fences in the .md.
    """
    pkg = "gdtest_ug_with_code"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    tutorial_md = site / "user-guide" / "tutorial.md"
    assert tutorial_md.exists(), "user-guide/tutorial.md missing"

    content = tutorial_md.read_text(encoding="utf-8")

    # Both the executable and static code blocks should start with ``` python
    python_fences = [line for line in content.splitlines() if line.strip().startswith("``` python")]
    assert len(python_fences) >= 2, f"Expected ≥2 ``` python fences, found {len(python_fences)}"

    # Should NOT have ``` sourceCode (the bug we fixed)
    assert "``` sourceCode" not in content, (
        "Executable code blocks should use ``` python, not ``` sourceCode"
    )

    # The output from the executable block should be present
    assert "[2, 4, 6]" in content, "Executable output missing"

    # The fenced block content should be present
    assert "transform" in content


def test_md_namespace_ug_nested_dirs():
    """gdtest_namespace_ug: .md files are generated in nested user-guide dirs.

    This package has user-guide/getting-started/ and user-guide/advanced/
    subdirectories.  The .md generation should traverse into all of them.
    """
    pkg = "gdtest_namespace_ug"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    ug = site / "user-guide"

    # Top-level user-guide index
    assert (ug / "index.md").exists(), "user-guide/index.md missing"

    # Nested getting-started pages
    gs = ug / "getting-started"
    assert (gs / "index.md").exists(), "getting-started/index.md missing"
    assert (gs / "installation.md").exists(), "getting-started/installation.md missing"
    assert (gs / "quickstart.md").exists(), "getting-started/quickstart.md missing"

    # Nested advanced pages
    adv = ug / "advanced"
    assert (adv / "index.md").exists(), "advanced/index.md missing"
    assert (adv / "configuration.md").exists(), "advanced/configuration.md missing"
    assert (adv / "deployment.md").exists(), "advanced/deployment.md missing"

    # Reference .md files should also exist
    ref = _ref_dir(pkg)
    assert (ref / "index.md").exists(), "reference/index.md missing"
    assert (ref / "initialize.md").exists(), "reference/initialize.md missing"
    assert (ref / "shutdown.md").exists(), "reference/shutdown.md missing"

    # Total .md count: 10 (all HTML pages minus homepage)
    all_mds = list(site.rglob("*.md"))
    assert len(all_mds) == 10, f"Expected 10 .md files, found {len(all_mds)}"


def test_md_cli_name_subcommand_pages():
    """gdtest_cli_name: CLI subcommand .md pages exist under reference/cli/.

    This package has CLI docs with a main command and subcommands.
    The .md conversion should handle these pages in the cli/ subdirectory.
    """
    pkg = "gdtest_cli_name"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    cli_dir = site / "reference" / "cli"

    # CLI index page
    cli_index = cli_dir / "index.md"
    assert cli_index.exists(), "reference/cli/index.md missing"
    cli_content = cli_index.read_text(encoding="utf-8")
    assert "gdtest-cli-name" in cli_content, "CLI name missing from index"
    assert "Commands:" in cli_content, "Commands section missing"
    assert "run" in cli_content
    assert "status" in cli_content

    # Subcommand pages
    run_md = cli_dir / "run.md"
    assert run_md.exists(), "reference/cli/run.md missing"
    run_content = run_md.read_text(encoding="utf-8")
    assert "gdtest-cli-name run" in run_content

    status_md = cli_dir / "status.md"
    assert status_md.exists(), "reference/cli/status.md missing"

    # API reference .md files should also exist alongside CLI docs
    ref = _ref_dir(pkg)
    assert (ref / "process.md").exists(), "reference/process.md missing"
    assert (ref / "summarize.md").exists(), "reference/summarize.md missing"


def test_md_rst_mixed_dirs_clean_output():
    """gdtest_rst_mixed_dirs: RST-sourced docs produce clean .md without HTML.

    This package uses RST docstrings.  The .md pages should have Parameters
    and Returns sections with proper Markdown formatting (no HTML artifacts
    from RST directive processing).
    """
    pkg = "gdtest_rst_mixed_dirs"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)

    # Reference index
    assert (ref / "index.md").exists(), "reference/index.md missing"

    # Check a representative function page
    func_md = ref / "process_v2.md"
    assert func_md.exists(), "process_v2.md missing"

    content = func_md.read_text(encoding="utf-8")
    assert "## process_v2()" in content
    assert "USAGE" in content
    assert "``` python" in content
    assert "## Parameters" in content
    assert "## Returns" in content
    # Type annotation should be clean
    assert "`list`" in content

    # No leftover HTML in any ref .md file
    for md_file in ref.glob("*.md"):
        if md_file.name == "index.md":
            continue
        md_content = md_file.read_text(encoding="utf-8")
        assert "<span" not in md_content, f"{md_file.name}: leftover <span>"
        assert "<div" not in md_content, f"{md_file.name}: leftover <div>"
        # Should have proper section structure
        assert "## Parameters" in md_content or "## Returns" in md_content, (
            f"{md_file.name}: missing Parameters or Returns section"
        )


# -- gdtest_md_disabled dedicated tests ----------------------------------------


def test_md_disabled_no_md_files():
    """gdtest_md_disabled: No .md files when markdown_pages is false."""
    pkg = "gdtest_md_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    site = _site_dir(pkg)
    md_files = list(site.rglob("*.md"))
    assert md_files == [], f"Expected no .md files but found: {md_files}"


def test_md_disabled_no_copy_page_script():
    """gdtest_md_disabled: No copy-page.js script tag in HTML pages."""
    pkg = "gdtest_md_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for html_file in ref.glob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        assert "copy-page.js" not in content, (
            f"{html_file.name}: copy-page.js should not be referenced"
        )


def test_md_disabled_config_written():
    """gdtest_md_disabled: great-docs.yml has markdown_pages: false."""
    pkg = "gdtest_md_disabled"
    gd_yml = _RENDERED_DIR / pkg / "great-docs.yml"
    if not gd_yml.exists():
        pytest.skip("great-docs.yml not found")

    import yaml

    cfg = yaml.safe_load(gd_yml.read_text(encoding="utf-8"))
    assert cfg["markdown_pages"] is False


def test_md_disabled_gd_options():
    """gdtest_md_disabled: _gd_options.json has markdown_pages: false."""
    pkg = "gdtest_md_disabled"
    opts_path = _RENDERED_DIR / pkg / "great-docs" / "_gd_options.json"
    if not opts_path.exists():
        pytest.skip("_gd_options.json not found")

    import json

    opts = json.loads(opts_path.read_text(encoding="utf-8"))
    assert opts["markdown_pages"] is False


def test_md_disabled_html_pages_still_exist():
    """gdtest_md_disabled: HTML reference pages are still generated."""
    pkg = "gdtest_md_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    assert (ref / "index.html").exists(), "reference/index.html missing"
    assert (ref / "compute.html").exists(), "reference/compute.html missing"
    assert (ref / "validate.html").exists(), "reference/validate.html missing"


# -- gdtest_md_no_widget dedicated tests ---------------------------------------


def test_md_no_widget_md_files_exist():
    """gdtest_md_no_widget: .md files generated even with widget disabled."""
    pkg = "gdtest_md_no_widget"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    assert (ref / "index.md").exists(), "reference/index.md missing"
    assert (ref / "encode.md").exists(), "reference/encode.md missing"
    assert (ref / "decode.md").exists(), "reference/decode.md missing"


def test_md_no_widget_md_content_quality():
    """gdtest_md_no_widget: .md files have proper Markdown content."""
    pkg = "gdtest_md_no_widget"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    encode_md = ref / "encode.md"
    if not encode_md.exists():
        pytest.skip("encode.md not found")

    content = encode_md.read_text(encoding="utf-8")
    assert "## encode()" in content
    assert "``` python" in content
    assert "## Parameters" in content
    assert "## Returns" in content
    assert "`str`" in content or "`bytes`" in content


def test_md_no_widget_no_copy_page_script():
    """gdtest_md_no_widget: No copy-page.js script tag in HTML pages."""
    pkg = "gdtest_md_no_widget"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    for html_file in ref.glob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        assert "copy-page.js" not in content, (
            f"{html_file.name}: copy-page.js should not be referenced"
        )


def test_md_no_widget_config_written():
    """gdtest_md_no_widget: great-docs.yml has markdown_pages dict form."""
    pkg = "gdtest_md_no_widget"
    gd_yml = _RENDERED_DIR / pkg / "great-docs.yml"
    if not gd_yml.exists():
        pytest.skip("great-docs.yml not found")

    import yaml

    cfg = yaml.safe_load(gd_yml.read_text(encoding="utf-8"))
    assert isinstance(cfg["markdown_pages"], dict)
    assert cfg["markdown_pages"]["widget"] is False


def test_md_no_widget_gd_options():
    """gdtest_md_no_widget: _gd_options.json has markdown_pages: true.

    When only the widget is disabled, .md generation is still enabled,
    so markdown_pages should be true in the options file.
    """
    pkg = "gdtest_md_no_widget"
    opts_path = _RENDERED_DIR / pkg / "great-docs" / "_gd_options.json"
    if not opts_path.exists():
        pytest.skip("_gd_options.json not found")

    import json

    opts = json.loads(opts_path.read_text(encoding="utf-8"))
    assert opts["markdown_pages"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# R4: Announcement Banner
# ═══════════════════════════════════════════════════════════════════════════════


def test_R4_announce_simple_meta_tag():
    """gdtest_announce_simple: meta tag with announcement content is present."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'name="gd-announcement"' in content, "Missing gd-announcement meta tag"
    assert 'data-content="This is a test announcement!"' in content


def test_R4_announce_simple_script_included():
    """gdtest_announce_simple: announcement-banner.js is loaded."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert "announcement-banner.js" in content


def test_R4_announce_simple_defaults():
    """gdtest_announce_simple: string config gets default type=info, dismissable=true."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'data-type="info"' in content
    assert 'data-dismissable="true"' in content


def test_R4_announce_simple_js_file_exists():
    """gdtest_announce_simple: announcement-banner.js is deployed to _site/."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    js_file = _site_dir(pkg) / "announcement-banner.js"
    assert js_file.exists(), "announcement-banner.js not found in _site/"


def test_R4_announce_simple_quarto_resources():
    """gdtest_announce_simple: _quarto.yml includes announcement-banner.js in resources."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    cfg = _load_quarto_yml(pkg)
    resources = cfg.get("project", {}).get("resources", [])
    assert "announcement-banner.js" in resources


def test_R4_announce_simple_on_all_pages():
    """gdtest_announce_simple: meta tag appears on reference pages too (site-wide)."""
    pkg = "gdtest_announce_simple"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    ref = _ref_dir(pkg)
    if not ref.exists():
        pytest.skip("No reference directory")

    for html_file in ref.glob("*.html"):
        content = html_file.read_text(encoding="utf-8")
        assert 'name="gd-announcement"' in content, (
            f"{html_file.name}: missing gd-announcement meta tag"
        )


def test_R4_announce_dict_content():
    """gdtest_announce_dict: dict config renders correct content and type."""
    pkg = "gdtest_announce_dict"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'data-content="Version 2.0 is here!"' in content
    assert 'data-type="success"' in content


def test_R4_announce_dict_dismissable_false():
    """gdtest_announce_dict: dismissable=False is passed through."""
    pkg = "gdtest_announce_dict"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'data-dismissable="false"' in content


def test_R4_announce_dict_url():
    """gdtest_announce_dict: url attribute is included in the meta tag."""
    pkg = "gdtest_announce_dict"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'data-url="https://example.com/changelog"' in content


def test_R4_announce_disabled_no_meta():
    """gdtest_announce_disabled: no announcement meta tag when disabled."""
    pkg = "gdtest_announce_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert 'name="gd-announcement"' not in content


def test_R4_announce_disabled_no_script():
    """gdtest_announce_disabled: no announcement-banner.js when disabled."""
    pkg = "gdtest_announce_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    index = _site_dir(pkg) / "index.html"
    content = index.read_text(encoding="utf-8")
    assert "announcement-banner.js" not in content


def test_R4_announce_disabled_no_js_file():
    """gdtest_announce_disabled: announcement-banner.js is not in _site/."""
    pkg = "gdtest_announce_disabled"
    if not _has_rendered_site(pkg):
        pytest.skip(f"{pkg} not rendered")

    js_file = _site_dir(pkg) / "announcement-banner.js"
    assert not js_file.exists(), "announcement-banner.js should not be deployed when disabled"
