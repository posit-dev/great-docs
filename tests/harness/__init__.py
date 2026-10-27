"""
Characterisation harness for site initialisation, builds, watch mode and freezing

The harness compares a base commit with the checkout under test by running `great-docs
init`, `build`, `build --watch` and `freeze` on Gauntlet packages. A stub `quarto` skips
rendering, so a build takes about a second. Each command runs in a separate process through
the command-line interface; the harness never imports `great_docs`.

Run it from the repository root of a checkout whose `.venv` was created with
`env -u VIRTUAL_ENV uv sync --extra dev --frozen`:

```sh
make harness                       # base `main`, 40 cases
make harness-full                  # every Gauntlet package and its variants
make harness HARNESS_ARGS="--base HEAD~1 --only gdtest_minimal"
```

The exit status is 0 when every case matches and passes its checks, and 1 on any difference
or failed check. Status 2 means the harness refused to run: a required tool (`d2`, `ruff`,
`quarto`, `git` or `uv`) is missing, environments differ, or a recording uses another manifest
schema. Known gaps appear in a separate report section without changing the exit status.

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
