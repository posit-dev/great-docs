"""
Documentation builds from a Git repository in an isolated environment

Each build clones the repository into a temporary directory, installs great-docs and the
repository's package into a temporary virtual environment, builds the site with that
environment's great-docs, and copies the site out.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import venv
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from yaml12 import read_yaml

from .. import _manifest
from .._layout import Layout, LayoutError
from .._manifest import ManifestError
from .._subprocess import TEXT_MODE_KWARGS
from .._utils import record_site_ownership, validate_site_dir
from .._yaml import YamlMapping, YamlValue

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["build", "history_needed", "install_extras"]

# Optional-dependency groups likely to hold what a documentation build needs
_DOCS_EXTRAS = ("dev", "docs", "doc", "all")


def build(
    repo_url: str,
    *,
    branch: str | None = None,
    output_dir: str | None = None,
    config_path: str | None = None,
    refresh: bool = True,
    version_tags: list[str] | None = None,
    latest_only: bool = False,
    shallow: bool = False,
    report: Callable[[str], None],
) -> Path:
    """
    Build a Git repository's documentation site

    The build clones the repository, installs great-docs and the repository's package into a
    temporary virtual environment, runs that environment's `great-docs build`, and copies
    the site out. The temporary clone and environment are removed afterwards.

    Unless `shallow` is true, the clone is deepened as far as the selected configuration
    needs: the full history for versioned docs or page dates, tags for source links.

    Parameters
    ----------
    repo_url
        Git URL of the repository to clone (HTTPS or SSH).
    branch
        Branch or tag to check out. If `None`, use the repository's default branch.
    output_dir
        Directory to copy the built site into. If `None`, use the checkout's deployment path
        relative to the current working directory. An existing directory must be empty or
        hold only a site an earlier build copied there, which the new site replaces.
    config_path
        Configuration path relative to the checkout.
    refresh
        Whether to re-discover package exports before building.
    version_tags
        Version tags to build, instead of all of them.
    latest_only
        Whether to build only the latest version.
    shallow
        Whether to keep the shallow clone without fetching history. Versioned docs, page dates
        and tag-based source links then do not work.
    report
        A callback that receives each progress line for the user.

    Returns
    -------
    :
        The absolute path of the copied site.

    Raises
    ------
    LayoutError
        If `config_path` is absolute or resolves outside the checkout.
    ValueError
        If the output path exists and is neither an empty directory nor a site an earlier
        build copied there.
    RuntimeError
        If cloning, an installation or the build fails, or the build leaves no site.
    """
    if config_path is not None and Path(config_path).is_absolute():
        raise LayoutError("Remote configuration must be a relative path inside the checkout")

    with tempfile.TemporaryDirectory(
        prefix="great-docs-remote-", ignore_cleanup_errors=True
    ) as temporary:
        checkout = Path(temporary) / "repo"
        layout = _clone(
            repo_url,
            checkout,
            branch=branch,
            config_path=config_path,
            shallow=shallow,
            report=report,
        )
        output_path = (
            Path(output_dir).resolve()
            if output_dir
            else Path.cwd() / layout.site_dir.relative_to(checkout.resolve())
        )
        _check_replaceable(output_path)
        scripts = _install(checkout, Path(temporary) / "venv", report=report)

        report("🔨 Building documentation...")
        command = [str(scripts / _executable("great-docs")), "build"]
        command += ["--project-path", str(checkout)]
        if config_path is not None:
            command += ["--config", str(layout.config_path)]
        if not refresh:
            command.append("--no-refresh")
        if version_tags:
            command += ["--versions", ",".join(version_tags)]
        if latest_only:
            command.append("--latest-only")
        # The build inherits this environment, including `GITHUB_TOKEN` and `GH_TOKEN`
        environment = {
            **os.environ,
            "VIRTUAL_ENV": str(scripts.parent),
            "PATH": str(scripts) + os.pathsep + os.environ.get("PATH", ""),
        }
        result = subprocess.run(command, env=environment, cwd=str(checkout))
        if result.returncode != 0:
            raise RuntimeError(f"great-docs build failed (exit {result.returncode})")

        site_dir = layout.site_dir
        if not site_dir.exists():
            raise RuntimeError(f"Build completed but _site/ directory not found at {site_dir}")
        report(f"📂 Copying built site to {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # The directory may have changed during the build
        _check_replaceable(output_path)
        if output_path.exists():
            shutil.rmtree(output_path)
        _ = shutil.copytree(site_dir, output_path)
        record_site_ownership(output_path)
        report(f"✅ Site built successfully: {output_path}")
    return output_path


def install_extras(project_dir: Path) -> str:
    """
    Choose the optional-dependency groups to install for a documentation build

    Parameters
    ----------
    project_dir
        The project root, which holds `pyproject.toml`.

    Returns
    -------
    :
        The groups among `dev`, `docs`, `doc` and `all` that `pyproject.toml` defines, joined
        by commas, such as `"dev,docs"`. An empty string when none are defined or a packaging
        file cannot be read or parsed.
    """
    try:
        groups = _manifest.read(project_dir)["optional_dependencies"]
    except ManifestError:
        return ""
    return ",".join(group for group in _DOCS_EXTRAS if group in groups)


def history_needed(
    checkout: Path, *, config_path: Path | None = None
) -> Literal["full", "tags", "none"]:
    """
    Determine the Git history a checkout's documentation build needs

    Parameters
    ----------
    checkout
        The repository root.
    config_path
        The selected configuration file in the checkout. If `None`, use the configuration the
        checkout's layout finds.

    Returns
    -------
    :
        `"full"` when the configuration lists `versions` or turns on `show_dates`: versioned
        builds check out tags, and page dates read `git log`. `"none"` when it sets
        `source.branch`, or when the configuration file is missing, unreadable or malformed.
        `"tags"` otherwise, so that source links can point at the tag of the checked-out
        commit.
    """
    path = Layout.make(checkout, config_path).config_path
    try:
        value: YamlValue = read_yaml(path)
    except (OSError, ValueError):
        return "none"
    settings = YamlMapping(value) if isinstance(value, dict) else YamlMapping()

    # This read bypasses `Config`, which moves the legacy `site.show_dates` to the top level
    show_dates = settings.get("show_dates")
    if show_dates is None:
        show_dates = settings.mapping("site").get("show_dates")
    if settings.get("versions") or show_dates:
        return "full"
    if settings.mapping("source").get("branch"):
        return "none"
    return "tags"


def _check_replaceable(path: Path) -> None:
    """
    Refuse an output path whose contents a build did not copy there

    Parameters
    ----------
    path
        The output path.

    Raises
    ------
    ValueError
        If `path` exists and is neither an empty directory nor a site whose ownership
        manifest lists all of its contents.
    """
    if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):
        return
    validate_site_dir(path)


def _clone(
    repo_url: str,
    checkout: Path,
    *,
    branch: str | None,
    config_path: str | None,
    shallow: bool,
    report: Callable[[str], None],
) -> Layout:
    """
    Clone a repository with the Git history its documentation build needs

    Parameters
    ----------
    repo_url
        Git URL of the repository to clone.
    checkout
        The directory to clone into.
    branch
        Branch or tag to check out, or `None` for the default branch.
    config_path
        Configuration path relative to the checkout, or `None` for the one the layout finds.
    shallow
        Whether to keep the shallow clone without fetching history.
    report
        A callback that receives each progress line for the user.

    Returns
    -------
    :
        The checkout's layout under the selected configuration.

    Raises
    ------
    LayoutError
        If `config_path` resolves outside the checkout.
    RuntimeError
        If cloning fails.
    """
    report(f"📦 Cloning {repo_url}...")
    branch_option = ["--branch", branch] if branch else []
    result = _run(["git", "clone", "--depth=1", *branch_option, repo_url, str(checkout)])
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed (exit {result.returncode}):\n{result.stderr.strip()}")

    selected = (checkout / config_path).resolve() if config_path else None
    if selected is not None and not selected.is_relative_to(checkout.resolve()):
        raise LayoutError("Remote configuration must remain inside the checkout")
    layout = Layout.make(checkout, selected)

    # Fetch failures leave the shallow history, which builds with fewer features
    if not shallow:
        needed = history_needed(checkout, config_path=layout.config_path)
        if needed == "full":
            report("   Fetching full history (versioned docs / page dates)...")
            _ = _run(["git", "fetch", "--unshallow"], cwd=checkout)
            _ = _run(["git", "fetch", "--tags"], cwd=checkout)
        elif needed == "tags":
            report("   Fetching tags for source link detection...")
            _ = _run(["git", "fetch", "--tags"], cwd=checkout)
    report("   Cloned to temporary directory")
    return layout


def _install(checkout: Path, environment: Path, *, report: Callable[[str], None]) -> Path:
    """
    Create a virtual environment with great-docs and the checkout's package

    Install great-docs from the running source tree during development, or pin the PyPI
    installation to the running version. Install the checkout's package in editable mode with
    its documentation extras, retrying without extras if that installation fails.

    Parameters
    ----------
    checkout
        The repository root.
    environment
        The directory for the virtual environment.
    report
        A callback that receives each progress line for the user.

    Returns
    -------
    :
        The environment's scripts directory.

    Raises
    ------
    RuntimeError
        If great-docs or the package fails to install.
    """
    report("🐍 Creating temporary virtual environment...")
    venv.create(str(environment), with_pip=True, clear=True)
    scripts = environment / ("Scripts" if sys.platform == "win32" else "bin")
    pip = str(scripts / _executable("pip"))

    report("📥 Installing great-docs into temporary environment...")
    source_tree = _source_tree()
    requirement = (
        str(source_tree) if source_tree else f"great-docs=={metadata.version('great-docs')}"
    )
    result = _run([pip, "install", requirement])
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install {requirement}:\n{result.stderr.strip()}")

    report("📥 Installing target package...")
    extras = install_extras(checkout)
    result = _run([pip, "install", "-e", f"{checkout}[{extras}]" if extras else str(checkout)])
    if result.returncode != 0:
        result = _run([pip, "install", "-e", str(checkout)])
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install target package:\n{result.stderr.strip()}")
    return scripts


def _source_tree() -> Path | None:
    """
    Locate the source tree of the running great-docs installation

    Returns
    -------
    :
        The source root if its package metadata names the project `great-docs`, or
        `None` if the name is missing or different, or the metadata cannot be read or parsed.
    """
    root = Path(__file__).resolve().parents[2]
    try:
        name = _manifest.read(root)["name"]
    except ManifestError:
        return None
    return root if name == "great-docs" else None


def _executable(name: str) -> str:
    """
    Return a virtual environment's script name for the platform

    Parameters
    ----------
    name
        The script's name without an extension.

    Returns
    -------
    :
        The file name, with `.exe` on Windows.
    """
    return f"{name}.exe" if sys.platform == "win32" else name


def _run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """
    Run a command and capture its output as text

    Parameters
    ----------
    command
        The command and its arguments.
    cwd
        The working directory, or `None` for the current one.

    Returns
    -------
    :
        The finished process.
    """
    return subprocess.run(command, cwd=cwd, capture_output=True, **TEXT_MODE_KWARGS)
