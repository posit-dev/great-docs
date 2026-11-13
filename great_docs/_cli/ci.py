"""CI reporting and documentation workflow commands"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import click

from .._build.steps import PROJECT_ERRORS
from .._project import manifest as _manifest
from .._project.layout import Layout
from .._project.manifest import ManifestError
from . import options as _options
from .app import OrderedGroup


def _detect_python_version(project_root: Path) -> str | None:
    """
    Choose the Python version a documentation workflow runs on

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        A `major.minor` version from the project's Python requirement. For a requirement
        containing `>=` or `~=`, the first version (the lower bound), such as `3.10` for
        `>=3.10,<3.13`; otherwise, the highest version named. `None` when the project declares
        no requirement, the requirement names no version, or the metadata cannot be read.
    """
    try:
        requires_python = _manifest.read(project_root)["requires_python"]
    except ManifestError:
        return None

    # CI uses major.minor versions, for example from `>=3.12`, `>=3.10,<3.13`,
    # `~=3.11` or `>=3.9`.
    matches = re.findall(r"(\d+\.\d+)", requires_python)
    if not matches:
        return None

    # Treat the first version as the lower bound for `>=` and `~=` requirements.
    if ">=" in requires_python or "~=" in requires_python:
        return matches[0]

    # Other specifiers use the highest named version as the likely CI target.
    versions = [tuple(map(int, v.split("."))) for v in matches]
    max_version = max(versions)
    return f"{max_version[0]}.{max_version[1]}"


def _detect_package_manager(project_root: Path) -> str:
    """Detect the package manager used by the project.

    Checks for lock files to determine which package manager is in use:
    - uv.lock -> uv
    - poetry.lock -> poetry
    - Otherwise -> pip (default)

    Returns:
        One of: 'uv', 'poetry', or 'pip'
    """
    if (project_root / "uv.lock").exists():
        return "uv"
    if (project_root / "poetry.lock").exists():
        return "poetry"
    return "pip"


def _detect_optional_dependencies(project_root: Path) -> list[str]:
    """
    Choose the extras a documentation workflow installs

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        The sorted names of extras related to documentation, development or testing, such
        as `dev`, `docs` or `test`, for a command like `pip install -e ".[dev,docs]"`. An empty
        list when there are none or the project's metadata cannot be read.
    """
    try:
        extras = _manifest.read(project_root)["optional_dependencies"]
    except ManifestError:
        return []

    # Documentation workflows may also need development, notebook or test dependencies.
    terms = ["dev", "doc", "notebook", "test", "all", "full"]
    return sorted(extra for extra in extras if any(term in extra.lower() for term in terms))


@click.group(cls=OrderedGroup)
def ci() -> None:
    """
    Helpers for GitHub Actions and GitLab CI

    These emit the "preview this build locally" hints that let reviewers open a
    pull request's docs without a preview host: a workflow log notice and a
    sticky PR comment, both pointing at 'great-docs preview'.

    \b
    Examples:
      great-docs ci notice --run "$GITHUB_RUN_ID" --pr 302
      great-docs ci pr-comment --run "$GITHUB_RUN_ID" --pr 302
    """


@click.command(name="pr-comment")
@click.option(
    "--run", "run_id", type=int, required=True, help="Workflow run id that built the site."
)
@click.option("--pr", type=int, required=True, help="Pull request number to comment on.")
@click.option(
    "--repo",
    default=None,
    help="GitHub repo as 'owner/repo' (default: $GITHUB_REPOSITORY, then git remote).",
)
def ci_pr_comment(run_id: int, pr: int, repo: str | None) -> None:
    """Post or refresh a sticky PR comment with the local-preview command.

    Reads the token from GITHUB_TOKEN / GH_TOKEN and needs 'pull-requests: write'.
    """
    from .._build.github_ci import post_preview_comment
    from .._build.preview_artifacts import PreviewError

    try:
        action, repo_slug = post_preview_comment(run_id=run_id, pr=pr, repo_override=repo)
        click.echo(f"✓ {action.capitalize()} preview comment on {repo_slug}#{pr}")
    except PreviewError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command(name="notice")
@click.option(
    "--run", "run_id", type=int, required=True, help="Workflow run id that built the site."
)
@click.option("--pr", type=int, default=None, help="Pull request number (adds the --pr hint).")
def ci_notice(run_id: int, pr: int | None) -> None:
    """Print a workflow log notice with the local-preview command."""
    from .._build.github_ci import render_notice_lines

    for line in render_notice_lines(run_id, pr):
        click.echo(line)


def _gitlab_options(command: Any) -> Any:
    """Apply the shared GitLab build and project selectors to CI commands"""
    for option in (
        click.option(
            "--job",
            type=click.IntRange(min=1),
            default=None,
            help="Artifact-producing GitLab job ID.",
        ),
        click.option(
            "--pipeline",
            type=click.IntRange(min=1),
            default=None,
            help="Artifact-producing GitLab pipeline ID.",
        ),
        click.option(
            "--repo",
            default=None,
            help="MR target project URL or GitLab shorthand (default: CI MR project).",
        ),
        click.option(
            "--artifact-repo",
            default=None,
            help="Artifact-owning project, when a fork runs the build.",
        ),
        click.option(
            "--repo-base-url",
            default=None,
            help="GitLab instance base, including an HTTP installation prefix.",
        ),
        click.option(
            "--artifact",
            default="docs-html",
            help="Documentation job or archive name for pipeline/MR selection.",
        ),
    ):
        command = option(command)
    return command


@click.command(name="mr-comment")
@click.option(
    "--mr",
    type=click.IntRange(min=1),
    required=True,
    help="Project-local MR IID in the target project.",
)
@_gitlab_options
def ci_mr_comment(
    mr: int,
    job: int | None,
    pipeline: int | None,
    repo: str | None,
    artifact_repo: str | None,
    repo_base_url: str | None,
    artifact: str,
) -> None:
    """Post or update an opt-in GitLab note using a write-capable GITLAB_TOKEN"""
    from .._build.gitlab_ci import post_preview_comment
    from .._build.preview_artifacts import PreviewError

    try:
        action, target = post_preview_comment(
            mr=mr,
            job=job,
            pipeline=pipeline,
            repo=repo,
            artifact_repo=artifact_repo,
            base_url=repo_base_url,
            artifact=artifact,
        )
    except PreviewError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"{action.capitalize()} preview note on {target}!{mr}")


@click.command(name="gitlab-notice")
@click.option(
    "--mr", type=click.IntRange(min=1), default=None, help="MR IID for the latest-build hint."
)
@_gitlab_options
def ci_gitlab_notice(
    mr: int | None,
    job: int | None,
    pipeline: int | None,
    repo: str | None,
    artifact_repo: str | None,
    repo_base_url: str | None,
    artifact: str,
) -> None:
    """Print GitLab job-log preview commands with complete repository identities"""
    from .._build.gitlab_ci import render_notice_lines, resolve_ci_repositories
    from .._build.preview_artifacts import PreviewError

    try:
        target, owner = resolve_ci_repositories(repo, artifact_repo, repo_base_url)
        lines = render_notice_lines(
            target, owner, mr=mr, job=job, pipeline=pipeline, artifact=artifact
        )
    except PreviewError as error:
        raise click.ClickException(str(error)) from error
    for line in lines:
        click.echo(line)


@click.command(name="setup-github-pages")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--main-branch",
    type=str,
    default="main",
    help="Main branch name for deployment (default: main)",
)
@click.option(
    "--python-version",
    type=str,
    default=None,
    help="Python version for CI (default: auto-detect from pyproject.toml, or 3.11)",
)
@click.option(
    "--package-manager",
    type=click.Choice(["auto", "pip", "uv", "poetry"]),
    default="auto",
    help="Package manager for installing dependencies (default: auto-detect)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing workflow file without prompting",
)
@click.option(
    "--install-from-main",
    is_flag=True,
    help="Install Great Docs from GitHub main branch instead of PyPI release",
)
@_options.config_option
def setup_github_pages(
    project_path: str | None,
    main_branch: str,
    python_version: str | None,
    package_manager: str,
    force: bool,
    install_from_main: bool,
    config_path: str | None = None,
) -> None:
    """Set up automatic deployment to GitHub Pages.

    This command creates a GitHub Actions workflow that automatically builds
    and deploys your documentation when you push to the main branch.

    \b
    The workflow will:
    • Build docs on every push and pull request
    • Deploy to GitHub Pages on main branch pushes
    • Use Quarto's official GitHub Action for reliable builds
    • Install dev dependencies (auto-detected from your package manager)

    The Python version is automatically detected from your pyproject.toml's
    `requires-python` field. Use '--python-version' to override.

    The package manager is auto-detected by checking for lock files:
    • uv.lock -> uses uv (installs dev dependencies automatically)
    • poetry.lock -> uses poetry (installs with dev dependencies)
    • Otherwise -> uses pip with optional extras like [dev,docs]

    After running this command, commit the workflow file and enable GitHub
    Pages in your repository settings (Settings -> Pages ->
    Source: GitHub Actions).

    \b
    Examples:
      great-docs setup-github-pages                     # Auto-detect everything
      great-docs setup-github-pages --main-branch dev   # Deploy from 'dev' branch
      great-docs setup-github-pages --python-version 3.12
      great-docs setup-github-pages --package-manager uv
      great-docs setup-github-pages --force             # Overwrite existing workflow
      great-docs setup-github-pages --install-from-main # Use GitHub main branch
    """

    try:
        layout = Layout.make(
            Path(project_path or Path.cwd()), Path(config_path) if config_path else None
        )
        project_root = layout.package_root

        # Auto-detect Python version if not specified
        # Great Docs requires Python 3.11+, so we enforce that as the floor
        min_great_docs_version = (3, 11)
        if python_version is None:
            detected_version = _detect_python_version(project_root)
            if detected_version:
                detected_tuple = tuple(int(x) for x in detected_version.split("."))
                if detected_tuple < min_great_docs_version:
                    python_version = f"{min_great_docs_version[0]}.{min_great_docs_version[1]}"
                    click.echo(
                        f"📦 Project requires Python {detected_version}, "
                        f"but Great Docs needs >={python_version}; using {python_version}"
                    )
                else:
                    python_version = detected_version
                    click.echo(f"📦 Detected Python {python_version} from pyproject.toml")
            else:
                python_version = "3.12"
                click.echo("📦 Using default Python 3.12 (no requires-python found)")

        # Auto-detect package manager if not specified
        if package_manager == "auto":
            package_manager = _detect_package_manager(project_root)
            if package_manager == "uv":
                click.echo("🔧 Detected uv (found uv.lock)")
            elif package_manager == "poetry":
                click.echo("🔧 Detected poetry (found poetry.lock)")
            else:
                click.echo("🔧 Using pip (no uv.lock or poetry.lock found)")

        # Determine great-docs install source
        if install_from_main:
            great_docs_install = "git+https://github.com/posit-dev/great-docs.git"
            click.echo("📥 Will install Great Docs from GitHub main branch")
        else:
            great_docs_install = "great-docs"
            click.echo("📥 Will install Great Docs from PyPI (latest release)")

        # Generate install commands based on package manager
        if package_manager == "uv":
            install_commands = f"""\
          python -m pip install uv
          uv sync
          uv pip install {great_docs_install}"""
            build_command = "uv run great-docs build"
        elif package_manager == "poetry":
            install_commands = f"""\
          python -m pip install poetry
          poetry install
          poetry run pip install {great_docs_install}"""
            build_command = "poetry run great-docs build"
        else:
            # pip: try to detect optional dependencies
            optional_deps = _detect_optional_dependencies(project_root)
            if optional_deps:
                extras = ",".join(optional_deps)
                click.echo(f"📋 Found optional dependencies: {extras}")
                install_commands = f"""\
          python -m pip install --upgrade pip
          python -m pip install -e ".[{extras}]"
          python -m pip install {great_docs_install}"""
            else:
                install_commands = f"""\
          python -m pip install --upgrade pip
          python -m pip install -e .
          python -m pip install {great_docs_install}"""
            build_command = "great-docs build"

        if config_path:
            import shlex

            build_command += " --config " + shlex.quote(
                str(layout.config_path.relative_to(project_root))
            )

        # Create .github/workflows directory
        workflow_dir = project_root / ".github" / "workflows"
        workflow_file = workflow_dir / "docs.yml"

        # Check if workflow file already exists
        if workflow_file.exists() and not force:
            if not click.confirm(
                f"⚠️  Workflow file already exists at {workflow_file.relative_to(project_root)}\n"
                "   Overwrite it?",
                default=False,
            ):
                click.echo("❌ Aborted. Use --force to overwrite without prompting.")
                sys.exit(1)

        # Create directory structure
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Load template
        try:
            # For Python 3.9+
            from importlib.resources import files

            template_file = files("great_docs").joinpath("assets/github-workflow-template.yml")
            template_content = template_file.read_text()
        except (ImportError, AttributeError):
            # For Python 3.8 or earlier
            from importlib_resources import files

            template_file = files("great_docs").joinpath("assets/github-workflow-template.yml")
            template_content = template_file.read_text()

        # Replace placeholders (using replace() to handle linter-formatted templates)
        workflow_content = template_content.replace("{ main_branch }", main_branch)
        workflow_content = workflow_content.replace("{main_branch}", main_branch)
        workflow_content = workflow_content.replace("{ python_version }", python_version)
        workflow_content = workflow_content.replace("{python_version}", python_version)
        workflow_content = workflow_content.replace("{install_commands}", install_commands)
        workflow_content = workflow_content.replace("{build_command}", build_command)
        workflow_content = re.sub(
            r"(?<![\w/-])(?:great-docs|docs)/_site",
            lambda match: layout.site_dir.relative_to(project_root).as_posix(),
            workflow_content,
        )

        # Write workflow file
        _ = workflow_file.write_text(workflow_content)

        click.echo(
            f"✅ Created GitHub Actions workflow at {workflow_file.relative_to(project_root)}"
        )
        click.echo()
        click.echo("📋 Next steps:")
        click.echo("   1. Commit and push the workflow file to your repository")
        click.echo("   2. Go to your repository Settings → Pages")
        click.echo("   3. Set Source to 'GitHub Actions' (or 'gh-pages branch' if using that)")
        click.echo(f"   4. Push changes to '{main_branch}' branch to trigger deployment")
        click.echo()
        click.echo("💡 The workflow will:")
        click.echo(f"   • Build docs on every push to '{main_branch}' and pull requests")
        click.echo("   • Automatically deploy to GitHub Pages on main branch")
        click.echo("   • Comment on pull requests with a 'great-docs preview' command")

    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command(name="setup-gitlab-pages")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to the project root (default: current directory)",
)
@click.option(
    "--main-branch",
    default=None,
    help="Deployment branch (default: GitLab's CI_DEFAULT_BRANCH)",
)
@click.option(
    "--python-version",
    default=None,
    help="Python version for CI (default: project requirement, at least 3.11)",
)
@click.option(
    "--package-manager",
    type=click.Choice(["auto", "pip", "uv", "poetry"]),
    default="auto",
    help="Dependency environment (default: detect uv/Poetry lock files, otherwise uv pip)",
)
@click.option("--force", is_flag=True, help="Replace an existing .gitlab-ci.yml")
@_options.config_option
def setup_gitlab_pages(
    project_path: str | None,
    main_branch: str | None,
    python_version: str | None,
    package_manager: str,
    force: bool,
    config_path: str | None = None,
) -> None:
    """
    Create GitLab Pages and merge-request documentation jobs

    Require GitLab 17.10 or newer and a Linux Docker runner. Publish Pages on
    default-branch pushes and retain merge-request builds as ordinary artefacts.
    Print a mergeable snippet when a pipeline already exists; use `--force` to
    replace it. Install Quarto and dependencies with the detected environment.

    Parameters
    ----------
    project_path
        Project directory, or the current directory when omitted.
    main_branch
        Deployment branch, or GitLab's configured default branch when omitted.
    python_version
        Python image version, or the detected project requirement with a 3.11 floor.
    package_manager
        Dependency environment: `auto`, `pip`, `uv` or `poetry`.
    force
        Whether to replace an existing pipeline file.
    config_path
        Selected configuration file, resolved from the current directory.
    """
    from importlib.resources import files

    try:
        layout = Layout.make(
            Path(project_path or Path.cwd()), Path(config_path) if config_path else None
        )
        project_root = layout.package_root
        if python_version is None:
            detected = _detect_python_version(project_root) or "3.12"
            parts = max((3, 11), tuple(map(int, detected.split("."))))
            python_version = ".".join(map(str, parts))
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", python_version):
            raise click.BadParameter(
                "Use a Python version such as 3.12", param_hint="--python-version"
            )
        if tuple(map(int, python_version.split("."))) < (3, 11):
            raise click.BadParameter(
                "Great Docs requires Python 3.11 or newer", param_hint="--python-version"
            )

        if package_manager == "auto":
            package_manager = _detect_package_manager(project_root)
        if package_manager == "uv":
            install_commands = ["uv sync", "uv pip install great-docs"]
            build_command = "uv run --no-sync great-docs build"
        elif package_manager == "poetry":
            install_commands = [
                "UV_TOOL_BIN_DIR=/usr/local/bin uv tool install poetry --force",
                "poetry install",
                'uv pip install --python "$(poetry env info --executable)" great-docs',
            ]
            build_command = "poetry run great-docs build"
        else:
            extras = _detect_optional_dependencies(project_root)
            package = f".[{','.join(extras)}]" if extras else "."
            install_commands = ["uv venv", f"uv pip install -e {shlex.quote(package)} great-docs"]
            build_command = "uv run --no-sync great-docs build"

        report_command = build_command.removesuffix(" build")
        selected_config = layout.load_config()
        base_option = (
            " --repo-base-url " + shlex.quote(selected_config.repo_base_url)
            if selected_config.repo_base_url
            else ""
        )

        if config_path:
            build_command += " --config " + shlex.quote(
                layout.config_path.relative_to(project_root).as_posix()
            )
        branch = json.dumps(main_branch) if main_branch is not None else "$CI_DEFAULT_BRANCH"
        deploy_rule = f'$CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH == {branch}'
        template = (
            files("great_docs")
            .joinpath("assets/gitlab-ci-template.yml")
            .read_text(encoding="utf-8")
        )
        replacements = {
            "python_image": json.dumps(f"python:{python_version}-bookworm"),
            "install_commands": "\n".join(f"      {command}" for command in install_commands),
            "build_command": json.dumps(build_command),
            "site_dir": json.dumps(layout.site_dir.relative_to(project_root).as_posix()),
            "deploy_rule": json.dumps(deploy_rule),
            "report_command": report_command,
            "base_option": base_option,
        }
        for key, value in replacements.items():
            template = template.replace("{" + key + "}", value)

        pipeline_file = project_root / ".gitlab-ci.yml"
        if pipeline_file.exists() and not force:
            click.echo("Existing .gitlab-ci.yml preserved. Merge these jobs into your pipeline:")
            click.echo(template)
            click.echo("Add build to a custom stages list, or select an existing stage.")
            click.echo("Use --force to replace .gitlab-ci.yml instead.")
            return
        _ = pipeline_file.write_text(template, encoding="utf-8")
        click.echo(f"Created .gitlab-ci.yml with Python {python_version} and {package_manager}.")
        click.echo("Require GitLab 17.10 or newer and a Linux Docker runner.")
        click.echo(
            "Review and commit the pipeline, then check Deploy > Pages after a default-branch push."
        )
        click.echo("Merge-request builds retain artefacts without deploying production Pages.")
    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


ci.add_command(ci_pr_comment)
ci.add_command(ci_notice)

ci.add_command(ci_mr_comment)
ci.add_command(ci_gitlab_notice)
