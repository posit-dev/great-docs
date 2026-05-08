from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Agent format definitions
# ---------------------------------------------------------------------------

AgentFormat = Literal[
    "claude",
    "copilot",
    "cursor",
    "windsurf",
    "opencode",
    "codex",
]

# Maps agent format -> (detection markers, default skill directory template)
# The template uses {name} for the skill name.
_AGENT_FORMATS: dict[AgentFormat, dict] = {
    "claude": {
        "markers": [".claude"],
        "skill_dir": ".claude/skills/{name}",
        "global_dir": ".claude/skills/{name}",
        "description": "Claude Code",
    },
    "copilot": {
        "markers": [".github/copilot-instructions.md", ".github"],
        "skill_dir": ".github/skills/{name}",
        "global_dir": ".github/skills/{name}",
        "description": "GitHub Copilot",
    },
    "cursor": {
        "markers": [".cursor", ".cursorrules"],
        "skill_dir": ".cursor/skills/{name}",
        "global_dir": ".cursor/skills/{name}",
        "description": "Cursor",
    },
    "windsurf": {
        "markers": [".windsurf", ".windsurfrules"],
        "skill_dir": ".windsurf/skills/{name}",
        "global_dir": ".windsurf/skills/{name}",
        "description": "Windsurf",
    },
    "opencode": {
        "markers": [".opencode"],
        "skill_dir": ".opencode/skills/{name}",
        "global_dir": ".opencode/skills/{name}",
        "description": "OpenCode",
    },
    "codex": {
        "markers": [".codex"],
        "skill_dir": ".codex/skills/{name}",
        "global_dir": ".codex/skills/{name}",
        "description": "Codex",
    },
}


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from SKILL.md content.

    Returns (frontmatter_dict, body_text).
    """
    try:
        from py_yaml12 import loads as parse_yaml
    except ImportError:  # pragma: no cover
        import yaml

        parse_yaml = yaml.safe_load  # type: ignore[assignment]

    normalized = content.lstrip()
    if not normalized.startswith("---"):
        return {}, content

    parts = normalized.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        fm = parse_yaml(parts[1]) or {}
    except Exception:
        return {}, content

    if not isinstance(fm, dict):
        return {}, content

    return fm, parts[2].lstrip("\n")


# ---------------------------------------------------------------------------
# Skill source resolution
# ---------------------------------------------------------------------------


def _find_package_skills(package: str) -> list[Path]:
    """Find bundled SKILL.md files shipped inside a Python package.

    Looks for `skills/<name>/SKILL.md` inside the installed package directory. Returns a list of
    SKILL.md paths found.
    """
    try:
        from importlib.metadata import packages_distributions
    except ImportError:
        pass

    # Strategy: locate the package's top-level directory and look for skills/
    import importlib

    try:
        # Normalize package name for import (hyphens -> underscores)
        import_name = package.replace("-", "_")
        mod = importlib.import_module(import_name)
    except ImportError:
        return []

    if not hasattr(mod, "__file__") or mod.__file__ is None:
        return []  # pragma: no cover

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


def _find_skill_from_url(url: str) -> tuple[str, str] | None:
    """Fetch a SKILL.md from a well-known URL.

    Tries the agent-skills discovery protocol:

    1. `{url}/.well-known/agent-skills/index.json`
    2. falls back to `{url}/skill.md`

    Returns `(skill_name, content)` or `None` on failure.
    """
    import urllib.error
    import urllib.request

    base = url.rstrip("/")

    # Try the agent-skills discovery protocol
    index_url = f"{base}/.well-known/agent-skills/index.json"
    try:
        with urllib.request.urlopen(index_url, timeout=10) as resp:  # noqa: S310
            index_data = json.loads(resp.read().decode("utf-8"))

        skills = index_data.get("skills", [])
        if skills:
            skill_entry = skills[0]  # Take first skill
            name = skill_entry.get("name", "default")
            skill_url = f"{base}/.well-known/agent-skills/{name}/SKILL.md"
            with urllib.request.urlopen(skill_url, timeout=10) as resp:  # noqa: S310
                content = resp.read().decode("utf-8")
            return name, content
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, OSError):
        pass

    # Fallback: try direct skill.md
    try:
        skill_url = f"{base}/skill.md"
        with urllib.request.urlopen(skill_url, timeout=10) as resp:  # noqa: S310
            content = resp.read().decode("utf-8")
        fm, _ = _parse_frontmatter(content)
        name = fm.get("name", "default")
        return name, content
    except (urllib.error.URLError, OSError):
        pass

    return None


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------


def detect_agents(root: Path) -> list[AgentFormat]:
    """Detect which AI coding agents are configured in the given directory.

    Scans for agent-specific marker files/directories and returns a list of detected agent formats.
    """
    detected: list[AgentFormat] = []
    for fmt, info in _AGENT_FORMATS.items():
        for marker in info["markers"]:
            if (root / marker).exists():
                detected.append(fmt)
                break
    return detected


def detect_agents_global() -> list[AgentFormat]:
    """Detect which AI coding agents have global configuration."""
    home = Path.home()
    return detect_agents(home)


# ---------------------------------------------------------------------------
# Core install / check / list
# ---------------------------------------------------------------------------


def _get_package_version(package: str) -> str | None:
    """Get the installed version of a Python package."""
    try:
        from importlib.metadata import version

        return version(package)
    except Exception:
        return None


def _resolve_skill_dir(
    agent: AgentFormat,
    skill_name: str,
    *,
    global_: bool = False,
    path: str | None = None,
    root: Path | None = None,
) -> Path:
    """Resolve the target directory for skill installation."""
    if path:
        # Explicit path: use as-is (relative to root or absolute)
        p = Path(path)
        if not p.is_absolute():
            p = (root or Path.cwd()) / p
        return p

    fmt_info = _AGENT_FORMATS[agent]
    template = fmt_info["global_dir"] if global_ else fmt_info["skill_dir"]
    dir_path = template.format(name=skill_name)

    if global_:
        return Path.home() / dir_path
    return (root or Path.cwd()) / dir_path


def install_skill(
    *,
    package: str | None = None,
    url: str | None = None,
    skill_content: str | None = None,
    agent: AgentFormat | None = None,
    global_: bool = False,
    path: str | None = None,
    root: Path | None = None,
    detect: bool = False,
    skill_name: str | None = None,
    extra_files: dict[str, str] | None = None,
    quiet: bool = False,
) -> list[Path]:
    """Install a SKILL.md file for AI coding agents.

    Resolves skill content from one of three sources (in priority order):

    1. `skill_content`: raw SKILL.md text provided directly
    2. `url`: fetch from a documentation site's well-known endpoint
    3. `package`: find bundled skills inside an installed Python package

    The skill is installed to the appropriate agent directory based on auto-detection or explicit
    `agent` parameter.

    Parameters
    ----------
    package
        Python package name (e.g., `"great-tables"`). Skills are looked up inside the installed
        package's `skills/` directory.
    url
        Documentation site URL to fetch skills from via the `.well-known` discovery protocol.
    skill_content
        Raw SKILL.md content to install directly.
    agent
        Target agent format. If not set, auto-detected from the project root or prompted
        interactively.
    global_
        Install to the global (home directory) location instead of the repo.
    path
        Explicit target path. Overrides agent-based path resolution.
    root
        Project root directory. Defaults to the current working directory.
    detect
        Auto-detect existing installations and update them in place.
    skill_name
        Override the skill name (derived from frontmatter by default).
    extra_files
        Additional files to install alongside SKILL.md, as `{relative_path: content}` pairs.
    quiet
        Suppress output messages.

    Returns
    -------
    list[Path]
        Paths to installed SKILL.md files (one per agent if multiple detected).
    """
    root = root or Path.cwd()
    installed: list[Path] = []

    # --- Resolve skill content ---
    skills_to_install: list[tuple[str, str, dict[str, str]]] = []
    # Each entry: (name, content, extra_files)

    if skill_content:
        fm, _ = _parse_frontmatter(skill_content)
        name = skill_name or fm.get("name", "default")
        skills_to_install.append((name, skill_content, extra_files or {}))

    elif url:
        result = _find_skill_from_url(url)
        if result is None:
            if not quiet:
                print(f"Error: Could not find skills at {url}")
            return []
        name, content = result
        name = skill_name or name
        skills_to_install.append((name, content, extra_files or {}))

    elif package:
        skill_files = _find_package_skills(package)
        if not skill_files:
            if not quiet:
                print(f"Error: No skills found in package '{package}'")
            return []
        for sf in skill_files:
            content = sf.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(content)
            name = fm.get("name", sf.parent.name)
            # Gather extra files from the skill directory
            extras: dict[str, str] = {}
            skill_dir = sf.parent
            for extra_file in skill_dir.rglob("*"):
                if extra_file.is_file() and extra_file.name != "SKILL.md":
                    rel = extra_file.relative_to(skill_dir)
                    extras[str(rel)] = extra_file.read_text(encoding="utf-8")
            skills_to_install.append((name, content, extras))
    else:
        if not quiet:
            print("Error: Provide one of: package, url, or skill_content")
        return []

    if not skills_to_install:
        return []

    # --- Resolve target agent(s) ---
    if detect:
        agents = _find_existing_installations(root, global_=global_)
        if not agents:
            if not quiet:
                print("No existing skill installations found.")
            return []
    elif agent:
        agents = [agent]
    elif path:
        # Explicit path — install directly without agent detection
        agents = [None]  # type: ignore[list-item]
    else:
        detected = detect_agents_global() if global_ else detect_agents(root)
        if not detected:
            # Default to Claude Code if nothing detected
            detected = ["claude"]
            if not quiet:
                print("No agent detected, defaulting to Claude Code (.claude/skills/)")
        agents = detected

    # --- Stamp install metadata (package_version + content_hash) ---
    if package:
        pkg_ver = _get_package_version(package)
        if pkg_ver:
            stamped: list[tuple[str, str, dict[str, str]]] = []
            for name, content, extras in skills_to_install:
                content = _stamp_install_metadata(content, pkg_ver)
                stamped.append((name, content, extras))
            skills_to_install = stamped

    # --- Install each skill to each agent ---
    for name, content, extras in skills_to_install:
        for ag in agents:
            if ag is None:
                # Explicit path mode
                target_dir = Path(path)  # type: ignore[arg-type]
                if not target_dir.is_absolute():
                    target_dir = root / target_dir
            else:
                target_dir = _resolve_skill_dir(ag, name, global_=global_, path=None, root=root)

            target_dir.mkdir(parents=True, exist_ok=True)
            skill_path = target_dir / "SKILL.md"
            skill_path.write_text(content, encoding="utf-8")

            # Write extra files
            for rel_path, file_content in extras.items():
                extra_target = target_dir / rel_path
                extra_target.parent.mkdir(parents=True, exist_ok=True)
                extra_target.write_text(file_content, encoding="utf-8")

            installed.append(skill_path)
            if not quiet:
                agent_desc = _AGENT_FORMATS[ag]["description"] if ag else "custom path"
                extra_count = len(extras)
                extra_msg = f" (+{extra_count} files)" if extra_count else ""
                print(f"Installed skill '{name}' for {agent_desc}: {skill_path}{extra_msg}")

    return installed


def check_skill(
    *,
    package: str | None = None,
    global_: bool = False,
    local: bool = True,
    root: Path | None = None,
    update: bool = False,
    quiet: bool = False,
) -> list[dict]:
    """Check if installed skills are up to date.

    Scans for installed SKILL.md files and compares their version with the version bundled in the
    installed Python package.

    Parameters
    ----------
    package
        Python package name to check. If None, checks all detected skills.
    global_
        Only check global (home directory) installations.
    local
        Only check local (repository) installations.
    root
        Project root directory. Defaults to the current working directory.
    update
        Automatically update any outdated skills found.
    quiet
        Suppress output messages.

    Returns
    -------
    list[dict]
        Status entries: `{"path": Path, "name": str, "installed_version": str,
        "package_version": str, "status": "current"|"outdated"|"unknown"}`.
    """
    root = root or Path.cwd()
    results: list[dict] = []

    scan_roots: list[Path] = []
    if local:
        scan_roots.append(root)
    if global_:
        scan_roots.append(Path.home())

    for scan_root in scan_roots:
        for fmt, info in _AGENT_FORMATS.items():
            template = info["global_dir"] if scan_root == Path.home() else info["skill_dir"]
            # The template has {name} — glob for any skill name
            glob_pattern = template.replace("{name}", "*")
            skills_base = scan_root / glob_pattern.split("/")[0]
            if not skills_base.exists():
                continue

            # Find all SKILL.md files under agent skill directories
            for skill_md in scan_root.glob(f"{glob_pattern}/SKILL.md"):
                content = skill_md.read_text(encoding="utf-8")
                fm, _ = _parse_frontmatter(content)
                skill_name = fm.get("name", skill_md.parent.name)
                metadata = fm.get("metadata", {})
                installed_pkg_version = str(metadata.get("package_version", ""))
                installed_hash = str(metadata.get("content_hash", ""))

                # Try to find the package that provides this skill
                pkg_name = package or skill_name
                pkg_version = _get_package_version(pkg_name)

                if pkg_version is None:
                    status = "local"
                elif installed_hash:
                    # Content-hash comparison: check if the bundled skill changed
                    status = _check_content_freshness(pkg_name, skill_name, installed_hash)
                elif installed_pkg_version:
                    # Fallback: version comparison (URL-installed, no hash)
                    status = _compare_versions(installed_pkg_version, pkg_version)
                else:
                    # No metadata at all — assume outdated
                    status = "outdated"

                entry = {
                    "path": skill_md,
                    "name": skill_name,
                    "agent": fmt,
                    "installed_pkg_version": installed_pkg_version or "unknown",
                    "package_version": pkg_version or "not installed",
                    "status": status,
                }
                results.append(entry)

                if not quiet:
                    agent_desc = _AGENT_FORMATS[fmt]["description"]
                    if status == "local":
                        print(f"  · {skill_name} ({agent_desc}) [local]")
                    elif status == "current":
                        print(
                            f"  ✓ {skill_name} ({agent_desc}): v{installed_pkg_version} [current]"
                        )
                    else:
                        print(
                            f"  ⚠ {skill_name} ({agent_desc}): "
                            f"v{installed_pkg_version or '?'} → v{pkg_version or '?'} [outdated]"
                        )

    if update:
        outdated = [r for r in results if r["status"] == "outdated"]
        for entry in outdated:
            pkg_name = package or entry["name"]
            skill_files = _find_package_skills(pkg_name)
            for sf in skill_files:
                sf_content = sf.read_text(encoding="utf-8")
                sf_fm, _ = _parse_frontmatter(sf_content)
                if sf_fm.get("name", sf.parent.name) == entry["name"]:
                    target_dir = entry["path"].parent
                    # Re-stamp with current package version + content hash
                    stamped_content = sf_content
                    pkg_ver = _get_package_version(pkg_name)
                    if pkg_ver:
                        stamped_content = _stamp_install_metadata(sf_content, pkg_ver)
                    (target_dir / "SKILL.md").write_text(stamped_content, encoding="utf-8")
                    # Copy extra files
                    for extra in sf.parent.rglob("*"):
                        if extra.is_file() and extra.name != "SKILL.md":
                            rel = extra.relative_to(sf.parent)
                            dest = target_dir / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(extra, dest)
                    if not quiet:
                        print(f"  Updated '{entry['name']}' to v{entry['package_version']}")
                    entry["status"] = "updated"
                    break

    return results


def list_skills(
    *,
    package: str | None = None,
    url: str | None = None,
    quiet: bool = False,
) -> list[dict]:
    """List available skills from a package or URL.

    Parameters
    ----------
    package
        Python package name to list skills from.
    url
        Documentation site URL to query for skills.
    quiet
        Suppress output messages.

    Returns
    -------
    list[dict]
        Skill entries: `{"name": str, "description": str, "path": Path|None,
        "version": str|None}`.
    """
    results: list[dict] = []

    if package:
        skill_files = _find_package_skills(package)
        for sf in skill_files:
            content = sf.read_text(encoding="utf-8")
            fm, _ = _parse_frontmatter(content)
            metadata = fm.get("metadata", {})
            results.append(
                {
                    "name": fm.get("name", sf.parent.name),
                    "description": fm.get("description", ""),
                    "path": sf,
                    "version": str(metadata.get("version", "unknown")),
                    "source": "package",
                }
            )

    elif url:
        base = url.rstrip("/")
        import urllib.error
        import urllib.request

        index_url = f"{base}/.well-known/agent-skills/index.json"
        try:
            with urllib.request.urlopen(index_url, timeout=10) as resp:  # noqa: S310
                index_data = json.loads(resp.read().decode("utf-8"))
            for entry in index_data.get("skills", []):
                results.append(
                    {
                        "name": entry.get("name", "unknown"),
                        "description": entry.get("description", ""),
                        "path": None,
                        "version": None,
                        "source": "url",
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            if not quiet:
                print(f"Error: Could not fetch skill index from {url}")

    if not quiet and results:
        for skill in results:
            ver = f" (v{skill['version']})" if skill.get("version") else ""
            print(f"  {skill['name']}{ver}: {skill['description']}")

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_existing_installations(root: Path, *, global_: bool = False) -> list[AgentFormat]:
    """Find agent formats that already have skill installations."""
    scan_root = Path.home() if global_ else root
    found: list[AgentFormat] = []
    for fmt, info in _AGENT_FORMATS.items():
        template = info["global_dir"] if global_ else info["skill_dir"]
        glob_pattern = template.replace("{name}", "*")
        skill_files = list(scan_root.glob(f"{glob_pattern}/SKILL.md"))
        if skill_files:
            found.append(fmt)
    return found


def _content_hash(content: str) -> str:
    """Compute a SHA-256 hash of SKILL.md content for freshness checking.

    Hashes the *original* content (before any install-time stamping) so that the hash is stable
    across installs of the same skill version.
    """
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _stamp_install_metadata(content: str, pkg_version: str) -> str:
    """Inject install-time metadata into SKILL.md frontmatter.

    Stamps two fields into `metadata`:

    - `package_version`: the Python package version at install time
    - `content_hash`: SHA-256 prefix of the *original* content (before stamping)

    These allow `skill check` to determine whether the installed skill content is still current
    without false positives from version bumps that didn't change the skill text.
    """
    fm, body = _parse_frontmatter(content)
    if not fm:
        return content

    metadata = fm.setdefault("metadata", {})
    metadata["package_version"] = pkg_version
    metadata["content_hash"] = _content_hash(content)

    # Re-serialize frontmatter
    try:
        from py_yaml12 import dumps as format_yaml
    except ImportError:  # pragma: no cover
        import yaml

        format_yaml = yaml.dump  # type: ignore[assignment]

    fm_text = format_yaml(fm)
    if isinstance(fm_text, bytes):
        fm_text = fm_text.decode("utf-8")  # pragma: no cover
    return f"---\n{fm_text.rstrip()}\n---\n\n{body}"


def _check_content_freshness(
    pkg_name: str,
    skill_name: str,
    installed_hash: str,
) -> str:
    """Compare installed skill content hash against the bundled source.

    Looks up the bundled SKILL.md from the installed Python package, hashes it, and compares against
    the `content_hash` stamped at install time.

    Returns `"current"` if the content hasn't changed, `"outdated"` if it has, or `"outdated"` if
    the bundled source can't be found.
    """
    skill_files = _find_package_skills(pkg_name)
    for sf in skill_files:
        sf_content = sf.read_text(encoding="utf-8")
        sf_fm, _ = _parse_frontmatter(sf_content)
        if sf_fm.get("name", sf.parent.name) == skill_name:
            current_hash = _content_hash(sf_content)
            if current_hash == installed_hash:
                return "current"
            return "outdated"

    # Couldn't find bundled source — can't verify
    return "outdated"


def _compare_versions(installed: str, current: str) -> str:
    """Compare two version strings, returning a status.

    Returns `"current"` if the installed version is equal to or newer than the current package
    version, `"outdated"` if it is older.

    Used as a fallback when no content hash is available (e.g., URL installs).
    """
    try:
        from packaging.version import Version

        if Version(installed) >= Version(current):
            return "current"
        return "outdated"
    except Exception:
        if installed == current:
            return "current"
        return "outdated"
