"""
Great Docs Gauntlet (GDG) — master catalog of all 200 test packages.

Provides the registry of package names, their specs, and dimension metadata.
Specs are lazily imported from the ``specs`` sub-package so that adding a new
package is as simple as dropping a new file into ``specs/``.
"""

from __future__ import annotations

import importlib
from typing import Any

# ── Ordered list of all package names ─────────────────────────────────────────
# The canonical ordering follows the numbering in SYNTHETIC_TEST_PLAN.md.

ALL_PACKAGES: list[str] = [
    # 01–05: Docstring format variants
    "gdtest_minimal",  # 01
    "gdtest_google",  # 02
    "gdtest_sphinx",  # 03
    "gdtest_nodocs",  # 04
    "gdtest_mixed_docs",  # 05
    # 06–13: Package layout variants
    "gdtest_src_layout",  # 06
    "gdtest_python_layout",  # 07
    "gdtest_lib_layout",  # 08
    "gdtest_hatch",  # 09
    "gdtest_setuptools_find",  # 10
    "gdtest_setup_cfg",  # 11
    "gdtest_setup_py",  # 12
    "gdtest_auto_discover",  # 13
    # 14–17: Export discovery edge cases
    "gdtest_no_all",  # 14
    "gdtest_all_concat",  # 15
    "gdtest_config_exclude",  # 16
    "gdtest_auto_exclude",  # 17
    # 18–27: Object type archetypes
    "gdtest_small_class",  # 18
    "gdtest_big_class",  # 19
    "gdtest_dataclasses",  # 20
    "gdtest_enums",  # 21
    "gdtest_typed_containers",  # 22
    "gdtest_protocols",  # 23
    "gdtest_descriptors",  # 24
    "gdtest_dunders",  # 25
    "gdtest_nested_class",  # 26
    "gdtest_constants",  # 27
    # 28–29: Directive combinations
    "gdtest_seealso",  # 28
    "gdtest_nodoc",  # 29
    # 33–38: User guide variants
    "gdtest_user_guide_auto",  # 33
    "gdtest_user_guide_sections",  # 34
    "gdtest_user_guide_subdirs",  # 35
    "gdtest_user_guide_explicit",  # 36
    "gdtest_user_guide_custom_dir",  # 37
    "gdtest_user_guide_hyphen",  # 38
    # 39–43: Landing page / index variants
    "gdtest_readme_rst",  # 39
    "gdtest_index_qmd",  # 40
    "gdtest_index_md",  # 41
    "gdtest_no_readme",  # 42
    "gdtest_index_wins",  # 43
    # 44–45: Supporting pages
    "gdtest_full_extras",  # 44
    "gdtest_github_contrib",  # 45
    # 46–47: CLI documentation
    "gdtest_cli_click",  # 46
    "gdtest_cli_nested",  # 47
    # 48–50: Config-driven features
    "gdtest_explicit_ref",  # 48
    "gdtest_kitchen_sink",  # 49
    "gdtest_name_mismatch",  # 50
    # 43–54: Cross-dimension combos
    "gdtest_src_big_class",  # 43
    "gdtest_google_big_class",  # 44
    "gdtest_user_guide_cli",  # 45
    "gdtest_explicit_big_class",  # 46
    "gdtest_src_no_all",  # 47
    "gdtest_extras_guide",  # 48
    "gdtest_google_seealso",  # 49
    "gdtest_setup_cfg_src",  # 50
    "gdtest_exclude_cli",  # 51
    "gdtest_src_explicit_ref",  # 52
    # 66–77: New API patterns
    "gdtest_async_funcs",  # 66
    "gdtest_generators",  # 67
    "gdtest_overloads",  # 68
    "gdtest_abstract_props",  # 69
    "gdtest_multi_inherit",  # 70
    "gdtest_slots_class",  # 71
    "gdtest_frozen_dc",  # 72
    "gdtest_generics",  # 73
    "gdtest_context_mgr",  # 74
    "gdtest_decorators",  # 75
    "gdtest_exceptions",  # 76
    "gdtest_reexports",  # 77
    # 78–82: Scale & stress
    "gdtest_many_exports",  # 78
    "gdtest_deep_nesting",  # 79
    "gdtest_long_docs",  # 80
    "gdtest_many_guides",  # 81
    "gdtest_many_big_classes",  # 82
    # 83–88: Build systems & layouts
    "gdtest_flit",  # 83
    "gdtest_pdm",  # 84
    "gdtest_namespace",  # 85
    "gdtest_monorepo",  # 86
    "gdtest_multi_module",  # 87
    "gdtest_src_legacy",  # 88
    # 89–95: Edge cases
    "gdtest_empty_module",  # 89
    "gdtest_all_private",  # 90
    "gdtest_duplicate_all",  # 91
    "gdtest_badge_readme",  # 92
    "gdtest_math_docs",  # 93
    "gdtest_mixed_guide_ext",  # 94
    "gdtest_unicode_docs",  # 95
    # 96–100: Config matrix
    "gdtest_config_all_on",  # 96
    "gdtest_config_display",  # 97
    "gdtest_config_minimal",  # 98
    "gdtest_config_parser",  # 99
    "gdtest_config_extra_keys",  # 100
    # ── v2: Configuration option permutations (101–125) ──
    # 01–25: Configuration option permutations
    "gdtest_github_icon",  # 01
    "gdtest_source_branch",  # 02
    "gdtest_source_path",  # 03
    "gdtest_source_title",  # 04
    "gdtest_source_disabled",  # 05
    "gdtest_sidebar_disabled",  # 06
    "gdtest_sidebar_min_items",  # 07
    "gdtest_cli_name",  # 08
    "gdtest_dynamic_false",  # 09
    "gdtest_parser_google",  # 10
    "gdtest_parser_sphinx",  # 11
    "gdtest_display_name",  # 12
    "gdtest_funding",  # 13
    "gdtest_authors_multi",  # 14
    "gdtest_no_darkmode",  # 15
    "gdtest_exclude_list",  # 16
    "gdtest_jupyter_kernel",  # 17
    "gdtest_config_sections",  # 18
    "gdtest_config_ug_string",  # 19
    "gdtest_config_ug_list",  # 20
    "gdtest_config_changelog",  # 21
    "gdtest_config_reference",  # 22
    "gdtest_config_combo_a",  # 23
    "gdtest_config_combo_b",  # 24
    "gdtest_config_combo_c",  # 25
    "gdtest_config_combo_d",  # 26
    "gdtest_config_combo_e",  # 27
    "gdtest_config_combo_f",  # 28
    # 29–53: Docstring richness & post-render
    "gdtest_rst_versionadded",  # 26
    "gdtest_rst_deprecated",  # 27
    "gdtest_rst_note",  # 28
    "gdtest_rst_warning",  # 29
    "gdtest_rst_tip",  # 30
    "gdtest_rst_caution",  # 31
    "gdtest_rst_danger",  # 32
    "gdtest_rst_important",  # 33
    "gdtest_rst_mixed_dirs",  # 34
    "gdtest_sphinx_func_role",  # 35
    "gdtest_sphinx_class_role",  # 36
    "gdtest_sphinx_exc_role",  # 37
    "gdtest_sphinx_meth_role",  # 38
    "gdtest_sphinx_mixed_roles",  # 39
    "gdtest_numpy_rich",  # 40
    "gdtest_google_rich",  # 41
    "gdtest_sphinx_rich",  # 42
    "gdtest_docstring_examples",  # 43
    "gdtest_docstring_notes",  # 44
    "gdtest_docstring_warnings",  # 45
    "gdtest_docstring_references",  # 46
    "gdtest_docstring_seealso",  # 47
    "gdtest_docstring_math",  # 48
    "gdtest_docstring_tables",  # 49
    "gdtest_docstring_combo",  # 50
    # 51–65: User guide variations
    "gdtest_ug_auto",  # 51
    "gdtest_ug_numbered",  # 52
    "gdtest_ug_sections_fm",  # 53
    "gdtest_ug_subdirs",  # 54
    "gdtest_ug_custom_dir",  # 55
    "gdtest_ug_deep_nest",  # 56
    "gdtest_ug_mixed_ext",  # 57
    "gdtest_ug_many_pages",  # 58
    "gdtest_ug_explicit_order",  # 59
    "gdtest_ug_single_page",  # 60
    "gdtest_ug_no_frontmatter",  # 61
    "gdtest_ug_with_code",  # 62
    "gdtest_ug_with_images",  # 63
    "gdtest_ug_hyphen_dir",  # 64
    "gdtest_ug_combo",  # 65
    # 66–75: Custom sections
    "gdtest_sec_examples",  # 66
    "gdtest_sec_tutorials",  # 67
    "gdtest_sec_recipes",  # 68
    "gdtest_sec_blog",  # 69
    "gdtest_sec_faq",  # 70
    "gdtest_sec_multi",  # 71
    "gdtest_sec_navbar_after",  # 72
    "gdtest_sec_with_ug",  # 73
    "gdtest_sec_with_ref",  # 74
    "gdtest_sec_deep",  # 75
    # 76–85: Reference config
    "gdtest_ref_explicit",  # 76
    "gdtest_ref_members_false",  # 77
    "gdtest_ref_mixed",  # 78
    "gdtest_ref_reorder",  # 79
    "gdtest_ref_sectioned",  # 80
    "gdtest_ref_single_section",  # 81
    "gdtest_ref_module_expand",  # 82
    "gdtest_ref_big_class",  # 83
    "gdtest_ref_multi_big",  # 84
    "gdtest_ref_title",  # 85
    # 86–95: Site theming & display
    "gdtest_theme_cosmo",  # 86
    "gdtest_theme_lumen",  # 87
    "gdtest_theme_cerulean",  # 88
    "gdtest_toc_disabled",  # 89
    "gdtest_toc_depth",  # 90
    "gdtest_toc_title",  # 91
    "gdtest_site_combo",  # 92
    "gdtest_display_badges",  # 93
    "gdtest_display_authors",  # 94
    "gdtest_display_funding",  # 95
    # 96–100: Cross-feature stress tests
    "gdtest_stress_all_config",  # 96
    "gdtest_stress_all_docstr",  # 97
    "gdtest_stress_all_ug",  # 98
    "gdtest_stress_all_sections",  # 99
    "gdtest_stress_everything",  # 100
    # 101–105: Cross-dimension combos (layout × docstrings × directives)
    "gdtest_src_google_seealso",  # 101
    "gdtest_hatch_nodoc",  # 102
    "gdtest_pdm_big_class",  # 103
    "gdtest_flit_enums",  # 104
    "gdtest_namespace_ug",  # 105
    # 106: Subdirectory user guide with numeric prefixes
    "gdtest_ug_subdir_numbered",  # 106
]


# ── Dimension metadata ───────────────────────────────────────────────────────

DIMENSIONS: dict[str, dict[str, str]] = {
    "A1": {"axis": "layout", "label": "Flat layout"},
    "A2": {"axis": "layout", "label": "src/ layout"},
    "A3": {"axis": "layout", "label": "python/ layout"},
    "A4": {"axis": "layout", "label": "lib/ layout"},
    "A5": {"axis": "layout", "label": "Hatch layout"},
    "A6": {"axis": "layout", "label": "Setuptools find"},
    "A7": {"axis": "layout", "label": "setup.cfg only"},
    "A8": {"axis": "layout", "label": "setup.py only"},
    "A9": {"axis": "layout", "label": "Auto-discover"},
    "A10": {"axis": "layout", "label": "Flit build"},
    "A11": {"axis": "layout", "label": "PDM build"},
    "A12": {"axis": "layout", "label": "Namespace package"},
    "A13": {"axis": "layout", "label": "Monorepo sub-dir"},
    "B1": {"axis": "exports", "label": "Explicit __all__"},
    "B2": {"axis": "exports", "label": "__all__ concatenation"},
    "B3": {"axis": "exports", "label": "No __all__ (griffe)"},
    "B4": {"axis": "exports", "label": "__all__ concatenation (B2 alias)"},
    "B5": {"axis": "exports", "label": "Config exclude"},
    "B6": {"axis": "exports", "label": "Submodule exports"},
    "B7": {"axis": "exports", "label": "AUTO_EXCLUDE names"},
    "B8": {"axis": "exports", "label": "Multi-module re-export"},
    "C1": {"axis": "objects", "label": "Functions only"},
    "C2": {"axis": "objects", "label": "Small classes (≤5)"},
    "C3": {"axis": "objects", "label": "Big class (>5)"},
    "C4": {"axis": "objects", "label": "Mixed class+func"},
    "C5": {"axis": "objects", "label": "Dataclasses"},
    "C6": {"axis": "objects", "label": "Enums"},
    "C7": {"axis": "objects", "label": "NamedTuple/TypedDict"},
    "C8": {"axis": "objects", "label": "ABC/Protocol"},
    "C9": {"axis": "objects", "label": "Descriptors"},
    "C10": {"axis": "objects", "label": "Dunder methods"},
    "C11": {"axis": "objects", "label": "Nested classes"},
    "C12": {"axis": "objects", "label": "Constants/aliases"},
    "C13": {"axis": "objects", "label": "Async functions"},
    "C14": {"axis": "objects", "label": "Generator functions"},
    "C15": {"axis": "objects", "label": "Overloaded functions"},
    "C16": {"axis": "objects", "label": "Abstract properties"},
    "C17": {"axis": "objects", "label": "Multiple inheritance"},
    "C18": {"axis": "objects", "label": "__slots__ classes"},
    "C19": {"axis": "objects", "label": "Frozen dataclasses"},
    "C20": {"axis": "objects", "label": "Generic classes"},
    "C21": {"axis": "objects", "label": "Context managers"},
    "C22": {"axis": "objects", "label": "Decorator functions"},
    "C23": {"axis": "objects", "label": "Custom exceptions"},
    "C24": {"axis": "objects", "label": "Re-exported symbols"},
    "D1": {"axis": "docstrings", "label": "NumPy"},
    "D2": {"axis": "docstrings", "label": "Google"},
    "D3": {"axis": "docstrings", "label": "Sphinx"},
    "D4": {"axis": "docstrings", "label": "No docstrings"},
    "D5": {"axis": "docstrings", "label": "Mixed styles"},
    "E3": {"axis": "directives", "label": "%seealso"},
    "E4": {"axis": "directives", "label": "%nodoc"},
    "E5": {"axis": "directives", "label": "Mixed directives"},
    "E6": {"axis": "directives", "label": "No directives"},
    "F1": {"axis": "user_guide", "label": "Auto-discover"},
    "F2": {"axis": "user_guide", "label": "Frontmatter sections"},
    "F3": {"axis": "user_guide", "label": "Subdirectories"},
    "F4": {"axis": "user_guide", "label": "Explicit ordering"},
    "F5": {"axis": "user_guide", "label": "Custom dir"},
    "F6": {"axis": "user_guide", "label": "No user guide"},
    "F7": {"axis": "user_guide", "label": "Hyphenated dir"},
    "G1": {"axis": "landing", "label": "README.md"},
    "G2": {"axis": "landing", "label": "README.rst"},
    "G3": {"axis": "landing", "label": "index.qmd"},
    "G4": {"axis": "landing", "label": "index.md"},
    "G5": {"axis": "landing", "label": "No readme"},
    "G6": {"axis": "landing", "label": "index.qmd wins"},
    "H1": {"axis": "extras", "label": "LICENSE"},
    "H2": {"axis": "extras", "label": "CITATION.cff"},
    "H3": {"axis": "extras", "label": "CONTRIBUTING.md"},
    "H4": {"axis": "extras", "label": "CODE_OF_CONDUCT.md"},
    "H5": {"axis": "extras", "label": ".github/CONTRIBUTING.md"},
    "H6": {"axis": "extras", "label": "assets/"},
    "H7": {"axis": "extras", "label": "No extras"},
    # ── v2 axes ──
    # Config axes
    "K1": {"axis": "config", "label": "github_style: icon"},
    "K2": {"axis": "config", "label": "source.branch override"},
    "K3": {"axis": "config", "label": "source.path override"},
    "K4": {"axis": "config", "label": "source.placement: title"},
    "K5": {"axis": "config", "label": "source.enabled: false"},
    "K6": {"axis": "config", "label": "sidebar_filter.enabled: false"},
    "K7": {"axis": "config", "label": "sidebar_filter.min_items"},
    "K8": {"axis": "config", "label": "cli.name explicit"},
    "K9": {"axis": "config", "label": "dynamic: false"},
    "K10": {"axis": "config", "label": "parser: google"},
    "K11": {"axis": "config", "label": "parser: sphinx"},
    "K12": {"axis": "config", "label": "display_name override"},
    "K13": {"axis": "config", "label": "funding config"},
    "K14": {"axis": "config", "label": "multiple authors"},
    "K15": {"axis": "config", "label": "dark_mode_toggle: false"},
    "K16": {"axis": "config", "label": "exclude list"},
    "K17": {"axis": "config", "label": "jupyter kernel"},
    "K18": {"axis": "config", "label": "sections config"},
    "K19": {"axis": "config", "label": "user_guide: string"},
    "K20": {"axis": "config", "label": "user_guide: list"},
    "K21": {"axis": "config", "label": "changelog config"},
    "K22": {"axis": "config", "label": "reference config"},
    # Docstring richness axes
    "L1": {"axis": "docstring", "label": ".. versionadded::"},
    "L2": {"axis": "docstring", "label": ".. deprecated::"},
    "L3": {"axis": "docstring", "label": ".. note::"},
    "L4": {"axis": "docstring", "label": ".. warning::"},
    "L5": {"axis": "docstring", "label": ".. tip::"},
    "L6": {"axis": "docstring", "label": ".. caution::"},
    "L7": {"axis": "docstring", "label": ".. danger::"},
    "L8": {"axis": "docstring", "label": ".. important::"},
    "L9": {"axis": "docstring", "label": "Mixed RST directives"},
    "L10": {"axis": "docstring", "label": ":py:func: role"},
    "L11": {"axis": "docstring", "label": ":py:class: role"},
    "L12": {"axis": "docstring", "label": ":py:exc: role"},
    "L13": {"axis": "docstring", "label": ":py:meth: role"},
    "L14": {"axis": "docstring", "label": "Mixed Sphinx roles"},
    "L15": {"axis": "docstring", "label": "Rich numpy sections"},
    "L16": {"axis": "docstring", "label": "Rich google sections"},
    "L17": {"axis": "docstring", "label": "Rich sphinx sections"},
    "L18": {"axis": "docstring", "label": "Examples section"},
    "L19": {"axis": "docstring", "label": "Notes section"},
    "L20": {"axis": "docstring", "label": "Warnings section"},
    "L21": {"axis": "docstring", "label": "References section"},
    "L22": {"axis": "docstring", "label": "See Also section"},
    "L23": {"axis": "docstring", "label": "Math in docstrings"},
    "L24": {"axis": "docstring", "label": "Tables in docstrings"},
    # User guide axes
    "M1": {"axis": "user_guide", "label": "Auto-discover UG"},
    "M2": {"axis": "user_guide", "label": "Numbered UG files"},
    "M3": {"axis": "user_guide", "label": "Frontmatter sections"},
    "M4": {"axis": "user_guide", "label": "Subdirectory UG"},
    "M5": {"axis": "user_guide", "label": "Custom UG dir"},
    "M6": {"axis": "user_guide", "label": "Deeply nested UG"},
    "M7": {"axis": "user_guide", "label": "Mixed .qmd/.md"},
    "M8": {"axis": "user_guide", "label": "Many UG pages"},
    "M9": {"axis": "user_guide", "label": "Explicit ordering"},
    "M10": {"axis": "user_guide", "label": "Single page UG"},
    "M11": {"axis": "user_guide", "label": "No frontmatter UG"},
    "M12": {"axis": "user_guide", "label": "UG with code blocks"},
    "M13": {"axis": "user_guide", "label": "Hyphenated UG dir"},
    # Sections axes
    "N1": {"axis": "sections", "label": "Examples section"},
    "N2": {"axis": "sections", "label": "Tutorials section"},
    "N3": {"axis": "sections", "label": "Recipes section"},
    "N4": {"axis": "sections", "label": "Blog section"},
    "N5": {"axis": "sections", "label": "FAQ section"},
    "N6": {"axis": "sections", "label": "Multiple sections"},
    "N7": {"axis": "sections", "label": "navbar_after"},
    # Reference axes
    "P1": {"axis": "reference", "label": "Explicit reference"},
    "P2": {"axis": "reference", "label": "members: false"},
    "P3": {"axis": "reference", "label": "Mixed auto+explicit"},
    "P4": {"axis": "reference", "label": "Reordered sections"},
    "P5": {"axis": "reference", "label": "Multi-section ref"},
    "P6": {"axis": "reference", "label": "Module expansion"},
    "P7": {"axis": "reference", "label": "Big class ref"},
    "P8": {"axis": "reference", "label": "Reference title"},
    # Site/theme axes
    "Q1": {"axis": "theme", "label": "Cosmo theme"},
    "Q2": {"axis": "theme", "label": "Lumen theme"},
    "Q3": {"axis": "theme", "label": "Cerulean theme"},
    "Q4": {"axis": "theme", "label": "TOC disabled"},
    "Q5": {"axis": "theme", "label": "TOC depth 3"},
    "Q6": {"axis": "theme", "label": "Custom TOC title"},
    "Q7": {"axis": "theme", "label": "Site combo"},
}


# ── Plain-English package descriptions ────────────────────────────────────────
# Each entry gives a human-friendly explanation of what the synthetic package
# exercises and why it matters. Displayed on the hub card and detail pages.

PACKAGE_DESCRIPTIONS: dict[str, str] = {
    "gdtest_minimal": (
        "The simplest possible package: two functions (greet, add) with NumPy "
        "docstrings in a flat layout. On the Reference page you should see a "
        "single 'Functions' section listing both. Each function should show a "
        "Parameters table and a Returns block. If this build fails, nothing "
        "else will work."
    ),
    "gdtest_google": (
        "Three functions (connect, disconnect, send_message) documented in "
        "Google style with Args/Returns/Raises sections. On the Reference page "
        "you should see a 'Functions' section. Each function's rendered docs "
        "should display parameter tables and return types parsed from the "
        "Google-style format — not raw 'Args:' text."
    ),
    "gdtest_sphinx": (
        "Three exports (Timer class, start_timer, format_duration) with "
        "classic Sphinx :param:/:returns:/:rtype:/:raises: field lists. On "
        "the Reference page you should see 'Classes' and 'Functions' sections. "
        "Parameter types and defaults should be rendered from the Sphinx field "
        "list syntax, not shown as raw :param: markers."
    ),
    "gdtest_nodocs": (
        "Four exports (Processor class, run, stop, status) with zero "
        "docstrings. On the Reference page you should see 'Classes' and "
        "'Functions' sections listing all four items, but each entry should "
        "have no description text — just the signature. The page must not "
        "crash or show broken rendering."
    ),
    "gdtest_mixed_docs": (
        "Five exports (Converter class, encode, decode, validate, transform) "
        "mixing NumPy and Google docstrings in the same module. On the "
        "Reference page you should see 'Classes' and 'Functions' sections. "
        "Both docstring styles should be rendered cleanly — NumPy Parameters "
        "tables and Google Args sections should both appear correctly."
    ),
    "gdtest_src_layout": (
        "Module lives under src/gdtest_src_layout/ (modern src-layout). "
        "Three exports (Widget class, create_widget, destroy_widget). On the "
        "Reference page you should see 'Classes' and 'Functions' sections. "
        "The key test: Great Docs must find the module inside src/ without "
        "any explicit path configuration."
    ),
    "gdtest_python_layout": (
        "Module lives under python/gdtest_pylayout/ (less common convention). "
        "Two functions (read_file, write_file). On the Reference page you "
        "should see a 'Functions' section with both. The key test: Great Docs "
        "searches the python/ subdirectory as a source root."
    ),
    "gdtest_lib_layout": (
        "Module lives under lib/gdtest_lib_layout/. Two functions "
        "(open_connection, close_connection). On the Reference page you should "
        "see a 'Functions' section with both. The key test: lib/ is recognized "
        "as a source root alongside src/ and python/."
    ),
    "gdtest_hatch": (
        "Uses the Hatch build system with [tool.hatch.build.targets.wheel] "
        "specifying the package location. The module name (gdtest_hatch_pkg) "
        "differs from the project name (gdtest-hatch). On the Reference page "
        "you should see 'Classes' (Builder) and 'Functions' (build, clean). "
        "The key test: module discovery via Hatch metadata."
    ),
    "gdtest_setuptools_find": (
        "Uses setuptools find:packages with where=src. Module is at "
        "src/gdtest_stfind/ (different name from the project). Three exports "
        "(Scanner class, scan, report). On the Reference page you should see "
        "'Classes' and 'Functions' sections. The key test: Great Docs parses "
        "setuptools find configuration to locate the correct module."
    ),
    "gdtest_setup_cfg": (
        "No pyproject.toml — only setup.cfg for metadata. Two functions "
        "(ping, pong). On the Reference page you should see a 'Functions' "
        "section. The site title should be 'gdtest-setup-cfg' (read from "
        "setup.cfg [metadata]). The key test: metadata detection falls back "
        "to setup.cfg."
    ),
    "gdtest_setup_py": (
        "No pyproject.toml, no setup.cfg — only a legacy setup.py. Two "
        "functions (echo, reverse). On the Reference page you should see a "
        "'Functions' section. The site title should be 'gdtest-setup-py'. "
        "The key test: name detection falls back to parsing setup.py."
    ),
    "gdtest_auto_discover": (
        "No pyproject.toml, no setup.cfg, no setup.py — zero metadata files. "
        "Three exports (Engine class, ignite, shutdown). On the Reference page "
        "you should see 'Classes' and 'Functions' sections. The key test: "
        "Great Docs discovers the package purely from directory structure."
    ),
    "gdtest_no_all": (
        "Module defines functions and classes but has no __all__ list. Three "
        "exports (Registry class, create_registry, list_keys) discovered via "
        "griffe fallback. On the Reference page you should see these three "
        "items but NOT any names starting with underscore. The key test: "
        "griffe-based public API inference without __all__."
    ),
    "gdtest_all_concat": (
        "Builds __all__ by concatenating sub-module __all__ lists "
        "(__all__ = _models.__all__ + _utils.__all__). Because the AST parser "
        "cannot extract a non-literal list, the system falls back to griffe "
        "discovery. On the Reference page you should see Record, "
        "validate_record, format_output, and parse_input — all four exports "
        "from the two submodules."
    ),
    "gdtest_config_exclude": (
        "All four exports are in __all__, but great-docs.yml excludes "
        "helper_func and InternalClass. On the Reference page you should see "
        "only PublicAPI and transform — the excluded items must be absent. "
        "The key test: config-level exclusion via the exclude list in "
        "great-docs.yml."
    ),
    "gdtest_auto_exclude": (
        "Module exports common boilerplate names (main, cli, config, utils, "
        "logger) alongside real API (MyClass, real_func). On the Reference "
        "page you should see only MyClass and real_func — the AUTO_EXCLUDE "
        "names must be filtered out automatically."
    ),
    "gdtest_small_class": (
        "Two small classes (Point, Color) each with ≤5 methods. On the "
        "Reference page you should see a 'Classes' section where methods are "
        "rendered inline within each class entry — there should be NO separate "
        "'Point Methods' or 'Color Methods' subsection pages."
    ),
    "gdtest_big_class": (
        "DataProcessor class has 8 public methods, exceeding the threshold "
        "for expanded rendering. On the Reference page you should see three "
        "sections: 'Classes', 'DataProcessor Methods' (a dedicated subsection "
        "listing all 8 methods), and 'Functions' (load_data, save_data). "
        "The key test: big-class method extraction into a separate section."
    ),
    "gdtest_dataclasses": (
        "Two @dataclass types (Config, Record) with typed fields, defaults, "
        "and field() calls. On the Reference page you should see a "
        "'Dataclasses' section. Each dataclass should show its field "
        "signatures with type annotations and default values rendered in "
        "the constructor docs."
    ),
    "gdtest_enums": (
        "Two enum types: Color (Enum with RED/GREEN/BLUE) and Priority "
        "(IntEnum with LOW/MEDIUM/HIGH). On the Reference page you should "
        "see an 'Enums' section listing both. Enum members and their values "
        "should be visible in the rendered docs."
    ),
    "gdtest_typed_containers": (
        "Coordinate (NamedTuple) and UserProfile (TypedDict) — typed "
        "container types with field-level annotations. On the Reference page "
        "you should see a 'Named Tuples' section and a 'Typed Dicts' section. "
        "Each type's fields should appear with their type annotations intact."
    ),
    "gdtest_protocols": (
        "Serializable (ABC) and Renderable (Protocol) with abstract methods. "
        "On the Reference page you should see a 'Classes' section listing "
        "both. Abstract methods should be shown with their signatures. "
        "The key test: ABC/Protocol types are handled without errors."
    ),
    "gdtest_descriptors": (
        "Resource class with @property (name), @classmethod (from_dict), and "
        "@staticmethod (validate). On the Reference page you should see a "
        "'Classes' section. Each descriptor should display with its correct "
        "decorator label — property, classmethod, or staticmethod markers."
    ),
    "gdtest_dunders": (
        "Collection class with 6 dunder methods: __init__, __repr__, __eq__, "
        "__len__, __getitem__, __iter__. On the Reference page you should see "
        "a 'Classes' section. The dunder methods should appear in the class "
        "documentation with their docstrings and signatures rendered."
    ),
    "gdtest_nested_class": (
        "Tree class with a nested Node inner class. On the Reference page you "
        "should see a 'Classes' section with Tree. The inner Node class should "
        "appear under Tree — check whether it renders as a nested entry or a "
        "separate top-level item."
    ),
    "gdtest_constants": (
        "Five exports: three constants (DEFAULT_TIMEOUT, MAX_RETRIES, "
        "SUPPORTED_FORMATS), one type alias (HandlerFunc), and one function "
        "(process). On the Reference page you should see both constants and "
        "the function listed. Constants should show their values and type "
        "annotations."
    ),
    "gdtest_seealso": (
        "Four exports (Encoder class, encode, decode, validate) with %seealso "
        "cross-references. On the Reference page, each function's docs should "
        "include a 'See Also' block with links to the related functions. "
        "For example, encode's docs should link to decode and validate."
    ),
    "gdtest_nodoc": (
        "Four exports in __all__ (Calculator, compute, reset, debug_info) but "
        "reset and debug_info are tagged with %nodoc. On the Reference page "
        "you should see only Calculator and compute — reset and debug_info "
        "must be completely absent from the rendered docs."
    ),
    "gdtest_user_guide_auto": (
        "Has user_guide/ with three numbered files: 01-intro.qmd, "
        "02-quickstart.qmd, 03-advanced.qmd. The sidebar should show a "
        "'User Guide' section with these three pages in numeric order. "
        "Clicking each should navigate to the corresponding guide page. "
        "The Reference page should show App (class) and run_app (function)."
    ),
    "gdtest_user_guide_sections": (
        "Has user_guide/ with four pages that use frontmatter guide-section "
        "keys: 01-welcome and 02-install under 'Getting Started', "
        "03-customization and 04-plugins under 'Advanced'. In the sidebar, "
        "user guide pages should be grouped under these section headings, "
        "not listed flat."
    ),
    "gdtest_user_guide_subdirs": (
        "User guide pages are in subdirectories: user_guide/basics/ "
        "(01-intro.qmd, 02-setup.qmd) and user_guide/advanced/ (01-tips.qmd). "
        "The sidebar should show user guide pages preserving the subdirectory "
        "hierarchy — basics and advanced as separate groups."
    ),
    "gdtest_user_guide_explicit": (
        "User guide order is defined in great-docs.yml: 'Get Started' section "
        "(Welcome → quickstart.qmd) then 'Advanced' section (advanced.qmd). "
        "The sidebar should show exactly this ordering, ignoring filename "
        "sort. 'Welcome' should use custom text (not the filename)."
    ),
    "gdtest_user_guide_custom_dir": (
        "User guide lives in docs/guides/ instead of user_guide/. The config "
        "specifies user_guide: 'docs/guides'. In the sidebar you should see "
        "user guide pages from this custom directory. Two functions (fetch, "
        "store) should appear on the Reference page."
    ),
    "gdtest_user_guide_hyphen": (
        "Uses user-guide/ (with hyphen) instead of user_guide/ (with "
        "underscore). One guide page: 01-intro.qmd. The sidebar should show "
        "a 'User Guide' section with this page. The key test: both naming "
        "conventions (hyphen and underscore) are supported."
    ),
    "gdtest_readme_rst": (
        "Landing page source is README.rst in reStructuredText. The landing "
        "page should show the converted content — RST headings, code blocks, "
        "and links should render as proper HTML, not raw RST markup. Two "
        "functions (convert, parse) on the Reference page."
    ),
    "gdtest_index_qmd": (
        "Provides an index.qmd with title 'Custom Landing Page'. The landing "
        "page should display this Quarto content as-is — look for the text "
        "'This is a custom landing page written in Quarto markdown.' The "
        "Reference page should show one function (hello)."
    ),
    "gdtest_index_md": (
        "Has both README.md and index.md. The landing page should show the "
        "index.md content ('Custom Index') NOT the README.md content. Look "
        "for the text 'This is index.md and should take priority over "
        "README.md.' One function (greet) on the Reference page."
    ),
    "gdtest_no_readme": (
        "Has no README, no index file — nothing for the landing page. Great "
        "Docs auto-generates a minimal landing page from package metadata. "
        "The landing page should show the package name and an installation "
        "command. One function (noop) on the Reference page."
    ),
    "gdtest_index_wins": (
        "Has both index.qmd and README.md. The landing page should show the "
        "index.qmd content ('Index Wins') NOT the README.md. Look for the "
        "text 'This index.qmd should take priority over README.md.' Tests the "
        "full priority chain: index.qmd > index.md > README.md."
    ),
    "gdtest_full_extras": (
        "Includes every supporting page type. The sidebar/nav should show "
        "links to: License, Citation, Contributing, and Code of Conduct. "
        "There should also be a User Guide section (Getting Started, "
        "Configuration). The Reference page should show Manager (class), "
        "start and stop (functions)."
    ),
    "gdtest_github_contrib": (
        "CONTRIBUTING.md lives in .github/ (not the project root). The "
        "sidebar should still show a Contributing link. Clicking it should "
        "display the contributing content. The Reference page should show "
        "two functions (process, validate). The key test: .github/ fallback "
        "path for contributing."
    ),
    "gdtest_cli_click": (
        "A package with Click CLI commands and cli.enabled=true in config. "
        "The sidebar should show a CLI Reference section alongside the API "
        "Reference. The CLI reference page should document the Click commands. "
        "The API Reference should show Formatter (class) and format_text "
        "(function)."
    ),
    "gdtest_cli_nested": (
        "Click CLI with nested groups: main command → task group (run, list) "
        "and config group (show, set). The CLI Reference should show the "
        "multi-level command hierarchy with subgroups. The API Reference "
        "should show Engine (class) and run_task (function)."
    ),
    "gdtest_explicit_ref": (
        "Reference structure is defined in great-docs.yml with two sections: "
        "'Core' (MyClass with members=false, helper_func) and 'Utilities' "
        "(util_a, util_b). On the Reference page you should see exactly these "
        "two named sections — not auto-generated ones. MyClass should appear "
        "WITHOUT its methods (members: false)."
    ),
    "gdtest_kitchen_sink": (
        "Maximum coverage: src/ layout, 10 exports, Pipeline as a big class "
        "with 6+ methods, user guide (3 pages), all supporting pages (License, "
        "Citation, Contributing, Code of Conduct), author metadata in sidebar, "
        "display_name 'Kitchen Sink'. Every feature should work together "
        "without conflicts."
    ),
    "gdtest_name_mismatch": (
        "Project name is 'gdtest-name-mismatch' but the module is 'gdtest_nm' "
        "(completely different). Config sets module: gdtest_nm. The site title "
        "should use the project name. The Reference page should show exports "
        "from gdtest_nm: Mapper (class) and transform (function). The key "
        "test: config-driven module name override."
    ),
    # ── 43-52: Cross-dimension combos ─────────────────────────────────────
    "gdtest_src_big_class": (
        "src/ layout (A2) with a big class (C3) having 7 methods. Module at "
        "src/gdtest_src_big_class/. Pipeline class with add_step, remove_step, "
        "run, pause, resume, reset, status. On the Reference page you should "
        "see 'Classes' and a separate 'Pipeline Methods' subsection. Key "
        "test: big-class method extraction works from src/ layout."
    ),
    "gdtest_google_big_class": (
        "Google docstrings (D2) with a big class (C3). DataProcessor has 7 "
        "methods all documented in Google style. On the Reference page you "
        "should see the class with a separate methods subsection, and each "
        "method's Args/Returns sections should be parsed correctly from "
        "Google format — not shown as raw text."
    ),
    "gdtest_user_guide_cli": (
        "User guide (F1) combined with CLI documentation. Has user_guide/ "
        "with two pages plus a Click CLI. The top nav should show both "
        "'User Guide' and 'Reference'. On the Reference page you should "
        "see two functions (process, analyze) and a sidebar switcher to "
        "toggle between API and CLI reference."
    ),
    "gdtest_explicit_big_class": (
        "Explicit reference config with a big class. Config defines sections "
        "'Core' with BigEngine (members: false) and 'Helpers' with helper_a, "
        "helper_b. On the Reference page BigEngine should appear WITHOUT its "
        "methods listed (members: false suppresses them), and there should be "
        "NO separate 'BigEngine Methods' subsection."
    ),
    "gdtest_src_no_all": (
        "src/ layout (A2) with no __all__ (B3). Module at "
        "src/gdtest_src_no_all/ defines functions without an __all__ list. "
        "On the Reference page you should see only public names (fetch, "
        "store, Record) — names starting with underscore must be absent. "
        "Key test: griffe fallback within src/ layout."
    ),
    "gdtest_extras_guide": (
        "Full supporting pages (H1-H4) combined with a user guide (F1). "
        "Sidebar should show License, Citation, Contributing, Code of "
        "Conduct links AND a User Guide section with two pages. "
        "Reference page shows two functions (start, stop)."
    ),
    "gdtest_google_seealso": (
        "Google docstrings (D2) with %seealso directives (E3). Four exports "
        "(encode, decode, compress, decompress) with Google-style Args/Returns "
        "plus %seealso cross-references. Each function's rendered docs should "
        "show both the Google parameter tables and a 'See Also' block."
    ),
    "gdtest_setup_cfg_src": (
        "setup.cfg only (A7) with src/ layout. No pyproject.toml — metadata "
        "comes from setup.cfg, but the module lives in src/. On the Reference "
        "page you should see two functions (parse, format). Key test: "
        "setup.cfg metadata detection combined with src/ directory scanning."
    ),
    "gdtest_exclude_cli": (
        "Config-level exclusion (B5) with CLI documentation. Two API exports "
        "are excluded via config, plus a Click CLI. The sidebar should show "
        "CLI Reference. The API Reference should show only the non-excluded "
        "items (execute, report) — hidden_func must be absent."
    ),
    "gdtest_src_explicit_ref": (
        "src/ layout (A2) with explicit reference config. Config defines two "
        "sections: 'Core' (Engine, run) and 'Utils' (format_result). Module "
        "lives in src/. On the Reference page you should see exactly 'Core' "
        "and 'Utils' headings. Key test: explicit ref + src/ layout together."
    ),
    # ── 66-77: New API patterns ───────────────────────────────────────────
    "gdtest_async_funcs": (
        "Module with async def functions: async_fetch, async_process, "
        "async_save. On the Reference page you should see these functions "
        "with 'async' in their signatures. The coroutine return types should "
        "display correctly. Key test: async functions render without errors."
    ),
    "gdtest_generators": (
        "Module with generator functions using yield: count_up, fibonacci, "
        "iter_chunks. On the Reference page the functions should show "
        "Iterator/Generator return types. The yield-based docstrings should "
        "render properly. Key test: generator signatures are handled."
    ),
    "gdtest_overloads": (
        "Module using @overload from typing: process() has three overloads "
        "(str→str, int→int, list→list) plus the implementation. On the "
        "Reference page you should ideally see the overloaded signatures. "
        "At minimum, the function must render without errors."
    ),
    "gdtest_abstract_props": (
        "ABC with abstract methods and @property decorators. Shape class has "
        "abstract area (property) and perimeter (property), plus concrete "
        "describe(). Circle subclass implements them. On the Reference page "
        "you should see both classes with property markers on the abstract "
        "properties."
    ),
    "gdtest_multi_inherit": (
        "Diamond inheritance: Base → Mixin1, Mixin2 → Combined. Each class "
        "adds methods. On the Reference page you should see all four classes. "
        "Combined should show its own methods and potentially inherited ones. "
        "Key test: multiple inheritance doesn't crash the renderer."
    ),
    "gdtest_slots_class": (
        "Class using __slots__ = ('x', 'y', 'label') instead of __dict__. "
        "SlottedPoint class with three slots and four methods. On the "
        "Reference page you should see the class with its methods. The slots "
        "should ideally appear as documented attributes."
    ),
    "gdtest_frozen_dc": (
        "Frozen dataclass: @dataclass(frozen=True) with typed fields. "
        "Coordinate has x (float), y (float), label (str). On the Reference "
        "page you should see the class with its field signatures and defaults. "
        "Key test: frozen=True doesn't break introspection."
    ),
    "gdtest_generics": (
        "Generic classes using TypeVar: Stack[T] with push, pop, peek methods "
        "and a Pair[K, V] container. On the Reference page you should see "
        "the classes with their generic type parameters. Key test: TypeVar "
        "parameterized classes render correctly."
    ),
    "gdtest_context_mgr": (
        "Context manager classes with __enter__/__exit__: ManagedResource and "
        "Timer. On the Reference page the classes should show their dunder "
        "methods and any public methods. Key test: context manager protocols "
        "render cleanly."
    ),
    "gdtest_decorators": (
        "Module of decorator functions: retry, cache, validate_args, log_calls. "
        "Each returns a wrapper function. On the Reference page you should see "
        "these in the 'Functions' section with their signatures showing the "
        "decorator parameters like max_retries, ttl, etc."
    ),
    "gdtest_exceptions": (
        "Custom exception hierarchy: AppError (base), ValidationError, "
        "NotFoundError, PermissionError_, TimeoutError_. On the Reference "
        "page you should see a 'Classes' section with all five exceptions. "
        "Key test: exception classes (inheriting from Exception) render "
        "like normal classes."
    ),
    "gdtest_reexports": (
        "Package with submodules (core.py, utils.py) that re-exports symbols "
        "via __init__.py __all__. On the Reference page you should see the "
        "re-exported names (Engine, run, format_result, parse_input) as if "
        "they belong to the top-level package. Submodule origins should not "
        "be visible."
    ),
    # ── 78-82: Scale & stress ─────────────────────────────────────────────
    "gdtest_many_exports": (
        "Module with 30+ exported functions (func_01 through func_30). On "
        "the Reference page you should see a very long 'Functions' section "
        "listing all 30. The page should not crash or truncate. Key test: "
        "large export count doesn't break rendering or navigation."
    ),
    "gdtest_deep_nesting": (
        "Deeply nested subpackages: gdtest_deep_nesting.level1.level2.level3 "
        "with exports at each level. On the Reference page you should see "
        "the leaf-level exports. Key test: deep package hierarchies are "
        "traversed without errors."
    ),
    "gdtest_long_docs": (
        "Three functions with very long docstrings containing multiple "
        "sections: Parameters, Returns, Raises, Notes, Examples (with code "
        "blocks), Warnings, References. On the Reference page each function "
        "should render all docstring sections fully — nothing truncated."
    ),
    "gdtest_many_guides": (
        "User guide with 10 pages (01-introduction through 10-appendix). "
        "The sidebar should list all 10 pages in order. Scrolling the "
        "sidebar should show every page. Key test: large user guide count "
        "doesn't break sidebar rendering."
    ),
    "gdtest_many_big_classes": (
        "Five big classes each with 6+ methods: Processor, Transformer, "
        "Validator, Formatter, Exporter. On the Reference page you should "
        "see 'Classes' plus FIVE separate method subsections. Key test: "
        "multiple big classes coexist without section name collisions."
    ),
    # ── 83-88: Build systems & layouts ────────────────────────────────────
    "gdtest_flit": (
        "Uses Flit build backend (flit_core.buildapi). Module location "
        "auto-detected by Flit conventions. On the Reference page you should "
        "see two functions (compose, publish). Key test: Flit build-system "
        "metadata is parsed correctly for module discovery."
    ),
    "gdtest_pdm": (
        "Uses PDM build backend (pdm.backend). Module location auto-detected. "
        "On the Reference page you should see two functions (install, remove). "
        "Key test: PDM build-system configuration is recognized."
    ),
    "gdtest_namespace": (
        "Implicit namespace package (no __init__.py in top-level). Module "
        "code lives in gdtest_namespace/sub/module.py. On the Reference page "
        "you should see exports from the sub-module. Key test: namespace "
        "package without __init__.py is handled gracefully."
    ),
    "gdtest_monorepo": (
        "Package lives in packages/mylib/ subdirectory (monorepo pattern). "
        "The pyproject.toml is at the subdir level. On the Reference page "
        "you should see two functions (build, deploy). Key test: package "
        "discovery works when not at repository root."
    ),
    "gdtest_multi_module": (
        "Package with three submodules (models.py, views.py, controllers.py) "
        "re-exported via __init__.py. On the Reference page you should see "
        "all exports merged: Model, View, Controller classes plus create, "
        "render, dispatch functions. Key test: multi-module packages."
    ),
    "gdtest_src_legacy": (
        "src/ layout with legacy setup.py (no pyproject.toml). Module at "
        "src/gdtest_src_legacy/. On the Reference page you should see two "
        "functions (legacy_init, legacy_run). Key test: src/ detection works "
        "even with setup.py-only metadata."
    ),
    # ── 89-95: Edge cases ─────────────────────────────────────────────────
    "gdtest_empty_module": (
        "Module contains only __version__ — no functions, no classes, nothing "
        "to document. The build should succeed. The Reference page should "
        "exist but be empty or show only the module description. Key test: "
        "zero-export packages don't crash the build."
    ),
    "gdtest_all_private": (
        "Module has mostly _private names with only one public function "
        "(public_api). __all__ lists just public_api. On the Reference page "
        "you should see only public_api — none of the _private_* names. "
        "Key test: private-heavy modules filter correctly."
    ),
    "gdtest_duplicate_all": (
        "Module where __all__ accidentally lists 'transform' twice. On the "
        "Reference page transform should appear exactly once, not duplicated. "
        "Build should not crash on the duplicate. Key test: graceful handling "
        "of duplicate __all__ entries."
    ),
    "gdtest_badge_readme": (
        "README.md with shields.io badges, images, and complex Markdown "
        "(tables, footnotes, nested lists). The landing page should render "
        "badges as images, tables as HTML tables, and links should be "
        "clickable. Key test: complex Markdown in README."
    ),
    "gdtest_math_docs": (
        "Docstrings containing LaTeX math notation: inline $x^2$ and block "
        "$$\\\\sum_{i=1}^n x_i$$ equations. On the Reference page the math "
        "should render as formatted equations (or at minimum not break the "
        "page). Key test: math in docstrings."
    ),
    "gdtest_mixed_guide_ext": (
        "User guide with mixed file extensions: intro.qmd, setup.md, and "
        "advanced.qmd. All three should appear in the sidebar. Key test: "
        ".md and .qmd files coexist in user_guide/."
    ),
    "gdtest_unicode_docs": (
        "Docstrings with unicode characters: accented names (René), emoji "
        "(📊), CJK characters (数据), mathematical symbols (∫∑∏). On the "
        "Reference page all characters should render correctly without "
        "encoding errors. Key test: unicode safety."
    ),
    # ── 96-100: Config matrix ─────────────────────────────────────────────
    "gdtest_config_all_on": (
        "Every possible config toggle set to a non-default value: parser, "
        "display_name, source.enabled=true, dark_mode, authors, funding, "
        "user_guide, reference sections. Key test: all config options "
        "together don't conflict."
    ),
    "gdtest_config_display": (
        "Config sets display_name='Pretty Display Name', theme color, authors "
        "with roles, and funding info. The site title should show 'Pretty "
        "Display Name' not the package name. Author info should appear in "
        "the sidebar."
    ),
    "gdtest_config_minimal": (
        "Config explicitly sets source.enabled=false and dark_mode=false. "
        "The site should NOT show source code links and should NOT have a "
        "dark mode toggle. Key test: opt-out config flags are respected."
    ),
    "gdtest_config_parser": (
        "Config overrides parser to 'google' even though docstrings are "
        "written in Google style (matching). On the Reference page, Google "
        "Args/Returns should parse correctly with the explicit parser setting."
    ),
    "gdtest_config_extra_keys": (
        "Config YAML includes unrecognized keys (custom_field, future_option) "
        "alongside valid ones. The build should succeed without errors — "
        "unknown keys should be silently ignored. Key test: forward-"
        "compatible config parsing."
    ),
    # ── v2 packages ──
    # ── 01–25: Config options ─────────────────────────────────────────────
    "gdtest_github_icon": (
        "Tests github_style: 'icon' config (vs. default 'widget'). The GitHub "
        "link in the navbar should render as a simple icon, not the full "
        "star-count widget. Two functions (fetch, store) with NumPy docs."
    ),
    "gdtest_source_branch": (
        "Tests source.branch: 'develop' override. Source links should point "
        "to the 'develop' branch instead of auto-detected main/master. Two "
        "functions (read_data, write_data) with NumPy docs."
    ),
    "gdtest_source_path": (
        "Tests source.path: 'src/mylib' override. Source links should include "
        "the custom path prefix. Module at top level but source links pretend "
        "it's in src/mylib. Two functions (parse, format_output)."
    ),
    "gdtest_source_title": (
        "Tests source.placement: 'title' (vs. default 'usage'). Source code "
        "links should appear near the title/heading of each API entry, not "
        "in the usage section. Two functions (compress, decompress)."
    ),
    "gdtest_source_disabled": (
        "Tests source.enabled: false. No source code links should appear "
        "anywhere in the rendered docs. Two functions (encrypt, decrypt) with "
        "NumPy docstrings."
    ),
    "gdtest_sidebar_disabled": (
        "Tests sidebar_filter.enabled: false. The sidebar search/filter "
        "widget should NOT appear even if there are many items. Five "
        "functions (a through e) to ensure enough items exist."
    ),
    "gdtest_sidebar_min_items": (
        "Tests sidebar_filter.min_items: 3 (low threshold). The sidebar "
        "filter should appear even with just 4 items because the threshold "
        "is set low. Four functions (w, x, y, z)."
    ),
    "gdtest_cli_name": (
        "Tests cli.name: 'mytool' (explicit CLI name). The CLI reference "
        "should show 'mytool' as the command name. Has a Click app with "
        "two commands (run, status)."
    ),
    "gdtest_dynamic_false": (
        "Tests dynamic: false config. Uses static introspection instead of "
        "runtime import. Two simple functions (greet, farewell) to verify "
        "static analysis works."
    ),
    "gdtest_parser_google": (
        "Tests parser: 'google' with all-Google docstrings. Five functions "
        "with Args/Returns/Raises sections. Parser should correctly handle "
        "Google format without falling back to numpy."
    ),
    "gdtest_parser_sphinx": (
        "Tests parser: 'sphinx' with Sphinx :param:/:returns: docstrings. "
        "Three functions and one class. Parser should correctly handle Sphinx "
        "field list format."
    ),
    "gdtest_display_name": (
        "Tests display_name: 'My Pretty Library'. Site title in navbar and "
        "browser tab should show 'My Pretty Library', not the raw package "
        "name. Two functions (init, cleanup)."
    ),
    "gdtest_funding": (
        "Tests funding config with all fields: name, roles, homepage, ror. "
        "The funding info should appear somewhere in the rendered site "
        "(sidebar or footer). Two functions (donate, sponsor)."
    ),
    "gdtest_authors_multi": (
        "Tests authors config with three author entries, each having name, "
        "email, role, and github username. Author info should render in the "
        "sidebar. Two functions (collaborate, review)."
    ),
    "gdtest_no_darkmode": (
        "Tests dark_mode_toggle: false. The dark mode toggle switch should "
        "NOT appear in the navbar. Two functions (light_func, bright_func)."
    ),
    "gdtest_exclude_list": (
        "Tests exclude config list. Module has 5 exports but 2 are excluded "
        "via config. Reference page should show only the 3 non-excluded items."
    ),
    "gdtest_jupyter_kernel": (
        "Tests jupyter: 'python3' explicit kernel config. Doesn't change "
        "behavior for non-notebook builds but exercises the config path. "
        "Two functions (compute, evaluate)."
    ),
    "gdtest_config_sections": (
        "Tests the sections config for custom page groups. Config defines "
        "an 'Examples' section pointing to examples/ dir. Two example pages "
        "should appear in the sidebar under 'Examples'."
    ),
    "gdtest_config_ug_string": (
        "Tests user_guide: 'guides' (string pointing to custom dir). User "
        "guide pages live in guides/ instead of user_guide/. Sidebar should "
        "show them."
    ),
    "gdtest_config_ug_list": (
        "Tests user_guide as explicit list of sections with pages. Config "
        "defines exact ordering: 'Getting Started' (install, quickstart) "
        "then 'Advanced' (customization). Sidebar should show this structure."
    ),
    "gdtest_config_changelog": (
        "Tests changelog config: enabled: true, max_releases: 5. Since "
        "there's no real GitHub repo, the changelog feature should degrade "
        "gracefully without breaking the build."
    ),
    "gdtest_config_reference": (
        "Tests reference config with explicit sections. Config defines two "
        "reference sections: 'Core API' and 'Utilities'. On the reference "
        "page these should appear as named section headings."
    ),
    "gdtest_config_combo_a": (
        "Combination: display_name + authors + funding + github_icon + "
        "source.placement=title. All these config options together should "
        "not conflict. Site title ≠ package name."
    ),
    "gdtest_config_combo_b": (
        "Combination: parser=google + dynamic=false + sidebar_filter.enabled="
        "false + dark_mode_toggle=false + source.enabled=false. All opt-out "
        "flags together."
    ),
    "gdtest_config_combo_c": (
        "Combination: sections (examples + tutorials) + user_guide (list) + "
        "reference (explicit). Full navigation structure defined by config."
    ),
    # ── 26–50: Docstring richness ─────────────────────────────────────────
    "gdtest_rst_versionadded": (
        "Docstrings contain '.. versionadded:: 2.0' RST directive. Post-render "
        "should translate this into a styled callout div with version info. "
        "Two functions with versionadded in their docstrings."
    ),
    "gdtest_rst_deprecated": (
        "Docstrings contain '.. deprecated:: 1.5' with deprecation message. "
        "Post-render should show a deprecation warning callout. Two functions "
        "with deprecated directives."
    ),
    "gdtest_rst_note": (
        "Docstrings contain '.. note::' with body text. Post-render should "
        "translate into a note callout. Three functions with note blocks."
    ),
    "gdtest_rst_warning": (
        "Docstrings contain '.. warning::' directive. Post-render should "
        "translate into a warning callout (yellow/orange). Two functions "
        "with warning blocks."
    ),
    "gdtest_rst_tip": (
        "Docstrings contain '.. tip::' directive. Post-render should "
        "translate into a tip callout. Two functions with helpful tips."
    ),
    "gdtest_rst_caution": (
        "Docstrings contain '.. caution::' directive. Post-render should "
        "translate into a caution callout (orange). Two functions."
    ),
    "gdtest_rst_danger": (
        "Docstrings contain '.. danger::' directive. Post-render should "
        "translate into a danger callout (red). Two functions with hazard "
        "warnings."
    ),
    "gdtest_rst_important": (
        "Docstrings contain '.. important::' directive. Post-render should "
        "translate into an important callout. Two functions."
    ),
    "gdtest_rst_mixed_dirs": (
        "Docstrings mix multiple RST directives: versionadded, deprecated, "
        "note, warning, tip in the same module and sometimes SAME docstring. "
        "All should render as distinct callouts."
    ),
    "gdtest_sphinx_func_role": (
        "Docstrings contain :py:func:`other_func` cross-reference roles. "
        "Post-render should strip the :py:func: prefix and add () to the "
        "linked name. Three functions cross-referencing each other."
    ),
    "gdtest_sphinx_class_role": (
        "Docstrings contain :py:class:`MyClass` cross-reference roles. "
        "Post-render should strip :py:class: prefix, keeping the class name "
        "without parentheses. One class and two functions."
    ),
    "gdtest_sphinx_exc_role": (
        "Docstrings contain :py:exc:`ValueError` cross-reference roles. "
        "Post-render should strip :py:exc: prefix. Functions that raise "
        "named exceptions with Sphinx-style references."
    ),
    "gdtest_sphinx_meth_role": (
        "Docstrings contain :py:meth:`MyClass.method` cross-reference roles. "
        "Post-render should strip :py:meth: prefix and add (). One class "
        "with methods referencing each other."
    ),
    "gdtest_sphinx_mixed_roles": (
        "Docstrings mix :py:func:, :py:class:, :py:exc:, :py:meth:, and "
        ":py:attr: roles in the same module. All should be translated "
        "correctly by post-render."
    ),
    "gdtest_numpy_rich": (
        "Rich NumPy-style docstrings with ALL standard sections: Parameters, "
        "Returns, Raises, Notes, Examples, Warnings, References, See Also. "
        "Every section should render properly."
    ),
    "gdtest_google_rich": (
        "Rich Google-style docstrings with all standard sections: Args, "
        "Returns, Raises, Note, Example, Warning, References, See Also. "
        "All sections should render."
    ),
    "gdtest_sphinx_rich": (
        "Rich Sphinx-style docstrings with :param:, :type:, :returns:, "
        ":rtype:, :raises: field lists, plus prose Notes/Examples blocks. "
        "Everything should parse and render."
    ),
    "gdtest_docstring_examples": (
        "Docstrings with extended Examples sections containing multiple code "
        "blocks, expected output, and prose explanation between blocks. Code "
        "should render as syntax-highlighted blocks."
    ),
    "gdtest_docstring_notes": (
        "Docstrings with detailed Notes sections including multi-paragraph "
        "text, inline code, and references. Notes should render as flowing "
        "prose below the parameter tables."
    ),
    "gdtest_docstring_warnings": (
        "Docstrings with Warnings sections (NumPy style) describing hazards. "
        "The Warnings section should render visually distinct from Notes, "
        "ideally with some form of alert styling."
    ),
    "gdtest_docstring_references": (
        "Docstrings with References sections containing bibliography entries "
        "and links. References should render as a list below the main docs."
    ),
    "gdtest_docstring_seealso": (
        "Docstrings with See Also sections listing related functions, each "
        "with a brief description. Should render as a linked list of related "
        "API entries."
    ),
    "gdtest_docstring_math": (
        "Docstrings containing LaTeX math: inline $x^2 + y^2$ and display "
        "blocks $$\\\\sum_{i=1}^{n} x_i$$. Math should render via KaTeX or "
        "MathJax without breaking the page."
    ),
    "gdtest_docstring_tables": (
        "Docstrings containing RST-style tables (grid tables and simple "
        "tables). Tables should render as HTML tables in the output."
    ),
    "gdtest_docstring_combo": (
        "Stress test: docstrings combining RST directives (versionadded, "
        "note), Sphinx roles (:py:func:), rich sections (Notes, Examples, "
        "See Also), math, and tables all in one module."
    ),
    # ── 51–65: User guide variations ──────────────────────────────────────
    "gdtest_ug_auto": (
        "Basic auto-discovered user guide: user_guide/ dir with 3 unnumbered "
        ".qmd files. Sidebar should discover and list them alphabetically."
    ),
    "gdtest_ug_numbered": (
        "Numbered user guide files: 01-intro.qmd, 02-install.qmd, "
        "03-usage.qmd, 04-advanced.qmd. Should appear in numeric order in "
        "the sidebar."
    ),
    "gdtest_ug_sections_fm": (
        "User guide with frontmatter guide-section metadata grouping pages "
        "into 'Getting Started' and 'Advanced Topics'. Sidebar should show "
        "section headings."
    ),
    "gdtest_ug_subdirs": (
        "User guide with subdirectories: user_guide/basics/ and "
        "user_guide/advanced/. Pages should be grouped by subdirectory in "
        "the sidebar."
    ),
    "gdtest_ug_custom_dir": (
        "User guide lives in docs/ instead of user_guide/. Config sets "
        "user_guide: 'docs'. Sidebar should find pages from the custom dir."
    ),
    "gdtest_ug_deep_nest": (
        "Deeply nested user guide: user_guide/section1/subsection1/ with "
        "pages at multiple levels. Tests multi-level directory traversal."
    ),
    "gdtest_ug_mixed_ext": (
        "User guide with mixed file extensions: intro.qmd, setup.md, "
        "advanced.qmd. Both .qmd and .md should appear in sidebar."
    ),
    "gdtest_ug_many_pages": (
        "User guide with 12 pages to test scrolling/navigation with many entries in the sidebar."
    ),
    "gdtest_ug_explicit_order": (
        "User guide ordering defined explicitly in great-docs.yml config. "
        "Pages appear in config-specified order, not alphabetical."
    ),
    "gdtest_ug_single_page": (
        "Minimal user guide with just one page. Sidebar should show a "
        "User Guide section with a single entry."
    ),
    "gdtest_ug_no_frontmatter": (
        "User guide .qmd files with NO YAML frontmatter. Title should be "
        "inferred from the first heading or filename."
    ),
    "gdtest_ug_with_code": (
        "User guide pages containing Python code blocks, both fenced and "
        "executable. Code should be syntax-highlighted."
    ),
    "gdtest_ug_with_images": (
        "User guide page referencing images from an assets directory. Images "
        "should be copied and displayed correctly."
    ),
    "gdtest_ug_hyphen_dir": (
        "User guide in user-guide/ (hyphenated). Both user_guide/ and "
        "user-guide/ naming conventions should work."
    ),
    "gdtest_ug_combo": (
        "Combination: numbered files + frontmatter sections + subdirs + "
        "mixed extensions. Complex user guide structure."
    ),
    # ── 66–75: Custom sections ────────────────────────────────────────────
    "gdtest_sec_examples": (
        "Custom 'Examples' section via config sections. examples/ dir with "
        "3 example pages. Should appear as a separate nav section."
    ),
    "gdtest_sec_tutorials": (
        "Custom 'Tutorials' section. tutorials/ dir with step-by-step "
        "pages. Should appear as a separate nav section."
    ),
    "gdtest_sec_recipes": (
        "Custom 'Recipes' section. recipes/ dir with short how-to pages. "
        "Should appear as a separate nav section."
    ),
    "gdtest_sec_blog": (
        "Blog section using Quarto's native listing directive. blog/ dir "
        "with posts in subdirectories. Uses type: blog for auto-listing."
    ),
    "gdtest_sec_faq": (
        "Custom 'FAQ' section. faq/ dir with question-based pages. "
        "Should appear as a separate nav section."
    ),
    "gdtest_sec_multi": (
        "Multiple custom sections: Examples + Tutorials + Recipes. Three "
        "different section dirs, all configured via sections list. All "
        "should appear as separate nav sections."
    ),
    "gdtest_sec_navbar_after": (
        "Custom section with navbar_after specified. Section should appear "
        "after a specific navbar item. Tests ordering control."
    ),
    "gdtest_sec_with_ug": (
        "Custom section (Examples) combined with auto-discovered user guide. "
        "Both should appear as separate nav sections without conflict."
    ),
    "gdtest_sec_with_ref": (
        "Custom section (Tutorials) combined with explicit reference config. "
        "Both custom nav sections and custom reference order should work."
    ),
    "gdtest_sec_deep": (
        "Custom section with nested subdirectories: tutorials/beginner/ and "
        "tutorials/advanced/. Deep structure within a custom section."
    ),
    # ── 76–85: Reference config ───────────────────────────────────────────
    "gdtest_ref_explicit": (
        "Reference config with explicit contents list defining which objects "
        "appear on the reference page and in what order."
    ),
    "gdtest_ref_members_false": (
        "Reference config with members: false on a class. The class should "
        "appear but its methods should NOT be listed separately."
    ),
    "gdtest_ref_mixed": (
        "Mix of explicit reference items and auto-discovered ones. Config "
        "defines some sections explicitly, others are auto-generated."
    ),
    "gdtest_ref_reorder": (
        "Reference config that reorders the default sections. Functions "
        "appear before Classes, reversing the normal order."
    ),
    "gdtest_ref_sectioned": (
        "Reference with 4 named sections: Constructors, Transformers, "
        "Validators, Utilities. Each lists specific exports."
    ),
    "gdtest_ref_single_section": (
        "Reference with a single named section containing all exports. "
        "Everything under one heading."
    ),
    "gdtest_ref_module_expand": (
        "Reference config that references a submodule name. The builder "
        "should expand the module into its individual members."
    ),
    "gdtest_ref_big_class": (
        "Reference config featuring a big class (>5 methods). Config sets "
        "members: true explicitly. Big class methods should get their own "
        "subsection."
    ),
    "gdtest_ref_multi_big": (
        "Reference with multiple big classes in the same config. Each should "
        "get its own methods subsection without name collisions."
    ),
    "gdtest_ref_title": (
        "Reference config with title: 'API Docs' instead of default. The "
        "reference page heading should use this custom title."
    ),
    # ── 86–95: Site theming & display ─────────────────────────────────────
    "gdtest_theme_cosmo": (
        "Tests site.theme: 'cosmo'. The site should render with the Cosmo "
        "Bootstrap theme. All pages should apply the theme consistently."
    ),
    "gdtest_theme_lumen": ("Tests site.theme: 'lumen'. Site renders with the Lumen theme."),
    "gdtest_theme_cerulean": (
        "Tests site.theme: 'cerulean'. Site renders with the Cerulean theme."
    ),
    "gdtest_toc_disabled": (
        "Tests site.toc: false. No table of contents should appear on any "
        "page. The layout should adjust to fill the space."
    ),
    "gdtest_toc_depth": (
        "Tests site.toc-depth: 3 (deeper than default 2). The table of "
        "contents should show h3 headings as well as h2."
    ),
    "gdtest_toc_title": (
        "Tests site.toc-title: 'Contents' (vs. default 'On this page'). "
        "The TOC heading should show 'Contents'."
    ),
    "gdtest_site_combo": (
        "Combination: cosmo theme + toc-depth:3 + custom toc-title + "
        "display_name. All site settings together."
    ),
    "gdtest_display_badges": (
        "Package with complex README containing badges, version shields, "
        "and download counts. Landing page should render these correctly."
    ),
    "gdtest_display_authors": (
        "Authors displayed with all metadata: name, email, role, github, "
        "and a URL avatar. Sidebar should show author cards."
    ),
    "gdtest_display_funding": (
        "Funding org with name, roles, homepage, and ROR identifier. "
        "Footer or sidebar should show the funding acknowledgment."
    ),
    # ── 96–100: Cross-feature stress ──────────────────────────────────────
    "gdtest_stress_all_config": (
        "ALL config options set to non-default values at once. Every toggle "
        "flipped. Build should succeed without conflicts."
    ),
    "gdtest_stress_all_docstr": (
        "Module with every docstring feature: RST directives, Sphinx roles, "
        "all NumPy sections, math, tables, examples, code blocks. "
        "Post-render should handle everything."
    ),
    "gdtest_stress_all_ug": (
        "Maximum user guide complexity: 8 pages, frontmatter sections, "
        "subdirs, mixed extensions, numbered, with code blocks. Everything "
        "together."
    ),
    "gdtest_stress_all_sections": (
        "Five custom sections (Examples, Tutorials, Recipes, FAQ, Blog) "
        "combined with user guide and explicit reference. Maximum navigation "
        "complexity."
    ),
    "gdtest_stress_everything": (
        "The ultimate stress test: ALL config options + all docstring features "
        "+ complex user guide + multiple custom sections + explicit reference "
        "+ non-default theme + authors + funding. If this builds, everything "
        "works."
    ),
}


# ── Spec access ──────────────────────────────────────────────────────────────

_spec_cache: dict[str, dict[str, Any]] = {}


def get_spec(name: str) -> dict[str, Any]:
    """
    Load and return the spec dict for the given package name.

    Parameters
    ----------
    name
        One of the names in :data:`ALL_PACKAGES`.

    Returns
    -------
    dict
        The full spec dict (keys: name, dimensions, files, expected, …).
    """
    if name in _spec_cache:
        return _spec_cache[name]

    if name not in ALL_PACKAGES:
        raise ValueError(f"Unknown synthetic package: {name!r}")

    # Import from specs sub-package
    mod = importlib.import_module(f".specs.{name}", package=__package__)
    spec: dict[str, Any] = mod.SPEC  # type: ignore[attr-defined]

    # Validate minimal required keys
    assert spec.get("name") == name, f"Spec 'name' must be {name!r}, got {spec.get('name')!r}"
    assert "files" in spec, f"Spec for {name!r} must have a 'files' dict"

    _spec_cache[name] = spec
    return spec


def get_specs_by_dimension(dim_code: str) -> list[dict[str, Any]]:
    """
    Return all specs whose ``dimensions`` list contains *dim_code*.

    Parameters
    ----------
    dim_code
        A dimension code like ``"A2"`` or ``"C5"``.

    Returns
    -------
    list[dict]
        Matched specs (loaded lazily).
    """
    results: list[dict[str, Any]] = []
    for name in ALL_PACKAGES:
        spec = get_spec(name)
        if dim_code in spec.get("dimensions", []):
            results.append(spec)
    return results
