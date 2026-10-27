"""
Build cases and package generation for the characterisation harness

A build case specifies a Gauntlet package, the commands to run and, for a variant, how the
package or its configuration differs from the spec. The default tier contains 33 packages
selected to exercise build features, plus their variants. The full catalogue includes every
Gauntlet package supported by the build interpreter, plus the variants of those packages.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from tests.harness.sides import run_checked

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
    "gdtest_config_combo_e",
)

# The overlay covers sitemap, page-date and social-card generation absent from the specs.
SHOW_DATES_OVERLAY: Mapping[str, Any] = {
    "show_dates": True,
    "seo": {"canonical": {"base_url": "https://example.com/kitchen-sink/"}},
    "social_cards": {"enabled": True},
}

# A public function that the second release of `gdtest_kitchen_sink` adds.
KITCHEN_SINK_ADDITION = '''

def summarise(values: list[float]) -> float:
    """
    Add up the values.

    Parameters
    ----------
    values
        The values to add.

    Returns
    -------
    float
        Their sum.
    """
    return sum(values)


__all__ += ["summarise"]
'''

# Arguments after `great-docs` for each command a case can run.
COMMANDS: Mapping[str, tuple[str, ...]] = {
    "init": ("init", "--force"),
    "build": ("build",),
    "freeze": ("freeze",),
    "watch": ("build", "--watch"),
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

# Fixed identities and an empty Git configuration give every copy of a release repository the
# same commit hashes; each release's commit is dated one day after the previous one.
GIT_ENVIRONMENT: Mapping[str, str] = {
    "GIT_AUTHOR_NAME": "Great Docs harness",
    "GIT_AUTHOR_EMAIL": "harness@example.com",
    "GIT_COMMITTER_NAME": "Great Docs harness",
    "GIT_COMMITTER_EMAIL": "harness@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


@dataclass(frozen=True)
class Release:
    """
    A commit of a package's Git repository and the tag that names it

    Attributes
    ----------
    tag :
        Tag on the commit.
    appended :
        Text appended to files before the commit, keyed by path relative to the package root.
    """

    tag: str
    appended: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class BuildCase:
    """
    A Gauntlet package and the commands the harness runs on it

    Attributes
    ----------
    package :
        Gauntlet spec name, which is also the package directory name.
    variant :
        Name of the variant, or `None` for the package as its spec describes it.
    overlay :
        Mapping merged into the spec's configuration.
    commands :
        Keys of `COMMANDS`, run in order. `init` runs only when the package ships no
        configuration, as in the Gauntlet.
    arguments :
        Arguments added after a command's own, keyed by command.
    root_layout :
        Whether the package keeps its documentation sources, configuration included, at its
        root instead of in `docs/`.
    releases :
        Commits of a Git repository made in the package, oldest first; empty for a package
        outside any repository.
    render_pages :
        Whether the stub `quarto render` writes a placeholder page for each source page.
    watch_edit :
        Source file, relative to the package root, that a `watch` command edits once its
        first build has started the preview.
    expects_reference :
        Whether every Quarto project the commands leave must hold `reference/index.qmd`.
    """

    package: str
    variant: str | None = None
    overlay: Mapping[str, Any] = field(default_factory=dict[str, Any])
    commands: tuple[str, ...] = ("init", "build")
    arguments: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    root_layout: bool = False
    releases: tuple[Release, ...] = ()
    render_pages: bool = False
    watch_edit: str | None = None
    expects_reference: bool = False

    @property
    def id(self) -> str:
        """Identifier of the case in recordings and reports"""
        return f"{self.package}+{self.variant}" if self.variant else self.package


# Cases beyond one per package; each follows its package in a catalogue.
VARIANTS: tuple[BuildCase, ...] = (
    BuildCase("gdtest_kitchen_sink", "show_dates", SHOW_DATES_OVERLAY),
    # Freeze one page after a build. Freeze prepares the build directory again, so its file
    # changes show where freeze preparation departs from the build's. The package has a CLI
    # reference and a user guide, and no changelog, which freeze is meant to skip.
    BuildCase(
        "gdtest_user_guide_cli",
        "freeze",
        commands=("init", "build", "freeze"),
        arguments={"freeze": ("docs/user_guide/01-getting-started.qmd",)},
    ),
    # Build two versions from a repository with two tags. Version 0.2 is the checkout, at tag
    # `v0.2`; version 0.1 takes its API from tag `v0.1`, which lacks one function. Quarto
    # must leave pages in `_site/`, or the versioned build stops before assembling the site.
    BuildCase(
        "gdtest_kitchen_sink",
        "versions",
        {"versions": [{"tag": "0.2"}, {"tag": "0.1", "git_ref": "v0.1"}]},
        releases=(
            Release("v0.1"),
            Release("v0.2", {"src/gdtest_kitchen_sink/__init__.py": KITCHEN_SINK_ADDITION}),
        ),
        render_pages=True,
    ),
    # Start watch mode, edit a user-guide page once the preview runs, then interrupt it.
    BuildCase(
        "gdtest_page_tags",
        "watch",
        commands=("init", "watch"),
        watch_edit="docs/user_guide/02-configuration.qmd",
    ),
    # Keep `great-docs.yml`, without `module:`, and the user guide at the package root, so the
    # build writes to `great-docs/`.
    BuildCase("gdtest_page_status", "root_layout", root_layout=True),
)


def tier_cases(test_packages: Path) -> list[BuildCase]:
    """
    List the default cases, including the variants of tier packages

    Parameters
    ----------
    test_packages :
        The `test-packages` directory that holds the catalogue.

    Returns
    -------
    :
        The 33 tier packages, each followed by its variants.
    """
    return with_variants(TIER, test_packages)


def full_cases(test_packages: Path, python: tuple[int, ...]) -> list[BuildCase]:
    """
    List every Gauntlet package the child interpreter supports, plus the variants

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
        One case per package in catalogue order, each followed by its variants.
    """
    catalog = _synthetic(test_packages, "catalog")
    names: list[str] = []
    for name in catalog.ALL_PACKAGES:
        if not (test_packages / "synthetic" / "specs" / f"{name}.py").exists():
            continue
        minimum = catalog.get_spec(name).get("min_python")
        if minimum is None or python >= tuple(minimum):
            names.append(name)
    return with_variants(names, test_packages)


def with_variants(packages: Iterable[str], test_packages: Path) -> list[BuildCase]:
    """
    Make one case per package, adding each package's variants after it

    Parameters
    ----------
    packages :
        Gauntlet spec names.
    test_packages :
        The `test-packages` directory that holds the catalogue.

    Returns
    -------
    :
        The cases in the given order, with the reference expectation of each spec.
    """
    catalog = _synthetic(test_packages, "catalog")
    cases: list[BuildCase] = []
    for name in packages:
        # The rule of `test_reference_index_exists` in `tests/test_gdg_rendered.py`: a spec
        # that lists its exports expects an API reference.
        expected = catalog.get_spec(name).get("expected", {})
        expects = bool(expected.get("export_names"))
        for case in (BuildCase(name), *(v for v in VARIANTS if v.package == name)):
            cases.append(dataclasses.replace(case, expects_reference=expects))
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
        The package directory, a Git repository when the case has releases.
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
    if case.root_layout:
        docs = package / "docs"
        for source in sorted(docs.iterdir()):
            if (package / source.name).exists():
                raise ValueError(f"{case.id}: {source.name} exists in docs/ and at the root")
            _ = source.rename(package / source.name)
        docs.rmdir()
    if case.releases:
        make_repository(package, case.releases)
    pin_mtimes(package)
    return package


def make_repository(package: Path, releases: Sequence[Release]) -> None:
    """
    Commit and tag each release of a package in a new Git repository

    Every repository made from the same package and releases has the same commit hashes.

    Parameters
    ----------
    package :
        Package directory, which becomes the repository's work tree on branch `main`.
    releases :
        Releases, oldest first; the work tree ends at the last.

    Raises
    ------
    HarnessError
        If a Git command fails.
    """
    for day, release in enumerate(releases):
        for path, text in release.appended.items():
            with (package / path).open("a", encoding="utf-8") as file:
                _ = file.write(text)
        date = f"@{PINNED_MTIME + day * 86400} +0000"
        env = {**os.environ, **GIT_ENVIRONMENT, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        if day == 0:
            _ = run_checked(["git", "init", "--quiet", "--initial-branch", "main"], package, env)
        for argv in (
            ["git", "add", "--all"],
            ["git", "commit", "--quiet", "--message", f"Release {release.tag}"],
            ["git", "tag", release.tag],
        ):
            _ = run_checked(argv, package, env)


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
