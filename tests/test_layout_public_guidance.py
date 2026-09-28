"""Keep public command examples and deployment templates on the default layout"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from great_docs.cli import cli


@pytest.mark.parametrize("command", ["init", "build", "preview", "config", "uninstall", "freeze"])
def test_help_uses_documentation_paths(command: str) -> None:
    result = CliRunner().invoke(cli, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "great-docs/_site" not in result.output
    assert "'great-docs/'" not in result.output
    assert "docs/" in result.output
    assert "--config" in result.output


def test_workflow_template_deploys_default_layout() -> None:
    template = Path(__file__).parents[1] / "great_docs/assets/github-workflow-template.yml"
    text = template.read_text()
    assert "great-docs/_site" not in text
    assert "path: docs/_site\n" in text
    assert "path: docs/_site/build-timings.json" in text
