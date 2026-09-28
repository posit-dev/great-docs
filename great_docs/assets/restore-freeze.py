import json
import shutil
from pathlib import Path

# Version projects share a depth, so the relative cache path also applies to
# historical copies. Older generated projects use ancestor discovery.
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

if freeze_source.is_dir():
    freeze_dest = build_dir / "_freeze"
    if freeze_dest.exists():
        shutil.rmtree(freeze_dest)
    shutil.copytree(freeze_source, freeze_dest)
    n_items = sum(1 for _ in freeze_dest.rglob("*") if _.is_file())
    print(f"[pre-render] Restored _freeze/ ({n_items} cached files)")
else:
    print("[pre-render] No _freeze/ found, skipping")
