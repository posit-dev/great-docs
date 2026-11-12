"""
Run `version-selector.js` with Node in a stub page

`run_selector` loads a copy of the script and reports what `window.greatDocsVersions`
answers and which links the selector and its banner built. See
`tests/js/version_selector_harness.js` for the options and the report.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "great_docs" / "assets" / "version-selector.js"
HARNESS = ROOT / "tests" / "js" / "version_selector_harness.js"


def run_selector(script: Path = SCRIPT, **options: Any) -> dict[str, Any]:
    """
    Run the version selector in a stub page

    Parameters
    ----------
    script
        The copy of `version-selector.js` to run, by default the packaged one.
    **options
        The harness options, such as `map`, `pathname` and `offset`.

    Returns
    -------
    :
        What the harness observed.
    """
    completed = subprocess.run(
        ["node", str(HARNESS), str(script), json.dumps(options)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)
