from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from great_docs import GreatDocs
from great_docs._build import quarto

# ---------------------------------------------------------------------------
# Page progress in Quarto output
# ---------------------------------------------------------------------------


class TestParseProgress:
    """Page progress parsed from Quarto output"""

    def test_basic_line(self):
        assert quarto.parse_progress("[  1/42] user-guide/overview.html") == quarto.Progress(
            1, 42, "user-guide/overview.html"
        )

    def test_double_digit(self):
        assert quarto.parse_progress("[ 12/42] reference/GT.html") == quarto.Progress(
            12, 42, "reference/GT.html"
        )

    def test_no_leading_space(self):
        assert quarto.parse_progress("[3/5] recipes/freeze-demo.html") == quarto.Progress(
            3, 5, "recipes/freeze-demo.html"
        )

    def test_non_matching_line(self):
        assert quarto.parse_progress("WARN: something went wrong") is None

    def test_line_with_ansi(self):
        # Quarto sometimes emits ANSI color codes around the line
        line = "\x1b[32m[  5/10] user-guide/config.html\x1b[0m"
        assert quarto.parse_progress(line) == quarto.Progress(5, 10, "user-guide/config.html")


# ---------------------------------------------------------------------------
# _write_build_timing
# ---------------------------------------------------------------------------


class TestWriteBuildTiming:
    """Test the _write_build_timing method writes correct JSON."""

    def _make_gd(self, tmp_path: Path) -> GreatDocs:
        """Create a project with its resolved build and deployment paths"""
        (tmp_path / "great-docs.yml").write_text("name: test-pkg\n")
        return GreatDocs(project_path=str(tmp_path))

    def test_single_version_flat(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        timings = [
            {"page": "user-guide/overview.html", "seconds": 1.2},
            {"page": "user-guide/benchmarks.html", "seconds": 28.4},
            {"page": "reference/GT.html", "seconds": 2.1},
        ]

        result = gd._write_build_timing(page_timings=timings)
        assert result is not None
        assert result.name == "build-timings.json"

        data = json.loads(result.read_text())
        assert "build_time" in data
        assert data["total_seconds"] == pytest.approx(31.7, abs=0.01)
        # Pages should be sorted by seconds descending
        assert data["pages"][0]["page"] == "user-guide/benchmarks.html"
        assert data["pages"][-1]["page"] == "user-guide/overview.html"
        assert len(data["pages"]) == 3
        # No versions key for single-version
        assert "versions" not in data

    def test_multi_version(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        timings_by_version = {
            "0.10": [
                {"page": "user-guide/overview.html", "seconds": 1.2},
                {"page": "user-guide/benchmarks.html", "seconds": 28.4},
            ],
            "0.9": [
                {"page": "user-guide/overview.html", "seconds": 0.9},
                {"page": "reference/GT.html", "seconds": 1.8},
            ],
        }

        result = gd._write_build_timing(timings_by_version=timings_by_version)
        assert result is not None

        data = json.loads(result.read_text())
        assert "build_time" in data
        assert data["total_seconds"] == pytest.approx(32.3, abs=0.01)
        assert "versions" in data
        assert set(data["versions"].keys()) == {"0.10", "0.9"}

        v010 = data["versions"]["0.10"]
        assert v010["seconds"] == pytest.approx(29.6, abs=0.01)
        assert len(v010["pages"]) == 2
        # Sorted descending by seconds
        assert v010["pages"][0]["page"] == "user-guide/benchmarks.html"

        v09 = data["versions"]["0.9"]
        assert v09["seconds"] == pytest.approx(2.7, abs=0.01)
        assert len(v09["pages"]) == 2

    def test_no_site_dir_returns_none(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        # No _site/ directory
        result = gd._write_build_timing(page_timings=[{"page": "x.html", "seconds": 1.0}])
        assert result is None

    def test_no_timings_returns_none(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)
        result = gd._write_build_timing()
        assert result is None

    def test_empty_timings_returns_none(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)
        result = gd._write_build_timing(page_timings=[])
        assert result is None

    def test_build_time_is_utc_iso(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        timings = [{"page": "index.html", "seconds": 0.5}]
        result = gd._write_build_timing(page_timings=timings)
        data = json.loads(result.read_text())

        # Should be ISO 8601 UTC format
        bt = data["build_time"]
        assert bt.endswith("Z")
        assert "T" in bt

    def test_frozen_annotation_single_version(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        # Create a _freeze/ entry for one page
        freeze_entry = tmp_path / "_freeze" / "recipes" / "freeze-demo" / "execute-results"
        freeze_entry.mkdir(parents=True)
        (freeze_entry / "html.json").write_text("{}")

        timings = [
            {"page": "recipes/freeze-demo.qmd", "seconds": 0.3},
            {"page": "user-guide/overview.qmd", "seconds": 1.2},
        ]

        result = gd._write_build_timing(page_timings=timings)
        data = json.loads(result.read_text())

        pages_by_name = {p["page"]: p for p in data["pages"]}
        assert pages_by_name["recipes/freeze-demo.qmd"]["frozen"] is True
        assert pages_by_name["user-guide/overview.qmd"]["frozen"] is False

    def test_frozen_annotation_multi_version(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        # Create a _freeze/ entry
        freeze_entry = tmp_path / "_freeze" / "user-guide" / "benchmarks" / "execute-results"
        freeze_entry.mkdir(parents=True)
        (freeze_entry / "html.json").write_text("{}")

        timings_by_version = {
            "0.10": [
                {"page": "user-guide/benchmarks.qmd", "seconds": 0.5},
                {"page": "user-guide/overview.qmd", "seconds": 1.2},
            ],
        }

        result = gd._write_build_timing(timings_by_version=timings_by_version)
        data = json.loads(result.read_text())

        pages = data["versions"]["0.10"]["pages"]
        pages_by_name = {p["page"]: p for p in pages}
        assert pages_by_name["user-guide/benchmarks.qmd"]["frozen"] is True
        assert pages_by_name["user-guide/overview.qmd"]["frozen"] is False

    def test_no_freeze_dir_all_false(self, tmp_path: Path):
        gd = self._make_gd(tmp_path)
        site_dir = gd.layout.site_dir
        site_dir.mkdir(parents=True)

        timings = [{"page": "index.qmd", "seconds": 0.5}]
        result = gd._write_build_timing(page_timings=timings)
        data = json.loads(result.read_text())
        assert data["pages"][0]["frozen"] is False


# ---------------------------------------------------------------------------
# Timing computation from timestamps (unit logic)
# ---------------------------------------------------------------------------


class TestTimingComputation:
    """Page durations computed from consecutive start times"""

    def test_consecutive_timestamps_give_deltas(self):
        stamps = [("page-a.html", 10.0), ("page-b.html", 11.5), ("page-c.html", 13.0)]

        assert quarto.page_timings(stamps, ended=14.2) == [
            {"page": "page-a.html", "seconds": 1.5},
            {"page": "page-b.html", "seconds": 1.5},
            {"page": "page-c.html", "seconds": 1.2},
        ]

    def test_single_page(self):
        """A single page gets the full elapsed time."""
        stamps = [("only-page.html", 10.0)]

        assert quarto.page_timings(stamps, ended=15.0) == [
            {"page": "only-page.html", "seconds": 5.0}
        ]

    def test_no_pages(self):
        assert quarto.page_timings([], ended=15.0) == []


# ---------------------------------------------------------------------------
# Versioned build: page_timings in result tuple
# ---------------------------------------------------------------------------


class TestVersionedBuildTimings:
    """Verify render_versions_parallel returns page_timings in result tuples."""

    def test_returns_5_tuple(self, tmp_path: Path):
        """Return a five-element result with page timings last"""
        from great_docs._versioned_build import _render_version

        fake_dir = tmp_path / "fake"
        fake_dir.mkdir()
        (fake_dir / "_quarto.yml").write_text("project:\n  type: website\n")

        result = _render_version(str(fake_dir), None)
        assert len(result) == 5
        # Last element is page_timings (list)
        assert isinstance(result[4], list)
