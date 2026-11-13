"""
Shared configuration and build setup for `GreatDocs` tests

`write_config` writes and loads `great-docs.yml`. `mock_config` provides a `Config` double
with empty defaults. `write_pyproject` declares a project's name. `make_project` reads a
project's facts as a build does, `make_exports` prepares to find its exports, and `make_run`
creates build state for testing build methods directly. `prepare_build_directory`,
`update_quarto_config`, `add_api_block` and `write_homepage` provide the project inputs for
individual build operations. `user_guide_step`, `sections_step`, `custom_pages_step` and
`freeze_cache_step` run individual steps with the build's arguments, and
`apply_contributions` adds what a step records to `_quarto.yml`.
`stubbed_build` stubs Quarto and build steps while preserving the build's control flow.
`StubRemote` supplies repository and PyPI data without network requests. `homepage_hero` and
`homepage_margin` build the homepage hero and sidebar from the project's configuration and metadata.
`find_user_guide_dir` and `discover_user_guide` find a project's user guide and print its warnings
as a build does. `write_authored_pages` creates a project with each kind of authored page
the build publishes.
"""

from __future__ import annotations

import importlib
import inspect
import io
import types
import typing
from collections.abc import Callable, Collection, Generator, Iterable, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import DEFAULT, MagicMock, NonCallableMagicMock, patch

from yaml12 import format_yaml

from great_docs import Config, GreatDocs
from great_docs._build import content, pipeline, prepare, reference, site
from great_docs._build.log import BuildLog
from great_docs._build.pipeline import Run
from great_docs._build.steps import Outcome, Skipped, print_warning
from great_docs._content import user_guide
from great_docs._project import Project
from great_docs._reference.exports import Exports
from great_docs._website import quarto_yml
from great_docs._website.ai_agents import llms_txt
from great_docs._website.homepage import hero, margin
from great_docs._website.project_pages import community

if TYPE_CHECKING:
    from great_docs._content.user_guide import UserGuide
    from great_docs._project.repository import Repository
    from great_docs._project.remote import ReleaseData
    from great_docs._project.layout import Layout

# Stub calls within step actions to preserve the step table and build control flow.
# List functions in first-call order by dotted path relative to `great_docs._build`.
# Update paths when steps move.
_BUILD_CALLS: tuple[str, ...] = (
    "prepare.build_directory",
    "content.user_guide",
    "content.sections",
    "content.custom_pages",
    "content.assets",
    "site.update_quarto_config",
    "passes.terminal_recordings",
    "site.default_description",
    "site.structured_data",
    "finish.print_layout_notice",
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
    the empty value of its declared return type. A method returning `Config` returns this
    double so configuration copies retain its settings. The empty value is `None` when the type admits
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
            result = _return_type(member)
            getattr(config, name).return_value = config if result is Config else _empty(result)
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


def make_exports(docs: GreatDocs) -> Exports:
    """
    Prepare export discovery from the project's current files, as a build does

    Parameters
    ----------
    docs
        The project.

    Returns
    -------
    :
        An export discovery object with no packages loaded or exports discovered.
    """
    return Exports(docs._config, make_project(docs))


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


def prepare_build_directory(docs: GreatDocs, run: Run) -> Outcome:
    """
    Prepare a fresh build directory using the project's build inputs

    Write the Quarto configuration that preparation holds to `_quarto.yml`, as the end of
    a build's preparation does.

    Parameters
    ----------
    docs
        The project supplying configuration, directories and remote data.
    run
        The current build, which supplies the page authors and receives the configuration.

    Returns
    -------
    :
        The step's outcome.
    """
    outcome = prepare.build_directory(
        run,
        docs._config,
        docs.layout,
        remote=docs._remote,
        page_authors=run.page_authors,
        refresh=True,
    )
    quarto_yml.write(docs.layout.build_dir, run.quarto_config)
    return outcome


def update_quarto_config(docs: GreatDocs, run: Run) -> None:
    """
    Merge site settings into the project's existing Quarto configuration

    Parameters
    ----------
    docs
        The project, whose `_quarto.yml` holds the configuration to update.
    run
        The current build.

    Returns
    -------
    :
    """
    with _quarto_config_in(docs.layout.build_dir, run):
        site.update_quarto_config(run, docs._config, docs.layout, remote=docs._remote)


def apply_contributions(docs: GreatDocs, run: Run) -> None:
    """
    Apply the build's recorded Quarto contributions in step order

    With recorded contributions, create `_quarto.yml` if missing and supply missing
    `website` defaults before applying them. Leave the file unchanged when the build has
    no contributions.

    Parameters
    ----------
    docs
        The project.
    run
        The build that recorded the contributions.

    Returns
    -------
    :
    """
    if not run.contributions:
        return
    quarto_config = _seeded_quarto_config(docs.layout.build_dir)
    for contribution in run.contributions:
        quarto_yml.apply(quarto_config, contribution, docs._config)
    quarto_yml.write(docs.layout.build_dir, quarto_config)


def _seeded_quarto_config(build_dir: Path) -> dict[str, Any]:
    """
    Read a test's Quarto configuration and supply missing navigation defaults

    Use an empty configuration if `_quarto.yml` is missing. Supply an empty `sidebar`
    list if absent and a `navbar` mapping with an empty `left` list if `navbar` is
    absent, so contributions can extend a partial test configuration.

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        The parsed configuration with navigation defaults. A missing file starts with
        an empty configuration.
    """
    file_exists = quarto_yml.path(build_dir).exists()
    quarto_config = quarto_yml.read(build_dir) if file_exists else {}
    website = quarto_config.setdefault("website", {})
    website.setdefault("sidebar", [])
    website.setdefault("navbar", {"left": []})
    return quarto_config


def add_api_block(docs: GreatDocs, run: Run) -> None:
    """
    Configure the project's API reference using the supplied build state

    Parameters
    ----------
    docs
        The project, whose `_quarto.yml` receives the API reference configuration.
    run
        The current build.

    Returns
    -------
    :
    """
    with _quarto_config_in(docs.layout.build_dir, run):
        reference.add_api_block(run, docs._config, refresh=True)


@contextmanager
def _quarto_config_in(build_dir: Path, run: Run) -> Generator[None]:
    """
    Hold a test's `_quarto.yml` in the build state while a step runs, then write it back

    The step sees the file's configuration, or an empty one when the file is missing. The
    file is created only when the step adds configuration, and left unchanged when the step
    raises an exception.

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    run
        The build state that holds the configuration.

    Yields
    ------
    :
    """
    file_exists = quarto_yml.path(build_dir).exists()
    run.quarto_config = quarto_yml.read(build_dir) if file_exists else {}
    yield
    if file_exists or run.quarto_config:
        quarto_yml.write(build_dir, run.quarto_config)


def write_homepage(docs: GreatDocs, *, has_api_reference: bool = True) -> None:
    """
    Write the project's homepage and project pages with a freshly discovered user guide

    Parameters
    ----------
    docs
        The project.
    has_api_reference
        Whether homepage links should include an API reference.

    Returns
    -------
    :
    """
    run = make_run(docs, user_guide=discover_user_guide(docs), has_api_reference=has_api_reference)
    content.homepage(
        run, docs._config, docs.layout, page_authors=run.page_authors, remote=docs._remote
    )


def user_guide_step(docs: GreatDocs, guide: UserGuide | None = None) -> Outcome:
    """
    Run the build's user guide step on its own

    Parameters
    ----------
    docs
        The project.
    guide
        The discovered user guide, or `None` when it has no pages.

    Returns
    -------
    :
        The step's outcome.
    """
    return _preparation_step(docs, "Process User Guide", make_run(docs, user_guide=guide))


def sections_step(docs: GreatDocs, guide: UserGuide | None = None) -> Outcome:
    """
    Run the build's sections step on its own

    Parameters
    ----------
    docs
        The project.
    guide
        The discovered user guide, or `None` when it has no pages.

    Returns
    -------
    :
        The step's outcome.
    """
    return _preparation_step(docs, "Process custom sections", make_run(docs, user_guide=guide))


def custom_pages_step(docs: GreatDocs, guide: UserGuide | None = None) -> Outcome:
    """
    Run the build's custom pages step on its own

    Parameters
    ----------
    docs
        The project.
    guide
        The discovered user guide, or `None` when it has no pages.

    Returns
    -------
    :
        The step's outcome.
    """
    return _preparation_step(docs, "Process custom pages", make_run(docs, user_guide=guide))


def freeze_cache_step(docs: GreatDocs, *, watch: bool = False) -> Outcome:
    """
    Run the build's freeze cache step on its own

    Parameters
    ----------
    docs
        The project.
    watch
        Whether the build watches for changes.

    Returns
    -------
    :
        The step's outcome.
    """
    return _preparation_step(docs, "Prepare freeze cache", make_run(docs, watch=watch))


def _preparation_step(docs: GreatDocs, title: str, run: Run) -> Outcome:
    """
    Run one preparation step with the build's arguments and apply its contributions

    The step sees the test's `_quarto.yml`, with missing `website` defaults supplied.

    Parameters
    ----------
    docs
        The project.
    title
        The step's title in the build log.
    run
        The current build.

    Returns
    -------
    :
        The step's outcome.
    """
    run.quarto_config = _seeded_quarto_config(docs.layout.build_dir)
    steps = pipeline.preparation_steps(
        run, docs._config, docs.layout, BuildLog(stream=io.StringIO()), remote=docs._remote
    )
    outcome = next(step for step in steps if step.title == title).run()
    apply_contributions(docs, run)
    return outcome


@dataclass(frozen=True)
class BuildStubs:
    """
    Stubs for build steps and the Quarto render process

    Attributes
    ----------
    steps
        Function stubs keyed by path relative to `great_docs._build`. Set `side_effect`
        to an exception to make a step fail.
    render
        The `quarto render` process, which defaults to exit status 0 and no output. Set
        `returncode` and `stderr` to simulate a render failure.
    """

    steps: dict[str, MagicMock]
    render: MagicMock


@contextmanager
def stubbed_build(
    run: Iterable[str] = (),
    *,
    api_reference: bool = False,
    **returns: object,
) -> Generator[BuildStubs]:
    """
    Stub Quarto and selected build calls while preserving the build's control flow

    Within the block, the Quarto installation check passes and the render environment is
    empty. The stubbed preparation starts from the test's `_quarto.yml`, the stubbed
    configuration step applies recorded contributions to it, and the build writes it back. Stubbed processes, including `quarto render`, exit successfully without
    output.
    Build calls are stubbed except those listed in `run`. Stubs enforce the real call
    signatures and return empty values of their declared return types unless `returns`
    overrides them. Calls returning `Outcome` report a skip, which counts as a completed
    step in the build log.

    Identify a call by its function path relative to `great_docs._build`, such as
    `content.sections`.

    Parameters
    ----------
    run
        Names of calls to run for real, including any other calls they need to run for real.
        Leave all other calls stubbed.
    api_reference
        Whether the stubbed preparation of the build directory leaves the site with an API
        reference, configured by the `api-reference` block of the test's `_quarto.yml`. By
        default it configures none, as for a project without one.
    **returns
        Return values for stubbed build steps, by name.

    Yields
    ------
    :
        The stubs to configure before the build and inspect afterwards.

    Raises
    ------
    ValueError
        If `run` or `returns` names a build step that `build()` does not call, both name the
        same step, or `api_reference` is true while build directory preparation runs for real.
    AttributeError
        If a build step in the list no longer exists.
    """
    real = set(run)
    unknown = sorted((real | set(returns)) - set(_BUILD_CALLS))
    if unknown:
        raise ValueError(f"build() does not call {unknown}")
    both = sorted(real & set(returns))
    if both:
        raise ValueError(f"a call that runs cannot have a stubbed return value: {both}")
    if api_reference and "prepare.build_directory" in real:
        raise ValueError(
            "the real build directory preparation decides whether there is an API reference"
        )
    missing = [name for name in _BUILD_CALLS if not hasattr(*_step_owner(name))]
    if missing:
        raise AttributeError(f"no build step {missing}; update the step list in {__name__}")

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
        # Waiting for a process, including the Git lookup, must yield a successful exit.
        render.__enter__.return_value = render
        render.args = []
        render.communicate.return_value = ("", "")
        render.poll.return_value = 0

        steps: dict[str, MagicMock] = {}
        for name in _BUILD_CALLS:
            if name in real:
                continue
            owner, attribute = _step_owner(name)
            value = returns[name] if name in returns else _stub_value(getattr(owner, attribute))
            steps[name] = stack.enter_context(
                patch.object(owner, attribute, autospec=True, return_value=value)
            )
        if "prepare.build_directory" in steps:
            steps["prepare.build_directory"].side_effect = (
                _record_written_api_reference if api_reference else _configure_no_api_reference
            )
        if "site.update_quarto_config" in steps:
            steps["site.update_quarto_config"].side_effect = _apply_recorded_contributions
        yield BuildStubs(steps=steps, render=render)


def _stub_value(step: Callable[..., object]) -> object:
    """
    Choose what a stubbed build step returns by default

    Parameters
    ----------
    step
        The real build step.

    Returns
    -------
    :
        A skipped outcome for an `Outcome` return type, or the empty value of any other
        declared return type.
    """
    annotation = _return_type(step)
    return Skipped("stubbed") if annotation == Outcome else _empty(annotation)


def _step_owner(name: str) -> tuple[types.ModuleType, str]:
    """
    Find the module that defines a build step

    Parameters
    ----------
    name
        The step function's path below `great_docs._build`.

    Returns
    -------
    :
        The module and the function's name within it.
    """
    module, _, function = name.rpartition(".")
    return importlib.import_module(f"great_docs._build.{module}"), function


def _configure_no_api_reference(
    run: Run, config: Config, layout: Layout, *args: object, **kwargs: object
) -> object:
    """
    Prepare a stubbed build without an API reference and keep the stub's return value

    The build's Quarto configuration is the test's `_quarto.yml`, or empty when the test
    writes none.

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    *args
        Additional positional arguments accepted by the preparation stub and ignored here.
    **kwargs
        Keyword arguments accepted by the preparation stub and ignored here.

    Returns
    -------
    :
        `DEFAULT`, so the stub returns its configured value.
    """
    if quarto_yml.path(layout.build_dir).exists():
        run.quarto_config = quarto_yml.read(layout.build_dir)
    run.has_api_reference = False
    return DEFAULT


def _record_written_api_reference(
    run: Run, config: Config, layout: Layout, *args: object, **kwargs: object
) -> object:
    """
    Prepare a stubbed build with the test's API reference and keep the stub's return value

    The build's Quarto configuration is the test's `_quarto.yml`, and its `api-reference`
    block is the recorded one.

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    *args
        Additional positional arguments accepted by the preparation stub and ignored here.
    **kwargs
        Keyword arguments accepted by the preparation stub and ignored here.

    Returns
    -------
    :
        `DEFAULT`, so the stub returns its configured value.

    Raises
    ------
    KeyError
        If the test's `_quarto.yml` has no `api-reference` block.
    """
    run.quarto_config = quarto_yml.read(layout.build_dir)
    run.api_block = run.quarto_config["api-reference"]
    return DEFAULT


def _apply_recorded_contributions(
    run: Run, config: Config, layout: Layout, *args: object, **kwargs: object
) -> object:
    """
    Add a stubbed build's recorded contributions to its Quarto configuration

    The real configuration step also merges site settings; this stub applies only the
    contributions.

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    *args
        Additional positional arguments accepted by the configuration stub and ignored here.
    **kwargs
        Keyword arguments accepted by the configuration stub and ignored here.

    Returns
    -------
    :
        `DEFAULT`, so the stub returns its configured value.
    """
    for contribution in run.contributions:
        quarto_yml.apply(run.quarto_config, contribution, config)
    return DEFAULT


def _return_type(function: Callable[..., object]) -> object:
    """
    Resolve the declared return type of a function

    Evaluate only the return annotation. Parameter annotations may refer to types imported
    only during type checking.

    Parameters
    ----------
    function
        An annotated function or method.

    Returns
    -------
    :
        The evaluated return annotation.
    """
    annotation = inspect.get_annotations(function)["return"]
    if isinstance(annotation, str):
        annotation = eval(annotation, vars(inspect.getmodule(function)), _TYPE_CHECKING_NAMES)
    # Annotation evaluation gives `None`, but the caller needs its type to choose an empty value.
    return type(None) if annotation is None else annotation


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
    Preset repository and PyPI data for a `GreatDocs` instance

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
    releases: list[ReleaseData] = field(default_factory=list)
    release_dates: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def repository_stats(self, repo: Repository) -> dict[str, int]:
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
        self.calls.append("repository_stats")
        return self.stats

    def repository_releases(self, repo: Repository, max_releases: int) -> list[ReleaseData]:
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
        self.calls.append("repository_releases")
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
        metadata=project.manifest,
        package_name=project.name,
        pages=content.page_map(docs._config, docs.layout, discover_user_guide(docs)),
    )
    return html, found.body if html else None


def homepage_margin(docs: GreatDocs, *, api_block: dict[str, Any] | None = None) -> str:
    """
    Write a project's community pages and render its homepage sidebar, as a build does

    Parameters
    ----------
    docs
        The project.
    api_block
        The API reference configuration, which decides whether the sidebar links to
        `llms.txt`, or `None` for a site without one.

    Returns
    -------
    :
        The sidebar's Markdown.
    """
    project = make_project(docs)
    return margin.render(
        docs._config,
        docs.layout,
        metadata=project.manifest,
        repository=project.repository,
        package_name=project.name,
        community_pages=community.write_pages(
            docs._config, docs.layout, make_run(docs).page_authors
        ),
        has_llms_txt=llms_txt.is_planned(api_block),
    )


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
    return user_guide.find_dir(docs._config, docs.layout, report=print_warning)


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
    return user_guide.discover(docs._config, docs.layout, report=print_warning)


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
