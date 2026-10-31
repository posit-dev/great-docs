"""Published destinations of authored pages"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .naming import published_path, section_slug

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .._layout import Layout
    from ..config import Config


def output_destination(layout: Layout, output: str) -> Path:
    """
    Resolve a configured output path within the build directory

    Parameters
    ----------
    layout
        The project's directories.
    output
        A path relative to the build directory, such as a custom page directory's `output`.

    Returns
    -------
    :
        The resolved destination.

    Raises
    ------
    ValueError
        If `output` is absolute, contains `..` or resolves outside the build directory.
    """
    path = Path(output)
    destination = (layout.build_dir / path).resolve()
    if (
        path.is_absolute()
        or ".." in path.parts
        or not destination.is_relative_to(layout.build_dir.resolve())
    ):
        raise ValueError(f"Output path must remain inside the build directory: {output}")
    return destination


def section_destination(layout: Layout, section: Mapping[str, object]) -> Path | None:
    """
    Resolve a section's destination directory in the build tree

    The destination is the slug of the section's `dir`. If `dir` is absolute or contains
    `..`, use its path relative to the package root. This preserves the name of a shared
    section when documentation sources are in a subdirectory. For a section outside the
    package, use only the directory name.

    Parameters
    ----------
    layout
        The project's directories.
    section
        An entry in the `sections` setting.

    Returns
    -------
    :
        The destination, or `None` when the entry has no string `dir`.
    """
    directory = section.get("dir")
    if not directory or not isinstance(directory, str):
        return None
    source = Path(directory)
    if source.is_absolute() or ".." in source.parts:
        resolved = (layout.source_dir / source).resolve()
        source = (
            resolved.relative_to(layout.package_root)
            if resolved.is_relative_to(layout.package_root)
            else Path(source.name)
        )
    return output_destination(layout, section_slug(source.as_posix()))


@dataclass(frozen=True)
class PageRoot:
    """An authored page directory and its destination directory in the build tree"""

    source: Path
    """The resolved source directory"""

    destination: Path
    """The directory that receives the pages"""

    strip_prefix: bool
    """Whether published paths drop the numeric ordering prefix of every component"""


@dataclass(frozen=True)
class PageMap:
    """Published page paths indexed by their source paths"""

    homepage: Path
    """The page that the homepage sources publish as"""

    homepage_sources: frozenset[Path]
    """The resolved sources that publish as the homepage"""

    roots: tuple[PageRoot, ...]
    """The page directories, in the order a source is matched against them"""

    @classmethod
    def make(
        cls, config: Config, layout: Layout, guide: Path | None, homepage: Iterable[Path]
    ) -> PageMap:
        """
        Map a project's user guide, sections and custom pages to their published paths

        Parameters
        ----------
        config
            The project's configuration.
        layout
            The project's directories.
        guide
            The user guide's source directory, or `None` when the project has none.
        homepage
            The sources that publish as the homepage.

        Returns
        -------
        :
            The page map, with roots ordered as user guide, sections, then custom pages. A
            page in more than one root publishes under the first matching root.

        Raises
        ------
        ValueError
            If a custom page directory's `output` lies outside the build directory.
        """
        roots: list[PageRoot] = []
        if guide is not None:
            roots.append(
                PageRoot(
                    guide.resolve(),
                    layout.build_dir / "user-guide",
                    not config.user_guide_is_explicit,
                )
            )
        for entry in cast("list[object]", config.sections or []):
            if not isinstance(entry, dict):
                continue
            section = cast("Mapping[str, object]", entry)
            destination = section_destination(layout, section)
            if destination is not None:
                roots.append(
                    PageRoot(
                        (layout.source_dir / str(section["dir"])).resolve(),
                        destination,
                        section.get("type") != "blog",
                    )
                )
        for page in config.custom_pages:
            roots.append(
                PageRoot(
                    (layout.source_dir / page["dir"]).resolve(),
                    output_destination(layout, page["output"]),
                    False,
                )
            )
        return cls(
            layout.build_dir / "index.qmd",
            frozenset(source.resolve() for source in homepage),
            tuple(roots),
        )

    def destination(self, source: Path) -> Path | None:
        """
        Find the published path of an authored page

        Parameters
        ----------
        source
            The resolved path of the page's source.

        Returns
        -------
        :
            The page's destination in the build tree, or `None` if no root contains the page.
        """
        if source in self.homepage_sources:
            return self.homepage
        for root in self.roots:
            if source.is_relative_to(root.source):
                relative = source.relative_to(root.source)
                return root.destination / published_path(relative, strip_prefix=root.strip_prefix)
        return None
