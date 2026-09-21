"""Resolve package and documentation layout paths"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_PROJECT_MANIFESTS = ("pyproject.toml", "setup.py", "go.mod", "Cargo.toml")
_UNSAFE_TAG_CHARS = re.compile(r"[^A-Za-z0-9._-]")


class LayoutError(ValueError):
    """An invalid or ambiguous documentation layout"""


@dataclass(frozen=True)
class Layout:
    """Resolved paths for a Great Docs project"""

    package_root: Path
    config_path: Path
    source_dir: Path
    build_dir: Path
    site_dir: Path
    freeze_dir: Path
    cache_dir: Path

    @classmethod
    def make(
        cls,
        project_path: Path,
        config_path: Path | None = None,
        *,
        create: bool = False,
    ) -> Layout:
        """
        Resolve a documentation layout from project context

        Automatic selection considers configuration files at the package root
        and in `docs/`. An explicit configuration must remain within the
        discovered package root.

        Parameters
        ----------
        project_path
            Directory where package discovery begins.
        config_path
            Explicit configuration file. Relative paths use the current
            working directory.
        create
            Permit a missing explicit file or select `docs/great-docs.yml`
            when neither conventional configuration exists.

        Returns
        -------
        Layout
            The resolved package, source, build, site, and cache paths.

        Raises
        ------
        LayoutError
            If automatic selection is ambiguous, an explicit file is missing,
            or the selected configuration is outside the package root.
        """
        package_root = _find_package_root(project_path.resolve())
        selected = _select_config(package_root, config_path, create=create)
        resolved_config = selected.resolve()
        if not resolved_config.is_relative_to(package_root):
            raise LayoutError(
                f"Configuration must be inside the package root {package_root}: {selected}"
            )

        source_dir = resolved_config.parent
        if source_dir == package_root:
            build_dir = package_root / "great-docs"
            site_dir = build_dir / "_site"
            cache_dir = package_root / ".great-docs-cache"
        else:
            build_dir = source_dir / "_quarto" / "default"
            site_dir = source_dir / "_site"
            cache_dir = source_dir / ".cache"

        return cls(
            package_root=package_root,
            config_path=resolved_config,
            source_dir=source_dir,
            build_dir=build_dir,
            site_dir=site_dir,
            freeze_dir=source_dir / "_freeze",
            cache_dir=cache_dir,
        )

    def build_dir_for(self, tag: str, latest_tag: str) -> Path:
        """
        Derive the Quarto project directory for a version tag

        Parameters
        ----------
        tag
            Configured version tag.
        latest_tag
            Tag rendered through the default build directory.

        Returns
        -------
        Path
            The default build directory for the latest tag or a sanitised
            historical directory for any other tag.
        """
        if tag == latest_tag:
            return self.build_dir

        safe_tag = _UNSAFE_TAG_CHARS.sub("-", tag)
        if self.source_dir == self.package_root:
            return self.build_dir.parent / f"{self.build_dir.name}-{safe_tag}"
        if safe_tag in {"", ".", "..", "default"}:
            raise LayoutError(f"Historical version tag {tag!r} cannot use build name {safe_tag!r}")
        return self.build_dir.parent / safe_tag


def _find_package_root(project_path: Path) -> Path:
    """
    Find the nearest supported project manifest within five directory levels

    Parameters
    ----------
    project_path
        Directory where the upward search begins.

    Returns
    -------
    Path
        The nearest package root, or the initial directory when no manifest is
        found.
    """
    current = project_path
    for _ in range(5):
        if any((current / manifest).exists() for manifest in _PROJECT_MANIFESTS):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return project_path


def _select_config(
    package_root: Path,
    config_path: Path | None,
    *,
    create: bool,
) -> Path:
    """
    Select an explicit or conventional configuration path

    Parameters
    ----------
    package_root
        Root used for conventional configuration candidates.
    config_path
        Explicit configuration file, if supplied.
    create
        Permit selection of a file that does not yet exist.

    Returns
    -------
    Path
        The selected configuration path before containment validation.

    Raises
    ------
    LayoutError
        If an explicit file is missing or both conventional files exist.
    """
    if config_path is not None:
        selected = config_path.resolve()
        if create and not selected.exists():
            conventional = [package_root / "great-docs.yml", package_root / "docs/great-docs.yml"]
            if any(path.is_file() and path.resolve() != selected for path in conventional):
                raise LayoutError(
                    "A conventional configuration already exists. Select it or migrate the project before creating another configuration."
                )
        if selected.exists() and not selected.is_file():
            raise LayoutError(f"Configuration path is not a file: {selected}")
        if not create and not selected.is_file():
            raise LayoutError(f"Configuration file does not exist: {selected}")
        return selected

    root_config = package_root / "great-docs.yml"
    docs_config = package_root / "docs" / "great-docs.yml"
    root_exists = root_config.is_file()
    docs_exists = docs_config.is_file()
    if root_exists and docs_exists:
        raise LayoutError(
            "Found Great Docs configuration files in both the package root "
            "and docs/. Select one explicitly."
        )
    if root_exists:
        return root_config
    if docs_exists:
        return docs_config
    if create:
        return docs_config
    return root_config
