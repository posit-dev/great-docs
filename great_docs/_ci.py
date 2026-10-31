"""Helpers for `great-docs ci`: small utilities meant to run inside CI.

These render (and post) the "preview this build locally" hints that tell reviewers how to open a
PR's docs without a preview host. Keeping the message text here (rather than inline in workflow
YAML) means it lives in one place, is unit-testable, and stays consistent between the log notice and
the sticky PR comment. See `great_docs._pr_preview` for the `preview` command these hints point at.
"""

from __future__ import annotations

import os

from ._github import GithubRepo, token_from_env
from ._pr_preview import GITHUB_API, PreviewError, _parse_owner_repo

_TIMEOUT = 15

# Hidden marker used to find (and update in place) our own PR comment.
PREVIEW_COMMENT_MARKER = "<!-- great-docs:docs-preview -->"


# ---------------------------------------------------------------------------
# Message rendering (single source of truth for both the notice and the comment)
# ---------------------------------------------------------------------------


def render_preview_comment(run_id: int | str, pr: int | str) -> str:
    """Render the sticky PR comment body (Markdown), including the hidden marker."""
    lines = [
        PREVIEW_COMMENT_MARKER,
        "### 📚 Preview this PR's docs locally",
        "",
        "Fetch the just-built site and open it in your browser:",
        "",
        "```bash",
        "# this exact build",
        f"great-docs preview --run {run_id}",
        "",
        "# or always the latest build for this PR",
        f"great-docs preview --pr {pr}",
        "```",
        "",
        "<details>",
        "<summary>Auth &amp; tips</summary>",
        "",
        "- **Requires** `great-docs`: `pip install great-docs` (or run via `pipx`/`uvx`).",
        "- **Auth:** run `gh auth login` then add `--use-gh`, or set `GITHUB_TOKEN` "
        "(needs *Actions: read*).",
        "- **Jump to a page:** add `--path reference/index.html`.",
        "- **Latest vs exact:** `--pr <n>` grabs the newest build; `--run <id>` pins this one.",
        "- **Re-download:** `--refresh` ignores the local cache.",
        "",
        "</details>",
    ]
    return "\n".join(lines)


def render_notice_lines(run_id: int | str, pr: int | str | None = None) -> list[str]:
    """Render the workflow-log notice lines.

    The first line is a GitHub Actions ``::notice::`` workflow command, so it
    also surfaces in the run's annotations; the rest are plain log output.
    """
    lines = [
        f"::notice title=Preview these docs locally::great-docs preview --run {run_id}",
        "",
        "  # this exact build:",
        f"  great-docs preview --run {run_id}",
    ]
    if pr is not None:
        lines += [
            "",
            "  # or always the latest build for this PR:",
            f"  great-docs preview --pr {pr}",
        ]
    lines += [
        "",
        "  Don't have it? pip install great-docs (or: pipx run / uvx great-docs preview ...).",
        "  Auth: 'gh auth login' then add --use-gh, or set GITHUB_TOKEN (Actions:read).",
        "  Tip: add --path reference/index.html to jump straight to a page.",
    ]
    return lines


# ---------------------------------------------------------------------------
# Repo / token resolution (CI context)
# ---------------------------------------------------------------------------


def resolve_ci_repo(repo_override: str | None) -> tuple[str, str]:
    """Determine `(owner, repo)` in a CI run.

    Precedence: `--repo` -> `$GITHUB_REPOSITORY` (set by GitHub Actions) -> git remote / project
    config.
    """
    if repo_override:
        github = GithubRepo.parse(repo_override)
        parsed = (github.owner, github.name) if github else _parse_owner_repo(repo_override)
        if parsed:
            return parsed
        raise PreviewError(
            f"Could not parse --repo '{repo_override}'. Expected 'owner/repo' or a GitHub URL."
        )

    env_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in env_repo:
        owner, _, repo = env_repo.partition("/")
        if owner and repo:
            return owner, repo

    from ._pr_preview import resolve_repo

    return resolve_repo(None, None)


def _github_token() -> str:
    token = token_from_env()
    if not token:
        raise PreviewError(
            "No GITHUB_TOKEN/GH_TOKEN in the environment. In GitHub Actions, pass "
            "`env: GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` and grant "
            "`permissions: pull-requests: write`."
        )
    return token


# ---------------------------------------------------------------------------
# Sticky PR comment upsert
# ---------------------------------------------------------------------------


def _find_existing_comment(owner: str, repo: str, pr: int, headers: dict[str, str]) -> int | None:
    """Return the id of our previously-posted comment, following pagination."""
    import requests

    url: str | None = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr}/comments?per_page=100"
    while url:
        resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
        if resp.status_code != 200:
            raise PreviewError(f"Could not list PR comments (HTTP {resp.status_code}).")
        for comment in resp.json():
            if PREVIEW_COMMENT_MARKER in (comment.get("body") or ""):
                return comment.get("id")
        url = resp.links.get("next", {}).get("url")
    return None


def upsert_pr_comment(owner: str, repo: str, pr: int, body: str, token: str) -> str:
    """Create or update the sticky preview comment. Returns "created" or "updated"."""
    import requests

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }

    existing_id = _find_existing_comment(owner, repo, pr, headers)
    try:
        if existing_id is not None:
            resp = requests.patch(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/comments/{existing_id}",
                headers=headers,
                json={"body": body},
                timeout=_TIMEOUT,
            )
            action = "updated"
        else:
            resp = requests.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr}/comments",
                headers=headers,
                json={"body": body},
                timeout=_TIMEOUT,
            )
            action = "created"
    except requests.RequestException as exc:
        raise PreviewError(f"Failed to post PR comment: {exc}") from exc

    if resp.status_code not in (200, 201):
        raise PreviewError(f"Failed to {action[:-1]} PR comment (HTTP {resp.status_code}).")
    return action


def post_preview_comment(
    run_id: int | str,
    pr: int,
    repo_override: str | None = None,
) -> tuple[str, str]:
    """Render and upsert the preview comment. Returns `(action, "owner/repo")`."""
    owner, repo = resolve_ci_repo(repo_override)
    token = _github_token()
    body = render_preview_comment(run_id, pr)
    action = upsert_pr_comment(owner, repo, pr, body, token)
    return action, f"{owner}/{repo}"
