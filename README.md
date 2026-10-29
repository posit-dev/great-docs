<p align="center">
<a href="https://posit-dev.github.io/great-docs/">
<img src="https://posit-dev.github.io/great-docs/assets/logo.svg" alt="Great Docs" width="350">
</a>
</p>
<p align="center">Documentation sites for Python packages: start simple, go deep</p>
<p align="center">
<a href="https://pypi.org/project/great-docs/"><img src="https://img.shields.io/pypi/v/great-docs?logo=python&logoColor=white&color=orange" alt="PyPI"></a>
<a href="https://pypi.org/project/great-docs/"><img src="https://img.shields.io/pypi/pyversions/great-docs.svg" alt="Python versions"></a>
<a href="https://pypistats.org/packages/great-docs"><img src="https://img.shields.io/pypi/dm/great-docs" alt="Downloads"></a>
<a href="https://choosealicense.com/licenses/mit/"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
<a href="https://github.com/posit-dev/great-docs/actions/workflows/test.yml"><img src="https://github.com/posit-dev/great-docs/actions/workflows/test.yml/badge.svg?branch=main" alt="CI"></a>
</p>
<p align="center">
<a href="https://www.repostatus.org/#active"><img src="https://www.repostatus.org/badges/latest/active.svg" alt="Repo Status"></a>
<a href="https://posit-dev.github.io/gdg/"><img src="https://img.shields.io/badge/Great%20Docs%20Gauntlet-300%2B%20test%20sites-7c3aed?logo=pytest&logoColor=white" alt="Great Docs Gauntlet"></a>
</p>
<p align="center">
<a href="https://posit-dev.github.io/great-docs/"><img src="https://img.shields.io/badge/docs-project_website-blue.svg" alt="Documentation"></a>
<a href="https://github.com/posit-dev/great-docs/graphs/contributors"><img src="https://img.shields.io/github/contributors/posit-dev/great-docs" alt="Contributors"></a>
<a href="https://deepwiki.com/posit-dev/great-docs"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
<a href="https://www.contributor-covenant.org/version/3/0/"><img src="https://img.shields.io/badge/Contributor%20Covenant-v3.0%20adopted-ff69b4.svg" alt="Contributor Covenant"></a>
</p>
<p align="center">
<a href="#get-started-in-60-seconds">Quickstart</a> ·
<a href="#full-feature-set">Features</a> ·
<a href="#configuration">Configuration</a> ·
<a href="#recipes">Recipes</a> ·
<a href="https://posit-dev.github.io/great-docs/">Docs</a>
</p>

---

> [!TIP]
> **📺 Featured on Talk Python:** [**the "Great Docs" live stream**](https://www.youtube.com/live/rj2hY2Bsi30)
>
> See Great Docs in action and hear the story behind it: a full walkthrough on Talk Python.
>
> <a href="https://www.youtube.com/live/rj2hY2Bsi30"><img src="https://img.youtube.com/vi/rj2hY2Bsi30/maxresdefault.jpg" alt="Watch the Great Docs live stream on Talk Python" width="480"></a>

Great Docs turns your Python package into a polished documentation site in minutes. It auto-discovers your public API, detects your docstring format, generates structured reference pages, and renders a modern site, all from a single command. When you're ready to customize, there's a deep set of tools and options waiting for you.

And it's battle-tested: every release runs against [300+ synthetic packages](https://posit-dev.github.io/gdg/) in the Great Docs Gauntlet, backed by a suite of 26,000+ tests.

<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/landing-demo.svg" alt="Great Docs in action: init, build, and preview a documentation site" width="720">
</p>
<p align="center"><em>From zero to a live site in three commands.</em></p>

<p align="center">
<a href="https://posit-dev.github.io/great-docs/assets/great-docs-tour.mp4"><img src="https://posit-dev.github.io/great-docs/assets/great-docs-tour-poster.png" alt="Watch a 22-second tour of a generated Great Docs site" width="720"></a>
</p>
<p align="center"><em>A 22-second tour of a generated site: going through some of the site's many useful pages. Great Docs documents itself -> <a href="https://posit-dev.github.io/great-docs/">explore the live site</a>.</em></p>

## Why Great Docs?

Writing documentation shouldn't be harder than writing the code it describes. Most documentation generators require you to author page templates, organize content by hand, and wire up a build system. Great Docs inverts that: point it at a Python package and get a great site right away, then explore further at your own pace.

- **Instant setup**: `great-docs init` inspects your package and generates a complete config
- **Smart defaults**: API reference pages are created automatically from your code (no manual authoring needed)
- **Real documentation, not stubs**: renders full parameter tables, return types, examples, and cross-references from your existing docstrings
- **Looks great out of the box**: gradient navbars, dark mode, responsive layout, GitHub widget, sidebar search, keyboard navigation
- **Deep when you need it**: user guides, multi-version docs, freeze caching, link checking, proofreading, SEO, internationalization (20+ languages), and more (all opt-in)
- **AI-ready**: auto-generates `llms.txt`, agent skills, and markdown pages for LLM consumption
- **Deploys anywhere**: one command creates a GitHub Actions workflow for GitHub Pages

## How It Compares

Most Python documentation tools hand you a framework and ask you to assemble the site yourself. Great Docs assembles a complete site for you first, then gets out of the way when you want control.

| | Great Docs | Sphinx | MkDocs | pdoc |
| --- | :---: | :---: | :---: | :---: |
| Polished site with **zero config** | ✅ | ➖ | ➖ | ✅ |
| API reference from your docstrings | ✅ | ✅ | plugin | ✅ |
| Prose guides, recipes, custom pages | ✅ | ✅ | ✅ | ➖ |
| Click CLI **and** MCP server reference | ✅ | ➖ | ➖ | ➖ |
| Dark mode, search, theming built in | ✅ | theme | theme | basic |
| AI-ready: `llms.txt`, agent skills | ✅ | ➖ | ➖ | ➖ |
| Link check, lint, proofread, SEO | ✅ | partial | plugins | ➖ |

Great Docs is built on [Quarto](https://quarto.org/), so you get its rendering power (executable code, math, diagrams) without having to wire any of it up.

## Get Started in 60 Seconds

> [!IMPORTANT]
> Great Docs needs two things on your system: **Python 3.11+** and **[Quarto](https://quarto.org/docs/get-started/)**, the rendering engine. Quarto is a separate, one-time install (it isn't a Python package), so set it up before running the commands below. See [Requirements](#requirements) for details.

### Install

```bash
pip install great-docs
```

### Initialize, build, and preview

```bash
cd your-python-package

great-docs init     # auto-detect package, generate config
great-docs build    # generate and render the site
great-docs preview  # open in your browser at localhost:3000
```

That's it. Your documentation site is ready.

## What Gets Generated

Every site built by Great Docs includes:

### Landing Page

Your README is transformed into a landing page with a hero section, metadata sidebar (authors, license, links), and quick-start instructions.

### API Reference

Classes, functions, methods, and attributes are automatically organized into categorized sections. Large classes get dedicated method pages. Every item links back to source code on GitHub.

<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/api-reference-index.png" alt="API reference index with categorized sections" width="720">
</p>

<details>
<summary>See more: class page and method page</summary>
<br>
<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/class-page.png" alt="A class documentation page with parameters and methods" width="720">
</p>
<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/method-page.png" alt="A method documentation page with signature and examples" width="720">
</p>
</details>

### CLI Reference

Click-based CLIs get rich, sectioned reference pages with usage signatures, typed options, and descriptions extracted directly from code. Each command page includes structured documentation alongside a collapsible `--help` output view.

<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/cli-page.png" alt="CLI reference page with structured documentation and collapsible help output" width="720">
</p>

### MCP Server Reference

If your package ships an [MCP](https://modelcontextprotocol.io/) server, Great Docs generates structured reference pages for every tool, resource, and prompt it exposes. Parameters, types, required/optional markers, and descriptions are extracted automatically from your server definitions. Both standard MCP and [FastMCP](https://gofastmcp.com/) servers are detected automatically.

### Terminal Recordings

Teach your CLI visually with Termshow: record terminal sessions (by hand, or from a list of steps that `termshow check` can re-run in CI to catch demos that have gone out of date), edit them in a browser-based visual editor, and embed the results as animated SVG players in your documentation. Recordings are lightweight, theme-aware, and play inline without JavaScript dependencies. It's incredibly useful in onboarding guides, tutorials, and landing pages. If you already have VHS tapes, `great-docs termshow import-tape` turns them into Termshow scripts. For places that can't run the player, such as a GitHub README, `great-docs termshow export` writes the recording as a single animated SVG, with light and dark versions if you want them; `--gif`, `--mp4`, and `--webm` make a GIF or a video for pull requests, chat, and slides (with `ffmpeg`), `--cast` writes an asciicast file for asciinema, `--bundle` puts a recording for the player in one `.termshow.json` file, and `termshow snap` takes a still SVG or PNG of any moment. Every embedded recording carries a transcript of its text for screen readers and the page's Markdown version, and `termshow transcript` prints it, or the annotations and chapters as WebVTT. The player can be used from the keyboard and with a screen reader, and readers who ask for reduced motion get a still poster that steps through chapter by chapter. On sites built without Quarto, a `<termshow-player>` element plays recordings on any HTML page.

### Lightbox

Any image can expand into a focused, full-screen view. Add a `.lightbox` class to a single image or set `lightbox: auto` on a page to enlarge them all. The viewer supports zoom and panning, multi-image galleries with a filmstrip, captions and credits, dark-mode variants, image annotations, before/after comparison, and a copy/download toolbar. Assets load automatically, so there's nothing to install or enable.

### Dark Mode

A persistent dark mode toggle with flash-free loading. Your users' preference is remembered across visits.

<p align="center">
<img src="https://posit-dev.github.io/great-docs/assets/dark-mode.png" alt="Documentation site in dark mode" width="720">
</p>

## Full Feature Set

<details>
<summary><em>80+ capabilities across 8 categories (click to expand)</em></summary>
<br>

<table>
<tr>
<td width="50%" valign="top">

**Documentation Generation**

- Auto-discovers exports via `__all__`, `dir()`, or static analysis
- Detects NumPy, Google, and Sphinx docstring formats
- 13 object types with smart categorization
- CLI documentation (Python Click, Go, and Rust)
- User Guide pages from `docs/user_guide/` directory
- Custom sections (recipes, blog, tutorials, etc.)
- Custom HTML pages with passthrough or raw layouts
- Multi-version documentation with version selector
- Video embeds (YouTube, Vimeo, local files)
- Interactive Marimo notebooks
- Mermaid and D2 diagram pre-rendering (light + dark variants)
- Freeze/cache support for expensive computations

</td>
<td width="50%" valign="top">

**Site Features**

- Dark mode toggle with persistent preference
- Lightbox image viewer (zoom, pan, galleries)
- GitHub widget with live star/fork counts
- Sidebar search filter for large APIs
- Source links to GitHub for every item
- Copy-to-clipboard for code blocks
- Responsive, mobile-friendly layout
- Page tags and tag index pages
- Page status badges (experimental, stable, deprecated)
- API evolution annotations (new, changed, deprecated)
- Social cards (Open Graph / Twitter)
- Keyboard navigation with shortcut overlay
- Back-to-top floating button
- Navigation icons (Lucide icon set)
- Scale-to-fit for wide HTML output

</td>
</tr>
<tr>
<td width="50%" valign="top">

**AI & LLM Integration**

- Auto-generates `llms.txt` and `llms-full.txt`
- Agent Skills generation ([agentskills.io](https://agentskills.io/) compliant)
- Multiple named skills per package
- Skill install/check/list CLI commands
- Markdown page generation for LLM consumption
- MCP server reference pages (tools, resources, prompts)

</td>
<td width="50%" valign="top">

**Configuration & Branding**

- Announcement banners (dismissible, styled)
- Logo with light/dark variants
- Custom favicon and Open Graph images
- Author metadata with ORCID support
- Changelog from GitHub Releases
- Internationalization (20+ languages)
- Accent color (global or per-mode)
- Navbar gradient presets or solid colors
- Content area gradient presets

</td>
</tr>
<tr>
<td width="50%" valign="top">

**Quality & Reliability**

- Built-in link checker
- Documentation linter (docstrings, cross-refs, style)
- Proofreading (spelling & grammar)
- SEO auditing (sitemap, robots.txt, canonical URLs, structured data)
- API diff between versions
- Build timings reporting
- Tested against 300+ synthetic packages via the [Great Docs Gauntlet](https://posit-dev.github.io/gdg/)
- 26,000+ tests

</td>
<td width="50%" valign="top">

**Deployment**

- One-command GitHub Pages setup
- GitHub Actions workflow generation
- Multi-version deployment with version selector
- Floating version aliases (`/v/latest/`, `/v/stable/`, `/v/dev/`)
- Custom domain support
- Static output: host anywhere

</td>
</tr>
<tr>
<td width="50%" valign="top">

**Shortcodes & Widgets**

- Color swatches (inline and grid)
- Lightbox (zoom, galleries, annotations, before/after compare)
- Terminal recordings (record, edit, embed, export as animated SVG, GIF, MP4, WebM, asciicast, or a single-file bundle, screenshot, transcripts)
- Collapsible details sections
- Keyboard keys styling
- Horizontal rules with accent colors
- Table previews (Python API for notebooks)
- Table explorer (interactive data tables)

</td>
<td width="50%" valign="top">

**Developer Experience**

- `great-docs init` auto-detects package manager (uv, poetry, pip)
- `great-docs freeze` for caching expensive computations
- `great-docs timings` for build performance insight
- Pre-render script hooks
- Page metadata timestamps (creation/modification dates)

</td>
</tr>
</table>

</details>

## Configuration

All configuration lives in `docs/great-docs.yml`. The `init` command generates it for you.
Source paths such as `assets/logo.svg` are relative to `docs/`; package metadata,
Python sources, and the README stay at the project root. You can customise everything:

```yaml
# Theming
navbar_style: sky
content_style: lilac
dark_mode_toggle: true
accent_color: "#3b82f6"

# Branding
display_name: My Package
logo:
  light: assets/logo.svg
  dark: assets/logo-dark.svg

# Announcement banner
announcement:
  content: "v2.0 is here!"
  style: mint
  dismissable: true

# GitHub integration
repo: https://github.com/your-org/your-package # Optional override
github_style: widget

# CLI documentation
cli:
  enabled: true
  module: my_package.cli
  name: cli

# Multi-version documentation
versions:
  - tag: v2.0.0
    label: "2.0 (latest)"
  - tag: v1.5.0
    label: "1.5"

# Freeze cache for expensive computations
freeze: auto

# Internationalization
site:
  language: fr

# Custom sections
sections:
  - title: Recipes
    dir: recipes
    navbar_after: User Guide
```

Custom HTML pages can live in a `custom/` directory and are discovered automatically during build.

```html
---
title: Landing Page
layout: passthrough
navbar: true
---
<section class="hero">...</section>
```

Use `layout: passthrough` to wrap the HTML body with the normal Great Docs shell, or `layout: raw` to copy the HTML file through unchanged.
Set `navbar: true` to add the page to the site navbar using its title, or use `navbar: {text: Showcase, after: Guide}` for explicit navbar label and placement.

Build with `great-docs build` and deploy `docs/_site/`. Generated Quarto projects
live in `docs/_quarto/default/`, with historical versions in `docs/_quarto/<tag>/`.
For a custom source directory, run
`great-docs build --config website/great-docs.yml`; its output is `website/_site/`.

See the [Configuration Guide](https://posit-dev.github.io/great-docs/user-guide/configuration.html) for the full reference.

## Deploying to GitHub Pages

```bash
great-docs setup-github-pages
```

This creates a `.github/workflows/` file that builds and publishes your site on every push to `main`. Your docs stay in sync with your code automatically.

## CLI Commands

Beyond `init`, `build`, and `preview`, Great Docs includes a full suite of quality and maintenance tools:

| Command | Purpose |
| --- | --- |
| `great-docs scan` | Preview discovered exports before building |
| `great-docs lint` | Check for missing docstrings, broken cross-refs, style issues |
| `great-docs proofread` | Catch spelling and grammar problems |
| `great-docs check-examples` | Check that code examples in pages and docstrings run without errors |
| `great-docs check-links` | Validate all links in the built site |
| `great-docs seo` | Audit SEO health (sitemap, meta tags, structured data) |
| `great-docs api-diff OLD NEW` | Show API changes between two versions |
| `great-docs api-snapshot` | Capture a JSON snapshot of your public API |
| `great-docs versions` | List and validate multi-version configuration |
| `great-docs changelog` | Generate changelog from GitHub Releases |
| `great-docs freeze` | Execute specific pages and persist their freeze cache |
| `great-docs timings` | Show page-level build timings from the last build |
| `great-docs setup-github-pages` | Create CI workflow for GitHub Pages deployment |
| `great-docs ci pr-comment` | Post or refresh a PR comment with the local-preview command (in CI) |
| `great-docs ci notice` | Print a workflow log notice with the local-preview command (in CI) |
| `great-docs config` | Generate a fully-documented config template |
| `great-docs uninstall` | Remove great-docs from your project |
| `great-docs skill install` | Install AI agent skills for your package |
| `great-docs skill check` | Check if installed skills are up to date |
| `great-docs skill list` | List available skills from a package or URL |
| `great-docs termshow record` | Record a terminal session as a `.termshow` file, live or from scripted `steps:` |
| `great-docs termshow edit` | Open the browser-based visual editor for a recording |
| `great-docs termshow play` | Preview a recording in the terminal |
| `great-docs termshow render` | Render SVG frames without a full site build |
| `great-docs termshow export` | Export a recording as one animated SVG for READMEs, as a GIF or video (`--gif`, `--mp4`, `--webm`), as asciicast (`--cast`), or as a single-file bundle for the player (`--bundle`) |
| `great-docs termshow snap` | Take a still SVG or PNG of one moment in a recording |
| `great-docs termshow transcript` | Print a recording's text as Markdown, or its annotations or chapters as WebVTT |
| `great-docs termshow validate` | Check a recording and its script for mistakes |
| `great-docs termshow check` | Re-run scripted steps and report recordings whose output has changed (`--json` for CI) |
| `great-docs termshow assets` | Copy the web player for pages built without Quarto |
| `great-docs termshow import-cast` | Import an asciinema `.cast` file |
| `great-docs termshow import-tape` | Convert a VHS `.tape` file to a script with `steps:` |

## Recipes

The documentation includes 24 step-by-step recipes.

<details>
<summary><em>Browse all 24 recipes (click to expand)</em></summary>
<br>

### Content & API

| Recipe                                                                                                       | Topic                                      |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| [Hide Internal Symbols](https://posit-dev.github.io/great-docs/recipes/hide-internal-symbols.html)           | Control what appears in your API reference |
| [Customize API Organization](https://posit-dev.github.io/great-docs/recipes/customize-api-organization.html) | Structure reference sections your way      |
| [Document a CLI](https://posit-dev.github.io/great-docs/recipes/document-a-cli.html)                         | Auto-generate CLI reference from Click     |
| [Cross-Reference Items](https://posit-dev.github.io/great-docs/recipes/cross-reference-items.html)           | Link between documented objects            |
| [Write Effective Docstrings](https://posit-dev.github.io/great-docs/recipes/write-effective-docstrings.html) | Get the most out of auto-generated docs    |
| [Add Images & Diagrams](https://posit-dev.github.io/great-docs/recipes/add-images-diagrams.html)             | Include visuals in your documentation      |
| [Embed Videos](https://posit-dev.github.io/great-docs/recipes/embed-videos.html)                             | Add YouTube, Vimeo, and local videos       |

### Theming & Appearance

| Recipe                                                                                                             | Topic                                      |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| [Add Custom CSS](https://posit-dev.github.io/great-docs/recipes/add-custom-css.html)                               | Override styles with your own SCSS         |
| [Choose Gradient Theme](https://posit-dev.github.io/great-docs/recipes/choose-gradient-theme.html)                 | Pick and customize navbar gradients        |
| [Add Logo & Favicon](https://posit-dev.github.io/great-docs/recipes/add-logo-favicon.html)                         | Brand your site with custom icons          |
| [Customize Announcement Banner](https://posit-dev.github.io/great-docs/recipes/customize-announcement-banner.html) | Add dismissible site-wide notices          |

### Publishing & Versioning

| Recipe                                                                                                             | Topic                                      |
| ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| [Create Changelog](https://posit-dev.github.io/great-docs/recipes/create-changelog.html)                           | Pull changelog from GitHub Releases        |
| [GitHub Pages & CI](https://posit-dev.github.io/great-docs/recipes/github-pages-ci.html)                           | Automate deployment with Actions           |
| [Add Custom Domain](https://posit-dev.github.io/great-docs/recipes/add-custom-domain.html)                         | Serve docs from your own domain            |
| [Enable Multi-Version Docs](https://posit-dev.github.io/great-docs/recipes/enable-multi-version-docs.html)         | Add a version selector to your site        |
| [Use Version Fences and Badges](https://posit-dev.github.io/great-docs/recipes/use-version-fences-and-badges.html) | Annotate version-specific content          |

### AI-Assisted Workflows

| Recipe                                                                                                   | Topic                                      |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| [Install Great Docs Skill](https://posit-dev.github.io/great-docs/recipes/install-great-docs-skill.html) | Generate an Agent Skill for your package   |
| [Build Site with LLM](https://posit-dev.github.io/great-docs/recipes/build-site-with-llm.html)           | Use an AI assistant to set up your site    |
| [Customize Site with LLM](https://posit-dev.github.io/great-docs/recipes/customize-site-with-llm.html)   | Use an AI assistant to tweak your site     |
| [Understand llms.txt](https://posit-dev.github.io/great-docs/recipes/understand-llms-txt.html)           | Make your docs AI-accessible               |

### Build & Quality

| Recipe                                                                                                 | Topic                                      |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| [Fix Common Build Errors](https://posit-dev.github.io/great-docs/recipes/fix-common-build-errors.html) | Troubleshoot build issues quickly          |
| [Proofread Documentation](https://posit-dev.github.io/great-docs/recipes/proofread-documentation.html) | Catch spelling and grammar issues          |
| [Use Freeze Cache](https://posit-dev.github.io/great-docs/recipes/use-freeze-cache.html)               | Cache expensive notebooks across builds    |
| [Freeze a Page to Cache Outputs](https://posit-dev.github.io/great-docs/recipes/freeze-demo.html)      | See page-level freeze in action            |

</details>

## Documentation

Full documentation is available at **[posit-dev.github.io/great-docs](https://posit-dev.github.io/great-docs/)**.

<details>
<summary><em>Full guide index (45 pages, click to expand)</em></summary>
<br>

**Getting Started**

- [Welcome to Great Docs](https://posit-dev.github.io/great-docs/user-guide/introduction.html): what Great Docs does and what this guide covers
- [Installation](https://posit-dev.github.io/great-docs/user-guide/installation.html): setup and requirements
- [Quick Start](https://posit-dev.github.io/great-docs/user-guide/quickstart.html): first site in minutes
- [Authoring QMD Files](https://posit-dev.github.io/great-docs/user-guide/authoring-qmd-files.html): Markdown, frontmatter, and Quarto features
- [Writing Docstrings](https://posit-dev.github.io/great-docs/user-guide/writing-docstrings.html): docstrings that render into great reference pages

**Config & Theming**

- [Configuration](https://posit-dev.github.io/great-docs/user-guide/configuration.html): every option explained
- [Theming & Appearance](https://posit-dev.github.io/great-docs/user-guide/theming.html): gradients, colors, dark mode
- [Cross-Referencing](https://posit-dev.github.io/great-docs/user-guide/cross-referencing.html): linking between documented items and pages
- [Internationalization](https://posit-dev.github.io/great-docs/user-guide/internationalization.html): 20+ language translations
- [Scale-to-Fit](https://posit-dev.github.io/great-docs/user-guide/scale-to-fit.html): auto-shrink wide output

**Site Content**

- [API Documentation](https://posit-dev.github.io/great-docs/user-guide/api-documentation.html): how API references are generated
- [CLI Documentation](https://posit-dev.github.io/great-docs/user-guide/cli-documentation.html): documenting Click, Go, and Rust CLIs
- [User Guides](https://posit-dev.github.io/great-docs/user-guide/user-guides.html): adding prose documentation
- [Custom Sections](https://posit-dev.github.io/great-docs/user-guide/custom-sections.html): recipes, tutorials, and other sections
- [Blog](https://posit-dev.github.io/great-docs/user-guide/blog.html): a dated, listing-based blog
- [Diagrams](https://posit-dev.github.io/great-docs/user-guide/diagrams.html): Mermaid and D2 diagram pre-rendering
- [Videos](https://posit-dev.github.io/great-docs/user-guide/videos.html): embedding YouTube, Vimeo, and local videos
- [Custom Static Pages](https://posit-dev.github.io/great-docs/user-guide/custom-pages.html): static HTML pages
- [Page Tags](https://posit-dev.github.io/great-docs/user-guide/page-tags.html): categorize pages with tags
- [Page Status Badges](https://posit-dev.github.io/great-docs/user-guide/page-status-badges.html): lifecycle indicators
- [Table Previews](https://posit-dev.github.io/great-docs/user-guide/table-previews.html): show what a dataset looks like
- [Table Explorer](https://posit-dev.github.io/great-docs/user-guide/table-explorer.html): interactive data tables
- [Horizontal Rules](https://posit-dev.github.io/great-docs/user-guide/horizontal-rules.html): styled section dividers
- [Keyboard Keys](https://posit-dev.github.io/great-docs/user-guide/keyboard-keys.html): styled keyboard shortcuts
- [Color Swatches](https://posit-dev.github.io/great-docs/user-guide/color-swatches.html): inline and grid color swatches
- [Collapsible Details](https://posit-dev.github.io/great-docs/user-guide/collapsible-details.html): expandable sections for long pages
- [Terminal Recordings](https://posit-dev.github.io/great-docs/user-guide/terminal-recordings.html): record, edit, embed, and export terminal sessions
- [Termshow File Formats](https://posit-dev.github.io/great-docs/user-guide/termshow-file-formats.html): the recording and script file formats
- [Lightbox](https://posit-dev.github.io/great-docs/user-guide/lightbox.html): full-screen image viewer with zoom, galleries, and annotations
- [Marimo Notebooks](https://posit-dev.github.io/great-docs/user-guide/marimo-notebooks.html): interactive notebooks embedded in pages

**Build & Deploy**

- [Building & Previewing](https://posit-dev.github.io/great-docs/user-guide/building.html): the build command and local previews
- [Deployment](https://posit-dev.github.io/great-docs/user-guide/deployment.html): GitHub Pages and beyond
- [SEO Optimization](https://posit-dev.github.io/great-docs/user-guide/seo.html): search engine optimization
- [Social Cards](https://posit-dev.github.io/great-docs/user-guide/social-cards.html): Open Graph and Twitter cards
- [Versioned Docs](https://posit-dev.github.io/great-docs/user-guide/multi-version-docs.html): version selector and versioned builds
- [Freeze & Caching](https://posit-dev.github.io/great-docs/user-guide/freeze.html): caching expensive computations

**Quality & Maintenance**

- [Link Checker](https://posit-dev.github.io/great-docs/user-guide/link-checker.html): validate all links
- [Proofreading](https://posit-dev.github.io/great-docs/user-guide/proofreading.html): spelling & grammar checks
- [Changelog](https://posit-dev.github.io/great-docs/user-guide/changelog.html): a changelog page from GitHub Releases
- [Community Files](https://posit-dev.github.io/great-docs/user-guide/community-files.html): contributing guides, codes of conduct, and more
- [Docs Linting](https://posit-dev.github.io/great-docs/user-guide/linting.html): documentation quality checks
- [API Evolution](https://posit-dev.github.io/great-docs/user-guide/api-evolution.html): tracking API changes across versions

**AI & Agents**

- [Agent Skills](https://posit-dev.github.io/great-docs/user-guide/agent-skills.html): AI coding agent integration
- [llms.txt](https://posit-dev.github.io/great-docs/user-guide/llms-txt.html): making your docs readable by LLMs
- [MCP Documentation](https://posit-dev.github.io/great-docs/user-guide/mcp-documentation.html): reference pages for MCP servers

</details>

## Requirements

- **Python 3.11+**
- **[Quarto](https://quarto.org/docs/get-started/)** (the rendering engine)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING](https://posit-dev.github.io/great-docs/contributing.html) for guidelines and the [Code of Conduct](https://posit-dev.github.io/great-docs/code-of-conduct.html).

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
Built by <a href="https://posit.co">Posit, PBC</a>.
</p>
