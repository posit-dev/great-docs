"""
GitHub workflow artifact previews
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from great_docs._build import preview_artifacts as pa
from great_docs._build.repo_hosts import github_preview as pp


def test_parse_owner_repo():
    assert pp._parse_owner_repo("posit-dev/great-docs") == ("posit-dev", "great-docs")
    assert pp._parse_owner_repo("posit-dev/great-docs.git") == ("posit-dev", "great-docs")
    assert pp._parse_owner_repo("nope") is None


def test_resolve_repo_override_variants():
    assert pp.resolve_repo(None, "posit-dev/great-docs") == ("posit-dev", "great-docs")
    assert pp.resolve_repo(None, "https://github.com/posit-dev/great-docs") == (
        "posit-dev",
        "great-docs",
    )


def test_resolve_repo_override_invalid():
    with pytest.raises(pa.PreviewError):
        pp.resolve_repo(None, "not a repo!!")


def test_resolve_repo_from_git_remote(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: ("posit-dev", "great-docs"))
    assert pp.resolve_repo("/somewhere", None) == ("posit-dev", "great-docs")


def test_resolve_repo_unresolvable(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: None)
    monkeypatch.setattr(pp, "_config_repo", lambda p: None)
    with pytest.raises(pa.PreviewError):
        pp.resolve_repo(None, None)


def test_resolve_token_from_env(monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "envtok")
    token, source = pp.resolve_token(None, None)
    assert token == "envtok"
    assert source == "GITHUB_TOKEN"


def test_resolve_token_explicit_env_file_wins(monkeypatch, tmp_path):
    # Even with an environment token present, an explicit --env-file takes precedence.
    monkeypatch.setenv("GITHUB_TOKEN", "envtok")
    env_file = tmp_path / "secrets.env"
    env_file.write_text("GITHUB_TOKEN=filetok\n")
    token, source = pp.resolve_token(None, str(env_file))
    assert token == "filetok"
    assert str(env_file) in source


def test_resolve_token_autodetect_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    (tmp_path / ".env").write_text("GH_TOKEN=dottok\n")
    token, source = pp.resolve_token(tmp_path, None)
    assert token == "dottok"


def test_resolve_token_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    monkeypatch.setattr(pp, "find_dotenv", lambda usecwd=True: "")
    # No env, no gh, no discoverable .env in an isolated dir.
    token, source = pp.resolve_token(None, None)
    # A stray .env in the repo working dir shouldn't matter for this assertion's intent;
    # the important behavior is that missing env + no gh yields no env-based token.
    assert source != "GITHUB_TOKEN"


class FakeClient:
    """A stand-in for GitHubClient that returns canned JSON keyed by path substring."""

    def __init__(self, responses, owner="posit-dev", repo="great-docs"):
        self.owner = owner
        self.repo = repo
        self._responses = responses
        self.calls: list[str] = []

    def get_json(self, path, params=None):
        self.calls.append(path)
        for key, val in self._responses.items():
            if key in path:
                return val
        raise AssertionError(f"unexpected path: {path}")


def test_pick_run_prefers_success_then_newest():
    runs = {
        "workflow_runs": [
            {"id": 1, "name": "CI Docs", "created_at": "2026-01-01", "conclusion": "failure"},
            {"id": 2, "name": "CI Docs", "created_at": "2026-01-03", "conclusion": "success"},
            {"id": 3, "name": "CI Docs", "created_at": "2026-01-02", "conclusion": "success"},
            {"id": 4, "name": "Other", "created_at": "2026-01-09", "conclusion": "success"},
        ]
    }
    info = pp._pick_run(runs, "CI Docs")
    assert info.run_id == 2  # newest successful CI Docs run


def test_pick_run_falls_back_to_newest_when_none_succeeded():
    runs = {
        "workflow_runs": [
            {"id": 1, "name": "CI Docs", "created_at": "2026-01-01", "conclusion": "failure"},
            {"id": 2, "name": "CI Docs", "created_at": "2026-01-05", "conclusion": "failure"},
        ]
    }
    info = pp._pick_run(runs, "CI Docs")
    assert info.run_id == 2
    assert info.conclusion == "failure"


def test_resolve_run_direct_id():
    info = pp.resolve_run(FakeClient({}), pr=None, run=18273645521, branch=None)
    assert info.run_id == 18273645521


def test_resolve_run_by_pr():
    client = FakeClient(
        {
            "pulls/302": {
                "head": {"sha": "a1b2c3d4", "repo": {"full_name": "posit-dev/great-docs"}},
                "base": {"repo": {"full_name": "posit-dev/great-docs"}},
            },
            "actions/runs": {
                "workflow_runs": [
                    {
                        "id": 99,
                        "name": "CI Docs",
                        "created_at": "2026-01-01",
                        "conclusion": "success",
                    }
                ]
            },
        }
    )
    info = pp.resolve_run(client, pr=302, run=None, branch=None)
    assert info.run_id == 99
    assert info.head_sha == "a1b2c3d4"
    assert info.head_repo == "posit-dev/great-docs"


def test_resolve_run_by_pr_no_run(monkeypatch):
    client = FakeClient(
        {
            "pulls/5": {"head": {"sha": "deadbeef"}, "base": {}},
            "actions/runs": {"workflow_runs": []},
        }
    )
    with pytest.raises(pa.PreviewError, match="No 'CI Docs' run"):
        pp.resolve_run(client, pr=5, run=None, branch=None)


def test_choose_artifact_exact_match():
    arts = [
        {"name": "build-timings", "created_at": "2026-01-01"},
        {"name": "docs-html", "created_at": "2026-01-01"},
    ]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "docs-html"


def test_choose_artifact_single_fallback(capsys):
    arts = [{"name": "site", "created_at": "2026-01-01"}]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "site"
    assert "using the only one" in capsys.readouterr().out


def test_choose_artifact_multiple_non_interactive_newest():
    arts = [
        {"name": "docs-html-a", "created_at": "2026-01-01"},
        {"name": "docs-html-b", "created_at": "2026-01-09"},
    ]
    chosen = pp.choose_artifact(arts, name="docs-html", interactive=False)
    assert chosen["name"] == "docs-html-b"


def test_choose_artifact_none_raises():
    with pytest.raises(pa.PreviewError, match="no artifacts"):
        pp.choose_artifact([], name="docs-html", interactive=False)


class FakeDownloadClient:
    def __init__(self):
        self.owner = "posit-dev"
        self.repo = "great-docs"
        self.downloads = 0

    def download_artifact(self, run_id, artifact, dest):
        self.downloads += 1
        (dest / "index.html").write_text("<html>built</html>")


def test_cache_dir_for_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    got = pp.cache_dir_for("posit-dev", "great-docs", 42, "docs-html")
    assert (
        got == tmp_path / "great-docs" / "pr-preview" / "posit-dev-great-docs" / "42" / "docs-html"
    )


def test_download_and_extract_caches(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    client = FakeDownloadClient()
    art = {"name": "docs-html"}

    root1 = pp.download_and_extract(client, run_id=42, artifact=art, refresh=False)
    assert (root1 / "index.html").is_file()
    assert client.downloads == 1

    # Second call hits the cache (no new download).
    root2 = pp.download_and_extract(client, run_id=42, artifact=art, refresh=False)
    assert root2 == root1
    assert client.downloads == 1
    assert "cached" in capsys.readouterr().out

    # --refresh forces a re-download.
    pp.download_and_extract(client, run_id=42, artifact=art, refresh=True)
    assert client.downloads == 2


def test_download_and_extract_missing_index_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    class NoIndexClient(FakeDownloadClient):
        def download_artifact(self, run_id, artifact, dest):
            (dest / "notes.txt").write_text("no site here")

    with pytest.raises(pa.PreviewError, match="index.html"):
        pp.download_and_extract(NoIndexClient(), run_id=7, artifact={"name": "x"}, refresh=False)


def test_preview_pr_requires_auth(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: (None, None))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    with pytest.raises(pa.PreviewError, match="No GitHub credentials"):
        pp.preview_pr(None, run=123)


def test_git_remote_repo_success(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "https://github.com/posit-dev/great-docs.git\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp._git_remote_repo(tmp_path)
    assert result == ("posit-dev", "great-docs")


def test_git_remote_repo_nonzero_returncode(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 128)
        r.stdout = ""
        r.stderr = "fatal: not a git repository"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._git_remote_repo(tmp_path) is None


def test_git_remote_repo_os_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._git_remote_repo(tmp_path) is None


def test_git_remote_repo_none_path(monkeypatch):
    import subprocess as sp

    captured_kwargs = {}

    def fake_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "https://github.com/o/r\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    result = pp._git_remote_repo(None)
    assert result == ("o", "r")
    assert captured_kwargs["cwd"] is None


def test_config_repo_reads_the_project_urls(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\n\n[project.urls]\n'
        'Repository = "https://github.com/posit-dev/great-docs"\n',
        encoding="utf-8",
    )
    assert pp._config_repo(tmp_path) == ("posit-dev", "great-docs")


def test_config_repo_returns_none_for_an_ambiguous_layout(tmp_path: Path):
    # Configuration files in the root and in `docs/` make the layout unreadable.
    (tmp_path / "great-docs.yml").write_text("repo: https://github.com/a/b\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "great-docs.yml").write_text("", encoding="utf-8")
    assert pp._config_repo(tmp_path) is None


def test_config_repo_returns_none_without_a_github_repository(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    assert pp._config_repo(tmp_path) is None


def test_gh_token_success(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "ghp_abc123\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") == "ghp_abc123"


def test_gh_token_not_logged_in(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "not logged in"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


def test_gh_token_empty_output(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "\n"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


def test_gh_token_os_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    assert pp._gh_token("/usr/bin/gh") is None


def test_token_from_dotenv_bad_file(tmp_path):
    bad = tmp_path / "nonexistent.env"
    assert pp._token_from_dotenv(bad) is None


def test_token_from_dotenv_gh_token(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GH_TOKEN=ghtok123\n")
    assert pp._token_from_dotenv(env) == "ghtok123"


def test_resolve_token_from_gh_auth(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: "ghtok_from_cli")
    token, source = pp.resolve_token(None, None)
    assert token == "ghtok_from_cli"
    assert source == "gh auth token"


def test_resolve_token_find_dotenv_path(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=found_it\n")
    monkeypatch.setattr(pp, "find_dotenv", lambda usecwd=True: str(env_file))
    token, source = pp.resolve_token(None, None)
    assert token == "found_it"


def test_resolve_token_skips_duplicates(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    env_file = tmp_path / ".env"
    env_file.write_text("GITHUB_TOKEN=tok\n")
    monkeypatch.setattr(pp, "find_dotenv", lambda usecwd=True: str(env_file))
    token, source = pp.resolve_token(tmp_path, None)
    assert token == "tok"


class _FakeRequestsResponse:
    def __init__(self, status_code, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        return self._json


def test_requests_get_success(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(200, {"runs": []})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    result = client._requests_get("repos/posit-dev/great-docs/actions/runs", None)
    assert result == {"runs": []}


def test_requests_get_404(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(404)

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pa.PreviewError, match="404"):
        client._requests_get("repos/posit-dev/great-docs/pulls/999", None)


def test_requests_get_rate_limited(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(403, headers={"X-RateLimit-Remaining": "0"})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pa.PreviewError, match="rate limit"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_401_no_rate_limit(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(401, headers={})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pa.PreviewError, match="denied"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_500(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(500)

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pa.PreviewError, match="500"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_network_error(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")

    class FakeRequestException(Exception):
        pass

    fake_requests.RequestException = FakeRequestException

    def fake_get(url, headers=None, params=None, timeout=None):
        raise FakeRequestException("Connection reset")

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token="tok123")
    with pytest.raises(pa.PreviewError, match="request failed"):
        client._requests_get("repos/posit-dev/great-docs/actions/runs", None)


def test_requests_get_no_token(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception
    captured_headers = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured_headers.update(headers or {})
        return _FakeRequestsResponse(200, {"ok": True})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("posit-dev", "great-docs", token=None)
    client._requests_get("repos/posit-dev/great-docs/actions/runs", None)
    assert "Authorization" not in captured_headers


def test_gh_api_success(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"total_count": 1}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    result = client._gh_api("repos/posit-dev/great-docs/actions/runs", {"per_page": 100})
    assert result == {"total_count": 1}


def test_gh_api_no_params(monkeypatch):
    import subprocess as sp

    captured_cmd = []

    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"ok": true}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client._gh_api("repos/posit-dev/great-docs/pulls/5", None)
    assert "?" not in captured_cmd[2]


def test_gh_api_nonzero_returncode(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "HTTP 404"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pa.PreviewError, match="failed"):
        client._gh_api("repos/posit-dev/great-docs/pulls/999", None)


def test_gh_api_invalid_json(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = "not json at all"
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pa.PreviewError, match="parse"):
        client._gh_api("repos/posit-dev/great-docs/actions/runs", None)


def test_gh_api_os_error(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("gh not found")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pa.PreviewError, match="failed"):
        client._gh_api("repos/posit-dev/great-docs/actions/runs", None)


def test_gh_download_success(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client._gh_download(42, {"name": "docs-html"}, tmp_path)


def test_gh_download_failure(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 1)
        r.stdout = ""
        r.stderr = "error downloading artifact"
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pa.PreviewError, match="gh run download"):
        client._gh_download(42, {"name": "docs-html"}, tmp_path)


def test_gh_download_os_error(monkeypatch, tmp_path):
    def fake_run(cmd, **kwargs):
        raise OSError("no gh")

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    with pytest.raises(pa.PreviewError, match="gh run download"):
        client._gh_download(42, {"name": "docs-html"}, tmp_path)


def test_requests_download_success(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_content = b""
    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html>hi</html>")
    zip_content = zip_buf.read_bytes()

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    client._requests_download({"id": 1, "archive_download_url": "https://x"}, dest)
    assert (dest / "index.html").is_file()


def test_requests_download_410_expired(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    class FakeResp:
        status_code = 410
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pa.PreviewError, match="expired"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_bad_status(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    class FakeResp:
        status_code = 500
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pa.PreviewError, match="500"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_resume_206(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html>hi</html>")
    zip_content = zip_buf.read_bytes()
    first_half = zip_content[: len(zip_content) // 2]
    second_half = zip_content[len(zip_content) // 2 :]

    call_count = [0]

    class FakeResp200:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield first_half
            raise fake_requests.RequestException("dropped")

    class FakeResp206:
        status_code = 206
        headers = {"Content-Length": str(len(second_half))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield second_half

    def fake_get(url, headers=None, timeout=None, stream=False):
        call_count[0] += 1
        if call_count[0] == 1:
            return FakeResp200()
        return FakeResp206()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )
    monkeypatch.setattr(pp, "_DOWNLOAD_RETRIES", 3)
    # Patch time.sleep to not actually wait
    monkeypatch.setattr("time.sleep", lambda s: None)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    client._requests_download({"id": 1}, dest)
    assert (dest / "index.html").is_file()


def test_requests_download_all_retries_exhausted(monkeypatch, tmp_path):
    import types

    fake_requests = types.ModuleType("requests")

    class FakeRequestException(Exception):
        pass

    fake_requests.RequestException = FakeRequestException

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": "100"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield b"x" * 10
            raise FakeRequestException("timeout")

    def fake_get(url, headers=None, timeout=None, stream=False):
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )
    monkeypatch.setattr(pp, "_DOWNLOAD_RETRIES", 2)
    monkeypatch.setattr("time.sleep", lambda s: None)

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok")
    with pytest.raises(pa.PreviewError, match="failed after"):
        client._requests_download({"id": 1}, dest)


def test_requests_download_no_token_no_auth_header(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html></html>")
    zip_content = zip_buf.read_bytes()

    captured_headers = {}

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    def fake_get(url, headers=None, timeout=None, stream=False):
        captured_headers.update(headers or {})
        return FakeResp()

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    dest.mkdir()
    client = pp.GitHubClient("posit-dev", "great-docs", token=None)
    client._requests_download({"id": 1, "archive_download_url": "https://x"}, dest)
    assert "Authorization" not in captured_headers


def test_resolve_run_invalid_run_id():
    with pytest.raises(pa.PreviewError, match="Invalid --run"):
        pp.resolve_run(FakeClient({}), pr=None, run="abc", branch=None)


def test_resolve_run_no_head_sha():
    client = FakeClient(
        {
            "pulls/10": {"head": {"sha": None}, "base": {}},
            "actions/runs": {"workflow_runs": []},
        }
    )
    with pytest.raises(pa.PreviewError, match="head commit"):
        pp.resolve_run(client, pr=10, run=None, branch=None)


def test_resolve_run_by_branch():
    client = FakeClient(
        {
            "actions/runs": {
                "workflow_runs": [
                    {
                        "id": 77,
                        "name": "CI Docs",
                        "created_at": "2026-02-01",
                        "conclusion": "success",
                    }
                ]
            },
        }
    )
    info = pp.resolve_run(client, pr=None, run=None, branch="feature-x")
    assert info.run_id == 77


def test_resolve_run_by_branch_no_run():
    client = FakeClient({"actions/runs": {"workflow_runs": []}})
    with pytest.raises(pa.PreviewError, match="No 'CI Docs' run found for branch"):
        pp.resolve_run(client, pr=None, run=None, branch="feature-x")


def test_resolve_run_no_source():
    with pytest.raises(pa.PreviewError, match="Specify one of"):
        pp.resolve_run(FakeClient({}), pr=None, run=None, branch=None)


def test_find_artifacts_non_dict_response():
    class BadClient:
        owner = "posit-dev"
        repo = "great-docs"

        def get_json(self, path, params=None):
            return []  # non-dict

    assert pp.find_artifacts(BadClient(), 42, "docs-html") == []


def test_find_artifacts_no_artifacts_key():
    class EmptyClient:
        owner = "posit-dev"
        repo = "great-docs"

        def get_json(self, path, params=None):
            return {}

    assert pp.find_artifacts(EmptyClient(), 42, "docs-html") == []


def test_choose_artifact_interactive_prompt(monkeypatch):
    import click

    arts = [
        {"name": "site-a", "created_at": "2026-01-01", "size_in_bytes": 5_000_000},
        {"name": "site-b", "created_at": "2026-01-02", "size_in_bytes": 10_000_000},
    ]
    monkeypatch.setattr(click, "prompt", lambda *a, **kw: 1)
    chosen = pp.choose_artifact(arts, name="nope", interactive=True)
    # Sorted by created_at descending, so index 1 = site-b (newest first)
    assert chosen["name"] == "site-b"


def test_prompt_artifact_selects_second(monkeypatch):
    import click

    arts = [
        {"name": "site-a", "created_at": "2026-01-01", "size_in_bytes": 5_000_000},
        {"name": "site-b", "created_at": "2026-01-02", "size_in_bytes": 10_000_000},
    ]
    monkeypatch.setattr(click, "prompt", lambda *a, **kw: 2)
    chosen = pp._prompt_artifact(arts)
    # Second in descending order is site-a
    assert chosen["name"] == "site-a"


def test_print_run_line_full(capsys):
    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_sha = "abc1234567890"
    pp._print_run_line(info, pr=5, branch=None)
    out = capsys.readouterr().out
    assert "PR #5" in out
    assert "commit abc1234" in out
    assert "run 42" in out
    assert "(success)" in out


def test_print_run_line_branch_no_sha(capsys):
    info = pp.RunInfo(run_id=100, conclusion=None)
    pp._print_run_line(info, pr=None, branch="main")
    out = capsys.readouterr().out
    assert "branch main" in out
    assert "run 100" in out
    assert "()" not in out  # no conclusion shown


def test_preview_pr_use_gh_not_installed(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)
    with pytest.raises(pa.PreviewError, match="not installed"):
        pp.preview_pr(None, run=123, use_gh=True)


def test_preview_pr_use_gh_not_logged_in(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: None)
    with pytest.raises(pa.PreviewError, match="not logged in"):
        pp.preview_pr(None, run=123, use_gh=True)


def test_preview_pr_fork_warning(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_sha = "abc123"
    info.head_repo = "contributor/great-docs"
    info.base_repo = "posit-dev/great-docs"
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 1000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 1000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, pr=5, open_browser=False)
    out = capsys.readouterr().out
    assert "fork" in out


def test_preview_pr_non_success_warning(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="failure")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 1000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 1000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, run=42, open_browser=False)
    out = capsys.readouterr().out
    assert "did not succeed" in out


def test_preview_pr_expired_artifact(monkeypatch):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "resolve_token", lambda p, e: ("tok", "env"))
    monkeypatch.setattr(pp, "_gh_path", lambda: None)

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp,
        "find_artifacts",
        lambda c, r, n: [{"name": "docs-html", "expired": True, "size_in_bytes": 0}],
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "expired": True, "size_in_bytes": 0},
    )

    with pytest.raises(pa.PreviewError, match="expired"):
        pp.preview_pr(None, run=42, open_browser=False)


def test_preview_pr_use_gh_success(monkeypatch, capsys):
    monkeypatch.setattr(pp, "resolve_repo", lambda p, r: ("posit-dev", "great-docs"))
    monkeypatch.setattr(pp, "_gh_path", lambda: "/usr/bin/gh")
    monkeypatch.setattr(pp, "_gh_token", lambda gh: "ghtok")

    info = pp.RunInfo(run_id=42, conclusion="success")
    info.head_repo = None
    info.base_repo = None
    monkeypatch.setattr(pp, "resolve_run", lambda client, **kw: info)
    monkeypatch.setattr(
        pp, "find_artifacts", lambda c, r, n: [{"name": "docs-html", "size_in_bytes": 5000}]
    )
    monkeypatch.setattr(
        pp,
        "choose_artifact",
        lambda arts, name, interactive: {"name": "docs-html", "size_in_bytes": 5000},
    )
    monkeypatch.setattr(
        pp,
        "download_and_extract",
        lambda c, run_id, artifact, refresh: Path("/tmp/fake"),
    )

    monkeypatch.setattr(pp.serve, "site", lambda root, **kwargs: None)

    pp.preview_pr(None, run=42, use_gh=True, open_browser=False)
    out = capsys.readouterr().out
    assert "gh CLI" in out


def test_github_client_init():
    client = pp.GitHubClient("owner", "repo", token="tok", use_gh=True, gh="/bin/gh")
    assert client.owner == "owner"
    assert client.repo == "repo"
    assert client.token == "tok"
    assert client.use_gh is True
    assert client.gh == "/bin/gh"


def test_github_client_get_json_dispatches_gh(monkeypatch):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = '{"dispatched": true}'
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    client = pp.GitHubClient("o", "r", use_gh=True, gh="/bin/gh")
    assert client.get_json("repos/o/r/pulls/1") == {"dispatched": True}


def test_github_client_get_json_dispatches_requests(monkeypatch):
    import types

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeRequestsResponse(200, {"dispatched": True})

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    client = pp.GitHubClient("o", "r", token="tok", use_gh=False)
    assert client.get_json("repos/o/r/pulls/1") == {"dispatched": True}


def test_download_artifact_dispatches_gh(monkeypatch, tmp_path):
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        r = sp.CompletedProcess(cmd, 0)
        r.stdout = ""
        r.stderr = ""
        return r

    monkeypatch.setattr(pp.subprocess, "run", fake_run)
    dest = tmp_path / "out"
    client = pp.GitHubClient("posit-dev", "great-docs", use_gh=True, gh="/usr/bin/gh")
    client.download_artifact(42, {"name": "docs-html"}, dest)
    assert dest.exists()


def test_download_artifact_dispatches_requests(monkeypatch, tmp_path):
    import types
    import zipfile as zf

    fake_requests = types.ModuleType("requests")
    fake_requests.RequestException = Exception

    zip_buf = tmp_path / "_make.zip"
    with zf.ZipFile(zip_buf, "w") as z:
        z.writestr("index.html", "<html></html>")
    zip_content = zip_buf.read_bytes()

    class FakeResp:
        status_code = 200
        headers = {"Content-Length": str(len(zip_content))}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def iter_content(self, chunk_size=None):
            yield zip_content

    fake_requests.get = lambda url, headers=None, timeout=None, stream=False: FakeResp()
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(
        pp.sys,
        "stderr",
        type(
            "F",
            (),
            {"isatty": lambda s: False, "write": lambda s, x: None, "flush": lambda s: None},
        )(),
    )

    dest = tmp_path / "out"
    client = pp.GitHubClient("posit-dev", "great-docs", token="tok", use_gh=False)
    client.download_artifact(42, {"id": 1, "archive_download_url": "https://x"}, dest)
    assert (dest / "index.html").is_file()


def test_token_from_dotenv_undecodable_file(tmp_path):
    """Ignore a token file that cannot be decoded"""
    env = tmp_path / ".env"
    env.write_bytes(b"GITHUB_TOKEN=\xff\xfe\x00\n")
    assert pp._token_from_dotenv(env) is None


def test_token_from_dotenv_bug_propagates(monkeypatch, tmp_path):
    """Propagate an unexpected error while reading a token file"""

    def broken_dotenv_values(path):
        raise TypeError("bug")

    monkeypatch.setattr(pp, "dotenv_values", broken_dotenv_values)
    with pytest.raises(TypeError):
        pp._token_from_dotenv(tmp_path / ".env")


def test_resolve_repo_from_config(monkeypatch):
    monkeypatch.setattr(pp, "_git_remote_repo", lambda p: None)
    monkeypatch.setattr(pp, "_config_repo", lambda p: ("owner", "repo"))
    assert pp.resolve_repo("/path", None) == ("owner", "repo")


def test_gh_path_returns_path(monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: "/usr/bin/gh")
    assert pp._gh_path() == "/usr/bin/gh"


def test_gh_path_returns_none(monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: None)
    assert pp._gh_path() is None


def test_resolve_token_skips_nonexistent_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(pp.shutil, "which", lambda cmd: None)
    nonexistent = tmp_path / ".env"
    token, source = pp.resolve_token(project_path=str(tmp_path), env_file=None)
    assert token is None


@pytest.mark.parametrize(
    "url", ["https://gitlab.com/group/project", "git@gitlab.com:group/project.git"]
)
def test_gitlab_preview_override_reports_unsupported(url: str) -> None:
    with pytest.raises(pa.PreviewError, match="Use GitLab --mr"):
        pp.resolve_repo(None, url)


def test_configured_custom_gitlab_preview_reports_unsupported(tmp_path: Path) -> None:
    (tmp_path / "great-docs.yml").write_text(
        "repo: https://code.example.org/gitlab/group/project\n"
        "repo_provider: gitlab\nrepo_base_url: https://code.example.org/gitlab\n",
        encoding="utf-8",
    )
    with pytest.raises(pa.PreviewError, match="Use GitLab --mr"):
        pp._config_repo(tmp_path)


def test_gitlab_remote_does_not_fall_back_to_github(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        pp.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="git@gitlab.com:g/p.git"),
    )
    monkeypatch.setattr(
        pp, "_config_repo", lambda path: pytest.fail("must not select another repository")
    )
    with pytest.raises(pa.PreviewError, match="Use GitLab --mr"):
        pp.resolve_repo(None, None)
