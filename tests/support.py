"""
Shared configuration and build setup for `GreatDocs` tests

`write_config` writes and loads `great-docs.yml`. `mock_config` provides a `Config` double
with empty defaults. `write_pyproject` declares a project's name. `make_project` reads a
project's facts as a build does, and `make_run` creates build state for testing build methods
directly.
`stubbed_build` stubs Quarto and build steps while preserving the build's control flow.
`StubRemote` supplies GitHub and PyPI data without network requests. `homepage_hero` and
`homepage_margin` build the homepage hero and sidebar from the project's configuration and metadata.
`find_user_guide_dir` and `discover_user_guide` find a project's user guide and print its warnings
as a build does. `write_authored_pages` creates a project with each kind of authored page
the build publishes.
"""

from __future__ import annotations

import types
import typing
from collections.abc import Callable, Collection, Generator, Iterable, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, NonCallableMagicMock, patch

from yaml12 import format_yaml

from great_docs import Config, GreatDocs
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._content import user_guide
from great_docs._project import Project
from great_docs._website.homepage import hero, margin
from great_docs._website.project_pages import community

if TYPE_CHECKING:
    from great_docs._content.user_guide import UserGuide
    from great_docs._github import GithubRepo

# Keep these methods in the order `GreatDocs.build()` first calls them. Stub the methods
# called by the step actions so the step table and its actions still run.
# Update this list when a build step moves out of `GreatDocs`.
_BUILD_METHODS: tuple[str, ...] = (
    "_griffe_search_paths",
    "_prepare_build_directory",
    "_resolve_importable_name",
    "_detect_module_name",
    "_process_user_guide",
    "_process_sections",
    "_process_custom_pages",
    "_copy_assets",
    "_update_quarto_config",
    "_prerender_term_player",
    "_default_description",
    "_structured_data",
    "_auto_save_snapshot",
    "_print_layout_notice",
)

# Configuration and build annotations use names imported only while type
# checking. Supply them so the annotations can be resolved at runtime.
_TYPE_CHECKING_NAMES: dict[str, Any] = {
    "Any": Any,
    "BuildLog": BuildLog,
    "ConfigDict": dict[str, Any],
}

# Public attributes that `Config.__init__` sets and the class does not declare.
_CONFIG_INSTANCE_ATTRIBUTES = ("project_root", "config_path", "cache_dir")


def write_config(root: Path, settings: str | Mapping[str, object] = "") -> Config:
    """
    Write and load a project's `great-docs.yml`

    Parameters
    ----------
    root
        The project directory.
    settings
        YAML text to write unchanged, or a mapping to serialise as YAML.

    Returns
    -------
    :
        The configuration loaded from `root`.
    """
    text = settings if isinstance(settings, str) else format_yaml(dict(settings))
    (root / "great-docs.yml").write_text(text, encoding="utf-8")
    return Config(root)


def mock_config(**values: object) -> NonCallableMagicMock:
    """
    Create a `Config` double with empty defaults

    Each property reads as the empty value of its declared type, and each public method returns
    the empty value of its declared return type. The empty value is `None` when the type admits
    `None`, and otherwise the type's falsy value, such as `False`, `""`, `[]` or `{}`. Reading or
    setting a name that `Config` lacks raises `AttributeError`, so a test fails at its setup when
    a setting it names is renamed.

    Parameters
    ----------
    **values
        Values for properties or attributes, by name.

    Returns
    -------
    :
        A configuration double with the supplied values and empty defaults.
    """
    config = NonCallableMagicMock(spec_set=[*dir(Config), *_CONFIG_INSTANCE_ATTRIBUTES])
    for name, member in vars(Config).items():
        if isinstance(member, property) and member.fget is not None:
            setattr(config, name, _empty(_return_type(member.fget)))
        elif callable(member) and not name.startswith("_"):
            getattr(config, name).return_value = _empty(_return_type(member))
    for name, value in values.items():
        setattr(config, name, value)
    return config


def write_pyproject(root: Path, name: str | None) -> Path:
    """
    Declare a project's distribution name in its `pyproject.toml`

    Parameters
    ----------
    root
        The project directory.
    name
        The name to declare, or `None` to leave the packaging files unchanged. Without a
        declared name or a sole package directory, the project has no detected name.

    Returns
    -------
    :
        `root`, for use as a project double's package root.
    """
    if name is not None:
        (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n', encoding="utf-8")
    return root


def make_project(docs: GreatDocs) -> Project:
    """
    Read a project's facts from its files, as a build does when it starts

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The project's name, metadata and GitHub repository as its files describe them now.
    """
    return Project.make(docs._config, docs.layout)


def make_run(docs: GreatDocs, **values: Any) -> Run:
    """
    Create build state from the project's current files, with optional field overrides

    Watch mode is off unless overridden.

    Parameters
    ----------
    docs
        The project.
    **values
        Overrides for `Run` fields, by name.

    Returns
    -------
    :
        The build state with the supplied values.
    """
    return replace(Run.make(docs._config, docs.layout, watch=False), **values)


@dataclass(frozen=True)
class BuildStubs:
    """
    Stubs for build steps and the Quarto render process

    Attributes
    ----------
    steps
        Method stubs keyed by name. Set `side_effect` to an exception to make a step fail.
    render
        The `quarto render` process, which defaults to exit status 0 and no output. Set
        `returncode` and `stderr` to simulate a render failure.
    """

    steps: dict[str, MagicMock]
    render: MagicMock


@contextmanager
def stubbed_build(
    docs: GreatDocs,
    run: Iterable[str] = (),
    *,
    api_reference: bool = False,
    **returns: object,
) -> Generator[BuildStubs]:
    """
    Stub Quarto and the methods `GreatDocs.build()` calls on an instance

    Within the block, `docs.build()` keeps its control flow: the Quarto installation check
    passes, the render environment is empty and `quarto render` succeeds silently. Build steps
    are stubbed except those listed in `run`. Stubs enforce the real methods' call signatures
    and return empty values of their declared return types unless overridden in `returns`.

    Parameters
    ----------
    docs
        The instance to stub.
    run
        Names of methods to run for real. Also include any build steps these methods need to
        call for real; other steps remain stubbed.
    api_reference
        Whether the stubbed preparation of the build directory leaves the site with an API
        reference. By default it configures none, as for a project without one.
    **returns
        Return values for stubbed methods, by method name.

    Yields
    ------
    :
        The stubs to configure before the build and inspect afterwards.

    Raises
    ------
    ValueError
        If `run` or `returns` names a method that `build()` does not call, both name the same
        method, or `api_reference` is true while build directory preparation runs for real.
    AttributeError
        If a method in the build-step list no longer exists on `GreatDocs`.
    """
    real = set(run)
    unknown = sorted((real | set(returns)) - set(_BUILD_METHODS))
    if unknown:
        raise ValueError(f"build() does not call {unknown}")
    both = sorted(real & set(returns))
    if both:
        raise ValueError(f"a method that runs cannot have a stubbed return value: {both}")
    if api_reference and "_prepare_build_directory" in real:
        raise ValueError(
            "the real build directory preparation decides whether there is an API reference"
        )
    missing = [name for name in _BUILD_METHODS if not hasattr(GreatDocs, name)]
    if missing:
        raise AttributeError(f"GreatDocs has no {missing}; update the method list in {__name__}")

    with ExitStack() as stack:
        stack.enter_context(
            patch("great_docs._website.ai_agents.skills.SkillsWriter.write", autospec=True)
        )
        stack.enter_context(patch("great_docs._build.quarto.ensure_installed", autospec=True))
        stack.enter_context(
            patch("great_docs._build.quarto.environment", autospec=True, return_value={})
        )
        render = stack.enter_context(patch("subprocess.Popen", autospec=True)).return_value
        render.stdout = iter(())
        render.stderr = iter(())
        render.returncode = 0

        steps: dict[str, MagicMock] = {}
        for name in _BUILD_METHODS:
            if name in real:
                continue
            value = (
                returns[name] if name in returns else _empty(_return_type(getattr(GreatDocs, name)))
            )
            steps[name] = stack.enter_context(
                patch.object(docs, name, autospec=True, return_value=value)
            )
        if not api_reference and "_prepare_build_directory" in steps:
            steps["_prepare_build_directory"].side_effect = _configure_no_api_reference
        yield BuildStubs(steps=steps, render=render)


def _configure_no_api_reference(run: Run) -> None:
    """
    Record a build directory prepared without an API reference

    Parameters
    ----------
    run
        The current build.
    """
    run.has_api_reference = False


def _return_type(function: Callable[..., object]) -> object:
    """
    Resolve the declared return type of a function

    Parameters
    ----------
    function
        An annotated function or method.

    Returns
    -------
    :
        The evaluated return annotation.
    """
    return typing.get_type_hints(function, localns=_TYPE_CHECKING_NAMES)["return"]


def _empty(annotation: object) -> object:
    """
    Create the default empty value for a type annotation

    Parameters
    ----------
    annotation
        An evaluated type annotation.

    Returns
    -------
    :
        `None` for a type that allows it, a tuple of empty values for a fixed-length tuple, or
        the falsy value constructed by calling the type with no arguments.

    Raises
    ------
    TypeError
        If calling the type with no arguments does not produce a falsy value.
    """
    members = (
        typing.get_args(annotation)
        if typing.get_origin(annotation) in (typing.Union, types.UnionType)
        else (annotation,)
    )
    if type(None) in members:
        return None
    first = members[0]
    origin = typing.get_origin(first) or first
    if origin is tuple:
        return tuple(_empty(member) for member in typing.get_args(first))
    value = origin() if isinstance(origin, type) else None
    if value is None or value:
        raise TypeError(f"{annotation!r} has no empty value")
    return value


@dataclass
class StubRemote:
    """
    Preset GitHub and PyPI data for a `GreatDocs` instance

    Assign an instance to `docs._remote` to prevent network requests in a test.

    Attributes
    ----------
    stats
        The same star and fork counts for every repository.
    releases
        The same releases for every repository, newest first.
    release_dates
        PyPI release dates by package name.
    calls
        The name of each method called, in order.
    """

    stats: dict[str, int] = field(default_factory=dict)
    releases: list[dict[str, Any]] = field(default_factory=list)
    release_dates: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def github_stats(self, repo: GithubRepo) -> dict[str, int]:
        """
        Return `stats` for any repository

        Parameters
        ----------
        repo
            The repository.

        Returns
        -------
        :
            `stats`.
        """
        self.calls.append("github_stats")
        return self.stats

    def github_releases(self, repo: GithubRepo, max_releases: int) -> list[dict[str, Any]]:
        """
        Return the first `max_releases` entries of `releases`

        Parameters
        ----------
        repo
            The repository.
        max_releases
            The maximum number of releases to return.

        Returns
        -------
        :
            The newest releases.
        """
        self.calls.append("github_releases")
        return self.releases[:max_releases]

    def pypi_release_dates(self, package_names: Collection[str]) -> dict[str, str]:
        """
        Return known release dates for the named packages

        Parameters
        ----------
        package_names
            The PyPI names of the packages.

        Returns
        -------
        :
            The entries in `release_dates` for the named packages.
        """
        self.calls.append("pypi_release_dates")
        return {name: date for name, date in self.release_dates.items() if name in package_names}


def homepage_hero(docs: GreatDocs, readme: str | None = None) -> tuple[str, str | None]:
    """
    Build a project's homepage hero from its configuration and metadata

    Parameters
    ----------
    docs
        The project.
    readme
        The homepage Markdown, or `None` for a page that is not a README.

    Returns
    -------
    :
        The hero HTML, or `""` when the homepage has none, and the README without its badges,
        or `None` when the hero leaves it unchanged.
    """
    found = hero.find(docs._config, docs.layout.source_dir, readme)
    if found is None:
        return "", None
    project = make_project(docs)
    html = hero.render(
        found,
        docs._config,
        docs.layout,
        docs.build_dir,
        metadata=project.manifest,
        package_name=project.name,
        pages=docs._page_map(discover_user_guide(docs)),
    )
    return html, found.body if html else None


def homepage_margin(docs: GreatDocs) -> str:
    """
    Write a project's community pages and render its homepage sidebar, as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The sidebar's Markdown.
    """
    package_root = docs.layout.package_root
    project = make_project(docs)
    return margin.render(
        docs._config,
        docs.build_dir,
        package_root=package_root,
        metadata=project.manifest,
        package_name=project.name,
        community_pages=community.write_pages(
            docs._config, package_root, docs.build_dir, docs._page_authors
        ),
    )


def _print_warning(message: str) -> None:
    """
    Print a warning as a build step's detail line

    Parameters
    ----------
    message
        The warning's text.

    Returns
    -------
    :
    """
    print(f"   ⚠️  {message}")


def find_user_guide_dir(docs: GreatDocs) -> Path | None:
    """
    Find a project's user guide directory, printing warnings as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The directory, or `None` when the project has none.
    """
    return user_guide.find_dir(docs._config, docs.layout, report=_print_warning)


def discover_user_guide(docs: GreatDocs) -> UserGuide | None:
    """
    Discover a project's user guide, printing warnings as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        The guide, or `None` when the project has no guide pages.
    """
    return user_guide.discover(docs._config, docs.layout, report=_print_warning)


AUTHORED_PAGES = [
    "README.md",
    "guides/intro.qmd",
    "tutorials/first.md",
    "pages/notes.md",
]
"""Published authored pages in expected discovery order"""


def write_authored_pages(root: Path) -> None:
    """
    Write a project with a `src/` package and every kind of authored page

    `README.md` supplies the homepage. The configured guide, section and custom page
    directory each contain a page with a URL. The guide include file, unpublished `recipes/`
    directory and generated build page also contain URLs, so checks must exclude those
    sources. The package's `__init__.py` contains one URL for source and docstring checks.

    Parameters
    ----------
    root
        The project directory.

    Returns
    -------
    :
    """
    files = {
        "pyproject.toml": '[project]\nname = "demo"\n',
        "great-docs.yml": (
            "user_guide: guides\n"
            "sections:\n  - title: Tutorials\n    dir: tutorials\n"
            "custom_pages: pages\n"
        ),
        "src/demo/__init__.py": '"""See https://example.com/module"""\n',
        "guides/_include.qmd": "See https://example.com/include\n",
        "recipes/recipe.qmd": "See https://example.com/recipe\n",
        "great-docs/generated.qmd": "See https://example.com/generated\n",
    }
    files.update({page: f"See https://example.com/{Path(page).stem}\n" for page in AUTHORED_PAGES})
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
