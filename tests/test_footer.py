from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from great_docs._website import footer
from tests.support import mock_config

_GIT = "great_docs._website.footer.subprocess.run"


def _register(metadata: dict[str, Any] | None = None, **settings: Any) -> dict[str, Any]:
    quarto_config: dict[str, Any] = {"website": {}, "format": {"html": {}}}
    config = mock_config(lang="en", **settings)
    footer.register(quarto_config, config, metadata or {})
    return quarto_config


def _git(*results: subprocess.CompletedProcess[str] | BaseException) -> Any:
    return patch(_GIT, side_effect=list(results))


def _done(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["git"], returncode, stdout=stdout, stderr="")


class TestCredits:
    def test_lists_authors_then_new_maintainers_then_configured_authors(self):
        metadata = {
            "authors": [{"name": "Ann Lee"}, "Bob"],
            "maintainers": ["Bob", {"name": "Cy"}, {"email": "x@example.com"}],
        }
        authors = [{"name": "Cy"}, {"name": "Di", "homepage": "https://di.example"}, "Ed"]

        center = _register(metadata, authors=authors)["website"]["page-footer"]["center"]

        assert center == (
            "Developed by <strong>Ann&nbsp;Lee</strong>, <strong>Bob</strong>, "
            '<strong>Cy</strong>, and <a href="https://di.example"><strong>Di</strong></a>.'
        )

    def test_joins_two_names_without_a_comma(self):
        metadata = {"authors": ["Ann", "Bob"]}

        center = _register(metadata)["website"]["page-footer"]["center"]

        assert center == "Developed by <strong>Ann</strong> and <strong>Bob</strong>."

    def test_names_the_funder_after_the_developers(self):
        funding = {"name": "ACME Foundation", "homepage": "https://acme.org"}

        center = _register({"authors": ["Ann"]}, funding=funding)["website"]["page-footer"][
            "center"
        ]

        assert center == (
            "Developed by <strong>Ann</strong>. Supported by "
            '<a href="https://acme.org"><strong>ACME&nbsp;Foundation</strong></a>.'
        )

    def test_credits_the_funder_alone_without_developers(self):
        center = _register(funding={"name": "ACME"})["website"]["page-footer"]["center"]

        assert center == "Supported by <strong>ACME</strong>."

    def test_leaves_the_footer_out_without_developers_or_funder(self):
        assert "page-footer" not in _register()["website"]

    def test_keeps_an_existing_footer(self):
        quarto_config: dict[str, Any] = {"website": {"page-footer": {"left": "Mine"}}}

        footer.register(quarto_config, mock_config(lang="en"), {"authors": ["Ann"]})

        assert quarto_config["website"]["page-footer"] == {"left": "Mine"}


class TestAttribution:
    def test_appends_the_credit_once(self):
        quarto_config: dict[str, Any] = {"website": {}}
        config = mock_config(lang="en", attribution=True)

        with _git(_done("", returncode=1), _done("", returncode=1)):
            footer.register(quarto_config, config, {"authors": ["Ann"]})
            footer.register(quarto_config, config, {"authors": ["Ann"]})

        assert quarto_config["website"]["page-footer"]["center"] == (
            "Developed by <strong>Ann</strong>.<br>"
            "Site created with <strong>Great&nbsp;Docs</strong>."
        )

    def test_links_the_commit_of_a_great_docs_checkout(self):
        with _git(_done("git@github.com:posit-dev/great-docs.git\n"), _done("abc1234\n")):
            center = _register(attribution=True)["website"]["page-footer"]["center"]

        assert center == (
            "Site created with <strong>Great&nbsp;Docs</strong> (<a href="
            '"https://github.com/posit-dev/great-docs/commit/abc1234">abc1234</a>).'
        )

    @pytest.mark.parametrize(
        "results",
        [
            [_done("https://github.com/someone/project.git\n")],
            [FileNotFoundError("git")],
            [subprocess.TimeoutExpired("git", 5)],
            [_done("great-docs"), _done("", returncode=128)],
        ],
        ids=["other-repository", "git-missing", "timeout", "no-head"],
    )
    def test_omits_the_commit_when_git_does_not_name_one(
        self, results: list[subprocess.CompletedProcess[str] | BaseException]
    ):
        with _git(*results):
            center = _register(attribution=True)["website"]["page-footer"]["center"]

        assert center == "Site created with <strong>Great&nbsp;Docs</strong>."


class TestPositBadge:
    def test_adds_the_badge_once_for_posit(self):
        quarto_config: dict[str, Any] = {"website": {}}
        config = mock_config(lang="en", funding={"name": "Posit Software, PBC"})

        footer.register(quarto_config, config, {})
        footer.register(quarto_config, config, {})

        headers = quarto_config["format"]["html"]["include-in-header"]
        assert [h for h in headers if "supported-by-posit" in str(h)] == headers
        assert len(headers) == 1

    def test_matches_posit_as_a_whole_word(self):
        quarto_config = _register(funding={"name": "Positronic Labs"})

        assert "include-in-header" not in quarto_config["format"]["html"]
