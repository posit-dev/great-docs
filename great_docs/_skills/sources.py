"""
Discover skills bundled in packages and published at URLs
"""

from __future__ import annotations

import json
from pathlib import Path

from .._yaml import split_front_matter

WELL_KNOWN_ROOT = ".well-known/agent-skills"
INDEX_FILE = "index.json"
SKILL_FILE = "SKILL.md"


def find_in_package(package: str) -> list[Path]:
    """Find bundled SKILL.md files shipped inside a Python package.

    Looks for `skills/<name>/SKILL.md` inside the installed package directory. Returns a list of
    SKILL.md paths found.
    """
    # Strategy: locate the package's top-level directory and look for skills/
    import importlib

    try:
        # Normalize package name for import (hyphens -> underscores)
        import_name = package.replace("-", "_")
        mod = importlib.import_module(import_name)
    except ImportError:
        return []

    if not hasattr(mod, "__file__") or mod.__file__ is None:
        return []

    pkg_dir = Path(mod.__file__).parent

    # Check for skills/ directory inside the package
    skills_dir = pkg_dir / "skills"
    if not skills_dir.is_dir():
        # Also check at the project root (one level up from package dir)
        project_root = pkg_dir.parent
        skills_dir = project_root / "skills"
        if not skills_dir.is_dir():
            return []

    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    return skill_files


def find_at_url(url: str) -> list[tuple[str, str]] | None:
    """Fetch skills from a well-known URL.

    Tries the agent-skills discovery protocol:

    1. `{url}/.well-known/agent-skills/index.json` — fetches *all* listed skills
    2. falls back to `{url}/skill.md` (single skill)

    Returns a list of `(skill_name, content)` tuples, or `None` on failure.
    """
    import urllib.error
    import urllib.request

    base = url.rstrip("/")

    # Try the agent-skills discovery protocol
    index_url = f"{base}/{WELL_KNOWN_ROOT}/{INDEX_FILE}"
    try:
        with urllib.request.urlopen(index_url, timeout=10) as resp:  # noqa: S310
            index_data = json.loads(resp.read().decode("utf-8"))

        skills = index_data.get("skills", [])
        if skills:
            results: list[tuple[str, str]] = []
            for skill_entry in skills:
                name = skill_entry.get("name", "default")
                skill_url = f"{base}/{WELL_KNOWN_ROOT}/{name}/{SKILL_FILE}"
                try:
                    with urllib.request.urlopen(skill_url, timeout=10) as resp:  # noqa: S310
                        content = resp.read().decode("utf-8")
                    results.append((name, content))
                except (urllib.error.URLError, OSError):
                    pass  # Skip skills that fail to download
            if results:
                return results
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, OSError):
        pass

    # Fallback: try direct skill.md
    try:
        skill_url = f"{base}/skill.md"
        with urllib.request.urlopen(skill_url, timeout=10) as resp:  # noqa: S310
            content = resp.read().decode("utf-8")
        fm, _ = split_front_matter(content)
        name = fm.string("name") or "default"
        return [(name, content)]
    except (urllib.error.URLError, OSError):
        pass

    return None
