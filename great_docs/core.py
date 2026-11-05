import json
import os
import shutil
import subprocess
import sys
from functools import partial
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from . import _marimo
from ._build import content, finish, outputs, quarto, render, serve
from ._build.facts import Facts, source_links
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
from ._content import publish, user_guide
from ._content.user_guide import UserGuide
from ._install import update_gitignore, write_initial_config
from ._layout import Layout
from ._manifest import Manifest
from ._project import Project
from ._reference import block as reference_block
from ._reference import sections as reference_sections
from ._reference.exports import Exports
from ._remote import HttpRemote, Remote
from ._subprocess import TEXT_MODE_KWARGS
from ._term_player import prerender as term_prerender
from ._utils import GITIGNORE_CONTENT
from ._website import (
    assembly,
    changelog,
    inline_data,
    page_dates,
    page_status,
    prerender,
    quarto_yml,
    scripts,
    tags,
)
from ._website.ai_agents import llms_txt
from ._website.ai_agents.skills import SkillsWriter
from ._website.homepage import page as homepage_page
from ._website.identity import Identity
from ._website.navigation import shared_sidebar
from ._website.project_pages import citation, licence, package_info
from ._website.seo import description as seo_description
from ._website.seo.structured_data import StructuredData
from .config import Config

if TYPE_CHECKING:
    from ._apiref.api_reference import APIReference
    from ._build.log import BuildLog


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

        self._page_authors = page_dates.site_authors(
            self._config,
            self.layout.source_dir,
            self._identity(Project.make(self._config, self.layout)).base_url,
        )

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
            has_repository=run.project.github is not None,
        )

        # Create .gitignore for the great-docs directory
        gitignore_path = self.build_dir / ".gitignore"
        gitignore_path.write_text(GITIGNORE_CONTENT, encoding="utf-8")

        # The user guide step copies the guide later, stripping numeric prefixes for clean URLs

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
        self._create_index_from_readme(
            run.project, run.user_guide, run.has_api_reference, force_rebuild=True
        )

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

        project = Project.make(self._config, self.layout)
        write_initial_config(
            self._config,
            self.layout,
            project,
            Exports(self._config, project),
            force=force,
            report=print,
        )

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

    def _default_description(self, manifest: Manifest) -> str | None:
        """
        Resolve the site's default search description

        Parameters
        ----------
        manifest
            The project's declared metadata, used when no search description is configured.

        Returns
        -------
        :
            The description as plain text, or `None` when neither
            `seo.default_description` nor the package description is set.
        """
        return seo_description.default_description(self._config, manifest["description"])

    def _structured_data(self, project: Project) -> StructuredData | None:
        """
        Describe the package as JSON-LD for the homepage and reference pages

        Parameters
        ----------
        project
            The documented project.

        Returns
        -------
        :
            The structured data, or `None` when it is disabled.
        """
        identity = self._identity(project)
        return StructuredData.make(self._config, project.manifest, identity.name, identity.base_url)

    def _create_index_from_readme(
        self,
        project: Project,
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
        project
            The project's name and metadata for the homepage and package information pages.
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
        metadata = project.manifest

        licence.write_page(
            self._config,
            package_root,
            self.build_dir,
            metadata["license"],
            self._page_authors,
            report=print,
        )
        citation.write_page(
            self._config, package_root, self.build_dir, self._page_authors, report=print
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
            package_name=project.name,
            pages=content.page_map(self._config, self.layout, guide),
            page_authors=self._page_authors,
            has_api_reference=has_api_reference,
            has_user_guide=lambda: guide is not None,
            rebuild=force_rebuild,
            report=print,
        )

    def _add_api_reference_config(self, run: Run) -> None:
        """
        Add API reference defaults to `_quarto.yml` unless already configured

        Warn and skip the API reference when no package name is detected. Also skip it
        when no documentable exports are found, unless `great-docs.yml` has an explicit
        `reference` configuration. Record either skip in the current build's state.

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

        # Non-Python projects have no importable Python package to introspect.
        if not self._config.is_python_project:
            print("API reference skipped (non-Python project)")
            run.has_api_reference = False
            return

        config = quarto_yml.read(self.build_dir)

        # Check if API reference config already exists
        if "api-reference" in config:
            print("API reference configuration already exists, skipping")
            return

        project = run.project
        if not project.name or not (importable_name := project.importable_name):
            _print_warning("Could not detect the package name; skipping the API reference")
            run.has_api_reference = False
            return

        print(f"Adding API reference configuration for package: {project.name}")

        # Report module names that differ even after hyphens are replaced with underscores.
        if importable_name not in (project.name, project.name.replace("-", "_")):
            print(f"Detected module name: {importable_name}")

        if project.compiled_extension:
            print("Detected compiled extension package (PyO3/Rust/Cython)")
            print("Note: The package must be installed (`pip install -e .` or `maturin develop`)")
            print("      for API reference generation.")

        # Try to auto-generate sections from discovered exports
        # Prioritizes explicit reference config from great-docs.yml over auto-discovery
        sections = run.exports.sections(importable_name)

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

        repo = run.project.github
        if run.facts is None:
            run.facts = Facts.make(self._config, repo, self._remote)

        assembly.assemble(
            quarto_config,
            self._config,
            self.layout,
            self.build_dir,
            repo=repo,
            facts=run.facts,
            identity=self._identity(run.project),
            package_name=run.project.name,
            metadata=run.project.manifest,
            has_api_reference=run.has_api_reference,
            report=print,
            warn=_print_warning,
        )

        quarto_yml.write(self.build_dir, quarto_config)

        print(f"Updated {quarto_yml.path(self.build_dir)} with great-docs configuration")

    def _identity(self, project: Project) -> Identity:
        """
        Resolve the site's name and addresses

        The site title in `_quarto.yml` changes during a build, so each call
        reads the identity afresh.

        Parameters
        ----------
        project
            The project's name and GitHub repository, used as fallbacks for the site's identity.

        Returns
        -------
        :
            The site's identity.
        """
        github = project.github
        return Identity.make(
            self._config,
            self.build_dir,
            github.owner if github else None,
            github.name if github else None,
            project.name,
        )

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
            reference_block.refresh(self._config, self.build_dir, run.exports.sections)
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
        llms_txt.write_index(self.build_dir, run.project.manifest, report=print)

        cli = None
        package_name = run.project.name if self._config.cli_enabled else None
        module = run.project.importable_name
        if package_name and module:
            try:
                cli = cli_click.discover(
                    module,
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

    def _step_skill_md(self, run: Run) -> Outcome:
        """
        Write the agent skill files and the skills page

        Parameters
        ----------
        run
            The current build.

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
            run.project.name,
            run.project.manifest,
        ).write()
        return "Created skill.md"

    def _warn_without_site_url(self, run: Run, log: "BuildLog") -> Outcome:
        """
        Warn when the skills page has no site URL for its install instructions

        Parameters
        ----------
        run
            The current build.
        log
            The build log.

        Returns
        -------
        :
            `None`; the warning belongs to the previous step.
        """
        if not self._config.skill_enabled:
            return None
        urls = run.project.manifest["urls"]
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

    def _step_changelog(self, run: Run) -> Outcome:
        """
        Write the changelog page from GitHub Releases and link it from the navbar

        Parameters
        ----------
        run
            The current build.

        Returns
        -------
        :
            The result line or skip reason.
        """
        if not self._config.changelog_enabled:
            return Skipped("disabled in config")
        repo = run.project.github
        if repo is None:
            return Skipped("no GitHub repo info")
        contribution = changelog.write_page(
            self._config, self.build_dir, repo, self._remote, report=print
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
        package_name = run.project.name
        module = run.project.importable_name
        if not package_name or not module:
            return Skipped("no package detected")
        cli_info = cli_click.discover(
            module,
            self.layout.package_root,
            cli_module=self._config.cli_module,
            cli_name=self._config.cli_name,
            display_name=package_name,
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
        mcp_package = run.project.importable_name
        from ._mcpref import build as mcp_build

        mcp_info = mcp_build.discover_server(self._config, mcp_package)
        if not mcp_info:
            return Skipped("no MCP server found")
        repo_url = run.project.github.url if run.project.github else None
        mcp_files = mcp_build.build_mcp_reference(
            self._config, mcp_info, self.build_dir, run.project.name, repo_url
        )
        if not mcp_files:
            return "No MCP pages generated"
        with quarto_yml.edit(self.build_dir) as quarto_config:
            quarto_yml.apply(quarto_config, mcp_build.contribution(self._config, mcp_files))
        print(f"Updated sidebar with {cli_render.count_pages(mcp_files)} MCP reference page(s)")
        return f"{len(mcp_info.get('tools', []))} MCP tool page(s) + manifest"

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
        repo_url = run.project.github.url if run.project.github else None
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

    def _step_interlinks(self, run: Run, log: "BuildLog", ref: "APIReference | None") -> Outcome:
        """
        Write the index that resolves cross-reference links to documented names

        Parameters
        ----------
        run
            The current build.
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
            run.project.name or "",
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
                self.build_dir,
                self._config,
                self._default_description(run.project.manifest),
                self._structured_data(run.project),
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

    def _preparation_steps(self, run: Run, log: "BuildLog", refresh: bool = True) -> list[Step]:
        """
        Return the build's preparation steps in execution order

        These steps write the Quarto project before rendering. Resolve methods and step
        functions when each step runs so tests can replace them after this list is created.

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

        def write_fallback_homepage() -> None:
            self._create_index_from_readme(
                run.project,
                run.user_guide,
                run.has_api_reference,
                force_rebuild=True,
                fallback_to_index=True,
            )

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
                lambda: self._step_skill_md(run),
                warn=Warn(
                    USER_CODE_ERRORS, "Error generating SKILL.md", "SKILL.md generation had issues"
                ),
                user_code=True,
            ),
            Step(
                "Check the site URL",
                lambda: self._warn_without_site_url(run, log),
                user_code=True,
                quiet=False,
                listed=False,
            ),
            Step(
                "Generate changelog",
                lambda: self._step_changelog(run),
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
                lambda: content.user_guide(
                    run,
                    self._config,
                    self.layout,
                    page_authors=self._page_authors,
                    write_fallback_homepage=write_fallback_homepage,
                ),
                fails_on=(ValueError,),
                user_code=True,
            ),
            Step(
                "Process custom sections",
                lambda: content.sections(
                    run, self._config, self.layout, page_authors=self._page_authors
                ),
                fails_on=(ValueError,),
            ),
            Step(
                "Process custom pages",
                # Read the site title when the step runs; earlier steps can change it.
                lambda: content.custom_pages(
                    run,
                    self._config,
                    self.layout,
                    page_authors=self._page_authors,
                    identity=self._identity(run.project),
                    structured_data=self._structured_data(run.project),
                    default_description=self._default_description(run.project.manifest),
                ),
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
                lambda: content.assets(
                    self.layout, update_quarto_config=lambda: self._update_quarto_config(run)
                ),
                fails_on=(ValueError, FileNotFoundError),
            ),
            Step("Generate API reference", generate_api_reference, user_code=True),
            Step(
                "Build interlinks index",
                lambda: self._step_interlinks(run, log, ref),
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

        # Share project facts within this build; reread packaging files for each new build.
        run = Run.make(self._config, self.layout, watch=watch)

        # --- Gather metadata for the build header -------------------------
        package_name = run.project.name or ""
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
            for _sp in run.project.search_paths():
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

        log = BuildLog(
            package_name=package_name,
            package_version=package_version,
            package_location=package_location,
            estimated_seconds=est_seconds,
        )

        # Render timings shared with the timings step
        render_timings: dict[str, Any] = {}

        def render_site() -> Outcome:
            result, render_timings["render"] = render.site(
                self._config, self.layout, log, render_jobs, last_timings, last_startup
            )
            render_timings["page_timings"] = result.page_timings
            return "Site rendered"

        def render_versions() -> Outcome:
            # Structured data names the site from `_quarto.yml`, which earlier steps edit
            outcome, result = render.versions(
                run,
                self._config,
                self.layout,
                log,
                version_tags,
                latest_only,
                default_description=self._default_description(run.project.manifest),
                structured_data=self._structured_data(run.project),
            )
            render_timings["timings_by_version"] = result.get("timings_by_version")
            return outcome

        steps = self._preparation_steps(run, log, refresh)
        if watch:
            render_step = Step("Build site with Quarto", lambda: "Starting watch mode...")
        elif self._config.has_versions:
            render_step = Step(
                "Build site with Quarto", render_versions, user_code=True, quiet=False
            )
        else:
            render_step = Step("Build site with Quarto", render_site, quiet=False)
        steps.append(render_step)
        if not self._config.has_versions:
            steps.append(
                Step(
                    "Assemble the site",
                    lambda: render.assemble_site(self.layout),
                    quiet=False,
                    listed=False,
                )
            )
        steps += [
            Step(
                "Generate SEO files",
                lambda: finish.seo_files(
                    self._config, self.layout, self._identity(run.project).base_url
                ),
                warn=Warn((OSError,), "Error generating SEO files", "SEO files had issues"),
            ),
            Step(
                "Write build timings",
                lambda: finish.write_timings(self.layout, log, **render_timings),
                quiet=False,
                listed=False,
            ),
            Step(
                "Save the freeze cache",
                lambda: finish.save_freeze_cache(self.layout, log),
                quiet=False,
                listed=False,
            ),
        ]
        if self._config.has_versions:
            steps.append(
                Step(
                    "Save an API snapshot",
                    lambda: finish.save_api_snapshot(run, self._config, self.layout, log),
                    user_code=True,
                    quiet=False,
                    listed=False,
                )
            )
        steps.append(
            Step(
                "Record site ownership",
                lambda: finish.record_site_ownership(self.layout),
                quiet=False,
                listed=False,
            )
        )

        log.total_steps = count_listed(steps)
        log.header()

        if watch:
            # Watch mode starts `quarto preview` after the render step and omits the finishing
            # steps, though the header still counts them.
            run_steps(steps[: steps.index(render_step) + 1], log, self.build_dir)
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
        if include_source:
            project = Project.make(self._config, self.layout)
            if project.name and project.importable_name:
                files += proofread.find_modules(self.layout, project.importable_name)
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
        if include_docstrings:
            project = Project.make(self._config, self.layout)
            if project.name and project.importable_name:
                files += proofread.find_modules(self.layout, project.importable_name)

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
