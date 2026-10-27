"""
Characterisation harness for `great-docs init` and `great-docs build`

The harness compares the output of Gauntlet packages built with a base commit and the
checkout under test. A stub `quarto` skips rendering, so a build takes about a second. Each
command runs in a separate process through the command-line interface; the harness never
imports `great_docs`.

Run it from the repository root of a checkout whose `.venv` was created with
`env -u VIRTUAL_ENV uv sync --extra dev --frozen`:

```sh
make harness                       # base `main`, 34 cases
make harness-full                  # every Gauntlet package
make harness HARNESS_ARGS="--base HEAD~1 --only gdtest_minimal"
```

The exit status is 0 when every case matches, 1 on any difference and 2 when the harness
refuses to run (a missing `d2`, `ruff`, `quarto` or `uv`, or environments that differ).

The cache directory must be outside any Git repository. Choose it with `--cache-dir`;
otherwise the harness uses `$GREAT_DOCS_HARNESS_CACHE`, then
`$XDG_CACHE_HOME/great-docs-harness`, then `~/.cache/great-docs-harness`. Unless `--out`
selects another destination for recordings and reports, the cache holds all output:

- `worktrees/<sha>`: a detached worktree of each base commit with its own virtual environment,
  reused by later runs and never deleted by the harness. Remove one with
  `git worktree remove <path>`;
- `runs/<timestamp>-<pid>`: each run's recordings, `report.txt` and `report.json`;
- `work/`: generated packages and job directories, deleted at the end of each run unless
  `--keep` is given.
"""
