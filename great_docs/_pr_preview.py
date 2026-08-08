"""Preview a documentation site that CI already built for a PR or workflow run.

Instead of standing up a preview host (Netlify, Cloudflare Pages, per-PR GitHub
Pages), this fetches the HTML site artifact that CI already uploaded for a run,
unpacks it into a local cache, and serves it with the preview server we ship.

The public entry point is `preview_pr`, called by `great-docs preview`
when one of `--pr` / `--run` / `--branch` is given. See PR_PREVIEW_PLAN.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

GITHUB_API = "https://api.github.com"
DEFAULT_WORKFLOW_NAME = "CI Docs"
DEFAULT_ARTIFACT = "docs-html"
_TIMEOUT = 15
_DOWNLOAD_TIMEOUT = 300
# Per-read timeout for the streamed artifact download (generous: blob storage
# can be slow) and how many times to retry, resuming from bytes already on disk.
_READ_TIMEOUT = 120
_DOWNLOAD_RETRIES = 5


class PreviewError(Exception):
    """A user-facing error; the CLI prints the message and exits non-zero."""


# ---------------------------------------------------------------------------
# GitHub URL / repo parsing
# ---------------------------------------------------------------------------


def parse_github_url(url: str | None) -> tuple[str, str] | None:
    """Parse a GitHub URL into `(owner, repo)`.

    Handles the common shapes:

        https://github.com/owner/repo
        https://github.com/owner/repo.git
        git@github.com:owner/repo.git

    Returns `None` if the string is not a GitHub URL.
    """
    if not url or "github.com" not in url:
        return None
    match = re.search(r"github\.com[/:]([^/]+)/([^/\s#?]+)", url)
    if not match:
        return None
    owner = match.group(1)
    repo = match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    repo = repo.rstrip("/")
    if not owner or not repo:
        return None
    return owner, repo


def _parse_owner_repo(value: str) -> tuple[str, str] | None:
    """Parse a plain `owner/repo` string (also tolerates a `.git`/trailing slash)."""
    match = re.fullmatch(r"\s*([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\s*", value or "")
    if match:
        return match.group(1), match.group(2)
    return None


def _git_remote_repo(project_path: str | Path | None) -> tuple[str, str] | None:
    """Read `git remote get-url origin` and parse it into `(owner, repo)`."""
    cwd = str(project_path) if project_path else None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return parse_github_url(result.stdout.strip())


def _config_repo(project_path: str | Path | None) -> tuple[str, str] | None:
    """Fall back to repo info from great-docs.yml / pyproject via GreatDocs."""
    try:
        from .core import GreatDocs

        docs = GreatDocs(project_path=project_path)
        owner, repo, _ = docs._get_github_repo_info()
        if owner and repo:
            return owner, repo
    except Exception:
        return None
    return None


def resolve_repo(
    project_path: str | Path | None,
    repo_override: str | None,
) -> tuple[str, str]:
    """Determine the target `(owner, repo)`.

    Precedence: `--repo` → `git remote origin` → great-docs.yml / pyproject.
    """
    if repo_override:
        parsed = parse_github_url(repo_override) or _parse_owner_repo(repo_override)
        if parsed:
            return parsed
        raise PreviewError(
            f"Could not parse --repo '{repo_override}'. Expected 'owner/repo' or a GitHub URL."
        )

    parsed = _git_remote_repo(project_path)
    if parsed:
        return parsed

    parsed = _config_repo(project_path)
    if parsed:
        return parsed

    raise PreviewError(
        "Could not determine the GitHub repo from git or configuration. Pass --repo owner/repo."
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _gh_path() -> str | None:
    """Return the path to the `gh` CLI, or `None` if it is not installed."""
    return shutil.which("gh")


def _gh_token(gh: str) -> str | None:
    """Read a token from `gh auth token` (empty/None when not logged in)."""
    try:
        result = subprocess.run(
            [gh, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


def _token_from_dotenv(path: str | Path) -> str | None:
    """Read GITHUB_TOKEN / GH_TOKEN from a specific `.env` file."""
    try:
        from dotenv import dotenv_values
    except Exception:  # pragma: no cover - python-dotenv is a hard dependency
        return None
    try:
        values = dotenv_values(str(path))
    except Exception:
        return None
    token = values.get("GITHUB_TOKEN") or values.get("GH_TOKEN")
    return token.strip() if token else None


def resolve_token(
    project_path: str | Path | None,
    env_file: str | None,
) -> tuple[str | None, str | None]:
    """Resolve a GitHub token, returning `(token, source_label)`.

    Order: explicit `--env-file` → environment variables → auto-detected
    `.env` (supplements, never overrides the environment) → `gh auth token`.
    """
    # 1. Explicit --env-file wins (the user deliberately pointed at it).
    if env_file:
        token = _token_from_dotenv(env_file)
        if token:
            return token, f"{env_file}"

    # 2. Real environment variables.
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip(), "GITHUB_TOKEN"

    # 3. Auto-detected .env files (project root, then cwd upward).
    candidates: list[Path] = []
    if project_path:
        candidates.append(Path(project_path) / ".env")
    try:
        from dotenv import find_dotenv

        found = find_dotenv(usecwd=True)
        if found:
            candidates.append(Path(found))
    except Exception:  # pragma: no cover
        pass
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen or not candidate.is_file():
            continue
        seen.add(key)
        token = _token_from_dotenv(candidate)
        if token:
            return token, f"{candidate}"

    # 4. gh auth token.
    gh = _gh_path()
    if gh:
        token = _gh_token(gh)
        if token:
            return token, "gh auth token"

    return None, None


def _no_auth_message() -> str:
    return (
        "No GitHub credentials found. Downloading CI artifacts needs a token with "
        "'Actions: read' (required even for public repos). Provide one via any of:\n"
        "  • gh auth login   (then re-run, optionally with --use-gh)\n"
        "  • GITHUB_TOKEN=... / GH_TOKEN=...   (environment)\n"
        "  • a .env file with GITHUB_TOKEN=...   (auto-detected, or pass --env-file)\n"
        "Create a fine-grained token at https://github.com/settings/tokens (Actions: read)."
    )


# ---------------------------------------------------------------------------
# GitHub client (requests, or the gh CLI)
# ---------------------------------------------------------------------------


@dataclass
class RunInfo:
    """A resolved workflow run and the context used to describe it."""

    run_id: int
    head_sha: str | None = None
    conclusion: str | None = None
    status: str | None = None
    display_title: str | None = None
    head_repo: str | None = None
    base_repo: str | None = None


class GitHubClient:
    """Talks to the GitHub API, either via `requests` + token or the `gh` CLI."""

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        token: str | None = None,
        use_gh: bool = False,
        gh: str | None = None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.use_gh = use_gh
        self.gh = gh

    # -- request helpers ----------------------------------------------------

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self.use_gh:
            return self._gh_api(path, params)
        return self._requests_get(path, params)

    def _requests_get(self, path: str, params: dict[str, Any] | None) -> Any:
        import requests

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            resp = requests.get(
                f"{GITHUB_API}/{path}", headers=headers, params=params, timeout=_TIMEOUT
            )
        except requests.RequestException as exc:
            raise PreviewError(f"GitHub request failed: {exc}") from exc

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            raise PreviewError(
                f"GitHub returned 404 for '{path}'. Wrong number, or a private repo "
                "your token can't see?"
            )
        if resp.status_code in (401, 403):
            if resp.headers.get("X-RateLimit-Remaining") == "0":
                raise PreviewError(
                    "GitHub API rate limit exceeded. Set GITHUB_TOKEN (or use --use-gh) "
                    "for a much higher limit."
                )
            raise PreviewError("GitHub denied the request (need a token with 'Actions: read').")
        raise PreviewError(f"GitHub API error {resp.status_code} for '{path}'.")

    def _gh_api(self, path: str, params: dict[str, Any] | None) -> Any:
        full = path
        if params:
            full = f"{path}?{urlencode(params)}"
        try:
            result = subprocess.run(
                [self.gh, "api", full],  # type: ignore[list-item]
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise PreviewError(f"'gh api {full}' failed: {exc}") from exc
        if result.returncode != 0:
            raise PreviewError(f"'gh api {full}' failed: {result.stderr.strip()}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise PreviewError(f"Could not parse response from 'gh api {full}'.") from exc

    # -- artifact download --------------------------------------------------

    def download_artifact(self, run_id: int, artifact: dict[str, Any], dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        if self.use_gh:
            self._gh_download(run_id, artifact, dest)
        else:
            self._requests_download(artifact, dest)

    def _gh_download(self, run_id: int, artifact: dict[str, Any], dest: Path) -> None:
        args = [
            self.gh,  # type: ignore[list-item]
            "run",
            "download",
            str(run_id),
            "-n",
            artifact["name"],
            "-D",
            str(dest),
            "-R",
            f"{self.owner}/{self.repo}",
        ]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=_DOWNLOAD_TIMEOUT)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PreviewError(f"'gh run download' failed: {exc}") from exc
        if result.returncode != 0:
            raise PreviewError(f"'gh run download' failed: {result.stderr.strip()}")

    def _requests_download(self, artifact: dict[str, Any], dest: Path) -> None:
        import time

        import requests

        url = artifact.get("archive_download_url") or (
            f"{GITHUB_API}/repos/{self.owner}/{self.repo}/actions/artifacts/{artifact['id']}/zip"
        )
        base_headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            base_headers["Authorization"] = f"Bearer {self.token}"

        zip_path = dest / "_artifact.zip"
        zip_path.unlink(missing_ok=True)

        # Artifacts can be hundreds of MB from slow blob storage. A single stalled
        # read shouldn't lose the whole transfer, so retry on network errors and
        # resume from the bytes already on disk via a Range request (the blob
        # store returns 206 + the remainder; if it ignores Range and returns 200,
        # we restart the file).
        last_exc: Exception | None = None
        for attempt in range(_DOWNLOAD_RETRIES):
            have = zip_path.stat().st_size if zip_path.exists() else 0
            headers = dict(base_headers)
            if have:
                headers["Range"] = f"bytes={have}-"
            try:
                # (connect timeout, per-read timeout) — a generous read timeout
                # tolerates slow chunks without abandoning the download.
                with requests.get(
                    url, headers=headers, timeout=(_TIMEOUT, _READ_TIMEOUT), stream=True
                ) as resp:
                    if resp.status_code == 410:
                        raise PreviewError(
                            "This artifact has expired and can no longer be downloaded. "
                            "Re-run the workflow to regenerate it."
                        )
                    if resp.status_code == 206:  # resuming
                        mode, start = "ab", have
                        total = have + int(resp.headers.get("Content-Length") or 0)
                    elif resp.status_code == 200:  # Range ignored; start over
                        mode, start = "wb", 0
                        total = int(resp.headers.get("Content-Length") or 0)
                    else:
                        raise PreviewError(
                            f"Artifact download failed (HTTP {resp.status_code})."
                        )
                    _stream_to_file(resp, zip_path, total, mode=mode, start=start)
                break  # completed
            except requests.RequestException as exc:
                last_exc = exc
                if attempt == _DOWNLOAD_RETRIES - 1:
                    raise PreviewError(
                        f"Artifact download failed after {_DOWNLOAD_RETRIES} attempts: {exc}"
                    ) from exc
                got = zip_path.stat().st_size if zip_path.exists() else 0
                print(
                    f"  … download interrupted ({type(exc).__name__}); "
                    f"resuming from {got / 1e6:.1f} MB "
                    f"(attempt {attempt + 2}/{_DOWNLOAD_RETRIES})",
                    file=sys.stderr,
                )
                time.sleep(2 * (attempt + 1))

        _safe_extract_zip(zip_path, dest)
        zip_path.unlink(missing_ok=True)


def _stream_to_file(
    resp: Any, zip_path: Path, total: int, mode: str = "wb", start: int = 0
) -> None:
    """Stream a response body to disk, showing a progress bar on an interactive terminal.

    Progress is rendered to stderr only when it's a TTY and the size is known. Otherwise the
    download runs quietly (e.g. in CI logs or when piped). ``mode`` is the file open mode
    (``"ab"`` to resume) and ``start`` is the byte count already on disk, used to seed the bar.
    """
    chunk_size = 1 << 16
    show_bar = total > 0 and sys.stderr.isatty()

    if show_bar:
        import click

        with (
            open(zip_path, mode) as handle,
            click.progressbar(
                length=total,
                label="→ Downloading",
                file=sys.stderr,
            ) as bar,
        ):
            if start:
                bar.update(start)
            for chunk in resp.iter_content(chunk_size=chunk_size):
                handle.write(chunk)
                bar.update(len(chunk))
    else:
        with open(zip_path, mode) as handle:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                handle.write(chunk)


# ---------------------------------------------------------------------------
# Resolution steps
# ---------------------------------------------------------------------------


def _pick_run(runs: Any, workflow_name: str) -> RunInfo | None:
    """Choose the newest matching run, preferring a successful conclusion."""
    items = runs.get("workflow_runs", []) if isinstance(runs, dict) else []
    if not items:
        return None
    matches = [r for r in items if r.get("name") == workflow_name] or items
    matches.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    successful = [r for r in matches if r.get("conclusion") == "success"]
    chosen = successful[0] if successful else matches[0]
    return RunInfo(
        run_id=int(chosen["id"]),
        conclusion=chosen.get("conclusion"),
        status=chosen.get("status"),
        display_title=chosen.get("display_title"),
    )


def resolve_run(
    client: GitHubClient,
    *,
    pr: int | None,
    run: int | None,
    branch: str | None,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
) -> RunInfo:
    """Resolve `--pr` / `--run` / `--branch` into a concrete run."""
    if run is not None:
        try:
            return RunInfo(run_id=int(run))
        except (TypeError, ValueError):
            raise PreviewError(f"Invalid --run value: {run!r} (expected a run id).") from None

    owner, repo = client.owner, client.repo

    if pr is not None:
        pull = client.get_json(f"repos/{owner}/{repo}/pulls/{pr}")
        head = pull.get("head", {}) or {}
        sha = head.get("sha")
        if not sha:
            raise PreviewError(f"Could not find the head commit for PR #{pr}.")
        head_repo = (head.get("repo") or {}).get("full_name")
        base_repo = ((pull.get("base", {}) or {}).get("repo") or {}).get("full_name")
        runs = client.get_json(
            f"repos/{owner}/{repo}/actions/runs",
            params={"head_sha": sha, "per_page": 100},
        )
        info = _pick_run(runs, workflow_name)
        if info is None:
            raise PreviewError(
                f"No '{workflow_name}' run found for PR #{pr} (still building?). "
                "Try again shortly, or pass --run <id>."
            )
        info.head_sha = sha
        info.head_repo = head_repo
        info.base_repo = base_repo
        return info

    if branch is not None:
        runs = client.get_json(
            f"repos/{owner}/{repo}/actions/runs",
            params={"branch": branch, "per_page": 100},
        )
        info = _pick_run(runs, workflow_name)
        if info is None:
            raise PreviewError(f"No '{workflow_name}' run found for branch '{branch}'.")
        return info

    raise PreviewError("Specify one of --pr, --run, or --branch.")


def find_artifacts(client: GitHubClient, run_id: int, name: str) -> list[dict[str, Any]]:
    """Return all artifacts uploaded by a run (name filtering happens in choose)."""
    data = client.get_json(
        f"repos/{client.owner}/{client.repo}/actions/runs/{run_id}/artifacts",
        params={"per_page": 100},
    )
    return data.get("artifacts", []) if isinstance(data, dict) else []


def choose_artifact(
    artifacts: list[dict[str, Any]],
    *,
    name: str,
    interactive: bool,
) -> dict[str, Any]:
    """Pick the artifact to download.

    Exact name match wins. Otherwise, if several artifacts exist we prompt (or
    take the newest when non-interactive); a lone artifact is used with a note.
    """
    if not artifacts:
        raise PreviewError(
            "This run uploaded no artifacts (did the build fail before the upload step?)."
        )

    named = [a for a in artifacts if a.get("name") == name]
    if len(named) == 1:
        return named[0]

    candidates = named if len(named) > 1 else artifacts
    if not named:
        if len(artifacts) == 1:
            only = artifacts[0]
            print(f"⚠️  No artifact named '{name}'; using the only one, '{only.get('name')}'.")
            return only
        print(f"⚠️  No artifact named '{name}' on this run — choose one of its artifacts:")

    if not interactive:
        return max(candidates, key=lambda a: a.get("created_at", ""))
    return _prompt_artifact(candidates)


def _prompt_artifact(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    import click

    ordered = sorted(candidates, key=lambda a: a.get("created_at", ""), reverse=True)
    for idx, art in enumerate(ordered, start=1):
        size_mb = (art.get("size_in_bytes", 0) or 0) / 1e6
        created = (art.get("created_at", "") or "").replace("T", " ").replace("Z", " UTC")
        click.echo(f"  {idx}. {art.get('name')}  ({size_mb:.1f} MB, {created})")
    choice = click.prompt("Artifact number", type=click.IntRange(1, len(ordered)), default=1)
    return ordered[choice - 1]


# ---------------------------------------------------------------------------
# Download + extract (with cache)
# ---------------------------------------------------------------------------


def _cache_root() -> Path:
    env = os.environ.get("XDG_CACHE_HOME")
    if env:
        base = Path(env)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path.home() / ".cache"
    return base / "great-docs" / "pr-preview"


def cache_dir_for(owner: str, repo: str, run_id: int, artifact_name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", artifact_name)
    return _cache_root() / f"{owner}-{repo}" / str(run_id) / safe


def clear_cache() -> tuple[bool, Path]:
    """Delete the PR-preview download cache. Returns `(existed, path)`."""
    root = _cache_root()
    existed = root.exists()
    if existed:
        shutil.rmtree(root, ignore_errors=True)
    return existed, root


def _safe_extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract a zip, refusing any member that would escape `dest` (zip-slip)."""
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (dest / member).resolve()
            if target != dest and not str(target).startswith(str(dest) + os.sep):
                raise PreviewError(f"Refusing to extract unsafe path from artifact: {member!r}")
        zf.extractall(dest)


def _find_site_root(base: Path) -> Path | None:
    """Return the shallowest directory under `base` that contains `index.html`."""
    if (base / "index.html").is_file():
        return base
    candidates = sorted(
        base.rglob("index.html"),
        key=lambda p: len(p.relative_to(base).parts),
    )
    return candidates[0].parent if candidates else None


def download_and_extract(
    client: GitHubClient,
    *,
    run_id: int,
    artifact: dict[str, Any],
    refresh: bool = False,
) -> Path:
    """Download + unpack the artifact into the cache and return the site root."""
    dest = cache_dir_for(client.owner, client.repo, run_id, artifact["name"])
    marker = dest / ".gd-complete"

    if not refresh and marker.exists():
        root = _find_site_root(dest)
        if root is not None:
            print("→ Using cached download")
            return root

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)

    client.download_artifact(run_id, artifact, dest)

    root = _find_site_root(dest)
    if root is None:
        raise PreviewError(
            "The downloaded artifact does not contain an index.html — is this a docs site?"
        )
    marker.write_text("ok\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def _print_run_line(info: RunInfo, *, pr: int | None, branch: str | None) -> None:
    bits = []
    if pr is not None:
        bits.append(f"PR #{pr}")
    if branch is not None:
        bits.append(f"branch {branch}")
    if info.head_sha:
        bits.append(f"commit {info.head_sha[:7]}")
    bits.append(f"run {info.run_id}")
    tail = f" ({info.conclusion})" if info.conclusion else ""
    print("→ " + " → ".join(bits) + tail)


def preview_pr(
    project_path: str | Path | None,
    *,
    pr: int | None = None,
    run: int | None = None,
    branch: str | None = None,
    repo: str | None = None,
    artifact: str = DEFAULT_ARTIFACT,
    path: str = "",
    port: int = 3000,
    open_browser: bool = True,
    refresh: bool = False,
    use_gh: bool = False,
    env_file: str | None = None,
    workflow_name: str = DEFAULT_WORKFLOW_NAME,
) -> None:
    """Fetch a CI-built docs site for a PR/run/branch and serve it locally."""
    owner, repo_name = resolve_repo(project_path, repo)
    print(f"→ Repo: {owner}/{repo_name}")

    gh = _gh_path()

    if use_gh:
        if not gh:
            raise PreviewError(
                "--use-gh was given but the 'gh' CLI is not installed. "
                "Install it from https://cli.github.com/, or use a token instead."
            )
        if not _gh_token(gh):
            raise PreviewError(
                "--use-gh was given but 'gh' is not logged in. Run 'gh auth login' first."
            )
        print("→ Auth: gh CLI (--use-gh)")
        client = GitHubClient(owner, repo_name, use_gh=True, gh=gh)
    else:
        token, source = resolve_token(project_path, env_file)
        if not token:
            raise PreviewError(_no_auth_message())
        print(f"→ Auth: {source}")
        client = GitHubClient(owner, repo_name, token=token)

    info = resolve_run(client, pr=pr, run=run, branch=branch, workflow_name=workflow_name)
    _print_run_line(info, pr=pr, branch=branch)

    if info.head_repo and info.base_repo and info.head_repo != info.base_repo:
        print(
            f"⚠️  This build is from a fork ({info.head_repo}). You'll be viewing "
            "contributor-authored HTML/JS locally — same trust as reviewing their diff."
        )
    if info.conclusion and info.conclusion != "success":
        print(
            f"⚠️  The '{workflow_name}' run did not succeed (conclusion: {info.conclusion}); "
            "the site may be incomplete."
        )

    artifacts = find_artifacts(client, info.run_id, artifact)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    chosen = choose_artifact(artifacts, name=artifact, interactive=interactive)

    if chosen.get("expired"):
        raise PreviewError(
            f"Artifact '{chosen.get('name')}' has expired and can no longer be "
            "downloaded. Re-run the workflow to regenerate it."
        )

    size_mb = (chosen.get("size_in_bytes", 0) or 0) / 1e6
    print(f"→ Artifact: {chosen.get('name')} ({size_mb:.1f} MB)")

    root = download_and_extract(client, run_id=info.run_id, artifact=chosen, refresh=refresh)

    from .core import GreatDocs

    GreatDocs.preview_site(root, port=port, open_path=path, open_browser=open_browser)
