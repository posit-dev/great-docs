# CLI Reference — great-docs

## Contents

- Global options
- init
- build
- preview
- scan
- config
- uninstall
- setup-github-pages

All commands accept `--project-path PATH` to target a different directory.

## Global options

```
great-docs [OPTIONS] COMMAND [ARGS]
```

| Option                | Description                                       |
| --------------------- | ------------------------------------------------- |
| `--project-path PATH` | Path to project root (default: current directory) |
| `--version`           | Show version and exit                             |
| `--help`              | Show help and exit                                |

## init

One-time setup: create `great-docs.yml` and auto-discover API.

```bash
great-docs init
great-docs init --force   # reset existing config
```

| Option    | Description                         |
| --------- | ----------------------------------- |
| `--force` | Overwrite existing `great-docs.yml` |

Creates `great-docs.yml` with detected package name, module, parser
style, and API sections. Safe to run multiple times (no-op if config
exists unless `--force`).

## build

Full build pipeline: prepare → render → build HTML.

```bash
great-docs build
great-docs build --no-refresh   # skip API rediscovery (faster)
great-docs build --watch        # rebuild on file changes
```

| Option         | Description                                  |
| -------------- | -------------------------------------------- |
| `--watch`      | Watch for changes and rebuild incrementally  |
| `--no-refresh` | Skip API reference rediscovery (uses cached) |

Output goes to `great-docs/_site/`. Build streams progress in
real-time.

## preview

Start a local development server.

```bash
great-docs preview
great-docs preview --port 8080
```

| Option   | Default | Description |
| -------- | ------- | ----------- |
| `--port` | `3000`  | Server port |

Serves `great-docs/_site/` with live reload. Run `build` first if
the site doesn't exist yet.

## scan

Preview which API items will be documented.

```bash
great-docs scan
great-docs scan --verbose   # show methods and attributes
```

| Option      | Description                               |
| ----------- | ----------------------------------------- |
| `--verbose` | Show member details (methods, attributes) |

Useful for verifying what `great-docs init` will discover before
committing to a build.

## config

Generate a template `great-docs.yml`.

```bash
great-docs config
great-docs config --force   # overwrite existing
```

| Option    | Description                    |
| --------- | ------------------------------ |
| `--force` | Overwrite existing config file |

Similar to `init` but only creates the config file without
running any discovery or setup.

## uninstall

Remove `great-docs.yml` and the `great-docs/` build directory.

```bash
great-docs uninstall
```

Preserves source files (`user_guide/`, `recipes/`, `assets/`).

## setup-github-pages

Create a GitHub Actions workflow for automated deployment.

```bash
great-docs setup-github-pages
great-docs setup-github-pages --main-branch main --python-version 3.12
```

| Option             | Default  | Description                     |
| ------------------ | -------- | ------------------------------- |
| `--main-branch`    | `"main"` | Branch that triggers deployment |
| `--python-version` | `"3.12"` | Python version in CI            |
| `--force`          | —        | Overwrite existing workflow     |

Creates `.github/workflows/docs.yml` configured for GitHub Pages
deployment with proper caching and Quarto installation.
