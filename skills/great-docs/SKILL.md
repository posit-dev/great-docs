---
name: great-docs
description: >
  Generate documentation sites for Python packages with Great Docs.
  Covers init, build, preview, configuration (great-docs.yml), API
  reference, CLI docs, user guides, theming, deployment, and the
  llms.txt agent-context files. Use when creating, configuring,
  building, or troubleshooting Python package documentation.
license: MIT
compatibility: Requires Python >=3.11, Quarto CLI installed.
metadata:
  author: rich-iannone
  version: "2.0"
  tags:
    - documentation
    - python-packages
    - quarto
    - api-reference
    - static-site
---

# Great Docs

A docs generator for Python packages. Introspects your API, renders
reference pages, and produces a Quarto-based static site with user
guides, CLI docs, theming, and more.

## Quick start

```bash
pip install great-docs
# Quarto must also be installed: https://quarto.org/docs/get-started/

cd my-package/        # directory with pyproject.toml
great-docs init       # create great-docs.yml, discover API
great-docs build      # full build -> great-docs/_site/
great-docs preview    # local server on port 3000
```

## Skill directory structure

This skill ships with companion files for agent consumption:

```
skills/great-docs/
├── SKILL.md                ← This file
├── references/
│   ├── config-reference.md ← All great-docs.yml options
│   ├── cli-reference.md    ← CLI commands and arguments
│   └── common-errors.md    ← Error patterns and fixes
├── scripts/
│   ├── setup-env.sh        ← Environment bootstrap script
│   └── run-build.sh        ← Build with validation
└── assets/
    └── config-template.yaml ← Starter great-docs.yml
```

## When to use what

| Need                      | Use                                     |
| ------------------------- | --------------------------------------- |
| Start a new docs site     | `great-docs init`                       |
| Full build from scratch   | `great-docs build`                      |
| Rebuild after edits       | `great-docs build --no-refresh`         |
| Live preview              | `great-docs preview`                    |
| See discoverable API      | `great-docs scan --verbose`             |
| Change docstring parser   | `parser: google` in great-docs.yml      |
| Add CLI reference         | `cli: {enabled: true, module: pkg.cli}` |
| Add a gradient navbar     | `navbar_style: sky`                     |
| Exclude internal symbols  | `exclude: [_InternalClass]`             |
| Add user guide pages      | Create `user_guide/05-topic.qmd`        |
| Add recipes               | Create `recipes/07-topic.qmd`           |
| Set up GitHub Pages CI    | `great-docs setup-github-pages`         |
| Use static analysis       | `dynamic: false` (for tricky imports)   |
| Generate agent skill file | `skill: {enabled: true}`                |

## Core concepts

### Configuration (`great-docs.yml`)

Single YAML file at the project root controls everything. All keys
are optional — sensible defaults are auto-detected from
`pyproject.toml` and package structure.

**Full config reference**: See [references/config-reference.md](references/config-reference.md)

### Build pipeline

The `build` command runs 13 steps in order:

1. Prepare build directory (copy assets, JS, SCSS)
2. Copy user guide from `user_guide/`
3. Copy project `assets/`
4. Refresh API reference (introspect package)
5. Generate `llms.txt` and `llms-full.txt`
6. Generate `skill.md` (if enabled)
7. Generate source links JSON
8. Generate changelog (from GitHub Releases)
9. Generate CLI reference (if enabled)
10. Process user guide (frontmatter, sidebar)
11. Process custom sections
12. Render API reference (`.qmd` files)
13. Run `quarto render` -> `_site/` HTML output

The `great-docs/` directory is **ephemeral** — regenerated on every
build. Never edit files inside it directly.

### Two rendering modes

- **Dynamic** (default): imports the package at runtime for full
  introspection. Requires `pip install -e .` first.
- **Static** (`dynamic: false`): uses griffe for AST-based analysis.
  Use when the package has circular imports, lazy loading, or
  compiled extensions.

Dynamic mode auto-falls-back to static if the import fails.

### Docstring directives

Custom directives inside docstrings use `%` prefix:

```python
def my_function():
    """
    Description.

    %seealso func_a, func_b: related functions, ClassC
    %nodoc
    """
```

- `%seealso name1, name2: desc` — Cross-references in rendered docs
- `%nodoc` — Exclude this item from documentation

## Workflows

### New documentation site

```
Task Progress:
- [ ] Step 1: Install prerequisites
- [ ] Step 2: Initialize configuration
- [ ] Step 3: Customize config
- [ ] Step 4: Build and preview
- [ ] Step 5: Verify output
```

**Step 1**: Ensure `great-docs` and `quarto` are installed. The
target package must be importable (`pip install -e .`).

**Step 2**: Run `great-docs init` from the project root (where
`pyproject.toml` lives). This creates `great-docs.yml`.

**Step 3**: Edit `great-docs.yml` to customize. See
[references/config-reference.md](references/config-reference.md) or
[assets/config-template.yaml](assets/config-template.yaml) for all
options.

**Step 4**: Run `great-docs build` then `great-docs preview`.

**Step 5**: Check the site at `http://localhost:3000`. If errors
occur, see [references/common-errors.md](references/common-errors.md).

### Adding content

**User guide page**: Create `user_guide/NN-title.qmd` with a
2-digit numeric prefix. Auto-discovered on next build.

**Recipe**: Create `recipes/NN-title.qmd`. Same numeric prefix
convention.

**Custom section**: Add to `great-docs.yml`:

```yaml
sections:
  - title: Examples
    dir: examples
```

### Customizing appearance

```yaml
# great-docs.yml
navbar_style: sky # gradient: sky, peach, lilac, mint, etc.
content_style: lilac # content area glow
dark_mode_toggle: true # toggle switch in navbar
logo: assets/logo.svg # or {light: ..., dark: ...}
hero: true # landing page hero section
announcement:
  content: "v2 is out!"
  type: info
  dismissable: true
```

### Troubleshooting a build

1. Run `great-docs build` and read the error output
2. Check [references/common-errors.md](references/common-errors.md) for
   the error pattern
3. Fix the config or source file
4. Rebuild with `great-docs build --no-refresh` (faster, skips API
   rediscovery)
5. If the error persists, try `great-docs build` with full refresh

## Reference files

### Config reference (`references/config-reference.md`)

Complete list of every `great-docs.yml` option with types, defaults,
and examples. Organized by category: metadata, GitHub, navigation,
theming, content, features, and advanced.

### CLI reference (`references/cli-reference.md`)

All CLI commands with arguments and usage examples:

| Command              | Purpose                     |
| -------------------- | --------------------------- |
| `init`               | Create config, discover API |
| `build`              | Full build pipeline         |
| `preview`            | Local dev server            |
| `scan`               | Preview discoverable API    |
| `config`             | Generate template config    |
| `uninstall`          | Remove config and build dir |
| `setup-github-pages` | Create CI/CD workflow       |

### Common errors (`references/common-errors.md`)

Error patterns, causes, and fixes for the most frequent build
failures — import errors, missing exports, config mismatches,
Quarto issues, and more.

## Scripts

### `scripts/setup-env.sh`

Bootstrap a development environment:

```bash
#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install great-docs
quarto --version || echo "ERROR: Quarto not installed"
```

### `scripts/run-build.sh`

Build with validation:

```bash
#!/usr/bin/env bash
set -euo pipefail
great-docs build
echo "Build complete. Site at great-docs/_site/"
ls great-docs/_site/index.html && echo "OK: index.html exists"
```

## Configuration template

The `assets/config-template.yaml` provides a starter config with
annotated options. Copy it as `great-docs.yml` and customize.

## Gotchas

1. **Run from project root.** All commands must run from the
   directory containing `great-docs.yml` (and `pyproject.toml`).
2. **`module` vs package name.** The `module` key is the Python
   importable name, not the PyPI name. For `py-shiny`, set
   `module: shiny`.
3. **Circular imports.** Set `dynamic: false` for packages with
   lazy loading or circular aliases.
4. **User guide ordering.** Files need numeric prefixes
   (`00-intro.qmd`, `01-install.qmd`) for deterministic order.
5. **Don't edit `great-docs/` directly.** It's regenerated on every
   build. Edit source files instead.
6. **Quarto required.** If `quarto` is not on `PATH`, the build
   fails at step 13.
7. **Package must be importable.** In dynamic mode, run
   `pip install -e .` before building.

## Capabilities and boundaries

**What agents can configure:**

- All `great-docs.yml` settings
- User guide `.qmd` pages in `user_guide/`
- Recipe `.qmd` pages in `recipes/`
- Custom section `.qmd` pages
- Logo, favicon, and other assets
- Custom CSS/SCSS overrides
- Docstring directives (`%seealso`, `%nodoc`)

**Requires human setup:**

- `pip install great-docs` and Quarto installation
- `pip install -e .` for the target package
- GitHub Pages or hosting deployment
- Custom domain DNS
- GitHub access tokens (for changelog)

## Resources

- [Full documentation](https://posit-dev.github.io/great-docs/)
- [llms.txt](llms.txt) — Indexed API reference for LLMs
- [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs
- [Configuration guide](https://posit-dev.github.io/great-docs/user-guide/03-configuration.html)
- [GitHub repository](https://github.com/posit-dev/great-docs)
