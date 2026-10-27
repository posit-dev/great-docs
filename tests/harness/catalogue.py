"""
Build cases and package generation for the characterisation harness

A build case specifies a Gauntlet package, an optional configuration overlay and the
commands to run. The default tier contains 33 packages selected to exercise build features,
plus a `show_dates` overlay. The full catalogue includes every Gauntlet package supported by
the build interpreter.
"""

from __future__ import annotations

import copy
import importlib
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

TIER: tuple[str, ...] = (
    "gdtest_minimal",
    "gdtest_kitchen_sink",
    "gdtest_big_class",
    "gdtest_explicit_ref",
    "gdtest_ref_include_inherited",
    "gdtest_inline_threshold",
    "gdtest_stress_everything_q",
    "gdtest_stress_all_sections",
    "gdtest_homepage_ug_subdirs",
    "gdtest_custom_missing_dir_combo",
    "gdtest_cli_nested",
    "gdtest_cli_typer",
    "gdtest_user_guide_cli",
    "gdtest_mcp",
    "gdtest_page_tags",
    "gdtest_page_status",
    "gdtest_config_changelog",
    "gdtest_skill_combo",
    "gdtest_i18n_arabic",
    "gdtest_navbar_color",
    "gdtest_announce_dict",
    "gdtest_nav_icons",
    "gdtest_bibliography_csl",
    "gdtest_readme_rst",
    "gdtest_no_readme",
    "gdtest_namespace_src",
    "gdtest_extras_guide",
    "gdtest_hero_basic",
    "gdtest_config_combo_f",
    "gdtest_config_combo_d",
    "gdtest_go_cli",
    "gdtest_termshow",
    # A scalar `changelog:` value makes the build exit 1; kept so the harness records that failure.
    "gdtest_config_combo_e",
)

# The overlay covers sitemap, page-date and social-card generation absent from the specs.
SHOW_DATES_PACKAGE = "gdtest_kitchen_sink"
SHOW_DATES_OVERLAY: Mapping[str, Any] = {
    "show_dates": True,
    "seo": {"canonical": {"base_url": "https://example.com/kitchen-sink/"}},
    "social_cards": {"enabled": True},
}

# Arguments after `great-docs` for each command a case can run.
COMMANDS: Mapping[str, tuple[str, ...]] = {
    "init": ("init", "--force"),
    "build": ("build",),
}

# Where `great-docs` looks for an existing configuration, relative to the package root.
CONFIG_LOCATIONS = (
    "great-docs.yml",
    "docs/great-docs.yml",
    "docs-website/great-docs.yml",
    "doc/great-docs.yml",
    "website/great-docs.yml",
)

# Modification time of every generated file: 2025-01-01T00:00:00Z.
PINNED_MTIME = 1735689600


@dataclass(frozen=True)
class BuildCase:
    """
    A Gauntlet package and the commands the harness runs on it

    Attributes
    ----------
    package :
        Gauntlet spec name, which is also the package directory name.
    overlay_name :
        Name of the configuration overlay, or `None` for the spec's own configuration.
    overlay :
        Mapping merged into the spec's configuration.
    commands :
        Keys of `COMMANDS`, run in order. `init` runs only when the package ships no
        configuration, as in the Gauntlet.
    """

    package: str
    overlay_name: str | None = None
    overlay: Mapping[str, Any] = field(default_factory=dict[str, Any])
    commands: tuple[str, ...] = ("init", "build")

    @property
    def id(self) -> str:
        """Identifier of the case in recordings and reports"""
        return f"{self.package}+{self.overlay_name}" if self.overlay_name else self.package


def tier_cases() -> list[BuildCase]:
    """
    List the default cases, including the page-date overlay

    Returns
    -------
    :
        The 33 tier packages and the `show_dates` overlay on `gdtest_kitchen_sink`.
    """
    return with_overlay(TIER)


def full_cases(test_packages: Path, python: tuple[int, ...]) -> list[BuildCase]:
    """
    List every Gauntlet package the child interpreter supports, plus the overlay

    Parameters
    ----------
    test_packages :
        The `test-packages` directory that holds the catalogue.
    python :
        Version of the interpreter that runs the builds, compared with each spec's
        `min_python`.

    Returns
    -------
    :
        One case per package in catalogue order, with the overlay after its package.
    """
    catalog = _synthetic(test_packages, "catalog")
    names: list[str] = []
    for name in catalog.ALL_PACKAGES:
        if not (test_packages / "synthetic" / "specs" / f"{name}.py").exists():
            continue
        minimum = catalog.get_spec(name).get("min_python")
        if minimum is None or python >= tuple(minimum):
            names.append(name)
    return with_overlay(names)


def with_overlay(packages: Iterable[str]) -> list[BuildCase]:
    """
    Make one case per package, adding the `show_dates` overlay after its package

    Parameters
    ----------
    packages :
        Gauntlet spec names.

    Returns
    -------
    :
        The cases in the given order.
    """
    cases: list[BuildCase] = []
    for name in packages:
        cases.append(BuildCase(name))
        if name == SHOW_DATES_PACKAGE:
            cases.append(BuildCase(name, "show_dates", SHOW_DATES_OVERLAY))
    return cases


def select(cases: Sequence[BuildCase], only: Sequence[str]) -> list[BuildCase]:
    """
    Keep the cases named on the command line

    Parameters
    ----------
    cases :
        Cases of the chosen catalogue.
    only :
        Case identifiers or package names; empty keeps every case.

    Returns
    -------
    :
        The matching cases in catalogue order.

    Raises
    ------
    ValueError
        If a name matches no case.
    """
    if not only:
        return list(cases)
    unknown = [n for n in only if not any(n in (c.id, c.package) for c in cases)]
    if unknown:
        raise ValueError(f"No build case named {', '.join(unknown)}")
    return [c for c in cases if c.id in only or c.package in only]


def generate(case: BuildCase, test_packages: Path, parent: Path) -> Path:
    """
    Write a case's package into a directory

    A `pyproject.toml` marks the package root, as in the Gauntlet. Fixed modification times
    keep page dates consistent between runs.

    Parameters
    ----------
    case :
        The case to generate.
    test_packages :
        The `test-packages` directory that holds the catalogue.
    parent :
        Directory that receives the package directory.

    Returns
    -------
    :
        The package directory.
    """
    catalog = _synthetic(test_packages, "catalog")
    generator = _synthetic(test_packages, "generator")
    spec: dict[str, Any] = copy.deepcopy(catalog.get_spec(case.package))
    if case.overlay:
        spec["config"] = deep_merge(spec.get("config") or {}, case.overlay)
    package = Path(generator.generate_package(spec, parent))
    pyproject = package / "pyproject.toml"
    if not pyproject.exists():
        name = spec.get("expected", {}).get("detected_name", case.package)
        _ = pyproject.write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n', encoding="utf-8"
        )
    pin_mtimes(package)
    return package


def has_config(package: Path) -> bool:
    """
    Report whether a package ships a Great Docs configuration

    Parameters
    ----------
    package :
        Package directory.

    Returns
    -------
    :
        Whether a configuration exists where `great-docs` looks for one.
    """
    return any((package / location).is_file() for location in CONFIG_LOCATIONS)


def pin_mtimes(root: Path) -> None:
    """
    Set the modification time of every path under a directory to `PINNED_MTIME`

    Parameters
    ----------
    root :
        Directory whose contents and own modification time are fixed.
    """
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            os.utime(Path(dirpath) / name, (PINNED_MTIME, PINNED_MTIME), follow_symlinks=False)
        os.utime(dirpath, (PINNED_MTIME, PINNED_MTIME))


def deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """
    Merge an overlay into a configuration mapping

    Parameters
    ----------
    base :
        The configuration.
    overlay :
        Values that take precedence over `base`; nested mappings merge key by key.

    Returns
    -------
    :
        A new mapping.
    """
    merged = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(value, Mapping) and isinstance(current, Mapping):
            merged[key] = deep_merge(
                cast(Mapping[str, Any], current), cast(Mapping[str, Any], value)
            )
        else:
            merged[key] = copy.deepcopy(overlay[key])
    return merged


def _synthetic(test_packages: Path, module: str) -> Any:
    """
    Import a module of the Gauntlet's `synthetic` package

    Parameters
    ----------
    test_packages :
        The `test-packages` directory.
    module :
        Module name inside `synthetic`.

    Returns
    -------
    :
        The imported module.
    """
    if str(test_packages) not in sys.path:
        sys.path.insert(0, str(test_packages))
    return importlib.import_module(f"synthetic.{module}")
