import os
from importlib import resources
from pathlib import Path

from ._build import finish, outputs, pipeline, serve
from ._build.quarto import QuartoNotFoundError as QuartoNotFoundError
from ._build.quarto import QuartoVersionError as QuartoVersionError
from ._build.steps import print_warning
from ._checks import links, proofread
from ._checks.proofread import CheckedFile
from ._install import update_gitignore, write_initial_config
from ._layout import Layout
from ._project import Project
from ._reference.exports import Exports
from ._remote import HttpRemote, Remote
from .config import Config


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
            If `True`, serve the site with `quarto preview` and rebuild it when the
            documentation sources or `great-docs.yml` change.
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
        pipeline.run(
            self._config,
            self.layout,
            remote=self._remote,
            watch=watch,
            refresh=refresh,
            version_tags=version_tags,
            latest_only=latest_only,
            jobs=jobs,
        )

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
            finish.print_layout_notice(self.layout)
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
            files += proofread.find_pages(self._config, self.layout, report=print_warning)

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
            files = proofread.find_pages(self._config, self.layout, report=print_warning)
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
