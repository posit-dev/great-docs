import shutil
from pathlib import Path

# Quarto sets the working directory to the Quarto project directory.
# In a normal build this is great-docs/ (one level below project root).
# In a versioned build this is .great-docs-build/<version>/ (two levels below).
# We find the project root by walking upward until we find great-docs.yml.
build_dir = Path.cwd()


def _find_project_root(start: Path) -> Path:
    """Walk up from *start* until we find great-docs.yml."""
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

if freeze_source.is_dir():
    freeze_dest = build_dir / "_freeze"
    if freeze_dest.exists():
        shutil.rmtree(freeze_dest)
    shutil.copytree(freeze_source, freeze_dest)
    n_items = sum(1 for _ in freeze_dest.rglob("*") if _.is_file())
    print(f"[pre-render] Restored _freeze/ ({n_items} cached files)")
else:
    print("[pre-render] No _freeze/ found, skipping")
