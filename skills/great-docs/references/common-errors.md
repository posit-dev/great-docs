# Common Errors — great-docs

## Contents

- Import and discovery errors
- Configuration errors
- Build and rendering errors
- Quarto errors
- Deployment errors

## Import and discovery errors

### `Cannot find an object named X`

**Cause**: Object listed in API config but not exported from `__init__.py`.

**Fix**: Add `from .module import X` to the package's `__init__.py`.

### `dynamic: true` fails with ImportError

**Cause**: Package is not importable in the current environment.

**Fix**: Run `pip install -e .` in the project root, or set
`dynamic: false` in `great-docs.yml` to use static analysis.

### No API items discovered

**Cause**: Package has no public exports in `__init__.py`.

**Fix**: Ensure public classes and functions are imported in
`__init__.py` or listed in `__all__`.

### Wrong items documented

**Cause**: Re-exported third-party symbols treated as own API.

**Fix**: Add unwanted items to `exclude` list in `great-docs.yml`:

```yaml
exclude:
  - ThirdPartyClass
  - imported_helper
```

## Configuration errors

### `module` not found

**Cause**: `module` key doesn't match the importable package name.

**Fix**: Use the Python import name, not the PyPI install name.
For `pip install py-shiny`, set `module: shiny`.

### Parser mismatch (garbled docstrings)

**Cause**: Docstring style doesn't match `parser` setting.

**Fix**: Set `parser` to match your docstrings:

```yaml
parser: numpy    # Parameters\n----------\narg : type
parser: google   # Args:\n    arg (type): desc
parser: sphinx   # :param arg: desc\n:type arg: type
```

### CLI reference not generated

**Cause**: `cli.module` points to wrong module or the Click app
isn't findable.

**Fix**: Verify `cli.module` and `cli.name`:

```yaml
cli:
  enabled: true
  module: my_package.cli # must contain a Click group/command
  name: my-cli # the CLI entry point name
```

## Build and rendering errors

### `great-docs/` directory has stale content

**Cause**: Edited files inside `great-docs/` directly.

**Fix**: Delete `great-docs/` and rebuild. Never edit the build
directory — it's overwritten on every build.

### User guide pages in wrong order

**Cause**: Missing or inconsistent numeric prefixes.

**Fix**: Use 2-digit prefixes: `00-intro.qmd`, `01-install.qmd`,
`02-quickstart.qmd`. Gaps are fine (`00`, `05`, `10`).

### Missing cross-references

**Cause**: `%seealso` directive references items not in the API.

**Fix**: Ensure referenced items are exported and not in `exclude`.

### Source links point to wrong branch

**Cause**: `source.branch` doesn't match the repository default.

**Fix**:

```yaml
source:
  branch: main # or "master", "develop", etc.
```

## Quarto errors

### `quarto: command not found`

**Cause**: Quarto is not installed or not on PATH.

**Fix**: Install from https://quarto.org/docs/get-started/ and
ensure `quarto --version` works in the terminal.

### Quarto render fails with YAML error

**Cause**: Generated `_quarto.yml` has invalid syntax, usually
from special characters in config values.

**Fix**: Check `great-docs.yml` for unquoted special characters.
Wrap values with colons, brackets, or quotes in double quotes:

```yaml
announcement:
  content: "Version 2.0: now with more features!"
```

### Quarto render fails with missing bibliography

**Cause**: `.qmd` files reference a .bib file that doesn't exist.

**Fix**: Remove the `bibliography` field from .qmd frontmatter or
create the referenced `.bib` file.

## Deployment errors

### GitHub Pages shows 404

**Cause**: Workflow deploys from wrong directory or branch.

**Fix**: Run `great-docs setup-github-pages` to regenerate the
workflow. Ensure GitHub Pages is configured to deploy from
GitHub Actions (Settings → Pages → Source → GitHub Actions).

### Site URL incorrect in links

**Cause**: `site-url` not set in Quarto config.

**Fix**: Great Docs auto-detects this from `pyproject.toml` URLs.
Add a `Documentation` URL:

```toml
[project.urls]
Documentation = "https://my-org.github.io/my-package/"
```

### Changelog empty

**Cause**: No GitHub Releases exist, or `GITHUB_TOKEN` not
available in CI.

**Fix**: Create at least one GitHub Release, or set
`changelog: {enabled: false}` to disable.
