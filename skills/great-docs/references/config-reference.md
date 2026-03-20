# Configuration Reference — great-docs.yml

## Contents

- Metadata and package info
- GitHub and source links
- Navigation and theming
- Logo, favicon, and hero
- Content organization
- Features
- Advanced

All keys are optional. Defaults are auto-detected from `pyproject.toml`.

## Metadata and package info

| Key            | Type        | Default       | Description                                             |
| -------------- | ----------- | ------------- | ------------------------------------------------------- |
| `module`       | `str`       | auto-detected | Python importable name (not PyPI name)                  |
| `display_name` | `str`       | package name  | Custom site title                                       |
| `parser`       | `str`       | `"numpy"`     | Docstring style: `"numpy"`, `"google"`, `"sphinx"`      |
| `dynamic`      | `bool`      | `true`        | `true`: runtime introspection; `false`: static (griffe) |
| `exclude`      | `list[str]` | `[]`          | Items to hide from API docs                             |

## GitHub and source links

| Key                | Type   | Default       | Description                          |
| ------------------ | ------ | ------------- | ------------------------------------ |
| `repo`             | `str`  | auto-detected | GitHub repository URL                |
| `github_style`     | `str`  | `"widget"`    | `"widget"` (shows stars) or `"icon"` |
| `source.enabled`   | `bool` | `true`        | Show "View source" links             |
| `source.branch`    | `str`  | `"main"`      | Git branch for source links          |
| `source.path`      | `str`  | auto-detected | Path to package source               |
| `source.placement` | `str`  | `"repo"`      | Where source links point             |

## Navigation and theming

| Key                | Type            | Default | Description                                                                              |
| ------------------ | --------------- | ------- | ---------------------------------------------------------------------------------------- |
| `navbar_style`     | `str`           | none    | Gradient preset: `"sky"`, `"peach"`, `"lilac"`, `"slate"`, `"honey"`, `"dusk"`, `"mint"` |
| `navbar_color`     | `str` or `dict` | none    | Solid color: `"#1a1a2e"` or `{light: "#fff", dark: "#1a1a2e"}`                           |
| `content_style`    | `str` or `dict` | none    | Content glow: `"lilac"` or `{preset: "sky", pages: "homepage"}`                          |
| `dark_mode_toggle` | `bool`          | `true`  | Dark mode toggle in navbar                                                               |
| `attribution`      | `bool`          | `true`  | "Built with Great Docs" footer                                                           |

## Logo, favicon, and hero

| Key       | Type             | Default        | Description                                                 |
| --------- | ---------------- | -------------- | ----------------------------------------------------------- |
| `logo`    | `str` or `dict`  | auto-detected  | Logo path or `{light: ..., dark: ...}`                      |
| `favicon` | `str`            | auto-generated | Favicon path (generated from logo if SVG)                   |
| `hero`    | `bool` or `dict` | auto           | Hero section on homepage. `{enabled: true, tagline: "..."}` |

Logo auto-detection looks for `assets/logo.svg`, `assets/logo-dark.svg`, etc.

## Content organization

| Key          | Type           | Default       | Description                                             |
| ------------ | -------------- | ------------- | ------------------------------------------------------- |
| `homepage`   | `str`          | `"index"`     | `"index"` (README) or `"user_guide"` (first guide page) |
| `user_guide` | auto or `dict` | auto-discover | User guide content source                               |
| `reference`  | auto or `list` | auto-discover | API reference sections                                  |
| `sections`   | `list[dict]`   | `[]`          | Custom pages: `[{title: "Examples", dir: "examples"}]`  |

## Features

| Key                        | Type   | Default | Description                             |
| -------------------------- | ------ | ------- | --------------------------------------- |
| `cli.enabled`              | `bool` | `false` | Generate CLI reference from Click app   |
| `cli.module`               | `str`  | —       | Module containing the Click app         |
| `cli.name`                 | `str`  | —       | CLI command name                        |
| `changelog.enabled`        | `bool` | `true`  | Generate changelog from GitHub Releases |
| `markdown_pages`           | `bool` | `false` | Generate downloadable `.md` pages       |
| `sidebar_filter.enabled`   | `bool` | `true`  | Search/filter in API reference sidebar  |
| `sidebar_filter.min_items` | `int`  | `10`    | Minimum items to show filter box        |
| `skill.enabled`            | `bool` | `false` | Generate SKILL.md for agent consumption |
| `skill.file`               | `str`  | —       | Path to hand-written SKILL.md           |

## Advanced

| Key                 | Type            | Default         | Description                                                                         |
| ------------------- | --------------- | --------------- | ----------------------------------------------------------------------------------- |
| `announcement`      | `str` or `dict` | none            | Banner: `"text"` or `{content: "...", type: "info", dismissable: true, url: "..."}` |
| `authors`           | `list[dict]`    | `[]`            | Author metadata: `{name, affiliation, github, orcid}`                               |
| `funding`           | `dict`          | none            | Funding/copyright: `{funder: "...", award: "..."}`                                  |
| `include_in_header` | `list[str]`     | `[]`            | Custom HTML/CSS/JS includes                                                         |
| `site`              | `dict`          | Quarto defaults | Quarto theme, TOC, grid settings                                                    |
| `jupyter`           | `str`           | `"python3"`     | Jupyter kernel for executable code cells                                            |

## Example: minimal config

```yaml
# great-docs.yml
parser: numpy
```

## Example: fully customized config

```yaml
# great-docs.yml
module: my_package
display_name: My Package
parser: google
dynamic: true
exclude:
  - _InternalClass
  - _helper_fn

navbar_style: sky
content_style: lilac
dark_mode_toggle: true

logo:
  light: assets/logo.svg
  dark: assets/logo-dark.svg
hero:
  enabled: true
  tagline: "Beautiful documentation for Python"

announcement:
  content: "v2.0 released!"
  type: info
  dismissable: true

cli:
  enabled: true
  module: my_package.cli
  name: my-cli

changelog:
  enabled: true

sections:
  - title: Examples
    dir: examples

skill:
  enabled: true
```
