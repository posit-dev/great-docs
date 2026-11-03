"""
Link checks for package sources and documentation pages

The checker collects URLs from Python files and `.qmd` and `.md` pages and probes them over HTTP.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

import requests

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from .._layout import Layout

__all__ = ["check", "find_pages"]

_URL = re.compile(r'https?://[^\s<>"\')\]}`\\]+', re.IGNORECASE)

# Matches `http://example.com{.gd-no-link}` and `` `http://example.com`{.gd-no-link} ``
_NO_LINK = re.compile(r'`?(https?://[^\s<>"\')\]}`\\{]+)`?\{\.gd-no-link\}', re.IGNORECASE)

_HEADERS = {"User-Agent": "great-docs-link-checker/1.0"}

_WORKERS = 16


@dataclass(frozen=True)
class _Probe:
    """The outcome of requesting one URL"""

    kind: Literal["ok", "redirects", "broken"]
    """The result list the URL belongs in"""

    message: str
    """The progress line reported for the URL"""

    status: int | None = None
    """The HTTP status code, or `None` if no response arrived"""

    location: str | None = None
    """The redirect target of a 3xx response"""

    error: str | None = None
    """Why the URL counts as broken"""


def find_pages(layout: Layout, guide_dir: Path | None) -> list[Path]:
    """
    Find the documentation pages to check

    Parameters
    ----------
    layout
        The project's paths.
    guide_dir
        The user guide's source directory, or `None` when the project has none.

    Returns
    -------
    :
        The `.qmd` files followed by the `.md` files under the user guide directory, or under
        the build directory if the project has no user guide directory. An existing
        `README.md` in the package root comes last.
    """
    pages: list[Path] = []
    pages_dir = guide_dir if guide_dir is not None else layout.build_dir
    if pages_dir.exists():
        pages.extend(pages_dir.rglob("*.qmd"))
        pages.extend(pages_dir.rglob("*.md"))

    readme = layout.package_root / "README.md"
    if readme.exists():
        pages.append(readme)
    return pages


def check(
    files: Sequence[Path],
    root: Path,
    *,
    timeout: float,
    ignore_patterns: Sequence[str],
    report: Callable[[str], None],
) -> dict[str, Any]:
    """
    Check the URLs found in files

    URLs in whole-line Python comments and in fenced or inline code in `.qmd` and `.md`
    files are excluded. URLs containing `{`, including f-string placeholders and
    `{.gd-no-link}` markers, are also excluded. Each unique URL that matches no ignore
    pattern is probed with `HEAD` and retried with `GET` on a 405 response. Redirects are
    not followed.

    File reads that raise `OSError` produce a warning through `report`. Requests that raise
    `requests.RequestException` mark the URL as broken. Other errors propagate.

    Parameters
    ----------
    files
        The files to scan, in the order their URLs are reported.
    root
        The project root; file paths in the results are relative to it.
    timeout
        Timeout in seconds for each HTTP request.
    ignore_patterns
        Regular expressions matched case-insensitively against each URL; a matching URL is
        skipped. A pattern that is not a valid regular expression matches literally.
    report
        A callback that receives a line for each unreadable file, the number of URLs found and
        the outcome of each URL.

    Returns
    -------
    :
        A dictionary with the unique URL count in `total`, URL lists in `ok` and
        `skipped`, and each file's URLs in `by_file`. Entries in `redirects` contain `url`,
        `status`, `files` and `location`; entries in `broken` contain `url`, `status`,
        `files` and `error`. URL lists preserve discovery order, and `files` lists
        preserve scan order.
    """
    ignore = [_compile_ignore(pattern) for pattern in ignore_patterns]
    url_to_files: dict[str, list[str]] = {}
    by_file: dict[str, list[str]] = {}

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            report(f"Warning: Could not read {file_path}: {e}")
            continue
        if urls := _urls_in(content, file_path.suffix):
            rel_path = str(file_path.relative_to(root))
            by_file[rel_path] = urls
            for url in urls:
                url_to_files.setdefault(url, []).append(rel_path)

    ok: list[str] = []
    redirects: list[dict[str, Any]] = []
    broken: list[dict[str, Any]] = []
    skipped: list[str] = []

    report(f"\n🔍 Found {len(url_to_files)} unique URLs to check\n")

    skipped_urls = {url for url in url_to_files if any(p.search(url) for p in ignore)}
    urls_to_check = [url for url in url_to_files if url not in skipped_urls]

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        probes = iter(executor.map(partial(_probe, timeout=timeout), urls_to_check))
        for url in url_to_files:
            if url in skipped_urls:
                skipped.append(url)
                report(f"⏭️  Skipped: {url}")
                continue

            probe = next(probes)
            if probe.kind == "ok":
                ok.append(url)
            elif probe.kind == "redirects":
                redirects.append(
                    {
                        "url": url,
                        "status": probe.status,
                        "location": probe.location,
                        "files": url_to_files[url],
                    }
                )
            else:
                broken.append(
                    {
                        "url": url,
                        "status": probe.status,
                        "error": probe.error,
                        "files": url_to_files[url],
                    }
                )
            report(probe.message)

    return {
        "total": len(url_to_files),
        "ok": ok,
        "redirects": redirects,
        "broken": broken,
        "skipped": skipped,
        "by_file": by_file,
    }


def _compile_ignore(pattern: str) -> re.Pattern[str]:
    """
    Compile a case-insensitive ignore pattern

    Parameters
    ----------
    pattern
        The regular expression to compile, or literal text if the expression is invalid.

    Returns
    -------
    :
        A case-insensitive pattern.
    """
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return re.compile(re.escape(pattern), re.IGNORECASE)


def _urls_in(content: str, suffix: str) -> list[str]:
    """
    Extract the URLs to check from a file's text

    Parameters
    ----------
    content
        The text of the file.
    suffix
        The file's suffix, which selects the content excluded from scanning.

    Returns
    -------
    :
        The URLs in the order they appear, without trailing punctuation.
    """
    excluded: set[str] = set()
    if suffix in (".qmd", ".md"):
        excluded = {match.group(1) for match in _NO_LINK.finditer(content)}
        # Read markers before removing example code: a marker may follow a URL in inline code.
        content = re.sub(r"```[^`]*```", "", content, flags=re.DOTALL)
        content = re.sub(r"`[^`]+`", "", content)

    if suffix == ".py":
        # Blank whole-line comments only; a `#` after code may sit inside a string
        content = "\n".join(
            "" if line.lstrip().startswith("#") else line for line in content.split("\n")
        )

    urls: list[str] = []
    for url in _URL.findall(content):
        url = url.rstrip(".,;:!?")
        while url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        if "{" in url or url in excluded:
            continue
        urls.append(url)
    return urls


def _probe(url: str, timeout: float) -> _Probe:
    """
    Request a URL and classify the response

    Parameters
    ----------
    url
        The URL to request.
    timeout
        Timeout in seconds for each request.

    Returns
    -------
    :
        A probe result with `kind` set to `ok` for a 2xx response, `redirects` for a 3xx
        response, or `broken` for any other status or a `requests.RequestException`.
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=False, headers=_HEADERS)
        if response.status_code == 405:
            response = requests.get(
                url, timeout=timeout, allow_redirects=False, headers=_HEADERS, stream=True
            )
            response.close()

        status = response.status_code
        if 200 <= status < 300:
            return _Probe("ok", f"✅ {status} {url}", status)
        if 300 <= status < 400:
            location = response.headers.get("Location", "Unknown")
            return _Probe("redirects", f"↪️  {status} {url} -> {location}", status, location)
        return _Probe("broken", f"❌ {status} {url}", status, error=f"HTTP {status}")
    except requests.exceptions.Timeout:
        return _Probe("broken", f"⏱️  Timeout: {url}", error="Timeout")
    except requests.exceptions.SSLError as e:
        return _Probe("broken", f"🔐 SSL Error: {url}", error=f"SSL Error: {str(e)[:50]}")
    except requests.exceptions.ConnectionError:
        return _Probe("broken", f"🔌 Connection failed: {url}", error="Connection failed")
    except requests.RequestException as e:
        return _Probe("broken", f"⚠️  Error: {url} - {e}", error=str(e)[:100])
