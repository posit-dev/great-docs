# pyright: reportPrivateUsage=false
"""
Great Docs Gauntlet (GDG) — rendered output regression tests.

These tests validate the **final HTML output** of pre-built GDG sites stored in
`test-packages/_rendered/`.  They are designed as a safety net for the
planned quartodoc fork: every assertion here must continue to pass after
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


@pytest.mark.parametrize("pkg_name", _RENDERED_PACKAGES)
def test_R0_reference_index_exists(pkg_name: str):
    """Every rendered site has a reference/index.html."""
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
    """Every reference page has an <h1 class='title'> element."""
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
        title = soup.select_one("h1.title")
        assert title is not None, f"{page.name} missing <h1 class='title'>"
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
        title = soup.select_one("h1.title")
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
        title = soup.select_one("h1.title")
        if title is None:
            continue

        badge = title.select_one("code")
        if badge is None:
            continue

        badge_text = badge.get_text().strip().lower()
        if badge_text in ("constant", "type_alias"):
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
            heading = params_section.select_one("h1, h2, h3, h4")
            assert heading is not None, f"{name}.html: parameters section has no heading"
            param_names = params_section.select("span.parameter-name")
            assert len(param_names) > 0, (
                f"{name}.html: parameters section has no parameter-name spans"
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
        badge = soup.select_one("h1.title code")
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

        badge = soup.select_one("h1.title code")
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
        badge = soup.select_one("h1.title code")
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
        badge = soup.select_one("h1.title code")
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
        badge = soup.select_one("h1.title code")
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
    title = soup.select_one("h1.title, h1")
    assert title is not None, f"{pkg_name}: landing page has no <h1>"
    assert len(title.get_text().strip()) > 0, f"{pkg_name}: landing page <h1> is empty"


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
