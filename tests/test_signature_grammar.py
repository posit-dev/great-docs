import importlib.util
from pathlib import Path

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
