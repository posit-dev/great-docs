import io
import os
import subprocess
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner
from yaml12 import read_yaml

from great_docs._layout import Layout
from great_docs._layout_migration import analyse
from great_docs._layout_migration.model import MigrationError, Move, Note, fingerprint
from great_docs._utils import QUARTO_YML_HEADER
from great_docs.cli import cli


def test_note_behaves_as_its_message_string() -> None:
    note = Note("Review dynamic reference in a.qmd: b", category="Dynamic References to Review")
    assert note == "Review dynamic reference in a.qmd: b"
    assert "dynamic reference" in note
    assert note.category == "Dynamic References to Review"
    assert note.path is None
    assert note.line is None
    assert note.snippet is None


def test_note_carries_location_metadata() -> None:
    path = Path("docs/index.qmd")
    note = Note(
        "Review X",
        category="HTML Attributes to Update Manually",
        path=path,
        line=7,
        snippet="<img>",
    )
    assert note.path == path
    assert note.line == 7
    assert note.snippet == "<img>"


def test_note_dedup_by_message_matches_prior_string_behaviour() -> None:
    first = Note("Review X in a.qmd", category="A")
    second = Note("Review X in a.qmd", category="B")
    deduped = tuple(dict.fromkeys([first, second]))
    assert deduped == (first,)
    assert len(deduped) == 1


def test_note_survives_copy_and_deepcopy() -> None:
    import copy

    note = Note(
        "Review X in a.qmd",
        category="HTML Attributes to Update Manually",
        path=Path("a.qmd"),
        line=3,
        snippet="<img>",
    )
    shallow = copy.copy(note)
    deep = copy.deepcopy(note)
    for copied in (shallow, deep):
        assert copied == note
        assert copied.category == "HTML Attributes to Update Manually"
        assert copied.path == Path("a.qmd")
        assert copied.line == 3
        assert copied.snippet == "<img>"


class TerminalInput(io.BytesIO):
    """Confirmation input from an interactive terminal"""

    def isatty(self) -> bool:
        return True


@pytest.mark.parametrize(
    "flags, reply, applied",
    [
        ([], b"y\n", True),
        ([], b"n\n", False),
        (["--yes"], None, True),
        (["--dry-run", "--yes"], None, False),
    ],
)
def test_migration_command_confirmation(
    project: Path, flags: list[str], reply: bytes | None, applied: bool
) -> None:
    before = snapshot(project)
    result = CliRunner().invoke(
        cli,
        ["migrate-layout", "--project-path", str(project), *flags],
        input=TerminalInput(reply) if reply else None,
    )
    assert result.exit_code == 0, result.output
    assert (project / "docs/great-docs.yml").is_file() == applied
    if not applied:
        assert snapshot(project) == before


def test_migration_command_requires_interactive_confirmation(project: Path) -> None:
    before = snapshot(project)
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project)], input="y\n"
    )
    assert result.exit_code != 0
    assert "--yes" in result.output
    assert snapshot(project) == before


@pytest.mark.parametrize("destination", ["docs", "website", "website pages"])
def test_migration_command_repeat_is_read_only(
    project: Path, destination: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project)
    args = ["migrate-layout", "--project-path", str(project), "--to", destination]
    result = CliRunner().invoke(cli, [*args, "--yes"])
    assert result.exit_code == 0, result.output
    assert (project / destination / "great-docs.yml").is_file()
    assert str(Path(destination) / "_site") in result.output
    if destination != "docs":
        import shlex

        commands = [
            line.strip()
            for line in result.output.splitlines()
            if line.strip().startswith("great-docs build")
        ]
        assert ["great-docs", "build", "--config", str(Path(destination) / "great-docs.yml")] in [
            shlex.split(command) for command in commands
        ]
    before = snapshot(project)
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "no migration is needed" in result.output.lower()
    assert snapshot(project) == before


def test_migration_command_reports_conflicts_even_with_yes(project: Path) -> None:
    put(project, "docs/great-docs.yml", "display_name: Occupied\n")
    before = snapshot(project)
    result = CliRunner().invoke(
        cli,
        [
            "migrate-layout",
            "--project-path",
            str(project),
            "--config",
            str(project / "great-docs.yml"),
            "--yes",
        ],
    )
    assert result.exit_code != 0
    assert "already exists" in result.output.lower()
    assert snapshot(project) == before


def test_dry_run_report_prints_move_count_header(project: Path) -> None:
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "File / Folder to Move (1)" in result.output
    assert "great-docs.yml -> docs/great-docs.yml" in result.output
    assert "to Review" not in result.output
    assert "Blocking Problem" not in result.output


def test_dry_run_report_groups_review_items_by_category(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: essays}]\n")
    put(project, "essays/notes.rst", "Notes\n")
    put(project, "essays/one.md", "# One\n")
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "File to Review (1)" in result.output
    assert "reStructuredText Files to Check (1)" in result.output
    assert "essays/notes.rst" in result.output


def test_dry_run_report_groups_blockers_by_category(project: Path) -> None:
    # Both a root and a `docs/` config now exist; `--config` disambiguates them,
    # matching `test_migration_command_reports_conflicts_even_with_yes`, so the
    # run reaches the blocked-report path instead of the config-selection error.
    put(project, "docs/great-docs.yml", "display_name: Occupied\n")
    result = CliRunner().invoke(
        cli,
        [
            "migrate-layout",
            "--project-path",
            str(project),
            "--config",
            str(project / "great-docs.yml"),
            "--dry-run",
            "--yes",
        ],
    )
    assert result.exit_code != 0
    assert "Blocking Problem (1)" in result.output
    assert "Conflicts at the Destination (1)" in result.output


def test_dry_run_report_prints_a_located_excerpt(project: Path) -> None:
    put(project, "a.png", b"\x89PNG")
    put(project, "index.qmd", 'before\n<img src="a.png" srcset="a.png 1x, b.png 2x">\n')
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "index.qmd:2:" in result.output
    assert "srcset" in result.output


def test_dry_run_report_shows_bare_subject_for_single_template_categories(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: essays}]\n")
    put(project, "essays/script.py", "print('demo')\n")
    put(project, "essays/one.md", "# One\n")
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Scripts and Notebooks to Verify (1)" in result.output
    assert "essays/script.py" in result.output
    assert "Review dynamic code, notebook references" not in result.output


def test_dry_run_report_suppresses_snippet_for_code_blocks(project: Path) -> None:
    put(project, "index.qmd", 'text\n```{python}\nopen("x")\n```\n')
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Code Blocks to Verify (1)" in result.output
    assert "index.qmd:2" in result.output
    assert "```{python}" not in result.output


def test_dry_run_report_keeps_trailing_detail_for_old_output_paths(project: Path) -> None:
    put(project, "Makefile", "publish:\n\trsync -a great-docs/_site/ remote:/var/www\n")
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Old Output Paths to Update (1)" in result.output
    assert "Makefile; publish docs/_site" in result.output


def test_dry_run_report_does_not_flag_a_curated_skill_file(project: Path) -> None:
    put(project, "skills/sample/SKILL.md", "# Demo\n")
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "skill" not in result.output.lower()


def test_dry_run_report_keeps_the_reason_for_files_retained_as_is(project: Path) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    put(project, "README.md", "![Chart](assets/chart.png)\n")
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Files Retained As-Is (1)" in result.output
    assert "something outside the moving documentation still references it" in result.output
    assert "assets" in result.output


def test_dry_run_report_styles_section_headers_when_color_is_forced(project: Path) -> None:
    result = CliRunner().invoke(
        cli,
        ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"],
        color=True,
    )
    assert result.exit_code == 0, result.output
    assert click.style("File / Folder to Move (1)", bold=True) in result.output


def test_dry_run_report_styles_review_paths_red_when_color_is_forced(project: Path) -> None:
    put(project, "user_guide/demo.termshow", "")
    result = CliRunner().invoke(
        cli,
        ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"],
        color=True,
    )
    assert result.exit_code == 0, result.output
    assert click.style("user_guide/demo.termshow", fg="red") in result.output


def test_dry_run_report_highlights_the_path_within_a_mixed_category(project: Path) -> None:
    put(project, "great-docs.yml", "bibliography: missing.bib\n")
    result = CliRunner().invoke(
        cli,
        ["migrate-layout", "--project-path", str(project), "--dry-run", "--yes"],
        color=True,
    )
    assert result.exit_code != 0
    assert "Configuration to Review" in result.output
    assert click.style("missing.bib", fg="red") in result.output
    assert "Configured input does not exist for" in result.output


@pytest.mark.parametrize("failure", ["absent", "unreadable", "symlink", "escape"])
def test_migration_custom_fallback_is_validated(
    project: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    (project / "great-docs.yml").unlink()
    destination = "website"
    if failure == "unreadable":
        selected = put(project, "website/great-docs.yml", "module: sample\n")
        read_bytes = Path.read_bytes

        def unreadable(path: Path) -> bytes:
            if path == selected:
                raise PermissionError("Configuration is unreadable")
            return read_bytes(path)

        monkeypatch.setattr(Path, "read_bytes", unreadable)
    elif failure == "symlink":
        put(project, "actual/great-docs.yml", "module: sample\n")
        (project / "website").symlink_to(project / "actual", target_is_directory=True)
    elif failure == "escape":
        destination = "../outside"
    before = {str(path.relative_to(project)) for path in project.rglob("*")}
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--to", destination, "--yes"]
    )
    assert result.exit_code != 0, result.output
    assert {str(path.relative_to(project)) for path in project.rglob("*")} == before


def test_explicit_migrated_config_is_noop_unless_relocation_requested(project: Path) -> None:
    (project / "great-docs.yml").unlink()
    selected = put(project, "website/settings.yml", "module: sample\n")
    args = ["migrate-layout", "--project-path", str(project), "--config", str(selected)]
    before = snapshot(project)
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "no migration is needed" in result.output.lower()
    result = CliRunner().invoke(cli, [*args, "--to", "docs", "--yes"])
    assert result.exit_code != 0
    assert "relocation not supported" in result.output.lower()
    assert snapshot(project) == before


def test_migration_uses_one_proposal_for_preview_and_application(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs import _layout_migration as migration_api
    from great_docs._layout_migration import Migration

    analysed: list[Migration] = []
    analyse_original, apply_original = migration_api.analyse, migration_api.apply

    def analyse_once(layout: Layout, target: Path) -> Migration:
        proposal = analyse_original(layout, target)
        analysed.append(proposal)
        return proposal

    def apply_reviewed(proposal: Migration) -> None:
        assert len(analysed) == 1
        assert proposal is analysed[0]
        apply_original(proposal)

    monkeypatch.setattr(migration_api, "analyse", analyse_once)
    monkeypatch.setattr(migration_api, "apply", apply_reviewed)
    result = CliRunner().invoke(cli, ["migrate-layout", "--project-path", str(project), "--yes"])
    assert result.exit_code == 0, result.output
    assert len(analysed) == 1
    assert (project / "docs/great-docs.yml").is_file()


def test_migration_rejects_changes_made_during_confirmation(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def confirm(*args: object, **kwargs: object) -> bool:
        (project / "great-docs.yml").write_text("display_name: Later user edit\n")
        return True

    monkeypatch.setattr("click.confirm", confirm)
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project)], input=TerminalInput(b"y\n")
    )
    assert result.exit_code != 0
    assert "fresh preview" in result.output
    assert (project / "great-docs.yml").read_text() == "display_name: Later user edit\n"
    assert not (project / "docs").exists()


def test_migration_command_preserves_noncanonical_filename_selection(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shlex

    monkeypatch.chdir(project)
    selected = project / "settings file.yml"
    (project / "great-docs.yml").rename(selected)
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--config", str(selected), "--yes"]
    )
    assert result.exit_code == 0, result.output
    command = next(
        line.strip()
        for line in result.output.splitlines()
        if line.strip().startswith("great-docs build")
    )
    assert shlex.split(command) == ["great-docs", "build", "--config", "docs/settings file.yml"]
    before = snapshot(project)
    result = CliRunner().invoke(
        cli,
        [
            "migrate-layout",
            "--project-path",
            str(project),
            "--config",
            str(project / "docs/settings file.yml"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "no migration is needed" in result.output.lower()
    assert snapshot(project) == before


@pytest.mark.parametrize("working_directory", ["root", "nested", "outside"])
@pytest.mark.parametrize("destination", ["docs", "website pages"])
def test_migration_suggested_commands_select_project_from_invocation_directory(
    project: Path, monkeypatch: pytest.MonkeyPatch, working_directory: str, destination: str
) -> None:
    import shlex

    cwd = {"root": project, "nested": project / "sample", "outside": project.parent}[
        working_directory
    ]
    monkeypatch.chdir(cwd)
    result = CliRunner().invoke(
        cli, ["migrate-layout", "--project-path", str(project), "--to", destination, "--yes"]
    )
    assert result.exit_code == 0, result.output
    selection = [] if working_directory == "root" else ["--project-path", str(project)]
    if destination != "docs":
        selected = project / destination / "great-docs.yml"
        selection += [
            "--config",
            str(selected.relative_to(project) if working_directory == "root" else selected),
        ]
    commands = [
        shlex.split(line.strip())
        for line in result.output.splitlines()
        if line.strip().startswith("great-docs ")
    ]
    assert ["great-docs", "build", *selection] in commands
    assert ["great-docs", "preview", *selection] in commands


def test_migration_help_is_directly_available_but_hidden_from_public_reference(
    project: Path,
) -> None:
    from great_docs import GreatDocs

    result = CliRunner().invoke(cli, ["migrate-layout", "--help"])
    assert result.exit_code == 0, result.output
    assert "--config" in result.output and "--dry-run" in result.output
    result = CliRunner().invoke(cli, ["--help"])
    assert "migrate-layout" not in result.output
    info = GreatDocs(str(project))._extract_click_command(cli, "great-docs")
    assert all(command["name"] != "migrate-layout" for command in info["commands"])


@pytest.mark.parametrize("selected", ["missing", "ambiguous", "migrated"])
def test_pending_recovery_precedes_config_selection(
    project: Path, monkeypatch: pytest.MonkeyPatch, selected: str
) -> None:
    import importlib

    from great_docs._layout_migration import apply

    application = importlib.import_module("great_docs._layout_migration.apply")
    move = application._move

    def interrupt(source: Path, destination: Path) -> None:
        move(source, destination)
        if source == project / "great-docs.yml":
            raise KeyboardInterrupt

    monkeypatch.setattr(application, "_move", interrupt)
    with pytest.raises(KeyboardInterrupt):
        apply(analyse(Layout.make(project), Path("docs")))
    args = ["migrate-layout", "--project-path", str(project), "--yes"]
    if selected == "missing":
        args += ["--config", str(project / "great-docs.yml")]
    elif selected == "ambiguous":
        put(project, "great-docs.yml", "module: sample\n")
    before = snapshot(project)
    result = CliRunner().invoke(cli, args)
    assert result.exit_code != 0
    assert "recovery" in result.output.lower()
    assert "manifest.json" in result.output
    assert "no completion record" in result.output
    assert snapshot(project) == before


def put(root: Path, relative: str, content: str | bytes = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode() if isinstance(content, str) else content)
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    put(tmp_path, "pyproject.toml", '[project]\nname = "sample"\nversion = "1.0"\n')
    put(tmp_path, "great-docs.yml", "module: sample\n")
    put(tmp_path, "sample/__init__.py")
    return tmp_path


def snapshot(root: Path) -> dict[str, tuple[int, bytes | str]]:
    return {
        str(path.relative_to(root)): (
            path.lstat().st_mode,
            os.readlink(path)
            if path.is_symlink()
            else path.read_bytes()
            if path.is_file()
            else b"",
        )
        for path in root.rglob("*")
    }


@pytest.mark.parametrize("destination", ["docs", "website/manual"])
def test_analysis_is_read_only_with_shared_assets(project: Path, destination: str) -> None:
    put(project, "great-docs.yml", "bibliography: refs.bib # Citation\nsections: [{dir: essays}]\n")
    put(project, "refs.bib", "@book{ref}\n")
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    put(project, "essays/one.md", "# One\n")
    put(project, "custom/about.html", "<h1>About</h1>\n")
    put(project, "index.qmd", "# Homepage\n")
    put(project, "README.md", "# Package\n")
    put(project, ".gitignore", "great-docs/\n_freeze/\n")
    before = snapshot(project)
    migration = analyse(Layout.make(project), Path(destination))
    assert snapshot(project) == before
    assert not migration.blockers
    for name in ("great-docs.yml", "user_guide", "essays", "custom", "index.qmd", "assets"):
        assert Move(project / name, project / destination / name) in migration.moves
    assert not any(move.source.name in {"README.md", "sample"} for move in migration.moves)
    fingerprints = dict(migration.fingerprints)
    assert project / "assets/chart.png" in fingerprints
    assert project / "refs.bib" in fingerprints
    assert project / "user_guide" in fingerprints
    edits = {edit.path: edit for edit in migration.edits}
    assert project / "user_guide/page.qmd" not in edits
    assert (
        edits[project / ".gitignore"].after
        == (
            f"great-docs/\n_freeze/\n/{destination}/_quarto/\n/{destination}/_site/\n"
            f"/{destination}/.cache/\n"
        ).encode()
    )


def test_asset_directory_referenced_only_by_moving_content_folds_in(project: Path) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert Move(project / "assets", project / "docs/assets") in result.moves
    assert not any(edit.path == project / "user_guide/page.qmd" for edit in result.edits)
    assert not any("external reference" in message.lower() for message in result.follow_up)


def test_asset_directory_referenced_externally_stays_protected(project: Path) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    put(project, "README.md", "![Chart](assets/chart.png)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not any(move.source == project / "assets" for move in result.moves)
    edits = {edit.path: edit for edit in result.edits}
    assert edits[project / "user_guide/page.qmd"].after == b"![Chart](../../assets/chart.png)\n"
    assert any(
        "external reference" in message.lower() and "assets/chart.png" in message
        for message in result.follow_up
    )
    note = next(
        n for n in result.follow_up if "external reference" in n.lower() and "assets/chart.png" in n
    )
    assert note.category == "References Outside the Move"


def test_directory_referenced_only_from_config_path_folds_in(project: Path) -> None:
    put(
        project,
        "great-docs.yml",
        "module: sample\nskill: {skills: [{file: skills/demo/SKILL.md}]}\n",
    )
    put(project, "skills/demo/SKILL.md", "# Demo skill\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert Move(project / "skills", project / "docs/skills") in result.moves


def test_mixed_fold_in_and_protected_directories(project: Path) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    put(project, "README.md", "![Chart](assets/chart.png)\n")
    put(project, "great-docs.yml", "skill: {skills: [{file: skills/demo/SKILL.md}]}\n")
    put(project, "skills/demo/SKILL.md", "# Demo skill\n")
    result = analyse(Layout.make(project), Path("docs"))
    moved = {move.source for move in result.moves}
    assert project / "skills" in moved
    assert project / "assets" not in moved


def test_absolutely_pinned_directory_does_not_fold_in_via_document_link(project: Path) -> None:
    directory = project / "essays"
    put(project, "essays/one.md", "# One\n")
    put(project, "great-docs.yml", f"module: sample\nsections: [{{dir: '{directory}'}}]\n")
    put(project, "user_guide/page.qmd", "[Essay](../essays/one.md)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    # `essays` is pinned absolutely in the config, so `_dedicated_directories`
    # never selects it into `moves` either; a moving document also linking to
    # it must not fold it in behind the config's back.
    assert not any(move.source == directory for move in result.moves)


def test_fold_in_checks_a_candidates_own_referrer_for_external_references(
    project: Path,
) -> None:
    put(project, "user_guide/page.qmd", "[Notes](../notes/a.md)\n![Chart](../assets/chart.png)\n")
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "notes/a.md", "[Chart](../assets/chart.png)\n")
    put(project, "README.md", "[Notes](notes/a.md)\n")
    result = analyse(Layout.make(project), Path("docs"))
    moved = {move.source for move in result.moves}
    # `notes` stays protected because README references it directly. `notes/a.md`
    # itself references `assets`, so `assets` must stay protected too, even
    # though `notes`'s own subtree was excluded from the batch's move-set walk.
    assert project / "notes" not in moved
    assert project / "assets" not in moved


def test_fold_in_candidate_overlapping_the_destination_stays_in_place(project: Path) -> None:
    put(project, "user_guide/page.qmd", "[Existing](../docs/notes.md)\n")
    put(project, "docs/notes.md", "# Notes\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert not any(move.source == project / "docs" for move in result.moves)


def test_directory_holding_a_render_script_does_not_fold_in(project: Path) -> None:
    put(project, "great-docs.yml", "module: sample\npre_render: tools/build.py\n")
    put(project, "tools/build.py", "print('build')\n")
    put(project, "tools/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../tools/chart.png)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    # `pre_render` names an executable path that only the shell running it resolves,
    # so folding its directory in would relocate the script out from under the caller.
    assert not any(move.source == project / "tools" for move in result.moves)


def test_fold_in_reports_unreadable_git_ignore_rules_as_a_blocker(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")

    def unreadable(root: Path) -> frozenset[Path] | None:
        raise MigrationError("local Git check exited 128")

    monkeypatch.setattr(
        sys.modules["great_docs._layout_migration.analyse"], "_ignored_paths", unreadable
    )
    result = analyse(Layout.make(project), Path("docs"))
    assert any("git ignore rules" in message for message in result.blockers)


def test_symlink_inside_a_fold_in_candidate_blocks_instead_of_crashing(project: Path) -> None:
    put(project, "assets/chart.png", b"\x00\xff")
    (project / "assets/link.png").symlink_to(project / "outside.png")
    put(project, "user_guide/page.qmd", "![Chart](../assets/chart.png)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert any("Cannot inspect" in message and "assets" in message for message in result.blockers)


def test_folded_in_notebook_gets_the_same_review_note_as_a_selected_directory(
    project: Path,
) -> None:
    put(project, "extras/demo.ipynb", '{"cells": []}\n')
    put(project, "user_guide/page.qmd", "[Demo](../extras/demo.ipynb)\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert Move(project / "extras", project / "docs/extras") in result.moves
    assert any(
        "Review dynamic code" in message and "extras/demo.ipynb" in message
        for message in result.follow_up
    )


def test_external_reference_survives_as_a_review_note(project: Path) -> None:
    put(project, "CONTRIBUTING.md", "# Contributing\n")
    put(project, "user_guide/page.qmd", "{{< include ../CONTRIBUTING.md >}}\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert any(
        "external reference" in message.lower() and "CONTRIBUTING.md" in message
        for message in result.follow_up
    )


@pytest.mark.parametrize("target", ["great-docs.yml", "user_guide", "_freeze"])
def test_destination_collisions_block_without_writes(project: Path, target: str) -> None:
    put(project, "user_guide/page.md", "# Page")
    put(project, "_freeze/page/cache.json", b"\xff\x00")
    put(project, f"docs/{target}", "User file")
    before = snapshot(project)
    result = analyse(Layout.make(project, project / "great-docs.yml"), Path("docs"))
    assert any(target in message for message in result.blockers)
    assert snapshot(project) == before


def test_migration_moves_existing_cache_into_destination(project: Path) -> None:
    put(project, ".great-docs-cache/d2/abc.svg", "<svg/>")
    put(project, ".great-docs-cache/interlinks/pkg_objects.inv", b"\x00\x01")
    put(project, ".great-docs-cache/snapshots/v0.2.0.json", "{}")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert Move(project / ".great-docs-cache/d2", project / "docs/.cache/d2") in result.moves
    assert (
        Move(project / ".great-docs-cache/interlinks", project / "docs/.cache/interlinks")
        in result.moves
    )
    assert (
        Move(project / ".great-docs-cache/snapshots", project / "docs/.cache/snapshots")
        in result.moves
    )


def test_migration_blocks_existing_destination_cache(project: Path) -> None:
    put(project, ".great-docs-cache/d2/abc.svg", "<svg/>")
    put(project, ".great-docs-cache/interlinks/pkg_objects.inv", b"\x00\x01")
    put(project, "docs/.cache/d2/abc.svg", "<svg/>")
    put(project, "docs/.cache/interlinks/pkg_objects.inv", b"\x00\x01")
    before = snapshot(project)
    result = analyse(Layout.make(project), Path("docs"))
    assert any("Destination cache already exists" in message for message in result.blockers)
    assert snapshot(project) == before


def test_migration_blocks_non_directory_cache(project: Path) -> None:
    put(project, ".great-docs-cache/d2", "not a directory")
    put(project, ".great-docs-cache/interlinks", "not a directory")
    result = analyse(Layout.make(project), Path("docs"))
    assert any("Persistent cache must be a directory" in message for message in result.blockers)


def test_migration_applies_cache_move_to_disk(project: Path) -> None:
    from great_docs._layout_migration import apply

    put(project, ".great-docs-cache/d2/abc.svg", "<svg/>")
    put(project, ".great-docs-cache/interlinks/pkg_objects.inv", "cached inventory")
    put(project, ".great-docs-cache/snapshots/v0.2.0.json", "{}")
    migration = analyse(Layout.make(project), Path("docs"))
    apply(migration)
    assert (project / "docs/.cache/d2/abc.svg").read_text() == "<svg/>"
    assert (project / "docs/.cache/interlinks/pkg_objects.inv").read_text() == "cached inventory"
    assert (project / "docs/.cache/snapshots/v0.2.0.json").read_text() == "{}"
    assert not (project / ".great-docs-cache/d2").exists()
    assert not (project / ".great-docs-cache/interlinks").exists()
    assert not (project / ".great-docs-cache/snapshots").exists()


@pytest.mark.parametrize("source", ["sample", "src", "user_guide/sub", "great-docs", "docs/inside"])
def test_overlapping_sources_are_blocked(project: Path, source: str) -> None:
    put(project, "great-docs.yml", f"sections: [{{dir: {source}}}]\n")
    put(project, "user_guide/sub/page.md", "# Page")
    put(project, f"{source}/other.md", "# Other")
    result = analyse(Layout.make(project), Path("docs"))
    assert result.blockers


@pytest.mark.parametrize("kind", ["source", "child", "destination", "shared", "freeze"])
def test_symlinks_are_blocked(project: Path, kind: str) -> None:
    target = put(project, "retained.txt", "Original")
    if kind == "source":
        (project / "user_guide").symlink_to(project / "sample", target_is_directory=True)
    elif kind == "child":
        (project / "user_guide").mkdir()
        (project / "user_guide/link").symlink_to(target)
    elif kind == "destination":
        (project / "docs").symlink_to(project / "sample", target_is_directory=True)
    elif kind == "shared":
        (project / "refs.bib").symlink_to(target)
        put(project, "great-docs.yml", "bibliography: refs.bib\n")
    else:
        (project / "_freeze").symlink_to(project / "sample", target_is_directory=True)
    before = snapshot(project)
    result = analyse(Layout.make(project), Path("docs"))
    assert any("symlink" in message.lower() for message in result.blockers)
    assert snapshot(project) == before


def test_read_failure_is_a_blocker(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = put(project, "user_guide/page.md", "# Page")
    original = Path.read_bytes

    def fail_selected(self: Path) -> bytes:
        if self == path:
            raise PermissionError("Cannot read selected page")
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", fail_selected)
    result = analyse(Layout.make(project), Path("docs"))
    assert any("page.md" in message for message in result.blockers)


def test_already_migrated_is_noop(project: Path) -> None:
    config = put(project, "docs/great-docs.yml", "module: sample\n")
    before = snapshot(project)
    result = analyse(Layout.make(project, config), Path("docs"))
    assert not result.moves and not result.edits and not result.blockers
    assert any("already" in message.lower() for message in result.follow_up)
    assert snapshot(project) == before


@pytest.fixture
def isolated_git(project: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(project / "git-config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(project / "xdg"))
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    return project


@pytest.mark.usefixtures("isolated_git")
@pytest.mark.parametrize("cache", ["moved", "empty", "recovered"])
@pytest.mark.parametrize("rules", ["/_freeze/\n", "/docs/_freeze/\n"])
def test_migration_blocks_changed_freeze_ignore_policy(
    project: Path, cache: str, rules: str
) -> None:
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    put(project, ".gitignore", rules)
    if cache == "empty":
        (project / "_freeze").mkdir()
    elif cache == "moved":
        put(project, "_freeze/result.json", b"cache\x00")
    else:
        put(project, "great-docs/_quarto.yml", QUARTO_YML_HEADER)
        put(project, "great-docs/_freeze/result.json", b"cache\x00")
    before = snapshot(project)

    result = analyse(Layout.make(project), Path("docs"))

    assert any("ignore policy" in message for message in result.blockers)
    assert snapshot(project) == before


@pytest.mark.usefixtures("isolated_git")
@pytest.mark.parametrize("rules", ["", "**/_freeze/*\n!**/_freeze/kept.json\n"])
def test_migration_preserves_matching_freeze_ignore_policy(project: Path, rules: str) -> None:
    from great_docs._layout_migration import apply

    subprocess.run(["git", "init", "-q", str(project)], check=True)
    put(project, ".gitignore", rules)
    put(project, "_freeze/result.json", b"cache\x00")
    put(project, "_freeze/kept.json", b"tracked cache\x00")
    subprocess.run(["git", "-C", str(project), "add", "-f", "_freeze/kept.json"], check=True)

    result = analyse(Layout.make(project), Path("docs"))

    assert not result.blockers
    apply(result)
    assert (project / "docs/_freeze/result.json").read_bytes() == b"cache\x00"
    assert (project / "docs/_freeze/kept.json").read_bytes() == b"tracked cache\x00"
    for name in ("result.json", "kept.json"):
        statuses = [
            subprocess.run(
                ["git", "-C", str(project), "check-ignore", "--no-index", "-q", path],
                check=False,
            ).returncode
            for path in (f"_freeze/{name}", f"docs/_freeze/{name}")
        ]
        assert statuses[0] == statuses[1]


@pytest.mark.usefixtures("isolated_git")
@pytest.mark.parametrize("ignored", [False, True])
def test_migration_preserves_forced_cache_tracking_or_refuses(project: Path, ignored: bool) -> None:
    from great_docs._layout_migration import apply

    rules = "_freeze/\n" if ignored else "/_freeze/\n/docs/_freeze/*\n!/docs/_freeze/kept.json\n"
    put(project, ".gitignore", rules)
    put(project, "_freeze/kept.json", b"tracked cache\x00")
    subprocess.run(["git", "-C", str(project), "add", "-f", "_freeze/kept.json"], check=True)
    proposal = analyse(Layout.make(project), Path("docs"))
    if not ignored:
        assert not proposal.blockers
    if proposal.blockers:
        assert any("tracked cache" in message for message in proposal.blockers)
        assert (project / "_freeze/kept.json").read_bytes() == b"tracked cache\x00"
        assert not (project / "docs/_freeze/kept.json").exists()
        return

    apply(proposal)
    subprocess.run(["git", "-C", str(project), "add", "-A"], check=True)
    tracked = subprocess.run(
        ["git", "-C", str(project), "ls-files", "docs/_freeze/kept.json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tracked.strip() == "docs/_freeze/kept.json"


@pytest.mark.usefixtures("isolated_git")
def test_migration_revalidates_cache_tracking_index(project: Path) -> None:
    from great_docs._layout_migration import MigrationError, apply

    put(project, "_freeze/result.json", b"cache\x00")
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers
    subprocess.run(["git", "-C", str(project), "add", "_freeze/result.json"], check=True)
    before = snapshot(project)

    with pytest.raises(MigrationError):
        apply(proposal)

    assert snapshot(project) == before


@pytest.mark.usefixtures("isolated_git")
def test_migration_revalidates_shared_cache_tracking_index(project: Path) -> None:
    from great_docs._layout_migration import MigrationError, apply

    put(project, "_freeze/result.json", b"cache\x00")
    subprocess.run(["git", "-C", str(project), "add", "_freeze/result.json"], check=True)
    subprocess.run(["git", "-C", str(project), "update-index", "--split-index"], check=True)
    shared = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--shared-index-path"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    shared_path = project / shared
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers
    assert shared_path in dict(proposal.fingerprints)
    shared_path.write_bytes(shared_path.read_bytes() + b"changed")
    before = snapshot(project)

    with pytest.raises(MigrationError):
        apply(proposal)

    assert snapshot(project) == before


@pytest.mark.usefixtures("isolated_git")
def test_migration_revalidates_freeze_ignore_inputs(project: Path) -> None:
    from great_docs._layout_migration import MigrationError, apply

    subprocess.run(["git", "init", "-q", str(project)], check=True)
    put(project, "_freeze/result.json", b"cache\x00")
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers
    put(project, ".git/info/exclude", "/docs/_freeze/\n")
    before = snapshot(project)

    with pytest.raises(MigrationError):
        apply(proposal)

    assert snapshot(project) == before


@pytest.mark.usefixtures("isolated_git")
@pytest.mark.parametrize("change", ["contents", "retarget", "remove", "ancestor"])
def test_migration_revalidates_linked_external_ignore_policy(
    project: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from great_docs._layout_migration import MigrationError, apply

    external = tmp_path_factory.mktemp("external-ignore")
    policy = put(external, "policies/excludes", "")
    link = external / "linked"
    link.symlink_to(policy.parent, target_is_directory=True)
    config = put(external, "config", f"[core]\nexcludesFile = {link / 'excludes'}\n")
    config_link = external / "gitconfig"
    config_link.symlink_to(config)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config_link))
    put(project, "_freeze/result.json", b"cache\x00")
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers
    if change == "contents":
        policy.write_text("/docs/_freeze/\n")
    elif change == "remove":
        config_link.unlink()
    elif change == "retarget":
        config_link.unlink()
        config_link.symlink_to(put(external, "other-config", config.read_bytes()))
    else:
        link.unlink()
        alternative = external / "alternative"
        alternative.mkdir()
        put(alternative, "excludes", "")
        link.symlink_to(alternative, target_is_directory=True)
    before = snapshot(project)

    with pytest.raises(MigrationError):
        apply(proposal)

    assert snapshot(project) == before


def test_migration_freeze_policy_with_host_git_configuration(project: Path) -> None:
    from great_docs._layout_migration import apply

    subprocess.run(["git", "init", "-q", str(project)], check=True)
    put(project, "_freeze/result.json", b"cache\x00")
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers

    apply(proposal)

    assert (project / "docs/_freeze/result.json").read_bytes() == b"cache\x00"


@pytest.mark.usefixtures("isolated_git")
def test_migration_revalidates_missing_included_git_config(
    project: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs._layout_migration import MigrationError, apply

    external = tmp_path_factory.mktemp("included-ignore")
    config = put(external, "config", "[include]\npath = extra-config\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    put(project, "_freeze/result.json", b"cache\x00")
    proposal = analyse(Layout.make(project), Path("docs"))
    assert not proposal.blockers
    put(external, "extra-config", "[core]\nexcludesFile = changed-rules\n")
    before = snapshot(project)

    with pytest.raises(MigrationError):
        apply(proposal)

    assert snapshot(project) == before


@pytest.mark.usefixtures("isolated_git")
def test_migration_blocks_conditional_git_ignore_configuration(project: Path) -> None:
    put(project, "git-config", '[includeIf "onbranch:future"]\npath = extra-config\n')
    put(project, "_freeze/result.json", b"cache\x00")

    proposal = analyse(Layout.make(project), Path("docs"))

    assert any("conditional" in message for message in proposal.blockers)


def test_freeze_move_preserves_bytes_and_generated_trees(project: Path) -> None:
    put(project, "_freeze/page/cache.js", b"\xff\x00no newline")
    put(project, "great-docs/_quarto.yml", QUARTO_YML_HEADER)
    put(project, "great-docs/_freeze/page/cache.js", b"different")
    before = snapshot(project)
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert Move(project / "_freeze", project / "docs/_freeze") in result.moves
    assert not any(edit.path.name == "cache.js" for edit in result.edits)
    assert any("great-docs" in message for message in result.follow_up)
    assert snapshot(project) == before


def test_freeze_recovery_merges_historical_first_latest_last(project: Path) -> None:
    for name in ("great-docs-v1", "great-docs-v2", "great-docs"):
        put(project, f"{name}/_quarto.yml", QUARTO_YML_HEADER)
        put(project, f"{name}/_freeze/page/cache.js", name.encode())
    put(project, "great-docs-v1/_freeze/old/cache.json", b"\xffold")
    put(project, "great-docs-unmarked/_freeze/ignored.json", "Ignore")
    before = snapshot(project)
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    edits = {edit.path.relative_to(project).as_posix(): edit for edit in result.edits}
    assert edits["docs/_freeze/page/cache.js"].before is None
    assert edits["docs/_freeze/page/cache.js"].after == b"great-docs"
    assert edits["docs/_freeze/old/cache.json"].after == b"\xffold"
    assert "docs/_freeze/ignored.json" not in edits
    assert snapshot(project) == before


def test_implicit_logos_become_explicit_without_losing_settings(project: Path) -> None:
    put(project, "great-docs.yml", "logo: {alt: 'Sample'} # Keep\nhero:\n  tagline: Simple\n")
    put(project, "assets/logo.svg", "<svg/>")
    put(project, "assets/logo-dark.svg", "<svg>dark</svg>")
    put(project, "logo-hero.png", b"hero")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    # Nothing besides the implicit logo fields references `assets`, so it folds
    # into the destination alongside `great-docs.yml`; the two move together and
    # the relative path between them is unchanged.
    assert Move(project / "assets", project / "docs/assets") in result.moves
    edit = next(edit for edit in result.edits if edit.path == project / "great-docs.yml")
    config = read_yaml(io.StringIO(edit.after.decode()))
    assert config["logo"] == {
        "alt": "Sample",
        "light": "assets/logo.svg",
        "dark": "assets/logo-dark.svg",
    }
    assert config["hero"]["logo"] == {"light": "../logo-hero.png", "dark": "../logo-hero.png"}
    assert config["hero"]["tagline"] == "Simple"
    assert "# Keep" in edit.after.decode()


def test_automation_follow_up_names_file_and_new_site(project: Path) -> None:
    put(project, ".github/workflows/docs.yml", "path: great-docs/_site\n")
    result = analyse(Layout.make(project), Path("website"))
    assert any(
        ".github/workflows/docs.yml" in message and "website/_site" in message
        for message in result.follow_up
    )


@pytest.mark.parametrize("change", ["add", "remove", "mode", "symlink"])
def test_directory_fingerprint_detects_stale_inventory(project: Path, change: str) -> None:
    path = put(project, "user_guide/page.md", "# Page")
    directory = path.parent
    before = fingerprint(directory)
    if change == "add":
        put(project, "user_guide/new.md", "# New")
    elif change == "remove":
        path.unlink()
    elif change == "mode":
        path.chmod(0o700)
    else:
        (directory / "linked").symlink_to(path)
    assert fingerprint(directory) != before


def test_package_readme_stays_at_root_with_rebased_guide_link(project: Path) -> None:
    put(project, "README.md", "[Guide](user_guide/page.md)\n")
    put(project, "user_guide/page.md", "# Page")
    result = analyse(Layout.make(project), Path("docs"))
    edit = next(edit for edit in result.edits if edit.path == project / "README.md")
    assert edit.after == b"[Guide](docs/user_guide/page.md)\n"
    assert not any(move.source == project / "README.md" for move in result.moves)
    assert not result.blockers


def test_absolute_source_directory_is_retained(project: Path) -> None:
    directory = project / "essays"
    put(project, "essays/page.md", "# Page")
    put(project, "great-docs.yml", f"sections: [{{dir: '{directory}'}}]\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    assert not any(move.source == directory for move in result.moves)
    assert directory in dict(result.fingerprints)
    assert not any(edit.path == project / "great-docs.yml" for edit in result.edits)


def test_nested_package_blocks_document_directory_move(project: Path) -> None:
    put(project, "user_guide/nested_package/__init__.py")
    result = analyse(Layout.make(project), Path("docs"))
    assert any(
        "package" in message.lower() and "user_guide" in message for message in result.blockers
    )


def test_recovered_cache_file_directory_collision_blocks(project: Path) -> None:
    for name in ("great-docs-old", "great-docs"):
        put(project, f"{name}/_quarto.yml", QUARTO_YML_HEADER)
    put(project, "great-docs-old/_freeze/page", "File")
    put(project, "great-docs/_freeze/page/data.json", "Cache")
    result = analyse(Layout.make(project), Path("docs"))
    assert any(
        "cache" in message.lower() and "overlap" in message.lower() for message in result.blockers
    )


def test_missing_configuration_blocks_instead_of_proposing_empty_file(project: Path) -> None:
    (project / "great-docs.yml").unlink()
    result = analyse(Layout.make(project), Path("docs"))
    assert result.blockers
    assert not result.moves


def test_root_freeze_must_be_a_directory(project: Path) -> None:
    put(project, "_freeze", "Not a cache directory")
    result = analyse(Layout.make(project), Path("docs"))
    assert any("cache" in message.lower() for message in result.blockers)


def test_destination_rejects_symlink_before_parent_normalisation(project: Path) -> None:
    (project / "link").symlink_to(project / "sample", target_is_directory=True)
    result = analyse(Layout.make(project), Path("link/../docs"))
    assert any("symlink" in message.lower() for message in result.blockers)


def test_absolute_file_reference_cannot_point_into_a_moved_directory(project: Path) -> None:
    asset = put(project, "user_guide/refs.bib", "@book{ref}")
    put(project, "great-docs.yml", f"bibliography: '{asset}'\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert any(
        "absolute" in message.lower() and "refs.bib" in message for message in result.blockers
    )


def test_unreferenced_implicit_asset_is_reported(project: Path) -> None:
    put(project, "assets/download.zip", b"download")
    result = analyse(Layout.make(project), Path("docs"))
    assert any(
        "download.zip" in message and "implicit" in message.lower() for message in result.blockers
    )


def test_migrated_shared_asset_is_staged_under_the_build(project: Path) -> None:
    from great_docs import GreatDocs

    put(project, "assets/chart.png", b"chart")
    put(
        project,
        "user_guide/01-start.qmd",
        "---\ntitle: Start\n---\n![Chart](../assets/chart.png)\n",
    )
    # A second, non-moving reference keeps `assets` outside the move-set (see
    # `test_asset_directory_referenced_externally_stays_protected`), so this
    # fixture still exercises the build's `_shared` staging for a genuinely
    # shared asset rather than one that now moves alongside the user guide.
    put(project, "README.md", "![Chart](assets/chart.png)\n")
    migration = analyse(Layout.make(project), Path("docs"))
    assert not migration.blockers
    for edit in migration.edits:
        edit.path.parent.mkdir(parents=True, exist_ok=True)
        edit.path.write_bytes(edit.after)
    for move in migration.moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        move.source.rename(move.destination)
    gd = GreatDocs(str(project))
    gd._prepare_build_directory()
    gd._copy_user_guide_to_docs(gd._discover_user_guide())
    page = gd.build_dir / "user-guide/start.qmd"
    assert "![Chart](../_shared/assets/chart.png)" in page.read_text()
    assert (gd.build_dir / "_shared/assets/chart.png").read_bytes() == b"chart"


def test_retained_narrative_links_follow_moved_guides(project: Path) -> None:
    directory = project / "essays"
    page = put(project, "essays/page.md", "[Guide](../user_guide/start.md)\n")
    put(project, "user_guide/start.md", "# Start")
    put(project, "great-docs.yml", f"sections: [{{dir: '{directory}'}}]\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers
    edit = next(edit for edit in result.edits if edit.path == page)
    assert edit.after == b"[Guide](../docs/user_guide/start.md)\n"


def test_recursive_terminal_recordings_have_file_specific_follow_up(project: Path) -> None:
    recording = put(project, "examples/nested/demo.termshow", "Recording")
    companion = put(project, "examples/nested/demo.yml", "command: echo demo")
    result = analyse(Layout.make(project), Path("docs"))
    assert any(str(recording) in message for message in result.follow_up)
    assert recording in dict(result.fingerprints)
    assert companion in dict(result.fingerprints)


def test_termshow_inside_a_moved_directory_gets_one_note_not_two(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: essays}]\n")
    recording = put(project, "essays/demo.termshow", "Recording")
    put(project, "essays/demo.yml", "command: echo demo")
    put(project, "essays/one.md", "# One\n")
    result = analyse(Layout.make(project), Path("docs"))
    matches = [n for n in result.follow_up if str(recording) in n]
    assert len(matches) == 1
    assert matches[0].category == "Terminal Recordings to Check"


def test_gitignored_fixture_tree_is_not_reviewed(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    put(project, ".gitignore", "test-packages/*/\n")
    put(project, "test-packages/_rendered/demo.termshow", "recording")
    put(project, "assets/demo.termshow", "recording")
    result = analyse(Layout.make(project), Path("docs"))
    assert not any("test-packages" in message for message in result.follow_up)
    assert any("assets/demo.termshow" in message for message in result.follow_up)


def test_unavailable_git_ignore_check_is_a_blocker_not_a_crash(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    analyse_module = importlib.import_module("great_docs._layout_migration.analyse")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    def unavailable(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
        raise MigrationError("git executable not found")

    monkeypatch.setattr(analyse_module, "_git", unavailable)
    result = analyse(Layout.make(project), Path("docs"))
    assert any("git ignore rules" in message.lower() for message in result.blockers)


@pytest.mark.parametrize("directory", ["user_guide", "_freeze", "great-docs/_freeze"])
def test_preview_fingerprint_detects_changed_tree_hierarchy(project: Path, directory: str) -> None:
    if directory.startswith("great-docs/"):
        put(project, "great-docs/_quarto.yml", QUARTO_YML_HEADER)
    tree = project / directory
    (tree / "a").mkdir(parents=True)
    sibling = put(tree, "b", b"same bytes")
    migration = analyse(Layout.make(project), Path("docs"))
    assert not migration.blockers
    before = dict(migration.fingerprints)[tree]
    sibling.rename(tree / "a/b")
    assert fingerprint(tree) != before


def test_intermediate_destination_file_blocks_without_writes(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: tutorials/guides}]\n")
    put(project, "tutorials/guides/start.md", "# Start")
    obstruction = put(project, "docs/tutorials", "User file")
    before = snapshot(project)
    migration = analyse(Layout.make(project), Path("docs"))
    assert any(str(obstruction) in message for message in migration.blockers)
    assert snapshot(project) == before


@pytest.mark.parametrize("extension", ["html", "qmd"])
def test_generated_reference_links_do_not_block_analysis(project: Path, extension: str) -> None:
    reference = f"reference/sample.api.{extension}?view=full#usage"
    content = f"[API]({reference})\n"
    put(project, "index.qmd", content)
    put(project, "user_guide/start.qmd", f"[API](../{reference})\n")
    before = snapshot(project)
    migration = analyse(Layout.make(project), Path("docs"))
    assert not migration.blockers
    assert not any(edit.path.suffix == ".qmd" for edit in migration.edits)
    assert snapshot(project) == before


def test_bare_numeric_prefix_reference_is_not_a_broken_link(project: Path) -> None:
    put(project, "user_guide/00-introduction.qmd", "[Install](installation.qmd)")
    put(project, "user_guide/01-installation.qmd", "# Installation")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers


def test_inline_code_include_example_is_not_rewritten(project: Path) -> None:
    put(project, "user_guide/authoring.qmd", "Include syntax: `{{< include file.qmd >}}`\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers


def test_real_missing_include_still_blocks(project: Path) -> None:
    put(project, "user_guide/page.qmd", "{{< include missing.qmd >}}\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert any("missing.qmd" in message for message in result.blockers)


@pytest.mark.parametrize("name", ["llms.txt", "llms-full.txt"])
def test_llms_txt_reference_does_not_block_analysis(project: Path, name: str) -> None:
    put(
        project,
        "great-docs.yml",
        "module: sample\nskill:\n  skills:\n    - name: sample\n      file: skills/sample/SKILL.md\n",
    )
    put(project, "skills/sample/SKILL.md", f"[{name}]({name})\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert not result.blockers


def test_move_contents_flag_package_metadata_and_dynamic_files(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: essays}]\n")
    put(project, "essays/__init__.py", "")
    put(project, "essays/analysis.ipynb", "{}")
    put(project, "essays/notes.rst", "Notes\n")
    put(project, "essays/one.md", "# One\n")
    result = analyse(Layout.make(project), Path("docs"))
    directory = next(n for n in result.blockers if "package sources or metadata" in n.lower())
    assert directory.category == "Package Files Mixed Into Docs"
    dynamic = next(n for n in result.follow_up if "notebook references" in n.lower())
    assert dynamic.category == "Scripts and Notebooks to Verify"
    unsupported = next(n for n in result.follow_up if "restructuredtext references" in n.lower())
    assert unsupported.category == "reStructuredText Files to Check"


def test_inspection_errors_are_categorized(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    put(project, "great-docs.yml", "bibliography: refs.bib\n")
    put(project, "refs.bib", "@book{ref}\n")
    read_bytes = Path.read_bytes

    def unreadable(path: Path) -> bytes:
        if path.name == "refs.bib":
            raise PermissionError("unreadable")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = analyse(Layout.make(project), Path("docs"))
    error = next(n for n in result.blockers if "cannot inspect" in n.lower() and "refs.bib" in n)
    assert error.category == "Files That Could Not Be Read"


def test_repeat_migration_reports_a_status_note(project: Path) -> None:
    from great_docs._layout_migration import apply

    apply(analyse(Layout.make(project), Path("docs")))
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.follow_up if "no migration is needed" in n.lower())
    assert note.category == "Already Migrated"


def test_relocating_migrated_project_is_blocked_with_category(project: Path) -> None:
    from great_docs._layout_migration import apply

    apply(analyse(Layout.make(project), Path("docs")))
    result = analyse(Layout.make(project), Path("website"))
    note = next(n for n in result.blockers if "unsupported" in n.lower())
    assert note.category == "Relocation Not Supported"


def test_destination_must_be_a_descendant_is_categorized(project: Path) -> None:
    result = analyse(Layout.make(project), Path("."))
    note = next(n for n in result.blockers if "must be a descendant" in n.lower())
    assert note.category == "Conflicts at the Destination"


def test_missing_documentation_source_is_categorized(project: Path) -> None:
    put(project, "great-docs.yml", "sections: [{dir: essays}]\n")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.blockers if "does not exist" in n.lower() and "essays" in n)
    assert note.category == "Conflicts With the Source"


def test_missing_configured_input_is_categorized(project: Path) -> None:
    put(project, "great-docs.yml", "bibliography: missing.bib\n")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.blockers if "configured input does not exist" in n.lower())
    assert note.category == "Configuration to Review"


def test_curated_skill_file_is_fingerprinted_without_a_review_note(project: Path) -> None:
    skill = put(project, "skills/sample/SKILL.md", "# Demo\n")
    result = analyse(Layout.make(project), Path("docs"))
    assert skill in dict(result.fingerprints)
    assert not any("skill" in n.lower() for n in result.follow_up)


def test_unreferenced_asset_is_categorized(project: Path) -> None:
    put(project, "assets/orphan.png", b"\x00")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.blockers if "unreferenced implicit asset" in n.lower())
    assert note.category == "Assets With Unclear Ownership"


def test_freeze_cache_conflict_is_categorized(project: Path) -> None:
    put(project, "docs/_freeze/.gitkeep", "")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.blockers if "destination cache already exists" in n.lower())
    assert note.category == "Cached Build Conflicts"


def test_terminal_recording_is_categorized(project: Path) -> None:
    put(project, "user_guide/demo.termshow", "")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.follow_up if "terminal recording" in n.lower())
    assert note.category == "Terminal Recordings to Check"


def test_automation_output_path_is_categorized(project: Path) -> None:
    put(project, "Makefile", "publish:\n\trsync -a great-docs/_site/ remote:/var/www\n")
    result = analyse(Layout.make(project), Path("docs"))
    note = next(n for n in result.follow_up if "update old output paths" in n.lower())
    assert note.category == "Old Output Paths to Update"
