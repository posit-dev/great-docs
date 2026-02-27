# pyright: reportPrivateUsage=false
"""
Tests for the Great Docs Gauntlet (GDG).

These tests exercise Great Docs against spec-driven GDG packages that
cover every feature dimension.  The tests are organized by assertion level:

- **L0**: Package/module name detection (instant, no I/O)
- **L1**: Export discovery + section structure (fast, griffe only)
- **L2**: `great-docs init` / config generation (fast, file I/O)
- **L3**: `_quarto.yml` + `.qmd` generation (medium)
- **L4**: Full Quarto render to HTML (slow, nightly only)

Run with:
    pytest tests/test_synthetic.py -v
    pytest tests/test_synthetic.py -v -k "L0"           # just detection
    pytest tests/test_synthetic.py -v -k "gdtest_minimal"  # one package
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from great_docs import GreatDocs

# ── Setup: make test-packages/synthetic importable ───────────────────────────

_SYNTHETIC_DIR = Path(__file__).resolve().parent.parent / "test-packages"
if str(_SYNTHETIC_DIR) not in sys.path:
    sys.path.insert(0, str(_SYNTHETIC_DIR))

from synthetic.catalog import ALL_PACKAGES, get_spec  # noqa: E402
from synthetic.generator import generate_package  # noqa: E402

# ── Phase 1 packages (the initial 5 specs implemented) ───────────────────────

PHASE1_PACKAGES = [
    "gdtest_minimal",
    "gdtest_src_layout",
    "gdtest_big_class",
    "gdtest_seealso",
    "gdtest_kitchen_sink",
]

# Only parametrize over specs that actually exist on disk.
# As more specs are added in later phases they'll automatically be picked up.
_AVAILABLE_PACKAGES = []
for _name in ALL_PACKAGES:
    _spec_file = _SYNTHETIC_DIR / "synthetic" / "specs" / f"{_name}.py"
    if _spec_file.exists():
        _AVAILABLE_PACKAGES.append(_name)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_package(pkg_name: str, tmp_path: Path) -> tuple[Path, dict]:
    """Generate a synthetic package and return (pkg_dir, spec)."""
    spec = get_spec(pkg_name)
    pkg_dir = generate_package(spec, tmp_path)

    # Add pkg_dir to sys.path so griffe/importlib can find the module
    if str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))

    # For non-flat layouts, add the appropriate subfolder
    for subdir_name in ("src", "python", "lib"):
        sub = pkg_dir / subdir_name
        if sub.is_dir() and str(sub) not in sys.path:
            sys.path.insert(0, str(sub))

    return pkg_dir, spec


# ═══════════════════════════════════════════════════════════════════════════════
# L0: Package & Module Detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L0_package_name_detection(pkg_name: str, tmp_path: Path):
    """GreatDocs correctly detects the project (PyPI) name."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "detected_name" not in expected:
        pytest.skip("No 'detected_name' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    detected = docs._detect_package_name()
    assert detected == expected["detected_name"], (
        f"Expected package name {expected['detected_name']!r}, got {detected!r}"
    )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L0_module_name_detection(pkg_name: str, tmp_path: Path):
    """GreatDocs correctly detects the importable module name."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "detected_module" not in expected:
        pytest.skip("No 'detected_module' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    module_name = expected["detected_module"]

    # Verify the module's __init__.py can be found
    init_file = docs._find_package_init(module_name)
    assert init_file is not None, f"Could not find __init__.py for module {module_name!r}"
    assert init_file.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# L1: Export Discovery & Section Generation
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L1_export_discovery(pkg_name: str, tmp_path: Path):
    """All expected exports are discovered."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "export_names" not in expected:
        pytest.skip("No 'export_names' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    module_name = expected.get("detected_module", pkg_name)
    exports = docs._parse_package_exports(module_name)

    # Packages without __all__ use griffe-based discovery
    if exports is None:
        exports = docs._discover_package_exports(module_name)

    assert exports is not None, (
        f"Neither _parse_package_exports nor _discover_package_exports found "
        f"exports for {module_name!r}"
    )

    expected_names = set(expected["export_names"])
    actual_names = set(exports)
    assert expected_names <= actual_names, (
        f"Missing exports: {expected_names - actual_names}\n"
        f"  Expected: {sorted(expected_names)}\n"
        f"  Got:      {sorted(actual_names)}"
    )

    if "num_exports" in expected:
        assert len(exports) == expected["num_exports"], (
            f"Expected {expected['num_exports']} exports, got {len(exports)}: {sorted(exports)}"
        )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L1_section_generation(pkg_name: str, tmp_path: Path):
    """Quartodoc sections match expected structure."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "section_titles" not in expected:
        pytest.skip("No 'section_titles' in spec expected outcomes")

    # Explicit reference specs are tested separately with their own config
    if expected.get("explicit_reference"):
        pytest.skip("Explicit reference config tested in test_L2_explicit_reference_config")

    docs = GreatDocs(project_path=str(pkg_dir))
    module_name = expected.get("detected_module", pkg_name)
    sections = docs._create_quartodoc_sections(module_name)

    if sections is None:
        pytest.skip(
            f"Section generation returned None for {module_name!r} "
            "(griffe cannot resolve all exports)"
        )
    assert len(sections) > 0, "No sections generated"

    actual_titles = [s["title"] for s in sections]
    for expected_title in expected["section_titles"]:
        assert expected_title in actual_titles, (
            f"Expected section title {expected_title!r} not found.\n"
            f"  Actual titles: {actual_titles}"
        )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L1_big_class_method_section(pkg_name: str, tmp_path: Path):
    """Classes with >5 methods get a separate method section."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "big_class_name" not in expected:
        pytest.skip("No 'big_class_name' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    module_name = expected.get("detected_module", pkg_name)
    sections = docs._create_quartodoc_sections(module_name)
    assert sections is not None

    big_class = expected["big_class_name"]
    method_section_title = f"{big_class} Methods"

    # The class entry should have members: []
    class_section = next((s for s in sections if s["title"] == "Classes"), None)
    if class_section is None:
        # Look for the class in any section
        class_entry = None
        for s in sections:
            for c in s.get("contents", []):
                if isinstance(c, dict) and c.get("name") == big_class:
                    class_entry = c
                    break
        if class_entry is not None:
            assert class_entry.get("members") == [], (
                f"{big_class} should have members: [], got {class_entry}"
            )
    else:
        class_entry = next(
            (
                c
                for c in class_section["contents"]
                if isinstance(c, dict) and c.get("name") == big_class
            ),
            None,
        )
        assert class_entry is not None, f"{big_class} not found in Classes section"
        assert class_entry.get("members") == [], (
            f"{big_class} should have members: [], got {class_entry}"
        )

    # There should be a separate method section
    method_section = next((s for s in sections if s["title"] == method_section_title), None)
    assert method_section is not None, (
        f"No '{method_section_title}' section found. Sections: {[s['title'] for s in sections]}"
    )

    if "big_class_method_count" in expected:
        assert len(method_section["contents"]) == expected["big_class_method_count"], (
            f"Expected {expected['big_class_method_count']} methods, "
            f"got {len(method_section['contents'])}: {method_section['contents']}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# L1: Docstring Parser Detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L1_docstring_parser_detection(pkg_name: str, tmp_path: Path):
    """Docstring format is correctly auto-detected."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "detected_parser" not in expected:
        pytest.skip("No 'detected_parser' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    module_name = expected.get("detected_module", pkg_name)
    init_file = docs._find_package_init(module_name)
    assert init_file is not None

    detected = docs._detect_docstring_style(module_name)
    assert detected == expected["detected_parser"], (
        f"Expected parser {expected['detected_parser']!r}, got {detected!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# L2: Init / Config Generation
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", PHASE1_PACKAGES)
def test_L2_init_creates_config(pkg_name: str, tmp_path: Path):
    """``great-docs init --force`` produces a valid great-docs.yml."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    config_path = pkg_dir / "great-docs.yml"
    assert config_path.exists(), "great-docs.yml was not created"

    # Config should be parseable YAML
    import yaml

    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    # Should not be None/empty
    assert config_data is not None, "great-docs.yml is empty"


@pytest.mark.parametrize("pkg_name", PHASE1_PACKAGES)
def test_L2_init_detects_correct_exports(pkg_name: str, tmp_path: Path):
    """Init generates reference sections that include expected exports."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "export_names" not in expected:
        pytest.skip("No 'export_names' in spec")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    # Read the generated config and check reference sections
    import yaml

    config_path = pkg_dir / "great-docs.yml"
    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    # Collect all content items from reference sections
    reference = config_data.get("reference", [])
    all_items: set[str] = set()
    for section in reference:
        for item in section.get("contents", []):
            if isinstance(item, str):
                all_items.add(item)
            elif isinstance(item, dict):
                name = item.get("name", "")
                all_items.add(name)
                # Also check for ClassName.method entries
                if name:
                    all_items.add(name)

    # Every expected export should be referenced somewhere
    expected_names = set(expected["export_names"])
    # Some exports may appear as ClassName.method, so extract base names
    base_items = {item.split(".")[0] for item in all_items}
    combined = all_items | base_items

    missing = expected_names - combined
    assert not missing, (
        f"Missing exports in generated config: {missing}\n  Reference items: {sorted(all_items)}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# L2: User Guide Detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_user_guide_detection(pkg_name: str, tmp_path: Path):
    """User guide presence is correctly detected."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "has_user_guide" not in expected:
        pytest.skip("No 'has_user_guide' in spec")

    has_guide = (pkg_dir / "user_guide").is_dir() or (pkg_dir / "user-guide").is_dir()

    assert has_guide == expected["has_user_guide"], (
        f"Expected has_user_guide={expected['has_user_guide']}, "
        f"but user_guide/ {'exists' if has_guide else 'does not exist'}"
    )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_user_guide_files(pkg_name: str, tmp_path: Path):
    """User guide has the expected files."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if "user_guide_files" not in expected:
        pytest.skip("No 'user_guide_files' in spec")

    guide_dir = pkg_dir / "user_guide"
    if not guide_dir.exists():
        guide_dir = pkg_dir / "user-guide"

    assert guide_dir.exists(), "No user guide directory found"

    actual_files = sorted(f.name for f in guide_dir.glob("*.qmd"))
    expected_files = sorted(expected["user_guide_files"])
    assert actual_files == expected_files, (
        f"User guide file mismatch.\n  Expected: {expected_files}\n  Actual:   {actual_files}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# L2: Supporting Pages Detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_supporting_pages(pkg_name: str, tmp_path: Path):
    """Supporting pages (LICENSE, CITATION.cff, etc.) are correctly detected."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})

    checks = {
        "has_license_page": [pkg_dir / "LICENSE"],
        "has_citation_page": [pkg_dir / "CITATION.cff"],
        "has_contributing_page": [
            pkg_dir / "CONTRIBUTING.md",
            pkg_dir / ".github" / "CONTRIBUTING.md",
        ],
        "has_code_of_conduct_page": [pkg_dir / "CODE_OF_CONDUCT.md"],
    }

    performed = False
    for key, file_paths in checks.items():
        if key in expected:
            performed = True
            found = any(fp.exists() for fp in file_paths)
            assert found == expected[key], (
                f"{key}: expected {expected[key]}, "
                f"but none of {[fp.name for fp in file_paths]} found"
            )

    if "has_assets" in expected:
        performed = True
        assert (pkg_dir / "assets").is_dir() == expected["has_assets"]

    if not performed:
        pytest.skip("No supporting page expectations in spec")


# ═══════════════════════════════════════════════════════════════════════════════
# L2: Explicit Reference Config
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_explicit_reference_config(pkg_name: str, tmp_path: Path):
    """Explicit reference config produces correct section structure."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("explicit_reference"):
        pytest.skip("Not an explicit reference config spec")

    config = spec.get("config", {})
    reference = config.get("reference", [])

    assert reference, "Spec says explicit_reference but no reference config found"

    docs = GreatDocs(project_path=str(pkg_dir))
    sections = docs._build_sections_from_reference_config(reference)
    assert sections is not None, "Sections were None from explicit reference config"
    assert len(sections) == len(reference)

    # Check section titles match
    actual_titles = [s["title"] for s in sections]
    for exp_title in expected.get("section_titles", []):
        assert exp_title in actual_titles, (
            f"Expected section {exp_title!r} not found in {actual_titles}"
        )

    # Check members:false handling
    if "members_false_classes" in expected:
        for class_name in expected["members_false_classes"]:
            found = False
            for section in sections:
                for item in section.get("contents", []):
                    if isinstance(item, dict) and item.get("name") == class_name:
                        assert item.get("members") == [], (
                            f"{class_name} should have members: [] but got {item}"
                        )
                        found = True
            assert found, f"{class_name} not found in any section"


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_explicit_reference_survives_init(pkg_name: str, tmp_path: Path):
    """``init --force`` preserves explicit reference sections from great-docs.yml."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("explicit_reference"):
        pytest.skip("Not an explicit reference config spec")

    import yaml

    config = spec.get("config", {})
    original_reference = config.get("reference", [])
    assert original_reference, "Spec says explicit_reference but no reference config found"

    original_titles = [s["title"] for s in original_reference]

    # Run init --force (this overwrites great-docs.yml)
    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    # Re-read the generated config
    config_path = pkg_dir / "great-docs.yml"
    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    regenerated_reference = config_data.get("reference", [])
    assert regenerated_reference, "reference sections are missing after init --force"

    # Section titles must match the original explicit config
    regenerated_titles = [s["title"] for s in regenerated_reference]
    assert regenerated_titles == original_titles, (
        f"init --force changed explicit reference section titles.\n"
        f"  Original: {original_titles}\n"
        f"  After init: {regenerated_titles}"
    )

    # Verify members:false entries are preserved
    if "members_false_classes" in expected:
        for class_name in expected["members_false_classes"]:
            found = False
            for section in regenerated_reference:
                for item in section.get("contents", []):
                    if isinstance(item, dict) and item.get("name") == class_name:
                        assert item.get("members") is False, (
                            f"{class_name} should have members: false after init, got {item}"
                        )
                        found = True
            assert found, (
                f"{class_name} not found in any section after init --force"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# L2: Name / Module Mismatch
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_name_module_mismatch(pkg_name: str, tmp_path: Path):
    """Packages where project name ≠ module name are handled correctly."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("name_module_mismatch"):
        pytest.skip("Not a name/module mismatch spec")

    docs = GreatDocs(project_path=str(pkg_dir))

    # Project name detection should find the pyproject.toml name
    detected_name = docs._detect_package_name()
    assert detected_name == expected["detected_name"]

    # Module should differ from normalized project name
    module_name = expected["detected_module"]
    normalized = expected["detected_name"].replace("-", "_")
    assert module_name != normalized, (
        f"Module {module_name!r} should differ from normalized project name {normalized!r}"
    )

    # The module's __init__.py should still be findable
    init_file = docs._find_package_init(module_name)
    assert init_file is not None, f"Could not find __init__.py for {module_name!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# Generator Sanity
# ═══════════════════════════════════════════════════════════════════════════════


def test_generator_creates_expected_files(tmp_path: Path):
    """Smoke test: the generator creates the right file tree."""
    spec = get_spec("gdtest_minimal")
    pkg_dir = generate_package(spec, tmp_path)

    assert pkg_dir.exists()
    assert (pkg_dir / "pyproject.toml").exists()
    assert (pkg_dir / "README.md").exists()
    assert (pkg_dir / "gdtest_minimal" / "__init__.py").exists()


def test_generator_with_config_override(tmp_path: Path):
    """Config override replaces any spec-bundled config."""
    spec = get_spec("gdtest_minimal")
    config_path = (
        Path(__file__).resolve().parent.parent
        / "test-packages"
        / "synthetic"
        / "configs"
        / "config_google.yml"
    )
    pkg_dir = generate_package(spec, tmp_path, config_override=config_path)

    config_file = pkg_dir / "great-docs.yml"
    assert config_file.exists()
    content = config_file.read_text()
    assert "google" in content


# ═══════════════════════════════════════════════════════════════════════════════
# L3: CLI Sidebar Structure
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L3_cli_sidebar_flat_paths(pkg_name: str, tmp_path: Path):
    """Flat CLI (no nested groups) produces only plain path strings in the sidebar."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_enabled"):
        pytest.skip("No 'cli_enabled' in spec")
    if expected.get("cli_has_groups"):
        pytest.skip("This test is for flat (non-grouped) CLIs only")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None

    sidebar_items = docs._generate_cli_reference_pages(cli_info)
    assert len(sidebar_items) >= 1, "No sidebar items generated"

    # First item should be the main index page
    assert sidebar_items[0] == "reference/cli/index.qmd"

    # Every item should be a plain path string (no section dicts)
    for item in sidebar_items:
        assert isinstance(item, str), (
            f"Expected plain path string, got dict: {item}"
        )
        assert item.startswith("reference/cli/"), (
            f"Sidebar path {item!r} does not start with 'reference/cli/'"
        )
        assert item.endswith(".qmd"), (
            f"Sidebar path {item!r} does not end with '.qmd'"
        )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L3_cli_sidebar_nested_structure(pkg_name: str, tmp_path: Path):
    """Nested CLI groups produce hierarchical section/contents sidebar items."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_has_groups"):
        pytest.skip("No 'cli_has_groups' in spec")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None

    sidebar_items = docs._generate_cli_reference_pages(cli_info)
    assert len(sidebar_items) >= 2, "Too few sidebar items for a grouped CLI"

    # First item should be the main index
    assert sidebar_items[0] == "reference/cli/index.qmd"

    # Collect section dicts from the sidebar items
    section_items = [item for item in sidebar_items if isinstance(item, dict)]
    assert len(section_items) > 0, (
        f"No section dicts found in sidebar items; "
        f"nested groups should use {{section: ..., contents: [...]}} structure. "
        f"Got: {sidebar_items}"
    )

    # Verify each expected group appears as a section
    if "cli_group_names" in expected:
        section_names = {s["section"] for s in section_items}
        for group_name in expected["cli_group_names"]:
            assert group_name in section_names, (
                f"Expected group {group_name!r} as a sidebar section, "
                f"but only found: {sorted(section_names)}"
            )

    # Every section dict must have 'section' and 'contents' keys
    for item in section_items:
        assert "section" in item, f"Missing 'section' key in sidebar item: {item}"
        assert "contents" in item, f"Missing 'contents' key in sidebar item: {item}"
        assert len(item["contents"]) >= 1, (
            f"Section {item['section']!r} has empty contents"
        )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L3_cli_sidebar_no_wrong_level_paths(pkg_name: str, tmp_path: Path):
    """Nested subcommand paths must not be flattened to reference/cli/<leaf>.qmd."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_has_groups"):
        pytest.skip("No 'cli_has_groups' in spec")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None

    sidebar_items = docs._generate_cli_reference_pages(cli_info)

    # Collect all string paths (including those inside section dicts)
    def _collect_paths(items: list) -> list[str]:
        paths = []
        for item in items:
            if isinstance(item, str):
                paths.append(item)
            elif isinstance(item, dict) and "contents" in item:
                paths.extend(_collect_paths(item["contents"]))
        return paths

    all_paths = _collect_paths(sidebar_items)

    # Every path must point to an actual file on disk.
    # _generate_cli_reference_pages writes files under docs.project_path
    # (i.e. <pkg_dir>/great-docs/).
    docs_dir = docs.project_path
    for path in all_paths:
        full = docs_dir / path
        assert full.exists(), (
            f"Sidebar path {path!r} does not exist on disk at {full}"
        )

    # Leaf subcommand paths (those inside a group dir on disk) must use
    # the nested prefix, not the bare reference/cli/ prefix.
    group_names = expected.get("cli_group_names", [])
    for path in all_paths:
        # Skip the index and the group overview pages themselves
        if path == "reference/cli/index.qmd":
            continue
        stem = path.split("/")[-1].replace(".qmd", "")
        if stem in [g.replace("-", "_") for g in group_names]:
            continue  # group overview page like reference/cli/task.qmd
        # Any remaining page that lives in a subdirectory on disk should
        # have the nested prefix in the sidebar path.
        parts = path.removeprefix("reference/cli/").split("/")
        if len(parts) > 1:
            # This is fine — path is already nested
            continue
        # Single-segment path: make sure it doesn't belong to a group subdir
        for group in group_names:
            nested_file = (
                docs_dir / "reference" / "cli" / group.replace("-", "_") / f"{stem}.qmd"
            )
            assert not nested_file.exists(), (
                f"Sidebar has flat path {path!r} but the file exists "
                f"at {nested_file.relative_to(docs_dir)} — the path should "
                f"be nested under the group"
            )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L3_cli_navbar_link(pkg_name: str, tmp_path: Path):
    """CLI-enabled packages do NOT get a separate navbar entry; the sidebar switcher handles it."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_enabled"):
        pytest.skip("No 'cli_enabled' in spec")

    import yaml

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)
    docs._prepare_build_directory()

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None

    cli_files = docs._generate_cli_reference_pages(cli_info)
    assert cli_files, "No CLI files generated"

    docs._update_sidebar_with_cli(cli_files)

    quarto_yml = docs.project_path / "_quarto.yml"
    assert quarto_yml.exists(), "_quarto.yml was not created"

    with open(quarto_yml, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # CLI Reference should NOT appear as a separate navbar entry —
    # navigation between API and CLI is handled by the reference-switcher widget
    navbar_left = config.get("website", {}).get("navbar", {}).get("left", [])
    cli_navbar_items = [
        item for item in navbar_left
        if isinstance(item, dict) and item.get("text") == "CLI Reference"
    ]
    assert len(cli_navbar_items) == 0, (
        f"'CLI Reference' should not appear in the navbar (handled by switcher). "
        f"Navbar left: {navbar_left}"
    )

    # The cli-reference sidebar should still be created
    sidebar = config.get("website", {}).get("sidebar", [])
    cli_sidebars = [
        s for s in sidebar
        if isinstance(s, dict) and s.get("id") == "cli-reference"
    ]
    assert len(cli_sidebars) == 1, (
        f"Expected exactly one 'cli-reference' sidebar, "
        f"got {len(cli_sidebars)}"
    )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L3_cli_and_user_guide_navbar(pkg_name: str, tmp_path: Path):
    """Packages with both CLI and user guide show all three navbar sections."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not (expected.get("cli_enabled") and expected.get("has_user_guide")):
        pytest.skip("Need both 'cli_enabled' and 'has_user_guide' in spec")

    import yaml

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)
    docs._prepare_build_directory()

    # Generate CLI docs
    detected_name = docs._detect_package_name()
    assert detected_name is not None
    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None
    cli_files = docs._generate_cli_reference_pages(cli_info)
    docs._update_sidebar_with_cli(cli_files)

    # Process user guide
    docs._process_user_guide()

    quarto_yml = docs.project_path / "_quarto.yml"
    with open(quarto_yml, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    navbar_left = config.get("website", {}).get("navbar", {}).get("left", [])
    navbar_texts = [
        item.get("text") for item in navbar_left if isinstance(item, dict)
    ]

    assert "User Guide" in navbar_texts, (
        f"'User Guide' missing from navbar. Got: {navbar_texts}"
    )
    assert "Reference" in navbar_texts, (
        f"'Reference' missing from navbar. Got: {navbar_texts}"
    )
    assert "CLI Reference" not in navbar_texts, (
        f"'CLI Reference' should not be a separate navbar entry (handled by switcher). "
        f"Got: {navbar_texts}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# L2: CLI Config Preservation
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_cli_config_preserved(pkg_name: str, tmp_path: Path):
    """``great-docs init --force`` preserves CLI config when cli_enabled is True."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_enabled"):
        pytest.skip("No 'cli_enabled' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    import yaml

    config_path = pkg_dir / "great-docs.yml"
    assert config_path.exists(), "great-docs.yml was not created"

    with open(config_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    assert config_data is not None, "great-docs.yml is empty"
    cli_section = config_data.get("cli")
    assert cli_section is not None, "CLI section missing from great-docs.yml"
    assert cli_section.get("enabled") is True, f"CLI should be enabled but got: {cli_section}"


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_cli_discovery(pkg_name: str, tmp_path: Path):
    """Click CLI commands are discovered for packages with cli_enabled=True."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_enabled"):
        pytest.skip("No 'cli_enabled' in spec expected outcomes")

    # Install the package so imports work
    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None, (
        f"CLI discovery returned None for {detected_name!r}; expected a Click CLI to be found"
    )
    assert "commands" in cli_info or "name" in cli_info, (
        f"CLI info missing expected keys: {list(cli_info.keys())}"
    )


@pytest.mark.parametrize("pkg_name", _AVAILABLE_PACKAGES)
def test_L2_cli_nested_groups(pkg_name: str, tmp_path: Path):
    """Nested Click groups are correctly discovered."""
    pkg_dir, spec = _make_package(pkg_name, tmp_path)
    expected = spec.get("expected", {})
    if not expected.get("cli_has_groups"):
        pytest.skip("No 'cli_has_groups' in spec expected outcomes")

    docs = GreatDocs(project_path=str(pkg_dir))
    docs.install(force=True)

    detected_name = docs._detect_package_name()
    assert detected_name is not None

    cli_info = docs._discover_click_cli(detected_name)
    assert cli_info is not None, "CLI discovery returned None for nested groups"

    # CLI info should have subcommands
    commands = cli_info.get("commands", [])
    assert len(commands) > 0, "No commands found in CLI group"

    # Check expected group names
    if "cli_group_names" in expected:
        command_names = {cmd.get("name") for cmd in commands}
        for group_name in expected["cli_group_names"]:
            assert group_name in command_names, (
                f"Expected group {group_name!r} not found in CLI commands: {sorted(command_names)}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Generator Sanity
# ═══════════════════════════════════════════════════════════════════════════════


def test_all_phase1_specs_loadable():
    """All Phase 1 specs can be loaded from the catalog."""
    for name in PHASE1_PACKAGES:
        spec = get_spec(name)
        assert spec["name"] == name
        assert "files" in spec
        assert "dimensions" in spec
