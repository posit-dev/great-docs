"""
Comparison of the Quarto projects that two commits of great-docs write

A Quarto project is the directory holding `_quarto.yml` and its sources: the `.qmd` pages,
scripts, stylesheets and data files that great-docs writes before Quarto renders anything.
The tool runs `great-docs init`, `build`, `build --watch` and `freeze` on Gauntlet packages,
once with a base commit and once with the checkout under test, and compares every file each
command writes. It also compares exit statuses, build steps, logged warnings, handled
exceptions, process counts and calls to `quarto`. A stub `quarto` skips rendering, so a build
takes about a second. Each command runs in a separate process through the command-line
interface; the tool never imports `great_docs`.

Run it from the repository root of a checkout whose `.venv` was created with
`env -u VIRTUAL_ENV uv sync --extra dev --frozen`:

```sh
make quarto-project-diff          # base `main`, 40 cases
make quarto-project-diff-full     # every Gauntlet package and its variants
make quarto-project-diff QUARTO_PROJECT_DIFF_ARGS="--base HEAD~1 --only gdtest_minimal"
make quarto-project-diff QUARTO_PROJECT_DIFF_ARGS="--fail-on difference"
```

Every difference is reported. The exit status is 1 on a regression: a failed check, a command
that now exits with a non-zero status, a command or case recorded on one side only, or
environments that differ. Other differences, such as changed files or new warnings, leave the
exit status at 0, since a change can alter output on purpose; `--fail-on difference` makes
them fail too, for changes that should leave the output alone. Status 2 means the tool refused to run: a
required tool (`d2`, `ruff`, `quarto`, `git` or `uv`) is missing, environments differ, or a
recording uses another manifest schema. Known gaps appear in a separate report section without
changing the exit status.

The cache directory must be outside any Git repository. Choose it with `--cache-dir`;
otherwise the tool uses `$GREAT_DOCS_QUARTO_PROJECT_DIFF_CACHE`, then
`$XDG_CACHE_HOME/great-docs-quarto-project-diff`, then
`~/.cache/great-docs-quarto-project-diff`. Unless `--out` selects another destination for
recordings and reports, the cache holds all output:

- `worktrees/<sha>`: a detached worktree of each base commit with its own virtual environment,
  reused by later runs and never deleted by the tool. Remove one with
  `git worktree remove <path>`;
- `runs/<timestamp>-<pid>`: each run's recordings, `report.txt` and `report.json`;
- `work/`: generated packages and job directories, deleted at the end of each run unless
  `--keep` is given.
"""
