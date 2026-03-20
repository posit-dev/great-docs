import json
import os
import re
import shutil
from importlib import resources
from pathlib import Path

from yaml12 import format_yaml, parse_yaml, read_yaml, write_yaml

from .config import Config


class GreatDocs:
    """
    GreatDocs class for creating beautiful API documentation sites.

    This class provides methods to install assets and configure
    Quarto projects with the great-docs styling and functionality.
    """

    def __init__(self, project_path: str | None = None):
        """
        Initialize GreatDocs instance.

        Parameters
        ----------
        project_path
            Path to the project root directory. Defaults to current directory.
        """
        self.project_root = Path(project_path or os.getcwd())
        # Build directory is always 'great-docs' - created during build, not init
        self.docs_dir = Path("great-docs")
        self.project_path = self.project_root / self.docs_dir
        try:
            # Python 3.9+
            self.package_path = Path(resources.files("great_docs"))
        except AttributeError:  # pragma: no cover
            # Fallback for older Python versions
            import importlib_resources  # type: ignore[import-not-found]

            self.package_path = Path(importlib_resources.files("great_docs"))
        self.assets_path = self.package_path / "assets"

        # Load configuration from great-docs.yml
        self._config = Config(self._find_package_root())

        # Whether API reference was successfully configured (set during build)
        self._has_api_reference = True

        # Set environment variables needed by the qrenderer
        _, _, url = self._get_github_repo_info()
        if url:
            os.environ["GITHUB_REPO_URL"] = str(url)
        os.environ["GIT_REF"] = self._detect_git_ref()

    def _prepare_build_directory(self) -> None:
        """
        Prepare the great-docs/ build directory with all necessary assets.

        This method creates the great-docs/ directory (if it doesn't exist) and
        copies all CSS, JavaScript, and other assets needed for the build.
        It also creates the _quarto.yml configuration and other necessary files.

        The great-docs/ directory is ephemeral and should not be committed to
        version control. It will be recreated on each build.
        """
        print(f"Preparing build directory: {self.project_path.relative_to(self.project_root)}/")

        # Clean any existing build directory to avoid stale artifacts
        if self.project_path.exists():
            shutil.rmtree(self.project_path)

        # Create the great-docs directory
        self.project_path.mkdir(parents=True, exist_ok=True)

        # Create necessary subdirectories
        scripts_dir = self.project_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)

        reference_dir = self.project_path / "reference"
        reference_dir.mkdir(exist_ok=True)

        # Copy post-render script
        post_render_src = self.assets_path / "post-render.py"
        post_render_dst = scripts_dir / "post-render.py"
        shutil.copy2(post_render_src, post_render_dst)

        # Copy qrenderer assets
        renderer_src = self.assets_path / "_renderer.py"
        if renderer_src.exists():
            shutil.copy2(renderer_src, self.project_path / "_renderer.py")

        # Copy SCSS theme file (contains all site styling)
        scss_src = self.assets_path / "great-docs.scss"
        shutil.copy2(scss_src, self.project_path / "great-docs.scss")

        # Copy JavaScript files
        js_files = [
            "github-widget.js",
            "sidebar-filter.js",
            "sidebar-wrap.js",
            "reference-switcher.js",
            "dark-mode-toggle.js",
            "theme-init.js",
        ]
        if self._config.markdown_pages_widget:
            js_files.append("copy-page.js")
        if self._config.announcement:
            js_files.append("announcement-banner.js")
        if self._config.navbar_style:
            js_files.append("navbar-style.js")
        if self._config.content_style is not None:
            js_files.append("content-style.js")
        for js_file in js_files:
            js_src = self.assets_path / js_file
            if js_src.exists():
                js_dst = self.project_path / js_file
                shutil.copy2(js_src, js_dst)

        # Create .gitignore for the great-docs directory
        gitignore_content = """# Great Docs build directory
# This directory is ephemeral and regenerated on each build
# Do not commit this directory to version control
*
!.gitignore
"""
        gitignore_path = self.project_path / ".gitignore"
        gitignore_path.write_text(gitignore_content, encoding="utf-8")

        # Create index.qmd from README.md or user_guide files
        self._create_index_from_readme(force_rebuild=True)

        # Note: User guide files are copied by _process_user_guide() during build
        # which handles stripping numeric prefixes for clean URLs

        # Create _quarto.yml configuration
        self._update_quarto_config()

        # Write options JSON for the post-render script
        gd_options = {
            "markdown_pages": self._config.markdown_pages,
        }
        gd_options_path = self.project_path / "_gd_options.json"
        with open(gd_options_path, "w") as f:
            json.dump(gd_options, f)

        # Add API reference configuration
        # (auto-skips if no documentable exports are found)
        self._add_api_reference_config()
        if self._has_api_reference:
            self._update_sidebar_from_sections()
            self._update_reference_index_frontmatter()

    def _copy_user_guide_files(self) -> None:
        """
        Copy user guide files from project root to build directory.

        Resolves the source directory using `_find_user_guide_dir()`.
        When `user_guide` config is a list (explicit ordering), only the directory
        is resolved from conventional locations.

        Copies `.qmd` and `.md` files to `great-docs/user-guide/` directory.
        """
        configured_path = self._config.user_guide_dir  # str or None (ignores list)

        if configured_path is not None:
            source_user_guide = self.project_root / configured_path
        else:
            source_user_guide = self.project_root / "user_guide"
            if not source_user_guide.exists():
                # Also check for 'user-guide' with hyphen
                source_user_guide = self.project_root / "user-guide"

        if source_user_guide.exists() and source_user_guide.is_dir():
            dest_user_guide = self.project_path / "user-guide"
            dest_user_guide.mkdir(exist_ok=True)

            # Copy all .qmd and .md files
            for pattern in ["*.qmd", "*.md"]:
                for file_path in source_user_guide.glob(pattern):
                    shutil.copy2(file_path, dest_user_guide / file_path.name)

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
        source_assets = self.project_root / "assets"

        if not source_assets.exists() or not source_assets.is_dir():
            return False

        dest_assets = self.project_path / "assets"

        # Remove existing assets directory to ensure clean copy
        if dest_assets.exists():
            shutil.rmtree(dest_assets)

        # Copy entire assets directory
        shutil.copytree(source_assets, dest_assets)

        # Count files for reporting
        file_count = sum(1 for _ in dest_assets.rglob("*") if _.is_file())
        print(f"\n📦 Copied {file_count} asset file(s) to great-docs/assets/")

        return True

    def install(self, force: bool = False) -> None:
        """
        Initialize great-docs in your project.

        This method creates a great-docs.yml configuration file in the project root
        with discovered exports and sensible defaults. The docs directory and assets
        will be created later during the build process.

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

        # Generate great-docs.yml with discovered exports
        self._generate_initial_config(force=force)

        # Reload configuration after generating it
        self._config = Config(self._find_package_root())

        # Update project root .gitignore to exclude great-docs/
        self._update_project_gitignore(force=force)

        print("\n✅ Great Docs initialization complete!")
        print("\nNext steps:")
        print("1. Review great-docs.yml to customize your API reference structure")
        print("   (Reorder items, add sections, set 'members: false' to exclude methods)")
        print("2. Run `great-docs build` to generate and build your documentation site")
        print("3. Run `great-docs preview` to view the site locally")
        print("\nOther helpful commands:")
        print("  great-docs scan           # Preview API organization")
        print("  great-docs build --watch  # Watch for changes and rebuild")

    def _update_project_gitignore(self, force: bool = False) -> None:
        """
        Update project root .gitignore to exclude the great-docs/ build directory.

        Prompts the user for permission before modifying .gitignore, unless force=True.
        This ensures the ephemeral build directory is not committed to version control.

        Parameters
        ----------
        force
            If True, skip the prompt and automatically update .gitignore.
        """
        gitignore_path = self.project_root / ".gitignore"

        # Entry to add
        entry = "# Great Docs build directory (ephemeral, do not commit)\ngreat-docs/\n"

        # Check if already present
        if gitignore_path.exists():
            with open(gitignore_path, "r", encoding="utf-8") as f:
                content = f.read()

            if "great-docs/" in content:
                # Already present, no need to ask
                return

        # If force=True, skip the prompt
        if force:
            if gitignore_path.exists():
                # Append to existing .gitignore
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write("\n" + entry)
                print("✅ Updated .gitignore to exclude great-docs/ directory")
            else:
                # Create new .gitignore
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(entry)
                print("✅ Created .gitignore to exclude great-docs/ directory")
            return

        # Ask for permission in interactive mode
        print("\nThe great-docs/ directory is ephemeral and should not be committed to git.")
        response = (
            input("Add 'great-docs/' to .gitignore? [Y/n]: ").strip().lower()
        )  # pragma: no cover

        if response in ("", "y", "yes"):  # pragma: no cover
            if gitignore_path.exists():
                # Append to existing .gitignore
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write("\n" + entry)
                print("✅ Updated .gitignore to exclude great-docs/ directory")
            else:
                # Create new .gitignore
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(entry)
                print("✅ Created .gitignore to exclude great-docs/ directory")
        else:
            print(
                "⚠️  Skipped .gitignore update. Remember to exclude great-docs/ from version control."
            )

    def _detect_package_name(self) -> str | None:
        """
        Detect the Python package name from project structure.

        Returns
        -------
        str | None
            The detected package name, or None if not found.
        """
        # Look for pyproject.toml
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            import tomllib

            with open(pyproject_path, "rb") as f:
                try:
                    data = tomllib.load(f)
                    name = data.get("project", {}).get("name")
                    if name:
                        return name
                except Exception:
                    pass

        # Look for setup.cfg
        setup_cfg = self.project_root / "setup.cfg"
        if setup_cfg.exists():
            try:
                import configparser

                cfg = configparser.ConfigParser()
                cfg.read(setup_cfg, encoding="utf-8")
                name = cfg.get("metadata", "name", fallback=None)
                if name:
                    return name
            except Exception:  # pragma: no cover
                pass

        # Look for setup.py
        setup_py = self.project_root / "setup.py"
        if setup_py.exists():
            with open(setup_py, "r") as f:
                content = f.read()
                # Simple regex to find name="..." in setup()
                import re

                match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)

        # Look for a single Python package directory
        potential_packages = [
            d
            for d in self.project_root.iterdir()
            if d.is_dir() and (d / "__init__.py").exists() and not d.name.startswith(".")
        ]
        if len(potential_packages) == 1:
            return potential_packages[0].name

        return None

    def _detect_logo(self) -> dict[str, str] | None:
        """
        Scan conventional paths for logo files.

        Looks for logo files in the project root using common naming conventions. If a matching file
        is found, returns a normalized logo dict. Also checks for dark-mode variants automatically.

        Returns
        -------
        dict | None
            A dict with `light` (and optionally `dark`) keys pointing to paths relative to the
            project root, or `None` if no logo file was found.
        """
        package_root = self._find_package_root()
        package_name = self._detect_package_name() or ""
        importable = package_name.replace("-", "_")

        # Candidate paths for the primary (light) logo, in priority order
        candidates = [
            "logo.svg",
            "logo.png",
            "assets/logo.svg",
            "assets/logo.png",
            "docs/assets/logo.svg",
            "docs/assets/logo.png",
        ]
        # Package-name variants
        if package_name:
            candidates.extend(
                [
                    f"{package_name}_logo.svg",
                    f"{package_name}_logo.png",
                    f"assets/{package_name}_logo.svg",
                    f"assets/{package_name}_logo.png",
                ]
            )
        if importable and importable != package_name:
            candidates.extend(
                [
                    f"{importable}_logo.svg",
                    f"{importable}_logo.png",
                    f"assets/{importable}_logo.svg",
                    f"assets/{importable}_logo.png",
                ]
            )
        # Also try logo-light naming convention
        candidates.extend(
            [
                "assets/logo-light.svg",
                "assets/logo-light.png",
            ]
        )

        found_path: str | None = None
        for candidate in candidates:
            full = package_root / candidate
            if full.is_file():
                found_path = candidate
                break

        if found_path is None:
            return None

        # Build the result dict
        result: dict[str, str] = {"light": found_path}

        # Check for a dark variant alongside the found file
        light_p = Path(found_path)
        stem = light_p.stem.replace("-light", "")
        parent = str(light_p.parent) if str(light_p.parent) != "." else ""

        for ext in [light_p.suffix]:  # same extension first
            dark_name = f"{stem}-dark{ext}"
            dark_candidate = f"{parent}/{dark_name}" if parent else dark_name
            if (package_root / dark_candidate).is_file():
                result["dark"] = dark_candidate
                break

        # If no separate dark variant, use the same file for both
        if "dark" not in result:
            result["dark"] = found_path

        return result

    def _detect_hero_logo(self) -> dict[str, str] | None:
        """
        Scan conventional paths for hero-specific logo files.

        Looks for ``logo-hero.*`` files in the project root and ``assets/``
        directory.  If a light/dark pair is found (``logo-hero-light.*`` and
        ``logo-hero-dark.*``), both are returned.

        Returns
        -------
        dict | None
            A dict with ``light`` (and optionally ``dark``) keys, or ``None``
            if no hero logo file was found.
        """
        package_root = self._find_package_root()

        # Candidate paths in priority order
        candidates = [
            "logo-hero.svg",
            "logo-hero.png",
            "assets/logo-hero.svg",
            "assets/logo-hero.png",
            "logo-hero-light.svg",
            "logo-hero-light.png",
            "assets/logo-hero-light.svg",
            "assets/logo-hero-light.png",
        ]

        found_path: str | None = None
        for candidate in candidates:
            if (package_root / candidate).is_file():
                found_path = candidate
                break

        if found_path is None:
            return None

        result: dict[str, str] = {"light": found_path}

        # Check for a dark variant alongside the found file
        light_p = Path(found_path)
        stem = light_p.stem.replace("-light", "")
        parent = str(light_p.parent) if str(light_p.parent) != "." else ""

        dark_name = f"{stem}-dark{light_p.suffix}"
        dark_candidate = f"{parent}/{dark_name}" if parent else dark_name
        if (package_root / dark_candidate).is_file():
            result["dark"] = dark_candidate

        # If no separate dark variant, use the same file for both
        if "dark" not in result:
            result["dark"] = found_path

        return result

    def _generate_favicons(self, logo_src: Path, dest_dir: Path) -> dict[str, str]:
        """
        Generate favicon files from a source logo image.

        Produces raster favicons from SVG or PNG sources using cairosvg and Pillow. For SVG sources,
        cairosvg rasterizes to PNG first, then Pillow creates the multi-size ICO and
        apple-touch-icon. For PNG sources, Pillow resizes directly.

        Parameters
        ----------
        logo_src
            Absolute path to the source logo file (SVG or PNG).
        dest_dir
            Directory to write generated favicon files into.

        Returns
        -------
        dict[str, str]
            Mapping of purpose to filename (relative to dest_dir). Possible keys: `"icon"` (primary
            favicon), `"icon-svg"`, `"icon-32"`, `"icon-16"`, `"apple-touch-icon"`. Only includes
            files that were successfully generated.
        """
        import io

        import cairosvg
        from PIL import Image

        result: dict[str, str] = {}
        suffix = logo_src.suffix.lower()

        print(f"Favicon: generating from {logo_src.name}")

        # --- SVG source ---
        if suffix == ".svg":
            # Always copy the SVG as favicon.svg (modern browsers support it)
            shutil.copy2(logo_src, dest_dir / "favicon.svg")
            result["icon-svg"] = "favicon.svg"
            result["icon"] = "favicon.svg"

            # Rasterize SVG → PNG preserving aspect ratio, then resize
            png_data = cairosvg.svg2png(url=str(logo_src), scale=4)
            raw = Image.open(io.BytesIO(png_data))

            # Fit into a square canvas with transparent padding
            master = self._fit_to_square(raw, 512)

            # Generate standard favicon sizes
            for size, name in [
                (16, "favicon-16x16.png"),
                (32, "favicon-32x32.png"),
                (180, "apple-touch-icon.png"),
            ]:
                resized = master.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(dest_dir / name, "PNG")
                if size == 16:
                    result["icon-16"] = name
                elif size == 32:
                    result["icon-32"] = name
                elif size == 180:
                    result["apple-touch-icon"] = name

            # Generate ICO with multiple sizes embedded
            master.save(
                dest_dir / "favicon.ico",
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48)],
            )
            result["icon"] = "favicon.ico"

        # --- PNG source ---
        elif suffix == ".png":
            raw = Image.open(logo_src)
            # Fit into a square canvas with transparent padding
            master = self._fit_to_square(raw, max(raw.size))

            for size, name in [
                (16, "favicon-16x16.png"),
                (32, "favicon-32x32.png"),
                (180, "apple-touch-icon.png"),
            ]:
                resized = master.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(dest_dir / name, "PNG")
                if size == 16:
                    result["icon-16"] = name
                elif size == 32:
                    result["icon-32"] = name
                elif size == 180:
                    result["apple-touch-icon"] = name

            # Generate ICO with multiple sizes embedded
            master.save(
                dest_dir / "favicon.ico",
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48)],
            )
            result["icon"] = "favicon.ico"
            result["icon-32"] = "favicon-32x32.png"

        if result:
            files = ", ".join(dict.fromkeys(result.values()))
            print(f"Favicon: created {files}")

        return result

    @staticmethod
    def _fit_to_square(img: "Image.Image", size: int) -> "Image.Image":
        """Fit an image into a square canvas, preserving aspect ratio.

        The image is scaled to fit within ``size x size``, then centered
        on a transparent canvas of exactly ``size x size``.
        """
        from PIL import Image

        img = img.convert("RGBA")
        img.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        canvas.paste(img, (x, y), img)
        return canvas

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

    def _detect_module_name(self) -> str | None:
        """
        Detect the actual importable module name for the package.

        The module name may differ from the project name (e.g., project 'py-yaml12'
        might have module 'yaml12' or 'pyyaml12'). This method tries to find the
        actual module directory or stub file.

        Priority:
        1. Explicit 'module' setting in great-docs.yml
        2. .pyi stub files (for compiled extensions)
        3. pyproject.toml configuration ([tool.maturin], [tool.setuptools], etc.)
        4. Auto-discovery via _find_package_init

        Returns
        -------
        str | None
            The detected module name, or None if not found.
        """
        # First, check for explicit module name in great-docs.yml
        if self._config.module:
            return self._config.module

        package_root = self._find_package_root()

        # Check for .pyi stub files (common for PyO3/Rust/compiled extensions)
        # These indicate the actual module name for compiled packages
        pyi_files = list(package_root.glob("*.pyi"))
        if pyi_files:
            # Use the first .pyi file found (excluding __init__.pyi)
            for pyi_file in pyi_files:
                if pyi_file.stem != "__init__":
                    return pyi_file.stem

        # Check pyproject.toml for explicit package configuration
        pyproject_path = package_root / "pyproject.toml"
        if pyproject_path.exists():
            import tomllib

            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)

                # Check [tool.maturin] for PyO3/Rust projects
                maturin = data.get("tool", {}).get("maturin", {})
                if maturin:
                    # maturin projects: module name is often in module-name or derived from Cargo.toml
                    module_name = maturin.get("module-name")
                    if module_name:
                        return module_name

                # Check [tool.setuptools.packages] for explicit package list
                setuptools = data.get("tool", {}).get("setuptools", {})
                if "packages" in setuptools:
                    packages = setuptools["packages"]
                    if packages and isinstance(packages, list):
                        # Return the first package (main package)
                        return packages[0].split("/")[-1]

                # Check [tool.setuptools.packages.find]
                find_config = setuptools.get("packages", {})
                if isinstance(find_config, dict) and "find" in find_config:
                    where = find_config["find"].get("where", ["."])
                    if isinstance(where, str):
                        where = [where]
                    for base_dir in where:
                        base_path = package_root / base_dir
                        if base_path.exists():
                            for item in base_path.iterdir():
                                if item.is_dir() and (item / "__init__.py").exists():
                                    if not item.name.startswith((".", "_", "test")):
                                        return item.name

                # Check [tool.hatch.build.targets.wheel.packages]
                hatch_packages = (
                    data.get("tool", {})
                    .get("hatch", {})
                    .get("build", {})
                    .get("targets", {})
                    .get("wheel", {})
                    .get("packages", [])
                )
                if hatch_packages:
                    pkg = hatch_packages[0]
                    return pkg.split("/")[-1]

            except Exception:
                pass

        # Try to find via _find_package_init
        project_name = self._detect_package_name()
        if project_name:
            init_file = self._find_package_init(project_name)
            if init_file:
                return init_file.parent.name

        return None

    def _is_compiled_extension(self) -> bool:
        """
        Check if this is a compiled extension package (PyO3, Cython, etc.).

        Returns
        -------
        bool
            True if this appears to be a compiled extension package.
        """
        package_root = self._find_package_root()

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

    def _find_package_root(self) -> Path:
        """
        Find the actual package root directory (where pyproject.toml or setup.py exists).

        When the docs directory is the current directory, project_root might point to
        the docs dir rather than the package root. This method searches upward to find
        the actual package root.

        Returns
        -------
        Path
            The package root directory
        """
        current = self.project_root

        # Search upward from current directory
        for _ in range(5):  # Limit search to 5 levels up
            if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
                return current
            parent = current.parent
            if parent == current:  # pragma: no cover — reached filesystem root
                break
            current = parent

        # Fallback to project_root if we can't find it
        return self.project_root

    def _get_quarto_env(self) -> dict[str, str]:
        """
        Get environment variables for running Quarto commands.

        Sets QUARTO_PYTHON to ensure Quarto uses the correct Python environment
        where the package and its dependencies are installed. This is essential
        for notebook execution and API introspection.

        Also sets PYTHONPATH to include the package root directory, ensuring that
        griffe can find the package even if it's not installed.

        The method looks for Python in the following order:
        1. Virtual environment in the project root (.venv/bin/python or .venv/Scripts/python.exe)
        2. The currently running Python interpreter

        Returns
        -------
        dict[str, str]
            Environment variables dictionary with QUARTO_PYTHON and PYTHONPATH set.
        """
        import sys

        env = os.environ.copy()
        package_root = self._find_package_root()

        # Look for a virtual environment in the project
        venv_paths = [
            package_root / ".venv" / "bin" / "python",  # Unix
            package_root / ".venv" / "Scripts" / "python.exe",  # Windows
            package_root / "venv" / "bin" / "python",  # Alternative name
            package_root / "venv" / "Scripts" / "python.exe",  # Windows alternative
        ]

        python_path = None
        for venv_python in venv_paths:
            if venv_python.exists():
                python_path = str(venv_python)
                break

        # Fallback to the currently running Python
        if python_path is None:
            python_path = sys.executable

        env["QUARTO_PYTHON"] = python_path

        # Add package root to PYTHONPATH so griffe can find the package
        # even if it's not installed (e.g., during development)
        pythonpath_dirs = [str(package_root)]

        # Also add src/ directory if it exists (common src-layout)
        src_dir = package_root / "src"
        if src_dir.exists() and src_dir.is_dir():
            pythonpath_dirs.append(str(src_dir))

        # Also add python/ directory if it exists (common for Rust/PyO3 projects)
        python_dir = package_root / "python"
        if python_dir.exists() and python_dir.is_dir():
            pythonpath_dirs.append(str(python_dir))

        existing_pythonpath = env.get("PYTHONPATH", "")
        new_pythonpath = os.pathsep.join(pythonpath_dirs)
        if existing_pythonpath:
            # Prepend our paths to existing PYTHONPATH
            env["PYTHONPATH"] = f"{new_pythonpath}{os.pathsep}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = new_pythonpath

        return env

    def _get_package_metadata(self) -> dict:
        """
        Extract package metadata from pyproject.toml and great-docs configuration.

        Reads project metadata (license, authors, URLs, etc.) from pyproject.toml
        and Great Docs configuration from great-docs.yml.

        Returns
        -------
        dict
            Dictionary containing package metadata and great-docs configuration.
        """
        metadata = {}
        package_root = self._find_package_root()
        pyproject_path = package_root / "pyproject.toml"

        # Read project metadata from pyproject.toml
        if pyproject_path.exists():
            import tomllib

            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    project = data.get("project", {})

                    # Extract relevant fields from [project] section
                    # License can be a string (PEP 639) or a dict with "text"/"file" keys
                    license_val = project.get("license", "")
                    if isinstance(license_val, dict):
                        metadata["license"] = license_val.get("text") or license_val.get("file", "")
                    else:
                        metadata["license"] = str(license_val) if license_val else ""
                    metadata["authors"] = project.get("authors", [])
                    metadata["maintainers"] = project.get("maintainers", [])
                    metadata["urls"] = project.get("urls", {})
                    metadata["requires_python"] = project.get("requires-python", "")
                    metadata["keywords"] = project.get("keywords", [])
                    metadata["description"] = project.get("description", "")
                    metadata["optional_dependencies"] = project.get("optional-dependencies", {})

            except Exception:
                pass

        # Fall back to setup.cfg if pyproject.toml didn't provide key metadata
        if not metadata.get("description"):
            setup_cfg = package_root / "setup.cfg"
            if setup_cfg.exists():
                try:
                    import configparser

                    cfg = configparser.ConfigParser()
                    cfg.read(setup_cfg, encoding="utf-8")

                    if not metadata.get("description"):
                        metadata["description"] = cfg.get("metadata", "description", fallback="")

                    if not metadata.get("license"):
                        metadata["license"] = cfg.get("metadata", "license", fallback="")

                    if not metadata.get("requires_python"):
                        metadata["requires_python"] = cfg.get(
                            "options", "python_requires", fallback=""
                        )

                    if not metadata.get("authors"):
                        author = cfg.get("metadata", "author", fallback="")
                        author_email = cfg.get("metadata", "author_email", fallback="")
                        if author:
                            entry = {"name": author}
                            if author_email:
                                entry["email"] = author_email
                            metadata["authors"] = [entry]

                    if not metadata.get("maintainers"):
                        maintainer = cfg.get("metadata", "maintainer", fallback="")
                        maintainer_email = cfg.get("metadata", "maintainer_email", fallback="")
                        if maintainer:
                            entry = {"name": maintainer}
                            if maintainer_email:
                                entry["email"] = maintainer_email
                            metadata["maintainers"] = [entry]

                    if not metadata.get("urls"):
                        urls = {}
                        # Main url field
                        url = cfg.get("metadata", "url", fallback="")
                        if url:
                            urls["Repository"] = url
                        # project_urls is a multi-line value
                        project_urls_raw = cfg.get("metadata", "project_urls", fallback="")
                        if project_urls_raw:
                            for line in project_urls_raw.strip().splitlines():
                                line = line.strip()
                                if "=" in line:
                                    key, val = line.split("=", 1)
                                    urls[key.strip()] = val.strip()
                        if urls:
                            metadata["urls"] = urls

                except Exception:  # pragma: no cover
                    pass

        # Read Great Docs configuration from great-docs.yml
        # Reload config to ensure we have the latest
        self._config = Config(package_root)

        # Map config properties to metadata dict for backward compatibility
        metadata["rich_authors"] = self._config.authors
        metadata["exclude"] = self._config.exclude

        # Source link configuration
        metadata["source_link_enabled"] = self._config.source_enabled
        metadata["source_link_branch"] = self._config.source_branch
        metadata["source_link_path"] = self._config.source_path
        metadata["source_link_placement"] = self._config.source_placement

        # GitHub link style
        metadata["github_style"] = self._config.github_style

        # Sidebar filter configuration
        metadata["sidebar_filter_enabled"] = self._config.sidebar_filter_enabled
        metadata["sidebar_filter_min_items"] = self._config.sidebar_filter_min_items

        # CLI documentation configuration
        metadata["cli_enabled"] = self._config.cli_enabled
        metadata["cli_module"] = self._config.cli_module
        metadata["cli_name"] = self._config.cli_name

        # Dark mode toggle
        metadata["dark_mode_toggle_enabled"] = self._config.dark_mode_toggle

        # Markdown pages (.md generation + copy-page widget)
        metadata["markdown_pages"] = self._config.markdown_pages
        metadata["markdown_pages_widget"] = self._config.markdown_pages_widget

        # Funding organization
        metadata["funding"] = self._config.funding

        # Logo & favicon configuration
        metadata["logo"] = self._config.logo
        metadata["logo_show_title"] = self._config.logo_show_title
        metadata["favicon"] = self._config.favicon

        return metadata

    def _update_navbar_github_link(
        self,
        config: dict,
        owner: str | None,
        repo: str | None,
        repo_url: str | None,
        github_style: str,
    ) -> None:
        """
        Update an existing navbar's GitHub link to use widget or icon style.

        Parameters
        ----------
        config
            The Quarto configuration dictionary.
        owner
            GitHub repository owner.
        repo
            GitHub repository name.
        repo_url
            Full GitHub repository URL.
        github_style
            Either "widget" (with stats dropdown) or "icon" (simple link).
        """
        if not repo_url:
            return

        navbar = config["website"]["navbar"]

        # Ensure right section exists
        if "right" not in navbar:
            navbar["right"] = []

        # Build the new GitHub entry based on style
        if github_style == "widget" and owner and repo:
            new_gh_entry = {
                "text": f'<div id="github-widget" data-owner="{owner}" data-repo="{repo}"></div>'
            }
        else:
            new_gh_entry = {"icon": "github", "href": repo_url}

        # Look for existing GitHub entry and replace it
        new_right = []
        found_github = False

        for item in navbar["right"]:
            if isinstance(item, dict):
                # Check for simple GitHub icon
                if item.get("icon") == "github":
                    new_right.append(new_gh_entry)
                    found_github = True
                # Check for existing widget
                elif "github-widget" in str(item.get("text", "")):
                    new_right.append(new_gh_entry)
                    found_github = True
                else:
                    new_right.append(item)
            else:
                new_right.append(item)

        # If no GitHub entry was found, add one
        if not found_github:
            new_right.append(new_gh_entry)

        navbar["right"] = new_right

    def _get_github_repo_info(self) -> tuple[str | None, str | None, str | None]:
        """
        Extract GitHub repository information.

        Checks `repo` in great-docs.yml first (as an override), then falls
        back to `[project.urls]` in pyproject.toml.

        Returns
        -------
        tuple[str | None, str | None, str | None]
            A tuple of (owner, repo_name, base_url) or (None, None, None) if not found.
        """
        metadata = self._get_package_metadata()

        # Check great-docs.yml `repo:` override first
        repo_url = self._config.repo

        # Fall back to pyproject.toml [project.urls]
        if not repo_url:
            urls = metadata.get("urls", {})
            for key in [
                "Repository",
                "repository",
                "Source",
                "source",
                "GitHub",
                "github",
                "Homepage",
                "homepage",
            ]:
                if key in urls:
                    repo_url = urls[key]
                    break

        if not repo_url or "github.com" not in repo_url:
            return None, None, None

        # Parse the GitHub URL to extract owner and repo
        # Handles formats like:
        # - https://github.com/owner/repo
        # - https://github.com/owner/repo.git
        # - git@github.com:owner/repo.git
        github_pattern = r"github\.com[/:]([^/]+)/([^/\s.]+)"
        match = re.search(github_pattern, repo_url)

        if match:
            owner = match.group(1)
            repo = match.group(2)
            # Remove .git suffix if present (use removesuffix, not rstrip which removes characters)
            if repo.endswith(".git"):
                repo = repo[:-4]
            base_url = f"https://github.com/{owner}/{repo}"
            return owner, repo, base_url

        return None, None, None

    # =========================================================================
    # Changelog (GitHub Releases) Methods
    # =========================================================================

    def _fetch_github_releases(
        self,
        owner: str,
        repo: str,
        max_releases: int = 50,
    ) -> list[dict]:
        """
        Fetch releases from the GitHub API.

        Parameters
        ----------
        owner
            GitHub repository owner.
        repo
            GitHub repository name.
        max_releases
            Maximum number of releases to return.

        Returns
        -------
        list[dict]
            List of release dicts with keys: tag_name, name, body, published_at,
            html_url, prerelease, draft.
        """
        import requests

        releases: list[dict] = []
        per_page = min(max_releases, 100)
        page = 1

        headers = {"Accept": "application/vnd.github+json"}

        # Honour GITHUB_TOKEN / GH_TOKEN for higher rate limits
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        while len(releases) < max_releases:
            url = (
                f"https://api.github.com/repos/{owner}/{repo}/releases"
                f"?per_page={per_page}&page={page}"
            )

            try:
                resp = requests.get(url, headers=headers, timeout=30)
            except requests.RequestException as exc:
                print(f"   ⚠️  Failed to fetch GitHub releases: {exc}")
                break

            if resp.status_code == 403:
                # Rate-limited
                print("   ⚠️  GitHub API rate limit reached; changelog may be incomplete")
                break
            if resp.status_code == 404:
                print(f"   ⚠️  GitHub repository {owner}/{repo} not found")
                break
            if resp.status_code != 200:
                print(f"   ⚠️  GitHub API returned status {resp.status_code}")
                break

            data = resp.json()
            if not data:
                break  # No more pages

            for release in data:
                if release.get("draft"):  # pragma: no cover
                    continue  # Skip drafts
                releases.append(
                    {
                        "tag_name": release.get("tag_name", ""),
                        "name": release.get("name", ""),
                        "body": release.get("body", ""),
                        "published_at": release.get("published_at", ""),
                        "html_url": release.get("html_url", ""),
                        "prerelease": release.get("prerelease", False),
                    }
                )
                if len(releases) >= max_releases:
                    break

            if len(data) < per_page:
                break  # Last page
            page += 1

        return releases

    @staticmethod
    def _linkify_github_references(text: str, owner: str, repo: str) -> str:
        """
        Turn GitHub shorthand references into Markdown links.

        Converts bare `#123`, `gh issue #123`, `gh pr #123`, and
        `@username` references into clickable Markdown links that point to
        the correct GitHub URL.

        Parameters
        ----------
        text
            The Markdown body text from a GitHub Release.
        owner
            GitHub repository owner.
        repo
            GitHub repository name.

        Returns
        -------
        str
            Text with shorthand references replaced by Markdown links.
        """
        base = f"https://github.com/{owner}/{repo}"

        # 0.  Remove GitHub's backslash escapes (the API often returns
        #     \@, \#, \', \" which break Markdown rendering and block
        #     the regex patterns below).
        text = re.sub(r"\\([\\@#'\"])", r"\1", text)

        # 1.  "gh issue #NNN" / "gh pr #NNN"  (case-insensitive)
        text = re.sub(
            r"(?i)\bgh\s+(?:issue|pr)\s+#(\d+)",
            rf"[#\1]({base}/issues/\1)",
            text,
        )

        # 2.  Bare "#NNN" not already inside a Markdown link.
        #     Skip when preceded by '[' (link text from step 1) or
        #     when inside a URL (preceded by '/').
        text = re.sub(
            r"(?<!\[)(?<!/)#(\d+)\b",
            rf"[#\1]({base}/issues/\1)",
            text,
        )

        # 3.  "@username" – valid GitHub usernames: alphanumeric + hyphens,
        #     1-39 chars, not starting/ending with hyphen.
        #     Negative look-behind avoids matching email addresses.
        text = re.sub(
            r"(?<![\w.])@([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?)",
            r"[@\1](https://github.com/\1)",
            text,
        )

        return text

    def _generate_changelog_page(self) -> str | None:
        """
        Generate a changelog.qmd page from GitHub Releases.

        Fetches releases via the GitHub API and renders them as a dated
        Markdown changelog. Returns the filename written (`"changelog.qmd"`)
        or `None` if the page could not be generated.

        Returns
        -------
        str | None
            `"changelog.qmd"` on success, `None` otherwise.
        """
        owner, repo, _base_url = self._get_github_repo_info()
        if not owner or not repo:
            return None

        max_releases = self._config.changelog_max_releases
        releases = self._fetch_github_releases(owner, repo, max_releases)
        if not releases:
            return None

        # Build .qmd content
        lines: list[str] = [
            "---",
            'title: "Changelog"',
            "toc: true",
            "toc-depth: 2",
            "---",
            "",
            "This changelog is generated automatically from ",
            f"[GitHub Releases](https://github.com/{owner}/{repo}/releases).",
            "",
        ]

        for rel in releases:
            # --- heading ------------------------------------------------
            tag = rel["tag_name"]
            name = rel["name"] or tag
            published = rel["published_at"][:10] if rel["published_at"] else ""
            gh_url = rel["html_url"]

            heading = f"## {name}"
            if published:
                heading += f"  {{.changelog-version}}"  # noqa: F541

            lines.append(heading)
            lines.append("")

            # Date + link line
            meta_parts: list[str] = []
            if published:
                meta_parts.append(f"*{published}*")
            if rel["prerelease"]:
                meta_parts.append("*(pre-release)*")
            meta_parts.append(f"[GitHub]({gh_url})")
            lines.append(" · ".join(meta_parts))
            lines.append("")

            # --- body ---------------------------------------------------
            body = (rel.get("body") or "").strip()
            if body:
                body = self._linkify_github_references(body, owner, repo)
                lines.append(body)
                lines.append("")

        changelog_path = self.project_path / "changelog.qmd"
        changelog_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Created {changelog_path}")

        return "changelog.qmd"

    def _add_changelog_to_navbar(self) -> None:
        """Add a *Changelog* link to the navbar (idempotent)."""
        quarto_yml = self.project_path / "_quarto.yml"
        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        navbar = config.get("website", {}).get("navbar")
        if not navbar or "left" not in navbar:
            return

        # Already present?
        if any(
            isinstance(item, dict) and item.get("text") == "Changelog" for item in navbar["left"]
        ):
            return

        # Insert before the last item (usually Reference) or at end
        navbar["left"].append({"text": "Changelog", "href": "changelog.qmd"})

        self._write_quarto_yml(quarto_yml, config)

    # =========================================================================
    # Custom Sections Methods
    # =========================================================================

    def _process_sections(self) -> int:
        """
        Process custom sections: discover files, copy, generate index, wire nav.

        Each configured section gets its own navbar link, sidebar, and
        (optionally) an auto-generated index page. Blog-type sections
        use Quarto's native `listing:` directive instead of cards and
        skip the sidebar.

        Returns
        -------
        int
            Number of sections successfully processed.
        """
        sections_config = self._config.sections
        if not sections_config:
            return 0

        # Sections must be a list of dicts
        if not isinstance(sections_config, list):
            print(f"   ⚠️  'sections' must be a list, got {type(sections_config).__name__}")
            return 0

        processed = 0

        for section_cfg in sections_config:
            if not isinstance(section_cfg, dict):
                print(f"   ⚠️  Section entry must be a dict, skipping: {section_cfg}")
                continue
            title = section_cfg.get("title")
            src_dir = section_cfg.get("dir")
            if not title or not src_dir:
                print(f"   ⚠️  Section missing 'title' or 'dir', skipping: {section_cfg}")
                continue

            source_path = self.project_root / src_dir
            if not source_path.exists() or not source_path.is_dir():
                print(f"   ⚠️  Section directory '{src_dir}' not found, skipping")
                continue

            section_type = section_cfg.get("type", "default")

            # Discover .qmd / .md files
            files = sorted(
                [
                    f
                    for f in source_path.rglob("*")
                    if f.suffix in (".qmd", ".md") and f.name != "README.md"
                ]
            )

            if not files:
                print(f"   ⚠️  Section '{title}' directory '{src_dir}' has no .qmd/.md files")
                continue

            # Determine the slug for the build directory (lowercase, hyphenated)
            slug = src_dir.replace("_", "-").replace(" ", "-").lower()
            dest_dir = self.project_path / slug
            dest_dir.mkdir(parents=True, exist_ok=True)

            if section_type == "blog":
                # Blog sections use Quarto's native listing directive
                copied = self._copy_blog_files(files, source_path, dest_dir)

                # For blogs, only a root-level index.qmd counts as a user index
                # (subdirectory index.qmd files are individual blog posts)
                has_user_index = (source_path / "index.qmd").exists()
                if has_user_index:
                    index_href = f"{slug}/index.qmd"
                else:
                    self._generate_blog_index(title, slug, dest_dir)
                    index_href = f"{slug}/index.qmd"

                # Blog sections don't get a sidebar — the listing page
                # is the primary navigation experience.
            else:
                # Default: sections with sidebar (index page is opt-in)
                copied = self._copy_section_files(files, source_path, dest_dir)

                has_user_index = any(f.name == "index.qmd" for f in files)
                generate_index = section_cfg.get("index", False)

                if has_user_index:
                    # User provided their own index.qmd — always use it
                    index_href = f"{slug}/index.qmd"
                elif generate_index:
                    # Auto-generate a card-based index page (opt-in)
                    self._generate_section_index(title, copied, slug, dest_dir)
                    index_href = f"{slug}/index.qmd"
                else:
                    # No index page — navbar links to the first content page
                    first_page = next((p for p in copied if p["filename"] != "index.qmd"), None)
                    if first_page:
                        index_href = f"{slug}/{first_page['filename']}"
                    else:
                        index_href = f"{slug}/index.qmd"

                # Add sidebar (skipped for single-page sections)
                self._add_section_sidebar(title, slug, copied, has_user_index, generate_index)

                # For single-page sections (no sidebar), inject a body class so
                # CSS can expand the content area into the sidebar space.
                content_pages = [p for p in copied if p["filename"] != "index.qmd"]
                has_index = has_user_index or generate_index
                sidebar_items = (1 if has_index else 0) + len(content_pages)
                if sidebar_items <= 1:
                    self._inject_section_body_class(slug, copied, dest_dir)

            # Add navbar link
            navbar_after = section_cfg.get("navbar_after")
            self._add_section_to_navbar(title, index_href, navbar_after)

            n_pages = len(copied)
            label = "📰" if section_type == "blog" else "📂"
            print(f"   {label} {title}: {n_pages} post(s) from {src_dir}/")
            processed += 1

        return processed

    def _copy_section_files(
        self,
        files: list[Path],
        source_dir: Path,
        dest_dir: Path,
    ) -> list[dict]:
        """
        Copy section files to the build directory.

        Strips numeric prefixes and adds `bread-crumbs: false` to frontmatter.

        Parameters
        ----------
        files
            List of source file paths.
        source_dir
            Root of the section source directory.
        dest_dir
            Destination directory in the build tree.

        Returns
        -------
        list[dict]
            List of dicts with `filename`, `title`, `description`, `image` keys.
        """
        copied: list[dict] = []

        for src_file in files:
            rel = src_file.relative_to(source_dir)

            # Strip numeric prefix from filename (e.g., 01-intro.qmd -> intro.qmd)
            clean_name = self._strip_numeric_prefix(rel.name)
            dest_file = dest_dir / rel.parent / clean_name

            # Ensure subdirectories exist
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            content = src_file.read_text(encoding="utf-8")

            # Parse frontmatter for metadata
            title = clean_name.replace(".qmd", "").replace(".md", "").replace("-", " ").title()
            description = ""
            image = ""

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        fm = parse_yaml(parts[1])
                        if isinstance(fm, dict):
                            title = fm.get("title", title)
                            description = fm.get("description", "")
                            image = fm.get("image", "")

                            # Add bread-crumbs: false
                            changed = False
                            if "bread-crumbs" not in fm:
                                fm["bread-crumbs"] = False
                                changed = True
                            if changed:
                                parts[1] = "\n" + format_yaml(fm) + "\n"
                                content = "---".join(parts)
                    except ValueError:
                        pass

            dest_file.write_text(content, encoding="utf-8")

            copied.append(
                {
                    "filename": str(rel.parent / clean_name)
                    if rel.parent != Path(".")
                    else clean_name,
                    "title": title,
                    "description": description,
                    "image": image,
                }
            )

        return copied

    def _copy_blog_files(
        self,
        files: list[Path],
        source_dir: Path,
        dest_dir: Path,
    ) -> list[dict]:
        """
        Copy blog post files to the build directory.

        Preserves subdirectory structure (e.g., `blog/my-post/index.qmd`)
        and leaves blog frontmatter intact so Quarto's `listing:` directive
        can read `title`, `author`, `date`, `categories`, etc.

        Parameters
        ----------
        files
            List of source file paths.
        source_dir
            Root of the blog source directory.
        dest_dir
            Destination directory in the build tree.

        Returns
        -------
        list[dict]
            List of dicts with `filename`, `title`, `description` keys.
        """
        copied: list[dict] = []

        for src_file in files:
            rel = src_file.relative_to(source_dir)
            dest_file = dest_dir / rel

            # Ensure subdirectories exist
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            content = src_file.read_text(encoding="utf-8")

            # Parse frontmatter for metadata (but don't modify it —
            # Quarto's listing needs the original frontmatter)
            title = rel.stem.replace("-", " ").title()
            description = ""

            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    try:
                        fm = parse_yaml(parts[1])
                        if isinstance(fm, dict):
                            title = fm.get("title", title)
                            description = fm.get("description", "")
                    except ValueError:
                        pass

            dest_file.write_text(content, encoding="utf-8")

            copied.append(
                {
                    "filename": str(rel),
                    "title": title,
                    "description": description,
                }
            )

        return copied

    def _generate_blog_index(
        self,
        title: str,
        slug: str,
        dest_dir: Path,
    ) -> None:
        """
        Auto-generate a blog listing index using Quarto's `listing:` directive.

        Creates a page that mirrors the approach used by Great Tables and other
        Quarto-based project blogs: a table-style listing sorted by date.

        Parameters
        ----------
        title
            Blog section title (used as page heading).
        slug
            URL slug for the blog section.
        dest_dir
            Build directory for the blog section.
        """
        lines = [
            "---",
            f'title: "{title}"',
            "listing:",
            "  type: default",
            '  sort: "date desc"',
            "  contents:",
            '    - "**.qmd"',
            "bread-crumbs: false",
            "---",
            "",
        ]

        index_file = dest_dir / "index.qmd"
        index_file.write_text("\n".join(lines), encoding="utf-8")

    def _generate_section_index(
        self,
        title: str,
        pages: list[dict],
        slug: str,
        dest_dir: Path,
    ) -> None:
        """
        Auto-generate an index page for a custom section.

        Creates a gallery-style listing from each page's frontmatter title
        and description.

        Parameters
        ----------
        title
            Section title (used as page heading).
        pages
            List of page dicts from ``_copy_section_files``.
        slug
            URL slug for the section.
        dest_dir
            Build directory for the section.
        """
        lines = [
            "---",
            f'title: "{title}"',
            "bread-crumbs: false",
            "---",
            "",
        ]

        # Filter out the index itself if present
        entries = [p for p in pages if p["filename"] != "index.qmd"]

        if not entries:
            lines.append("*No pages found.*")
        else:
            # Use inline styles to ensure card layout renders correctly
            # regardless of Quarto's page-columns grid system.
            # Build as a single contiguous HTML block so Quarto's Markdown
            # parser does not inject extra <p> or duplicate <a> elements.
            grid_style = (
                "display: grid; "
                "grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); "
                "gap: 1rem; "
                "margin-top: 0.5rem;"
            )
            card_style = (
                "display: block; "
                "padding: 1.25rem 1.5rem; "
                "border: 1px solid #dee2e6; "
                "border-radius: 0.5rem; "
                "color: inherit; "
                "text-decoration: none;"
            )
            title_style = (
                "font-size: 1.1rem; font-weight: 600; margin-bottom: 0.35rem; color: #0d6efd;"
            )
            desc_style = "font-size: 0.9rem; color: #6c757d; line-height: 1.45;"

            parts: list[str] = []
            parts.append(f'<div class="section-cards" style="{grid_style}">')

            for entry in entries:
                href = entry["filename"]
                entry_title = entry["title"]
                desc = entry.get("description", "")
                image = entry.get("image", "")

                parts.append(f'<a href="{href}" class="section-card" style="{card_style}">')

                if image:
                    parts.append(
                        f'<img src="{image}" class="section-card-img" '
                        'style="width: 100%; border-radius: 0.375rem; '
                        'margin-bottom: 0.75rem;" />'
                    )

                parts.append(
                    f'<div class="section-card-title" style="{title_style}">{entry_title}</div>'
                )
                if desc:
                    parts.append(
                        f'<div class="section-card-desc" style="{desc_style}">{desc}</div>'
                    )

                parts.append("</a>")

            # Close container on the same line as the last </a> to prevent
            # Quarto's Markdown parser from injecting a phantom <p><a></a></p>.
            parts[-1] = parts[-1] + "</div>"

            # Join without blank lines to keep it as one HTML block
            lines.append("\n".join(parts))

        lines.append("")
        index_file = dest_dir / "index.qmd"
        index_file.write_text("\n".join(lines), encoding="utf-8")

    def _add_section_sidebar(
        self,
        title: str,
        slug: str,
        pages: list[dict],
        has_user_index: bool,
        has_generated_index: bool = False,
    ) -> None:
        """
        Add a sidebar for the custom section to ``_quarto.yml``.

        Parameters
        ----------
        title
            Section title.
        slug
            URL slug for the section directory.
        pages
            List of page dicts from ``_copy_section_files``.
        has_user_index
            Whether the user provided their own index.qmd.
        has_generated_index
            Whether an auto-generated index page was created.
        """
        quarto_yml = self.project_path / "_quarto.yml"
        config = self._read_quarto_config(quarto_yml)

        sidebar_id = slug
        contents: list[dict | str] = []

        has_index = has_user_index or has_generated_index

        if has_index:
            # Add index as the first item when one exists
            contents.append({"text": title, "href": f"{slug}/index.qmd"})

        # Add each page (except index.qmd)
        for page in pages:
            if page["filename"] == "index.qmd":
                continue
            contents.append(
                {
                    "text": page["title"],
                    "href": f"{slug}/{page['filename']}",
                }
            )

        # Skip sidebar when a section has only a single page — the lone item
        # provides no navigation value and wastes horizontal space.  Without a
        # sidebar entry the page content expands into the full width.
        if len(contents) <= 1:
            return

        sidebar_config = {
            "id": sidebar_id,
            "title": title,
            "contents": contents,
        }

        # Remove existing sidebar with same id
        sidebar = config["website"]["sidebar"]
        sidebar = [s for s in sidebar if not (isinstance(s, dict) and s.get("id") == sidebar_id)]
        sidebar.append(sidebar_config)
        config["website"]["sidebar"] = sidebar

        self._write_quarto_yml(quarto_yml, config)

    def _inject_section_body_class(
        self,
        slug: str,
        pages: list[dict],
        dest_dir: Path,
    ) -> None:
        """
        Add `body-classes: gd-section-no-sidebar` to frontmatter of every page in a single-page
        section so CSS can expand the content area.
        """
        for page in pages:
            qmd_path = dest_dir / page["filename"]
            if not qmd_path.exists():
                continue

            content = qmd_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:  # pragma: no cover
                continue

            try:
                fm = parse_yaml(parts[1])
                if not isinstance(fm, dict):
                    continue
            except ValueError:  # pragma: no cover
                continue

            # Merge body-classes
            existing = fm.get("body-classes", "")
            classes = existing.split() if existing else []
            if "gd-section-no-sidebar" not in classes:
                classes.append("gd-section-no-sidebar")
                fm["body-classes"] = " ".join(classes)
                parts[1] = "\n" + format_yaml(fm) + "\n"
                qmd_path.write_text("---".join(parts), encoding="utf-8")

    def _add_section_to_navbar(
        self,
        title: str,
        href: str,
        navbar_after: str | None = None,
    ) -> None:
        """
        Add a navbar link for the custom section.

        Parameters
        ----------
        title
            Link text.
        href
            Link target.
        navbar_after
            Name of an existing navbar item to insert after. If None,
            inserts before "Reference".
        """
        quarto_yml = self.project_path / "_quarto.yml"
        config = self._read_quarto_config(quarto_yml)

        navbar = config.get("website", {}).get("navbar", {})
        if not navbar or "left" not in navbar:
            return

        # Check if link already exists
        if any(isinstance(item, dict) and item.get("text") == title for item in navbar["left"]):
            return

        link = {"text": title, "href": href}

        if navbar_after:
            # Find the item to insert after
            for i, item in enumerate(navbar["left"]):
                if isinstance(item, dict) and item.get("text") == navbar_after:
                    navbar["left"].insert(i + 1, link)
                    break
            else:
                # Fallback: insert before Reference
                self._insert_before_reference(navbar["left"], link)
        else:
            # Default: insert before Reference
            self._insert_before_reference(navbar["left"], link)

        self._write_quarto_yml(quarto_yml, config)

    def _insert_before_reference(self, navbar_items: list, link: dict) -> None:
        """Insert a link before the 'Reference' navbar item, or append."""
        for i, item in enumerate(navbar_items):
            if isinstance(item, dict) and item.get("text") == "Reference":
                navbar_items.insert(i, link)
                return
        # If no Reference found then append
        navbar_items.append(link)

    def _read_quarto_config(self, quarto_yml: Path) -> dict:
        """Read and return the _quarto.yml config, ensuring website.sidebar exists."""
        if quarto_yml.exists():
            with open(quarto_yml, "r") as f:
                config = read_yaml(f) or {}
        else:
            config = {}

        config.setdefault("website", {})
        config["website"].setdefault("sidebar", [])
        config["website"].setdefault("navbar", {"left": []})

        return config

    # =========================================================================
    # CLI Documentation Methods
    # =========================================================================

    def _discover_click_cli(self, package_name: str) -> dict | None:
        """
        Discover Click CLI commands and groups from a package.

        Attempts to find and import the Click CLI from the package, then extracts
        command structure, help text, options, and arguments.

        Parameters
        ----------
        package_name
            The name of the package to search for CLI.

        Returns
        -------
        dict | None
            Dictionary containing CLI structure, or None if no Click CLI found.
            Structure: {
                "name": "cli-name",
                "help": "CLI help text",
                "commands": [...],  # List of command dicts
                "options": [...],   # Global options
            }
        """
        metadata = self._get_package_metadata()

        # Check if CLI documentation is enabled
        if not metadata.get("cli_enabled", False):
            return None

        try:
            import click
        except ImportError:
            print("Click not installed, skipping CLI documentation")  # pragma: no cover
            return None  # pragma: no cover

        # Normalize to importable module name (hyphens → underscores)
        importable_name = self._normalize_package_name(package_name)

        # Determine the CLI module to import
        cli_module_path = metadata.get("cli_module")
        if not cli_module_path:
            # Try common CLI module locations
            common_cli_modules = [
                f"{importable_name}.cli",
                f"{importable_name}.__main__",
                f"{importable_name}.main",
                f"{importable_name}.console",
                f"{importable_name}.commands",
            ]
            cli_module_path = None
            for module_path in common_cli_modules:
                try:
                    import importlib

                    module = importlib.import_module(module_path)
                    # Look for Click command/group in module
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, (click.Command, click.Group)):
                            cli_module_path = module_path
                            break
                    if cli_module_path:
                        break
                except ImportError:
                    continue

        if not cli_module_path:
            print(f"No Click CLI found in {package_name}")
            return None

        try:
            import importlib

            module = importlib.import_module(cli_module_path)
        except ImportError as e:
            print(f"Could not import CLI module {cli_module_path}: {e}")
            return None

        # Find the main Click command/group
        cli_obj = None
        cli_name = metadata.get("cli_name")

        # First, look for explicitly named CLI
        if cli_name:
            cli_obj = getattr(module, cli_name, None)

        # Otherwise, search for Click commands/groups
        if not cli_obj:
            for attr_name in ["cli", "main", "app", "command", importable_name]:
                attr = getattr(module, attr_name, None)
                if isinstance(attr, (click.Command, click.Group)):
                    cli_obj = attr
                    cli_name = attr_name
                    break

        # If still not found, look for any Click command/group
        if not cli_obj:
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)
                if isinstance(attr, (click.Command, click.Group)):
                    cli_obj = attr
                    cli_name = attr_name
                    break

        if not cli_obj:
            print(f"No Click command/group found in {cli_module_path}")
            return None

        print(f"Found Click CLI: {cli_name} in {cli_module_path}")

        # Get the entry point name from pyproject.toml
        entry_point_name = self._get_cli_entry_point_name(package_name)
        display_name = entry_point_name or package_name.replace("_", "-")

        # Extract CLI structure
        cli_info = self._extract_click_command(cli_obj, display_name)
        cli_info["entry_point_name"] = display_name
        return cli_info

    def _get_cli_entry_point_name(self, package_name: str) -> str | None:
        """
        Get the CLI entry point name from pyproject.toml.

        Parameters
        ----------
        package_name
            The name of the package.

        Returns
        -------
        str | None
            The entry point name (e.g., "great-docs" from "[project.scripts]"),
            or None if not found.
        """
        package_root = self._find_package_root()
        pyproject_path = package_root / "pyproject.toml"

        if not pyproject_path.exists():
            return None

        import tomllib

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            # Look for [project.scripts]
            scripts = data.get("project", {}).get("scripts", {})
            if scripts:
                # Return the first entry point name
                return list(scripts.keys())[0]

            # Also check [project.gui-scripts] for GUI apps
            gui_scripts = data.get("project", {}).get("gui-scripts", {})
            if gui_scripts:
                return list(gui_scripts.keys())[0]

        except Exception:  # pragma: no cover
            pass  # pragma: no cover

        return None

    def _extract_click_command(self, cmd, name: str, parent_path: str = "") -> dict:
        """
        Extract information from a Click command or group.

        Parameters
        ----------
        cmd
            The Click Command or Group object.
        name
            The command name.
        parent_path
            The parent command path for nested commands.

        Returns
        -------
        dict
            Dictionary containing command information.
        """
        import click

        full_path = f"{parent_path} {name}".strip() if parent_path else name

        # Get the actual --help output from Click
        help_text = self._get_click_help_text(cmd, full_path)

        info = {
            "name": name,
            "full_path": full_path,
            "help": cmd.help or "",
            "short_help": getattr(cmd, "short_help", "") or "",
            "help_text": help_text,  # The actual --help output
            "deprecated": getattr(cmd, "deprecated", False),
            "hidden": getattr(cmd, "hidden", False),
            "commands": [],
            "is_group": isinstance(cmd, click.Group),
        }

        # Extract subcommands if this is a group
        if isinstance(cmd, click.Group):
            for subcmd_name, subcmd in cmd.commands.items():
                if not getattr(subcmd, "hidden", False):
                    subcmd_info = self._extract_click_command(subcmd, subcmd_name, full_path)
                    info["commands"].append(subcmd_info)

        return info

    def _get_click_help_text(self, cmd: "click.Command", full_path: str) -> str:
        """
        Get the formatted --help output from a Click command.

        Parameters
        ----------
        cmd
            The Click Command object.
        full_path
            The full command path (e.g., "great-docs build").

        Returns
        -------
        str
            The formatted help text as it would appear from --help.
        """
        import click

        # Create a context to get the help text
        ctx = click.Context(cmd, info_name=full_path)
        return cmd.get_help(ctx)

    def _generate_cli_reference_pages(self, cli_info: dict) -> list[str | dict]:
        """
        Generate Quarto reference pages for CLI commands.

        Parameters
        ----------
        cli_info
            Dictionary containing CLI structure from _discover_click_cli.

        Returns
        -------
        list[str | dict]
            Sidebar items — plain path strings for leaf commands, or
            `{"section": ..., "contents": [...]}` dicts for groups.
        """
        if not cli_info:
            return []

        cli_ref_dir = self.project_path / "reference" / "cli"
        cli_ref_dir.mkdir(parents=True, exist_ok=True)

        generated_files: list[str | dict] = []

        # Generate main CLI page
        main_page = self._generate_cli_command_page(cli_info, is_main=True)
        main_path = cli_ref_dir / "index.qmd"
        with open(main_path, "w") as f:
            f.write(main_page)
        generated_files.append("reference/cli/index.qmd")
        print(f"Generated CLI reference: {main_path.relative_to(self.project_path)}")

        # Generate pages for subcommands
        generated_files.extend(self._generate_subcommand_pages(cli_info, cli_ref_dir))

        return generated_files

    def _generate_subcommand_pages(
        self,
        cmd_info: dict,
        output_dir: Path,
        rel_prefix: str = "reference/cli",
    ) -> list[str | dict]:
        """
        Recursively generate pages for subcommands.

        Parameters
        ----------
        cmd_info
            Command information dictionary.
        output_dir
            Directory to write pages to.
        rel_prefix
            The relative path prefix for sidebar entries (e.g. `reference/cli`
            or `reference/cli/task` for nested groups).

        Returns
        -------
        list[str | dict]
            Sidebar items — plain path strings for leaf commands, or
            `{"section": ..., "contents": [...]}` dicts for groups.
        """
        sidebar_items: list[str | dict] = []

        for subcmd in cmd_info.get("commands", []):
            # Generate page for this subcommand
            page_content = self._generate_cli_command_page(subcmd, is_main=False)
            safe_name = subcmd["name"].replace("-", "_")
            page_path = output_dir / f"{safe_name}.qmd"

            with open(page_path, "w") as f:
                f.write(page_content)

            rel_path = f"{rel_prefix}/{safe_name}.qmd"
            print(f"Generated CLI reference: {page_path.relative_to(self.project_path)}")

            # Recursively generate for nested subcommands
            if subcmd.get("commands"):
                subcmd_dir = output_dir / safe_name
                subcmd_dir.mkdir(exist_ok=True)
                nested = self._generate_subcommand_pages(
                    subcmd, subcmd_dir, f"{rel_prefix}/{safe_name}"
                )
                sidebar_items.append({"section": subcmd["name"], "contents": [rel_path] + nested})
            else:
                sidebar_items.append(rel_path)

        return sidebar_items

    def _generate_cli_command_page(self, cmd_info: dict, is_main: bool = False) -> str:
        """
        Generate Quarto page content for a CLI command showing --help output.

        Parameters
        ----------
        cmd_info
            Command information dictionary.
        is_main
            Whether this is the main CLI entry point.

        Returns
        -------
        str
            Quarto markdown content with the CLI help output.
        """
        lines = []

        # Front matter: use just the command name/path as title
        title = cmd_info["full_path"] if not is_main else cmd_info["name"]
        lines.append("---")
        lines.append(f'title: "{title}"')
        lines.append("sidebar: cli-reference")
        lines.append("page-navigation: false")
        lines.append("---")
        lines.append("")

        # Output the help text in a styled div
        lines.append("::: {.cli-manpage}")
        lines.append("")
        lines.append("```")
        lines.append(cmd_info.get("help_text", "").rstrip())
        lines.append("```")
        lines.append("")
        lines.append(":::")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _count_cli_sidebar_items(items: list) -> int:
        """Count the total number of .qmd pages in a (possibly nested) sidebar list."""
        count = 0
        for item in items:
            if isinstance(item, str):
                count += 1
            elif isinstance(item, dict):
                count += GreatDocs._count_cli_sidebar_items(item.get("contents", []))
        return count

    def _update_sidebar_with_cli(self, cli_files: list[str | dict]) -> None:
        """
        Update the sidebar configuration to include CLI reference.

        Parameters
        ----------
        cli_files
            Sidebar items — plain path strings for leaf commands, or
            `{"section": ..., "contents": [...]}` dicts for groups.
        """
        if not cli_files:
            return

        quarto_yml = self.project_path / "_quarto.yml"
        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        if "website" not in config:
            config["website"] = {}

        # Ensure sidebar exists
        if "sidebar" not in config["website"]:
            config["website"]["sidebar"] = []

        # Check if CLI section already exists
        sidebar = config["website"]["sidebar"]
        cli_section_exists = False

        for section in sidebar:
            if isinstance(section, dict) and section.get("id") == "cli-reference":
                cli_section_exists = True
                # Update contents
                section["contents"] = cli_files
                break

        if not cli_section_exists:
            # Add CLI section
            cli_section = {
                "id": "cli-reference",
                "title": "CLI Reference",
                "contents": cli_files,
            }
            sidebar.append(cli_section)

        # Ensure the reference sidebar has an API link at the top
        for section in sidebar:
            if isinstance(section, dict) and section.get("id") == "reference":
                contents = section.get("contents", [])
                # Check if API link already exists at the top
                has_api_link = False
                if contents and isinstance(contents[0], dict):
                    if contents[0].get("text") == "API" or contents[0].get("href", "").endswith(
                        "reference/index.qmd"
                    ):
                        has_api_link = True
                if not has_api_link:
                    # Add API link at the top
                    section["contents"] = [
                        {"text": "API", "href": "reference/index.qmd"},
                    ] + contents
                break

        self._write_quarto_yml(quarto_yml, config)

        print(
            f"Updated sidebar with {self._count_cli_sidebar_items(cli_files)} CLI reference page(s)"
        )

    # =========================================================================
    # User Guide Methods
    # =========================================================================

    def _find_user_guide_dir(self) -> Path | None:
        """
        Find the user guide source directory.

        Resolves the directory in the following order:

        1. If `user_guide` is a string in great-docs.yml, that path is used.
        2. Otherwise, looks for `user_guide/` then `user-guide/` in the project root.

        Returns
        -------
        Path | None
            Path to the user guide source directory, or `None` if not found.
        """
        package_root = self._find_package_root()
        configured_dir = self._config.user_guide_dir  # str or None (ignores list)

        if configured_dir is not None:
            user_guide_dir = package_root / configured_dir

            # Warn if conventional directory also exists but is being ignored
            conventional_dir = package_root / "user_guide"
            if conventional_dir.exists() and conventional_dir.is_dir():
                if user_guide_dir.resolve() != conventional_dir.resolve():
                    print(
                        f"   ⚠️  Both 'user_guide' config option ('{configured_dir}') and "
                        f"'user_guide/' directory exist; using configured path"
                    )

            if not user_guide_dir.exists() or not user_guide_dir.is_dir():
                print(
                    f"   ⚠️  User guide directory '{configured_dir}' "
                    f"specified in great-docs.yml does not exist"
                )
                return None

            return user_guide_dir

        # Fall back to conventional directory names
        user_guide_dir = package_root / "user_guide"
        if not user_guide_dir.exists() or not user_guide_dir.is_dir():
            user_guide_dir = package_root / "user-guide"
        if not user_guide_dir.exists() or not user_guide_dir.is_dir():
            return None

        return user_guide_dir

    def _discover_user_guide_explicit(
        self, user_guide_dir: Path, explicit_config: list[dict]
    ) -> dict | None:
        """
        Build user guide info from explicit section ordering in great-docs.yml.

        When `user_guide` is a list of section dicts in the config, this method
        resolves the referenced files and builds the user_guide_info structure.
        Files are referenced by name relative to the user guide source directory
        (no `user_guide/` prefix needed). Numeric filename prefixes are preserved.

        Parameters
        ----------
        user_guide_dir
            Path to the user guide source directory.
        explicit_config
            The list of section dicts from `user_guide` config.

        Returns
        -------
        dict | None
            User guide info structure with `explicit` flag set to True, or `None`
            if no valid files are found.
        """
        files_info = []
        sections: dict[str, list] = {}
        has_index = False
        seen_files: set[str] = set()

        for section_entry in explicit_config:
            section_name = section_entry.get("section", "")
            section_contents = section_entry.get("contents", [])

            if not section_name or not section_contents:
                continue

            section_files = []

            for item in section_contents:
                # Each item is either a string (filename) or a dict with text/href
                if isinstance(item, str):
                    filename = item
                    custom_text = None
                elif isinstance(item, dict):
                    filename = item.get("href", "")
                    custom_text = item.get("text")
                else:
                    continue

                if not filename or filename in seen_files:
                    continue

                # Resolve the file in the source directory
                file_path = user_guide_dir / filename
                if not file_path.exists():
                    print(f"   ⚠️  User guide file '{filename}' referenced in config does not exist")
                    continue

                seen_files.add(filename)

                # Parse the file for title/frontmatter
                file_info = self._parse_user_guide_file(file_path)
                if not file_info:
                    continue

                # Override section from config (not frontmatter)
                file_info["section"] = section_name

                # Store custom text if provided
                if custom_text:
                    file_info["custom_text"] = custom_text

                files_info.append(file_info)
                section_files.append(file_info)

                if file_path.name == "index.qmd":
                    has_index = True

            if section_files:
                sections[section_name] = section_files

        if not files_info:
            return None

        return {
            "files": files_info,
            "sections": sections,
            "has_index": has_index,
            "source_dir": user_guide_dir,
            "explicit": True,
            "explicit_config": explicit_config,
        }

    def _discover_user_guide(self) -> dict | None:
        """
        Discover user guide content from the user_guide directory.

        Supports two modes:

        1. **Explicit ordering**: When `user_guide` in great-docs.yml is a list of
           section dicts, files are ordered and grouped exactly as specified.
        2. **Auto-discovery**: When `user_guide` is a string (directory path) or `None`,
           files are discovered from the directory and sorted by filename.

        The source directory is resolved by `_find_user_guide_dir()`.

        Returns
        -------
        dict | None
            Dictionary containing user guide structure, or `None` if no user guide found.
            Structure: {
                "files": [{"path": Path, "section": str | None, "title": str}, ...],
                "sections": {"Section Name": [file_info, ...], ...},
                "has_index": bool,
                "source_dir": Path,
                "explicit": bool  (True when using explicit config ordering)
            }
        """
        # Check for explicit section ordering in config
        user_guide_config = self._config.user_guide
        if isinstance(user_guide_config, list):
            user_guide_dir = self._find_user_guide_dir()
            if not user_guide_dir:
                return None
            return self._discover_user_guide_explicit(user_guide_dir, user_guide_config)

        # Auto-discovery mode
        user_guide_dir = self._find_user_guide_dir()
        if not user_guide_dir:
            return None

        # Find all .qmd and .md files (not in subdirectories that are likely asset folders)
        guide_files = []
        valid_extensions = {".qmd", ".md"}
        # Check if directory is completely empty
        dir_contents = list(user_guide_dir.iterdir())
        if not dir_contents:
            print(f"   ⚠️  User guide directory '{user_guide_dir}' is empty")
            return None

        for item in dir_contents:
            if item.is_file() and item.suffix in valid_extensions:
                guide_files.append(item)
            elif item.is_dir():
                # Recursively check subdirectories for guide files at any depth
                for ext in valid_extensions:
                    for subitem in item.rglob(f"*{ext}"):
                        if subitem.is_file():
                            guide_files.append(subitem)

        if not guide_files:
            print(f"   ⚠️  User guide directory '{user_guide_dir}' contains no .qmd or .md files")
            return None

        # Sort files by name to respect ordering prefixes
        guide_files.sort(key=lambda p: p.name)

        # Parse each file to extract section and title from frontmatter
        files_info = []
        sections: dict[str, list] = {}
        has_index = False

        for qmd_path in guide_files:
            file_info = self._parse_user_guide_file(qmd_path)
            if file_info:
                files_info.append(file_info)

                # Track if there's an index.qmd
                if qmd_path.name == "index.qmd":
                    has_index = True

                # Group by section
                section_name = file_info.get("section")
                if section_name:
                    if section_name not in sections:
                        sections[section_name] = []
                    sections[section_name].append(file_info)

        if not files_info:
            return None

        return {
            "files": files_info,
            "sections": sections,
            "has_index": has_index,
            "source_dir": user_guide_dir,
            "explicit": False,
        }

    def _parse_user_guide_file(self, qmd_path: Path) -> dict | None:
        """
        Parse a user guide .qmd file to extract metadata from frontmatter.

        Parameters
        ----------
        qmd_path
            Path to the .qmd file.

        Returns
        -------
        dict | None
            Dictionary with file info: {"path": Path, "section": str | None, "title": str}
        """
        try:
            with open(qmd_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        # Extract YAML frontmatter
        frontmatter = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = parse_yaml(parts[1]) or {}
                except ValueError:
                    pass

        # Get title from frontmatter or derive from filename
        title = frontmatter.get("title")
        if not title:
            # Derive title from filename: "01-getting-started.qmd" -> "Getting Started"
            name = qmd_path.stem
            # Remove leading number prefix like "01-" or "00_"
            name = re.sub(r"^\d+[-_]", "", name)
            # Convert to title case
            title = name.replace("-", " ").replace("_", " ").title()

        # Get section from frontmatter (use 'guide-section' to avoid conflict with Quarto's 'section')
        section = frontmatter.get("guide-section")

        return {
            "path": qmd_path,
            "section": section,
            "title": title,
            "frontmatter": frontmatter,
        }

    def _strip_numeric_prefix(self, filename: str) -> str:
        """
        Strip numeric ordering prefix from a filename.

        Handles common patterns like:

        - 00-introduction.qmd -> introduction.qmd
        - 01-installation.qmd -> installation.qmd
        - 1-getting-started.qmd -> getting-started.qmd
        - 0001-overview.qmd -> overview.qmd

        Parameters
        ----------
        filename
            The filename to process.

        Returns
        -------
        str
            The filename with numeric prefix stripped, or unchanged if no prefix.
        """
        # Pattern matches: digits followed by a hyphen or underscore at the start
        # e.g., "00-", "01-", "1-", "0001-", "00_", etc.
        pattern = r"^\d+-|^\d+_"
        return re.sub(pattern, "", filename)

    def _copy_user_guide_to_docs(self, user_guide_info: dict) -> list[str]:
        """
        Copy user guide files from project root to docs directory.

        Adds `bread-crumbs: false` to the frontmatter of each file to disable breadcrumb
        navigation on user guide pages.

        When using explicit ordering (`user_guide` is a list in config), filenames are
        preserved as-is. In auto-discovery mode, numeric prefixes are stripped for cleaner URLs.

        Parameters
        ----------
        user_guide_info
            User guide structure from `_discover_user_guide`.

        Returns
        -------
        list[str]
            List of copied file paths relative to docs dir.
        """
        if not user_guide_info:
            return []

        source_dir = user_guide_info["source_dir"]
        target_dir = self.project_path / "user-guide"
        target_dir.mkdir(parents=True, exist_ok=True)

        is_explicit = user_guide_info.get("explicit", False)
        copied_files = []

        for file_info in user_guide_info["files"]:
            src_path = file_info["path"]

            # Determine relative path from source_dir
            try:
                rel_path = src_path.relative_to(source_dir)
            except ValueError:
                rel_path = Path(src_path.name)

            if is_explicit:
                # Explicit mode: preserve filenames as-is
                dest_rel_path = rel_path
            else:
                # Auto-discovery mode: strip numeric prefixes from both
                # directory names and filenames for cleaner URLs
                clean_parts = [self._strip_numeric_prefix(part) for part in rel_path.parts]
                dest_rel_path = Path(*clean_parts) if clean_parts else rel_path

            dst_path = target_dir / dest_rel_path
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Read the source file and modify frontmatter
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Add bread-crumbs: false to frontmatter
            content = self._add_frontmatter_option(content, "bread-crumbs", False)

            # Write to destination
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(content)

            copied_files.append(f"user-guide/{dest_rel_path}")

        # Also copy any asset directories (directories without .qmd files)
        for item in source_dir.iterdir():
            if item.is_dir():
                # Check if this directory has any .qmd files
                has_qmd = any(f.suffix == ".qmd" for f in item.rglob("*"))
                if not has_qmd:
                    # This is likely an asset directory, copy it
                    dst_dir = target_dir / item.name
                    if dst_dir.exists():
                        shutil.rmtree(dst_dir)
                    shutil.copytree(item, dst_dir)

        return copied_files

    def _add_frontmatter_option(self, content: str, key: str, value) -> str:
        """
        Add or update an option in the YAML frontmatter of a .qmd file.

        Parameters
        ----------
        content
            The file content.
        key
            The frontmatter key to add/update.
        value
            The value to set.

        Returns
        -------
        str
            The modified content with the frontmatter option added.
        """
        # Convert value to YAML string representation
        if isinstance(value, bool):
            yaml_value = "true" if value else "false"
        elif isinstance(value, str):
            yaml_value = f'"{value}"'
        else:
            yaml_value = str(value)

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                rest = parts[2]

                # Check if the key already exists
                key_pattern = rf"^{re.escape(key)}:\s*.*$"
                if re.search(key_pattern, frontmatter, re.MULTILINE):
                    # Update existing key
                    frontmatter = re.sub(
                        key_pattern, f"{key}: {yaml_value}", frontmatter, flags=re.MULTILINE
                    )
                else:
                    # Add new key at the end of frontmatter
                    frontmatter = frontmatter.rstrip() + f"\n{key}: {yaml_value}\n"

                return f"---{frontmatter}---{rest}"

        # No frontmatter, create one
        return f"---\n{key}: {yaml_value}\n---\n\n{content}"

    def _generate_user_guide_sidebar(self, user_guide_info: dict) -> dict:
        """
        Generate sidebar configuration for the user guide.

        In explicit mode, builds the sidebar directly from the config structure.
        In auto-discovery mode, builds it from discovered files and frontmatter sections.

        Parameters
        ----------
        user_guide_info
            User guide structure from _discover_user_guide.

        Returns
        -------
        dict
            Sidebar configuration dict for Quarto.
        """
        is_explicit = user_guide_info.get("explicit", False)

        if is_explicit:
            return self._generate_user_guide_sidebar_explicit(user_guide_info)

        return self._generate_user_guide_sidebar_auto(user_guide_info)

    def _generate_user_guide_sidebar_explicit(self, user_guide_info: dict) -> dict:
        """
        Generate sidebar from explicit config ordering.

        Builds the sidebar structure directly from the `user_guide` config list,
        preserving exact section ordering and file ordering as specified by the user.
        Filenames are used as-is (no numeric prefix stripping).

        Parameters
        ----------
        user_guide_info
            User guide structure from `_discover_user_guide_explicit`.

        Returns
        -------
        dict
            Sidebar configuration dict for Quarto.
        """
        explicit_config = user_guide_info["explicit_config"]
        source_dir = user_guide_info["source_dir"]
        contents = []

        for section_entry in explicit_config:
            section_name = section_entry.get("section", "")
            section_contents = section_entry.get("contents", [])

            if not section_name or not section_contents:
                continue

            sidebar_section_contents = []

            for item in section_contents:
                if isinstance(item, str):
                    filename = item
                    custom_text = None
                elif isinstance(item, dict):
                    filename = item.get("href", "")
                    custom_text = item.get("text")
                else:
                    continue

                if not filename:
                    continue

                # Verify the file exists in the source directory
                file_path = source_dir / filename
                if not file_path.exists():
                    continue

                href = f"user-guide/{filename}"

                if custom_text:
                    sidebar_section_contents.append({"text": custom_text, "href": href})
                else:
                    sidebar_section_contents.append(href)

            if sidebar_section_contents:
                contents.append(
                    {
                        "section": section_name,
                        "contents": sidebar_section_contents,
                    }
                )

        return {
            "id": "user-guide",
            "title": "User Guide",
            "contents": contents,
        }

    def _generate_user_guide_sidebar_auto(self, user_guide_info: dict) -> dict:
        """
        Generate sidebar from auto-discovered files.

        Builds the sidebar structure from discovered files and frontmatter sections,
        stripping numeric prefixes from filenames for cleaner URLs.

        Parameters
        ----------
        user_guide_info
            User guide structure from _discover_user_guide.

        Returns
        -------
        dict
            Sidebar configuration dict for Quarto.
        """
        source_dir = user_guide_info["source_dir"]
        files_info = user_guide_info["files"]
        sections = user_guide_info["sections"]

        contents = []

        # Helper to get clean href (strips numeric prefixes for cleaner URLs)
        def get_clean_href(file_info: dict) -> str:
            rel_path = file_info["path"].relative_to(source_dir)
            clean_parts = [self._strip_numeric_prefix(part) for part in rel_path.parts]
            clean_rel_path = Path(*clean_parts) if clean_parts else rel_path
            return f"user-guide/{clean_rel_path}"

        # If we have sections, organize by section
        if sections:
            # Track which files have been assigned to sections
            assigned_files = set()

            # First, preserve section order based on first file appearance
            section_order = []
            for file_info in files_info:
                section = file_info.get("section")
                if section and section not in section_order:
                    section_order.append(section)

            # Build section entries
            for section_name in section_order:
                section_files = sections[section_name]
                section_contents = []

                for file_info in section_files:
                    href = get_clean_href(file_info)
                    assigned_files.add(file_info["path"])

                    # Use custom text for index.qmd if it has a title
                    if file_info["path"].name == "index.qmd":
                        section_contents.append(
                            {
                                "text": file_info["title"],
                                "href": href,
                            }
                        )
                    else:
                        section_contents.append(href)

                contents.append(
                    {
                        "section": section_name,
                        "contents": section_contents,
                    }
                )

            # Add any files without sections at the end
            unsectioned = []
            for file_info in files_info:
                if file_info["path"] not in assigned_files:
                    unsectioned.append(get_clean_href(file_info))

            if unsectioned:
                contents.extend(unsectioned)

        else:
            # Check if files span multiple subdirectories — if so, group by
            # parent directory to give the sidebar a logical structure.
            subdirs = {}
            root_files = []
            for file_info in files_info:
                rel_path = file_info["path"].relative_to(source_dir)
                parent = rel_path.parent
                if parent == Path("."):
                    root_files.append(file_info)
                else:
                    parent_str = str(parent)
                    if parent_str not in subdirs:
                        subdirs[parent_str] = []
                    subdirs[parent_str].append(file_info)

            if subdirs:
                # Put root-level files first (index.qmd at the very top)
                root_files.sort(key=lambda fi: (fi["path"].name != "index.qmd", fi["path"].name))
                for file_info in root_files:
                    href = get_clean_href(file_info)
                    if file_info["path"].name == "index.qmd":
                        contents.append({"text": file_info["title"], "href": href})
                    else:
                        contents.append(href)

                # Then add subdirectory groups, sorted by directory name
                for subdir in sorted(subdirs):
                    dir_files = subdirs[subdir]
                    # Use the index.qmd title as the section title if present,
                    # otherwise derive from the directory name
                    section_title = subdir.replace("-", " ").replace("_", " ").title()
                    section_contents = []
                    for file_info in dir_files:
                        if file_info["path"].name == "index.qmd":
                            section_title = file_info["title"]
                        else:
                            section_contents.append(get_clean_href(file_info))

                    contents.append({"section": section_title, "contents": section_contents})
            else:
                # All files at the root level — list in order
                for file_info in files_info:
                    contents.append(get_clean_href(file_info))

        return {
            "id": "user-guide",
            "title": "User Guide",
            "contents": contents,
        }

    def _rewrite_sidebar_first_entry(self, sidebar_config: dict, blended_first: str) -> None:
        """
        Rewrite the first sidebar entry to point to ``index.qmd``.

        In blended homepage mode the first UG page lives at the site root
        as ``index.qmd``, so the sidebar must link there instead of to
        ``user-guide/<page>.qmd``.

        Handles both flat and sectioned sidebar layouts by recursively
        searching for the first href match.

        Parameters
        ----------
        sidebar_config
            The user-guide sidebar dict (modified in place).
        blended_first
            The original href that was promoted (e.g. ``"user-guide/introduction.qmd"``).
        """
        contents = sidebar_config.get("contents", [])
        self._rewrite_href_recursive(contents, blended_first, "index.qmd")

    def _rewrite_href_recursive(self, items: list, old_href: str, new_href: str) -> bool:
        """Recursively find and replace the first matching href in sidebar items."""
        for item in items:
            if isinstance(item, dict):
                if item.get("href") == old_href:
                    item["href"] = new_href
                    return True
                # Check nested section contents
                nested = item.get("contents", [])
                if nested and self._rewrite_href_recursive(nested, old_href, new_href):
                    return True
            elif isinstance(item, str) and item == old_href:
                # Bare string entry — replace in parent list
                idx = items.index(item)
                items[idx] = {"text": "Home", "href": new_href}
                return True
        return False

    def _update_config_with_user_guide(self, user_guide_info: dict) -> None:
        """
        Update _quarto.yml with user guide sidebar and navbar.

        Parameters
        ----------
        user_guide_info
            User guide structure from _discover_user_guide.
        """
        quarto_yml = self.project_path / "_quarto.yml"
        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        if "website" not in config:
            config["website"] = {}

        # Generate and add/update user guide sidebar
        sidebar_config = self._generate_user_guide_sidebar(user_guide_info)

        # In blended homepage mode, rewrite the first sidebar entry to point
        # to index.qmd (the promoted first UG page) instead of user-guide/...
        blended_first = getattr(self, "_blended_first_page", None)
        if self._config.homepage == "user_guide" and blended_first:
            self._rewrite_sidebar_first_entry(sidebar_config, blended_first)

        if "sidebar" not in config["website"]:
            config["website"]["sidebar"] = []

        sidebar = config["website"]["sidebar"]

        # Remove existing user-guide sidebar if present
        sidebar = [s for s in sidebar if not (isinstance(s, dict) and s.get("id") == "user-guide")]

        # Add the new user guide sidebar
        sidebar.append(sidebar_config)
        config["website"]["sidebar"] = sidebar

        # Update navbar to include User Guide link (skip in blended homepage mode)
        if self._config.homepage != "user_guide" and "navbar" in config["website"]:
            navbar = config["website"]["navbar"]
            if "left" in navbar:
                # Check if User Guide link already exists
                has_user_guide = any(
                    isinstance(item, dict) and item.get("text") == "User Guide"
                    for item in navbar["left"]
                )
                if not has_user_guide:
                    # Find the position before "Reference"
                    insert_idx = 0  # Default: beginning of navbar
                    for i, item in enumerate(navbar["left"]):
                        if isinstance(item, dict) and item.get("text") == "Reference":
                            insert_idx = i
                            break

                    # Determine the href for User Guide (with clean filename)
                    if user_guide_info.get("has_index"):
                        user_guide_href = "user-guide/index.qmd"
                    else:
                        # Use the first file with clean filename
                        first_file = user_guide_info["files"][0]
                        rel_path = first_file["path"].relative_to(user_guide_info["source_dir"])
                        clean_filename = self._strip_numeric_prefix(rel_path.name)
                        clean_rel_path = rel_path.parent / clean_filename
                        user_guide_href = f"user-guide/{clean_rel_path}"

                    navbar["left"].insert(
                        insert_idx,
                        {
                            "text": "User Guide",
                            "href": user_guide_href,
                        },
                    )

        self._write_quarto_yml(quarto_yml, config)

    def _process_user_guide(self) -> bool:
        """
        Process user guide content: discover, copy, and update configuration.

        Returns
        -------
        bool
            True if user guide was processed, False otherwise.
        """
        # Discover user guide
        user_guide_info = self._discover_user_guide()
        if not user_guide_info:
            # Fallback: if homepage mode is "user_guide" but no UG pages exist,
            # warn and create a normal index from README instead.
            if self._config.homepage == "user_guide":
                print(
                    "   ⚠️  homepage: user_guide is set but no user guide pages found; "
                    "falling back to index mode"
                )
                self._homepage_fallback_to_index = True
                self._create_index_from_readme(force_rebuild=True)
                self._homepage_fallback_to_index = False
            return False

        print("\n📖 Processing User Guide...")

        is_explicit = user_guide_info.get("explicit", False)
        if is_explicit:
            print("   Using explicit section ordering from great-docs.yml")

        print(f"   Found {len(user_guide_info['files'])} page(s)")

        # Copy files to docs directory
        copied_files = self._copy_user_guide_to_docs(user_guide_info)
        print(f"   Copied {len(copied_files)} file(s) to docs/user-guide/")

        # In "user_guide" homepage mode, promote the first UG page to index.qmd
        if self._config.homepage == "user_guide":
            self._create_blended_index(user_guide_info, copied_files)

        # Update configuration
        self._update_config_with_user_guide(user_guide_info)

        # Report sections
        if user_guide_info["sections"]:
            section_names = list(user_guide_info["sections"].keys())
            print(f"   Sections: {', '.join(section_names)}")

        print("✅ User Guide configured")
        return True

    def _create_blended_index(self, user_guide_info: dict, copied_files: list[str]) -> None:
        """
        Create `index.qmd` from the first user-guide page (blended homepage mode).

        The first UG page becomes the site root `index.qmd` with the project
        metadata sidebar appended in the right margin.  The duplicate file
        under `user-guide/` is removed.

        Parameters
        ----------
        user_guide_info
            User guide structure from `_discover_user_guide()`.
        copied_files
            List of copied file paths relative to the docs dir (e.g.
            `["user-guide/introduction.qmd", ...]`).
        """
        if not user_guide_info["files"]:
            return

        first_file = user_guide_info["files"][0]
        is_explicit = user_guide_info.get("explicit", False)

        # Determine the filename of the first page in user-guide/
        source_dir = user_guide_info["source_dir"]
        try:
            rel_path = first_file["path"].relative_to(source_dir)
        except ValueError:
            rel_path = Path(first_file["path"].name)

        if is_explicit:
            dest_filename = rel_path.name
        else:
            dest_filename = self._strip_numeric_prefix(rel_path.name)

        first_ug_path = self.project_path / "user-guide" / dest_filename

        if not first_ug_path.exists():
            print(f"   ⚠️  First UG page '{first_ug_path}' not found for blended homepage")
            return

        # Read the first UG file content
        with open(first_ug_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Inject toc: false into frontmatter (bread-crumbs: false is already set
        # by _copy_user_guide_to_docs). Keep the original frontmatter title so
        # Quarto renders a proper title-block header matching other UG pages.
        content = self._add_frontmatter_option(content, "toc", False)

        # Build the metadata margin sidebar
        margin_content = self._build_metadata_margin()

        # Build hero section for blended homepage
        hero_html, _ = self._build_hero_section()

        # Split content into frontmatter and body. Headings are NOT bumped
        # here, unlike _create_index_from_readme, because UG pages already
        # have a frontmatter title. Quarto absorbs the first body `#`
        # heading (matching the title) and `shift-heading-level-by: -1`
        # promotes the remaining `##` → `<h1>`, `###` → `<h2>`, etc.
        # — exactly the same as every other UG page.
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_block = f"---{parts[1]}---\n"
                body = parts[2].lstrip("\n")
            else:
                frontmatter_block = ""
                body = content
        else:
            frontmatter_block = ""
            body = content

        # Strip the first `# …` heading from the body. The frontmatter
        # `title` already provides the title-block heading; keeping the
        # body `#` would render as a duplicate paragraph because
        # `shift-heading-level-by: -1` demotes it below heading level.
        import re

        body = re.sub(r"^#\s+[^\n]*\n?", "", body, count=1, flags=re.MULTILINE)

        # Build hero block for insertion
        hero_block = ""
        if hero_html:
            hero_block = f"""```{{=html}}
{hero_html}```

"""

        # Reassemble with margin content inserted after frontmatter
        if margin_content:
            blended_content = f"{frontmatter_block}\n{hero_block}::: {{.gd-meta-sidebar}}\n{margin_content}\n:::\n\n{body}"
        else:
            blended_content = f"{frontmatter_block}\n{hero_block}{body}"

        # Write to index.qmd at the site root
        index_qmd = self.project_path / "index.qmd"
        with open(index_qmd, "w", encoding="utf-8") as f:
            f.write(blended_content)

        # Remove the duplicate from user-guide/
        first_ug_path.unlink()

        # Track the first file's destination filename for sidebar adjustment
        self._blended_first_page = f"user-guide/{dest_filename}"

        print("   📄 Blended homepage: first UG page → index.qmd")

    def _get_source_location(self, package_name: str, item_name: str) -> dict | None:
        """
        Get source file and line numbers for a class, method, or function.

        Uses griffe for static analysis to avoid import side effects.

        Parameters
        ----------
        package_name
            The name of the package containing the item.
        item_name
            The fully qualified name of the item (e.g., "ClassName" or "ClassName.method_name").

        Returns
        -------
        dict | None
            Dictionary with file path and line numbers, or None if not found.
        """
        try:
            import griffe

            normalized_name = package_name.replace("-", "_")

            # Load the package with griffe
            try:
                pkg = griffe.load(normalized_name)
            except Exception:
                return None

            # Navigate to the item (handle dotted names like "ClassName.method")
            parts = item_name.split(".")
            obj = pkg

            for part in parts:
                if part not in obj.members:
                    return None
                obj = obj.members[part]

            # Get source information
            if not hasattr(obj, "lineno") or obj.lineno is None:
                return None  # pragma: no cover

            # Get the file path relative to package root
            if hasattr(obj, "filepath") and obj.filepath:
                filepath = str(obj.filepath)
            else:
                return None

            # Get end line number
            end_lineno = getattr(obj, "endlineno", obj.lineno)

            return {
                "file": filepath,
                "start_line": obj.lineno,
                "end_line": end_lineno or obj.lineno,
            }

        except ImportError:  # pragma: no cover
            return None  # pragma: no cover
        except Exception:  # pragma: no cover
            return None  # pragma: no cover

    def _build_github_source_url(
        self, source_location: dict, branch: str | None = None
    ) -> str | None:
        """
        Build a GitHub URL for viewing source code at specific line numbers.

        Parameters
        ----------
        source_location
            Dictionary with file path and line numbers.
        branch
            Git branch/tag to link to. If None, attempts to detect from git
            or falls back to 'main'.

        Returns
        -------
        str | None
            Full GitHub URL with line anchors, or None if repo info not available.
        """
        owner, repo, base_url = self._get_github_repo_info()

        if not base_url:
            return None

        # Determine the branch/ref to use
        if branch is None:
            branch = self._detect_git_ref()  # pragma: no cover

        # Get the file path relative to the repository root
        filepath = source_location.get("file", "")
        package_root = self._find_package_root()

        # Handle source path configuration for monorepos
        metadata = self._get_package_metadata()
        source_path = metadata.get("source_link_path")

        if source_path:
            # Custom source path specified (for monorepos)
            relative_path = f"{source_path}/{Path(filepath).name}"
        else:
            # Try to make the path relative to package root
            try:
                filepath_obj = Path(filepath)
                if filepath_obj.is_absolute():
                    relative_path = str(filepath_obj.relative_to(package_root))
                else:
                    relative_path = filepath
            except ValueError:
                # Path is not relative to package root, use as-is
                relative_path = filepath

        # Build the URL with line number anchors
        start_line = source_location.get("start_line", 1)
        end_line = source_location.get("end_line", start_line)

        url = f"{base_url}/blob/{branch}/{relative_path}"

        if start_line == end_line:
            url += f"#L{start_line}"
        else:
            url += f"#L{start_line}-L{end_line}"

        return url

    def _detect_git_ref(self) -> str:
        """
        Detect the current git branch or tag.

        Returns
        -------
        str
            The current branch/tag name, or 'main' as fallback.
        """
        import subprocess

        package_root = self._find_package_root()

        # First check if there's a configured branch in metadata
        metadata = self._get_package_metadata()
        configured_branch = metadata.get("source_link_branch")
        if configured_branch:
            return configured_branch

        try:
            # Try to get the current tag first (for versioned docs)
            result = subprocess.run(
                ["git", "describe", "--tags", "--exact-match"],
                cwd=package_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()

            # Fall back to branch name
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=package_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                if branch != "HEAD":
                    return branch

        except Exception:
            pass

        # Default fallback
        return "main"

    def _generate_source_links_json(self, package_name: str) -> None:
        """
        Generate a JSON file mapping object names to their GitHub source URLs.

        This file is used by the post-render script to inject source links
        into the HTML documentation.

        Parameters
        ----------
        package_name
            The name of the package to generate source links for.
        """
        import json

        metadata = self._get_package_metadata()

        # Check if source links are enabled
        if not metadata.get("source_link_enabled", True):
            print("Source links disabled in configuration")
            return

        # Check if we have GitHub repo info
        owner, repo, base_url = self._get_github_repo_info()
        if not base_url:
            print("No GitHub repository URL found, skipping source links")
            return

        print(f"Generating source links for {package_name}...")

        source_links: dict[str, dict] = {}
        normalized_name = package_name.replace("-", "_")

        # Get all exports
        exports = self._get_package_exports(package_name)
        if not exports:
            return

        # Get branch for source links
        branch = self._detect_git_ref()
        print(f"Using git ref: {branch}")

        # Generate source links for each export
        for item_name in exports:
            source_loc = self._get_source_location(normalized_name, item_name)
            if source_loc:
                github_url = self._build_github_source_url(source_loc, branch)
                if github_url:
                    source_links[item_name] = {
                        "url": github_url,
                        "file": source_loc.get("file", ""),
                        "start_line": source_loc.get("start_line", 0),
                        "end_line": source_loc.get("end_line", 0),
                    }

            # Also get source links for methods of classes
            categories = self._categorize_api_objects(package_name, [item_name])
            if item_name in categories.get("all_classes", []):
                method_names = categories.get("class_method_names", {}).get(item_name, [])
                for method_name in method_names:
                    full_name = f"{item_name}.{method_name}"
                    method_loc = self._get_source_location(normalized_name, full_name)
                    if method_loc:
                        method_url = self._build_github_source_url(method_loc, branch)
                        if method_url:
                            source_links[full_name] = {
                                "url": method_url,
                                "file": method_loc.get("file", ""),
                                "start_line": method_loc.get("start_line", 0),
                                "end_line": method_loc.get("end_line", 0),
                            }

        # Write to JSON file in the docs directory
        source_links_path = self.project_path / "_source_links.json"
        with open(source_links_path, "w", encoding="utf-8") as f:
            json.dump(source_links, f, indent=2)

        print(f"Generated source links for {len(source_links)} items")

    def _find_package_init(self, package_name: str) -> Path | None:
        """
        Find the __init__.py file for a package, searching common locations.

        This handles packages with non-standard structures like Rust bindings
        that may have their Python code in subdirectories like python/, src/, etc.

        Parameters
        ----------
        package_name
            The name of the package to find.

        Returns
        -------
        Path | None
            Path to the __init__.py file, or None if not found.
        """
        # Normalize package name (replace dashes with underscores)
        normalized_name = package_name.replace("-", "_")

        # First, try to get explicit package info from pyproject.toml
        package_root = self._find_package_root()
        pyproject_path = package_root / "pyproject.toml"
        explicit_packages = []

        if pyproject_path.exists():
            import tomllib

            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)

                # Check [tool.setuptools.packages] for explicit package list
                setuptools = data.get("tool", {}).get("setuptools", {})
                if "packages" in setuptools:
                    explicit_packages = setuptools["packages"]
                elif "packages" in setuptools.get("find", {}):  # pragma: no cover
                    # [tool.setuptools.packages.find] with where
                    where = setuptools.get("find", {}).get("where", ["."])
                    if isinstance(where, str):
                        where = [where]
                    for base_dir in where:
                        base_path = package_root / base_dir
                        if base_path.exists():
                            # Look for packages in this directory
                            for item in base_path.iterdir():
                                if item.is_dir() and (item / "__init__.py").exists():
                                    if not item.name.startswith((".", "_", "test")):
                                        explicit_packages.append(item.name)

                # Check [tool.hatch.build.targets.wheel] for hatch projects
                hatch_packages = (
                    data.get("tool", {})
                    .get("hatch", {})
                    .get("build", {})
                    .get("targets", {})
                    .get("wheel", {})
                    .get("packages", [])
                )
                if hatch_packages:
                    explicit_packages.extend(hatch_packages)

            except Exception:  # pragma: no cover
                pass

        # Build search paths, prioritizing explicit packages from pyproject.toml
        search_paths = []

        # Add explicit packages first (from pyproject.toml config)
        for pkg in explicit_packages:
            # Handle "src/package" style paths
            if "/" in pkg:
                search_paths.append(package_root / pkg)
            else:
                search_paths.append(package_root / pkg)
                search_paths.append(package_root / "src" / pkg)

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
                    with open(init_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "__version__" in content or "__all__" in content:
                            return init_file
                except Exception:  # pragma: no cover
                    continue

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

    def _parse_package_exports(self, package_name: str) -> list | None:
        """
        Parse __all__ from package's __init__.py to get public API.

        Also checks for exclude in great-docs.yml to filter out
        non-documentable items.

        Parameters
        ----------
        package_name
            The name of the package to parse.

        Returns
        -------
        list | None
            List of public names from __all__ (filtered by exclusions), or None if not found.
        """
        # Find the package's __init__.py file
        init_file = self._find_package_init(package_name)
        if not init_file:
            # Show both the original and normalized name for clarity
            normalized = package_name.replace("-", "_")
            if normalized != package_name:
                print(
                    f"Could not locate __init__.py for package '{package_name}' (module name: '{normalized}')"
                )
                print(f"Tip: Ensure a '{normalized}/' directory exists with an __init__.py file")
            else:
                print(f"Could not locate __init__.py for package '{package_name}'")
            return None

        print(f"Found package __init__.py at: {init_file.relative_to(self.project_root)}")

        # Get exclusions from great-docs.yml
        metadata = self._get_package_metadata()
        config_exclude = metadata.get("exclude", [])

        try:
            with open(init_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Try to extract __all__ using AST (safer than eval)
            import ast

            tree = ast.parse(content)

            all_exports = None

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        # Extract __all__
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, ast.List):
                                all_exports = []
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        all_exports.append(elt.value)

            if all_exports:
                print(f"Successfully parsed __all__ with {len(all_exports)} exports")

                # Filter out excluded items from great-docs.yml
                if config_exclude:
                    filtered = [e for e in all_exports if e not in config_exclude]
                    excluded_count = len(all_exports) - len(filtered)
                    if excluded_count > 0:
                        print(
                            f"Filtered out {excluded_count} item(s) from great-docs.yml exclude: {', '.join(config_exclude)}"
                        )
                    return filtered
                else:
                    return all_exports

            print("No __all__ definition found in __init__.py")
            return None
        except Exception as e:  # pragma: no cover
            print(f"Error parsing __all__: {type(e).__name__}: {e}")
            return None

    # Auto-excluded names that are typically not meant for documentation
    # These are common internal/utility exports that most packages don't want documented
    AUTO_EXCLUDE = {
        # CLI and entry points
        "main",  # CLI entry point function
        "cli",  # CLI module
        # Version and metadata
        "version",  # Version string/function
        "VERSION",  # Uppercase version constant
        "VERSION_INFO",  # Version info tuple
        # Common module re-exports
        "core",  # Core module
        "utils",  # Utilities module
        "helpers",  # Helpers module
        "constants",  # Constants module
        "config",  # Config module
        "settings",  # Settings module
        # Standard library re-exports
        "PackageNotFoundError",  # importlib.metadata exception
        "typing",  # typing module re-export
        "annotations",  # annotations module re-export
        "TYPE_CHECKING",  # typing.TYPE_CHECKING constant
        # Logging
        "logger",  # Module-level logger instance
        "log",  # Alternative logger name
        "logging",  # logging module re-export
    }

    def _discover_package_exports(self, package_name: str) -> list | None:
        """
        Discover public API objects using griffe introspection.

        This method uses griffe (the project's introspection module) to statically analyze the
        package and discover all public objects by filtering out private/internal names (those
        starting with underscore).

        Auto-excludes common internal names (see `AUTO_EXCLUDE`). Additional items can be
        excluded via the `exclude` option in `great-docs.yml`.

        Parameters
        ----------
        package_name
            The name of the package to discover exports from.

        Returns
        -------
        list | None
            List of public names discovered (filtered by exclusions), or `None` if discovery failed.
        """
        try:
            import griffe

            # Normalize package name (replace dashes with underscores)
            normalized_name = package_name.replace("-", "_")

            # Load the package using griffe
            try:
                pkg = griffe.load(normalized_name)
            except Exception as e:
                print(f"Warning: Could not load package with griffe ({type(e).__name__})")
                if package_name != normalized_name:
                    print(
                        f"   (Looking for module '{normalized_name}' from project '{package_name}')"
                    )
                return None

            # Get all members from the package (equivalent to dir(package))
            all_members = list(pkg.members.keys())

            # If the package defines __all__, restrict to those names
            if pkg.exports:
                public_members = [name for name in all_members if name in set(pkg.exports)]
                print(f"Using __all__ with {len(public_members)} exports")
            else:
                # Filter out private names (starting with underscore)
                # This also filters out dunder names like __version__, __all__, etc.
                public_members = [name for name in all_members if not name.startswith("_")]
                print(f"Discovered {len(public_members)} public names")

            # Get config from great-docs.yml
            metadata = self._get_package_metadata()
            config_exclude = set(metadata.get("exclude", []))

            # Apply auto-exclusions
            auto_excluded_found = [name for name in public_members if name in self.AUTO_EXCLUDE]
            if auto_excluded_found:
                print(
                    f"Auto-excluding {len(auto_excluded_found)} item(s): "
                    f"{', '.join(sorted(auto_excluded_found))}"
                )

            # Combine all exclusions (auto + user-specified)
            all_exclude = self.AUTO_EXCLUDE | config_exclude

            # Filter out excluded items
            filtered = [name for name in public_members if name not in all_exclude]

            # Report user-specified exclusions separately
            if config_exclude:
                user_excluded_found = [
                    name
                    for name in public_members
                    if name in config_exclude and name not in self.AUTO_EXCLUDE
                ]
                if user_excluded_found:
                    print(
                        f"Filtered out {len(user_excluded_found)} item(s) from great-docs.yml exclude: "
                        f"{', '.join(sorted(user_excluded_found))}"
                    )

            # Super-safe filtering: try each object with the renderer's get_object
            # If it fails for ANY reason, exclude it; this catches:
            # - Cyclic aliases
            # - Unresolvable aliases
            # - Rust/PyO3 objects (KeyError)
            # - Submodules (which would cause recursive documentation issues)
            # - Any other edge case that would crash the API reference build
            safe_exports = []
            failed_exports = {}  # name -> error type for reporting

            # Try to use the renderer's `get_object()` for validation
            gd_get_object = None
            try:
                from functools import partial

                from great_docs._qrenderer.introspection import get_object as qd_get_object

                # uses `parser="numpy"` by default which affects alias resolution
                gd_get_object = partial(qd_get_object, dynamic=True, parser="numpy")
            except ImportError:  # pragma: no cover
                pass

            # Try to import the actual package to detect modules
            actual_package = None
            try:
                import importlib

                actual_package = importlib.import_module(normalized_name)
            except ImportError:  # pragma: no cover
                pass

            for name in filtered:
                # Check if this is a submodule; these are allowed through but will
                # be introspected by _categorize_api_objects to discover their
                # public classes and functions
                is_submodule = False

                # Check via runtime import first
                if actual_package is not None:
                    runtime_obj = getattr(actual_package, name, None)
                    if runtime_obj is not None:
                        import types

                        if isinstance(runtime_obj, types.ModuleType):
                            is_submodule = True

                # Fallback: check via griffe static analysis
                # (handles packages where __all__ lists submodules that aren't
                # auto-imported at runtime, e.g., lazy imports)
                if not is_submodule and name in pkg.members:
                    try:
                        if pkg.members[name].kind.value == "module":
                            is_submodule = True
                    except Exception:  # pragma: no cover
                        pass

                if is_submodule:
                    # Submodules are passed through to categorization which will
                    # drill into them to discover classes/functions
                    safe_exports.append(name)
                    continue

                if gd_get_object is not None:
                    try:
                        # Try to load the object exactly as the renderer would
                        qd_obj = gd_get_object(f"{normalized_name}:{name}")
                        # Try to access members to trigger any lazy resolution errors
                        _ = qd_obj.members
                        _ = qd_obj.kind

                        # Exclude stdlib / third-party re-exports: if the object
                        # is an alias whose canonical path lives outside this
                        # package, it is a re-export and should not be documented.
                        if (
                            hasattr(qd_obj, "is_alias")
                            and qd_obj.is_alias
                            and hasattr(qd_obj, "canonical_path")
                        ):
                            canon = qd_obj.canonical_path
                            if not canon.startswith(normalized_name + "."):
                                failed_exports[name] = "external re-export"
                                continue

                        safe_exports.append(name)
                    except griffe.CyclicAliasError:  # pragma: no cover
                        failed_exports[name] = "cyclic alias"
                    except griffe.AliasResolutionError:  # pragma: no cover
                        failed_exports[name] = "unresolvable alias"
                    except KeyError:  # pragma: no cover
                        failed_exports[name] = "not found (likely Rust/PyO3)"
                    except Exception as e:  # pragma: no cover
                        # Catch-all for any other error that would crash the build
                        failed_exports[name] = f"{type(e).__name__}"
                else:
                    # Fallback: use basic griffe check if renderer not available
                    try:
                        obj = pkg.members[name]
                        _ = obj.kind
                        _ = obj.members
                        safe_exports.append(name)
                    except Exception as e:  # pragma: no cover
                        failed_exports[name] = f"{type(e).__name__}"

            # Report excluded items grouped by error type
            if failed_exports:
                # Group by error type for cleaner output
                by_error = {}
                for name, error in failed_exports.items():
                    by_error.setdefault(error, []).append(name)

                for error_type, names in sorted(by_error.items()):
                    print(
                        f"Excluding {len(names)} object(s) ({error_type}): "
                        f"{', '.join(sorted(names))}"
                    )

            return safe_exports

        except ImportError:  # pragma: no cover
            print("Warning: griffe not available, cannot use dir() discovery")  # pragma: no cover
            return None  # pragma: no cover
        except Exception as e:  # pragma: no cover
            print(
                f"Error discovering exports via dir(): {type(e).__name__}: {e}"
            )  # pragma: no cover
            return None  # pragma: no cover

    def _detect_docstring_style(self, package_name: str) -> str:
        """
        Detect the docstring style used in a package.

        Analyzes docstrings from the package to determine if they use NumPy, Google,
        or Sphinx style formatting. The detection is based on characteristic patterns:

        - NumPy style: Uses `---` underlines under section headers (Parameters, Returns, etc.)
        - Google style: Uses section headers with colons but NO underlines (Args:, Returns:)
        - Sphinx style: Uses `:param:`, `:returns:`, etc. field markers

        Parameters
        ----------
        package_name
            The name of the package to analyze.

        Returns
        -------
        str
            The detected docstring style: "numpy", "google", or "sphinx".
            Defaults to "numpy" if detection is inconclusive.
        """
        try:
            import griffe

            # Normalize package name
            normalized_name = package_name.replace("-", "_")

            # Load the package using griffe
            try:
                pkg = griffe.load(normalized_name)
            except Exception as e:
                print(
                    f"Warning: Could not load package for docstring detection ({type(e).__name__})"
                )
                return "numpy"

            # Collect docstrings from the package
            docstrings = []

            def collect_docstrings(obj, depth=0):
                """Recursively collect docstrings from an object and its members."""
                if depth > 2:  # Limit recursion depth
                    return

                # Get the object's docstring
                if hasattr(obj, "docstring") and obj.docstring:
                    docstrings.append(obj.docstring.value)

                # Recurse into members
                if hasattr(obj, "members"):
                    for member in obj.members.values():
                        try:
                            # Skip aliases to avoid infinite loops
                            if hasattr(member, "is_alias") and member.is_alias:
                                continue
                            collect_docstrings(member, depth + 1)
                        except Exception:  # pragma: no cover
                            continue

            collect_docstrings(pkg)

            if not docstrings:
                print("No docstrings found, defaulting to numpy style")
                return "numpy"

            # Analyze docstrings for style indicators
            numpy_indicators = 0
            google_indicators = 0
            sphinx_indicators = 0

            # Patterns for detection
            # NumPy: section headers followed by dashes (e.g., "Parameters\n----------")
            numpy_section_pattern = re.compile(
                r"^\s*(Parameters|Returns|Yields|Raises|Examples|Attributes|Methods|See Also|Notes|References|Warnings)\s*\n\s*-{3,}",
                re.MULTILINE,
            )

            # Google: section headers with colons (e.g., "Args:", "Returns:")
            google_section_pattern = re.compile(
                r"^\s*(Args|Arguments|Returns|Yields|Raises|Examples|Attributes|Note|Notes|Todo|Warning|Warnings):\s*$",
                re.MULTILINE,
            )

            # Sphinx: field markers (e.g., ":param name:", ":returns:")
            sphinx_pattern = re.compile(
                r"^\s*:(param|type|returns|rtype|raises|var|ivar|cvar)\s",
                re.MULTILINE,
            )

            # Example blocks with >>> are common in both NumPy and Google styles
            # but the presence/absence of --- is the key differentiator

            for docstring in docstrings:
                if not docstring:
                    continue

                # Check for NumPy style (section + dashes)
                if numpy_section_pattern.search(docstring):
                    numpy_indicators += 1

                # Check for Google style (section headers with colons, no dashes)
                if google_section_pattern.search(docstring):
                    # Only count as Google if there are NO numpy-style dashes nearby
                    if not numpy_section_pattern.search(docstring):
                        google_indicators += 1

                # Check for Sphinx style
                if sphinx_pattern.search(docstring):
                    sphinx_indicators += 1

            # Determine the winner
            total_indicators = numpy_indicators + google_indicators + sphinx_indicators

            if total_indicators == 0:
                print("No clear docstring style detected, defaulting to numpy")
                return "numpy"

            # Report findings
            print(
                f"Docstring style detection: numpy={numpy_indicators}, "
                f"google={google_indicators}, sphinx={sphinx_indicators}"
            )

            # Return the style with most indicators
            if sphinx_indicators > numpy_indicators and sphinx_indicators > google_indicators:
                print("Detected sphinx docstring style")
                return "sphinx"
            elif google_indicators > numpy_indicators:
                print("Detected google docstring style")
                return "google"
            else:
                print("Detected numpy docstring style")
                return "numpy"

        except ImportError:  # pragma: no cover
            print("Warning: griffe not available for docstring detection, defaulting to numpy")
            return "numpy"
        except Exception as e:  # pragma: no cover
            print(f"Error detecting docstring style: {type(e).__name__}: {e}")
            return "numpy"

    def _detect_dynamic_mode(self, package_name: str) -> bool:
        """
        Detect whether dynamic introspection mode works for a package.

        This method tests if dynamic mode works by attempting to load objects
        with the renderer's get_object function in dynamic mode AND accessing their
        members (which is what triggers cyclic alias errors in some packages).

        Parameters
        ----------
        package_name
            The name of the package to test.

        Returns
        -------
        bool
            True if dynamic mode works, False if it causes errors.
        """
        if not package_name or not package_name.strip():
            return True

        try:
            import griffe

            from great_docs._qrenderer.introspection import get_object as qd_get_object
        except ImportError:  # pragma: no cover
            # If renderer isn't available, default to True (will fail at build time anyway)
            return True  # pragma: no cover

        # Normalize package name
        normalized_name = package_name.replace("-", "_")

        # Get a sample of exports to test
        try:
            pkg = griffe.load(normalized_name)
            exports = [
                name
                for name in list(pkg.members.keys())[:10]  # Test first 10
                if not name.startswith("_")
            ]
        except Exception:
            # Can't load package, default to True
            return True

        if not exports:
            return True

        # Test dynamic mode with a few exports
        # We need to actually access .members and .kind to trigger cyclic alias errors
        cyclic_errors = 0
        for name in exports[:5]:  # Test up to 5 exports
            try:
                obj = qd_get_object(f"{normalized_name}:{name}", dynamic=True)
                # Access .members to trigger cyclic alias resolution
                # This is what the renderer does when rendering docs
                _ = obj.members
                _ = obj.kind
                # For classes, try to access individual members too
                if hasattr(obj, "members") and obj.members:
                    for member_name, member in list(obj.members.items())[:3]:
                        try:
                            _ = member.kind
                        except griffe.CyclicAliasError:
                            cyclic_errors += 1  # pragma: no cover
                            break  # pragma: no cover
            except griffe.CyclicAliasError:
                cyclic_errors += 1  # pragma: no cover
            except Exception:  # pragma: no cover
                # Other errors don't necessarily mean dynamic mode won't work
                pass  # pragma: no cover

        if cyclic_errors > 0:
            print(f"Detected {cyclic_errors} cyclic alias error(s), using dynamic: false")
            return False
        else:
            print("Dynamic introspection mode works for this package")
            return True

    def _get_package_exports(self, package_name: str) -> list | None:
        """
        Get package exports using static analysis.

        Uses griffe to statically analyze the package and discover public objects.
        Falls back to parsing __all__ if griffe introspection fails.

        Parameters
        ----------
        package_name
            The name of the package to get exports from.

        Returns
        -------
        list | None
            List of exported/public names, or None if discovery failed.
        """
        exports = self._discover_package_exports(package_name)
        if exports is None:
            print("Falling back to __all__ discovery")
            return self._parse_package_exports(package_name)
        return exports

    # ── Exception base classes (used for sub-classification) ─────────────
    _EXCEPTION_BASES = frozenset(
        {
            "Exception",
            "BaseException",
            # Built-in error types
            "ArithmeticError",
            "AssertionError",
            "AttributeError",
            "BlockingIOError",
            "BrokenPipeError",
            "BufferError",
            "BytesWarning",
            "ChildProcessError",
            "ConnectionAbortedError",
            "ConnectionError",
            "ConnectionRefusedError",
            "ConnectionResetError",
            "DeprecationWarning",
            "EOFError",
            "EnvironmentError",
            "FileExistsError",
            "FileNotFoundError",
            "FloatingPointError",
            "FutureWarning",
            "GeneratorExit",
            "IOError",
            "ImportError",
            "ImportWarning",
            "IndentationError",
            "IndexError",
            "InterruptedError",
            "IsADirectoryError",
            "KeyError",
            "KeyboardInterrupt",
            "LookupError",
            "MemoryError",
            "ModuleNotFoundError",
            "NameError",
            "NotADirectoryError",
            "NotImplementedError",
            "OSError",
            "OverflowError",
            "PendingDeprecationWarning",
            "PermissionError",
            "ProcessLookupError",
            "RecursionError",
            "ReferenceError",
            "ResourceWarning",
            "RuntimeError",
            "RuntimeWarning",
            "StopAsyncIteration",
            "StopIteration",
            "SyntaxError",
            "SyntaxWarning",
            "SystemError",
            "SystemExit",
            "TabError",
            "TimeoutError",
            "TypeError",
            "UnboundLocalError",
            "UnicodeDecodeError",
            "UnicodeEncodeError",
            "UnicodeError",
            "UnicodeTranslationError",
            "UnicodeWarning",
            "UserWarning",
            "ValueError",
            "Warning",
            "ZeroDivisionError",
        }
    )

    # ── Enum base classes ────────────────────────────────────────────────
    _ENUM_BASES = frozenset(
        {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "ReprEnum", "EnumCheck"}
    )

    @staticmethod
    def _sub_classify_class(obj) -> str:
        """
        Determine the sub-type of a griffe `class` object.

        Returns one of: `dataclass`, `enum`, `exception`,
        `namedtuple`, `typeddict`, `protocol`, `abc`,
        or `class` (the generic fallback).

        Parameters
        ----------
        obj
            A griffe `Class` object (or `Alias` that resolves to one).

        Returns
        -------
        str
            The sub-classification label.
        """
        # --- labels (fast path) ---
        try:
            labels = obj.labels
        except Exception:
            labels = set()

        if "dataclass" in labels:
            return "dataclass"

        # --- bases (may be short names like "Enum" or dotted) ---
        try:
            bases = [str(b) for b in obj.bases]
        except Exception:
            bases = []

        # Normalize base names: "enum.IntEnum" → "IntEnum"
        short_bases = {b.rsplit(".", 1)[-1] for b in bases}

        if short_bases & GreatDocs._ENUM_BASES:
            return "enum"
        if short_bases & GreatDocs._EXCEPTION_BASES:
            return "exception"
        if "NamedTuple" in short_bases:
            return "namedtuple"
        if "TypedDict" in short_bases:
            return "typeddict"
        if "Protocol" in short_bases or "runtime_checkable" in short_bases:
            return "protocol"
        if short_bases & {"ABC", "ABCMeta"}:
            return "abc"

        # --- decorators (secondary check for ABC) ---
        try:
            decorators = [str(d.value) for d in obj.decorators]
        except Exception:
            decorators = []

        if any("abstractmethod" in d for d in decorators):
            return "abc"

        return "class"

    @staticmethod
    def _sub_classify_function(obj) -> str:
        """
        Determine the sub-type of a griffe `function` object.

        Returns one of: `async`, `classmethod`, `staticmethod`,
        `property`, or `function` (the generic fallback).

        Parameters
        ----------
        obj
            A griffe `Function` object (or `Alias` that resolves to one).

        Returns
        -------
        str
            The sub-classification label.
        """
        try:
            labels = obj.labels
        except Exception:
            labels = set()

        if "async" in labels:
            return "async"
        if "classmethod" in labels:
            return "classmethod"
        if "staticmethod" in labels:
            return "staticmethod"
        if "property" in labels:
            return "property"

        return "function"

    @staticmethod
    def _sub_classify_attribute(obj) -> str:
        """
        Determine the sub-type of a griffe `attribute` object.

        Returns one of: `type_alias`, `typevar`, or `constant`.

        Parameters
        ----------
        obj
            A griffe `Attribute` object (or `Alias` that resolves to one).

        Returns
        -------
        str
            The sub-classification label.
        """
        try:
            labels = obj.labels
        except Exception:
            labels = set()

        # griffe >= 0.40 has a dedicated "type alias" kind
        try:
            if obj.kind.value == "type alias":
                return "type_alias"
        except Exception:
            pass

        # Check annotation for TypeVar / ParamSpec / TypeVarTuple
        try:
            annotation = str(obj.annotation) if obj.annotation else ""
        except Exception:
            annotation = ""

        if "TypeVar" in annotation or "ParamSpec" in annotation or "TypeVarTuple" in annotation:
            return "typevar"

        # Heuristic: assignment like `MyAlias = list[int]` with no annotation
        # is often a type alias, but we can't reliably distinguish from a
        # constant without more context. Default to constant.
        return "constant"

    @staticmethod
    def _extract_constant_metadata(obj, name: str, categories: dict) -> None:
        """
        Extract value and type annotation from a griffe constant/attribute.

        Populates `categories["constant_metadata"][name]` with `"value"`
        and `"annotation"` strings when they are available and simple enough
        to display.

        Parameters
        ----------
        obj
            A griffe `Attribute` (or `Alias`) object.
        name
            The documented name of the constant.
        categories
            The mutable categories dict being built.
        """
        meta: dict[str, str] = {}
        try:
            if obj.value is not None:
                val = str(obj.value)
                # Only store "simple" values (literals, short collections).
                # Avoid huge reprs that would clutter the page.
                if len(val) <= 200:
                    meta["value"] = val
        except Exception:
            pass
        try:
            if obj.annotation is not None:
                meta["annotation"] = str(obj.annotation)
        except Exception:
            pass
        if meta:
            categories["constant_metadata"][name] = meta

    @staticmethod
    def _empty_categories() -> dict:
        """Return a fresh, empty categories dict with all keys."""
        return {
            # ── Class-like ──
            "classes": [],
            "dataclasses": [],
            "enums": [],
            "exceptions": [],
            "namedtuples": [],
            "typeddicts": [],
            "protocols": [],
            "abstract_classes": [],
            # ── Function-like ──
            "functions": [],
            "async_functions": [],
            # ── Data ──
            "constants": [],
            "type_aliases": [],
            # ── Catch-all ──
            "other": [],
            # ── Metadata ──
            "class_methods": {},
            "class_method_names": {},
            "class_member_types": {},
            "constant_metadata": {},
            "cyclic_alias_count": 0,
            # ── Convenience unions ──
            "all_classes": [],
            "all_functions": [],
        }

    def _write_object_types_json(self, categories: dict) -> None:
        """
        Write `_object_types.json` mapping each documented name to its type.

        The post-render script reads this file instead of relying on heuristics
        (e.g. first-character case) to classify objects for badges and
        parentheses.

        Parameters
        ----------
        categories
            Dictionary returned by `_categorize_api_objects`.
        """
        import json

        # Map each category key to the type label used by post-render
        _CATEGORY_TYPE_MAP = {
            "classes": "class",
            "dataclasses": "class",
            "enums": "enum",
            "exceptions": "exception",
            "namedtuples": "namedtuple",
            "typeddicts": "typeddict",
            "protocols": "protocol",
            "abstract_classes": "abc",
            "functions": "function",
            "async_functions": "function",
            "constants": "constant",
            "type_aliases": "type_alias",
            "other": "other",
        }

        object_types: dict[str, str] = {}

        for cat_key, obj_type in _CATEGORY_TYPE_MAP.items():
            for name in categories.get(cat_key, []):
                object_types[name] = obj_type

        # Methods: ClassName.method → specific type (classmethod/staticmethod/method)
        member_types = categories.get("class_member_types", {})
        for class_name, method_names in categories.get("class_method_names", {}).items():
            for method in method_names:
                key = f"{class_name}.{method}"
                # Use the specific sub-type if available, otherwise "method"
                object_types[key] = member_types.get(key, "method")

        # Properties and other descriptor members not in class_method_names
        # (e.g., @property attributes classified as "attribute" by griffe)
        for key, member_type in member_types.items():
            if key not in object_types:
                object_types[key] = member_type

        types_path = self.project_path / "_object_types.json"
        types_path.parent.mkdir(parents=True, exist_ok=True)
        with open(types_path, "w") as f:
            json.dump(object_types, f, indent=2, sort_keys=True)

        print(f"Wrote object type metadata ({len(object_types)} items) to {types_path}")

        # Write constant value metadata (sidecar file) when any constants have
        # extractable values or annotations.
        constant_metadata = categories.get("constant_metadata", {})
        if constant_metadata:
            values_path = self.project_path / "_constant_values.json"
            with open(values_path, "w") as f:
                json.dump(constant_metadata, f, indent=2, sort_keys=True)
            print(
                f"Wrote constant value metadata ({len(constant_metadata)} items) to {values_path}"
            )

    def _categorize_api_objects(self, package_name: str, exports: list) -> dict:
        """
        Categorize API objects using griffe introspection.

        Uses griffe (the project's introspection module) to analyze the package
        structure without importing it. This is safer and works with packages
        that have non-Python components (e.g., Rust bindings).

        Parameters
        ----------
        package_name
            The name of the package.
        exports
            List of exported names from __all__.

        Returns
        -------
        dict
            Dictionary with:
            - classes: list of regular class names
            - dataclasses: list of dataclass names
            - enums: list of enum class names
            - exceptions: list of exception class names
            - namedtuples: list of NamedTuple class names
            - typeddicts: list of TypedDict class names
            - protocols: list of Protocol class names
            - abstract_classes: list of ABC class names
            - functions: list of function names
            - async_functions: list of async function names
            - constants: list of module-level constant names
            - type_aliases: list of type alias names
            - other: list of other object names
            - class_methods: dict mapping class name to method count
            - class_method_names: dict mapping class name to list of method names
            - all_classes: list of ALL class-like names (union for compat)
            - all_functions: list of ALL function-like names (union for compat)
        """
        try:
            import griffe

            # Load the package using griffe
            normalized_name = package_name.replace("-", "_")

            # Try to use the renderer's `get_object()` for validation
            gd_get_object = None
            try:
                from functools import partial

                from great_docs._qrenderer.introspection import get_object as qd_get_object

                gd_get_object = partial(qd_get_object, dynamic=True, parser="numpy")
            except ImportError:  # pragma: no cover
                pass  # pragma: no cover

            # Try to load the package with griffe
            try:
                pkg = griffe.load(normalized_name)
            except Exception as e:
                print(f"Warning: Could not load package with griffe ({type(e).__name__})")
                # Fallback: use importlib + inspect to categorize exports
                return self._categorize_api_objects_fallback(normalized_name, exports)

            categories = self._empty_categories()
            failed_introspection = []
            cyclic_aliases = []

            # Skip common metadata variables
            skip_names = {"__version__", "__author__", "__email__", "__all__"}

            for name in exports:
                # Skip metadata variables
                if name in skip_names:
                    continue

                try:
                    # Get the object from the loaded package
                    if name not in pkg.members:
                        categories["other"].append(name)
                        failed_introspection.append(name)
                        continue

                    obj = pkg.members[name]

                    # Categorize based on griffe's kind
                    # Note: Accessing obj.kind or obj.members on an Alias can trigger
                    # resolution which may raise CyclicAliasError or AliasResolutionError
                    if obj.kind.value == "class":
                        # Sub-classify the class
                        sub = self._sub_classify_class(obj)
                        _CLASS_SUB_MAP = {
                            "dataclass": "dataclasses",
                            "enum": "enums",
                            "exception": "exceptions",
                            "namedtuple": "namedtuples",
                            "typeddict": "typeddicts",
                            "protocol": "protocols",
                            "abc": "abstract_classes",
                            "class": "classes",
                        }
                        cat_key = _CLASS_SUB_MAP.get(sub, "classes")
                        categories[cat_key].append(name)
                        # Get documentable methods (exclude private methods but include
                        # documented dunder methods like __repr__, __eq__, __len__, etc.)
                        # __init__ is excluded because its parameters are already shown
                        # in the class constructor signature.
                        # We need to handle each member individually to catch cyclic aliases
                        # AND validate each method with get_object to catch type hint issues
                        # Collect (method_name, lineno) tuples to preserve source order
                        _INIT_DUNDERS = {"__init__", "__new__", "__init_subclass__"}
                        method_entries = []
                        skipped_methods = []
                        try:
                            for member_name, member in obj.members.items():
                                if member_name.startswith("__") and member_name.endswith("__"):
                                    # Dunder method: skip constructor-related ones,
                                    # include the rest (they have user-written docstrings)
                                    if member_name in _INIT_DUNDERS:
                                        continue
                                elif member_name.startswith("_"):
                                    # Single-underscore private method: skip
                                    continue
                                try:
                                    # Accessing member.kind can trigger alias resolution
                                    if member.kind.value in ("function", "method"):
                                        # Sub-classify to detect classmethod/staticmethod/property
                                        member_sub = self._sub_classify_function(member)
                                        # Get line number for source ordering
                                        lineno = getattr(member, "lineno", float("inf"))
                                        # Validate with get_object if available
                                        if gd_get_object is not None:
                                            try:
                                                qd_obj = gd_get_object(
                                                    f"{normalized_name}:{name}.{member_name}"
                                                )
                                                # Try to access properties that might fail
                                                _ = qd_obj.members
                                                _ = qd_obj.kind
                                                method_entries.append((member_name, lineno))
                                                # Store sub-type for classmethod/staticmethod/property
                                                if member_sub in (
                                                    "classmethod",
                                                    "staticmethod",
                                                    "property",
                                                ):
                                                    categories["class_member_types"][
                                                        f"{name}.{member_name}"
                                                    ] = member_sub
                                            except Exception:  # pragma: no cover
                                                # Method can't be documented by the renderer
                                                skipped_methods.append(
                                                    member_name
                                                )  # pragma: no cover
                                        else:
                                            method_entries.append((member_name, lineno))
                                            # Store sub-type for classmethod/staticmethod/property
                                            if member_sub in (
                                                "classmethod",
                                                "staticmethod",
                                                "property",
                                            ):
                                                categories["class_member_types"][
                                                    f"{name}.{member_name}"
                                                ] = member_sub
                                    elif member.kind.value == "attribute":
                                        # Check if this attribute is a @property descriptor
                                        try:
                                            member_labels = member.labels
                                        except Exception:
                                            member_labels = set()
                                        if "property" in member_labels:
                                            categories["class_member_types"][
                                                f"{name}.{member_name}"
                                            ] = "property"
                                except (
                                    griffe.CyclicAliasError,
                                    griffe.AliasResolutionError,
                                ):  # pragma: no cover
                                    # Skip cyclic/unresolvable class members
                                    skipped_methods.append(member_name)  # pragma: no cover
                                except Exception:  # pragma: no cover
                                    # Skip members that can't be introspected
                                    pass  # pragma: no cover
                        except (
                            griffe.CyclicAliasError,
                            griffe.AliasResolutionError,
                        ):  # pragma: no cover
                            # If we can't even iterate members, class has issues
                            skipped_methods.append("<members>")  # pragma: no cover

                        # Sort by line number to preserve source file order
                        method_entries.sort(key=lambda x: x[1])
                        method_names = [entry[0] for entry in method_entries]

                        if skipped_methods:
                            print(
                                f"{name}: class with {len(method_names)} public methods "
                                f"(skipped {len(skipped_methods)} undocumentable method(s): "
                                f"{', '.join(skipped_methods[:3])}{'...' if len(skipped_methods) > 3 else ''})"
                            )
                        else:
                            print(f"{name}: class with {len(method_names)} public methods")

                        categories["class_methods"][name] = len(method_names)
                        categories["class_method_names"][name] = method_names
                    elif obj.kind.value == "function":
                        # Sub-classify the function
                        sub = self._sub_classify_function(obj)
                        if sub == "async":
                            categories["async_functions"].append(name)
                        else:
                            categories["functions"].append(name)
                    elif obj.kind.value in ("attribute", "type alias"):
                        sub = self._sub_classify_attribute(obj)
                        if sub == "type_alias":
                            categories["type_aliases"].append(name)
                        elif sub == "typevar":
                            categories["type_aliases"].append(name)
                        else:
                            categories["constants"].append(name)
                            self._extract_constant_metadata(obj, name, categories)
                    elif obj.kind.value == "module":
                        # Drill into the module to discover its public classes and functions
                        # Use qualified names like "module.ClassName" so the renderer resolves
                        # them relative to the package (e.g., dateutil:easter.easter)
                        module_had_members = False
                        # Build a set of short names already in the exports list so we
                        # can skip submodule members that are re-exported at the package
                        # level (avoids duplicate entries like both "Model" and
                        # "models.Model" appearing in the reference).
                        _exports_set = set(exports)
                        try:
                            for member_name, member in obj.members.items():
                                if member_name.startswith("_"):
                                    continue
                                # If this member is already re-exported at the
                                # package level (i.e. its short name is in
                                # __all__ / exports), skip the qualified version
                                # to avoid duplicate reference entries.
                                if member_name in _exports_set:
                                    continue
                                try:
                                    member_kind = member.kind.value
                                except (
                                    griffe.CyclicAliasError,
                                    griffe.AliasResolutionError,
                                ):  # pragma: no cover
                                    continue  # pragma: no cover
                                except Exception:  # pragma: no cover
                                    continue  # pragma: no cover

                                qualified = f"{name}.{member_name}"

                                # Validate with get_object if available
                                # Try dynamic first, fall back to static if it fails
                                if gd_get_object is not None:
                                    try:
                                        qd_obj = gd_get_object(f"{normalized_name}:{qualified}")
                                        _ = qd_obj.kind
                                    except Exception:  # pragma: no cover
                                        # Dynamic mode failed; try static (no dynamic=True)
                                        try:
                                            from great_docs._qrenderer.introspection import (
                                                get_object as qd_get,
                                            )

                                            qd_obj = qd_get(
                                                f"{normalized_name}:{qualified}",
                                                parser="numpy",
                                            )
                                            _ = qd_obj.kind
                                        except Exception:  # pragma: no cover
                                            # Neither mode works; skip this member
                                            continue  # pragma: no cover

                                if member_kind == "class":
                                    sub = self._sub_classify_class(member)
                                    _CLASS_SUB_MAP = {
                                        "dataclass": "dataclasses",
                                        "enum": "enums",
                                        "exception": "exceptions",
                                        "namedtuple": "namedtuples",
                                        "typeddict": "typeddicts",
                                        "protocol": "protocols",
                                        "abc": "abstract_classes",
                                        "class": "classes",
                                    }
                                    cat_key = _CLASS_SUB_MAP.get(sub, "classes")
                                    categories[cat_key].append(qualified)
                                    module_had_members = True

                                    # Count public methods for classes inside modules
                                    method_entries = []
                                    try:
                                        for meth_name, meth in member.members.items():
                                            if meth_name.startswith("_"):
                                                continue
                                            try:
                                                if meth.kind.value in ("function", "method"):
                                                    # Sub-classify for descriptor types
                                                    meth_sub = self._sub_classify_function(meth)
                                                    lineno = getattr(meth, "lineno", float("inf"))
                                                    if gd_get_object is not None:
                                                        try:
                                                            qd_m = gd_get_object(
                                                                f"{normalized_name}:{qualified}.{meth_name}"
                                                            )
                                                            _ = qd_m.kind
                                                            method_entries.append(
                                                                (meth_name, lineno)
                                                            )
                                                            # Store sub-type
                                                            if meth_sub in (
                                                                "classmethod",
                                                                "staticmethod",
                                                                "property",
                                                            ):
                                                                categories["class_member_types"][
                                                                    f"{qualified}.{meth_name}"
                                                                ] = meth_sub
                                                        except Exception:  # pragma: no cover
                                                            # Dynamic failed; try static
                                                            try:
                                                                from great_docs._qrenderer.introspection import (
                                                                    get_object as qd_get,
                                                                )

                                                                qd_m = qd_get(
                                                                    f"{normalized_name}:{qualified}.{meth_name}",
                                                                    parser="numpy",
                                                                )
                                                                _ = qd_m.kind
                                                                method_entries.append(
                                                                    (meth_name, lineno)
                                                                )
                                                                # Store sub-type
                                                                if meth_sub in (
                                                                    "classmethod",
                                                                    "staticmethod",
                                                                    "property",
                                                                ):
                                                                    categories[
                                                                        "class_member_types"
                                                                    ][
                                                                        f"{qualified}.{meth_name}"
                                                                    ] = meth_sub
                                                            except Exception:  # pragma: no cover
                                                                pass  # pragma: no cover
                                                    else:
                                                        method_entries.append((meth_name, lineno))
                                                        # Store sub-type
                                                        if meth_sub in (
                                                            "classmethod",
                                                            "staticmethod",
                                                            "property",
                                                        ):
                                                            categories["class_member_types"][
                                                                f"{qualified}.{meth_name}"
                                                            ] = meth_sub
                                                elif meth.kind.value == "attribute":
                                                    # Check if attribute is a @property
                                                    try:
                                                        meth_labels = meth.labels
                                                    except Exception:  # pragma: no cover
                                                        meth_labels = set()  # pragma: no cover
                                                    if "property" in meth_labels:
                                                        categories["class_member_types"][
                                                            f"{qualified}.{meth_name}"
                                                        ] = "property"
                                            except (
                                                griffe.CyclicAliasError,
                                                griffe.AliasResolutionError,
                                            ):  # pragma: no cover
                                                pass  # pragma: no cover
                                            except Exception:  # pragma: no cover
                                                pass  # pragma: no cover
                                    except (
                                        griffe.CyclicAliasError,
                                        griffe.AliasResolutionError,
                                    ):  # pragma: no cover
                                        pass  # pragma: no cover

                                    method_entries.sort(key=lambda x: x[1])
                                    method_names_list = [e[0] for e in method_entries]
                                    categories["class_methods"][qualified] = len(method_names_list)
                                    categories["class_method_names"][qualified] = method_names_list
                                    print(
                                        f"{qualified}: class with "
                                        f"{len(method_names_list)} public methods"
                                    )

                                elif member_kind == "function":
                                    sub = self._sub_classify_function(member)
                                    if sub == "async":
                                        categories["async_functions"].append(qualified)
                                    else:
                                        categories["functions"].append(qualified)
                                    module_had_members = True

                                elif member_kind in ("attribute", "type alias"):
                                    sub = self._sub_classify_attribute(member)
                                    if sub == "type_alias":
                                        categories["type_aliases"].append(qualified)
                                    elif sub == "typevar":
                                        categories["type_aliases"].append(qualified)
                                    else:
                                        categories["constants"].append(qualified)
                                        self._extract_constant_metadata(
                                            member, qualified, categories
                                        )
                                    module_had_members = True

                        except (
                            griffe.CyclicAliasError,
                            griffe.AliasResolutionError,
                        ):
                            # Can't iterate module members
                            pass

                        if not module_had_members:
                            # Module has no documentable public members
                            categories["other"].append(name)
                    else:
                        # Aliases and other unknown kinds
                        categories["other"].append(name)

                except griffe.CyclicAliasError:  # pragma: no cover
                    # Cyclic alias detected (e.g., re-exported symbol pointing to itself)
                    # This can happen with complex re-export patterns
                    # Do NOT add to categories (these must be excluded entirely)
                    print(f"  Warning: Cyclic alias detected for '{name}', excluding from docs")
                    cyclic_aliases.append(name)
                except griffe.AliasResolutionError:  # pragma: no cover
                    # Alias could not be resolved (target not found)
                    # Do NOT add to categories (these must be excluded entirely)
                    print(f"  Warning: Could not resolve alias for '{name}', excluding from docs")
                    failed_introspection.append(name)
                except Exception as e:  # pragma: no cover
                    # If introspection fails for a specific object, still include it
                    print(f"  Warning: Could not introspect '{name}': {type(e).__name__}")
                    categories["other"].append(name)
                    failed_introspection.append(name)

            if cyclic_aliases:  # pragma: no cover
                print(f"Note: Excluded {len(cyclic_aliases)} cyclic alias(es) from documentation")
                categories["cyclic_alias_count"] = len(cyclic_aliases)

            if failed_introspection:  # pragma: no cover
                print(
                    f"Note: Could not introspect {len(failed_introspection)} item(s), categorizing as 'Other'"
                )

            # Build convenience union keys for backward compatibility
            categories["all_classes"] = (
                categories["classes"]
                + categories["dataclasses"]
                + categories["enums"]
                + categories["exceptions"]
                + categories["namedtuples"]
                + categories["typeddicts"]
                + categories["protocols"]
                + categories["abstract_classes"]
            )
            categories["all_functions"] = categories["functions"] + categories["async_functions"]

            return categories

        except ImportError:  # pragma: no cover
            print("Warning: griffe not available, using fallback categorization")
            # Fallback: use importlib + inspect to categorize exports
            normalized_name = package_name.replace("-", "_")
            return self._categorize_api_objects_fallback(normalized_name, exports)

    def _categorize_api_objects_fallback(self, package_name: str, exports: list[str]) -> dict:
        """
        Categorize API objects using importlib + inspect when griffe is unavailable.

        This fallback is used when griffe cannot load the package (e.g. during
        `great-docs init` when the package is not yet on sys.path). It
        attempts to import the module via `importlib` and uses `inspect` to
        distinguish functions from classes and other objects.

        Parameters
        ----------
        package_name
            The normalized importable package name.
        exports
            List of exported names to categorize.

        Returns
        -------
        dict
            Categories dictionary with the same structure as
            ``_categorize_api_objects``.
        """
        import inspect

        skip_names = {"__version__", "__author__", "__email__", "__all__"}
        filtered_exports = [e for e in exports if e not in skip_names]
        categories = self._empty_categories()

        try:
            mod = __import__(package_name)
        except Exception:
            # The normalized project name may not match the actual module name.
            # Try to discover the correct module by scanning the package root for
            # Python packages (dirs with __init__.py), just like _get_package_exports.
            mod = None
            try:
                package_root = self._find_package_root()
                for child in sorted(package_root.iterdir()):
                    if (
                        child.is_dir()
                        and not child.name.startswith((".", "_"))
                        and child.name not in ("great-docs", "docs", "tests", "test")
                        and (child / "__init__.py").exists()
                    ):
                        try:
                            mod = __import__(child.name)
                            print(
                                f"  Fallback: imported '{child.name}' "
                                f"(project name was '{package_name}')"
                            )
                            break
                        except Exception:  # pragma: no cover
                            continue  # pragma: no cover
            except Exception:  # pragma: no cover
                pass  # pragma: no cover

            if mod is None:
                # Neither the normalized name nor any discovered module worked
                categories["other"] = filtered_exports
                return categories

        for name in filtered_exports:
            obj = getattr(mod, name, None)
            if obj is None:
                categories["other"].append(name)
                continue

            if inspect.isclass(obj):
                if issubclass(obj, Exception):
                    categories["exceptions"].append(name)
                elif hasattr(obj, "__dataclass_fields__"):
                    categories["dataclasses"].append(name)
                else:
                    categories["classes"].append(name)
            elif inspect.isfunction(obj) or inspect.isbuiltin(obj):
                if inspect.iscoroutinefunction(obj):
                    categories["async_functions"].append(name)
                else:
                    categories["functions"].append(name)
            elif inspect.ismodule(obj):
                categories["other"].append(name)
            else:
                # Constants, type aliases, etc.
                categories["constants"].append(name)

        # Build convenience union keys
        categories["all_classes"] = (
            categories["classes"]
            + categories["dataclasses"]
            + categories["enums"]
            + categories["exceptions"]
            + categories["namedtuples"]
            + categories["typeddicts"]
            + categories["protocols"]
            + categories["abstract_classes"]
        )
        categories["all_functions"] = categories["functions"] + categories["async_functions"]

        return categories

    def _create_api_sections(self, package_name: str) -> list | None:
        """
        Create API reference sections based on discovered package exports.

        Uses static analysis (griffe) to discover public objects.

        Uses this heuristic:

        - classes with ≤5 methods: documented inline
        - classes with >5 methods: separate pages for each method

        Parameters
        ----------
        package_name
            The name of the package.

        Returns
        -------
        list | None
            List of section dictionaries, or None if no sections could be created.
        """
        exports = self._get_package_exports(package_name)
        if not exports:
            return None

        # Filter out metadata variables at the export level too
        skip_names = {"__version__", "__author__", "__email__", "__all__"}
        exports = [e for e in exports if e not in skip_names]

        if not exports:
            return None

        print(f"Found {len(exports)} exported names to document")

        # Categorize the exports
        categories = self._categorize_api_objects(package_name, exports)

        sections = []

        # Use static threshold of 5 methods for large class separation
        method_threshold = 5

        # ── Helper: build a class section with big-class splitting ────────
        def _make_class_section(title: str, desc: str, class_names: list) -> list[dict]:
            """Return section dicts (possibly with a Methods companion section)."""
            if not class_names:
                return []

            class_contents = []
            separate_methods = []

            for class_name in class_names:
                method_count = categories["class_methods"].get(class_name, 0)
                if method_count > method_threshold:
                    class_contents.append({"name": class_name, "members": []})
                    separate_methods.append(class_name)
                else:
                    class_contents.append(class_name)

            result = [{"title": title, "desc": desc, "contents": class_contents}]

            for class_name in separate_methods:
                method_names = categories["class_method_names"].get(class_name, [])
                method_count = len(method_names)
                method_contents = [f"{class_name}.{method}" for method in method_names]
                result.append(
                    {
                        "title": f"{class_name} Methods",
                        "desc": f"Methods for the {class_name} class",
                        "contents": method_contents,
                    }
                )
                print(f"  Created separate section for {class_name} with {method_count} methods")

            return result

        # ── Class-like sections ──────────────────────────────────────────
        sections.extend(_make_class_section("Classes", "Core classes", categories["classes"]))
        sections.extend(
            _make_class_section("Dataclasses", "Data-holding classes", categories["dataclasses"])
        )
        sections.extend(
            _make_class_section(
                "Abstract Classes", "Abstract base classes", categories["abstract_classes"]
            )
        )
        sections.extend(
            _make_class_section("Protocols", "Structural typing protocols", categories["protocols"])
        )

        # Enums, Exceptions, NamedTuples, TypedDicts — no big-class splitting
        if categories["enums"]:
            sections.append(
                {
                    "title": "Enumerations",
                    "desc": "Enum types",
                    "contents": categories["enums"],
                }
            )
        if categories["exceptions"]:
            sections.append(
                {
                    "title": "Exceptions",
                    "desc": "Exception classes",
                    "contents": categories["exceptions"],
                }
            )
        if categories["namedtuples"]:
            sections.append(
                {
                    "title": "Named Tuples",
                    "desc": "NamedTuple types",
                    "contents": categories["namedtuples"],
                }
            )
        if categories["typeddicts"]:
            sections.append(
                {
                    "title": "Typed Dicts",
                    "desc": "TypedDict types",
                    "contents": categories["typeddicts"],
                }
            )

        # ── Function sections ────────────────────────────────────────────
        if categories["functions"]:
            sections.append(
                {
                    "title": "Functions",
                    "desc": "Public functions",
                    "contents": categories["functions"],
                }
            )

        if categories["async_functions"]:
            sections.append(
                {
                    "title": "Async Functions",
                    "desc": "Asynchronous functions",
                    "contents": categories["async_functions"],
                }
            )

        # ── Data sections ────────────────────────────────────────────────
        if categories["constants"]:
            sections.append(
                {
                    "title": "Constants",
                    "desc": "Module-level constants and data",
                    "contents": categories["constants"],
                }
            )

        if categories["type_aliases"]:
            sections.append(
                {
                    "title": "Type Aliases",
                    "desc": "Type alias definitions",
                    "contents": categories["type_aliases"],
                }
            )

        # ── Catch-all ────────────────────────────────────────────────────
        if categories["other"]:
            sections.append(
                {"title": "Other", "desc": "Additional exports", "contents": categories["other"]}
            )

        # Write object type metadata for post-render classification
        self._write_object_types_json(categories)

        return sections if sections else None

    def _extract_all_directives(self, package_name: str) -> dict:
        """
        Extract Great Docs directives from all docstrings in the package.

        Scans all exported classes, methods, and functions for @seealso
        and @nodoc directives.

        Parameters
        ----------
        package_name
            The name of the package to scan.

        Returns
        -------
        dict
            Mapping of object names to their DocDirectives.
            Keys are either simple names (e.g., "MyClass") or qualified names
            (e.g., "MyClass.my_method").
        """
        from ._directives import extract_directives

        try:
            import griffe

            normalized_name = package_name.replace("-", "_")

            try:
                pkg = griffe.load(normalized_name)
            except Exception as e:
                print(f"Warning: Could not load package with griffe ({type(e).__name__})")
                return {}

            directive_map = {}

            # Use list() to materialize the iterator and catch any alias resolution errors
            try:
                members_list = list(pkg.members.items())
            except (griffe.CyclicAliasError, griffe.AliasResolutionError):  # pragma: no cover
                # Some members have unresolvable aliases so try to iterate more carefully
                members_list = []
                for name in list(pkg.members.keys()):
                    try:
                        members_list.append((name, pkg.members[name]))
                    except Exception:
                        # Skip members that can't be accessed
                        continue
            except Exception:  # pragma: no cover
                # Fall back to empty if we can't enumerate members at all
                return {}

            for name, obj in members_list:
                # Skip private members
                if name.startswith("_"):
                    continue

                # Skip aliases that can't be resolved (e.g., re-exports from external packages)
                try:
                    # Access kind to trigger alias resolution
                    _ = obj.kind
                except Exception:  # pragma: no cover
                    # Silently skip unresolvable aliases since they're usually re-exports
                    # from external packages that wouldn't be documented anyway
                    continue

                # Extract directives from the object's docstring
                try:
                    if obj.docstring:
                        directives = extract_directives(obj.docstring.value)
                        if directives:
                            directive_map[name] = directives
                except Exception:  # pragma: no cover
                    continue

                # For classes, also process methods
                try:
                    if obj.kind.value == "class":
                        for method_name, method in obj.members.items():
                            if method_name.startswith("_"):
                                continue
                            try:
                                if method.docstring:
                                    method_directives = extract_directives(method.docstring.value)
                                    if method_directives:
                                        directive_map[f"{name}.{method_name}"] = method_directives
                            except Exception:  # pragma: no cover
                                continue
                except Exception:  # pragma: no cover
                    # Skip if we can't introspect the class
                    pass

            return directive_map

        except ImportError:  # pragma: no cover
            print("Warning: griffe not available for directive extraction")  # pragma: no cover
            return {}  # pragma: no cover

    def _build_sections_from_reference_config(
        self, reference_config: list[dict]
    ) -> list[dict] | None:
        """
        Build API reference sections directly from reference config without validation.

        This is a fallback method used when auto-discovery fails but the user has
        explicitly specified their API structure in great-docs.yml. Unlike
        `_create_api_sections_from_config`, this method doesn't attempt to
        validate the references against discovered exports.

        Parameters
        ----------
        reference_config
            The reference configuration from great-docs.yml.

        Returns
        -------
        list[dict] | None
            List of section dictionaries, or None if config is empty.
        """
        if not reference_config:
            return None

        sections = []

        for section_config in reference_config:
            if not isinstance(section_config, dict):
                continue
            title = section_config.get("title", "Untitled")
            desc = section_config.get("desc", "")
            contents_config = section_config.get("contents", [])

            if not contents_config:
                continue

            section_contents = []

            for item in contents_config:
                if isinstance(item, str):
                    # Simple string reference - use as-is
                    section_contents.append(item)
                elif isinstance(item, dict):
                    # Dict with name and optional members config
                    name = item.get("name", "")
                    if not name:
                        continue

                    members = item.get("members", True)

                    if members is False:
                        # Don't document methods - just the class
                        section_contents.append({"name": name, "members": []})
                    else:
                        # Default: inline documentation (members: true)
                        section_contents.append(name)

            if section_contents:
                sections.append(
                    {
                        "title": title,
                        "desc": desc,
                        "contents": section_contents,
                    }
                )

        return sections if sections else None

    def _create_api_sections_from_config(self, package_name: str) -> list | None:
        """
        Create API reference sections from the `reference` config in great-docs.yml.

        This method reads the explicit section configuration from great-docs.yml
        and generates API reference sections accordingly. If no `reference` config
        is provided, returns None to fall back to auto-discovery.

        Parameters
        ----------
        package_name
            The name of the package.

        Returns
        -------
        list | None
            List of section dictionaries, or None if no reference config.
        """
        reference_config = self._config.reference
        if not reference_config:
            return None

        print("Using explicit reference configuration from great-docs.yml")

        # Get all exports to validate references and get method info
        exports = self._get_package_exports(package_name)
        if not exports:
            print("Warning: Could not discover package exports for validation")
            exports = []

        # Categorize exports to get class method info
        categories = self._categorize_api_objects(package_name, exports)

        # Build a mapping of module names → their expanded member names across
        # all categories.  When a user lists a bare module name (e.g. "parser")
        # in their reference config we expand it into the individual classes,
        # functions, constants, etc. that _categorize_api_objects discovered.
        _MEMBER_CATS = [
            "classes",
            "dataclasses",
            "abstract_classes",
            "protocols",
            "enums",
            "exceptions",
            "namedtuples",
            "typeddicts",
            "functions",
            "async_functions",
            "constants",
            "type_aliases",
            "other",
        ]
        module_members: dict[str, list[str]] = {}
        for cat_key in _MEMBER_CATS:
            for qualified in categories.get(cat_key, []):
                if "." in qualified:
                    mod_prefix = qualified.split(".")[0]
                    module_members.setdefault(mod_prefix, []).append(qualified)

        # Use the same big-class threshold as auto-discovery
        method_threshold = 5

        sections = []

        for section_config in reference_config:
            if not isinstance(section_config, dict):
                continue
            title = section_config.get("title", "Untitled")
            desc = section_config.get("desc", "")
            contents_config = section_config.get("contents", [])

            if not contents_config:
                continue

            section_contents = []
            # Track large classes that need companion method sections
            large_classes_in_section: list[str] = []

            for item in contents_config:
                if isinstance(item, str):
                    if item in module_members:
                        # This is a module name — expand into its individual members
                        for member in module_members[item]:
                            method_count = categories["class_methods"].get(member, 0)
                            if method_count > method_threshold:
                                section_contents.append({"name": member, "members": []})
                                large_classes_in_section.append(member)
                            else:
                                section_contents.append(member)
                    else:
                        # Regular item (class, function, etc.) — use as-is
                        method_count = categories["class_methods"].get(item, 0)
                        if method_count > method_threshold:
                            section_contents.append({"name": item, "members": []})
                            large_classes_in_section.append(item)
                        else:
                            section_contents.append(item)
                elif isinstance(item, dict):
                    # Dict with name and optional members config
                    name = item.get("name", "")
                    if not name:
                        continue

                    members = item.get("members", True)

                    if members is False:
                        # Don't document methods - just the class
                        section_contents.append({"name": name, "members": []})
                    else:
                        # Default: inline documentation (members: true)
                        section_contents.append(name)

            if section_contents:
                sections.append(
                    {
                        "title": title,
                        "desc": desc,
                        "contents": section_contents,
                    }
                )

            # Add companion method sections for large classes
            for class_name in large_classes_in_section:
                method_names = categories["class_method_names"].get(class_name, [])
                if method_names:
                    method_contents = [f"{class_name}.{m}" for m in method_names]
                    sections.append(
                        {
                            "title": f"{class_name} Methods",
                            "desc": f"Methods for the {class_name} class",
                            "contents": method_contents,
                        }
                    )
                    print(
                        f"  Created separate section for {class_name} "
                        f"with {len(method_names)} methods"
                    )

        if sections:
            print(f"Generated {len(sections)} section(s) from reference config")

        # Write object type metadata for post-render classification
        self._write_object_types_json(categories)

        return sections if sections else None

    def _create_api_sections_with_config(self, package_name: str) -> list | None:
        """
        Create API reference sections, prioritizing explicit config over auto-discovery.

        First checks for explicit `reference` configuration in great-docs.yml.
        If not found, falls back to auto-generating sections from discovered exports.
        After obtaining sections, filters out any items marked with `%nodoc`.

        Parameters
        ----------
        package_name
            The name of the package.

        Returns
        -------
        list | None
            List of section dictionaries, or None if no exports found.
        """
        # First, check for explicit reference config in great-docs.yml
        config_sections = self._create_api_sections_from_config(package_name)
        if config_sections:
            sections = config_sections
        else:
            # Fall back to auto-generated sections from discovered exports
            print("No reference config found, using auto-discovery")
            sections = self._create_api_sections(package_name)

        # Apply %nodoc filtering to remove excluded items
        if sections:
            sections = self._apply_nodoc_filter(package_name, sections)

        return sections

    def _apply_nodoc_filter(self, package_name: str, sections: list[dict]) -> list[dict] | None:
        """
        Filter out items marked with `%nodoc` from API reference sections.

        Extracts directives from all docstrings in the package and removes
        any items (and their companion method sections) whose docstrings
        contain the `%nodoc` directive.

        Parameters
        ----------
        package_name
            The name of the package to scan for directives.
        sections
            The API reference sections to filter.

        Returns
        -------
        list[dict] | None
            Filtered sections with `%nodoc` items removed, or None if all
            items were excluded.
        """
        directive_map = self._extract_all_directives(package_name)
        if not directive_map:
            return sections

        # Collect names of items marked with %nodoc
        nodoc_names: set[str] = set()
        for name, directives in directive_map.items():
            if directives.nodoc:
                nodoc_names.add(name)

        if not nodoc_names:
            return sections

        print(
            f"Excluding {len(nodoc_names)} item(s) marked with %nodoc: {', '.join(sorted(nodoc_names))}"
        )

        def _item_name(item: str | dict) -> str:
            """Extract the bare object name from a section content item."""
            if isinstance(item, dict):
                return item.get("name", "")
            return item

        filtered_sections = []
        for section in sections:
            contents = section.get("contents", [])
            filtered_contents = [item for item in contents if _item_name(item) not in nodoc_names]

            # Also drop companion method sections whose parent class is %nodoc
            title = section.get("title", "")
            # Companion sections have titles like "ClassName Methods"
            if title.endswith(" Methods"):
                class_name = title[: -len(" Methods")]
                if class_name in nodoc_names:
                    continue

            if filtered_contents:
                filtered_sections.append({**section, "contents": filtered_contents})

        return filtered_sections if filtered_sections else None

    def _extract_authors_from_pyproject(self) -> list[dict[str, str]]:
        """
        Extract author information from pyproject.toml.

        Reads authors and maintainers from pyproject.toml and combines them
        into a list suitable for the great-docs.yml authors section.

        Returns
        -------
        list[dict[str, str]]
            List of author dictionaries with name, email, and role fields.
        """
        package_root = self._find_package_root()
        pyproject_path = package_root / "pyproject.toml"

        if not pyproject_path.exists():
            return []

        try:
            import tomllib

            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                project = data.get("project", {})

            authors_list = project.get("authors", [])
            maintainers_list = project.get("maintainers", [])

            # Track seen names to avoid duplicates
            seen_names: set[str] = set()
            result: list[dict[str, str]] = []

            # Process maintainers first (they get "Maintainer" role)
            for maintainer in maintainers_list:
                if isinstance(maintainer, dict):
                    name = maintainer.get("name", "")
                    email = maintainer.get("email", "")
                    if name and name not in seen_names:
                        seen_names.add(name)
                        author_entry: dict[str, str] = {"name": name, "role": "Maintainer"}
                        if email:
                            author_entry["email"] = email
                        result.append(author_entry)

            # Process authors (they get "Author" role, unless already added as maintainer)
            for author in authors_list:
                if isinstance(author, dict):
                    name = author.get("name", "")
                    email = author.get("email", "")
                    if name and name not in seen_names:
                        seen_names.add(name)
                        author_entry = {"name": name, "role": "Author"}
                        if email:
                            author_entry["email"] = email
                        result.append(author_entry)

            return result

        except Exception:  # pragma: no cover
            return []  # pragma: no cover

    def _format_authors_yaml(self, authors: list[dict[str, str]]) -> str:
        """
        Format authors list as YAML for great-docs.yml.

        Parameters
        ----------
        authors
            List of author dictionaries from _extract_authors_from_pyproject.

        Returns
        -------
        str
            YAML-formatted authors section, or empty string if no authors.
        """
        if not authors:
            return ""

        lines = [
            "# Author Information",
            "# ------------------",
            "# Author metadata for display in the landing page sidebar",
            "# You can add additional fields: github, orcid, affiliation, homepage",
            "authors:",
        ]

        for author in authors:
            lines.append(f"  - name: {author['name']}")
            if "role" in author:
                lines.append(f"    role: {author['role']}")
            # Add commented placeholders for optional fields
            lines.append("    # affiliation: ")
            if "email" in author:
                lines.append(f"    email: {author['email']}")
            else:
                lines.append("    # email: ")
            lines.append("    # github: ")
            lines.append("    # orcid: ")
            lines.append("    # homepage: ")

        return "\n".join(lines)

    @staticmethod
    def _format_preserved_extras_yaml(
        display_name: str | None = None,
        site: dict | None = None,
        funding: dict | None = None,
    ) -> tuple[str, str, str]:
        """
        Build YAML fragments for preserved config values.

        Returns
        -------
        tuple[str, str, str]
            `(display_name_yaml, site_yaml, funding_yaml)`: each is either
            an active YAML block or the commented-out template placeholder.
        """
        # ── display_name ─────────────────────────────────────────────
        if display_name:
            dn_yaml = (
                "# Display Name\n"
                "# ------------\n"
                "# Custom display name for the site navbar/title\n"
                f'display_name: "{display_name}"\n'
            )
        else:
            dn_yaml = ""

        # ── site settings ────────────────────────────────────────────
        if site:
            parts = [
                "# Site Settings",
                "# -------------",
                "site:",
            ]
            for k, v in site.items():
                if isinstance(v, bool):
                    parts.append(f"  {k}: {'true' if v else 'false'}")
                elif isinstance(v, str):
                    parts.append(f"  {k}: {v}")
                else:
                    parts.append(f"  {k}: {v}")
            site_yaml = "\n".join(parts) + "\n"
        else:
            site_yaml = (
                "# Site Settings\n"
                "# -------------\n"
                "# site:\n"
                "#   theme: flatly              # Quarto theme (default: flatly)\n"
                "#   toc: true                  # Show table of contents (default: true)\n"
                "#   toc-depth: 2               # TOC heading depth (default: 2)\n"
                '#   toc-title: On this page    # TOC title (default: "On this page")\n'
            )

        # ── funding ──────────────────────────────────────────────────
        if funding and isinstance(funding, dict) and funding.get("name"):
            parts = [
                "# Funding / Copyright Holder",
                "# --------------------------",
                "funding:",
                f'  name: "{funding["name"]}"',
            ]
            if funding.get("roles"):
                parts.append("  roles:")
                for role in funding["roles"]:
                    parts.append(f"    - {role}")
            if funding.get("homepage"):
                parts.append(f"  homepage: {funding['homepage']}")
            if funding.get("ror"):
                parts.append(f"  ror: {funding['ror']}")
            funding_yaml = "\n".join(parts) + "\n"
        else:
            funding_yaml = (
                "# Funding / Copyright Holder\n"
                "# --------------------------\n"
                "# Credit the organization that funds or holds copyright for this package.\n"
                "# Displays in sidebar and footer. Homepage and ROR provide links.\n"
                "# funding:\n"
                '#   name: "Posit Software, PBC"\n'
                "#   roles:\n"
                "#     - Copyright holder\n"
                "#     - funder\n"
                "#   homepage: https://posit.co\n"
                "#   ror: https://ror.org/03wc8by49\n"
            )

        return dn_yaml, site_yaml, funding_yaml

    @staticmethod
    def _format_cli_yaml(cli_config: dict | None = None) -> str:
        """
        Build YAML fragment for CLI documentation configuration.

        Parameters
        ----------
        cli_config
            CLI config dict (e.g. `{"enabled": True, "module": "pkg.cli"}`),
            or `None` to emit a commented-out template.

        Returns
        -------
        str
            Active `cli:` YAML block when enabled, or a commented-out template.
        """
        if cli_config and cli_config.get("enabled"):
            parts = [
                "# CLI Documentation",
                "# -----------------",
                "cli:",
                "  enabled: true",
            ]
            if cli_config.get("module"):
                parts.append(f"  module: {cli_config['module']}")
            if cli_config.get("name"):
                parts.append(f"  name: {cli_config['name']}")
            return "\n".join(parts) + "\n"

        return (
            "\n".join(
                [
                    "# CLI Documentation",
                    "# -----------------",
                    "# cli:",
                    "#   enabled: true              # Enable CLI documentation",
                    "#   module: my_package.cli     # Module containing Click commands",
                    "#   name: cli                  # Name of the Click command object",
                ]
            )
            + "\n"
        )

    def _generate_initial_config(self, force: bool = False) -> bool:
        """
        Generate an initial great-docs.yml with discovered exports.

        Creates a great-docs.yml file in the project root with sensible defaults
        and a reference section populated from discovered package exports.

        Parameters
        ----------
        force
            If `True`, overwrite existing great-docs.yml without prompting.

        Returns
        -------
        bool
            True if config was created, False if skipped.
        """
        config_path = self._find_package_root() / "great-docs.yml"

        # Check if config already exists
        if config_path.exists() and not force:
            print(
                f"great-docs.yml already exists at {config_path}\n"
                "Use --force to overwrite it (this will reset to defaults)."
            )
            return False

        # Detect package name
        package_name = self._detect_package_name()
        if not package_name:
            print("Warning: Could not detect package name, creating minimal config")
            # Create minimal config without reference section
            config_content = self._generate_minimal_config()
            config_path.write_text(config_content, encoding="utf-8")
            print(f"Created {config_path}")
            return True

        # Get normalized package name for imports
        importable_name = self._normalize_package_name(package_name)

        # Detect docstring style
        print("Detecting docstring style...")
        parser_style = self._detect_docstring_style(importable_name)

        # Discover exports
        exports = self._get_package_exports(importable_name)
        if not exports:
            print("Warning: Could not discover exports, creating minimal config")
            # Without exports, we still try to detect dynamic mode
            print("Testing dynamic introspection mode...")
            dynamic_mode = self._detect_dynamic_mode(importable_name)
            config_content = self._generate_minimal_config(
                parser=parser_style,
                dynamic=dynamic_mode,
            )
            config_path.write_text(config_content, encoding="utf-8")
            print(f"Created {config_path}")
            return True

        # Categorize exports (this also detects cyclic aliases)
        print("Categorizing API objects...")
        categories = self._categorize_api_objects(importable_name, exports)

        # Determine dynamic mode based on cyclic alias detection during categorization
        cyclic_alias_count = categories.get("cyclic_alias_count", 0)
        if cyclic_alias_count > 0:
            print(f"Detected {cyclic_alias_count} cyclic alias(es), using dynamic: false")
            dynamic_mode = False
        else:
            # Run the explicit detection as a fallback
            print("Testing dynamic introspection mode...")
            dynamic_mode = self._detect_dynamic_mode(importable_name)

        # Generate config content
        config_content = self._generate_config_with_reference(
            categories,
            importable_name,
            parser=parser_style,
            dynamic=dynamic_mode,
        )

        config_path.write_text(config_content, encoding="utf-8")
        print(f"Created {config_path}")
        return True

    def _generate_minimal_config(
        self,
        parser: str = "numpy",
        dynamic: bool = True,
    ) -> str:
        """
        Generate minimal great-docs.yml without reference section.

        Parameters
        ----------
        parser
            The docstring parser style ("numpy", "google", or "sphinx").
        dynamic
            Whether to use dynamic introspection mode for API reference generation.

        Returns
        -------
        str
            YAML content for a minimal configuration file.
        """
        dynamic_str = "true" if dynamic else "false"

        # Extract authors from pyproject.toml
        authors = self._extract_authors_from_pyproject()
        authors_yaml = self._format_authors_yaml(authors)

        # Build the config with optional authors section
        authors_section = f"\n{authors_yaml}\n" if authors_yaml else ""

        # Build default YAML fragments for site, funding, etc.
        _dn_yaml, site_yaml, funding_yaml = self._format_preserved_extras_yaml()

        # Build CLI section (default commented-out template)
        cli_yaml = self._format_cli_yaml()

        return f"""# Great Docs Configuration
# See https://posit-dev.github.io/great-docs/user-guide/03-configuration.html

# Module Name (optional)
# ----------------------
# Set this if your importable module name differs from the project name.
# Example: project 'py-yaml12' with module name 'yaml12'
# module: yaml12

# Docstring Parser
# ----------------
# The docstring format used in your package (numpy, google, or sphinx)
parser: {parser}

# Dynamic Introspection
# ---------------------
# Use runtime introspection for more accurate documentation (default: true)
# Set to false if your package has cyclic alias issues (e.g., PyO3/Rust bindings)
dynamic: {dynamic_str}

# Exclusions
# ----------
# Items to exclude from auto-documentation (affects 'init' and 'scan')
# exclude:
#   - InternalClass
#   - helper_function

# Logo & Favicon
# ---------------
# Point to a single logo file (replaces the text title in the navbar):
# logo: assets/logo.svg
#
# For light/dark variants:
# logo:
#   light: assets/logo-light.svg
#   dark: assets/logo-dark.svg
#
# To show the text title alongside the logo, add: show_title: true
{authors_section}
{funding_yaml}
{site_yaml}
# Jupyter Kernel
# --------------
# Jupyter kernel to use for executing code cells in .qmd files.
# This is set at the project level so it applies to all pages, including
# auto-generated API reference pages. Can be overridden in individual .qmd
# file frontmatter if needed for special cases.
jupyter: python3

{cli_yaml}
# API Reference Structure
# -----------------------
# Auto-discovery couldn't determine your package's public API.
# You can manually specify which items to document here.
#
# Uncomment and customize the reference section below:
#
# reference:
#   - title: Functions
#     desc: Public functions provided by the package
#     contents:
#       - my_function
#       - another_function
#
#   - title: Classes
#     desc: Main classes for working with the package
#     contents:
#       - name: MyClass
#         members: false       # Don't document methods inline
#       - SimpleClass          # Methods documented inline (default)
#
# After editing, run 'great-docs build' to generate your documentation.
"""

    def _generate_config_with_reference(
        self,
        categories: dict,
        package_name: str,
        parser: str = "numpy",
        dynamic: bool = True,
    ) -> str:
        """
        Generate great-docs.yml with a reference section from discovered exports.

        Parameters
        ----------
        categories
            Dictionary from _categorize_api_objects with classes, functions, other.
        package_name
            The package name (for method threshold comments).
        parser
            The docstring parser style ("numpy", "google", or "sphinx").
        dynamic
            Whether to use dynamic introspection mode for API reference generation.

        Returns
        -------
        str
            YAML content for the configuration file.
        """
        dynamic_str = "true" if dynamic else "false"

        # Extract authors from pyproject.toml
        authors = self._extract_authors_from_pyproject()
        authors_yaml = self._format_authors_yaml(authors)

        lines = [
            "# Great Docs Configuration",
            "# See https://posit-dev.github.io/great-docs/user-guide/03-configuration.html",
            "",
            "# Module Name (optional)",
            "# ----------------------",
            "# Set this if your importable module name differs from the project name.",
            "# Example: project 'py-yaml12' with module name 'yaml12'",
            "# module: yaml12",
            "",
        ]

        lines.extend(
            [
                "# Docstring Parser",
                "# ----------------",
                "# The docstring format used in your package (numpy, google, or sphinx)",
                f"parser: {parser}",
                "",
                "# Dynamic Introspection",
                "# ---------------------",
                "# Use runtime introspection for more accurate documentation (default: true)",
                "# Set to false if your package has cyclic alias issues (e.g., PyO3/Rust bindings)",
                f"dynamic: {dynamic_str}",
                "",
                "# API Discovery Settings",
                "# ----------------------",
                "# Exclude items from auto-documentation",
                "# exclude:",
                "#   - InternalClass",
                "#   - helper_function",
                "",
                "# Logo & Favicon",
                "# ---------------",
                "# Point to a single logo file (replaces the text title in the navbar):",
                "# logo: assets/logo.svg",
                "#",
                "# For light/dark variants:",
                "# logo:",
                "#   light: assets/logo-light.svg",
                "#   dark: assets/logo-dark.svg",
                "#",
                "# To show the text title alongside the logo, add: show_title: true",
                "",
            ]
        )

        # Add authors section if we found any
        if authors_yaml:
            lines.append(authors_yaml)
            lines.append("")

        # Add funding section (default commented-out template)
        _dn_yaml, site_yaml, funding_yaml = self._format_preserved_extras_yaml()
        lines.extend(funding_yaml.rstrip("\n").splitlines())
        lines.append("")

        # Add reference section
        lines.extend(
            [
                "# API Reference Structure",
                "# -----------------------",
                "# Customize the sections below to organize your API documentation.",
                "# - Reorder items within a section to change their display order",
                "# - Move items between sections or create new sections",
                "# - Use 'members: false' to exclude methods from documentation",
                "# - Add 'desc:' to sections for descriptions",
                "",
                "reference:",
            ]
        )

        # Auto-generate reference sections from discovered exports
        class_methods = categories.get("class_methods", {})
        class_method_names = categories.get("class_method_names", {})

        # Use static threshold of 5 methods for large class separation
        threshold = 5

        # Track large classes that need separate method sections
        large_classes: list[str] = []

        # Track whether we've emitted any section yet (for blank-line spacing)
        has_prev_section = False

        # --- Class-like sections (support big-class splitting) ---
        _class_like_sections = [
            ("classes", "Classes", "Main classes provided by the package"),
            ("dataclasses", "Dataclasses", "Dataclass definitions"),
            ("abstract_classes", "Abstract Classes", "Abstract base classes"),
            ("protocols", "Protocols", "Protocol / structural-typing interfaces"),
        ]

        for cat_key, title, desc in _class_like_sections:
            items = categories.get(cat_key, [])
            if not items:
                continue
            if has_prev_section:
                lines.append("")
            lines.append(f"  - title: {title}")
            lines.append(f"    desc: {desc}")
            lines.append("    contents:")
            for class_name in sorted(items):
                method_count = class_methods.get(class_name, 0)
                if method_count > threshold:
                    lines.append(f"      - name: {class_name}")
                    lines.append(f"        members: false  # {method_count} methods listed below")
                    large_classes.append(class_name)
                elif method_count > 0:
                    lines.append(f"      - {class_name}  # {method_count} method(s)")
                else:
                    lines.append(f"      - {class_name}")
            has_prev_section = True

        # Add separate method sections for large classes
        for class_name in large_classes:
            method_names = class_method_names.get(class_name, [])
            if method_names:
                lines.append("")
                lines.append(f"  - title: {class_name} Methods")
                lines.append(f"    desc: Methods for the {class_name} class")
                lines.append("    contents:")
                for method_name in method_names:
                    lines.append(f"      - {class_name}.{method_name}")

        # --- Flat sections (simple lists, no big-class splitting) ---
        _flat_sections = [
            ("enums", "Enumerations", "Enumeration types"),
            ("exceptions", "Exceptions", "Exception classes"),
            ("namedtuples", "Named Tuples", "Named tuple definitions"),
            ("typeddicts", "Typed Dicts", "TypedDict definitions"),
            ("functions", "Functions", "Utility functions"),
            ("async_functions", "Async Functions", "Asynchronous functions"),
            ("constants", "Constants", "Module-level constants and data"),
            ("type_aliases", "Type Aliases", "Type alias definitions"),
            ("other", "Other", "Additional exports"),
        ]

        for cat_key, title, desc in _flat_sections:
            items = categories.get(cat_key, [])
            if not items:
                continue
            if has_prev_section:
                lines.append("")
            lines.append(f"  - title: {title}")
            lines.append(f"    desc: {desc}")
            lines.append("    contents:")
            for name in sorted(items):
                lines.append(f"      - {name}")
            has_prev_section = True

        # Add trailing sections for site settings (default templates)
        lines.extend(
            [
                "",
            ]
        )
        lines.extend(site_yaml.rstrip("\n").splitlines())

        lines.extend(
            [
                "",
                "# Jupyter Kernel",
                "# --------------",
                "# Jupyter kernel to use for executing code cells in .qmd files.",
                "# This is set at the project level so it applies to all pages, including",
                "# auto-generated API reference pages. Can be overridden in individual .qmd",
                "# file frontmatter if needed for special cases.",
                "jupyter: python3",
                "",
            ]
        )

        # Add CLI documentation section (default commented-out template)
        cli_yaml = self._format_cli_yaml()
        lines.extend(cli_yaml.rstrip("\n").splitlines())

        return "\n".join(lines) + "\n"

    def _find_index_source_file(self) -> tuple[Path | None, list[str]]:
        """
        Find the best source file for index.qmd based on priority.

        Priority order (highest to lowest):
        1. index.qmd in project root
        2. index.md in project root
        3. README.md in project root
        4. README.rst in project root (converted to Markdown via pandoc)

        Returns
        -------
        tuple[Path | None, list[str]]
            A tuple of (source_file_path, warnings_list).
            source_file_path is None if no suitable file is found.
        """
        package_root = self._find_package_root()
        warnings = []

        # Candidates in priority order
        candidates = [
            package_root / "index.qmd",
            package_root / "index.md",
            package_root / "README.md",
            package_root / "README.rst",
        ]

        found = [c for c in candidates if c.exists()]

        if not found:
            return None, warnings

        winner = found[0]

        # Warn if multiple candidates exist
        if len(found) > 1:
            others = ", ".join(f.name for f in found[1:])
            warnings.append(
                f"⚠️  Multiple index source files detected. Using {winner.name} (ignoring {others})"
            )

        return winner, warnings

    def _convert_rst_to_markdown(self, rst_path: Path) -> str:
        """
        Convert a reStructuredText file to Markdown using Quarto's bundled pandoc.

        Falls back to the raw RST content if pandoc conversion fails.

        Parameters
        ----------
        rst_path
            Path to the `.rst` file.

        Returns
        -------
        str
            The converted Markdown content.
        """
        import shutil
        import subprocess

        # Try 'quarto pandoc' first (always available when quarto is installed),
        # then fall back to standalone 'pandoc'
        pandoc_cmd = None
        if shutil.which("quarto"):
            pandoc_cmd = ["quarto", "pandoc"]
        elif shutil.which("pandoc"):
            pandoc_cmd = ["pandoc"]

        if pandoc_cmd is None:
            print("   ⚠️  pandoc not found; using raw RST content for landing page")
            return rst_path.read_text(encoding="utf-8")

        try:
            result = subprocess.run(
                [*pandoc_cmd, str(rst_path), "-f", "rst", "-t", "markdown", "--wrap=none"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"   ⚠️  pandoc conversion failed: {result.stderr.strip()}")
                print("   Falling back to raw RST content")
                return rst_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"   ⚠️  pandoc conversion error: {e}")
            print("   Falling back to raw RST content")
            return rst_path.read_text(encoding="utf-8")

    def _generate_landing_page_content(self, metadata: dict) -> str:
        """
        Generate landing page content from package metadata.

        When no README.md, index.md, or index.qmd is available, this method
        creates a tasteful landing page drawn from package metadata including
        the package name, description, installation instructions, and
        navigation links to available documentation sections.

        Parameters
        ----------
        metadata
            Dictionary of package metadata from ``_get_package_metadata()``.

        Returns
        -------
        str
            The generated Markdown content for the landing page body (not
            including YAML frontmatter or sidebar — those are added by the
            caller).
        """
        package_name = self._detect_package_name() or "Package"
        description = metadata.get("description", "")

        lines = []
        lines.append(f"## {package_name}")
        lines.append("")

        if description:
            lines.append(description)
            lines.append("")

        # Installation section
        install_name = package_name
        lines.append("### Installation")
        lines.append("")
        lines.append("```bash")
        lines.append(f"pip install {install_name}")
        lines.append("```")
        lines.append("")

        # Get Started - link to available sections
        nav_items = []

        # API Reference (if documentable exports exist)
        if self._has_api_reference:
            nav_items.append("- [API Reference](reference/index.qmd) — Full API documentation")

        # Check for User Guide (look at source directory since build hasn't run yet)
        ug_source = self._discover_user_guide()
        if ug_source:
            nav_items.append("- [User Guide](user-guide/index.qmd) — Guides and tutorials")

        if nav_items:
            lines.append("### Get Started")
            lines.append("")
            lines.extend(nav_items)
            lines.append("")

        return "\n".join(lines) + "\n"

    def _extract_badges_from_content(self, content: str) -> tuple[list[dict], str, dict]:
        """Extract badge image-links and hero elements from README/index content.

        Supports two common README layouts:

        1. **Top-of-file badges** — bare ``[![alt](img)](url)`` lines right
           after the first heading.
        2. **Centered-div badges** — badges inside a
           ``<div align="center">`` block (common in repos like Pointblank,
           Great Tables, etc.).  When this layout is detected, the entire
           centered block (hero image, italic tagline, and badges) is
           stripped because the hero section replaces it.  The logo image
           and tagline text are returned so the hero section can use them.

        Parameters
        ----------
        content
            Raw Markdown content (after any YAML frontmatter has been
            stripped).

        Returns
        -------
        tuple[list[dict], str, dict]
            ``(badges, cleaned_content, hero_extras)`` — a list of badge
            dicts (keys: ``url``, ``img``, ``alt``), the content with the
            badge block removed, and a dict of extracted hero elements
            (optional keys: ``logo_url``, ``tagline``).
        """
        import re

        badge_hosts = (
            "img.shields.io",
            "badge.fury.io",
            "github.com/",  # GitHub Actions badge URLs contain /badge.svg
            "codecov.io",
            "readthedocs.org",
            "repostatus.org",
            "pepy.tech",
            "pyopensci.org",
            "zenodo.org/badge",
            "www.contributor-covenant.org",
            "deepwiki.com",
            "static.pepy.tech",
        )

        # Pattern: [![alt](img_url)](link_url)
        md_badge_re = re.compile(r"\[!\[([^\]]*)\]\(([^)]+)\)\]\(([^)]+)\)")

        # ── Strategy 1: centered-div badges ─────────────────────────
        # Look for <div align="center"> containing badge markdown.
        center_div_re = re.compile(r'^<div\s+align=["\']center["\']', re.IGNORECASE)
        # Patterns for extracting hero elements from centered divs
        # HTML <a><img></a> (linked logo image)
        linked_img_re = re.compile(
            r'<a\s[^>]*href="([^"]+)"[^>]*>\s*<img\s[^>]*src="([^"]+)"[^>]*/?>\s*</a>',
            re.IGNORECASE,
        )
        # Bare <img> tag (logo image without link)
        bare_img_re = re.compile(
            r'<img\s[^>]*src="([^"]+)"[^>]*/?>',
            re.IGNORECASE,
        )
        # Italic tagline: *text* or _text_
        italic_re = re.compile(r"^[*_](.+)[*_]$")

        lines = content.split("\n")
        div_start = None
        div_end = None

        for i, line in enumerate(lines):
            if center_div_re.match(line.strip()):
                # Found a centered div — scan forward for badges and hero elements
                div_badges: list[dict] = []
                hero_extras: dict = {}
                for j in range(i + 1, len(lines)):
                    sline = lines[j].strip()
                    if sline == "</div>":
                        div_end = j
                        break

                    # Collect badges
                    for alt, img, url in md_badge_re.findall(sline):
                        if any(host in img for host in badge_hosts):
                            div_badges.append({"alt": alt, "img": img, "url": url})

                    # Extract logo image (HTML <a><img> or bare <img>),
                    # but skip lines that are markdown badge patterns
                    if "logo_url" not in hero_extras and not md_badge_re.search(sline):
                        linked_match = linked_img_re.search(sline)
                        if linked_match:
                            hero_extras["logo_url"] = linked_match.group(2)
                        else:
                            bare_match = bare_img_re.search(sline)
                            if bare_match:
                                hero_extras["logo_url"] = bare_match.group(1)

                    # Extract italic tagline
                    if "tagline" not in hero_extras:
                        italic_match = italic_re.match(sline)
                        if italic_match:
                            hero_extras["tagline"] = italic_match.group(1)

                if div_badges and div_end is not None:
                    div_start = i
                    # Remove the entire centered div block
                    remaining = lines[:div_start] + lines[div_end + 1 :]
                    cleaned = "\n".join(remaining)
                    # Collapse excess blank lines at the splice point
                    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
                    return div_badges, cleaned, hero_extras

                # Not a badge div — keep scanning for other centered divs
                continue

        # ── Strategy 2: top-of-file badges ──────────────────────────
        badges: list[dict] = []
        badge_end_idx = 0

        started = False
        for i, line in enumerate(lines):
            stripped = line.strip()

            if not started and not stripped:
                continue

            if not started and stripped.startswith("# "):
                started = True
                continue

            if not started and stripped:
                started = True

            if started and not stripped:
                has_more_badges = False
                for j in range(i + 1, min(i + 3, len(lines))):
                    if md_badge_re.search(lines[j]):
                        has_more_badges = True
                        break
                if has_more_badges:
                    badge_end_idx = i + 1
                    continue
                else:
                    break

            found_in_line = md_badge_re.findall(stripped)
            if found_in_line:
                for alt, img, url in found_in_line:
                    if any(host in img for host in badge_hosts):
                        badges.append({"alt": alt, "img": img, "url": url})
                badge_end_idx = i + 1
            elif started:
                break

        if badges and badge_end_idx > 0:
            kept_before: list[str] = []
            for i in range(badge_end_idx):
                stripped = lines[i].strip()
                if stripped.startswith("# "):
                    kept_before.append(lines[i])

            remaining = lines[badge_end_idx:]
            cleaned = "\n".join(kept_before + remaining)
            cleaned = cleaned.lstrip("\n")
            if kept_before:
                heading = kept_before[0]
                rest = "\n".join(remaining).lstrip("\n")
                cleaned = heading + "\n\n" + rest
        else:
            cleaned = content

        return badges, cleaned, {}

    def _build_hero_section(
        self,
        readme_content: str | None = None,
    ) -> tuple[str, str | None]:
        """Build the hero section HTML and optionally clean badges from content.

        Parameters
        ----------
        readme_content
            Raw README/index Markdown content. When provided and badge
            auto-extraction is enabled, badges are extracted and the cleaned
            content is returned.

        Returns
        -------
        tuple[str, str | None]
            ``(hero_html, cleaned_content)`` — the hero HTML block (empty
            string when hero is disabled) and the cleaned README content
            (``None`` when no cleaning was performed).
        """
        if self._config.hero_explicitly_disabled:
            return "", None

        # ── Early badge + hero extraction from README ───────────────
        # This must happen before the auto-enable check so we can
        # use README hero elements (logo, tagline) to decide whether
        # to auto-enable.
        badges_config = self._config.hero_badges
        badges: list[dict] = []
        cleaned_content = None
        readme_hero: dict = {}

        if badges_config == "auto" and readme_content:
            badges, cleaned, readme_hero = self._extract_badges_from_content(readme_content)
            if badges:
                cleaned_content = cleaned
        elif isinstance(badges_config, list):
            badges = badges_config

        if not self._config.hero_enabled:
            # Not explicitly enabled and no config-level logo — auto-enable
            # if hero logo files are detected on disk or README has hero content.
            if self._detect_hero_logo() is None and not readme_hero:
                return "", None

        metadata = self._get_package_metadata()

        # ── Logo ────────────────────────────────────────────────────
        logo_config = self._config.hero_logo
        logo_height = self._config.hero_logo_height
        logo_html = ""

        # Fallback chain: explicit hero.logo → auto-detected hero logo
        # → explicit top-level logo → auto-detected navbar logo
        if logo_config is None:
            logo_config = self._detect_hero_logo()
        if logo_config is None:
            logo_config = self._config.logo
        if logo_config is None:
            logo_config = self._detect_logo()
        if logo_config is None and readme_hero.get("logo_url"):
            logo_config = readme_hero["logo_url"]
        if logo_config is False:
            logo_config = None

        # Copy auto-detected logo files into the build dir so the HTML
        # references resolve.  Files under assets/ are already copied by
        # _copy_assets; root-level files need an explicit copy.
        if logo_config and isinstance(logo_config, dict):
            package_root = self._find_package_root()
            for key in ("light", "dark"):
                rel = logo_config.get(key)
                if rel and not rel.startswith("assets/"):
                    src = package_root / rel
                    if src.is_file():
                        dest = self.project_path / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        if not dest.exists():
                            shutil.copy2(src, dest)

        if logo_config:
            if isinstance(logo_config, dict):
                light = logo_config.get("light")
                dark = logo_config.get("dark")
                alt = logo_config.get("alt", "Logo")

                if light and dark and light != dark:
                    logo_html = (
                        f'<img src="{light}" alt="{alt}" class="gd-hero-logo gd-only-light" style="max-height:{logo_height}" />\n'
                        f'<img src="{dark}" alt="{alt}" class="gd-hero-logo gd-only-dark" style="max-height:{logo_height}" />'
                    )
                elif light:
                    logo_html = f'<img src="{light}" alt="{alt}" class="gd-hero-logo" style="max-height:{logo_height}" />'
            elif isinstance(logo_config, str):
                logo_html = f'<img src="{logo_config}" alt="Logo" class="gd-hero-logo" style="max-height:{logo_height}" />'

        # ── Name ────────────────────────────────────────────────────
        hero_name = self._config.hero_name
        if hero_name is None:
            # Fallback to package name from metadata
            hero_name = metadata.get("name") or self._detect_package_name()
        name_html = f'<p class="gd-hero-name">{hero_name}</p>' if hero_name else ""

        # ── Tagline ─────────────────────────────────────────────────
        tagline = self._config.hero_tagline
        if tagline is None:
            tagline = readme_hero.get("tagline") or metadata.get("description", "")
        tagline_html = f'<p class="gd-hero-tagline">{tagline}</p>' if tagline else ""

        # ── Badges ──────────────────────────────────────────────────
        badges_html = ""
        if badges:
            badge_items = []
            for b in badges:
                alt = b.get("alt", "")
                img = b.get("img", "")
                url = b.get("url", "")
                if url:
                    badge_items.append(f'<a href="{url}"><img alt="{alt}" src="{img}" /></a>')
                else:
                    badge_items.append(f'<img alt="{alt}" src="{img}" />')
            badges_html = '<div class="gd-hero-badges">\n' + "\n".join(badge_items) + "\n</div>"

        # ── Assemble ────────────────────────────────────────────────
        parts = [p for p in [logo_html, name_html, tagline_html, badges_html] if p]
        if not parts:
            return "", None

        hero_html = '<div class="gd-hero">\n' + "\n".join(parts) + "\n</div>\n\n"

        return hero_html, cleaned_content

    def _build_metadata_margin(self) -> str:
        """
        Build the `.column-margin` metadata sidebar content for the homepage.

        Generates Markdown for the right-hand margin containing project metadata
        in five sections: Links, AI / Agents, Developers, Community, and Meta.

        As a side effect, creates `contributing.qmd` and `code-of-conduct.qmd`
        in the project directory if the corresponding source files exist.

        Returns
        -------
        str
            The margin content as a Markdown string (without the `::: {.column-margin}`
            wrapper). Empty string if no metadata is available.
        """
        package_root = self._find_package_root()
        metadata = self._get_package_metadata()

        # Determine which supporting pages exist (already created by _create_index_from_readme)
        license_qmd = self.project_path / "license.qmd"
        license_link = "license.qmd" if license_qmd.exists() else None
        citation_qmd = self.project_path / "citation.qmd"
        citation_link = "citation.qmd" if citation_qmd.exists() else None

        margin_sections: list[str] = []

        # ── 1. Links ─────────────────────────────────────────────────────
        links_items: list[str] = []

        package_name = self._detect_package_name()
        if package_name:
            pypi_url = f"https://pypi.org/project/{package_name}/"
            links_items.append(f"[View on PyPI]({pypi_url})<br>")

        if metadata.get("urls"):
            urls = metadata["urls"]
            url_map = {
                "homepage": None,
                "repository": "Browse source code",
                "bug_tracker": "Report a bug",
                "documentation": None,
            }
            for name, url in urls.items():
                name_lower = name.lower().replace(" ", "_")
                display_name = url_map.get(name_lower, name.replace("_", " ").title())
                if display_name:
                    links_items.append(f"[{display_name}]({url})<br>")

        if links_items:
            margin_sections.append("#### Links\n")
            margin_sections.extend(links_items)

        # ── 2. AI / Agents ───────────────────────────────────────────────
        ai_items: list[str] = []
        if self._config.skill_enabled:
            ai_items.append("[Skills](skills.html)<br>")
        ai_items.append("[llms.txt](llms.txt)<br>")
        ai_items.append("[llms-full.txt](llms-full.txt)<br>")

        margin_sections.append("\n#### AI / Agents\n")
        margin_sections.extend(ai_items)

        # ── 3. Developers (Authors + Funding) ────────────────────────────
        authors_to_display = metadata.get("rich_authors") or metadata.get("authors", [])
        funding = metadata.get("funding")
        has_funding = funding and isinstance(funding, dict) and funding.get("name")

        if authors_to_display or has_funding:
            margin_sections.append("\n#### Developers\n")

            # Authors
            fallback_github = None
            if metadata.get("urls"):
                repo_url = metadata["urls"].get("repository", "") or metadata["urls"].get(
                    "Repository", ""
                )
                if "github.com/" in repo_url:
                    parts = repo_url.rstrip("/").split("github.com/")
                    if len(parts) > 1:
                        username_part = parts[1].split("/")[0]
                        if username_part:
                            fallback_github = username_part

            dev_idx = 0
            for author in authors_to_display:
                if isinstance(author, dict):
                    name = author.get("name", "")
                    email = author.get("email", "")
                    role = author.get("role", "")
                    affiliation = author.get("affiliation", "")
                    github = author.get("github", "")
                    homepage = author.get("homepage", "") or author.get("url", "")
                    orcid = author.get("orcid", "")

                    author_html_parts = []
                    name_html = (
                        f'<span><p><strong style="padding-bottom: 4px;">{name}</strong></p></span>'
                    )
                    author_html_parts.append(name_html)

                    if role:
                        role_html = (
                            f'<span style="margin-top: -0.15em; display: block;">'
                            f"<p><small>{role}</small></p></span>"
                        )
                        author_html_parts.append(role_html)

                    if affiliation:
                        affiliation_html = (
                            f'<span><p><small style="margin-top: -0.15em; display: block;">'
                            f"{affiliation}</small></p></span>"
                        )
                        author_html_parts.append(affiliation_html)

                    icon_links = []
                    if email:
                        icon_links.append(
                            f'<a href="mailto:{email}" title="Email"><i class="bi bi-envelope-fill"></i></a>'
                        )
                    if github:
                        icon_links.append(
                            f'<a href="https://github.com/{github}" title="GitHub"><i class="bi bi-github"></i></a>'
                        )
                    elif fallback_github:
                        icon_links.append(
                            f'<a href="https://github.com/{fallback_github}" title="GitHub"><i class="bi bi-github"></i></a>'
                        )
                    if homepage:
                        icon_links.append(
                            f'<a href="{homepage}" title="Website"><i class="bi bi-globe"></i></a>'
                        )
                    if orcid:
                        orcid_url = (
                            orcid if orcid.startswith("http") else f"https://orcid.org/{orcid}"
                        )
                        icon_links.append(
                            f'<a href="{orcid_url}" title="ORCID"><i class="fa-brands fa-orcid"></i></a>'
                        )

                    if icon_links:
                        icon_html = (
                            '<span style="margin-top: -0.15em; display: block;">'
                            + " ".join(icon_links)
                            + "</span>"
                        )
                        author_html_parts.append(icon_html)

                    author_div_content = "".join(author_html_parts)
                    if dev_idx == 0:
                        margin_sections.append(f"<div>{author_div_content}</div>")
                    else:
                        margin_sections.append(
                            f'<div style="padding-top: 10px;">{author_div_content}</div>'
                        )
                    dev_idx += 1

            # Funding (rendered as another entry in the Developers section)
            if has_funding:
                funder_name = funding.get("name", "")
                roles = funding.get("roles", [])
                homepage = funding.get("homepage", "")
                ror_url = funding.get("ror", "")

                funder_html_parts = []
                name_html = f'<span><p><strong style="padding-bottom: 4px;">{funder_name}</strong></p></span>'
                funder_html_parts.append(name_html)

                if roles:
                    roles_text = ", ".join(roles)
                    roles_html = (
                        f'<span style="margin-top: -0.15em; display: block;">'
                        f"<p><small>{roles_text}</small></p></span>"
                    )
                    funder_html_parts.append(roles_html)

                icon_links = []
                if homepage:
                    icon_links.append(
                        f'<a href="{homepage}" title="Website"><i class="bi bi-globe"></i></a>'
                    )
                if ror_url:
                    ror_icon = (
                        '<svg class="ror-sidebar-icon" viewBox="0 0 164 118" '
                        'xmlns="http://www.w3.org/2000/svg" '
                        'style="width: 1em; height: 0.75em; vertical-align: -0.05em; fill: currentColor;">'
                        '<g transform="translate(-0.945,-0.815)">'
                        '<path d="M68.65,4.16L56.52,22.74L44.38,4.16L68.65,4.16Z" style="fill:rgb(83,186,161);"/>'
                        '<path d="M119.41,4.16L107.28,22.74L95.14,4.16L119.41,4.16Z" style="fill:rgb(83,186,161);"/>'
                        '<path d="M44.38,115.47L56.52,96.88L68.65,115.47L44.38,115.47Z" style="fill:rgb(83,186,161);"/>'
                        '<path d="M95.14,115.47L107.28,96.88L119.41,115.47L95.14,115.47Z" style="fill:rgb(83,186,161);"/>'
                        '<path d="M145.53,63.71C149.83,62.91 153.1,61 155.33,57.99C157.57,54.98 158.68,51.32 158.68,47.03C158.68,43.47 158.06,40.51 156.83,38.13C155.6,35.75 153.93,33.86 151.84,32.45C149.75,31.05 147.31,30.04 144.53,29.44C141.75,28.84 138.81,28.54 135.72,28.54L112.16,28.54L112.16,47.37C111.97,46.82 111.77,46.28 111.55,45.74C109.92,41.79 107.64,38.42 104.71,35.64C101.78,32.86 98.32,30.72 94.3,29.23C90.29,27.74 85.9,26.99 81.14,26.99C76.38,26.99 72,27.74 67.98,29.23C63.97,30.72 60.5,32.86 57.57,35.64C54.95,38.13 52.85,41.1 51.27,44.54C51.04,42.07 50.46,39.93 49.53,38.13C48.3,35.75 46.63,33.86 44.54,32.45C42.45,31.05 40.01,30.04 37.23,29.44C34.45,28.84 31.51,28.54 28.42,28.54L4.87,28.54L4.87,89.42L18.28,89.42L18.28,65.08L24.9,65.08L37.63,89.42L53.71,89.42L38.24,63.71C42.54,62.91 45.81,61 48.04,57.99C48.14,57.85 48.23,57.7 48.33,57.56C48.31,58.03 48.3,58.5 48.3,58.98C48.3,63.85 49.12,68.27 50.75,72.22C52.38,76.17 54.66,79.54 57.59,82.32C60.51,85.1 63.98,87.24 68,88.73C72.01,90.22 76.4,90.97 81.16,90.97C85.92,90.97 90.3,90.22 94.32,88.73C98.33,87.24 101.8,85.1 104.73,82.32C107.65,79.54 109.93,76.17 111.57,72.22C111.79,71.69 111.99,71.14 112.18,70.59L112.18,89.42L125.59,89.42L125.59,65.08L132.21,65.08L144.94,89.42L161.02,89.42L145.53,63.71ZM36.39,50.81C35.67,51.73 34.77,52.4 33.68,52.83C32.59,53.26 31.37,53.52 30.03,53.6C28.68,53.69 27.41,53.73 26.2,53.73L18.29,53.73L18.29,39.89L27.06,39.89C28.26,39.89 29.5,39.98 30.76,40.15C32.02,40.32 33.14,40.65 34.11,41.14C35.08,41.63 35.89,42.33 36.52,43.25C37.15,44.17 37.47,45.4 37.47,46.95C37.47,48.6 37.11,49.89 36.39,50.81ZM98.74,66.85C97.85,69.23 96.58,71.29 94.91,73.04C93.25,74.79 91.26,76.15 88.93,77.13C86.61,78.11 84.01,78.59 81.15,78.59C78.28,78.59 75.69,78.1 73.37,77.13C71.05,76.16 69.06,74.79 67.39,73.04C65.73,71.29 64.45,69.23 63.56,66.85C62.67,64.47 62.23,61.85 62.23,58.98C62.23,56.17 62.67,53.56 63.56,51.15C64.45,48.74 65.72,46.67 67.39,44.92C69.05,43.17 71.04,41.81 73.37,40.83C75.69,39.86 78.28,39.37 81.15,39.37C84.02,39.37 86.61,39.86 88.93,40.83C91.25,41.8 93.24,43.17 94.91,44.92C96.57,46.67 97.85,48.75 98.74,51.15C99.63,53.56 100.07,56.17 100.07,58.98C100.07,61.85 99.63,64.47 98.74,66.85ZM143.68,50.81C142.96,51.73 142.06,52.4 140.97,52.83C139.88,53.26 138.66,53.52 137.32,53.6C135.97,53.69 134.7,53.73 133.49,53.73L125.58,53.73L125.58,39.89L134.35,39.89C135.55,39.89 136.79,39.98 138.05,40.15C139.31,40.32 140.43,40.65 141.4,41.14C142.37,41.63 143.18,42.33 143.81,43.25C144.44,44.17 144.76,45.4 144.76,46.95C144.76,48.6 144.4,49.89 143.68,50.81Z" style="fill:currentColor;"/>'
                        "</g></svg>"
                    )
                    icon_links.append(
                        f'<a href="{ror_url}" title="Research Organization Registry">{ror_icon}</a>'
                    )

                if icon_links:
                    icon_html = (
                        '<span style="margin-top: -0.15em; display: block;">'
                        + " ".join(icon_links)
                        + "</span>"
                    )
                    funder_html_parts.append(icon_html)

                funder_div_content = "".join(funder_html_parts)
                if dev_idx == 0:
                    margin_sections.append(f"<div>{funder_div_content}</div>")
                else:
                    margin_sections.append(
                        f'<div style="padding-top: 10px;">{funder_div_content}</div>'
                    )

        # ── 4. Community (Contributing, CoC, License, Citation) ──────────
        community_items: list[str] = []

        # Check for CONTRIBUTING.md in root or .github directory
        contributing_path = package_root / "CONTRIBUTING.md"
        if not contributing_path.exists():
            contributing_path = package_root / ".github" / "CONTRIBUTING.md"

        # Check for CODE_OF_CONDUCT.md in root or .github directory
        coc_path = package_root / "CODE_OF_CONDUCT.md"
        if not coc_path.exists():
            coc_path = package_root / ".github" / "CODE_OF_CONDUCT.md"

        if contributing_path.exists():
            community_items.append("[Contributing guide](contributing.qmd)<br>")
            with open(contributing_path, "r", encoding="utf-8") as f:
                contributing_content = f.read()

            lines = contributing_content.split("\n")
            if lines and lines[0].startswith("# "):
                contributing_content = "\n".join(lines[1:]).lstrip()

            contributing_qmd = self.project_path / "contributing.qmd"
            contributing_qmd_content = f"""---
title: "Contributing"
---

{contributing_content}
"""
            with open(contributing_qmd, "w", encoding="utf-8") as f:
                f.write(contributing_qmd_content)

        if coc_path.exists():
            community_items.append("[Code of conduct](code-of-conduct.qmd)<br>")
            with open(coc_path, "r", encoding="utf-8") as f:
                coc_content = f.read()

            lines = coc_content.split("\n")
            if lines and lines[0].startswith("# "):
                coc_content = "\n".join(lines[1:]).lstrip()

            coc_qmd = self.project_path / "code-of-conduct.qmd"
            coc_qmd_content = f"""---
title: "Code of Conduct"
---

{coc_content}
"""
            with open(coc_qmd, "w", encoding="utf-8") as f:
                f.write(coc_qmd_content)

        # License (folded into Community)
        if license_link:
            community_items.append(f"[Full license]({license_link})<br>")
        elif metadata.get("license"):
            community_items.append(f"{metadata['license']}<br>")

        # Citation (folded into Community)
        if citation_link:
            pkg_display = package_name or self._detect_package_name() or "this package"
            community_items.append(f"[Citing {pkg_display}]({citation_link})<br>")

        if community_items:
            margin_sections.append("\n#### Community\n")
            margin_sections.extend(community_items)

        # ── 5. Meta ──────────────────────────────────────────────────────
        meta_items: list[str] = []
        if metadata.get("requires_python"):
            meta_items.append(f"**Requires:** Python `{metadata['requires_python']}`")

        if metadata.get("optional_dependencies"):
            extras = list(metadata["optional_dependencies"].keys())
            if extras:
                extras_formatted = ", ".join(f"`{extra}`" for extra in extras)
                meta_items.append(f"**Provides-Extra:** {extras_formatted}")

        if meta_items:
            margin_sections.append("\n#### Meta\n")
            margin_sections.append("<br>\n".join(meta_items))

        return "\n".join(margin_sections) if margin_sections else ""

    def _create_index_from_readme(self, force_rebuild: bool = False) -> None:
        """
        Create or update index.qmd from the best available source file.

        Source file priority (highest to lowest):
        1. index.qmd in project root
        2. index.md in project root
        3. README.md in project root
        4. README.rst in project root (converted to Markdown via pandoc)

        If none of these exist, a landing page is auto-generated from package
        metadata (name, description, install command, navigation links).
        Includes a metadata sidebar with package information (license, authors, links, etc.)

        Parameters
        ----------
        force_rebuild
            If `True`, always rebuild `index.qmd` even if it exists. Used by the build command to
            sync with source file changes.
        """
        package_root = self._find_package_root()

        # Always create license.qmd if LICENSE file exists
        license_path = package_root / "LICENSE"
        license_link = None
        if license_path.exists():
            license_qmd = self.project_path / "license.qmd"
            with open(license_path, "r", encoding="utf-8") as f:
                license_content = f.read()

            license_qmd_content = f"""---
title: "License"
---

```
{license_content}
```
"""
            with open(license_qmd, "w", encoding="utf-8") as f:
                f.write(license_qmd_content)
            print(f"Created {license_qmd}")
            license_link = "license.qmd"

        # Always create citation.qmd if CITATION.cff exists
        citation_path = package_root / "CITATION.cff"
        citation_link = None
        if citation_path.exists():
            citation_qmd = self.project_path / "citation.qmd"

            # Get metadata first to access rich_authors and repo info
            metadata = self._get_package_metadata()

            # Parse CITATION.cff for structured data

            with open(citation_path, "r", encoding="utf-8") as f:
                citation_data = read_yaml(f)

            # Get package name for intro paragraph
            package_name = metadata.get("name", "this package")

            # Build GitHub link to CITATION.cff if repo URL is available
            repo_url = citation_data.get("repository-code") or citation_data.get("url")
            citation_file_link = ""
            if repo_url:
                # Ensure URL doesn't end with trailing slash
                repo_url = repo_url.rstrip("/")
                citation_file_link = f"{repo_url}/blob/main/CITATION.cff"

            # Build intro paragraph
            intro_paragraph = f"""
To cite {package_name} in publications, please use the following citation.
"""

            # Build Authors section
            authors_section = "## Authors\n\n"
            if citation_data.get("authors"):
                for author in citation_data["authors"]:
                    given = author.get("given-names", "")
                    family = author.get("family-names", "")
                    full_name = f"{given} {family}".strip()

                    # Get role from rich_authors if available
                    role = "Author"
                    if metadata.get("rich_authors"):
                        for rich_author in metadata["rich_authors"]:
                            if rich_author.get("name") == full_name:
                                role = rich_author.get("role", "Author")
                                break

                    authors_section += f"{full_name}. {role}.  \n"

            # Build Citation section with text and BibTeX
            citation_section = "## Citation\n\n"

            # Add link to CITATION.cff on GitHub if available
            if citation_file_link:
                citation_section += f"**Source:** [`CITATION.cff`]({citation_file_link})\n\n"
            else:
                citation_section += "**Source:** `CITATION.cff`\n\n"

            # Parse year from date-released field or use current year (used in multiple places)
            from datetime import datetime

            year = datetime.now().year
            if citation_data.get("date-released"):
                try:
                    date_released = citation_data["date-released"]
                    if isinstance(date_released, str):
                        year = datetime.fromisoformat(date_released).year
                    elif hasattr(date_released, "year"):
                        year = date_released.year
                except (ValueError, AttributeError):
                    pass  # Keep current year as fallback

            # Generate text citation
            if citation_data.get("authors"):
                # For text citation, use "et al." if more than 2 authors
                author_list = citation_data["authors"]
                if len(author_list) == 1:
                    author = author_list[0]
                    family = author.get("family-names", "")
                    given = author.get("given-names", "")
                    initial = given[0] if given else ""
                    authors_str = f"{family} {initial}" if initial else family
                elif len(author_list) == 2:
                    author_names = []
                    for author in author_list:
                        family = author.get("family-names", "")
                        given = author.get("given-names", "")
                        initial = given[0] if given else ""
                        author_names.append(f"{family} {initial}" if initial else family)
                    authors_str = " and ".join(author_names)
                else:
                    # More than 2 authors: use first author et al.
                    author = author_list[0]
                    family = author.get("family-names", "")
                    given = author.get("given-names", "")
                    initial = given[0] if given else ""
                    first_author = f"{family} {initial}" if initial else family
                    authors_str = f"{first_author} et al."

            # Generate BibTeX
            citation_section += "### BibTeX\n\n"
            citation_section += "```bibtex\n"
            citation_section += "@Manual{,\n"

            if citation_data.get("title"):
                citation_section += f"  title = {{{citation_data['title']}}},\n"

            if citation_data.get("authors"):
                author_names = []
                for author in citation_data["authors"]:
                    given = author.get("given-names", "")
                    family = author.get("family-names", "")
                    full_name = f"{given} {family}".strip()
                    author_names.append(full_name)
                citation_section += f"  author = {{{' and '.join(author_names)}}},\n"

            citation_section += f"  year = {{{year}}},\n"

            if citation_data.get("version"):
                citation_section += (
                    f"  note = {{Python package version {citation_data['version']}}},\n"
                )

            if citation_data.get("url"):
                citation_section += f"  url = {{{citation_data['url']}}},\n"

            citation_section += "}\n```\n\n"

            # Generate APA format
            citation_section += "### APA\n\n"
            if citation_data.get("authors"):
                # APA format: Author, A. A., Author, B. B., & Author, C. C. (Year).
                author_list = citation_data["authors"]
                apa_authors = []
                for author in author_list:
                    family = author.get("family-names", "")
                    given = author.get("given-names", "")
                    # Get initials from given names
                    initials = (
                        ". ".join([name[0] for name in given.split() if name]) + "."
                        if given
                        else ""
                    )
                    apa_authors.append(f"{family}, {initials}" if initials else family)

                if len(apa_authors) == 1:
                    apa_authors_str = apa_authors[0]
                elif len(apa_authors) == 2:
                    apa_authors_str = f"{apa_authors[0]} & {apa_authors[1]}"
                else:
                    # For 3+ authors, use commas and & before last
                    apa_authors_str = ", ".join(apa_authors[:-1]) + ", & " + apa_authors[-1]

                title = citation_data.get("title", "")
                version = citation_data.get("version", "")
                url = citation_data.get("url", "")

                # APA software citation format
                citation_section += f"{apa_authors_str} ({year}). *{title}* (Version {version}) [Computer software]. {url}\n\n"

            # Generate RIS format (for reference managers like Zotero, Mendeley, EndNote)
            citation_section += "### RIS\n\n"
            citation_section += "```ris\n"
            citation_section += "TY  - COMP\n"  # Type: Computer Program

            if citation_data.get("title"):
                citation_section += f"TI  - {citation_data['title']}\n"

            if citation_data.get("authors"):
                for author in citation_data["authors"]:
                    given = author.get("given-names", "")
                    family = author.get("family-names", "")
                    # RIS format: AU  - Last, First
                    citation_section += f"AU  - {family}, {given}\n"

            citation_section += f"PY  - {year}\n"

            if citation_data.get("version"):
                citation_section += f"VL  - {citation_data['version']}\n"

            if citation_data.get("url"):
                citation_section += f"UR  - {citation_data['url']}\n"

            if citation_data.get("abstract"):
                citation_section += f"AB  - {citation_data['abstract']}\n"

            citation_section += "ER  - \n"
            citation_section += "```\n"

            citation_qmd_content = f"""---
title: "Authors and Citation"
---
{intro_paragraph}

{authors_section}

{citation_section}
"""
            with open(citation_qmd, "w", encoding="utf-8") as f:
                f.write(citation_qmd_content)
            print(f"Created {citation_qmd}")
            citation_link = "citation.qmd"

        # Now check if we should create index.qmd
        index_qmd = self.project_path / "index.qmd"

        # In "user_guide" homepage mode, the first UG page becomes index.qmd
        # instead — skip README-based index generation entirely.
        # The _homepage_fallback_to_index flag overrides this when no UG pages exist.
        if self._config.homepage == "user_guide" and not getattr(
            self, "_homepage_fallback_to_index", False
        ):
            return

        if index_qmd.exists() and not force_rebuild:
            print("index.qmd already exists, skipping creation")
            return

        # Find the best source file
        source_file, warnings = self._find_index_source_file()

        # Print any warnings about multiple source files
        for warning in warnings:
            print(warning)

        if source_file is None:
            print("No index source file found (index.qmd, index.md, README.md, or README.rst)")
            print("Generating landing page from package metadata...")
            readme_content = self._generate_landing_page_content(self._get_package_metadata())
        else:
            source_name = source_file.name
            if force_rebuild:
                print(f"Rebuilding index.qmd from {source_name}...")
            else:
                print(f"Creating index.qmd from {source_name}...")

            # Read source content
            with open(source_file, "r", encoding="utf-8") as f:
                readme_content = f.read()

            # Convert RST to Markdown using Quarto's bundled pandoc
            if source_file.suffix.lower() == ".rst":
                readme_content = self._convert_rst_to_markdown(source_file)

        # Build hero section (must run before heading adjustment so badge
        # extraction works on original markdown)
        hero_html, cleaned_content = self._build_hero_section(readme_content)
        if cleaned_content is not None:
            readme_content = cleaned_content

        # If hero displays the package name, strip a matching first heading
        # to avoid visual duplication
        if hero_html and self._config.hero_enabled:
            import re as _re

            hero_name = self._config.hero_name
            if hero_name is None:
                metadata = self._get_package_metadata()
                hero_name = metadata.get("name") or self._detect_package_name()
            if hero_name:
                first_h1 = _re.match(r"^#\s+(.+)$", readme_content.strip(), _re.MULTILINE)
                if first_h1 and first_h1.group(1).strip().lower() == hero_name.strip().lower():
                    readme_content = readme_content.replace(first_h1.group(0), "", 1).lstrip("\n")

        if source_file is not None:
            # Adjust heading levels: bump all headings up by one level
            # This prevents h1 from becoming paragraphs and keeps proper hierarchy
            # Replace headings from highest to lowest level to avoid double-replacement
            import re

            readme_content = re.sub(r"^######\s+", r"####### ", readme_content, flags=re.MULTILINE)
            readme_content = re.sub(r"^#####\s+", r"###### ", readme_content, flags=re.MULTILINE)
            readme_content = re.sub(r"^####\s+", r"##### ", readme_content, flags=re.MULTILINE)
            readme_content = re.sub(r"^###\s+", r"#### ", readme_content, flags=re.MULTILINE)
            readme_content = re.sub(r"^##\s+", r"### ", readme_content, flags=re.MULTILINE)
            readme_content = re.sub(r"^#\s+", r"## ", readme_content, flags=re.MULTILINE)

        # Build margin content using the shared helper
        margin_content = self._build_metadata_margin()

        # CSS to reduce top margin of first heading element
        # The heading ends up inside a section.level1 > h1 structure
        first_heading_style = """<style>
section.level1:first-of-type > h1:first-child,
section.level2:first-of-type > h2:first-child,
.column-body-outset-right > section.level1:first-of-type > h1,
#quarto-document-content > section:first-of-type > h1 {
  margin-top: 4px !important;
}
</style>

"""

        # Create a qmd file with the README content
        # Use empty title so "Home" doesn't appear on landing page
        # Add margin content in a special div that Quarto will place in the margin
        # Prepend hero section (raw HTML block) when enabled
        hero_block = ""
        if hero_html:
            hero_block = f"""```{{=html}}
{hero_html}```

"""

        if margin_content:
            qmd_content = f"""---
title: ""
toc: false
---

{first_heading_style}{hero_block}::: {{.column-margin}}
{margin_content}
:::

{readme_content}
"""
        else:
            qmd_content = f"""---
title: ""
toc: false
---

{first_heading_style}{hero_block}{readme_content}
"""

        with open(index_qmd, "w", encoding="utf-8") as f:
            f.write(qmd_content)

        print(f"Created {index_qmd}")

    def _add_api_reference_config(self) -> None:
        """
        Add API reference configuration to _quarto.yml if not present.

        Adds sensible defaults for API reference generation with automatic
        package detection.  If no documentable exports are discovered (and no
        explicit `reference` config exists in great-docs.yml), the method
        skips API reference setup entirely and sets
        `self._has_api_reference = False`.
        """
        # Explicit opt-out via great-docs.yml
        if not self._config.reference_enabled:
            print("API reference disabled (reference: false), skipping")
            self._has_api_reference = False
            return

        quarto_yml = self.project_path / "_quarto.yml"

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

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
                self._has_api_reference = False
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
                print(f"Detected module name: {module_name}")
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

        # If no documentable exports were found, skip API reference entirely
        if not sections:
            print("No documentable exports found — skipping API reference")
            self._has_api_reference = False
            return

        # Add API reference configuration with sensible defaults
        # Use the importable name (actual module name) for the package field
        ref_title = self._config.reference_title or "Reference"
        ref_desc = self._config.reference_desc

        # Configure the qrenderer
        renderer_config = {"style": "_renderer.py"}

        api_ref_config = {
            "package": importable_name,
            "dir": "reference",
            "title": ref_title,
            "style": "pkgdown",
            "renderer": renderer_config,
        }
        if ref_desc:
            api_ref_config["desc"] = ref_desc

        # Get dynamic setting from great-docs.yml config (defaults to True)
        dynamic = self._config.dynamic
        api_ref_config["dynamic"] = dynamic
        if not dynamic:
            print("Using static introspection mode (dynamic: false)")

        # Get parser from great-docs.yml config (defaults to numpy)
        parser = self._config.parser
        if parser and parser != "numpy":
            # Only add parser if it's not the default (numpy)
            api_ref_config["parser"] = parser
            print(f"Using '{parser}' docstring parser")
        else:
            # Always explicitly set parser for clarity
            api_ref_config["parser"] = "numpy"

        # Get jupyter kernel from great-docs.yml config (defaults to python3)
        jupyter_kernel = self._config.jupyter
        if jupyter_kernel:
            config["jupyter"] = jupyter_kernel
            print(f"Using '{jupyter_kernel}' Jupyter kernel")

        api_ref_config["sections"] = sections
        print(f"Auto-generated {len(sections)} section(s) from package exports")

        config["api-reference"] = api_ref_config

        # Add "Reference" link to navbar
        if "website" in config and "navbar" in config["website"]:
            navbar = config["website"]["navbar"]
            left = navbar.get("left", [])
            # Only add if not already present
            has_ref = any(
                isinstance(item, dict) and item.get("href") == "reference/index.qmd"
                for item in left
            )
            if not has_ref:
                left.append({"text": ref_title, "href": "reference/index.qmd"})
                navbar["left"] = left

        # Add reference sidebar
        if "website" in config and "sidebar" in config["website"]:
            sidebars = config["website"]["sidebar"]
            has_ref_sidebar = any(
                isinstance(s, dict) and s.get("id") == "reference" for s in sidebars
            )
            if not has_ref_sidebar:
                sidebars.append({"id": "reference", "contents": "reference/"})

        # Write back to file
        self._write_quarto_yml(quarto_yml, config)

        print(f"Added API reference configuration to {quarto_yml}")

    def _refresh_api_reference_config(self) -> None:
        """
        Refresh the API reference sections in _quarto.yml based on current package exports.

        This method re-discovers the package API and updates the API reference sections without touching
        other configuration. Use this when your package API has changed (new classes, methods, or
        functions added/removed).

        The method preserves:

        - package name and other API reference settings
        - all non-API reference configuration in _quarto.yml

        Only the 'sections' key in API reference config is regenerated.
        """
        quarto_yml = self.project_path / "_quarto.yml"

        if not quarto_yml.exists():
            print("Error: _quarto.yml not found. Run 'great-docs init' first.")
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        if "api-reference" not in config:
            print("Error: No API reference configuration found. Run 'great-docs init' first.")
            return

        # Get the package name from existing config
        package_name = config["api-reference"].get("package")
        if not package_name:
            print("Error: No package name in API reference config.")
            return

        print(f"Re-discovering exports for package: {package_name}")

        # Re-generate sections from current package exports
        # Prioritizes explicit config from great-docs.yml over auto-discovery
        sections = self._create_api_sections_with_config(package_name)

        # Update parser and dynamic settings from great-docs.yml config
        parser = self._config.parser
        if parser:
            config["api-reference"]["parser"] = parser

        dynamic = self._config.dynamic
        config["api-reference"]["dynamic"] = dynamic

        # Update title and desc from great-docs.yml config
        ref_title = self._config.reference_title
        if ref_title:
            config["api-reference"]["title"] = ref_title
        ref_desc = self._config.reference_desc
        if ref_desc:
            config["api-reference"]["desc"] = ref_desc
        elif "desc" in config["api-reference"]:
            # Remove desc if it was previously set but is now absent
            del config["api-reference"]["desc"]

        # Update jupyter kernel from great-docs.yml config
        jupyter_kernel = self._config.jupyter
        if jupyter_kernel:
            config["jupyter"] = jupyter_kernel

        if sections:
            config["api-reference"]["sections"] = sections
            print(f"Updated API reference config with {len(sections)} section(s)")

            # Write back to file first, so sidebar update reads the new sections
            self._write_quarto_yml(quarto_yml, config)

            # Now update the sidebar to match the new sections
            self._update_sidebar_from_sections()

            print(f"✅ Refreshed API reference configuration in {quarto_yml}")
        else:
            # Check if user has explicit reference config that should be applied
            # even though auto-discovery failed
            reference_config = self._config.reference
            if reference_config:
                print(
                    "Auto-discovery failed, but applying explicit reference config from great-docs.yml"
                )
                # Build sections directly from user config without validation
                user_sections = self._build_sections_from_reference_config(reference_config)
                if user_sections:
                    config["api-reference"]["sections"] = user_sections
                    self._write_quarto_yml(quarto_yml, config)
                    self._update_sidebar_from_sections()
                    print(f"✅ Applied {len(user_sections)} section(s) from great-docs.yml")
                else:
                    print("Warning: reference config in great-docs.yml produced no sections")
            else:
                print("Warning: Could not discover package exports. Config unchanged.")
                print(
                    "Tip: Add a 'reference' section to great-docs.yml to manually specify your API structure."
                )

    def _write_quarto_yml(self, quarto_yml: Path, config: dict) -> None:
        """
        Write _quarto.yml with a header comment.

        Parameters
        ----------
        quarto_yml
            Path to the _quarto.yml file.
        config
            The configuration dictionary to write.
        """
        header_comment = (
            "# Generated by Great Docs - Do not modify this file by hand.\n"
            "# Configure settings in great-docs.yml instead.\n\n"
        )
        with open(quarto_yml, "w") as f:
            f.write(header_comment)
            write_yaml(config, f)

    def _update_quarto_config(self) -> None:
        """
        Update _quarto.yml with great-docs configuration.

        This private method modifies the Quarto configuration file to include the
        post-render script, CSS file, and website navigation required by great-docs.
        It preserves existing configuration while adding the necessary great-docs
        settings. If website navigation is not present, it adds a navbar with Home
        and API Reference links, and sets the site title to the package name.
        """
        quarto_yml = self.project_path / "_quarto.yml"

        if not quarto_yml.exists():
            print("Warning: _quarto.yml not found. Creating minimal configuration...")
            config = {
                "project": {"type": "website", "post-render": "scripts/post-render.py"},
                "format": {"html": {"theme": "flatly"}},
            }
        else:
            # Load existing configuration
            with open(quarto_yml, "r") as f:
                config = read_yaml(f) or {}

        # Ensure required structure exists
        if "project" not in config:
            config["project"] = {}
        if "format" not in config:
            config["format"] = {}
        if "html" not in config["format"]:
            config["format"]["html"] = {}

        # Add post-render script
        config["project"]["post-render"] = "scripts/post-render.py"

        # Add resources to copy static JS files to _site
        if "resources" not in config["project"]:
            config["project"]["resources"] = []
        elif isinstance(config["project"]["resources"], str):
            config["project"]["resources"] = [config["project"]["resources"]]

        # Ensure JS files are included as resources
        js_resource_files = [
            "github-widget.js",
            "sidebar-filter.js",
            "sidebar-wrap.js",
            "dark-mode-toggle.js",
            "theme-init.js",
        ]
        if self._config.markdown_pages_widget:
            js_resource_files.append("copy-page.js")
        for js_file in js_resource_files:
            if js_file not in config["project"]["resources"]:
                config["project"]["resources"].append(js_file)

        # Add assets directory to resources if it exists
        assets_dir = self.project_path / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            if "assets/**" not in config["project"]["resources"]:
                config["project"]["resources"].append("assets/**")

        # Add skill.md and .well-known to resources (so Quarto copies them to _site)
        # Also exclude them from rendering so Quarto doesn't convert them to HTML
        if self._config.skill_enabled:
            if "skill.md" not in config["project"]["resources"]:
                config["project"]["resources"].append("skill.md")

            # Exclude skill.md from rendering (Quarto renders .md by default)
            # The render list needs "**" first (render everything), then exclusions
            if "render" not in config["project"]:
                config["project"]["render"] = ["**"]
            if "!skill.md" not in config["project"]["render"]:
                config["project"]["render"].append("!skill.md")

            if self._config.skill_well_known:
                if ".well-known/**" not in config["project"]["resources"]:
                    config["project"]["resources"].append(".well-known/**")
                if "!.well-known/**" not in config["project"]["render"]:
                    config["project"]["render"].append("!.well-known/**")

        # Apply site settings from great-docs.yml (forwarded to format.html)
        site_settings = self._config.site
        config["format"]["html"]["theme"] = site_settings.get("theme", "flatly")
        config["format"]["html"]["toc"] = site_settings.get("toc", True)
        config["format"]["html"]["toc-depth"] = site_settings.get("toc-depth", 2)
        config["format"]["html"]["toc-title"] = site_settings.get("toc-title", "On this page")

        if "great-docs.scss" not in config["format"]["html"]["theme"]:
            if isinstance(config["format"]["html"]["theme"], str):
                config["format"]["html"]["theme"] = [config["format"]["html"]["theme"]]
            config["format"]["html"]["theme"].append("great-docs.scss")

        if "shift-heading-level-by" not in config["format"]["html"]:
            config["format"]["html"]["shift-heading-level-by"] = -1

        # Add Font Awesome for ORCID icon support
        if "include-in-header" not in config["format"]["html"]:
            config["format"]["html"]["include-in-header"] = []
        elif isinstance(config["format"]["html"]["include-in-header"], str):
            config["format"]["html"]["include-in-header"] = [
                config["format"]["html"]["include-in-header"]
            ]

        # Merge user-provided include-in-header entries from great-docs.yml
        for entry in self._config.include_in_header:
            if entry not in config["format"]["html"]["include-in-header"]:
                config["format"]["html"]["include-in-header"].append(entry)

        # Add Font Awesome CDN if not already present
        fa_cdn = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
        fa_entry = {"text": fa_cdn}
        if fa_entry not in config["format"]["html"]["include-in-header"]:
            # Check if any Font Awesome link already exists
            has_fa = any(
                "font-awesome" in str(item).lower()
                for item in config["format"]["html"]["include-in-header"]
            )
            if not has_fa:
                config["format"]["html"]["include-in-header"].append(fa_entry)

        # Add website navigation if not present
        if "website" not in config:
            config["website"] = {}

        # Enable page navigation for TOC
        if "page-navigation" not in config["website"]:
            config["website"]["page-navigation"] = True

        # Set title to package name if not already set
        if "title" not in config["website"]:
            # Use display_name from config if available, otherwise use package name as-is
            display_name = self._config.display_name
            if display_name:
                config["website"]["title"] = display_name
            else:
                package_name = self._detect_package_name()
                if package_name:
                    config["website"]["title"] = package_name

        # Get GitHub info and style preference
        owner, repo, repo_url = self._get_github_repo_info()
        metadata = self._get_package_metadata()
        github_style = metadata.get("github_style", "widget")  # "widget" or "icon"

        # Add or update navbar
        if "navbar" not in config["website"]:
            navbar_config = {
                "left": [],
            }

            # Add GitHub link on the right if repository URL is available
            if owner and repo and repo_url and github_style == "widget":
                gh_widget_html = (
                    f'<div id="github-widget" data-owner="{owner}" data-repo="{repo}"></div>'
                )
                navbar_config["right"] = [{"text": gh_widget_html}]
            elif repo_url:
                navbar_config["right"] = [{"icon": "github", "href": repo_url}]

            config["website"]["navbar"] = navbar_config
        else:
            # Update existing navbar: upgrade icon to widget if configured
            self._update_navbar_github_link(config, owner, repo, repo_url, github_style)

            # Remove legacy "Home" link (package name in navbar already links home)
            if "left" in config["website"]["navbar"]:
                config["website"]["navbar"]["left"] = [
                    item
                    for item in config["website"]["navbar"]["left"]
                    if not (isinstance(item, dict) and item.get("text") == "Home")
                ]

        # --- Logo & favicon injection ---
        logo_config = self._config.logo
        if logo_config is None:
            # Auto-detect logo from conventional paths
            logo_config = self._detect_logo()

        if logo_config is not None:
            package_root = self._find_package_root()
            navbar = config["website"]["navbar"]

            # Copy logo files into the Quarto project directory
            light_src = package_root / logo_config["light"]
            if light_src.is_file():
                light_dest_name = light_src.name
                # Avoid name collision: prefix with "logo-light" if needed
                if logo_config.get("dark") and logo_config["dark"] != logo_config["light"]:
                    if light_dest_name == Path(logo_config["dark"]).name:
                        light_dest_name = f"logo-light{light_src.suffix}"
                shutil.copy2(light_src, self.project_path / light_dest_name)
                navbar["logo"] = light_dest_name
            else:
                print(f"Warning: Logo file not found: {light_src}")

            # Dark variant
            dark_path = logo_config.get("dark")
            if dark_path and dark_path != logo_config["light"]:
                dark_src = package_root / dark_path
                if dark_src.is_file():
                    dark_dest_name = dark_src.name
                    shutil.copy2(dark_src, self.project_path / dark_dest_name)
                    navbar["logo-dark"] = dark_dest_name

                    # Ensure the dark logo is included as a resource so Quarto
                    # copies it to _site (needed for custom dark-mode toggle)
                    if "resources" not in config["project"]:
                        config["project"]["resources"] = []
                    if dark_dest_name not in config["project"]["resources"]:
                        config["project"]["resources"].append(dark_dest_name)

                    # Inject a meta tag so dark-mode-toggle.js can find the
                    # dark logo path and fix the navbar <img> src at runtime
                    dark_logo_meta = {
                        "text": f'<meta name="gd-logo-dark" content="{dark_dest_name}">'
                    }
                    header_list = config["format"]["html"].setdefault("include-in-header", [])
                    if not any("gd-logo-dark" in str(h) for h in header_list):
                        header_list.append(dark_logo_meta)
                else:
                    print(f"Warning: Dark logo file not found: {dark_src}")

            # Alt text (for accessibility)
            alt_text = logo_config.get("alt")
            if not alt_text:
                # Fall back to display name or package name
                alt_text = self._config.display_name or self._detect_package_name() or ""
            if alt_text:
                navbar["logo-alt"] = alt_text

            # Logo href (defaults to site root)
            logo_href = logo_config.get("href")
            if logo_href:
                navbar["logo-href"] = logo_href

            # Suppress the text title in the navbar unless show_title is True
            if not self._config.logo_show_title:
                navbar["title"] = False

            # Favicon: use explicit config, or auto-generate from logo
            favicon_config = self._config.favicon
            generated: dict[str, str] = {}
            if favicon_config is not None:
                # User supplied explicit favicon — generate raster variants too
                icon_src_path = favicon_config.get("icon")
                if icon_src_path:
                    fav_src = package_root / icon_src_path
                    if fav_src.is_file():
                        generated = self._generate_favicons(fav_src, self.project_path)
                        if generated.get("icon"):
                            config["website"]["favicon"] = generated["icon"]
                        else:
                            # Fallback: just copy the file
                            shutil.copy2(fav_src, self.project_path / fav_src.name)
                            config["website"]["favicon"] = fav_src.name
                    else:
                        print(f"Warning: Favicon file not found: {fav_src}")
            elif light_src.is_file():
                # Auto-generate favicons from the logo
                generated = self._generate_favicons(light_src, self.project_path)
                if generated.get("icon"):
                    config["website"]["favicon"] = generated["icon"]

            # Inject <link> tags for extra favicon assets
            if generated:
                favicon_links: list[str] = []
                if generated.get("icon") and generated["icon"].endswith(".ico"):
                    favicon_links.append(
                        '<link rel="icon" type="image/x-icon" href="favicon.ico" sizes="48x48">'
                    )
                if generated.get("icon-svg"):
                    favicon_links.append(
                        '<link rel="icon" type="image/svg+xml" href="favicon.svg">'
                    )
                if generated.get("icon-32"):
                    favicon_links.append(
                        '<link rel="icon" type="image/png" sizes="32x32" href="favicon-32x32.png">'
                    )
                if generated.get("icon-16"):
                    favicon_links.append(
                        '<link rel="icon" type="image/png" sizes="16x16" href="favicon-16x16.png">'
                    )
                if generated.get("apple-touch-icon"):
                    favicon_links.append(
                        '<link rel="apple-touch-icon" sizes="180x180" href="apple-touch-icon.png">'
                    )

                if favicon_links:
                    header_items = config["format"]["html"].get("include-in-header", [])
                    if isinstance(header_items, str):
                        header_items = [header_items]
                    for link_tag in favicon_links:
                        entry = {"text": link_tag}
                        if not any(link_tag in str(item) for item in header_items):
                            header_items.append(entry)
                    config["format"]["html"]["include-in-header"] = header_items

        # Add GitHub widget script to page if using widget style
        if owner and repo and github_style == "widget":
            if "include-after-body" not in config["format"]["html"]:
                config["format"]["html"]["include-after-body"] = []
            elif isinstance(config["format"]["html"]["include-after-body"], str):
                config["format"]["html"]["include-after-body"] = [
                    config["format"]["html"]["include-after-body"]
                ]

            # Add the GitHub widget script
            gh_script_entry = {"text": '<script src="github-widget.js"></script>'}
            if gh_script_entry not in config["format"]["html"]["include-after-body"]:
                # Check if github-widget.js is already included
                has_gh_widget = any(
                    "github-widget" in str(item)
                    for item in config["format"]["html"]["include-after-body"]
                )
                if not has_gh_widget:
                    config["format"]["html"]["include-after-body"].append(gh_script_entry)

        # Add copy-page widget script (if markdown_pages widget is enabled)
        if metadata.get("markdown_pages_widget", True):
            if "include-after-body" not in config["format"]["html"]:
                config["format"]["html"]["include-after-body"] = []
            elif isinstance(config["format"]["html"]["include-after-body"], str):
                config["format"]["html"]["include-after-body"] = [
                    config["format"]["html"]["include-after-body"]
                ]

            copy_page_entry = {"text": '<script src="copy-page.js"></script>'}
            has_copy_page = any(
                "copy-page" in str(item) for item in config["format"]["html"]["include-after-body"]
            )
            if not has_copy_page:
                config["format"]["html"]["include-after-body"].append(copy_page_entry)

        # Add sidebar smart-wrap script (inserts <wbr> for pretty line breaks)
        if "include-after-body" not in config["format"]["html"]:
            config["format"]["html"]["include-after-body"] = []
        elif isinstance(config["format"]["html"]["include-after-body"], str):
            config["format"]["html"]["include-after-body"] = [
                config["format"]["html"]["include-after-body"]
            ]

        wrap_script_entry = {"text": '<script src="sidebar-wrap.js"></script>'}
        has_wrap = any(
            "sidebar-wrap" in str(item) for item in config["format"]["html"]["include-after-body"]
        )
        if not has_wrap:
            config["format"]["html"]["include-after-body"].append(wrap_script_entry)

        # Add sidebar filter script if enabled
        if metadata.get("sidebar_filter_enabled", True):
            if "include-after-body" not in config["format"]["html"]:
                config["format"]["html"]["include-after-body"] = []
            elif isinstance(config["format"]["html"]["include-after-body"], str):
                config["format"]["html"]["include-after-body"] = [
                    config["format"]["html"]["include-after-body"]
                ]

            # Add the sidebar filter script
            filter_script_entry = {"text": '<script src="sidebar-filter.js"></script>'}
            has_filter = any(
                "sidebar-filter" in str(item)
                for item in config["format"]["html"]["include-after-body"]
            )
            if not has_filter:
                config["format"]["html"]["include-after-body"].append(filter_script_entry)

            # Add data attributes for configuration (must be before sidebar-filter.js)
            min_items = metadata.get("sidebar_filter_min_items", 20)
            if min_items != 20:
                # Add custom min_items via body data attribute and insert BEFORE the filter script
                min_items_script = {
                    "text": f'<script>document.body.dataset.sidebarFilterMinItems = "{min_items}";</script>'
                }
                has_min_items = any(
                    "sidebarFilterMinItems" in str(item)
                    for item in config["format"]["html"]["include-after-body"]
                )
                if not has_min_items:
                    # Insert before the sidebar-filter.js script
                    filter_index = next(
                        (
                            i
                            for i, item in enumerate(config["format"]["html"]["include-after-body"])
                            if "sidebar-filter" in str(item)
                        ),
                        len(config["format"]["html"]["include-after-body"]),
                    )
                    config["format"]["html"]["include-after-body"].insert(
                        filter_index, min_items_script
                    )

        # Add dark mode toggle script (if enabled)
        dark_mode_enabled = metadata.get("dark_mode_toggle_enabled", True)
        if dark_mode_enabled:
            if "include-after-body" not in config["format"]["html"]:
                config["format"]["html"]["include-after-body"] = []
            elif isinstance(config["format"]["html"]["include-after-body"], str):
                config["format"]["html"]["include-after-body"] = [
                    config["format"]["html"]["include-after-body"]
                ]

            dark_mode_script_entry = {"text": '<script src="dark-mode-toggle.js"></script>'}
            has_dark_mode = any(
                "dark-mode-toggle" in str(item)
                for item in config["format"]["html"]["include-after-body"]
            )
            if not has_dark_mode:
                config["format"]["html"]["include-after-body"].append(dark_mode_script_entry)

            # Add early theme detection script in header to prevent flash of wrong theme
            if "include-in-header" not in config["format"]["html"]:
                config["format"]["html"]["include-in-header"] = []
            elif isinstance(config["format"]["html"]["include-in-header"], str):
                config["format"]["html"]["include-in-header"] = [
                    config["format"]["html"]["include-in-header"]
                ]

            # Reference external script file for early theme detection (cleaner YAML)
            early_theme_script = {"text": '<script src="theme-init.js"></script>'}
            has_early_theme = any(
                "theme-init" in str(item) for item in config["format"]["html"]["include-in-header"]
            )
            if not has_early_theme:
                config["format"]["html"]["include-in-header"].append(early_theme_script)

        # Add reference switcher script (if CLI is enabled)
        cli_enabled = metadata.get("cli_enabled", False)
        if cli_enabled:
            if "include-after-body" not in config["format"]["html"]:
                config["format"]["html"]["include-after-body"] = []
            elif isinstance(config["format"]["html"]["include-after-body"], str):
                config["format"]["html"]["include-after-body"] = [
                    config["format"]["html"]["include-after-body"]
                ]

            ref_switcher_script_entry = {"text": '<script src="reference-switcher.js"></script>'}
            has_ref_switcher = any(
                "reference-switcher" in str(item)
                for item in config["format"]["html"]["include-after-body"]
            )
            if not has_ref_switcher:
                config["format"]["html"]["include-after-body"].append(ref_switcher_script_entry)

        # Add sidebar navigation (reference sidebar added later by
        # _add_api_reference_config if exports are discovered)
        if "sidebar" not in config["website"]:
            config["website"]["sidebar"] = []

        # Add page footer with "Developed by" notice (pkgdown style) if not present
        if "page-footer" not in config["website"]:
            metadata = self._get_package_metadata()

            # Build a dict of author name -> homepage URL from rich_authors
            author_homepages: dict[str, str] = {}
            for author in metadata.get("rich_authors", []):
                if isinstance(author, dict) and author.get("name"):
                    homepage = author.get("homepage", "")
                    if homepage:
                        author_homepages[author["name"]] = homepage

            # Collect all author/maintainer names from pyproject.toml
            author_names: list[str] = []
            for author in metadata.get("authors", []):
                if isinstance(author, dict) and author.get("name"):
                    author_names.append(author["name"])
                elif isinstance(author, str):
                    author_names.append(author)

            for maintainer in metadata.get("maintainers", []):
                if isinstance(maintainer, dict) and maintainer.get("name"):
                    name = maintainer["name"]
                    if name not in author_names:
                        author_names.append(name)
                elif isinstance(maintainer, str) and maintainer not in author_names:
                    author_names.append(maintainer)

            # Also check rich_authors from great-docs.yml (may have more detail)
            for author in metadata.get("rich_authors", []):
                if isinstance(author, dict) and author.get("name"):
                    name = author["name"]
                    if name not in author_names:
                        author_names.append(name)

            if author_names:
                # Format names, making them links if they have a homepage
                formatted_names: list[str] = []
                for name in author_names:
                    # Use non-breaking spaces so each name stays on one line
                    display_name = name.replace(" ", "&nbsp;")
                    if name in author_homepages:
                        formatted_names.append(
                            f'<a href="{author_homepages[name]}"><strong>{display_name}</strong></a>'
                        )
                    else:
                        formatted_names.append(f"<strong>{display_name}</strong>")

                # Format as "Developed by Name1 and Name2." or "Developed by Name1, Name2, and Name3."
                if len(formatted_names) == 1:
                    developed_by = f"Developed by {formatted_names[0]}."
                elif len(formatted_names) == 2:
                    developed_by = f"Developed by {formatted_names[0]} and {formatted_names[1]}."
                else:
                    developed_by = (
                        "Developed by "
                        + ", ".join(formatted_names[:-1])
                        + ", and "
                        + formatted_names[-1]
                        + "."
                    )

                # Build footer HTML with optional funding sentence
                footer_html = developed_by

                # Add funding organization as second sentence if configured
                funding = metadata.get("funding")
                if funding and isinstance(funding, dict) and funding.get("name"):
                    funder_name = funding["name"]
                    funder_url = funding.get("homepage", "")
                    # Use non-breaking spaces so the funder name stays on one line
                    funder_display = funder_name.replace(" ", "&nbsp;")
                    if funder_url:
                        funder_label = (
                            f'<a href="{funder_url}"><strong>{funder_display}</strong></a>'
                        )
                    else:
                        funder_label = f"<strong>{funder_display}</strong>"
                    footer_html += f" Supported by {funder_label}."

                config["website"]["page-footer"] = {"center": footer_html}

            else:
                # No authors: still emit a footer if funding is configured
                funding = metadata.get("funding")
                if funding and isinstance(funding, dict) and funding.get("name"):
                    funder_name = funding["name"]
                    funder_url = funding.get("homepage", "")
                    # Use non-breaking spaces so the funder name stays on one line
                    funder_display = funder_name.replace(" ", "&nbsp;")
                    if funder_url:
                        funder_label = (
                            f'<a href="{funder_url}"><strong>{funder_display}</strong></a>'
                        )
                    else:
                        funder_label = f"<strong>{funder_display}</strong>"
                    config["website"]["page-footer"] = {"center": f"Supported by {funder_label}."}

        # Append Great Docs attribution to footer if enabled
        if self._config.attribution:
            # Get the short commit hash of the great-docs source repo (only when
            # running from a development checkout, not a pip-installed copy)
            import subprocess

            gd_version_label = ""
            try:
                gd_source_dir = Path(__file__).resolve().parent.parent
                # Verify this is actually the great-docs repo, not the user's project
                remote_result = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=gd_source_dir,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                remote_url = remote_result.stdout.strip() if remote_result.returncode == 0 else ""
                if "great-docs" in remote_url:
                    result = subprocess.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        cwd=gd_source_dir,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        short_hash = result.stdout.strip()
                        gd_version_label = (
                            f' (<a href="https://github.com/posit-dev/great-docs/'
                            f'commit/{short_hash}">{short_hash}</a>)'
                        )
            except Exception:  # pragma: no cover
                pass  # pragma: no cover

            attribution = f"Site created with <strong>Great&nbsp;Docs</strong>{gd_version_label}."

            if "page-footer" in config["website"]:
                existing = config["website"]["page-footer"].get("center", "")
                if "Great&nbsp;Docs" not in existing:
                    if existing:
                        config["website"]["page-footer"]["center"] = f"{existing}<br>{attribution}"
                    else:
                        config["website"]["page-footer"]["center"] = attribution
            else:
                config["website"]["page-footer"] = {"center": attribution}

        # Add "Supported by Posit" badge if funding name contains "Posit" as a word
        funding = metadata.get("funding")
        if funding and isinstance(funding, dict) and funding.get("name"):
            if re.search(r"\bPosit\b", funding["name"], re.IGNORECASE):
                header_list = config["format"]["html"].setdefault("include-in-header", [])
                if isinstance(header_list, str):
                    header_list = [header_list]
                    config["format"]["html"]["include-in-header"] = header_list
                posit_badge_script = (
                    '<script src="https://cdn.jsdelivr.net/gh/posit-dev/'
                    'supported-by-posit/js/badge.min.js"></script>'
                )
                posit_entry = {"text": posit_badge_script}
                has_posit_badge = any("supported-by-posit" in str(item) for item in header_list)
                if not has_posit_badge:
                    header_list.append(posit_entry)

        # Add announcement banner if configured
        announcement = self._config.announcement
        if announcement:
            import html as html_mod

            ann_content = html_mod.escape(announcement["content"])
            ann_type = html_mod.escape(announcement.get("type", "info"))
            ann_dismissable = "true" if announcement.get("dismissable", True) else "false"
            ann_url = html_mod.escape(announcement.get("url") or "")
            ann_style = html_mod.escape(announcement.get("style") or "")

            ann_meta_tag = (
                f'<meta name="gd-announcement"'
                f' data-content="{ann_content}"'
                f' data-type="{ann_type}"'
                f' data-dismissable="{ann_dismissable}"'
                f' data-url="{ann_url}"'
                f' data-style="{ann_style}">'
            )

            # Add meta tag to header (replace any existing announcement meta)
            header_list = config["format"]["html"].setdefault("include-in-header", [])
            if isinstance(header_list, str):
                header_list = [header_list]
                config["format"]["html"]["include-in-header"] = header_list
            ann_meta_entry = {"text": ann_meta_tag}
            # Remove any stale announcement meta from a previous build
            header_list[:] = [h for h in header_list if "gd-announcement" not in str(h)]
            header_list.append(ann_meta_entry)

            # Add the banner script to after-body
            after_body = config["format"]["html"].setdefault("include-after-body", [])
            if isinstance(after_body, str):
                after_body = [after_body]
                config["format"]["html"]["include-after-body"] = after_body
            ann_script_entry = {"text": '<script src="announcement-banner.js"></script>'}
            if not any("announcement-banner" in str(item) for item in after_body):
                # Insert at position 0 so the banner script runs first
                after_body.insert(0, ann_script_entry)

            # Ensure the JS file is in resources
            resources_list = config["project"].setdefault("resources", [])
            if "announcement-banner.js" not in resources_list:
                resources_list.append("announcement-banner.js")

        # Add navbar gradient style if configured
        navbar_style = self._config.navbar_style
        if navbar_style:
            import html as html_mod_nb

            nb_preset = html_mod_nb.escape(str(navbar_style))
            nb_meta_tag = f'<meta name="gd-navbar-style" data-preset="{nb_preset}">'

            header_list = config["format"]["html"].setdefault("include-in-header", [])
            if isinstance(header_list, str):
                header_list = [header_list]
                config["format"]["html"]["include-in-header"] = header_list
            header_list[:] = [h for h in header_list if "gd-navbar-style" not in str(h)]
            header_list.append({"text": nb_meta_tag})

            after_body = config["format"]["html"].setdefault("include-after-body", [])
            if isinstance(after_body, str):
                after_body = [after_body]
                config["format"]["html"]["include-after-body"] = after_body
            nb_script_entry = {"text": '<script src="navbar-style.js"></script>'}
            if not any("navbar-style" in str(item) for item in after_body):
                after_body.append(nb_script_entry)

            resources_list = config["project"].setdefault("resources", [])
            if "navbar-style.js" not in resources_list:
                resources_list.append("navbar-style.js")

        # Add navbar solid color if configured (ignored when `navbar_style` is set)
        navbar_color = self._config.navbar_color
        if navbar_color:
            from great_docs.contrast import ideal_text_color, parse_color

            css_parts: list[str] = []

            for mode in ("light", "dark"):
                bg = navbar_color.get(mode)
                if not bg:
                    continue
                try:
                    r, g, b = parse_color(bg)
                except ValueError:
                    continue

                bg_hex = f"#{r:02x}{g:02x}{b:02x}"
                text_hex = ideal_text_color(bg)
                # Determine if elements on the navbar should look "light" or "dark"
                is_light_fg = text_hex.lower() in ("#ffffff", "#fff", "white")

                if is_light_fg:
                    # Light text elements on a dark-ish background
                    hover_bg = "rgba(255, 255, 255, 0.15)"
                    border_col = "rgba(255, 255, 255, 0.15)"
                    btn_bg = "rgba(255, 255, 255, 0.08)"
                    btn_border = "rgba(255, 255, 255, 0.15)"
                    btn_hover_bg = "rgba(255, 255, 255, 0.12)"
                    btn_hover_border = "rgba(255, 255, 255, 0.25)"
                    active_underline = "rgba(255, 255, 255, 0.75)"
                    toggler_stroke = "%23e0e0e0"
                else:
                    # Dark text elements on a light background
                    hover_bg = "rgba(0, 0, 0, 0.08)"
                    border_col = "rgba(0, 0, 0, 0.08)"
                    btn_bg = "rgba(0, 0, 0, 0.06)"
                    btn_border = "rgba(0, 0, 0, 0.15)"
                    btn_hover_bg = "rgba(0, 0, 0, 0.10)"
                    btn_hover_border = "rgba(0, 0, 0, 0.25)"
                    active_underline = "rgba(0, 0, 0, 0.45)"
                    toggler_stroke = "rgba(0,0,0,0.65)"

                if mode == "light":
                    selector = "body.quarto-light"
                else:
                    selector = ":is(html, body).quarto-dark"

                css_parts.append(f"""{selector} {{
    --gd-navbar-bg: {bg_hex};
    --gd-navbar-text: {text_hex};
}}
{selector} .navbar {{
    background: {bg_hex} !important;
    border-bottom: 1px solid {border_col};
}}
{selector} .navbar .navbar-title,
{selector} .navbar .nav-link {{
    color: {text_hex} !important;
}}
{selector} .navbar .nav-link:hover {{
    background-color: {hover_bg} !important;
    color: {text_hex} !important;
}}
{selector} .navbar .nav-item:has(#github-widget) .nav-link:hover {{
    background-color: transparent !important;
}}
{selector} .navbar .nav-link.active {{
    text-decoration-color: {active_underline} !important;
}}
{selector} .navbar .dark-mode-toggle,
{selector} #quarto-search .aa-DetachedSearchButton {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{selector} .navbar .dark-mode-toggle:hover,
{selector} #quarto-search .aa-DetachedSearchButton:hover {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{selector} .navbar .gh-widget-trigger {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{selector} .navbar .gh-widget-trigger:hover {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{selector} .navbar .quarto-navbar-tools button,
{selector} .navbar .quarto-navbar-tools .quarto-navigation-tool {{
    background: {btn_bg};
    border-color: {btn_border};
    color: {text_hex};
}}
{selector} .navbar .quarto-navbar-tools button:hover,
{selector} .navbar .quarto-navbar-tools .quarto-navigation-tool:hover {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{selector} .navbar .nav-item.compact .nav-link,
{selector} .navbar .gd-navbar-icon {{
    background: {btn_bg};
    border: 1px solid {btn_border};
    border-radius: 6px;
    color: {text_hex};
}}
{selector} .navbar .nav-item.compact .nav-link:hover,
{selector} .navbar .gd-navbar-icon:hover {{
    background: {btn_hover_bg};
    border-color: {btn_hover_border};
}}
{selector} .navbar .navbar-toggler-icon {{
    background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 30 30'%3e%3cpath stroke='{toggler_stroke}' stroke-linecap='round' stroke-miterlimit='10' stroke-width='2' d='M4 7h22M4 15h22M4 23h22'/%3e%3c/svg%3e") !important;
}}
{selector} .navbar .bi,
{selector} .navbar .aa-SubmitIcon {{
    color: {text_hex} !important;
}}
{selector} .navbar .version-badge {{
    color: {text_hex};
    opacity: 0.75;
    background-color: {btn_bg};
}}""")

            if css_parts:
                navbar_color_css = "\n".join(css_parts)
                style_tag = f"<style>\n/* Great Docs: navbar_color overrides */\n{navbar_color_css}\n</style>"
                after_body = config["format"]["html"].setdefault("include-after-body", [])
                if isinstance(after_body, str):
                    after_body = [after_body]
                    config["format"]["html"]["include-after-body"] = after_body
                after_body[:] = [h for h in after_body if "navbar_color overrides" not in str(h)]
                after_body.append({"text": style_tag})

        # Add content area gradient glow if configured
        content_style = self._config.content_style
        if content_style:
            import html as html_mod_cs

            cs_preset = html_mod_cs.escape(str(content_style["preset"]))
            cs_pages = html_mod_cs.escape(str(content_style["pages"]))
            cs_meta_tag = (
                f'<meta name="gd-content-style" data-preset="{cs_preset}" data-pages="{cs_pages}">'
            )

            header_list = config["format"]["html"].setdefault("include-in-header", [])
            if isinstance(header_list, str):
                header_list = [header_list]
                config["format"]["html"]["include-in-header"] = header_list
            header_list[:] = [h for h in header_list if "gd-content-style" not in str(h)]
            header_list.append({"text": cs_meta_tag})

            after_body = config["format"]["html"].setdefault("include-after-body", [])
            if isinstance(after_body, str):
                after_body = [after_body]
                config["format"]["html"]["include-after-body"] = after_body
            cs_script_entry = {"text": '<script src="content-style.js"></script>'}
            if not any("content-style" in str(item) for item in after_body):
                after_body.append(cs_script_entry)

            resources_list = config["project"].setdefault("resources", [])
            if "content-style.js" not in resources_list:
                resources_list.append("content-style.js")

        # Write package metadata JSON for post-render version badge injection.
        # The version and release date come from the latest GitHub Release so
        # the badge always reflects what has actually been published.
        meta_path = self.project_path / "_package_meta.json"

        if owner and repo:
            try:
                releases = self._fetch_github_releases(owner, repo, max_releases=1)
            except Exception:  # pragma: no cover
                releases = []

            if releases:
                latest = releases[0]
                tag = latest.get("tag_name", "")
                published = latest.get("published_at", "")

                # Strip leading 'v' for normalisation, then re-add for display
                version_str = tag.lstrip("v") if tag else ""

                if version_str:
                    meta: dict[str, str] = {"version": version_str}
                    if published:
                        meta["published_at"] = published
                    with open(meta_path, "w") as f:
                        json.dump(meta, f)
                    print(f"Wrote package metadata (version={version_str}) to {meta_path}")
                else:
                    # Tag with no version-like content — remove stale file
                    meta_path.unlink(missing_ok=True)  # pragma: no cover
            else:
                print(
                    "No GitHub releases found; skipping version badge metadata"
                )  # pragma: no cover
                # Remove stale metadata from a previous build
                meta_path.unlink(missing_ok=True)  # pragma: no cover
        else:
            print("No GitHub repository info available; skipping version badge metadata")
            meta_path.unlink(missing_ok=True)

        # Write back to file
        self._write_quarto_yml(quarto_yml, config)

        print(f"Updated {quarto_yml} with great-docs configuration")

    def _update_sidebar_from_sections(self) -> None:
        """
        Update sidebar navigation based on API reference sections.

        Builds a structured sidebar with sections and their contents, and excludes the index page
        from showing the sidebar.
        """
        quarto_yml = self.project_path / "_quarto.yml"

        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        # Get API reference sections if they exist
        if "api-reference" not in config or "sections" not in config["api-reference"]:
            return

        sections = config["api-reference"]["sections"]
        sidebar_contents = []

        # Build sidebar structure from sections
        for section in sections:
            section_entry = {"section": section["title"], "contents": []}

            # Add each item in the section
            for item in section.get("contents", []):
                # Handle both string and dict formats
                if isinstance(item, str):
                    section_entry["contents"].append(f"reference/{item}.qmd")
                elif isinstance(item, dict):
                    # Extract the name from dict format (e.g., {'name': 'Graph', 'members': []})
                    item_name = item.get("name", str(item))
                    section_entry["contents"].append(f"reference/{item_name}.qmd")
                else:
                    # Fallback for unexpected types
                    section_entry["contents"].append(f"reference/{item}.qmd")

            sidebar_contents.append(section_entry)

        # Update sidebar configuration
        if "website" not in config:
            config["website"] = {}

        # Build sidebar with API link at top (not subject to filtering)
        # followed by the sectioned contents
        full_contents = [
            {"text": "API", "href": "reference/index.qmd"},
        ] + sidebar_contents

        config["website"]["sidebar"] = [
            {
                "id": "reference",
                "contents": full_contents,
            }
        ]

        # Write back
        self._write_quarto_yml(quarto_yml, config)

    def _update_reference_index_frontmatter(self) -> None:
        """Ensure reference/index.qmd has proper frontmatter."""
        index_path = self.docs_dir / "reference" / "index.qmd"

        if not index_path.exists():
            return

        # Read the current content
        with open(index_path, "r") as f:
            content = f.read()

        # Check if frontmatter already exists; if so, inject page-navigation
        if content.startswith("---"):
            if "page-navigation:" not in content.split("---", 2)[1]:
                content = content.replace("---\n", "---\npage-navigation: false\n", 1)
                with open(index_path, "w") as f:
                    f.write(content)
            return

        # Add minimal frontmatter if none exists
        content = f"---\npage-navigation: false\n---\n\n{content}"

        # Write updated content
        with open(index_path, "w") as f:
            f.write(content)

    def _generate_llms_txt(self) -> None:
        """
        Generate an llms.txt file for LLM documentation indexing.

        Creates a structured markdown file that indexes the API reference pages, following the
        llms.txt standard format for LLM-readable documentation. The file is saved to the docs
        directory and will be included in the built site.

        The format follows the structure:

        - package title with description
        - API Reference section with links to each documented item
        """
        quarto_yml = self.project_path / "_quarto.yml"

        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        # Get API reference sections and package info
        if "api-reference" not in config:
            return

        api_ref_config = config["api-reference"]
        sections = api_ref_config.get("sections", [])
        package_name = api_ref_config.get("package")

        if not package_name or not sections:
            return

        # Get package metadata for description and site URL
        metadata = self._get_package_metadata()
        description = metadata.get("description", "")

        # Get the site URL and prefer the Documentation URL from pyproject.toml,
        # fall back to site-url from _quarto.yml
        urls = metadata.get("urls", {})
        site_url = urls.get("Documentation", "") or config.get("website", {}).get("site-url", "")

        # Clean up site URL and remove any trailing anchors or paths that aren't the base
        if site_url:
            # Remove trailing #readme or similar anchors
            if "#" in site_url:
                site_url = site_url.split("#")[0]
            # Ensure trailing slash
            if not site_url.endswith("/"):
                site_url += "/"

        # Build the llms.txt content
        lines = []

        # Header with package name
        lines.append(f"# {package_name}")
        lines.append("")

        # Description
        if description:
            lines.append(f"> {description}")
            lines.append("")

        # API Reference section
        lines.append("## Docs")
        lines.append("")
        lines.append("### API Reference")
        lines.append("")

        # Process each section
        for section in sections:
            section_title = section.get("title", "")
            section_desc = section.get("desc", "")

            # Add section header as a comment or sub-heading if there are multiple sections
            if len(sections) > 1 and section_title:
                lines.append(f"#### {section_title}")
                if section_desc:
                    lines.append(f"> {section_desc}")
                lines.append("")

            # Add each item in the section
            for item in section.get("contents", []):
                # Handle both string and dict formats
                if isinstance(item, str):
                    item_name = item
                    item_desc = ""
                elif isinstance(item, dict):
                    item_name = item.get("name", str(item))
                    item_desc = ""
                else:
                    continue

                # Get description from docstring if available
                if not item_desc:
                    item_desc = self._get_docstring_summary(package_name, item_name)

                # Build the URL
                if site_url:
                    url = f"{site_url}reference/{item_name}.html"
                else:
                    url = f"reference/{item_name}.html"

                # Format the line
                if item_desc:
                    lines.append(f"- [{item_name}]({url}): {item_desc}")
                else:
                    lines.append(f"- [{item_name}]({url})")

            lines.append("")

        # Write the llms.txt file
        llms_txt_path = self.project_path / "llms.txt"
        with open(llms_txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Created {llms_txt_path}")

    def _get_docstring_summary(self, package_name: str, item_name: str) -> str:
        """
        Get the first line of a docstring for an item.

        Parameters
        ----------
        package_name
            The name of the package containing the item.
        item_name
            The name of the class, function, or module to get the docstring for.

        Returns
        -------
        str
            The first line of the docstring, or empty string if not available.
        """
        try:
            import importlib

            # Normalize package name
            normalized_name = package_name.replace("-", "_")
            module = importlib.import_module(normalized_name)

            # Try to get the object
            obj = getattr(module, item_name, None)
            if obj is None:
                return ""

            # Get docstring
            docstring = getattr(obj, "__doc__", None)
            if not docstring:
                return ""

            # Extract first line/sentence
            first_line = docstring.strip().split("\n")[0].strip()

            # Clean up the line (remove trailing periods, normalize whitespace)
            first_line = first_line.rstrip(".")

            return first_line

        except Exception:  # pragma: no cover
            return ""  # pragma: no cover

    def _generate_llms_full_txt(self) -> None:
        """
        Generate an llms-full.txt file with comprehensive API documentation for LLMs.

        Creates a detailed markdown file containing full function/class signatures and
        docstrings, plus CLI help text if available. This provides comprehensive context
        for LLM-based tools to understand and work with the package's API.

        The format includes:
        - Package header with description
        - Full API documentation with signatures and docstrings organized by section
        - CLI documentation with --help output for all commands
        """

        quarto_yml = self.project_path / "_quarto.yml"

        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        # Get API reference sections and package info
        if "api-reference" not in config:
            return

        api_ref_config = config["api-reference"]
        sections = api_ref_config.get("sections", [])
        package_name = api_ref_config.get("package")

        if not package_name:
            return

        # Get package metadata
        metadata = self._get_package_metadata()
        description = metadata.get("description", "")

        # Import the package
        try:
            import importlib

            normalized_name = package_name.replace("-", "_")
            module = importlib.import_module(normalized_name)
        except ImportError as e:
            print(f"Could not import {package_name}: {e}")
            return

        sep_line = "-" * 70

        # Build the content
        lines = []
        lines.append(sep_line)
        lines.append(f"This is the API documentation for the {package_name} library.")
        lines.append(sep_line)
        lines.append("")

        # Process each section
        for section in sections:
            section_title = section.get("title", "")
            section_desc = section.get("desc", "")

            # Add section header
            if section_title:
                lines.append(f"\n## {section_title}\n")
                if section_desc:
                    lines.append(f"{section_desc}\n")
                lines.append("")

            # Process each item in the section
            for item in section.get("contents", []):
                # Handle both string and dict formats
                if isinstance(item, str):
                    item_name = item
                elif isinstance(item, dict):
                    item_name = item.get("name", str(item))
                else:
                    continue

                # Get the object's signature and docstring
                api_text = self._get_api_details(module, item_name)
                if api_text:
                    lines.append(api_text)
                    lines.append("")

        # Add CLI documentation if enabled
        cli_text = self._get_cli_help_text_for_llms()
        if cli_text:
            lines.append("")
            lines.append(sep_line)
            lines.append("This is the CLI documentation for the package.")
            lines.append(sep_line)
            lines.append("")
            lines.append(cli_text)

        # Add User Guide content if available
        user_guide_text = self._get_user_guide_text_for_llms()
        if user_guide_text:
            lines.append("")
            lines.append(sep_line)
            lines.append("This is the User Guide documentation for the package.")
            lines.append(sep_line)
            lines.append("")
            lines.append(user_guide_text)

        # Write the llms-full.txt file
        llms_full_path = self.project_path / "llms-full.txt"
        with open(llms_full_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Created {llms_full_path}")

    def _get_api_details(self, module, item_name: str) -> str:
        """
        Retrieve the signature and docstring for a function/class.

        Parameters
        ----------
        module
            The module from which to retrieve the function/class.
        item_name
            The name of the function or class (can be dotted for nested attributes).

        Returns
        -------
        str
            A string containing the name, signature, and docstring.
        """
        import inspect

        try:
            # Split the attribute path to handle nested attributes (e.g., "Class.method")
            parts = item_name.split(".")
            obj = module
            for part in parts:
                obj = getattr(obj, part)

            # Get the name of the object
            obj_name = getattr(obj, "__name__", item_name)

            # Get the function/class signature
            try:
                sig = inspect.signature(obj)
                sig_str = f"{obj_name}{sig}"
            except (ValueError, TypeError):
                # Some objects don't have signatures (e.g., some built-ins)
                sig_str = obj_name

            # Get the docstring
            doc = getattr(obj, "__doc__", None) or ""

            # Clean up the docstring - remove excessive indentation
            if doc:
                doc = inspect.cleandoc(doc)

            # Combine the signature and docstring
            return f"{sig_str}\n\n{doc}" if doc else sig_str

        except AttributeError:  # pragma: no cover
            return ""  # pragma: no cover
        except Exception:  # pragma: no cover
            return ""  # pragma: no cover

    def _generate_skill_md(self) -> None:
        """
        Generate a SKILL.md file conforming to the Agent Skills specification.

        Creates a skill file that gives AI coding agents structured context about the
        documented package — its capabilities, API decision table, gotchas, and links
        to comprehensive documentation.

        If the user has provided a hand-written SKILL.md via ``skill.file`` in
        ``great-docs.yml``, that file is copied verbatim instead of generating one.

        The generated file is written to ``<docs>/skill.md`` and optionally copied to
        ``<docs>/.well-known/skills/default/SKILL.md`` for auto-discovery.
        """
        import shutil

        if not self._config.skill_enabled:
            return

        package_root = self._find_package_root()

        # If user provided a hand-written SKILL.md via config, copy it
        if self._config.skill_file:
            src = package_root / self._config.skill_file
            if src.exists():
                dest = self.project_path / "skill.md"
                shutil.copy2(src, dest)
                print(f"Copied user SKILL.md from {src}")
                self._place_well_known_skill(dest)
                self._generate_skills_page(dest, skill_dir=src.parent)
                return
            else:
                print(f"Warning: skill.file '{src}' not found, falling back to discovery")

        # Check for a curated skill in skills/<package-name>/SKILL.md
        # This is the standard Agent Skills repo layout for distribution
        package_name_for_skill = self._detect_package_name() or ""
        install_name = package_name_for_skill.replace("_", "-") if package_name_for_skill else ""

        for candidate_name in [install_name, package_name_for_skill]:
            if not candidate_name:
                continue
            skills_path = package_root / "skills" / candidate_name / "SKILL.md"
            if skills_path.exists():
                dest = self.project_path / "skill.md"
                shutil.copy2(skills_path, dest)
                print(f"Using curated skill from {skills_path}")
                self._place_well_known_skill(dest)
                self._generate_skills_page(dest, skill_dir=skills_path.parent)
                return

        quarto_yml = self.project_path / "_quarto.yml"
        if not quarto_yml.exists():
            return

        with open(quarto_yml, "r") as f:
            config = read_yaml(f) or {}

        # Get API reference sections and package info
        api_ref_config = config.get("api-reference", {})
        sections = api_ref_config.get("sections", [])
        package_name = api_ref_config.get("package", "")

        # Get package metadata
        metadata = self._get_package_metadata()
        description = metadata.get("description", "")
        license_text = metadata.get("license", "")
        requires_python = metadata.get("requires_python", "")

        # Get site URL
        urls = metadata.get("urls", {})
        site_url = urls.get("Documentation", "") or config.get("website", {}).get("site-url", "")
        if site_url and "#" in site_url:
            site_url = site_url.split("#")[0]
        if site_url and not site_url.endswith("/"):
            site_url += "/"

        repo_url = urls.get("Repository", "") or urls.get("Source", "")

        # Derive install name from package name (PyPI name uses hyphens)
        install_name = package_name.replace("_", "-") if package_name else ""

        # Build skill name: lowercase, hyphens only, max 64 chars
        skill_name = install_name.lower()[:64] if install_name else "package"

        # Build frontmatter
        lines = ["---"]
        lines.append(f"name: {skill_name}")

        # Build description (max 1024 chars)
        desc_parts = []
        if description:
            desc_parts.append(description.rstrip(".") + ".")
        if package_name:
            desc_parts.append(f"Use when writing Python code that uses the {package_name} package.")
        skill_desc = " ".join(desc_parts)[:1024] if desc_parts else f"Use the {skill_name} package."
        lines.append("description: >")
        lines.append(f"  {skill_desc}")

        if license_text:
            lines.append(f"license: {license_text}")
        if requires_python:
            lines.append(f"compatibility: Requires Python {requires_python}.")
        lines.append("---")
        lines.append("")

        # Body: Package header
        display_name = self._config.display_name or package_name or skill_name
        lines.append(f"# {display_name}")
        lines.append("")
        if description:
            lines.append(description)
            lines.append("")

        # Installation section
        if install_name:
            lines.append("## Installation")
            lines.append("")
            lines.append("```bash")
            lines.append(f"pip install {install_name}")
            lines.append("```")
            lines.append("")

        # API decision table
        if sections:
            # Collect manual decision table rows from config
            manual_rows = self._config.skill_decision_table

            if manual_rows:
                lines.append("## When to use what")
                lines.append("")
                lines.append("| Need | Use |")
                lines.append("|------|-----|")
                for row in manual_rows:
                    need = row.get("need", "")
                    use = row.get("use", "")
                    lines.append(f"| {need} | `{use}` |")
                lines.append("")

            # API capabilities by section
            lines.append("## API overview")
            lines.append("")

            for section in sections:
                section_title = section.get("title", "")
                section_desc = section.get("desc", "")

                if section_title:
                    lines.append(f"### {section_title}")
                    if section_desc:
                        lines.append("")
                        lines.append(section_desc)
                    lines.append("")

                for item in section.get("contents", []):
                    if isinstance(item, str):
                        item_name = item
                    elif isinstance(item, dict):
                        item_name = item.get("name", str(item))
                    else:
                        continue

                    item_desc = self._get_docstring_summary(package_name, item_name)
                    if item_desc:
                        lines.append(f"- `{item_name}`: {item_desc}")
                    else:
                        lines.append(f"- `{item_name}`")

                lines.append("")

        # Gotchas section
        gotchas = self._config.skill_gotchas
        if gotchas:
            lines.append("## Gotchas")
            lines.append("")
            for i, gotcha in enumerate(gotchas, 1):
                lines.append(f"{i}. {gotcha}")
            lines.append("")

        # Best practices section
        best_practices = self._config.skill_best_practices
        if best_practices:
            lines.append("## Best practices")
            lines.append("")
            for practice in best_practices:
                lines.append(f"- {practice}")
            lines.append("")

        # Append extra body content if provided
        if self._config.skill_extra_body:
            extra_path = package_root / self._config.skill_extra_body
            if extra_path.exists():
                extra_content = extra_path.read_text(encoding="utf-8")
                lines.append(extra_content)
                lines.append("")

        # Links section
        lines.append("## Resources")
        lines.append("")
        if site_url:
            lines.append(f"- [Full documentation]({site_url})")
        lines.append("- [llms.txt](llms.txt) — Indexed API reference for LLMs")
        lines.append("- [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs")
        if repo_url:
            lines.append(f"- [Source code]({repo_url})")
        lines.append("")

        # Write the skill.md file
        skill_path = self.project_path / "skill.md"
        with open(skill_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"Created {skill_path}")

        # Place in .well-known if enabled
        self._place_well_known_skill(skill_path)

        # Generate the rendered skills.qmd page
        self._generate_skills_page(skill_path)

    def _generate_skills_page(self, skill_path: "Path", *, skill_dir: "Path | None" = None) -> None:
        """
        Generate a ``skills.qmd`` page that renders the raw SKILL.md content in a
        styled, human-readable format.

        The page displays the skill's YAML frontmatter as a highlighted block and
        the Markdown body with color-coded headings and monospaced font — a halfway
        point between raw Markdown and fully rendered HTML.

        When *skill_dir* points to a curated skill directory that contains companion
        subdirectories (``references/``, ``scripts/``, ``assets/``), a directory
        tree is rendered before the SKILL.md and each ``.md`` / ``.sh`` file is
        displayed in its own text area with anchor links.

        Parameters
        ----------
        skill_path
            Path to the skill.md file to render.
        skill_dir
            Optional path to the curated skill directory containing SKILL.md and
            its companion subdirectories.
        """
        import re

        if not skill_path.exists():
            return

        raw_content = skill_path.read_text(encoding="utf-8")

        # Split frontmatter from body
        frontmatter = ""
        body = raw_content
        if raw_content.startswith("---"):
            fm_match = re.match(r"^---\n(.*?\n)---\n?(.*)", raw_content, re.DOTALL)
            if fm_match:
                frontmatter = fm_match.group(1)
                body = fm_match.group(2).lstrip("\n")

        # Build the skills.qmd page
        lines = []
        lines.append("---")
        lines.append("title: Skills")
        lines.append("toc: false")
        lines.append("sidebar: false")
        lines.append("page-layout: full")
        lines.append('body-classes: "gd-skills-page"')
        lines.append("---")
        lines.append("")

        # Install instructions
        # Detect GitHub repo URL from metadata
        metadata = self._get_package_metadata()
        urls = metadata.get("urls", {})
        repo_url = urls.get("Repository", "") or urls.get("Source", "")
        github_owner_repo = ""
        if repo_url:
            gh_match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", repo_url)
            if gh_match:
                github_owner_repo = gh_match.group(1)

        # Detect site URL
        quarto_yml = self.project_path / "_quarto.yml"
        site_url = ""
        if quarto_yml.exists():
            with open(quarto_yml, "r") as f:
                qconfig = read_yaml(f) or {}
            site_url = urls.get("Documentation", "") or qconfig.get("website", {}).get(
                "site-url", ""
            )
            if site_url and not site_url.endswith("/"):
                site_url += "/"

        lines.append("```{=html}")
        lines.append('<div class="gd-skills-install">')
        lines.append(
            '  <button class="gd-skills-install-toggle" '
            'aria-expanded="false" aria-controls="gd-skills-install-body">'
        )
        lines.append(
            '    <span class="gd-skills-install-icon">&#9654;</span>    Install this skill'
        )
        lines.append("  </button>")
        lines.append('  <div class="gd-skills-install-body" id="gd-skills-install-body">')
        lines.append('    <div class="gd-skills-install-inner">')
        lines.append('      <div class="gd-skills-install-pad">')
        lines.append("```")
        lines.append("")

        # ── npx (universal installer) ──
        lines.append("**Any agent** --- install with [npx](https://github.com/vercel-labs/skills):")
        lines.append("")
        if site_url:
            lines.append("```bash")
            lines.append(f"npx skills add {site_url}")
            lines.append("```")
        elif github_owner_repo:
            lines.append("```bash")
            lines.append(f"npx skills add {github_owner_repo}")
            lines.append("```")
        else:
            lines.append("```bash")
            lines.append("npx skills add <site-url>")
            lines.append("```")
        lines.append("")
        lines.append(
            "Works with Claude Code, GitHub Copilot, Cursor, Gemini CLI, Codex, "
            "and [30+ other agents](https://github.com/vercel-labs/skills)."
        )
        lines.append("")

        # ── Codex / OpenCode (prompt-based fetch) ──
        skill_file_url = f"{site_url}skill.md" if site_url else ""
        lines.append("**Codex / OpenCode** --- tell the agent:")
        lines.append("")
        if skill_file_url:
            lines.append(
                f"> Fetch the skill file at `{skill_file_url}` and follow the instructions."
            )
        elif github_owner_repo:
            lines.append(
                f"> Fetch the skill file from "
                f"`https://github.com/{github_owner_repo}` "
                "and follow the instructions."
            )
        else:
            lines.append(
                "> Fetch the skill file at `<site-url>/skill.md` and follow the instructions."
            )
        lines.append("")

        # ── Manual (curl + raw links) ──
        lines.append("**Manual** --- download the skill file:")
        lines.append("")
        if skill_file_url:
            lines.append("```bash")
            lines.append(f"curl -O {skill_file_url}")
            lines.append("```")
        else:
            lines.append("```bash")
            lines.append("curl -O <site-url>/skill.md")
            lines.append("```")
        lines.append("")
        # Use raw HTML to prevent Quarto rewriting skill.md → skill.html.
        # The post-render script also fixes this link back to skill.md.
        lines.append("```{=html}")
        lines.append(
            '<p>Or browse the <a href="skill.md" class="gd-raw-link"><code>SKILL.md</code></a> file.</p>'
        )
        lines.append("```")
        lines.append("")

        lines.append("```{=html}")
        lines.append("      </div>")
        lines.append("    </div>")
        lines.append("  </div>")
        lines.append("</div>")
        lines.append("<script>")
        lines.append("(function() {")
        lines.append("  var btn = document.querySelector('.gd-skills-install-toggle');")
        lines.append("  var body = document.getElementById('gd-skills-install-body');")
        lines.append("  if (!btn || !body) return;")
        lines.append("  btn.addEventListener('click', function() {")
        lines.append("    var open = body.classList.toggle('gd-skills-install-open');")
        lines.append("    btn.setAttribute('aria-expanded', open);")
        lines.append("  });")
        lines.append("})();")
        lines.append("</script>")
        lines.append("```")
        lines.append("")

        # ── Discover companion files in the skill directory ──
        companion_files: list[tuple[str, str, str]] = []  # (subdir/name, ext, content)
        _ALLOWED_SUBDIRS = ("references", "scripts", "assets")
        _RENDERABLE_EXTS = {".md", ".sh", ".yaml", ".yml", ".py"}

        if skill_dir and skill_dir.is_dir():
            for subdir_name in _ALLOWED_SUBDIRS:
                subdir = skill_dir / subdir_name
                if not subdir.is_dir():
                    continue
                for file_path in sorted(subdir.iterdir()):
                    if file_path.is_file() and file_path.suffix in _RENDERABLE_EXTS:
                        rel = f"{subdir_name}/{file_path.name}"
                        content = file_path.read_text(encoding="utf-8")
                        companion_files.append((rel, file_path.suffix, content))

        # ── Directory tree (only when companion files exist) ──
        if companion_files:
            # Build the skill directory name from its parent dir name
            dir_label = skill_dir.name if skill_dir else "skill"
            tree_lines = [f"{dir_label}/"]
            # SKILL.md first
            tree_lines.append("\u251c\u2500\u2500 SKILL.md")
            # Group by subdirectory
            seen_subdirs: dict[str, list[str]] = {}
            for rel, _ext, _content in companion_files:
                parts = rel.split("/", 1)
                seen_subdirs.setdefault(parts[0], []).append(parts[1])
            subdir_items = list(seen_subdirs.items())
            for i, (sdir, files) in enumerate(subdir_items):
                is_last_dir = i == len(subdir_items) - 1
                branch = "\u2514\u2500\u2500" if is_last_dir else "\u251c\u2500\u2500"
                tree_lines.append(f"{branch} {sdir}/")
                for j, fname in enumerate(files):
                    is_last_file = j == len(files) - 1
                    prefix = "    " if is_last_dir else "\u2502   "
                    connector = "\u2514\u2500\u2500" if is_last_file else "\u251c\u2500\u2500"
                    # Create anchor id from the relative path
                    anchor = f"{sdir}/{fname}".replace("/", "-").replace(".", "-")
                    tree_lines.append(f'{prefix}{connector} <a href="#{anchor}">{fname}</a>')

            lines.append("```{=html}")
            lines.append('<h3 class="gd-skills-section-heading">SKILL LAYOUT</h3>')
            lines.append('<pre class="gd-skills-tree">')
            lines.append("\n".join(tree_lines))
            lines.append("</pre>")
            lines.append("```")
            lines.append("")

        # ── Render the full skill.md as a raw pre block (terminal style) ──
        full_skill = raw_content
        lines.append("```{=html}")
        lines.append('<h3 class="gd-skills-file-heading">SKILL.md</h3>')
        lines.append('<pre class="gd-skills-raw">')
        lines.append("```")
        lines.append("")
        lines.append("````markdown")
        lines.append(full_skill.rstrip("\n"))
        lines.append("````")
        lines.append("")
        lines.append("```{=html}")
        lines.append("</pre>")
        lines.append("```")
        lines.append("")

        # ── Render each companion file in its own pre block ──
        for rel, ext, content in companion_files:
            anchor = rel.replace("/", "-").replace(".", "-")
            # Choose syntax hint for the fenced block
            lang_map = {
                ".md": "markdown",
                ".sh": "bash",
                ".yaml": "yaml",
                ".yml": "yaml",
                ".py": "python",
            }
            lang = lang_map.get(ext, "")

            lines.append("```{=html}")
            lines.append(f'<h3 id="{anchor}" class="gd-skills-file-heading">{rel}</h3>')
            lines.append('<pre class="gd-skills-raw">')
            lines.append("```")
            lines.append("")
            lines.append(f"````{lang}")
            lines.append(content.rstrip("\n"))
            lines.append("````")
            lines.append("")
            lines.append("```{=html}")
            lines.append("</pre>")
            lines.append("```")
            lines.append("")

        skills_page = self.project_path / "skills.qmd"
        with open(skills_page, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _place_well_known_skill(self, skill_path: "Path") -> None:
        """
        Copy the SKILL.md to .well-known/skills/default/ for auto-discovery.

        Parameters
        ----------
        skill_path
            Path to the skill.md file to copy.
        """
        import shutil

        if not self._config.skill_well_known:
            return

        well_known_dir = self.project_path / ".well-known" / "skills" / "default"
        well_known_dir.mkdir(parents=True, exist_ok=True)

        dest = well_known_dir / "SKILL.md"
        shutil.copy2(skill_path, dest)

    def _get_cli_help_text_for_llms(self) -> str:
        """
        Get CLI help text formatted for llms-full.txt.

        Returns
        -------
        str
            Formatted CLI help text with all commands and subcommands.
        """
        metadata = self._get_package_metadata()

        if not metadata.get("cli_enabled", False):
            return ""

        package_name = self._detect_package_name()
        if not package_name:
            return ""

        cli_info = self._discover_click_cli(package_name)
        if not cli_info:
            return ""

        lines = []
        entry_point = cli_info.get("entry_point_name", package_name)

        # Main CLI help
        lines.append(f"## CLI: {entry_point}")
        lines.append("")
        lines.append("```")
        lines.append(cli_info.get("help_text", ""))
        lines.append("```")
        lines.append("")

        # Process subcommands recursively
        def add_subcommand_help(cmd_info: dict, depth: int = 0):
            nonlocal lines
            for subcmd in cmd_info.get("commands", []):
                if subcmd.get("hidden"):
                    continue

                full_path = subcmd.get("full_path", subcmd.get("name", ""))
                lines.append(f"### {full_path}")
                lines.append("")
                lines.append("```")
                lines.append(subcmd.get("help_text", ""))
                lines.append("```")
                lines.append("")

                # Recurse for nested subcommands
                if subcmd.get("commands"):
                    add_subcommand_help(subcmd, depth + 1)

        add_subcommand_help(cli_info)

        return "\n".join(lines)

    def _get_user_guide_text_for_llms(self) -> str:
        """
        Get User Guide content formatted for llms-full.txt.

        Reads all user guide .qmd files in order and extracts their content,
        stripping YAML frontmatter but preserving the document structure.

        Returns
        -------
        str
            Formatted User Guide content with all pages in order.
        """
        user_guide_info = self._discover_user_guide()
        if not user_guide_info:
            return ""

        lines = []
        files = user_guide_info.get("files", [])

        if not files:
            return ""

        current_section = None

        for file_info in files:
            file_path = file_info.get("path")
            title = file_info.get("title", "")
            section = file_info.get("section")

            if not file_path or not file_path.exists():
                continue

            # Add section header if this is a new section
            if section and section != current_section:
                lines.append(f"\n## {section}\n")
                current_section = section

            # Read the file content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:  # pragma: no cover
                continue  # pragma: no cover

            # Strip YAML frontmatter
            content = self._strip_frontmatter(content)

            # Add the page title as a header if not already starting with one
            content_stripped = content.strip()
            if not content_stripped.startswith("#"):
                lines.append(f"### {title}\n")

            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    def _strip_frontmatter(self, content: str) -> str:
        """
        Remove YAML frontmatter from a document.

        Parameters
        ----------
        content
            The document content.

        Returns
        -------
        str
            The content with frontmatter removed.
        """
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].lstrip()
        return content

    def uninstall(self) -> None:
        """
        Remove great-docs configuration and build directory from the project.

        This method deletes the great-docs.yml configuration file and the great-docs/
        build directory (if it exists).

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

        # Remove the great-docs.yml configuration file
        config_path = self.project_root / "great-docs.yml"
        if config_path.exists():
            config_path.unlink()
            print(f"Removed {config_path.relative_to(self.project_root)}")

        # Remove the great-docs/ build directory if it exists
        if self.project_path.exists():
            shutil.rmtree(self.project_path)
            print(f"Removed {self.project_path.relative_to(self.project_root)}/ directory")

        print("✅ Great-docs uninstalled successfully!")

    def build(self, watch: bool = False, refresh: bool = True) -> None:
        """
        Build the documentation site.

        Generates API reference pages followed by `quarto render`. By default, re-discovers package exports
        and updates the API reference configuration before building.

        Parameters
        ----------
        watch
            If `True`, watch for changes and rebuild automatically.
        refresh
            If `True` (default), re-discover package exports and update API reference config before
            building. Set to False for faster rebuilds when your package API hasn't changed.

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
        config_path = self.project_root / "great-docs.yml"
        if not config_path.exists():
            raise FileNotFoundError(
                "great-docs.yml not found. Run 'great-docs init' first to "
                "generate a configuration file."
            )

        import subprocess
        import sys
        import threading

        def run_streaming(cmd, env=None, prefix="   "):  # pragma: no cover
            """Run a subprocess and stream its output in real time.

            Returns a result-like object with returncode and captured stderr.
            """
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,  # Line-buffered
            )

            stderr_lines = []

            def read_stderr():
                for line in process.stderr:
                    stderr_lines.append(line)
                    stripped = line.rstrip()
                    if stripped:
                        print(f"{prefix}{stripped}", flush=True)

            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()

            # Stream stdout line by line
            for line in process.stdout:
                stripped = line.rstrip()
                if stripped:
                    print(f"{prefix}{stripped}", flush=True)

            process.wait()
            stderr_thread.join(timeout=5)

            class Result:
                pass

            r = Result()
            r.returncode = process.returncode
            r.stderr = "".join(stderr_lines)
            r.stdout = ""  # Already streamed
            return r

        print("Building documentation with great-docs...")

        # Prepare the build directory with all assets and configuration
        self._prepare_build_directory()

        # Change to build directory
        original_dir = os.getcwd()
        try:
            os.chdir(self.project_path)

            # Step 0.5: Refresh API reference config if requested
            if refresh and self._has_api_reference:
                print("\n🔄 Refreshing API reference configuration...")
                self._refresh_api_reference_config()

            # Step 0.6: Generate llms.txt and llms-full.txt files
            print("\n📝 Generating llms.txt and llms-full.txt...")
            self._generate_llms_txt()
            self._generate_llms_full_txt()

            # Step 0.65: Generate SKILL.md (Agent Skills specification)
            if self._config.skill_enabled:
                print("\n🤖 Generating SKILL.md...")
                self._generate_skill_md()

            # Step 0.7: Generate source links JSON
            print("\n🔗 Generating source links...")
            package_name = self._detect_package_name()
            if package_name:
                self._generate_source_links_json(package_name)

            # Step 0.75: Generate changelog from GitHub Releases (if enabled)
            if self._config.changelog_enabled:
                owner, repo, _base_url = self._get_github_repo_info()
                if owner and repo:
                    print("\n📋 Generating changelog from GitHub Releases...")
                    try:
                        result_file = self._generate_changelog_page()
                        if result_file:
                            self._add_changelog_to_navbar()
                            print("✅ Changelog generated")
                        else:
                            print("   No releases found; skipping changelog")
                    except Exception as e:
                        print(f"   ⚠️  Error generating changelog: {e}")

            # Step 0.8: Generate CLI documentation if enabled
            metadata = self._get_package_metadata()
            if metadata.get("cli_enabled", False):
                print("\n🖥️  Generating CLI reference...")
                try:
                    cli_info = self._discover_click_cli(package_name)
                    if cli_info:
                        cli_files = self._generate_cli_reference_pages(cli_info)
                        if cli_files:
                            self._update_sidebar_with_cli(cli_files)
                            n_pages = self._count_cli_sidebar_items(cli_files)
                            print(f"✅ Generated {n_pages} CLI reference page(s)")
                    else:
                        print(
                            "   No Click CLI found or CLI documentation disabled"
                        )  # pragma: no cover
                except Exception as e:
                    print(f"   ⚠️  Error generating CLI documentation: {e}")
                    import traceback

                    traceback.print_exc()

            # Step 0.9: Process User Guide if present
            try:
                self._process_user_guide()
            except Exception as e:
                print(f"   ⚠️  Error processing User Guide: {e}")
                import traceback

                traceback.print_exc()

            # Step 0.85: Process custom sections (examples, tutorials, etc.)
            if self._config.sections:
                print("\n📂 Processing custom sections...")
                try:
                    n_sections = self._process_sections()
                    if n_sections:
                        print(f"✅ {n_sections} section(s) processed")
                except Exception as e:
                    print(f"   ⚠️  Error processing sections: {e}")
                    import traceback

                    traceback.print_exc()

            # Step 0.95: Copy assets directory if present
            try:
                assets_copied = self._copy_assets()
                # Update Quarto config to include assets in resources if they were copied
                if assets_copied:
                    self._update_quarto_config()
            except Exception as e:
                print(f"   ⚠️  Error copying assets: {e}")
                import traceback

                traceback.print_exc()

            # Step 1: Build API reference using internal renderer (uses the internal renderer)
            if self._has_api_reference:
                print("\n📚 Step 1: Generating API reference...")

                # Set up PYTHONPATH so griffe can find the target package
                build_env = self._get_quarto_env()
                extra_paths = build_env.get("PYTHONPATH", "").split(os.pathsep)
                for p in extra_paths:
                    if p and p not in sys.path:
                        sys.path.insert(0, p)  # pragma: no cover

                try:
                    from great_docs._qrenderer.introspection import Builder

                    quarto_yml = self.project_path / "_quarto.yml"
                    builder = Builder.from_quarto_config(str(quarto_yml))
                    builder.build()
                    print("\n✅ API reference generated")
                except Exception as e:
                    # If dynamic mode was used, retry with static mode
                    dynamic = self._config.dynamic
                    if dynamic:
                        print("\n⚠️  API reference build failed with dynamic introspection.")
                        print("   Retrying with static analysis (dynamic: false)...\n")

                        with open(quarto_yml, "r") as f:
                            qconfig = read_yaml(f) or {}

                        if "api-reference" in qconfig:
                            qconfig["api-reference"]["dynamic"] = False
                            with open(quarto_yml, "w") as f:
                                write_yaml(qconfig, f)

                        try:
                            builder = Builder.from_quarto_config(str(quarto_yml))
                            builder.build()
                            print("\n✅ API reference generated (using static analysis)")
                            print(
                                "   Tip: Add 'dynamic: false' to great-docs.yml "
                                "to skip the retry next time"
                            )
                        except Exception as e2:
                            print("\n❌ API reference build failed (static mode):")
                            print(str(e2))
                            sys.exit(1)
                    else:
                        print("\n❌ API reference build failed:")
                        print(str(e))
                        import traceback

                        traceback.print_exc()
                        sys.exit(1)
            else:
                print("\n📚 Step 1: Skipping API reference (disabled)")

            # Get environment with QUARTO_PYTHON set for proper Python detection
            quarto_env = self._get_quarto_env()

            # Step 2: Run quarto render or preview
            if watch:
                print("\n🔄 Step 2: Starting Quarto in watch mode...")
                print("Press Ctrl+C to stop watching")
                subprocess.run(["quarto", "preview", "--no-browser"], env=quarto_env)
            else:
                print("\n🔨 Step 2: Building site with Quarto...")

                result = run_streaming(
                    ["quarto", "render"],
                    env=quarto_env,
                )

                if result.returncode != 0:
                    print("\n❌ quarto render failed:")
                    print(result.stderr)
                    sys.exit(1)
                else:
                    print("\n✅ Site built successfully")  # pragma: no cover
                    site_path = self.project_path / "_site" / "index.html"
                    if site_path.exists():
                        print(f"\n🎉 Your site is ready! Open: {site_path}")
                    else:
                        print(f"\n🎉 Your site is ready in: {self.project_path / '_site'}")

        finally:
            os.chdir(original_dir)

    def preview(self, port: int = 3000) -> None:
        """
        Preview the documentation site locally.

        Starts a local HTTP server and opens the built site in the default
        browser.  If the site hasn't been built yet, it will be built first.
        Use ``great-docs build`` to rebuild the site if you've made changes.

        Parameters
        ----------
        port
            The port number for the local HTTP server (default ``3000``).

        Examples
        --------
        Preview the documentation:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        docs.preview()
        ```
        """
        import functools
        import http.server
        import socketserver
        import sys
        import threading
        import webbrowser

        print("Previewing documentation...")

        # Check if site has been built
        site_path = self.project_path / "_site"
        index_html = site_path / "index.html"

        if not index_html.exists():
            print("Site not found, building first...")
            self.build()

        if not index_html.exists():
            print("❌ Could not find built site")
            sys.exit(1)

        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=str(site_path),
        )
        # Allow quick restart after Ctrl-C
        socketserver.TCPServer.allow_reuse_address = True

        try:
            httpd = socketserver.TCPServer(("", port), handler)
        except OSError:
            print(f"❌ Port {port} is already in use. Try a different port.")
            sys.exit(1)

        url = f"http://localhost:{port}/"
        print(f"\n🌐 Serving site at {url}")
        print("   Press Ctrl+C to stop\n")

        # Open browser after a short delay so the server is ready
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()

    def check_links(
        self,
        include_source: bool = True,
        include_docs: bool = True,
        timeout: float = 10.0,
        ignore_patterns: list[str] | None = None,
        verbose: bool = False,
    ) -> dict:
        """
        Check all links in source code and documentation for broken links.

        This method scans Python source files and documentation files (`.qmd`, `.md`)
        for URLs and checks their HTTP status. It reports broken links (404s) and
        warns about redirects.

        The following content is automatically excluded from link checking:

        - **Python comments**: URLs in lines starting with `#`
        - **Code blocks**: URLs inside fenced code blocks (````` ... `````)
        - **Inline code**: URLs inside backticks (`` `...` ``)
        - **Marked URLs**: URLs followed by `{.gd-no-link}` in `.qmd`/`.md` files

        For documentation, the checker scans the source `user_guide/` directory
        rather than the generated `docs/` directory to avoid checking transient files.

        In `.qmd` files, you can exclude specific URLs from checking by adding
        `{.gd-no-link}` immediately after the URL:

            Visit http://example.com{.gd-no-link} for an example.
            Also works with inline code: `http://example.com`{.gd-no-link}

        Parameters
        ----------
        include_source
            If `True`, scan Python source files in the package directory for URLs.
            Default is `True`.
        include_docs
            If `True`, scan documentation files (`.qmd`, `.md`) for URLs.
            Default is `True`.
        timeout
            Timeout in seconds for each HTTP request. Default is `10.0`.
        ignore_patterns
            List of URL patterns (strings or regex) to ignore. URLs matching any
            pattern will be skipped. Default is `None`.
        verbose
            If `True`, print detailed progress information. Default is `False`.

        Returns
        -------
        dict
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
        import requests

        # URL regex pattern - matches http and https URLs
        url_pattern = re.compile(
            r'https?://[^\s<>"\')\]}`\\]+',
            re.IGNORECASE,
        )

        # Pattern to detect URLs marked with {.gd-no-link} in .qmd files
        # This allows marking example/fake links for exclusion: http://example.com{.gd-no-link}
        # Also handles URLs in inline code: `http://example.com`{.gd-no-link}
        gd_no_link_pattern = re.compile(
            r'`?(https?://[^\s<>"\')\]}`\\{]+)`?\{\.gd-no-link\}',
            re.IGNORECASE,
        )

        # Compile ignore patterns
        ignore_regexes = []
        if ignore_patterns:
            for pattern in ignore_patterns:
                try:
                    ignore_regexes.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    # Treat as literal string if not valid regex
                    ignore_regexes.append(re.compile(re.escape(pattern), re.IGNORECASE))

        # Collect all files to scan
        files_to_scan: list[Path] = []

        if include_source:
            # Find package directory
            package_name = self._detect_package_name()
            if package_name:
                package_dir = self.project_root / package_name.replace("-", "_")
                if package_dir.exists():
                    files_to_scan.extend(package_dir.rglob("*.py"))

        if include_docs:
            # Scan documentation files
            # Priority: if user_guide/ exists, scan that (it's the source)
            # Otherwise, scan the docs directory directly

            user_guide_dir = self.project_root / "user_guide"
            if user_guide_dir.exists():
                # Scan user_guide source directory instead of generated docs/
                files_to_scan.extend(user_guide_dir.rglob("*.qmd"))
                files_to_scan.extend(user_guide_dir.rglob("*.md"))
            elif self.project_path.exists():  # pragma: no cover
                # No user_guide/, scan docs directory directly
                files_to_scan.extend(self.project_path.rglob("*.qmd"))  # pragma: no cover
                files_to_scan.extend(self.project_path.rglob("*.md"))  # pragma: no cover

            # Also check README in project root
            readme = self.project_root / "README.md"
            if readme.exists():
                files_to_scan.append(readme)

        # Extract URLs from all files
        url_to_files: dict[str, list[str]] = {}
        by_file: dict[str, list[str]] = {}

        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                # For .qmd and .md files, find URLs marked with {.gd-no-link} and exclude them
                # Also strip code blocks to avoid checking example URLs
                excluded_urls: set[str] = set()
                if file_path.suffix in (".qmd", ".md"):
                    for match in gd_no_link_pattern.finditer(content):
                        excluded_urls.add(match.group(1))

                    # Remove fenced code blocks (``` ... ```) before URL extraction
                    # This prevents example URLs in code blocks from being checked
                    content = re.sub(r"```[^`]*```", "", content, flags=re.DOTALL)

                    # Also remove inline code (`...`) to avoid example URLs
                    content = re.sub(r"`[^`]+`", "", content)

                # For Python files, exclude URLs in comments (lines starting with #)
                # This prevents example URLs in code comments from being checked
                if file_path.suffix == ".py":
                    # Remove single-line comments before URL extraction
                    lines = content.split("\n")
                    non_comment_lines = []
                    for line in lines:
                        # Find the start of a comment (# not inside a string)
                        # Simple approach: strip the comment portion from each line
                        stripped = line.lstrip()
                        if stripped.startswith("#"):
                            # Entire line is a comment, skip it
                            non_comment_lines.append("")
                        else:
                            # Keep the line (inline comments after code are less common
                            # for example URLs, but we keep them for now)
                            non_comment_lines.append(line)
                    content = "\n".join(non_comment_lines)

                urls = url_pattern.findall(content)

                # Clean URLs (remove trailing punctuation)
                cleaned_urls = []
                for url in urls:
                    # Remove trailing punctuation that's likely not part of the URL
                    url = url.rstrip(".,;:!?")
                    # Remove trailing parentheses if unbalanced
                    while url.endswith(")") and url.count(")") > url.count("("):
                        url = url[:-1]
                    # Skip URLs with f-string placeholders (e.g., {variable} or partial {var)
                    # This catches both complete {var} and incomplete {var patterns
                    if "{" in url:
                        continue
                    # Skip URLs marked with {.gd-no-link}
                    if url in excluded_urls:
                        continue
                    cleaned_urls.append(url)

                if cleaned_urls:
                    rel_path = str(file_path.relative_to(self.project_root))
                    by_file[rel_path] = cleaned_urls

                    for url in cleaned_urls:
                        if url not in url_to_files:
                            url_to_files[url] = []
                        url_to_files[url].append(rel_path)

            except Exception as e:  # pragma: no cover
                if verbose:
                    print(f"Warning: Could not read {file_path}: {e}")

        # Check each unique URL
        results = {
            "total": len(url_to_files),
            "ok": [],
            "redirects": [],
            "broken": [],
            "skipped": [],
            "by_file": by_file,
        }

        if verbose:
            print(f"\n🔍 Found {len(url_to_files)} unique URLs to check\n")

        for url in url_to_files:
            # Check if URL matches any ignore pattern
            should_skip = False
            for pattern in ignore_regexes:
                if pattern.search(url):
                    should_skip = True
                    break

            if should_skip:
                results["skipped"].append(url)
                if verbose:
                    print(f"⏭️  Skipped: {url}")
                continue

            try:
                # Use HEAD request first (faster), fall back to GET if needed
                response = requests.head(
                    url,
                    timeout=timeout,
                    allow_redirects=False,
                    headers={"User-Agent": "great-docs-link-checker/1.0"},
                )

                # Some servers don't support HEAD, try GET
                if response.status_code == 405:
                    response = requests.get(
                        url,
                        timeout=timeout,
                        allow_redirects=False,
                        headers={"User-Agent": "great-docs-link-checker/1.0"},
                        stream=True,  # Don't download body
                    )
                    response.close()

                status = response.status_code

                if 200 <= status < 300:
                    results["ok"].append(url)
                    if verbose:
                        print(f"✅ {status} {url}")
                elif 300 <= status < 400:  # pragma: no cover
                    location = response.headers.get("Location", "Unknown")
                    results["redirects"].append(
                        {
                            "url": url,
                            "status": status,
                            "location": location,
                            "files": url_to_files[url],
                        }
                    )
                    if verbose:
                        print(f"↪️  {status} {url} -> {location}")
                else:  # pragma: no cover
                    results["broken"].append(
                        {
                            "url": url,
                            "status": status,
                            "error": f"HTTP {status}",
                            "files": url_to_files[url],
                        }
                    )
                    if verbose:
                        print(f"❌ {status} {url}")

            except requests.exceptions.Timeout:  # pragma: no cover
                results["broken"].append(
                    {
                        "url": url,
                        "status": None,
                        "error": "Timeout",
                        "files": url_to_files[url],
                    }
                )
                if verbose:
                    print(f"⏱️  Timeout: {url}")
            except requests.exceptions.SSLError as e:  # pragma: no cover
                results["broken"].append(
                    {
                        "url": url,
                        "status": None,
                        "error": f"SSL Error: {str(e)[:50]}",
                        "files": url_to_files[url],
                    }
                )
                if verbose:
                    print(f"🔐 SSL Error: {url}")
            except requests.exceptions.ConnectionError:  # pragma: no cover
                results["broken"].append(
                    {
                        "url": url,
                        "status": None,
                        "error": "Connection failed",
                        "files": url_to_files[url],
                    }
                )
                if verbose:
                    print(f"🔌 Connection failed: {url}")
            except Exception as e:  # pragma: no cover
                results["broken"].append(
                    {
                        "url": url,
                        "status": None,
                        "error": str(e)[:100],
                        "files": url_to_files[url],
                    }
                )
                if verbose:
                    print(f"⚠️  Error: {url} - {e}")

        return results

    def spell_check(
        self,
        include_docs: bool = True,
        include_docstrings: bool = False,
        custom_dictionary: list[str] | None = None,
        language: str = "en",
        verbose: bool = False,
    ) -> dict:
        """
        Check spelling in documentation files and optionally docstrings.

        This method scans documentation files (`.qmd`, `.md`) for spelling errors using a
        dictionary-based approach. It intelligently skips code blocks, inline code, URLs, and common
        technical terms.

        Parameters
        ----------
        include_docs
            If `True`, scan documentation files (`.qmd`, `.md`) for spelling errors. Default is
            `True`.
        include_docstrings
            If `True`, also scan Python docstrings in the package. Default is `False`.
        custom_dictionary
            List of additional words to consider correct (e.g., project-specific terms, library
            names). Default is `None`.
        language
            Language for spell checking. Currently supports "en" (English). Default is `"en"`.
        verbose
            If `True`, print detailed progress information. Default is `False`.

        Returns
        -------
        dict
            A dictionary containing:

            - `total_words`: total number of words checked
            - `misspelled`: list of dicts with `word`, `suggestions`, `files`, `contexts`
            - `by_file`: dict mapping file paths to misspelled words in each file
            - `skipped_files`: list of files that couldn't be read

        Examples
        --------
        Check spelling in documentation:

        ```python
        from great_docs import GreatDocs

        docs = GreatDocs()
        results = docs.spell_check()

        print(f"Checked {results['total_words']} words")
        print(f"Misspelled: {len(results['misspelled'])}")

        for item in results['misspelled']:
            print(f"  {item['word']}: {item['suggestions'][:3]}")
        ```

        Check with custom dictionary:

        ```python
        results = docs.spell_check(
            custom_dictionary=["griffe", "docstring", "navbar"]
        )
        ```
        """
        from spellchecker import SpellChecker

        spell = SpellChecker(language=language)

        # Technical terms commonly found in documentation that should be ignored
        technical_terms = {
            # Programming terms
            "api",
            "apis",
            "cli",
            "sdk",
            "html",
            "css",
            "js",
            "json",
            "yaml",
            "yml",
            "xml",
            "sql",
            "http",
            "https",
            "url",
            "urls",
            "uri",
            "uris",
            "utf",
            "ascii",
            "unicode",
            "regex",
            "regexp",
            "stdin",
            "stdout",
            "stderr",
            "async",
            "await",
            "init",
            "kwargs",
            "args",
            "str",
            "int",
            "bool",
            "dict",
            "tuple",
            "config",
            "configs",
            "env",
            "localhost",
            "dev",
            # Python-specific
            "python",
            "pythonic",
            "pypi",
            "pip",
            "venv",
            "virtualenv",
            "conda",
            "pytest",
            "docstring",
            "docstrings",
            "numpy",
            "numpydoc",
            "pandas",
            "scipy",
            "matplotlib",
            "jupyter",
            "ipython",
            "cython",
            "pypy",
            "pydantic",
            "fastapi",
            "flask",
            "django",
            "setuptools",
            "pyproject",
            # Documentation tools
            "quarto",
            "sphinx",
            "mkdocs",
            "readthedocs",
            "rst",
            "markdown",
            "frontmatter",
            "readme",
            "changelog",
            "roadmap",
            # Great Docs specific
            "griffe",
            "pkgdown",
            "navbar",
            "sidebar",
            "toc",
            "qmd",
            # Git/GitHub
            "git",
            "github",
            "gitlab",
            "bitbucket",
            "repo",
            "repos",
            "pr",
            "prs",
            "ci",
            "cd",
            "workflow",
            "workflows",
            # Common abbreviations
            "e.g",
            "i.e",
            "etc",
            "vs",
            "misc",
            "info",
            "param",
            "params",
            "arg",
            "args",
            "attr",
            "attrs",
            "func",
            "funcs",
            "var",
            "vars",
            "src",
            "dest",
            "dir",
            "dirs",
            "tmp",
            "temp",
            "lib",
            "libs",
            # File extensions/types
            "py",
            "md",
            "txt",
            "csv",
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "svg",
            "gif",
            "ico",
            "webp",
            "toml",
            "cfg",
            "ini",
            "sh",
            "bash",
            "zsh",
            # Miscellaneous tech terms
            "localhost",
            "backend",
            "frontend",
            "fullstack",
            "middleware",
            "webhook",
            "webhooks",
            "oauth",
            "jwt",
            "ssl",
            "tls",
            "tcp",
            "udp",
            "dns",
            "cdn",
            "vm",
            "cpu",
            "gpu",
            "ram",
            "ssd",
            "hdd",
            "os",
            "linux",
            "macos",
            "windows",
            "ubuntu",
            "debian",
            "unix",
            "boolean",
            "booleans",
            "inline",
            "metadata",
            "runtime",
            "subprocess",
            "unicode",
            "utf8",
            "utf-8",
            "serializer",
            "deserialize",
            "lifecycle",
            # Web/cloud services
            "aws",
            "netlify",
            "vercel",
            "cloudflare",
            "heroku",
            "azure",
            # Quarto/documentation specific
            "callout",
            "callouts",
            "backticks",
            "monospace",
            "codeblock",
            "codeblocks",
            "filename",
            "filenames",
            "quickstart",
            "theming",
            "versioned",
            "screenshots",
            # CLI terms
            "subcommand",
            "subcommands",
            "clis",
            "eval",
            "cname",
            # Standards/formats
            "orcid",
            "rfc",
            "llm",
            "llms",
            # Contraction fragments (common in docs)
            "aren",  # aren't
            "doesn",  # doesn't
            "isn",  # isn't
            "shouldn",  # shouldn't
            "wouldn",  # wouldn't
            "couldn",  # couldn't
            "didn",  # didn't
            "hasn",  # hasn't
            "haven",  # haven't
            "wasn",  # wasn't
            "weren",  # weren't
            "won",  # won't (also a real word)
            "ll",  # you'll, we'll
            "ve",  # we've, you've
            # Other tech terms
            "classname",
            "classnames",
            "programmatically",
            "ip",
            "qa",
            "alt",
            "org",
            "greatdocs",
        }

        # Add custom dictionary words
        if custom_dictionary:
            technical_terms.update(word.lower() for word in custom_dictionary)

        # Add technical terms to the spell checker's known words
        spell.word_frequency.load_words(technical_terms)

        # Patterns to skip
        code_block_pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
        inline_code_pattern = re.compile(r"`[^`]+`")
        url_pattern = re.compile(r"https?://[^\s<>\"')\]}`\\]+", re.IGNORECASE)
        html_tag_pattern = re.compile(r"<[^>]+>")
        yaml_frontmatter_pattern = re.compile(r"^---\n[\s\S]*?\n---\n", re.MULTILINE)
        directive_pattern = re.compile(r"\{[^}]+\}")  # Quarto directives like {.callout}
        reference_pattern = re.compile(r"@\w+")  # References like @fig-example
        latex_pattern = re.compile(r"\$[^$]+\$")  # LaTeX math
        email_pattern = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
        # File paths: Unix and relative paths like /path/to/file.py, ./dir/file.qmd
        file_path_pattern = re.compile(r"(?:\.?\.?/[\w./\-_]+)")

        # Collect files to scan
        # Note: We scan source directories (user_guide/) not generated output (docs/)
        # because docs/ is transient and users shouldn't edit files there directly
        files_to_scan: list[Path] = []

        if include_docs:
            # Scan user_guide directory if it exists (source documentation)
            user_guide_dir = self.project_root / "user_guide"
            if user_guide_dir.exists():
                files_to_scan.extend(user_guide_dir.rglob("*.qmd"))
                files_to_scan.extend(user_guide_dir.rglob("*.md"))

            # Also check README in project root
            readme = self.project_root / "README.md"
            if readme.exists():
                files_to_scan.append(readme)

        # Track results
        word_to_files: dict[str, set[str]] = {}
        word_contexts: dict[str, list[str]] = {}
        by_file: dict[str, list[str]] = {}
        skipped_files: list[str] = []
        total_words = 0

        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                original_content = content

                # Remove patterns we want to skip
                content = yaml_frontmatter_pattern.sub(" ", content)
                content = code_block_pattern.sub(" ", content)
                content = inline_code_pattern.sub(" ", content)
                content = url_pattern.sub(" ", content)
                content = html_tag_pattern.sub(" ", content)
                content = directive_pattern.sub(" ", content)
                content = reference_pattern.sub(" ", content)
                content = latex_pattern.sub(" ", content)
                content = email_pattern.sub(" ", content)
                content = file_path_pattern.sub(" ", content)

                # Extract words (letters only, min 2 chars)
                words = re.findall(r"\b[a-zA-Z]{2,}\b", content)
                total_words += len(words)

                # Find misspelled words
                misspelled = spell.unknown(words)

                if misspelled:
                    rel_path = str(file_path.relative_to(self.project_root))
                    by_file[rel_path] = list(misspelled)

                    for word in misspelled:
                        word_lower = word.lower()
                        if word_lower not in word_to_files:
                            word_to_files[word_lower] = set()
                            word_contexts[word_lower] = []

                        word_to_files[word_lower].add(rel_path)

                        # Extract context (line containing the word)
                        if len(word_contexts[word_lower]) < 3:  # Limit contexts
                            for line in original_content.split("\n"):
                                if re.search(rf"\b{re.escape(word)}\b", line, re.IGNORECASE):
                                    context = line.strip()[:100]
                                    if context not in word_contexts[word_lower]:
                                        word_contexts[word_lower].append(context)
                                        break

                if verbose:
                    rel_path = str(file_path.relative_to(self.project_root))
                    if misspelled:
                        print(f"📄 {rel_path}: {len(misspelled)} issue(s)")
                    else:
                        print(f"✅ {rel_path}: OK")

            except Exception as e:  # pragma: no cover
                rel_path = str(file_path.relative_to(self.project_root))
                skipped_files.append(rel_path)
                if verbose:
                    print(f"⚠️  Could not read {rel_path}: {e}")

        # Scan docstrings if requested
        if include_docstrings:
            package_name = self._detect_package_name()
            if package_name:
                docstring_misspellings = self._check_docstring_spelling(
                    package_name, spell, verbose
                )
                for word, info in docstring_misspellings.items():
                    word_lower = word.lower()
                    if word_lower not in word_to_files:
                        word_to_files[word_lower] = set()
                        word_contexts[word_lower] = []
                    word_to_files[word_lower].update(info["files"])
                    word_contexts[word_lower].extend(info["contexts"])
                    total_words += info.get("word_count", 0)

        # Build results
        misspelled_list = []
        for word, files in sorted(word_to_files.items()):
            suggestions = list(spell.candidates(word) or [])[:5]
            misspelled_list.append(
                {
                    "word": word,
                    "suggestions": suggestions,
                    "files": sorted(files),
                    "contexts": word_contexts.get(word, []),
                }
            )

        return {
            "total_words": total_words,
            "misspelled": misspelled_list,
            "by_file": by_file,
            "skipped_files": skipped_files,
        }

    def _check_docstring_spelling(
        self,
        package_name: str,
        spell,
        verbose: bool = False,
    ) -> dict:
        """
        Check spelling in package docstrings using griffe.

        Parameters
        ----------
        package_name
            The name of the package to scan.
        spell
            SpellChecker instance to use.
        verbose
            If True, print progress.

        Returns
        -------
        dict
            Mapping of misspelled words to file/context info.
        """
        try:
            import griffe
        except ImportError:
            return {}

        results: dict[str, dict] = {}
        normalized_name = package_name.replace("-", "_")

        try:
            pkg = griffe.load(normalized_name)
        except Exception:  # pragma: no cover
            return {}  # pragma: no cover

        def check_docstring(obj, obj_name: str):
            if not hasattr(obj, "docstring") or not obj.docstring:
                return

            docstring = (
                obj.docstring.value if hasattr(obj.docstring, "value") else str(obj.docstring)
            )

            # Remove code blocks and inline code
            docstring = re.sub(r"```[\s\S]*?```", " ", docstring)
            docstring = re.sub(r"`[^`]+`", " ", docstring)
            docstring = re.sub(r"https?://[^\s]+", " ", docstring)

            words = re.findall(r"\b[a-zA-Z]{2,}\b", docstring)
            misspelled = spell.unknown(words)

            for word in misspelled:
                word_lower = word.lower()
                if word_lower not in results:
                    results[word_lower] = {"files": set(), "contexts": [], "word_count": 0}
                results[word_lower]["files"].add(f"docstring:{obj_name}")
                results[word_lower]["word_count"] += len(words)

                # Add context
                if len(results[word_lower]["contexts"]) < 2:
                    for line in docstring.split("\n"):
                        if word.lower() in line.lower():
                            context = line.strip()[:80]
                            if context:
                                results[word_lower]["contexts"].append(context)
                                break

        def process_members(obj, prefix=""):
            for name, member in obj.members.items():
                if name.startswith("_"):
                    continue

                full_name = f"{prefix}.{name}" if prefix else name

                try:
                    check_docstring(member, full_name)

                    # Process class methods
                    if hasattr(member, "members"):
                        for method_name, method in member.members.items():
                            if not method_name.startswith("_"):
                                check_docstring(method, f"{full_name}.{method_name}")
                except Exception:  # pragma: no cover
                    continue

        try:
            process_members(pkg)
        except Exception:  # pragma: no cover
            pass  # pragma: no cover

        return results
