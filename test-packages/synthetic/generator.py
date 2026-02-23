"""
Great Docs Gauntlet (GDG) — package directory generator.

Creates real directory structures on disk from declarative spec dicts.
Each spec defines the files, metadata, and expected outcomes for a
minimal GDG test package.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import yaml


def generate_package(
    spec: dict[str, Any],
    target_dir: Path,
    config_override: Path | str | None = None,
) -> Path:
    """
    Create a synthetic package directory from a spec.

    Parameters
    ----------
    spec
        Package specification dict. Must have at least ``"name"`` and ``"files"``.
    target_dir
        Parent directory in which to create the package folder.
    config_override
        Optional path to a YAML file to copy as ``great-docs.yml`` inside the
        generated package.  Overrides any ``great-docs.yml`` that the spec
        itself supplies in its ``"files"`` dict.

    Returns
    -------
    Path
        Absolute path to the created package directory.
    """
    pkg_name: str = spec["name"]
    pkg_dir = target_dir / pkg_name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    # --- pyproject.toml --------------------------------------------------
    if "pyproject_toml" in spec:
        _write_pyproject_toml(pkg_dir, spec["pyproject_toml"])

    # --- setup.cfg (for packages that use setup.cfg only) ----------------
    if "setup_cfg" in spec:
        (pkg_dir / "setup.cfg").write_text(spec["setup_cfg"], encoding="utf-8")

    # --- setup.py (for legacy packages) ----------------------------------
    if "setup_py" in spec:
        (pkg_dir / "setup.py").write_text(spec["setup_py"], encoding="utf-8")

    # --- Arbitrary files -------------------------------------------------
    files: dict[str, str] = spec.get("files", {})
    for rel_path, content in files.items():
        file_path = pkg_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Dedent the content to allow indented multi-line strings in specs
        file_path.write_text(textwrap.dedent(content), encoding="utf-8")

    # --- great-docs.yml (config) -----------------------------------------
    if "config" in spec:
        _write_yaml(pkg_dir / "great-docs.yml", spec["config"])

    # --- Config override (takes precedence) ------------------------------
    if config_override is not None:
        override_path = Path(config_override)
        if override_path.exists():
            (pkg_dir / "great-docs.yml").write_text(
                override_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        else:
            # Treat as raw YAML string
            (pkg_dir / "great-docs.yml").write_text(str(config_override), encoding="utf-8")

    return pkg_dir


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_pyproject_toml(pkg_dir: Path, data: dict[str, Any]) -> None:
    """Produce a minimal pyproject.toml from a nested dict."""
    lines: list[str] = []
    _toml_section(lines, data, prefix="")
    (pkg_dir / "pyproject.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_section(lines: list[str], data: dict[str, Any], prefix: str) -> None:
    """Recursively serialize a dict into TOML-ish text.

    Good enough for the simple structures we need (no arrays-of-tables, etc.).
    """
    scalars: dict[str, Any] = {}
    tables: dict[str, Any] = {}

    for k, v in data.items():
        if isinstance(v, dict):
            tables[k] = v
        else:
            scalars[k] = v

    # Emit scalars under current header
    if scalars:
        if prefix:
            lines.append(f"[{prefix}]")
        for k, v in scalars.items():
            # Keys with special characters or empty keys must be quoted
            key_str = f'"{k}"' if (not k or "-" in k or " " in k) else k
            lines.append(f"{key_str} = {_toml_value(v)}")
        lines.append("")

    # Recurse into sub-tables
    for k, v in tables.items():
        # Quote table key segments that contain special characters
        quoted_k = f'"{k}"' if ("-" in k or " " in k) else k
        sub_prefix = f"{prefix}.{quoted_k}" if prefix else quoted_k
        _toml_section(lines, v, sub_prefix)


def _toml_value(v: Any) -> str:
    """Format a Python value as a TOML literal."""
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int | float):
        return str(v)
    if isinstance(v, list):
        inner = ", ".join(_toml_value(i) for i in v)
        return f"[{inner}]"
    return f'"{v}"'


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a dict as YAML."""
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
