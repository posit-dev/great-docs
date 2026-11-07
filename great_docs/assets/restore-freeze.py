import json
import shutil
from pathlib import Path

# Restore the persisted freeze cache before rendering this Quarto project.
# Version projects share a depth, so the relative cache path also applies to
# historical copies. Older generated projects use ancestor discovery.
#
# Historical caches live under `_versions/<build directory name>/`. Fall back to
# the latest version's cache at the root when a version has no cache of its own.
# Quarto reuses a cached result only when the page's source hash matches.
VERSIONS_DIR = "_versions"
build_dir = Path.cwd()


def _find_project_root(start: Path) -> Path:
    """
    Find the project root at or above `start`

    Parameters
    ----------
    start
        Directory where the search begins.

    Returns
    -------
    Nearest directory containing `great-docs.yml`.

    Raises
    ------
    RuntimeError
        If the search reaches its directory limit without finding the file.
    """
    current = start
    for _ in range(10):  # safety limit
        if (current / "great-docs.yml").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: assume one level up (original behavior)
    return start.parent


project_root = _find_project_root(build_dir)
freeze_source = project_root / "_freeze"
options_path = build_dir / "_gd_options.json"
if options_path.is_file():
    options = json.loads(options_path.read_text(encoding="utf-8"))
    if options.get("freeze_dir"):
        freeze_source = (build_dir / options["freeze_dir"]).resolve()

version_source = freeze_source / VERSIONS_DIR / build_dir.name
if version_source.is_dir():
    freeze_source = version_source


def _skip_versions(directory: str, names: list[str]) -> list[str]:
    """
    Exclude historical caches from the root of the cache being restored

    Parameters
    ----------
    directory
        Directory whose entries are about to be copied.
    names
        Names of the entries in `directory`.

    Returns
    -------
    :
        Entry names to exclude from the copy.
    """
    return [VERSIONS_DIR] if Path(directory) == freeze_source else []


if freeze_source.is_dir():
    freeze_dest = build_dir / "_freeze"
    if freeze_dest.exists():
        shutil.rmtree(freeze_dest)
    shutil.copytree(freeze_source, freeze_dest, ignore=_skip_versions)
    n_items = sum(1 for _ in freeze_dest.rglob("*") if _.is_file())
    print(f"[pre-render] Restored _freeze/ ({n_items} cached files)")
else:
    print("[pre-render] No _freeze/ found, skipping")
