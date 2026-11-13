"""
Repository identities discovered locally from web and clone URLs
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote, unquote, urlsplit

__all__ = ["Repository"]

_HOST_PROVIDERS = {"github.com": "github", "gitlab.com": "gitlab"}
_SCP_URL = re.compile(r"(?:[^/@:]+@)?([^/:]+):(.+)")


@dataclass(frozen=True)
class Repository:
    """A GitHub or GitLab repository and its web instance"""

    provider: Literal["github", "gitlab"]
    """The service that defines repository routes and API behaviour"""

    base_url: str
    """The web instance address, including any installation prefix"""

    namespace: str
    """The owning account or complete sequence of GitLab groups"""

    name: str
    """The project name without a `.git` suffix"""

    @property
    def path(self) -> str:
        """Form the complete project path within the instance"""
        return f"{self.namespace}/{self.name}"

    @property
    def url(self) -> str:
        """Form the repository's web address"""
        return f"{self.base_url}/{quote(self.path, safe='/')}"

    def file_url(
        self, path: str, ref: str, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        """
        Form a file address with an optional source-line anchor

        Parameters
        ----------
        path
            The repository-relative POSIX file path.
        ref
            The branch, tag or commit, escaped as one URL component.
        start_line
            The first source line, or `None` to omit the anchor.
        end_line
            The final source line, or `None` for a single-line anchor.

        Returns
        -------
        :
            The provider's file address with escaped ref and path components.
        """
        route = "-/blob" if self.provider == "gitlab" else "blob"
        url = f"{self.url}/{route}/{quote(ref, safe='')}/{quote(path, safe='/')}"
        if start_line is not None:
            url += f"#L{start_line}"
            if end_line is not None and end_line != start_line:
                separator = "-" if self.provider == "gitlab" else "-L"
                url += f"{separator}{end_line}"
        return url

    @classmethod
    def parse(
        cls,
        url: str | None,
        *,
        provider: str | None = None,
        base_url: str | None = None,
    ) -> Repository | None:
        """
        Read an identity from a web or SSH repository address

        Infer providers only for `github.com` and `gitlab.com`. Other hosts require
        `provider="gitlab"`. An explicit web base can supply an installation prefix
        and a port that differs from the SSH endpoint. HTTP paths include this prefix;
        SSH paths identify the project without an installation prefix. Ignore GitHub
        page suffixes and GitLab page suffixes beginning with `/-/`.

        Parameters
        ----------
        url
            The repository URL, or `None` when none is available.
        provider
            The explicitly configured provider, if any.
        base_url
            The web instance address, including any installation prefix.

        Returns
        -------
        :
            The repository, or `None` for an unknown host or malformed address.

        Raises
        ------
        ValueError
            If explicit provider or base settings contradict the address or name an
            unsupported instance.
        """
        if provider is not None and provider not in ("github", "gitlab"):
            raise ValueError("repo_provider must be 'github', 'gitlab' or null.")
        base = None
        if base_url is not None:
            try:
                base = urlsplit(base_url)
                base.port
            except ValueError as error:
                raise ValueError("repo_base_url must be an HTTP or HTTPS instance URL.") from error
            if (
                base.scheme not in ("http", "https")
                or not base.hostname
                or base.username is not None
                or base.password is not None
                or base.query
                or base.fragment
                or not _valid_path(base.path)
            ):
                raise ValueError("repo_base_url must be an HTTP or HTTPS instance URL.")
            inferred = _HOST_PROVIDERS.get(base.hostname)
            if inferred is not None and provider is not None and inferred != provider:
                raise ValueError("repo_provider does not match the repo_base_url host.")
            provider = provider or inferred
            if provider is None:
                raise ValueError("A custom repo_base_url requires repo_provider: gitlab.")
            if provider == "github" and (base.hostname != "github.com" or base.path.strip("/")):
                raise ValueError("GitHub repositories require the https://github.com base URL.")
            base_url = f"{base.scheme}://{base.netloc}{base.path.rstrip('/')}"
        if not url:
            return None
        value = url.strip()
        if "://" not in value:
            match = _SCP_URL.fullmatch(value)
            if match is None:
                return None
            value = f"ssh://{match.group(1)}/{match.group(2)}"
        try:
            address = urlsplit(value)
            port = address.port
        except ValueError:
            return None
        if (
            address.scheme not in ("http", "https", "ssh")
            or not address.hostname
            or (address.scheme != "ssh" and address.username is not None)
        ):
            return None
        inferred = _HOST_PROVIDERS.get(address.hostname)
        if provider is not None and inferred is not None and provider != inferred:
            raise ValueError("repo_provider does not match the repository host.")
        selected = provider or inferred
        if selected is None:
            return None
        if selected == "github" and address.hostname != "github.com":
            raise ValueError("GitHub repositories require the github.com host.")
        path = address.path.rstrip("/")
        if base is not None:
            if address.hostname != base.hostname or (
                address.scheme != "ssh"
                and (address.scheme != base.scheme or address.port != base.port)
            ):
                raise ValueError("repo_base_url does not match the repository origin.")
            if address.scheme != "ssh":
                prefix = base.path.rstrip("/")
                if prefix and not path.startswith(prefix + "/"):
                    raise ValueError("The repository URL is outside repo_base_url's path prefix.")
                path = path.removeprefix(prefix)
        parts = path.strip("/").split("/")
        if selected == "github":
            parts = parts[:2]
        elif "-" in parts:
            parts = parts[: parts.index("-")]
        if not _valid_path("/".join(parts)):
            return None
        parts = [unquote(part) for part in parts]
        if len(parts) < 2:
            return None
        parts[-1] = parts[-1].removesuffix(".git")
        if parts[-1] in ("", ".", ".."):
            return None
        if base_url is None and selected == "github":
            base_url = "https://github.com"
        if base_url is None:
            host = address.hostname
            if ":" in host:
                host = f"[{host}]"
            web_port = (
                f":{port}"
                if port is not None and not (address.scheme == "ssh" and port == 22)
                else ""
            )
            scheme = address.scheme if address.scheme != "ssh" else "https"
            base_url = f"{scheme}://{host}{web_port}"
        return cls(
            "github" if selected == "github" else "gitlab",
            base_url,
            "/".join(parts[:-1]),
            parts[-1],
        )


def _valid_path(path: str) -> bool:
    """
    Check that a URL path contains unambiguous repository components

    Parameters
    ----------
    path
        The escaped URL path.

    Returns
    -------
    :
        Whether components contain no traversal, separators or whitespace.
    """
    return (
        all(
            part not in ("", ".", "..")
            and not any(character.isspace() or character in "/\\" for character in part)
            for part in (unquote(component) for component in path.strip("/").split("/"))
        )
        if path.strip("/")
        else True
    )
