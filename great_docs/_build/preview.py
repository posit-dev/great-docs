"""
Shared preview repository resolution and comment identity
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .._project import Project
from .._project.layout import Layout
from .._project.repository import Repository
from .preview_artifacts import PreviewError

PREVIEW_COMMENT_MARKER = "<!-- great-docs:docs-preview -->"


def repository_from_input(
    value: str, *, provider: str | None = None, base_url: str | None = None
) -> Repository:
    """Parse explicit preview input while keeping shorthand provider selection explicit"""
    value = value.strip()
    if "://" not in value and ":" not in value and "@" not in value:
        base = base_url or ("https://gitlab.com" if provider == "gitlab" else "https://github.com")
        value = f"{base.rstrip('/')}/{value}"
    try:
        repository = Repository.parse(value, provider=provider, base_url=base_url)
    except ValueError as error:
        raise PreviewError(str(error)) from error
    if repository is None:
        raise PreviewError(
            "Could not parse --repo. Use a full repository URL and an explicit provider for custom hosts."
        )
    return repository


def resolve_repository(
    project_path: str | Path | None,
    repo_override: str | None,
    *,
    provider: str | None = None,
    base_url: str | None = None,
    config_path: str | None = None,
) -> Repository:
    """Resolve preview identity without discarding a configured instance prefix"""
    configured: Repository | None = None
    try:
        layout = Layout.make(
            Path(project_path or Path.cwd()), Path(config_path) if config_path else None
        )
        configured = Project.make(layout.load_config(), layout).repository
    except (ValueError, OSError):
        pass

    def parse(value: str) -> Repository:
        selected_provider, selected_base = provider, base_url
        if configured is not None:
            host = urlsplit(value).hostname
            if "://" not in value and ":" in value:
                host = value.partition(":")[0].rpartition("@")[2]
            same_instance = host is not None and host == urlsplit(configured.base_url).hostname
            if same_instance:
                selected_provider = provider or configured.provider
                selected_base = base_url or configured.base_url
        return repository_from_input(value, provider=selected_provider, base_url=selected_base)

    if repo_override:
        return parse(repo_override)
    try:
        remote = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        remote = None
    if remote is not None and remote.returncode == 0:
        try:
            repository = parse(remote.stdout.strip())
        except PreviewError:
            repository = None
        if repository is not None:
            return repository
    if configured is not None:
        if provider is not None and configured.provider != provider:
            raise PreviewError("--provider conflicts with the configured repository provider.")
        return repository_from_input(
            configured.url, provider=configured.provider, base_url=base_url or configured.base_url
        )
    raise PreviewError("Could not determine the repository. Pass --repo with its full URL.")
