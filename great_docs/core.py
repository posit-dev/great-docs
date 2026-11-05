import json
import os
import re
import shutil
import subprocess
import sys
from functools import cache, partial
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import _manifest, _marimo
from ._build import freeze, outputs, quarto, serve, timings
from ._build.facts import Facts, exact_tag, source_links
from ._build.pipeline import Run
from ._build.quarto import QuartoNotFoundError as QuartoNotFoundError
from ._build.quarto import QuartoVersionError as QuartoVersionError
from ._build.steps import (
    USER_CODE_ERRORS,
    BuildError,
    Outcome,
    Skipped,
    Step,
    StepError,
    Warn,
    count_listed,
    run_steps,
)
from ._checks import links, proofread
from ._checks.proofread import CheckedFile
from ._cliref import click as cli_click
from ._cliref import render as cli_render
from ._cliref.model import CliCommand
from ._content import custom_pages, publish, sections, user_guide, walk
from ._content.naming import (
    published_path,
)
from ._content.pages import PageMap
from ._content.user_guide import UserGuide
from ._contribution import Contribution
from ._github import GithubRepo
from ._install import format_authors_yaml, update_gitignore
from ._layout import PACKAGE_DIRS, Layout
from ._manifest import Manifest, ManifestError
from ._reference import block as reference_block
from ._reference import discovery, documented, probe
from ._reference import sections as reference_sections
from ._reference.discovery import Categories
from ._remote import HttpRemote, Remote
from ._subprocess import TEXT_MODE_KWARGS
from ._term_player import prerender as term_prerender
from ._utils import (
    GITIGNORE_CONTENT,
    record_site_ownership,
)
from ._website import (
    assembly,
    changelog,
    inline_data,
    page_dates,
    page_status,
    prerender,
    quarto_yml,
    scripts,
    social_cards,
    tags,
)
from ._website.ai_agents import llms_txt
from ._website.ai_agents.skills import SkillsWriter
from ._website.homepage import page as homepage_page
from ._website.homepage import source as homepage_source
from ._website.identity import Identity
from ._website.navigation import navbar as nav_navbar
from ._website.navigation import shared_sidebar
from ._website.project_pages import citation, licence, package_info
from ._website.seo import description as seo_description
from ._website.seo import site_files
from ._website.seo.structured_data import StructuredData
from .config import Config, create_default_config

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ._apiref.api_reference import APIReference
    from ._build.log import BuildLog


# Recognised repository URL labels, casefolded without separators, in preference order.
_REPOSITORY_URL_LABELS = ("repository", "source", "sourcecode", "github", "homepage")


def _url_label(label: str) -> str:
    """
    Normalise a project URL label for matching

    Parameters
    ----------
    label
        The label as declared, such as `Source Code`.

    Returns
    -------
    :
        The label casefolded, without spaces, hyphens or underscores, such as `sourcecode`.
    """
    return re.sub(r"[\s_-]", "", label).casefold()


def _read_manifest(root: Path) -> Manifest:
    """
    Read project metadata with an empty fallback for packaging errors

    Parameters
    ----------
    root
        The directory holding the packaging files.

    Returns
    -------
    :
        The declared metadata, ignoring an unreadable or invalid `setup.cfg` when
        `pyproject.toml` can be read and parsed. Any other packaging read or parse error
        produces an empty manifest.
    """
    try:
        return _manifest.read(root, ignore_unparsable_setup_cfg=True)
    except ManifestError:
        return _manifest.empty()


def _initial_authors(manifest: Manifest) -> list[dict[str, str]]:
    """
    List maintainers and authors for a new `great-docs.yml`

    Parameters
    ----------
    manifest
        The project's declared metadata.

    Returns
    -------
    :
        Entries with a `name`, a `role` and an `email` when declared. List named
        maintainers first with role `Maintainer`, then named authors with role `Author`.
        Keep only the first entry for each name.
    """
    authors: dict[str, dict[str, str]] = {}
    for people, role in ((manifest["maintainers"], "Maintainer"), (manifest["authors"], "Author")):
        for person in people:
            name = person.get("name")
            if name and name not in authors:
                authors[name] = {"name": name, "role": role}
                if email := person.get("email"):
                    authors[name]["email"] = email
    return list(authors.values())


def _print_warning(message: str) -> None:
    """
    Print a warning as a detail line in the current build step

    Parameters
    ----------
    message
        The warning's text.

    Returns
    -------
    :
    """
    print(f"   ⚠️  {message}")


class GreatDocs:
    """
    GreatDocs class for creating beautiful API documentation sites.

    This class provides methods to install assets and configure Quarto projects with the great-docs
    styling and functionality. It handles package discovery, API reference generation, Quarto
    configuration, and site building with a consistent, polished look.

    Parameters
    ----------
    project_path
        Path to the project root directory. If `None` (the default), the current working directory
        is used.

    Attributes
    ----------
    project_root
        Absolute path to the project root directory.
    layout
        Resolved package, documentation, build, and deployment paths.
    build_dir
        Absolute path to the selected Quarto project directory.

    Examples
    --------
    Create a documentation site for a Python package:

    ```python
    from great_docs import GreatDocs

    gd = GreatDocs()

    # One-time setup: generates great-docs.yml and discovers exports
    gd.install()

    # Build the documentation site
    gd.build()

    # Preview locally in a browser
    gd.preview()
    ```

    Build from a different directory:

    ```python
    gd = GreatDocs(project_path="/path/to/my-package")
    gd.build()
    ```

    Notes
    -----
    The typical workflow is: `install()` once to scaffold configuration, then `build()` (and
    optionally `preview()`) as you iterate. The `build()` method re-discovers package exports by
    default, so new functions and classes are picked up automatically.
    """

    def __init__(
        self,
        project_path: str | None = None,
        *,
        config_path: str | None = None,
        create: bool = False,
    ) -> None:
        """
        Initialise a documentation project from its package and configuration

        Parameters
        ----------
        project_path
            Path to the project root directory. Defaults to current directory.
        config_path
            Configuration file, resolved from the current working directory.
        create
            Permit a missing configuration for initialisation without creating files.
        """
        self.layout = Layout.make(
            Path(project_path or os.getcwd()),
            Path(config_path) if config_path else None,
            create=create,
        )
        self._selected_config_path = Path(config_path).resolve() if config_path else None
        self.project_root = self.layout.package_root
        self.build_dir = self.layout.build_dir
        self.package_path = Path(resources.files("great_docs"))
        self.assets_path = self.package_path / "assets"

        # Load configuration from great-docs.yml
        self._config = Config(
            self.layout.package_root,
            config_path=self.layout.config_path,
            cache_dir=self.layout.cache_dir,
        )

        # GitHub and PyPI requests; release warnings print in the build log's format
        self._remote: Remote = HttpRemote(report=lambda message: print(f"   ⚠️  {message}"))

        # Caches for the instance's lifetime; builds do not reset them
        self._package_metadata_cache: dict[str, Any] | None = None
        self._griffe_pkg_cache: dict | None = None  # {normalized_name: griffe Package}
        self._cached_exports: list | None = None
        self._cached_package_name: str | None = None
        self._page_authors = page_dates.site_authors(
            self._config, self.layout.source_dir, self._identity().base_url
        )

    def _get_griffe_package(self, package_name: str):
        """Load a griffe package, using a per-build cache to avoid redundant loads.

        Parameters
        ----------
        package_name
            The normalized (underscored) package name.

        Returns
        -------
        griffe.Object
            The loaded griffe package object.
        """
        import griffe

        if self._griffe_pkg_cache is None:
            self._griffe_pkg_cache = {}

        normalized = package_name.replace("-", "_")
        if normalized not in self._griffe_pkg_cache:
            self._griffe_pkg_cache[normalized] = griffe.load(
                normalized, search_paths=self._griffe_search_paths()
            )
        return self._griffe_pkg_cache[normalized]

    def _prepare_build_directory(self, run: Run) -> None:
        """
        Prepare the great-docs/ build directory with all necessary assets.

        This method creates the great-docs/ directory (if it doesn't exist) and
        copies all CSS, JavaScript, and other assets needed for the build.
        It also creates the _quarto.yml configuration and other necessary files.

        The great-docs/ directory is ephemeral and should not be committed to
        version control. It will be recreated on each build.

        Parameters
        ----------
        run
            The current build, which records whether the site has an API reference.
        """
        print(f"Preparing build directory: {self.build_dir.relative_to(self.project_root)}/")

        outputs.validate(self._config, self.layout)

        hook_names = [Path(path).name for path in self._config.pre_render]
        if len(hook_names) != len(set(hook_names)) or "restore-freeze.py" in hook_names:
            raise ValueError("Pre-render scripts must have distinct, non-reserved filenames")

        # Clean any existing build directory to avoid stale artifacts
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)

        # Create the great-docs directory
        self.build_dir.mkdir(parents=True, exist_ok=True)
        quarto_yml.write_initial(self.build_dir)

        # Create necessary subdirectories
        scripts_dir = self.build_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        reference_dir = self.build_dir / "reference"
        reference_dir.mkdir(exist_ok=True)
        # Directory metadata also marks reference pages generated from older snapshots.
        page_dates.mark_generated(reference_dir, self._config)

        # Copy restore-freeze script when freeze is configured OR _freeze/ exists
        has_freeze_cache = self.layout.freeze_dir.is_dir()
        if self._config.freeze or has_freeze_cache:
            restore_freeze_src = self.assets_path / "restore-freeze.py"
            restore_freeze_dst = scripts_dir / "restore-freeze.py"
            shutil.copy2(restore_freeze_src, restore_freeze_dst)

        # Copy user-provided pre-render scripts
        for script_path in self._config.pre_render:
            src = self.layout.source_dir / script_path
            if src.is_file():
                dst = scripts_dir / src.name
                shutil.copy2(src, dst)
            else:
                print(f"Warning: Pre-render script not found: {script_path}")

        # Copy bibliography and CSL files into the build directory so that
        # project-level citations resolve (see _update_quarto_config for wiring)
        for bib_path in self._config.bibliography:
            src = self.layout.source_dir / bib_path
            if src.is_file():
                publish.copy_asset(self.layout, src, self.build_dir / src.name)
            else:
                print(f"Warning: Bibliography file not found: {bib_path}")
        csl_path = self._config.csl
        if csl_path:
            csl_src = self.layout.source_dir / csl_path
            if csl_src.is_file():
                publish.copy_asset(self.layout, csl_src, self.build_dir / csl_src.name)
            else:
                print(f"Warning: CSL file not found: {csl_path}")

        # Copy custom CSS files (site.css) into the build directory
        # where _quarto.yml will refer to them by basename
        for css_path in self._config.css:
            css_src = self.layout.source_dir / css_path
            if css_src.is_file():
                publish.copy_asset(self.layout, css_src, self.build_dir / css_src.name)
            else:
                print(f"Warning: CSS file not found: {css_path}")

        # Copy SCSS theme file (contains all site styling)
        scss_src = self.assets_path / "great-docs.scss"
        shutil.copy2(scss_src, self.build_dir / "great-docs.scss")

        # Quarto resolves the signature grammar relative to the build directory.
        shutil.copy2(
            self.assets_path / "pythonsignature.xml", self.build_dir / "pythonsignature.xml"
        )

        # Copy the evolution demo data file
        demo_json_src = self.assets_path / "api-evolution-demo.json"
        if demo_json_src.exists():
            shutil.copy2(demo_json_src, self.build_dir / "api-evolution-demo.json")

        # Copy the evolution shortcode extension (auto-discovered by Quarto)
        extensions_src = self.assets_path / "_extensions"
        if extensions_src.exists():
            extensions_dst = self.build_dir / "_extensions"
            shutil.copytree(extensions_src, extensions_dst, dirs_exist_ok=True)

        # Pages that embed marimo notebooks need their island HTML and WASM exports before
        # Quarto renders them.
        if self._config.marimo_enabled:
            _marimo.prepare_notebooks(
                self.layout.source_dir,
                self.build_dir,
                report=print,
                warn=partial(print, file=sys.stderr),
            )

        # Copy the site's scripts and stylesheets
        scripts.copy(
            self._config,
            self.build_dir,
            has_repository=self._get_github_repo_info()[0] is not None,
        )

        # Create .gitignore for the great-docs directory
        gitignore_path = self.build_dir / ".gitignore"
        gitignore_path.write_text(GITIGNORE_CONTENT, encoding="utf-8")

        # Note: User guide files are copied by _process_user_guide() during build
        # which handles stripping numeric prefixes for clean URLs

        # Create _quarto.yml configuration
        self._update_quarto_config(run)

        page_dates.copy_portraits(self._config, self.layout.source_dir, self.build_dir)

        # Write options JSON for the restore-freeze script
        gd_options = {
            "freeze_dir": os.path.relpath(self.layout.freeze_dir, self.build_dir),
        }
        gd_options_path = self.build_dir / "_gd_options.json"
        with open(gd_options_path, "w") as f:
            json.dump(gd_options, f)

        # Add API reference configuration
        # (auto-skips if no documentable exports are found)
        self._add_api_reference_config(run)
        if run.has_api_reference:
            reference_sections.update_sidebar(self._config, self.build_dir)

        # Build the homepage after the API reference configuration. Its metadata
        # margin can then include links to `llms.txt` and `llms-full.txt` when the
        # build will generate them.
        run.user_guide = user_guide.discover(self._config, self.layout, report=_print_warning)
        self._create_index_from_readme(run.user_guide, run.has_api_reference, force_rebuild=True)

    def _copy_assets(self) -> bool:
        """
        Copy assets directory from project root to build directory.

        Looks for assets/ directory in project root and copies all contents
        to great-docs/assets/ directory. This allows pages to reference assets
        at a predictable path (e.g., assets/image.png).

        Returns
        -------
        bool
            True if assets were copied, False if no assets directory found.
        """
        source_assets = self.layout.source_dir / "assets"

        if not source_assets.exists() or not source_assets.is_dir():
            return False

        dest_assets = self.build_dir / "assets"

        # Remove existing assets directory to ensure clean copy
        if dest_assets.exists():
            shutil.rmtree(dest_assets)

        # Copy entire assets directory
        shutil.copytree(source_assets, dest_assets)

        # Count files for reporting
        file_count = sum(1 for _ in dest_assets.rglob("*") if _.is_file())
        print(f"\n📦 Copied {file_count} asset file(s) to great-docs/assets/")

        return True

    def _page_map(self, guide: UserGuide | None) -> PageMap:
        """
        Map authored pages to their published paths for this build

        Parameters
        ----------
        guide
            The discovered user guide, or `None` when it has no pages.

        Returns
        -------
        :
            The page map for the current sources and configuration.
        """
        homepage = homepage_source.find(self.layout)[:1]
        if guide is not None and self._config.homepage == "user_guide":
            homepage.append(guide["files"][0]["path"])
        return PageMap.make(self._config, self.layout, guide, homepage)

    def install(self, force: bool = False) -> None:
        """
        Initialize great-docs in your project.

        This method creates a great-docs.yml configuration file in the project root
        with discovered exports and sensible defaults. The docs directory and assets
        will be created later during the build process.

        ::: {.callout-note}
        In practice, you would normally use the `great-docs init` CLI command rather
        than calling this method directly. See the
        [CLI reference](cli/init.qmd) for details.
        :::

        Parameters
        ----------
        force
            If `True`, overwrite existing great-docs.yml without prompting. Default is `False`.

        Examples
        --------
        Initialize great-docs in the current directory:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        docs.install()
        ```

        Initialize in a specific project directory, overwriting existing config:

        ```python
        docs = GreatDocs("/path/to/my/project")
        docs.install(force=True)
        ```
        """
        print("Initializing great-docs...")

        self.layout = Layout.make(self.project_root, self._selected_config_path, create=True)
        self.build_dir = self.layout.build_dir

        # Generate great-docs.yml with discovered exports
        self._generate_initial_config(force=force)

        # Reload configuration after generating it
        self._config = Config(
            self.layout.package_root,
            config_path=self.layout.config_path,
            cache_dir=self.layout.cache_dir,
        )

        # Update project root .gitignore to exclude great-docs/
        update_gitignore(self.layout, report=print, ask=None if force else input)

        print("\n✅ Great Docs initialization complete!")
        print("\nNext steps:")
        print("1. Review great-docs.yml to customize your API reference structure")
        print("   (Reorder items, add sections, set 'members: false' to exclude methods)")
        print("2. Run `great-docs build` to generate and build your documentation site")
        print("3. Run `great-docs preview` to view the site locally")
        print("\nOther helpful commands:")
        print("  great-docs scan           # Preview API organization")
        print("  great-docs build --watch  # Watch for changes and rebuild")

    def _detect_package_name(self) -> str | None:
        """
        Detect the project's distribution name

        Use the name declared in the packaging files. If none is available, use the sole
        non-hidden package directory at the project root.

        Returns
        -------
        :
            The declared name or package directory name, or `None` if neither identifies
            the distribution.
        """
        if name := _read_manifest(self.project_root)["name"]:
            return name
        potential_packages = [
            d
            for d in self.project_root.iterdir()
            if d.is_dir() and (d / "__init__.py").exists() and not d.name.startswith(".")
        ]
        if len(potential_packages) == 1:
            return potential_packages[0].name
        return None

    def _normalize_package_name(self, package_name: str) -> str:
        """
        Convert a package name to its importable form.

        PyPI package names can use hyphens (e.g., 'great-docs') but Python
        imports must use underscores (e.g., 'great_docs'). This method handles
        the conversion.

        Parameters
        ----------
        package_name
            The package name (potentially with hyphens)

        Returns
        -------
        str
            The importable package name (with underscores)
        """
        return package_name.replace("-", "_")

    def _resolve_importable_name(self, package_name: str) -> str:
        """
        Resolve the importable module name for a project.

        Prefers the module name from `_detect_module_name` (an explicit `module:` in great-docs.yml,
        build-backend hints, or auto-discovery), falling back to the normalized PyPI project name
        when detection returns `None`.

        Parameters
        ----------
        package_name
            The PyPI project name to fall back to.

        Returns
        -------
        str
            The importable module name.
        """
        module_name = self._detect_module_name()
        return module_name if module_name else self._normalize_package_name(package_name)

    def _detect_module_name(self) -> str | None:
        """
        Detect the importable module to document

        The module name can differ from the distribution name: `py-yaml12` may install
        `yaml12`. Use the first available module from these sources, in order:

        1. Use the configured `module`.
        2. Use the first project-root `.pyi` stub other than `__init__.pyi`.
        3. Use the top-level package of Maturin's compiled module.
        4. Use the first package found in setuptools discovery directories, excluding names
           beginning with `.`, `_` or `test`.
        5. Use the first setuptools `packages` entry. Preserve dotted import names such as
           `nspkg.core`; for a path, use its last component.
        6. Use the last component of the first hatch or Poetry package path. If it is a
           namespace directory without `__init__.py`, prefer its subpackage named by the
           remaining distribution name when that subpackage has `__init__.py`. For example,
           select `firebird.base` for distribution `firebird-base`.
        7. Find a package directory for the distribution name and form its dotted name
           relative to the first containing `src`, `python`, `lib` or discovery directory,
           then the project root. Fall back to the package directory's own name.

        Returns
        -------
        :
            The importable module name, or `None` if no source identifies one.
        """
        if self._config.module:
            return self._config.module

        package_root = self.layout.package_root

        for pyi_file in package_root.glob("*.pyi"):
            if pyi_file.stem != "__init__":
                return pyi_file.stem

        manifest = _read_manifest(package_root)
        if manifest["extension_module"]:
            # Document the top-level package rather than its compiled extension submodule.
            return manifest["extension_module"].split(".", 1)[0]

        for directory in manifest["discovery_dirs"]:
            base = package_root / directory
            if not base.is_dir():
                continue
            for item in base.iterdir():
                if (
                    item.is_dir()
                    and (item / "__init__.py").exists()
                    and not item.name.startswith((".", "_", "test"))
                ):
                    return item.name

        if manifest["declared_import_names"]:
            # Preserve dotted import names; path entries identify their last directory.
            return manifest["declared_import_names"][0].split("/")[-1]

        if manifest["declared_packages"]:
            declared = manifest["declared_packages"][0]
            name = declared.split("/")[-1]
            path = package_root / declared
            if path.is_dir() and not (path / "__init__.py").exists():
                distribution = (self._detect_package_name() or "").replace("-", "_")
                sub_name = distribution.removeprefix(f"{name}_")
                if (
                    distribution.startswith(f"{name}_")
                    and (path / sub_name / "__init__.py").exists()
                ):
                    return f"{name}.{sub_name}"
            return name

        project_name = self._detect_package_name()
        init_file = self._find_package_init(project_name) if project_name else None
        if init_file is None:
            return None
        package_dir = init_file.parent
        for layout_dir in (
            *(package_root / directory for directory in PACKAGE_DIRS),
            *(package_root / directory for directory in manifest["discovery_dirs"]),
            package_root,
        ):
            if package_dir != layout_dir and package_dir.is_relative_to(layout_dir):
                return ".".join(package_dir.relative_to(layout_dir).parts)
        return package_dir.name

    def _is_compiled_extension(self) -> bool:
        """
        Check if this is a compiled extension package (PyO3, Cython, etc.).

        Returns
        -------
        bool
            True if this appears to be a compiled extension package.
        """
        package_root = self.layout.package_root

        # Check for Cargo.toml (Rust/PyO3)
        if (package_root / "Cargo.toml").exists():
            return True

        # Check for .pyi stub files without corresponding .py files
        pyi_files = list(package_root.glob("*.pyi"))
        for pyi_file in pyi_files:
            if pyi_file.stem != "__init__":
                py_file = pyi_file.with_suffix(".py")
                if not py_file.exists():
                    return True

        return False

    def _griffe_search_paths(self) -> list[str | Path]:
        """Return search paths for griffe so it can find src/python/lib layouts.

        Prepends the package root and common sub-layouts (`src/`, `python/`, `lib/`) in front of
        `sys.path` so that griffe can locate packages in non-flat layouts while still falling back
        to the normal import path.
        """
        package_root = self.layout.package_root
        extra: list[str | Path] = [package_root]
        for subdir in PACKAGE_DIRS:
            candidate = package_root / subdir
            if candidate.is_dir():
                extra.append(candidate)
        return extra + sys.path

    def _get_package_metadata(self) -> dict[str, Any]:
        """
        Read project metadata from packaging files

        Read the description, licence, authors, maintainers, URLs, Python requirement,
        keywords and dependencies from the packaging files. Cache the first result when
        `pyproject.toml` exists; otherwise, read the files on each call.

        Returns
        -------
        :
            The project fields, keyed by name. Ignore an unreadable or invalid `setup.cfg`
            beside a readable, valid `pyproject.toml`. Other packaging read or parse errors
            leave the fields empty.
        """
        if self._package_metadata_cache is not None:
            return self._package_metadata_cache
        package_root = self.layout.package_root
        manifest = _read_manifest(package_root)
        metadata: dict[str, Any] = {
            "description": manifest["description"],
            "license": manifest["license"],
            "authors": manifest["authors"],
            "maintainers": manifest["maintainers"],
            "urls": manifest["urls"],
            "requires_python": manifest["requires_python"],
            "keywords": manifest["keywords"],
            "dependencies": manifest["dependencies"],
            "optional_dependencies": manifest["optional_dependencies"],
            # The package-information page requires this key for parsed optional dependencies.
            "optional_dependencies_full": manifest["optional_dependencies"],
        }
        if (package_root / "pyproject.toml").exists():
            self._package_metadata_cache = metadata
        return metadata

    def _get_github_repo_info(self) -> tuple[str | None, str | None, str | None]:
        """
        Find the project's GitHub repository

        Use the configured `repo`, falling back to project URLs labelled `Repository`,
        `Source`, `Source Code`, `GitHub` or `Homepage`, in that order. Ignore case,
        whitespace, hyphens and underscores when matching labels.

        Returns
        -------
        :
            The owner, repository name and repository URL, or three `None` values if no URL
            is selected or the selected URL is not a GitHub repository.
        """
        repo_url = self._config.repo
        if not repo_url:
            # Reverse insertion order so the first declared label wins after normalisation.
            urls = {
                _url_label(label): url
                for label, url in reversed(self._get_package_metadata().get("urls", {}).items())
            }
            repo_url = next(
                (urls[label] for label in _REPOSITORY_URL_LABELS if label in urls), None
            )
        repo = GithubRepo.parse(repo_url)
        if repo is None:
            return None, None, None
        return repo.owner, repo.name, repo.url

    # =========================================================================
    # Custom Sections Methods
    # =========================================================================

    def _process_sections(self, guide: UserGuide | None) -> int:
        """
        Publish the configured sections and add their sidebars and navbar links

        Parameters
        ----------
        guide
            The discovered user guide, or `None` when it has no pages.

        Returns
        -------
        :
            The number of sections published.
        """
        found = sections.read(
            self._config, self.layout, report=lambda message: print(f"   ⚠️  {message}")
        )
        if not found:
            return 0

        pages = self._page_map(guide)
        add_dates = partial(page_dates.add_to_page, config=self._config, authors=self._page_authors)
        for section in found:
            section.destination.mkdir(parents=True, exist_ok=True)
            # Copy asset directories first so published pages replace their raw copies
            for item in section.source.iterdir():
                if (
                    item.is_dir()
                    and not self.layout.is_reserved_directory(item)
                    and walk.is_asset_dir(item)
                ):
                    destination = section.destination / item.name
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(item, destination)

            published = sections.publish(
                section, config=self._config, layout=self.layout, pages=pages, add_dates=add_dates
            )
            if not section.blog:
                self._copy_directory_metadata(
                    section.files, section.source, section.destination, strip_prefix=True
                )

            quarto_config = quarto_yml.read(self.build_dir, seed_website=True)
            changed = published.sidebar is not None
            if published.sidebar is not None:
                sidebar_id = published.sidebar["id"]
                quarto_config["website"]["sidebar"] = [
                    *(
                        entry
                        for entry in quarto_config["website"]["sidebar"]
                        if not (isinstance(entry, dict) and entry.get("id") == sidebar_id)
                    ),
                    published.sidebar,
                ]
            if nav_navbar.add_link(
                quarto_config, published.navbar, self._config, after=published.navbar_after
            ):
                changed = True
            if changed:
                quarto_yml.write(self.build_dir, quarto_config)

            label = "📰" if section.blog else "📂"
            print(f"   {label} {section.title}: {len(published.pages)} post(s) from {section.dir}/")

        return len(found)

    # =========================================================================
    # Custom Static Pages Methods
    # =========================================================================

    def _process_custom_pages(self, guide: UserGuide | None) -> int:
        """
        Publish the configured custom pages

        Parameters
        ----------
        guide
            The discovered user guide, or `None` when it has no pages.

        Returns
        -------
        :
            The number of pages processed.
        """
        report = _print_warning
        sources = custom_pages.find_sources(self._config, self.layout, report=report)
        if not sources:
            return 0

        identity = self._identity()
        head = custom_pages.RawPageHead(
            base_url=identity.base_url,
            card_image_url=(
                social_cards.publish_image(
                    self._config, self.layout, self.build_dir, identity.base_url, report=report
                )
                if self._config.social_cards_enabled
                else None
            ),
            structured_data=self._structured_data(),
            site_name=identity.name,
            default_description=self._default_description(),
        )
        published = custom_pages.publish(
            sources,
            config=self._config,
            layout=self.layout,
            pages=self._page_map(guide),
            head=head,
            add_dates=partial(
                page_dates.add_to_page, config=self._config, authors=self._page_authors
            ),
            report=report,
        )
        # A page's `navbar_after` names a label, which a `Contribution` cannot express.
        for link, after in published.navbar:
            quarto_config = quarto_yml.read(self.build_dir, seed_website=True)
            if nav_navbar.add_link(quarto_config, link, self._config, after=after):
                quarto_yml.write(self.build_dir, quarto_config)
        if published.resources or published.render_excludes:
            contribution = Contribution(
                resources=tuple(published.resources),
                render_excludes=tuple(published.render_excludes),
            )
            with quarto_yml.edit(self.build_dir, seed_website=True) as quarto_config:
                quarto_yml.apply(quarto_config, contribution)
        return published.pages

    # =========================================================================
    # User Guide Methods
    # =========================================================================

    def _publish_user_guide(self, guide: UserGuide) -> list[str]:
        """
        Publish the user guide's pages, asset directories and directory metadata

        Parameters
        ----------
        guide
            The user guide.

        Returns
        -------
        :
            The copied page paths relative to the build directory, in reading order.
        """
        source_dir = guide["source_dir"]
        target_dir = self.build_dir / user_guide.SIDEBAR_ID
        strip_prefix = not guide.get("explicit", False)
        add_dates = partial(page_dates.add_to_page, config=self._config, authors=self._page_authors)
        copied_files = user_guide.copy_pages(
            guide, target_dir, layout=self.layout, pages=self._page_map(guide), add_dates=add_dates
        )

        # Also copy any asset directories (images, data, code snippets, etc.)
        for item in source_dir.iterdir():
            if (
                item.is_dir()
                and not self.layout.is_reserved_directory(item)
                and walk.is_asset_dir(item)
            ):
                dst_dir = target_dir / item.name
                if dst_dir.exists():
                    shutil.rmtree(dst_dir)  # pragma: no cover
                shutil.copytree(item, dst_dir)

        self._copy_directory_metadata(
            (page["path"] for page in guide["files"]),
            source_dir,
            target_dir,
            strip_prefix=strip_prefix,
        )

        return copied_files

    def _copy_directory_metadata(
        self,
        pages: "Iterable[Path]",
        source_dir: Path,
        dest_dir: Path,
        *,
        strip_prefix: bool,
    ) -> None:
        """
        Copy the `_metadata.yml` and `_metadata.yaml` files that apply to copied pages

        Quarto applies a directory's metadata file to the pages beneath it, so a file
        is copied from `source_dir` and from every directory between it and a page.
        Directories whose names start with `_` or `.` are skipped because Quarto
        renders no pages there. A destination file that already exists was written by
        the build itself; it is kept and the skipped source is reported.

        Parameters
        ----------
        pages
            Source pages that were copied into `dest_dir`.
        source_dir
            Root of the source tree the pages came from.
        dest_dir
            Build directory that mirrors `source_dir`.
        strip_prefix
            Whether numeric prefixes were stripped from the pages' directory names,
            so the metadata lands in the same renamed directories.

        Returns
        -------
        :
            Nothing; the files are copied in place.
        """
        directories = {Path()}
        for page in pages:
            if page.is_relative_to(source_dir):
                directories.update(page.relative_to(source_dir).parents)

        for rel_dir in sorted(directories):
            if any(part.startswith(("_", ".")) for part in rel_dir.parts):
                continue
            dest_rel = published_path(rel_dir, strip_prefix=strip_prefix)
            for name in ("_metadata.yml", "_metadata.yaml"):
                src_file = source_dir / rel_dir / name
                if not src_file.is_file():
                    continue
                dst_file = dest_dir / dest_rel / name
                if dst_file.exists():
                    print(
                        f"   ⚠️  Skipping {src_file}: the build already wrote "
                        f"{dst_file.relative_to(self.build_dir).as_posix()}"
                    )
                    continue
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)

    def _default_description(self) -> str | None:
        """
        Resolve the site's default search description

        Returns
        -------
        :
            The description as plain text, or `None` when neither
            `seo.default_description` nor the package description is set.
        """
        package_description = self._get_package_metadata().get("description")
        return seo_description.default_description(self._config, package_description)

    def _structured_data(self) -> StructuredData | None:
        """
        Describe the package as JSON-LD for the homepage and reference pages

        Returns
        -------
        :
            The structured data, or `None` when it is disabled.
        """
        identity = self._identity()
        return StructuredData.make(
            self._config, self._get_package_metadata(), identity.name, identity.base_url
        )

    def _update_config_with_user_guide(
        self, guide: UserGuide, blended_first_page: str | None = None
    ) -> None:
        """
        Add the user guide's sidebar and navbar link to `_quarto.yml`

        Parameters
        ----------
        guide
            The user guide.
        blended_first_page
            The promoted page's former path under `user-guide/`, or `None` when no page was
            promoted.

        Returns
        -------
        :
        """
        if not quarto_yml.path(self.build_dir).exists():
            return

        config = quarto_yml.read(self.build_dir)

        if "website" not in config:
            config["website"] = {}

        sidebar_config = user_guide.sidebar(guide)

        # Blended homepage mode publishes the first guide page at the site root
        if self._config.homepage == "user_guide" and blended_first_page:
            user_guide.link_homepage(sidebar_config, blended_first_page)  # pragma: no cover

        if "sidebar" not in config["website"]:
            config["website"]["sidebar"] = []

        sidebar = config["website"]["sidebar"]

        # Remove existing user-guide sidebar if present
        sidebar = [
            s for s in sidebar if not (isinstance(s, dict) and s.get("id") == user_guide.SIDEBAR_ID)
        ]

        # Add the new user guide sidebar
        sidebar.append(sidebar_config)
        config["website"]["sidebar"] = sidebar

        # Update navbar to include User Guide link (skip in blended homepage mode)
        if self._config.homepage != "user_guide" and "navbar" in config["website"]:
            navbar = config["website"]["navbar"]
            if "left" in navbar:
                href = user_guide.entry(guide)
                # Labels may already be translated; the target identifies an existing guide link
                has_user_guide = any(
                    isinstance(item, dict) and item.get("href") == href for item in navbar["left"]
                )
                if not has_user_guide:
                    # The User Guide link precedes Reference, or goes first if Reference is absent.
                    insert_idx = next(
                        (
                            i
                            for i, item in enumerate(navbar["left"])
                            if isinstance(item, dict)
                            and nav_navbar.REFERENCE.owns(item.get("href"))
                        ),
                        0,
                    )
                    navbar["left"].insert(
                        insert_idx,
                        {"text": nav_navbar.USER_GUIDE.label(self._config), "href": href},
                    )

        quarto_yml.write(self.build_dir, config)

    def _process_user_guide(self, guide: UserGuide | None, has_api_reference: bool) -> bool:
        """
        Publish the user guide and add its sidebar and navbar link

        Parameters
        ----------
        guide
            The discovered user guide, or `None` when it has no pages.
        has_api_reference
            Whether the site has an API reference, which a fallback homepage links to.

        Returns
        -------
        :
            Whether the user guide was published.
        """
        if not guide:
            # Fallback: if homepage mode is "user_guide" but no UG pages exist,
            # warn and create a normal index from README instead.
            if self._config.homepage == "user_guide":
                print(
                    "   ⚠️  homepage: user_guide is set but no user guide pages found; "
                    "falling back to index mode"
                )
                self._create_index_from_readme(
                    guide, has_api_reference, force_rebuild=True, fallback_to_index=True
                )
            return False

        print("\n📖 Processing User Guide...")

        if guide.get("explicit", False):
            print("   Using explicit section ordering from great-docs.yml")  # pragma: no cover

        print(f"   Found {len(guide['files'])} page(s)")

        copied_files = self._publish_user_guide(guide)
        print(f"   Copied {len(copied_files)} file(s) to docs/user-guide/")

        # In "user_guide" homepage mode, promote the first UG page to index.qmd
        blended_first_page = None
        if self._config.homepage == "user_guide":
            blended_first_page = self._create_blended_index(guide, copied_files)  # pragma: no cover

        self._update_config_with_user_guide(guide, blended_first_page)

        if guide["sections"]:
            print(f"   Sections: {', '.join(guide['sections'])}")

        print("✅ User Guide configured")
        return True

    def _create_blended_index(self, guide: UserGuide, copied_files: list[str]) -> str | None:
        """
        Promote the first user guide page to `index.qmd` in blended homepage mode

        Remove the original page from `user-guide/` after writing the homepage.

        Parameters
        ----------
        guide
            The user guide.
        copied_files
            List of copied file paths relative to the docs dir (e.g.
            `["user-guide/introduction.qmd", ...]`).

        Returns
        -------
        :
            The promoted page's former path under `user-guide/`, or `None` when no page was
            promoted.
        """
        if not guide["files"]:
            return None

        dest_rel = user_guide.published(guide, guide["files"][0])
        first_ug_path = self.build_dir / user_guide.SIDEBAR_ID / dest_rel

        if not first_ug_path.exists():
            print(f"   ⚠️  First UG page '{first_ug_path}' not found for blended homepage")
            return None

        homepage_page.write_blended(
            self._config,
            self.layout,
            self.build_dir,
            first_ug_path.read_text(encoding="utf-8"),
            metadata=self._get_package_metadata(),
            package_name=self._detect_package_name(),
            pages=self._page_map(guide),
            page_authors=self._page_authors,
        )

        # Remove the duplicate from user-guide/
        first_ug_path.unlink()

        print("   📄 Blended homepage: first UG page → index.qmd")
        return f"user-guide/{dest_rel}"

    def _find_package_init(self, package_name: str) -> Path | None:
        """
        Find a package's `__init__.py` in declared and common package locations

        Search declared package paths and setuptools discovery directories before common
        layouts such as `python/`, `src/` and `lib/`. Prefer a matching file containing
        `__version__` or `__all__`, then any matching file. If neither is found, search
        common layouts for another package.

        Parameters
        ----------
        package_name
            The name of the package to find.

        Returns
        -------
        :
            The path to `__init__.py`, or `None` if no package is found.
        """
        # Package directories may use underscores where distribution names use hyphens.
        normalized_name = package_name.replace("-", "_")

        package_root = self.layout.package_root
        manifest = _read_manifest(package_root)

        # Declared packages take precedence over candidates in discovery directories.
        search_paths: list[Path] = []
        for package in manifest["declared_packages"]:
            search_paths.append(package_root / package)
            if "/" not in package:
                search_paths.append(package_root / "src" / package)
        for directory in manifest["discovery_dirs"]:
            search_paths += [
                package_root / directory / name for name in (package_name, normalized_name)
            ]

        # Handle dotted module names (namespace packages like "firebird.base")
        # by converting dots to path separators
        dotted_path = None
        if "." in package_name:
            dotted_path = package_name.replace(".", os.sep)
            search_paths.extend(
                [
                    package_root / dotted_path,
                    package_root / "src" / dotted_path,
                    package_root / "python" / dotted_path,
                    package_root / "lib" / dotted_path,
                ]
            )

        # Then add standard locations based on package name
        search_paths.extend(
            [
                package_root / package_name,
                package_root / normalized_name,
                package_root / "python" / package_name,
                package_root / "python" / normalized_name,
                package_root / "src" / package_name,
                package_root / "src" / normalized_name,
                package_root / "lib" / package_name,
                package_root / "lib" / normalized_name,
            ]
        )

        # First pass: look for __init__.py with __version__ or __all__
        for package_dir in search_paths:
            if not package_dir.exists() or not package_dir.is_dir():
                continue

            init_file = package_dir / "__init__.py"
            if init_file.exists():
                try:
                    content = init_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if "__version__" in content or "__all__" in content:
                    return init_file

        # Second pass: accept any __init__.py in a matching directory
        for package_dir in search_paths:
            if not package_dir.exists() or not package_dir.is_dir():
                continue

            init_file = package_dir / "__init__.py"
            if init_file.exists():
                return init_file

        # Third pass: auto-discover any Python package in common locations
        # This handles cases where the package name doesn't match the project name
        auto_discover_dirs = [
            package_root,
            package_root / "src",
            package_root / "python",
            package_root / "lib",
        ]

        for base_dir in auto_discover_dirs:
            if not base_dir.exists():
                continue
            for item in base_dir.iterdir():
                if not item.is_dir():
                    continue
                # Skip common non-package directories
                if item.name.startswith((".", "_")) or item.name in (
                    "tests",
                    "test",
                    "docs",
                    "doc",
                    "examples",
                    "scripts",
                    "build",
                    "dist",
                    "__pycache__",
                    "venv",
                    ".venv",
                    "node_modules",
                    "site-packages",
                ):
                    continue
                init_file = item / "__init__.py"
                if init_file.exists():
                    return init_file

        return None

    def _get_package_exports(self, package_name: str) -> list[str] | None:
        """
        Find the names a package exports, and remember them for later calls

        Read griffe's model of the package. When griffe cannot load the package, or its
        `__all__` lists only names it does not define, read a literal `__all__` from its
        `__init__.py` instead.

        Parameters
        ----------
        package_name
            The package's importable name. Dashes count as underscores.

        Returns
        -------
        :
            The exported names, or `None` if neither source lists any.
        """
        normalized = package_name.replace("-", "_")
        if self._cached_package_name == normalized and self._cached_exports is not None:
            return self._cached_exports

        exports = None
        try:
            package = self._get_griffe_package(normalized)
        except USER_CODE_ERRORS as error:
            print(
                f"Warning: Could not load package with griffe ({type(error).__name__})",
                file=sys.stderr,
            )
            if package_name != normalized:
                print(
                    f"   (Looking for module '{normalized}' from project '{package_name}')",
                    file=sys.stderr,
                )
        else:
            exports = discovery.discover_exports(package, self._config, report=print)

        if exports is None:
            print("Falling back to __all__ discovery", file=sys.stderr)
            init_file = self._find_package_init(package_name)
            if init_file is None:
                print(
                    f"Could not locate __init__.py for package '{package_name}'"
                    + (f" (module name: '{normalized}')" if normalized != package_name else ""),
                    file=sys.stderr,
                )
                if normalized != package_name:
                    print(
                        f"Tip: Ensure a '{normalized}/' directory exists with an __init__.py file",
                        file=sys.stderr,
                    )
            else:
                print(f"Found package __init__.py at: {init_file.relative_to(self.project_root)}")
                exports = discovery.parse_dunder_all(init_file, self._config, report=print)

        self._cached_package_name = normalized
        self._cached_exports = exports
        return exports

    def _categorise_exports(self, package_name: str, exports: list[str]) -> Categories:
        """
        Sort a package's exports into the groups of the API reference

        A method, or a member of an exported module, stays only if the renderer can document
        it after importing the package; if the package cannot be imported, finding it by static
        analysis is enough. When griffe cannot load the package, every export other than a
        metadata name such as `__version__` goes under `other`.

        Parameters
        ----------
        package_name
            The package's importable name. Dashes count as underscores.
        exports
            The names to sort.

        Returns
        -------
        :
            The sorted exports.
        """
        normalized = package_name.replace("-", "_")
        try:
            package = self._get_griffe_package(normalized)
        except USER_CODE_ERRORS as error:
            print(
                f"Warning: Could not load package with griffe ({type(error).__name__})",
                file=sys.stderr,
            )
            categories = discovery.empty_categories()
            categories["other"] = [name for name in exports if name not in discovery.METADATA_NAMES]
            return categories

        return discovery.categorise_exports(
            package,
            exports,
            renderable=probe.RendererCheck(normalized, report=print),
            report=print,
        )

    def _create_api_sections_with_config(self, package_name: str) -> list | None:
        """
        Build API sections from explicit entries or discovered exports
        """
        reference_config = self._config.reference
        if reference_config:
            print("Using explicit reference configuration from great-docs.yml")
            try:
                package = self._get_griffe_package(package_name)
            except USER_CODE_ERRORS:
                categories = discovery.empty_categories()
            else:
                try:
                    categories = discovery.categorise_references(package, reference_config)
                except BuildError as error:
                    print(f"ERROR: {error}", file=sys.stderr)
                    raise
            configured = reference_sections.from_explicit_config(
                self._config, reference_config, categories
            )
            if configured:
                return configured

        exports = self._get_package_exports(package_name)
        if not exports:
            return None
        skip_names = {"__version__", "__author__", "__email__", "__all__"}
        exports = [name for name in exports if name not in skip_names]
        if not exports:
            return None
        print(f"Found {len(exports)} exported names to document")
        categories = self._categorise_exports(package_name, exports)
        return reference_sections.from_categories(self._config, categories)

    def _generate_initial_config(self, force: bool = False) -> bool:
        """
        Generate an initial great-docs.yml with discovered exports.

        Renders the shipped `great-docs.default.yml` template with detected
        values (`parser`, `dynamic`, and optionally `module`, `authors`,
        `reference`) spliced in as live keys.

        Parameters
        ----------
        force
            If `True`, overwrite existing great-docs.yml without prompting.

        Returns
        -------
        bool
            True if config was created, False if skipped.
        """
        config_path = self.layout.config_path

        if config_path.exists() and not force:
            print(
                f"great-docs.yml already exists at {config_path}\n"
                "Use --force to overwrite it (this will reset to defaults)."
            )
            return False

        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Detect package name
        package_name = self._detect_package_name()
        if not package_name:
            print("Warning: Could not detect package name, creating minimal config")
            # No importable name to detect from; fall back to the documented
            # parser/dynamic defaults so the emitted config is never empty.
            minimal_overrides = {"parser": "parser: numpy", "dynamic": "dynamic: true"}
            config_path.write_text(create_default_config(minimal_overrides), encoding="utf-8")
            print(f"Created {config_path}")
            return True

        overrides: dict[str, str] = {}

        # Resolve the importable module name.
        importable_name = self._normalize_package_name(package_name)
        module_name = self._detect_module_name()
        if module_name:
            importable_name = module_name
        normalized_name = self._normalize_package_name(package_name)
        explicit_module = module_name if module_name != normalized_name else None
        if explicit_module:  # pragma: no cover
            overrides["module"] = f"module: {explicit_module}"  # pragma: no cover

        # Detect docstring style
        print("Detecting docstring style...")
        package = None
        try:
            package = self._get_griffe_package(importable_name)
        except USER_CODE_ERRORS as error:
            print(
                f"Warning: Could not load package for docstring detection ({type(error).__name__})"
            )
            parser_style = "numpy"
        else:
            parser_style = probe.detect_docstring_style(package, report=print)
        overrides["parser"] = f"parser: {parser_style}"

        authors_yaml = format_authors_yaml(
            _initial_authors(_read_manifest(self.layout.package_root))
        )
        if authors_yaml:
            overrides["authors"] = authors_yaml

        # Discover exports
        exports = self._get_package_exports(importable_name)
        if not exports:
            print(
                "Warning: Could not discover exports; edit the commented "
                "'reference:' section in great-docs.yml to list your API."
            )
            print("Testing dynamic introspection mode...")
            dynamic_mode = package is None or probe.detect_dynamic_mode(
                package, package.members, report=print
            )
            overrides["dynamic"] = f"dynamic: {'true' if dynamic_mode else 'false'}"
            config_path.write_text(create_default_config(overrides), encoding="utf-8")
            print(f"Created {config_path}")
            return True

        # Categorize exports (this also detects cyclic aliases)
        print("Categorizing API objects...")
        categories = self._categorise_exports(importable_name, exports)

        cyclic_alias_count = categories.get("cyclic_alias_count", 0)
        if cyclic_alias_count > 0:
            print(
                f"Detected {cyclic_alias_count} cyclic alias(es), using dynamic: false"
            )  # pragma: no cover
            dynamic_mode = False  # pragma: no cover
        else:
            print("Testing dynamic introspection mode...")
            dynamic_mode = package is None or probe.detect_dynamic_mode(
                package, exports, report=print
            )
        overrides["dynamic"] = f"dynamic: {'true' if dynamic_mode else 'false'}"

        reference_yaml = reference_block.reference_yaml(self._config, categories)
        if "  - title:" in reference_yaml:
            overrides["reference"] = reference_yaml

        config_path.write_text(create_default_config(overrides), encoding="utf-8")
        print(f"Created {config_path}")
        return True

    def _create_index_from_readme(
        self,
        guide: UserGuide | None,
        has_api_reference: bool,
        force_rebuild: bool = False,
        fallback_to_index: bool = False,
    ) -> None:
        """
        Write the licence, citation and package information pages, then the README homepage

        Use the project's index page or README, or generate a landing page from the package
        metadata. With `homepage: user_guide`, skip the README homepage unless
        `fallback_to_index` is `True`; the first user guide page supplies the homepage instead.

        Parameters
        ----------
        guide
            The discovered user guide, or `None` when it has no pages.
        has_api_reference
            Whether the site has an API reference, which a generated landing page links to.
        force_rebuild
            If `True`, always rebuild `index.qmd` even if it exists. Used by the build command to
            sync with source file changes.
        fallback_to_index
            If `True`, create `index.qmd` even with `homepage: user_guide`, because the project
            has no user guide pages to promote.

        Returns
        -------
        :
            `None`.
        """
        package_root = self.layout.package_root
        metadata = self._get_package_metadata()

        licence.write_page(
            self._config,
            package_root,
            self.build_dir,
            metadata.get("license", ""),
            self._page_authors,
            report=print,
        )
        citation.write_page(
            self._config,
            package_root,
            self.build_dir,
            metadata,
            self._page_authors,
            report=print,
        )
        package_info.write_page(self._config, self.build_dir, metadata, self._remote, report=print)

        # User guide mode promotes its first page unless no guide pages are available.
        if self._config.homepage == "user_guide" and not fallback_to_index:
            return  # pragma: no cover

        if (self.build_dir / "index.qmd").exists() and not force_rebuild:
            print("index.qmd already exists, skipping creation")
            return

        homepage_page.write_readme(
            self._config,
            self.layout,
            self.build_dir,
            metadata=metadata,
            package_name=self._detect_package_name(),
            pages=self._page_map(guide),
            page_authors=self._page_authors,
            has_api_reference=has_api_reference,
            has_user_guide=lambda: guide is not None,
            rebuild=force_rebuild,
            report=print,
        )

    def _add_api_reference_config(self, run: Run) -> None:
        """
        Add API reference configuration to _quarto.yml if not present.

        Adds sensible defaults for API reference generation with automatic
        package detection.  If no documentable exports are discovered (and no
        explicit `reference` config exists in great-docs.yml), the method
        skips API reference setup and records that this build has no API
        reference.

        Parameters
        ----------
        run
            The current build, which records whether the site has an API reference and
            whether the package's exports were discovered.
        """
        # Explicit opt-out via great-docs.yml
        if not self._config.reference_enabled:
            print("API reference disabled (reference: false), skipping")
            run.has_api_reference = False
            return

        # Python API reference only applies to projects with a Python component.
        # Non-Python projects (e.g. project_type: go) have no importable package
        # to introspect — skip rather than prompting for a package name.
        if not self._config.is_python_project:
            print("API reference skipped (non-Python project)")
            run.has_api_reference = False
            return

        config = quarto_yml.read(self.build_dir)

        # Check if API reference config already exists
        if "api-reference" in config:
            print("API reference configuration already exists, skipping")
            return

        # Detect package name (project name from pyproject.toml)
        package_name = self._detect_package_name()

        if not package_name:
            try:  # pragma: no cover
                response = input(
                    "\nCould not auto-detect package name. Enter package name for API reference (or press Enter to skip): "
                ).strip()
            except EOFError:  # pragma: no cover
                response = ""
            if not response:  # pragma: no cover
                print("Skipping API reference configuration")
                run.has_api_reference = False
                return
            package_name = response  # pragma: no cover

        print(f"Adding API reference configuration for package: {package_name}")

        # Detect actual module name (may differ from project name)
        # e.g., project 'py-yaml12' might have module 'yaml12'
        module_name = self._detect_module_name()
        if module_name:
            importable_name = module_name
            if module_name != package_name and module_name != self._normalize_package_name(
                package_name
            ):
                print(f"Detected module name: {module_name}")  # pragma: no cover
        else:
            # Fall back to normalizing package name (hyphens -> underscores)
            importable_name = self._normalize_package_name(package_name)

        # Check if this is a compiled extension
        if self._is_compiled_extension():  # pragma: no cover
            print("Detected compiled extension package (PyO3/Rust/Cython)")
            print("Note: The package must be installed (`pip install -e .` or `maturin develop`)")
            print("      for API reference generation.")

        # Try to auto-generate sections from discovered exports
        # Prioritizes explicit reference config from great-docs.yml over auto-discovery
        sections = self._create_api_sections_with_config(importable_name)

        # Mark that discovery was performed this build (so Step 2 can skip re-doing it)
        run.api_discovery_done = True

        # If no documentable exports were found, skip API reference entirely
        if not sections:
            print("No documentable exports found — skipping API reference")
            run.has_api_reference = False
            return

        reference_block.configure(self._config, config, importable_name, sections)

        # Write back to file
        quarto_yml.write(self.build_dir, config)

        print(f"Added API reference configuration to {quarto_yml.path(self.build_dir)}")

    def _update_quarto_config(self, run: Run) -> None:
        """
        Merge Great Docs settings into the build directory's `_quarto.yml`

        The file must already exist; build preparation creates it with the website
        project type. Add render scripts, theme settings, resources and site
        navigation while preserving unrelated configuration. Repeated calls after
        later build steps refresh the settings those steps affect. The settings
        come from `great-docs.yml`, package metadata and the project's GitHub repository.

        Parameters
        ----------
        run
            The build state. Its API reference outcome determines whether the reference
            switcher offers an API reference. The first call fetches the repository's
            star and fork counts and latest release into it, and later calls reuse them.

        Returns
        -------
        :

        Raises
        ------
        FileNotFoundError
            If the build directory has no `_quarto.yml`, or a header include file
            does not exist.
        KeyError
            If `_quarto.yml` lacks a `project` or `format.html` mapping. An empty file
            lacks both.
        """
        quarto_config = quarto_yml.read(self.build_dir)

        owner, repo_name, _ = self._get_github_repo_info()
        repo = GithubRepo(owner, repo_name) if owner and repo_name else None
        if run.facts is None:
            run.facts = Facts.make(self._config, repo, self._remote)

        assembly.assemble(
            quarto_config,
            self._config,
            self.layout,
            self.build_dir,
            repo=repo,
            facts=run.facts,
            identity=self._identity(),
            package_name=self._detect_package_name(),
            metadata=self._get_package_metadata(),
            has_api_reference=run.has_api_reference,
            report=print,
            warn=_print_warning,
        )

        quarto_yml.write(self.build_dir, quarto_config)

        print(f"Updated {quarto_yml.path(self.build_dir)} with great-docs configuration")

    def _auto_save_snapshot(self) -> None:
        """
        Save an API snapshot after a successful versioned build (Strategy C)

        Save to `.great-docs/snapshots/<version>.json`, using the exact tag at
        `HEAD` as `<version>`, or `dev` when there is no tag. Retry once if `git`
        cannot start. Fall back silently to `dev` if it still cannot start or
        exceeds the 5-second timeout. Other errors propagate.
        """
        from great_docs._api_diff import snapshot_from_griffe

        package_name = self._detect_package_name()
        if not package_name:
            return

        # griffe loads by importable module name, which can differ from the
        # PyPI project name.
        importable_name = self._resolve_importable_name(package_name)

        try:
            version = exact_tag(self.project_root) or "dev"
        except (OSError, subprocess.TimeoutExpired):
            version = "dev"

        snap = snapshot_from_griffe(importable_name, version=version)

        # Include CLI snapshot when CLI documentation is enabled
        if self._config.cli_enabled:
            try:
                found = cli_click.find_command(
                    importable_name,
                    cli_module=self._config.cli_module,
                    cli_name=self._config.cli_name,
                )
                if found is not None:
                    snap.cli_commands = cli_click.extract_snapshot(found.command)
            except USER_CODE_ERRORS:
                pass  # CLI snapshot is best-effort

        snap_dir = self.project_root / ".great-docs" / "snapshots"
        snap.save(snap_dir / f"{version}.json")

    # ══════════════════════════════════════════════════════════════════════════
    # SEO GENERATION METHODS
    # ══════════════════════════════════════════════════════════════════════════

    def _identity(self) -> Identity:
        """
        Resolve the site's name and addresses

        The site title in `_quarto.yml` changes during a build, so each call
        reads the identity afresh.

        Returns
        -------
        :
            The site's identity.
        """
        owner, repo, _ = self._get_github_repo_info()
        return Identity.make(self._config, self.build_dir, owner, repo, self._detect_package_name())

    def _prerender_term_player(self, log: "BuildLog") -> None:
        """
        Render the source directory's `.termshow` recordings for the `termshow` shortcode

        Parameters
        ----------
        log
            Build logger for warnings about failed recordings and a summary of
            successful renders, if any.
        """
        source_dir = self.layout.source_dir
        recordings = term_prerender.find_recordings(
            source_dir,
            self.layout.generated_dirs(),
            prune_non_doc=source_dir == self.layout.package_root,
        )
        done = term_prerender.render_recordings(
            recordings, source_dir, self.build_dir, report=log.warn
        )
        if done.count:
            log.detail(
                f"Pre-rendered {done.count} terminal recording(s) "
                f"({done.manifest_bytes / 1024:.0f} KB of player data)"
            )
            with quarto_yml.edit(self.build_dir, seed_website=True) as quarto_config:
                quarto_yml.apply(quarto_config, done.contribution)

    def uninstall(self) -> None:
        """
        Remove Great Docs configuration and generated build directories

        Delete `great-docs.yml` and the current `great-docs/` build directory.
        Also delete each historical `great-docs-<tag>/` directory that is not a
        symlink and contains the complete generated-file header. Preserve
        symlinks and historical directories without this header.

        ::: {.callout-note}
        In practice, you would normally use the `great-docs uninstall` CLI command
        rather than calling this method directly. See the
        [CLI reference](cli/uninstall.qmd) for details.
        :::

        Examples
        --------
        Uninstall great-docs from the current directory:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        docs.uninstall()
        ```

        Uninstall from a specific project directory:

        ```python
        docs = GreatDocs("/path/to/my/project")
        docs.uninstall()
        ```
        """
        print("Uninstalling great-docs from your project...")
        outputs.remove(self.layout, report=print)
        print("✅ Great-docs uninstalled successfully!")

    def _print_layout_notice(self) -> None:
        """
        Show the migration route for the selected root-layout documentation
        """
        from ._layout_migration.notice import layout_notice

        notice = layout_notice(self.layout)
        if notice is not None:
            import click

            click.echo(notice)

    def _step_prepare_build_directory(self, run: Run) -> Outcome:
        """
        Create the build directory and its initial Quarto project

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The step's result line.
        """
        self._prepare_build_directory(run)
        return "Ready"

    def _log_render_settings(self, log: "BuildLog") -> Outcome:
        """
        Show the freeze mode and the pre-render scripts that Quarto will use

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; the settings are detail lines of the previous step.
        """
        freeze_mode = self._config.freeze
        if freeze_mode is not None:
            log.detail(f"Freeze mode: {'auto' if freeze_mode == 'auto' else 'true'}")
        for script in self._config.pre_render or ():
            log.detail(f"Pre-render script: {script}")
        return None

    def _step_api_reference_config(self, run: Run, refresh: bool) -> Outcome:
        """
        Update the API reference configuration from the package's exports

        Skip the discovery when preparing the build directory already discovered the exports.

        Parameters
        ----------
        run
            The current build.
        refresh
            Whether to rediscover package exports.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not run.has_api_reference:
            return Skipped("no API reference")
        if not refresh:
            return "Using existing config"
        if run.api_discovery_done:
            print("API reference already configured in this build, skipping re-discovery")
        else:
            reference_block.refresh(
                self._config, self.build_dir, self._create_api_sections_with_config
            )
        return "API reference refreshed"

    def _step_llms_txt(self, run: Run) -> Outcome:
        """
        Write `llms.txt` and `llms-full.txt`

        `llms-full.txt` includes user guide pages and, when `cli.enabled` is set, Click
        command-line help.

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not llms_txt.is_planned(self.build_dir):
            return Skipped("no API reference")
        llms_txt.write_index(self.build_dir, self._get_package_metadata(), report=print)

        cli = None
        package_name = self._detect_package_name() if self._config.cli_enabled else None
        if package_name:
            # The importable module name can differ from the PyPI project name.
            try:
                cli = cli_click.discover(
                    self._resolve_importable_name(package_name),
                    self.layout.package_root,
                    cli_module=self._config.cli_module,
                    cli_name=self._config.cli_name,
                    display_name=package_name,
                    report=print,
                )
            except ImportError:
                # The CLI reference step warns about this failure. Keep writing without the CLI.
                pass
        llms_txt.write_full(
            self.build_dir,
            cli=cli,
            user_guide=run.user_guide,
            report=print,
        )
        return "Created llms.txt + llms-full.txt"

    def _step_skill_md(self) -> Outcome:
        """
        Write the agent skill files and the skills page

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.skill_enabled:
            return Skipped("disabled in config")
        SkillsWriter(
            self._config,
            self.layout,
            self.build_dir,
            self._detect_package_name(),
            self._get_package_metadata(),
        ).write()
        return "Created skill.md"

    def _warn_without_site_url(self, log: "BuildLog") -> Outcome:
        """
        Warn when the skills page has no site URL for its install instructions

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; the warning belongs to the previous step.
        """
        if not self._config.skill_enabled:
            return None
        urls = self._get_package_metadata().get("urls", {})
        has_site_url = bool(self._config.site_url or urls.get("Documentation", ""))
        if not has_site_url and quarto_yml.path(self.build_dir).exists():
            website = quarto_yml.read(self.build_dir).get("website", {})
            has_site_url = bool(website.get("site-url", ""))
        if not has_site_url:
            log.warn(
                "No site URL found — skills page will show <site-url> placeholders. "
                "Set site_url in great-docs.yml or add a Documentation URL to "
                "[project.urls] in pyproject.toml."
            )
        return None

    def _step_changelog(self) -> Outcome:
        """
        Write the changelog page from GitHub Releases and link it from the navbar

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.changelog_enabled:
            return Skipped("disabled in config")
        owner, repo, _base_url = self._get_github_repo_info()
        if not (owner and repo):
            return Skipped("no GitHub repo info")
        contribution = changelog.write_page(
            self._config, self.build_dir, GithubRepo(owner, repo), self._remote, report=print
        )
        if contribution is None:
            return "No releases found; skipped"
        with quarto_yml.edit(self.build_dir) as quarto_config:
            quarto_yml.apply(quarto_config, contribution)
        return "Changelog from GitHub Releases"

    def _step_cli_reference(self, run: Run) -> Outcome:
        """
        Write reference pages for the package's Click command-line interface

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.cli_enabled:
            return Skipped("CLI not enabled")
        if not run.package_name:
            return Skipped("no package detected")
        # The importable module name can differ from the project name.
        module = self._resolve_importable_name(run.package_name)
        cli_info = cli_click.discover(
            module,
            self.layout.package_root,
            cli_module=self._config.cli_module,
            cli_name=self._config.cli_name,
            display_name=run.package_name,
            report=print,
        )
        if not cli_info:
            return Skipped("no Click CLI found")
        return self._add_cli_reference(cli_info, "CLI")

    def _step_go_cli_reference(self) -> Outcome:
        """
        Write reference pages for the project's Go command-line interface

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.go_cli_enabled:
            return Skipped("Go CLI not enabled")
        from great_docs._cliref.go import detect_go_cli_project, introspect_cobra_cli

        project = detect_go_cli_project(self.layout.package_root)
        if not project:
            return Skipped("no Go CLI project detected")
        cli_info = introspect_cobra_cli(project)
        if not cli_info:
            return Skipped("Go CLI introspection failed (is 'go' on PATH?)")
        return self._add_cli_reference(cli_info, "Go CLI", f" ({project.binary_name})")

    def _step_rust_cli_reference(self) -> Outcome:
        """
        Write reference pages for the project's Rust command-line interface

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.rust_cli_enabled:
            return Skipped("Rust CLI not enabled")
        from great_docs._cliref.rust import detect_rust_cli_project, introspect_rust_cli

        project = detect_rust_cli_project(self.layout.package_root)
        if not project:
            return Skipped("no Rust CLI project detected")
        cli_info = introspect_rust_cli(project)
        if not cli_info:
            return Skipped("Rust CLI introspection failed (is 'cargo' on PATH?)")
        return self._add_cli_reference(cli_info, "Rust CLI", f" ({project.binary_names[0]})")

    def _add_cli_reference(self, cli_info: CliCommand, kind: str, suffix: str = "") -> Outcome:
        """
        Write CLI reference pages and add their sidebar and Reference navbar link

        Parameters
        ----------
        cli_info
            The command tree to document.
        kind
            The interface label in the result line, such as `"Go CLI"`.
        suffix
            Text appended to the result line, such as the binary's name.

        Returns
        -------
        :
            The step's result line.
        """
        cli_files = cli_render.write_pages(self._config, self.build_dir, cli_info, report=print)
        if not cli_files:
            return f"No {kind} pages generated"  # pragma: no cover
        with quarto_yml.edit(self.build_dir) as quarto_config:
            quarto_yml.apply(quarto_config, cli_render.contribution(self._config, cli_files))
        n_pages = cli_render.count_pages(cli_files)
        print(f"Updated sidebar with {n_pages} CLI reference page(s)")
        return f"{n_pages} {kind} reference page(s){suffix}"

    def _step_mcp_reference(self, run: Run) -> Outcome:
        """
        Write reference pages and a discovery manifest for the project's MCP server

        Parameters
        ----------
        run
            The current build, which supplies the package name.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.mcp_enabled:
            return Skipped("MCP not enabled")
        mcp_package = (
            self._resolve_importable_name(run.package_name)
            if run.package_name
            else self._detect_module_name()
        )
        from ._mcpref import build as mcp_build

        mcp_info = mcp_build.discover_server(self._config, mcp_package)
        if not mcp_info:
            return Skipped("no MCP server found")
        package_name = self._detect_package_name()
        owner, repo, _ = self._get_github_repo_info()
        repo_url = f"https://github.com/{owner}/{repo}" if owner and repo else None
        mcp_files = mcp_build.build_mcp_reference(
            self._config, mcp_info, self.build_dir, package_name, repo_url
        )
        if not mcp_files:
            return "No MCP pages generated"
        with quarto_yml.edit(self.build_dir) as quarto_config:
            quarto_yml.apply(quarto_config, mcp_build.contribution(self._config, mcp_files))
        print(f"Updated sidebar with {cli_render.count_pages(mcp_files)} MCP reference page(s)")
        return f"{len(mcp_info.get('tools', []))} MCP tool page(s) + manifest"

    def _step_user_guide(self, run: Run) -> Outcome:
        """
        Copy the user guide into the build directory and add its sidebar

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._process_user_guide(run.user_guide, run.has_api_reference):
            return Skipped("no user guide found")
        return "User Guide configured"

    def _step_sections(self, run: Run) -> Outcome:
        """
        Copy the configured custom sections into the build directory

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.sections:
            return Skipped("no sections configured")
        n_sections = self._process_sections(run.user_guide)
        if not n_sections:
            return "No sections to process"
        return f"{n_sections} section(s) processed"

    def _step_custom_pages(self, run: Run) -> Outcome:
        """
        Copy the custom pages into the build directory

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        n_pages = self._process_custom_pages(run.user_guide)
        if not n_pages:
            return Skipped("no custom pages")
        return f"{n_pages} custom page(s)"

    def _step_tags(self) -> Outcome:
        """
        Write the tags index, embed tag pill data and add the navbar link

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.tags_enabled:
            return Skipped("tags not enabled")
        output = tags.write(self._config, self.layout, report=print)
        if output is None:
            return Skipped("no tagged pages found")
        with quarto_yml.edit(self.build_dir) as quarto_config:
            if output.page_data is not None:
                inline_data.add(
                    quarto_config, "__GD_TAGS_DATA__", output.page_data, before="page-tags.js"
                )
            quarto_yml.apply(quarto_config, output.contribution)
        return "Tags processed"

    def _step_page_statuses(self) -> Outcome:
        """
        Write the status badge data for pages that declare a status

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.page_status_enabled:
            return Skipped("page status not enabled")
        if not page_status.process(self._config, self.layout, self.build_dir):
            return Skipped("no pages with status")
        return "Status badges processed"

    def _step_assets(self, run: Run) -> Outcome:
        """
        Copy the project's assets and complete the Quarto configuration

        Earlier steps copy resources such as user-guide images. Register those resources in
        the Quarto configuration even when the project has no assets directory.

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        assets_copied = self._copy_assets()
        self._update_quarto_config(run)
        if not assets_copied:
            return Skipped("no assets directory")
        return "Assets copied"

    def _step_api_reference(
        self, run: Run, log: "BuildLog"
    ) -> "tuple[Outcome, APIReference | None]":
        """
        Write the API reference pages and the inventory of documented objects

        When dynamic introspection fails, the step retries once with static analysis.

        Parameters
        ----------
        run
            The current build.
        log
            The build log.

        Returns
        -------
        :
            The result line or skip reason, and the API reference if one was generated.

        Raises
        ------
        StepError
            If the API reference cannot be generated.
        """
        if not run.has_api_reference:
            return Skipped("API reference disabled"), None

        from great_docs._apiref.api_reference import APIReference

        build_env = quarto.environment(self._config)
        for p in build_env.get("PYTHONPATH", "").split(os.pathsep):
            if p and p not in sys.path:
                sys.path.insert(0, p)  # pragma: no cover

        from great_docs._apiref.resolve import ObjectNotFoundError

        failures = (*USER_CODE_ERRORS, ObjectNotFoundError)
        quarto_yml_path = str(quarto_yml.path(self.build_dir))
        _, _, repo_url = self._get_github_repo_info()
        links = source_links(self._config, self.layout.package_root, repo_url, warn=_print_warning)
        try:
            ref = APIReference(quarto_yml_path, links)
            ref.build()
            return "API reference generated", ref
        except failures as e:
            if not self._config.dynamic:
                message = f"API reference build failed: {e}"
                raise StepError(message, detail=str(e)) from e
            log.warn(
                "Dynamic introspection failed for a resolved item, retrying with static analysis..."
            )
            log.detail(str(e))
            with quarto_yml.edit(self.build_dir) as quarto_config:
                if "api-reference" in quarto_config:
                    quarto_config["api-reference"]["dynamic"] = False
        try:
            ref = APIReference(quarto_yml_path, links)
            ref.build()
        except failures as e:
            raise StepError(f"API reference build failed: {e}") from e
        return "API reference generated (static analysis)", ref

    def _step_interlinks(self, log: "BuildLog", ref: "APIReference | None") -> Outcome:
        """
        Write the index that resolves cross-reference links to documented names

        Parameters
        ----------
        log
            The build log.
        ref
            The project's API reference, if it has one.

        Returns
        -------
        :
            The step's result line.
        """
        from great_docs._interlinks import AliasClaims, build_project_index

        index, notes = build_project_index(
            self.build_dir,
            self._config,
            self._detect_package_name() or "",
            AliasClaims.make(ref.items) if ref is not None else AliasClaims(),
        )
        for note in notes:
            log.detail(note)
        for alias, targets in sorted(index.dropped.items()):
            log.detail(
                f"'{alias}' is ambiguous ({', '.join(targets)}); references to it stay unlinked"
            )
        return f"Indexed {len(index.names)} name(s)"

    def _step_freeze_cache(self, run: Run) -> "tuple[Outcome, list[str]]":
        """
        Expand the pages' freeze shorthand and write their metadata

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason, and the pages whose freeze shorthand was expanded.
        """
        frozen_pages = prerender.expand_freeze_shorthand(self.build_dir)
        # Versioned builds write metadata after resolving each version's content. Watch mode
        # previews this directory without the per-version pipeline, so it needs metadata here.
        if not self._config.has_versions or run.watch:
            prerender.write_page_metadata(
                self.build_dir, self._config, self._default_description(), self._structured_data()
            )
        if frozen_pages:
            return f"Using {len(frozen_pages)} page(s) from the freeze cache", frozen_pages
        if self.layout.freeze_dir.is_dir():
            return "Freeze cache will be restored during render", frozen_pages
        return Skipped("no frozen pages"), frozen_pages

    def _expand_mock_cells(self, log: "BuildLog") -> Outcome:
        """
        Expand `source-code: mock` cells before Quarto reads the pages

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; the result is a detail line of the previous step.
        """
        from great_docs._website.mock_code import process_directory

        modified = process_directory(self.build_dir)
        if modified:
            log.detail(f"Expanded {len(modified)} mock-code cell(s): " + ", ".join(modified))
        return None

    def _render_d2_diagrams(self, log: "BuildLog") -> Outcome:
        """
        Render d2 diagrams as light and dark SVG files, which Quarto cannot generate

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; the result is a detail line of the previous step.
        """
        from great_docs._website.d2 import process_directory

        modified = process_directory(self.build_dir, cache_dir=self.layout.cache_dir / "d2")
        if modified:
            log.detail(f"Rendered d2 diagrams in {len(modified)} page(s): " + ", ".join(modified))
        return None

    def _share_sidebars(self, run: Run, log: "BuildLog") -> Outcome:
        """
        Render each long reference sidebar once for reuse across pages

        A versioned build shares the sidebars of each version in its own directory.

        Parameters
        ----------
        run
            The current build.
        log
            The build log.

        Returns
        -------
        :
            `None`; the result is a detail line of the previous step.
        """
        if run.watch or not self._config.has_versions:
            shared = shared_sidebar.prepare(self.build_dir)
            if shared:
                log.detail("Sharing rendered sidebar(s): " + ", ".join(shared))
        return None

    def _step_render(
        self,
        log: "BuildLog",
        jobs: int,
        last_timings: dict[str, float],
        last_startup: float | None,
    ) -> "tuple[quarto.RenderResult, dict[str, object] | None]":
        """
        Render a single-version site with Quarto and show its progress

        Retry a transient failure once in one process, including failures from parallel renders.

        Parameters
        ----------
        log
            The build log.
        jobs
            The number of Quarto processes to split the pages among.
        last_timings
            The last build's render time of each page, which guides the split.
        last_startup
            How long Quarto took to start in the last parallel build, which also guides the
            split; `None` when unknown.

        Returns
        -------
        :
            The successful render result, and how the parallel render went: its number of
            processes and groups and how long Quarto took to start. The second is `None`
            unless a parallel render produced the result.

        Raises
        ------
        StepError
            If Quarto fails to render the site.
        """
        import threading

        from great_docs._build import parallel_render

        env = quarto.environment(self._config)
        result = None
        render_stats: dict[str, object] | None = None
        if jobs > 1:
            # Experimental: split the pages among several Quarto processes
            bar = log.progress("Rendering pages", 1)
            bar_lock = threading.Lock()
            pages_started = [0]

            def on_start(pages: int, groups: int, workers: int) -> None:
                bar.total = max(pages, 1)
                log.detail(
                    f"Rendering {pages} pages in {groups} groups with {workers} Quarto processes"
                )

            def on_page(_page: str) -> None:
                with bar_lock:
                    pages_started[0] = min(pages_started[0] + 1, bar.total)
                    bar.update(pages_started[0])

            result = parallel_render.render(
                self.build_dir,
                env,
                jobs,
                last_timings,
                on_start=on_start,
                on_page=on_page,
                overhead=last_startup,
            )
            bar.finish()
            if result.fallback:
                log.detail(f"Rendering in one process: {result.fallback}")
                result = None
            else:
                for warning in result.warnings:
                    log.warn(warning)
                render_stats = {"processes": result.workers, "groups": result.targets}
                if result.startup is not None:
                    render_stats["startup_seconds"] = result.startup

        if result is None:
            result = self._render_with_progress(log, "Rendering pages", env)

        # Retry a transient failure in one process, including failures from parallel renders
        if result.returncode != 0 and quarto.is_transient_error(result.stderr):
            log.warn("Quarto hit a transient filesystem error — retrying render...")
            render_stats = None
            result = self._render_with_progress(log, "Rendering pages (retry)", env)

        if result.returncode != 0:
            raise StepError("Quarto render failed", detail=result.stderr)
        return result, render_stats

    def _render_with_progress(
        self, log: "BuildLog", label: str, env: dict[str, str]
    ) -> "quarto.RenderResult":
        """
        Render the site with Quarto in one process and show page progress

        Quarto's warnings appear when the bar reaches its last page; warnings reported later
        are dropped.

        Parameters
        ----------
        log
            The build log.
        label
            The progress bar's label.
        env
            The environment for Quarto.

        Returns
        -------
        :
            The render result, whether rendering succeeded or failed.
        """
        bar = log.progress(label, 1)
        warnings: list[str] = []
        finished = False

        def on_page(progress: quarto.Progress) -> None:
            nonlocal finished
            if finished:
                return
            if progress.total != bar.total:
                bar.total = progress.total
            bar.update(progress.current)
            if progress.current >= progress.total:
                finished = True
                bar.finish()
                for warning in warnings:
                    log.warn(warning)

        def on_warning(warning: str) -> None:
            if not finished:
                warnings.append(warning)

        result = quarto.render(self.build_dir, env, on_page=on_page, on_warning=on_warning)
        bar.finish()  # The final page may already have finished the bar
        return result

    def _step_render_versions(
        self, log: "BuildLog", version_tags: list[str] | None, latest_only: bool
    ) -> "tuple[Outcome, dict[str, Any]]":
        """
        Render the selected versions of a versioned site and assemble them

        Parameters
        ----------
        log
            The build log.
        version_tags
            The versions to render, or `None` for every version.
        latest_only
            Whether to render only the latest version.

        Returns
        -------
        :
            The result line and the outcome of the versioned build.

        Raises
        ------
        StepError
            If every version fails to render.
        """
        from great_docs._versions.build import run_versioned_build
        from great_docs._versions.model import get_latest_version, parse_versions_config

        versions = parse_versions_config(self._config.versions)
        if latest_only:
            latest = get_latest_version(versions)
            latest_tag = latest.tag if latest else versions[0].tag
            targets = [v for v in versions if v.tag == latest_tag]
        elif version_tags:
            targets = [v for v in versions if v.tag in set(version_tags)]
        else:
            targets = list(versions)

        n_versions = len(targets)
        log.detail(
            f"Multi-version build: {'1 version' if n_versions == 1 else f'{n_versions} version(s)'}"
        )

        bars = log.multi_progress([f"v{v.label}" for v in targets])

        def on_progress(slot: int, current: int, total: int) -> None:
            bars.set_total(slot, total)
            bars.update(slot, current)

        # Uncached tag snapshots use the working tree's documented set. Cache the
        # result so it is resolved at most once per project name per build.
        @cache
        def documented_symbols(package_name: str) -> list[str]:
            return documented.symbol_names(
                self._config,
                importable_name=self._resolve_importable_name(package_name),
                search_paths=self._griffe_search_paths(),
                create_sections=self._create_api_sections_with_config,
            )

        result = run_versioned_build(
            source_dir=self.build_dir,
            project_root=self.project_root,
            versions_config=self._config.versions,
            quarto_env=quarto.environment(self._config),
            version_tags=version_tags,
            latest_only=latest_only,
            progress_callback=on_progress,
            on_renders_done=bars.finish,
            badge_expiry_raw=self._config["new_is_old"],
            config=self._config,
            layout=self.layout,
            default_description=self._default_description(),
            structured_data=self._structured_data(),
            documented_symbols=documented_symbols,
        )

        for warning in result.get("warnings", []):
            log.warn(warning)

        n_built = len(result["versions_built"])
        if result["success"]:
            return f"{n_built} version(s) rendered", result
        for error in result["errors"]:
            log.error_detail(error)
        if not n_built:
            raise StepError("All version builds failed")
        return f"{n_built} version(s) rendered ({len(result['errors'])} failed)", result

    def _assemble_separate_site(self) -> Outcome:
        """
        Copy the rendered site to a site directory outside the build directory

        Returns
        -------
        :
            `None`; the step has no result line.
        """
        if self.layout.site_dir != self.build_dir / "_site":
            from ._versions.build import assemble_site

            assemble_site(self.build_dir, [], "", self.layout.site_dir, layout=self.layout)
        return None

    def _step_seo_files(self) -> Outcome:
        """
        Write `sitemap.xml` and `robots.txt` for the rendered site

        Returns
        -------
        :
            The step's result line.
        """
        base_url = self._identity().base_url
        site_files.write(self.layout.site_dir, self._config, base_url, report=print)
        return "sitemap.xml + robots.txt"

    def _log_build_timing(
        self,
        log: "BuildLog",
        page_timings: list[dict[str, object]] | None = None,
        timings_by_version: dict[str, list[dict[str, object]]] | None = None,
        render: dict[str, object] | None = None,
    ) -> Outcome:
        """
        Write `build-timings.json` to the site

        Parameters
        ----------
        log
            The build log.
        page_timings
            The render time of each page of a single-version site.
        timings_by_version
            The render time of each page, by version.
        render
            How a parallel render of a single-version site went, which the next parallel
            build plans with.

        Returns
        -------
        :
            `None`; the result is a detail line of the previous step.
        """
        path = timings.write(
            self.layout,
            page_timings=page_timings,
            timings_by_version=timings_by_version,
            render=render,
        )
        if path:
            log.detail(f"Wrote {path.name}")
        return None

    def _log_freeze_cache_saved(self, log: "BuildLog") -> Outcome:
        """
        Save the rendered pages' freeze cache for later builds

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; the result is a detail line of the previous step.
        """
        n_frozen = freeze.save(self.layout)
        if n_frozen is not None:
            log.detail(f"Saved freeze cache ({n_frozen} files)")
        return None

    def _save_api_snapshot(self, log: "BuildLog") -> Outcome:
        """
        Save the current API snapshot for version comparisons

        Parameters
        ----------
        log
            The build log.

        Returns
        -------
        :
            `None`; handled exceptions become warnings attributed to the previous listed step.
        """
        try:
            self._auto_save_snapshot()
        except USER_CODE_ERRORS as e:
            log.warn(f"Snapshot auto-save failed: {e}")
        return None

    def _record_site_ownership(self) -> Outcome:
        """
        Record the files of a site directory outside the build directory

        Returns
        -------
        :
            `None`; the step has no result line.
        """
        if self.layout.site_dir != self.build_dir / "_site":
            record_site_ownership(self.layout.site_dir)
        return None

    def _preparation_steps(self, run: Run, log: "BuildLog", refresh: bool = True) -> list[Step]:
        """
        Return the build's preparation steps in execution order

        These steps write the Quarto project before rendering. Each step resolves its method
        when it runs, so tests can replace instance methods after the list is created.

        Parameters
        ----------
        run
            The current build.
        log
            The build log that the steps write to.
        refresh
            Whether to rediscover the package's exports for the API reference.

        Returns
        -------
        :
            The steps in the order they run.
        """
        # Results shared between preparation steps
        ref: APIReference | None = None
        frozen_pages: list[str] = []

        def generate_api_reference() -> Outcome:
            nonlocal ref
            outcome, ref = self._step_api_reference(run, log)
            return outcome

        def prepare_freeze_cache() -> Outcome:
            outcome, frozen_pages[:] = self._step_freeze_cache(run)
            return outcome

        def list_frozen_pages() -> Outcome:
            for page in frozen_pages:
                log.detail(f"  - {page}")
            return None

        return [
            Step("Prepare build directory", lambda: self._step_prepare_build_directory(run)),
            Step(
                "Show render settings",
                lambda: self._log_render_settings(log),
                quiet=False,
                listed=False,
            ),
            Step(
                "Configure API reference",
                lambda: self._step_api_reference_config(run, refresh),
                user_code=True,
            ),
            Step(
                "Generate llms.txt / llms-full.txt",
                lambda: self._step_llms_txt(run),
                warn=Warn(
                    USER_CODE_ERRORS, "Error generating llms.txt", "llms.txt generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Generate SKILL.md",
                lambda: self._step_skill_md(),
                warn=Warn(
                    USER_CODE_ERRORS, "Error generating SKILL.md", "SKILL.md generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Check the site URL",
                lambda: self._warn_without_site_url(log),
                user_code=True,
                quiet=False,
                listed=False,
            ),
            Step(
                "Generate changelog",
                lambda: self._step_changelog(),
                remote_content=True,
            ),
            Step(
                "Generate CLI reference",
                lambda: self._step_cli_reference(run),
                warn=Warn(
                    USER_CODE_ERRORS, "Error generating CLI docs", "CLI generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Generate Go CLI reference",
                lambda: self._step_go_cli_reference(),
                warn=Warn(
                    (OSError,), "Error generating Go CLI docs", "Go CLI generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Generate Rust CLI reference",
                lambda: self._step_rust_cli_reference(),
                warn=Warn(
                    (OSError,), "Error generating Rust CLI docs", "Rust CLI generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Generate MCP server reference",
                lambda: self._step_mcp_reference(run),
                warn=Warn(
                    USER_CODE_ERRORS, "Error generating MCP docs", "MCP generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Process User Guide",
                lambda: self._step_user_guide(run),
                fails_on=(ValueError,),
                user_code=True,
            ),
            Step(
                "Process custom sections",
                lambda: self._step_sections(run),
                fails_on=(ValueError,),
            ),
            Step(
                "Process custom pages",
                lambda: self._step_custom_pages(run),
                fails_on=(ValueError,),
            ),
            Step(
                "Process page tags",
                lambda: self._step_tags(),
            ),
            Step(
                "Process page status badges",
                lambda: self._step_page_statuses(),
            ),
            Step(
                "Copy assets",
                lambda: self._step_assets(run),
                fails_on=(ValueError, FileNotFoundError),
            ),
            Step("Generate API reference", generate_api_reference, user_code=True),
            Step(
                "Build interlinks index",
                lambda: self._step_interlinks(log, ref),
                quiet=False,
            ),
            Step("Prepare freeze cache", prepare_freeze_cache, quiet=False),
            Step("List frozen pages", list_frozen_pages, quiet=False, listed=False),
            Step(
                "Expand mock-code cells",
                lambda: self._expand_mock_cells(log),
                quiet=False,
                listed=False,
            ),
            Step(
                "Render d2 diagrams",
                lambda: self._render_d2_diagrams(log),
                user_code=True,
                quiet=False,
                listed=False,
            ),
            Step(
                "Pre-render terminal recordings",
                lambda: self._prerender_term_player(log),
                quiet=False,
                listed=False,
            ),
            Step(
                "Share sidebars",
                lambda: self._share_sidebars(run, log),
                quiet=False,
                listed=False,
            ),
        ]

    def build(
        self,
        watch: bool = False,
        refresh: bool = True,
        version_tags: list[str] | None = None,
        latest_only: bool = False,
        jobs: int | str | None = None,
    ) -> None:
        """
        Build the documentation site.

        Generates API reference pages followed by `quarto render`. By default, re-discovers package
        exports and updates the API reference configuration before building.

        ::: {.callout-note}
        In practice, you would normally use the `great-docs build` CLI command rather
        than calling this method directly. See the
        [CLI reference](cli/build.qmd) for details.
        :::

        Parameters
        ----------
        watch
            If `True`, watch for changes and rebuild automatically.
        refresh
            If `True` (default), re-discover package exports and update API reference config before
            building. Set to False for faster rebuilds when your package API hasn't changed.
        version_tags
            If provided, only build these specific version tags (for multi-version sites). Ignored
            when no `versions:` config is present.
        latest_only
            If `True`, build only the latest version (skip historical versions). Ignored when no
            `versions:` config is present.
        jobs
            Experimental. Render the pages of a single-version site with this many Quarto processes
            at once. Use a number, or `"auto"` to choose one from the CPU count. The default (`None`)
            reads the `GREAT_DOCS_RENDER_JOBS` environment variable and otherwise renders in one
            process. Sites that can't be split safely are rendered in one process anyway. Ignored
            for multi-version sites and in watch mode.

        Raises
        ------
        FileNotFoundError
            If the project has no `great-docs.yml`.
        BuildError
            If the build fails and leaves no usable site: Quarto is missing or too old, a
            configured reference name is missing from the installed package, the API reference
            cannot be generated, or Quarto fails to render the site. The failure has already
            been reported in the build log or on standard error.

        Examples
        --------
        Build the documentation (with API refresh):

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        docs.build()
        ```

        Build with watch mode:

        ```python
        docs.build(watch=True)
        ```

        Quick rebuild without API refresh:

        ```python
        docs.build(refresh=False)
        ```
        """
        # Require an explicit config file; init must have been run first
        outputs.validate(self._config, self.layout)
        config_path = self.layout.config_path
        if not config_path.exists():
            raise FileNotFoundError(
                "great-docs.yml not found. Run 'great-docs init' first to "
                "generate a configuration file."
            )

        try:
            quarto.ensure_installed()
        except BuildError as e:
            print(f"Error: {e}", file=sys.stderr)
            raise

        from great_docs._build import parallel_render
        from great_docs._build.log import BuildLog, estimate_build_time

        # Settle the render process count up front so a bad value fails fast, and read the last
        # build's page timings and Quarto start-up time before anything clears them (they guide
        # how pages are split)
        render_jobs = parallel_render.resolve_jobs(jobs)
        last_timings: dict[str, float] = {}
        last_startup: float | None = None
        if render_jobs > 1:
            timing_files = (
                self.layout.site_dir / "build-timings.json",
                self.build_dir / "_site" / "build-timings.json",
            )
            last_timings = parallel_render.read_timings(*timing_files)
            last_startup = parallel_render.read_startup(*timing_files)

        # --- Gather metadata for the build header -------------------------
        package_name = self._detect_package_name() or ""
        package_version = ""
        package_location = ""
        if package_name:
            try:
                from importlib.metadata import version as _pkg_version

                package_version = _pkg_version(package_name)
            except Exception:
                pass
            # Show the location Griffe will actually use for introspection
            # (prioritizes project root / src layout over sys.path)
            _normalized_pkg = package_name.replace("-", "_")
            for _sp in self._griffe_search_paths():
                _candidate = Path(_sp) / _normalized_pkg
                if _candidate.is_dir() and (_candidate / "__init__.py").exists():
                    package_location = str(_candidate)
                    break
            if not package_location:
                try:
                    import importlib.util

                    _spec = importlib.util.find_spec(_normalized_pkg)
                    if _spec and _spec.origin:
                        package_location = str(Path(_spec.origin).parent)
                except Exception:
                    pass
            # For --from-repo builds (temp clone dirs), show the git remote URL
            # instead of the opaque temp path
            if package_location:
                try:
                    import tempfile

                    _git_remote = subprocess.run(
                        ["git", "config", "--get", "remote.origin.url"],
                        cwd=str(self.project_root),
                        capture_output=True,
                        **TEXT_MODE_KWARGS,
                    )
                    if _git_remote.returncode == 0 and _git_remote.stdout.strip():
                        _remote_url = _git_remote.stdout.strip()
                        # Check if the package lives inside a temp clone directory
                        _tmp_prefixes = ("/tmp/", "/var/folders/", tempfile.gettempdir())
                        if any(package_location.startswith(p) for p in _tmp_prefixes):
                            package_location = _remote_url
                except Exception:
                    pass

        # Count total pages for time estimate (API items from config)
        n_api_items = 0
        n_total_pages = 0
        n_code_cells = 0
        # The previous build's inventory is the best count available before
        # this build resolves the package.
        import zlib

        from great_docs._interlinks.sphinx_inventory import INVENTORY_FILENAME, decode

        inventory_path = self.build_dir / INVENTORY_FILENAME
        if inventory_path.exists():
            try:
                n_api_items = len(decode(inventory_path.read_bytes()).entries)
            except (OSError, ValueError, zlib.error):
                pass

        # Cheap page & code-cell scan for the time estimate
        try:
            _qmd_exts = ("*.qmd", "*.md")
            _page_dirs: list[Path] = []

            # User guide pages
            # Build preparation has already reported directory warnings
            ug_dir = user_guide.find_dir(self._config, self.layout, report=lambda _: None)
            if ug_dir and ug_dir.is_dir():
                _page_dirs.append(ug_dir)

            # Custom section directories
            for sec in self._config.sections:
                sec_dir_name = sec.get("dir", "")
                if sec_dir_name:
                    sec_dir = self.layout.package_root / sec_dir_name
                    if sec_dir.is_dir():
                        _page_dirs.append(sec_dir)

            for d in _page_dirs:
                for ext in _qmd_exts:
                    for p in d.rglob(ext):
                        n_total_pages += 1
                        try:
                            text = p.read_text(encoding="utf-8", errors="ignore")
                            n_code_cells += text.count("```{python}")
                        except OSError:
                            pass

            # Reference pages (≈ n_api_items, one page per item)
            n_total_pages += n_api_items

            # Fixed pages: homepage, changelog, citation, etc.
            n_total_pages += 3

            # CLI pages (rough estimate if enabled)
            if self._config.cli_enabled:
                n_total_pages += 10
        except Exception:
            pass  # never let estimation crash the build

        est_seconds = estimate_build_time(
            n_api_items=n_api_items,
            n_total_pages=n_total_pages,
            n_code_cells=n_code_cells,
        )

        # Values that several steps read; a new build starts from a new `Run`
        run = Run(package_name=package_name, watch=watch)
        log = BuildLog(
            package_name=package_name,
            package_version=package_version,
            package_location=package_location,
            estimated_seconds=est_seconds,
        )

        # Render timings shared with the timings step
        render_timings: dict[str, Any] = {}

        def render_site() -> Outcome:
            result, render_timings["render"] = self._step_render(
                log, render_jobs, last_timings, last_startup
            )
            render_timings["page_timings"] = result.page_timings
            return "Site rendered"

        def render_versions() -> Outcome:
            outcome, result = self._step_render_versions(log, version_tags, latest_only)
            render_timings["timings_by_version"] = result.get("timings_by_version")
            return outcome

        steps = self._preparation_steps(run, log, refresh)
        if watch:
            render = Step("Build site with Quarto", lambda: "Starting watch mode...")
        elif self._config.has_versions:
            render = Step("Build site with Quarto", render_versions, user_code=True, quiet=False)
        else:
            render = Step("Build site with Quarto", render_site, quiet=False)
        steps.append(render)
        if not self._config.has_versions:
            steps.append(
                Step(
                    "Assemble the site",
                    lambda: self._assemble_separate_site(),
                    quiet=False,
                    listed=False,
                )
            )
        steps += [
            Step(
                "Generate SEO files",
                lambda: self._step_seo_files(),
                warn=Warn((OSError,), "Error generating SEO files", "SEO files had issues"),
            ),
            Step(
                "Write build timings",
                lambda: self._log_build_timing(log, **render_timings),
                quiet=False,
                listed=False,
            ),
            Step(
                "Save the freeze cache",
                lambda: self._log_freeze_cache_saved(log),
                quiet=False,
                listed=False,
            ),
        ]
        if self._config.has_versions:
            steps.append(
                Step(
                    "Save an API snapshot",
                    lambda: self._save_api_snapshot(log),
                    user_code=True,
                    quiet=False,
                    listed=False,
                )
            )
        steps.append(
            Step(
                "Record site ownership",
                lambda: self._record_site_ownership(),
                quiet=False,
                listed=False,
            )
        )

        log.total_steps = count_listed(steps)
        log.header()

        if watch:
            # Watch mode starts `quarto preview` after the render step and omits the finishing
            # steps, though the header still counts them.
            run_steps(steps[: steps.index(render) + 1], log, self.build_dir)
            log.footer(watch_mode=True)
            self._print_layout_notice()
            preview_env = quarto.environment(self._config)
            preview_env[shared_sidebar.PREVIEW_ENV] = "1"
            subprocess.run(
                ["quarto", "preview", "--no-browser"], cwd=self.build_dir, env=preview_env
            )
            return

        run_steps(steps, log, self.build_dir)
        site_path = self.layout.site_dir / "index.html"
        log.footer(site_path=str(site_path if site_path.exists() else self.layout.site_dir))
        self._print_layout_notice()

    def preview(self, port: int = 3000, *, open_path: str = "", open_browser: bool = True) -> None:
        """
        Preview the documentation site locally.

        Starts a local HTTP server and opens the built site in the default browser. If the site
        hasn't been built yet, it will be built first. Use `great-docs build` to rebuild the site if
        you've made changes.

        ::: {.callout-note}
        In practice, you would normally use the `great-docs preview` CLI command rather than calling
        this method directly. See the [CLI reference](cli/preview.qmd) for details.
        :::

        Parameters
        ----------
        port
            The port number for the local HTTP server (default `3000`).
        open_path
            A page to open instead of the home page, relative to the site, such as
            `reference/index.html`. If the page is missing, the home page opens instead.
        open_browser
            Whether to open the page in the default browser.

        Raises
        ------
        OSError
            If the site has no `index.html` after the build, or the server cannot listen on
            `port`.

        Examples
        --------
        Preview the documentation:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        docs.preview()
        ```
        """
        print("Previewing documentation...")

        site_path = self.layout.site_dir
        if not (site_path / "index.html").exists():
            print("Site not found, building first...")
            self.build()
        else:
            self._print_layout_notice()
        serve.site(site_path, port, open_path=open_path, open_browser=open_browser, report=print)

    def check_links(
        self,
        include_source: bool = True,
        include_docs: bool = True,
        timeout: float = 10.0,
        ignore_patterns: list[str] | None = None,
        verbose: bool = False,
    ) -> dict:
        """
        Check source code and documentation for broken links

        ::: {.callout-note}
        In practice, you would normally use the `great-docs check-links` CLI command rather than
        calling this method directly. See the [CLI reference](cli/check_links.qmd) for details.
        :::

        This method scans Python source files and documentation files (`.qmd`, `.md`) for URLs and
        checks their HTTP status. It reports broken links (404s) and warns about redirects.

        The following content is automatically excluded from link checking:

        - **Python comments**: URLs in lines starting with `#`
        - **Code blocks**: URLs inside fenced code blocks (````` ... `````)
        - **Inline code**: URLs inside backticks (`` `...` ``)
        - **Marked URLs**: URLs followed by `{.gd-no-link}` in `.qmd`/`.md` files

        For documentation, the checker scans the authored pages that the build publishes: the
        homepage source and the pages of the user guide, the sections and the custom page
        directories, plus `README.md` at the package root. Generated pages are not checked.

        In `.qmd` files, you can exclude specific URLs from checking by adding `{.gd-no-link}`
        immediately after the URL:

            Visit http://example.com{.gd-no-link} for an example.
            Also works with inline code: `http://example.com`{.gd-no-link}

        Parameters
        ----------
        include_source
            If `True`, scan Python source files in the package directory for URLs. Default is
            `True`.
        include_docs
            If `True`, scan documentation files (`.qmd`, `.md`) for URLs. Default is `True`.
        timeout
            Timeout in seconds for each HTTP request. Default is `10.0`.
        ignore_patterns
            List of URL patterns (strings or regex) to ignore. URLs matching any pattern will be
            skipped. Default is `None`.
        verbose
            If `True`, print detailed progress information. Default is `False`.

        Returns
        -------
        :
            A dictionary containing:

            - `total`: total number of unique links checked
            - `ok`: list of links that returned 2xx status
            - `redirects`: list of dicts with `url`, `status`, `location` for 3xx responses
            - `broken`: list of dicts with `url`, `status`, `error` for 4xx/5xx or errors
            - `skipped`: list of URLs that were skipped (matched ignore patterns)
            - `by_file`: dict mapping file paths to lists of links found in each file

        Examples
        --------
        Check all links in a project:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        results = docs.check_links()

        print(f"Checked {results['total']} links")
        print(f"Broken: {len(results['broken'])}")
        print(f"Redirects: {len(results['redirects'])}")
        ```

        Check only documentation files with custom timeout:

        ```python
        results = docs.check_links(
            include_source=False,
            timeout=5.0,
            ignore_patterns=["localhost", "127.0.0.1", "example.com"]
        )
        ```
        """
        files: list[Path] = []
        if include_source and (package_name := self._detect_package_name()):
            module = self._resolve_importable_name(package_name)
            files += proofread.find_modules(self.layout, module)
        if include_docs:
            files += proofread.find_pages(self._config, self.layout, report=_print_warning)

        return links.check(
            files,
            self.project_root,
            timeout=timeout,
            ignore_patterns=ignore_patterns or (),
            report=print if verbose else lambda _line: None,
        )

    def proofread(
        self,
        include_docs: bool = True,
        include_docstrings: bool = False,
        custom_words: list[str] | None = None,
        dialect: str = "us",
        ignore_rules: list[str] | None = None,
        only_rules: list[str] | None = None,
        strict: bool = False,
        verbose: bool = False,
    ) -> list[CheckedFile]:
        """
        Check spelling and grammar in documentation pages and Python docstrings with Harper

        ::: {.callout-note}
        In practice, you would normally use the `great-docs proofread` CLI command rather than
        calling this method directly. See the [CLI reference](cli/proofread.qmd) for details.
        :::

        Harper checks the published authored `.qmd` and `.md` pages: the homepage source, user
        guide, sections and custom page directories, plus `README.md` at the package root.
        Checks use the same defaults as `great-docs proofread`: a built-in dictionary of
        technical terms and ignored rules for technical writing. Front matter and fenced code
        blocks are excluded from `.qmd` checks.

        Parameters
        ----------
        include_docs
            If `True`, check the documentation pages. Default is `True`.
        include_docstrings
            If `True`, check docstrings in Python files under the package's importable module
            directory. Skip these files if no package is detected. Default is `False`.
        custom_words
            Additional accepted words, such as project-specific terms and library names.
            Default is `None`.
        dialect
            English dialect: `"us"`, `"uk"`, `"au"`, `"in"` or `"ca"`. Default is `"us"`.
        ignore_rules
            Harper rule names to skip, such as `["SentenceCapitalization"]`, in addition to
            any default exclusions enabled by `strict=False`. Default is `None`.
        only_rules
            Harper rule names to run exclusively (e.g., `["SpellCheck"]`). Default is `None`.
        strict
            If `True`, disable the built-in dictionary and default rule exclusions. Explicit
            `custom_words`, `only_rules` and `ignore_rules` still apply. Default is `False`.
        verbose
            If `True`, print progress as files are checked. Default is `False`.

        Returns
        -------
        :
            A list of checked files, each with a `file` path, a sequence of `issues` and an
            `error` message if checking failed, or `None` if it succeeded. Each issue has
            `line`, `column`, `kind`, `rule`, `message`, `matched_text` and `suggestions`.
            For `.qmd` pages, `file` is relative to the project root and issue line numbers
            refer to the original page.

        Raises
        ------
        RuntimeError
            If `harper-cli` is missing or a batch of `.md` or `.py` file checks raises
            `HarperError`. A missing executable stops the whole run, including runs with only
            `.qmd` pages. An `OSError`, `UnicodeDecodeError` or `HarperError` on a `.qmd` page
            is returned as that page's `error` instead.

        Examples
        --------
        Check all documentation:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        results = docs.proofread()

        for file_result in results:
            for issue in file_result.issues:
                print(f"{file_result.file}:{issue.line} - {issue.message}")
        ```

        Accept project-specific words:

        ```python
        results = docs.proofread(custom_words=["griffe", "quartodoc", "navbar"])
        ```

        Check only spelling:

        ```python
        results = docs.proofread(only_rules=["SpellCheck"])
        ```
        """
        from ._checks.harper import HarperError, HarperNotFoundError

        files: list[Path] = []
        if include_docs:
            files = proofread.find_pages(self._config, self.layout, report=_print_warning)
        if include_docstrings and (package_name := self._detect_package_name()):
            module = self._resolve_importable_name(package_name)
            files += proofread.find_modules(self.layout, module)

        options = proofread.Options(
            dialect=dialect,
            words=custom_words or (),
            only_rules=only_rules or (),
            ignore_rules=ignore_rules or (),
            builtin_dictionary=not strict,
            default_ignores=not strict,
        )
        try:
            return proofread.check(
                files,
                self.project_root,
                options,
                report=print if verbose else lambda _line: None,
            )
        except HarperNotFoundError as e:
            raise RuntimeError(str(e)) from e
        except HarperError as e:
            raise RuntimeError(f"Harper error: {e}") from e
