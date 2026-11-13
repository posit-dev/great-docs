"""
Build directory preparation

Replace the build directory with a fresh Quarto project containing the initial site
configuration, assets, scripts, stylesheets and bibliography. Configure the API reference
and write the homepage and project pages.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._content import marimo, publish
from .._content import user_guide as authored_guide
from .._reference import sections as reference_sections
from .._website import page_dates, quarto_yml, scripts
from . import content, outputs, reference
from .ownership import GITIGNORE_CONTENT
from .steps import Outcome, print_warning

if TYPE_CHECKING:
    from .._project.layout import Layout
    from .._project.remote import Remote
    from ..config import Config
    from .pipeline import Run

__all__ = ["build_directory"]

_ASSETS = Path(__file__).parents[1] / "assets"


def build_directory(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    remote: Remote,
    page_authors: list[dict[str, Any]],
    refresh: bool,
) -> Outcome:
    """
    Create the build directory and its initial Quarto project

    Remove the previous build directory so stale generated files cannot enter the new build.
    Warn when a configured pre-render script, bibliography, CSL or CSS file is missing.

    Parameters
    ----------
    run
        The current build, updated with the initial Quarto configuration, API reference
        availability, reference navigation and the discovered user guide.
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of PyPI release dates for the package information page.
    page_authors
        The site's authors, added to the homepage and project pages.
    refresh
        Whether to discover API reference sections even when the cached sections are valid.

    Returns
    -------
    :
        The result line indicating that the build directory is ready.

    Raises
    ------
    ValueError
        If two pre-render scripts share a filename, or one is named `restore-freeze.py`.
    """
    build_dir = layout.build_dir
    print(f"Preparing build directory: {build_dir.relative_to(layout.package_root)}/")

    outputs.validate(config, layout)

    hook_names = [Path(path).name for path in config.pre_render]
    if len(hook_names) != len(set(hook_names)) or "restore-freeze.py" in hook_names:
        raise ValueError("Pre-render scripts must have distinct, non-reserved filenames")

    if build_dir.exists():
        shutil.rmtree(build_dir)

    build_dir.mkdir(parents=True, exist_ok=True)
    run.quarto_config = quarto_yml.write_initial(build_dir)

    scripts_dir = build_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    reference_dir = build_dir / "reference"
    reference_dir.mkdir(exist_ok=True)
    # Directory metadata identifies reference pages from older snapshots as generated.
    page_dates.mark_generated(reference_dir, config)

    # Restore an existing freeze cache even when freezing is disabled for this build.
    if config.freeze or layout.freeze_dir.is_dir():
        _ = shutil.copy2(_ASSETS / "restore-freeze.py", scripts_dir / "restore-freeze.py")

    for script_path in config.pre_render:
        src = layout.source_dir / script_path
        if src.is_file():
            _ = shutil.copy2(src, scripts_dir / src.name)
        else:
            print(f"Warning: Pre-render script not found: {script_path}")

    # The site configuration refers to bibliography, CSL and CSS files by their basenames.
    for bib_path in config.bibliography:
        src = layout.source_dir / bib_path
        if src.is_file():
            _ = publish.copy_asset(layout, src, build_dir / src.name)
        else:
            print(f"Warning: Bibliography file not found: {bib_path}")
    csl_path = config.csl
    if csl_path:
        csl_src = layout.source_dir / csl_path
        if csl_src.is_file():
            _ = publish.copy_asset(layout, csl_src, build_dir / csl_src.name)
        else:
            print(f"Warning: CSL file not found: {csl_path}")
    for css_path in config.css:
        css_src = layout.source_dir / css_path
        if css_src.is_file():
            _ = publish.copy_asset(layout, css_src, build_dir / css_src.name)
        else:
            print(f"Warning: CSS file not found: {css_path}")

    _ = shutil.copy2(_ASSETS / "great-docs.scss", build_dir / "great-docs.scss")

    # Quarto resolves the signature grammar relative to the build directory.
    _ = shutil.copy2(_ASSETS / "pythonsignature.xml", build_dir / "pythonsignature.xml")

    demo_json_src = _ASSETS / "api-evolution-demo.json"
    if demo_json_src.exists():
        _ = shutil.copy2(demo_json_src, build_dir / "api-evolution-demo.json")

    # Quarto discovers the evolution shortcode extension in `_extensions/`.
    extensions_src = _ASSETS / "_extensions"
    if extensions_src.exists():
        _ = shutil.copytree(extensions_src, build_dir / "_extensions", dirs_exist_ok=True)

    # Embedded marimo notebooks need island HTML and WASM exports before Quarto renders them.
    if config.marimo_enabled:
        marimo.prepare_notebooks(
            layout.source_dir,
            build_dir,
            report=print,
            warn=partial(print, file=sys.stderr),
        )

    scripts.copy(
        config,
        build_dir,
        has_repository=(
            run.project.repository is not None and run.project.repository.provider == "github"
        ),
    )

    _ = (build_dir / ".gitignore").write_text(GITIGNORE_CONTENT, encoding="utf-8")

    page_dates.copy_portraits(config, layout.source_dir, build_dir)

    # The restore script needs the freeze cache path relative to the build directory.
    gd_options = {"freeze_dir": os.path.relpath(layout.freeze_dir, build_dir)}
    with open(build_dir / "_gd_options.json", "w") as f:
        json.dump(gd_options, f)

    reference.add_api_block(run, config, refresh=refresh)
    if run.api_block is not None:
        run.contributions.append(reference_sections.contribution(config, run.api_block))

    # API reference availability determines whether the homepage links to `llms.txt` and
    # `llms-full.txt`; resolve it before writing the homepage.
    run.user_guide = authored_guide.discover(config, layout, report=print_warning)
    content.homepage(run, config, layout, page_authors=page_authors, remote=remote)
    return "Ready"
