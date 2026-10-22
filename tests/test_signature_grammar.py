import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "make_signature_grammar.py"
GRAMMAR = REPO / "great_docs" / "assets" / "pythonsignature.xml"


def test_committed_grammar_matches_generator():
    spec = importlib.util.spec_from_file_location("make_signature_grammar", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # A mismatch means Pygments changed or the file was edited by hand.
    assert module.make_grammar() == GRAMMAR.read_text(encoding="utf-8"), (
        "great_docs/assets/pythonsignature.xml is out of date; run `make signature-grammar`"
    )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_grammar_highlights_non_ascii_names():
    """A name with non-ASCII letters is one token, classed like an ASCII name"""
    fence = "```pythonsignature\ncafé(naïve=None)\nKlaß.méthode(x)\n```\n"
    html = subprocess.run(
        ["quarto", "pandoc", "-t", "html", f"--syntax-definition={GRAMMAR}"],
        input=fence,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    tokens = re.findall(r'<span class="(\w+)">([^<]*)</span>', html)

    assert ("fu", "café") in tokens
    assert ("va", "naïve") in tokens
    assert ("dt", "Klaß") in tokens
    assert ("fu", "méthode") in tokens
