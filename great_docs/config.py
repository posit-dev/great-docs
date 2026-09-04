"""
great-docs configuration.

`great-docs.default.yml` is the single source of truth for every default; this
module reads a user's merged config and exposes it as typed properties.

Contract for adding an option — keep the single source intact:

- Declare the option and its default in `great-docs.default.yml`, never here.
  This module holds no default values.
- Read through `config["dot.path"]`. The lookup is strict: a key absent from
  the merged config raises `KeyError`. A user's bare `key:` (null) over a
  dict-valued option therefore means "not specified" and keeps the defaults,
  so such a read still resolves; see `Config._NULL_DISABLES` for the few
  options a null switches off instead.
- Default to a typed empty container (`[]`, `{}`) rather than `null`, unless the
  option is an optional scalar, a genuine tri-state, or a single optional record.
- For an option whose value is a dict of sub-fields, declare those sub-fields
  live in the YAML and expand any scalar/bool shorthand to that dict at load.
  Accessors must not supply sub-field defaults.
- A property is the typed view of an option: a thin one returns `self["key"]`;
  a richer one may coerce shape or derive from other options, but adds no
  default value.
"""

import copy
import io
import re
from importlib import resources
from pathlib import Path
from typing import Any, cast

from yaml12 import read_yaml


def _load_default_config() -> dict[str, Any]:
    """Load the packaged default configuration

    Returns
    -------
    dict
        The parsed contents of `great-docs.default.yml`, i.e. every config
        field at its default value.
    """
    text = (
        resources.files("great_docs")
        .joinpath("assets", "great-docs.default.yml")
        .read_text(encoding="utf-8")
    )
    return read_yaml(io.StringIO(text)) or {}


DEFAULT_CONFIG: dict[str, Any] = _load_default_config()

# great-docs-owned keys that older configs placed under `site`. They are
# top-level keys now; any found under `site` at load are lifted out so `site`
# stays a clean Quarto passthrough.
_LEGACY_SITE_KEYS: tuple[str, ...] = (
    "language",
    "show_dates",
    "date_format",
    "show_author",
    "show_security",
)


class Config:
    """
    Configuration manager for Great Docs.

    Loads configuration from great-docs.yml and provides access to settings
    with sensible defaults.
    """

    def __init__(self, project_root: Path):
        """
        Initialize configuration from great-docs.yml.

        Parameters
        ----------
        project_root
            Path to the project root directory where great-docs.yml is located.
        """
        self.project_root = project_root
        self.config_path = project_root / "great-docs.yml"
        self._config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        """
        Load configuration from great-docs.yml.

        Returns
        -------
        dict
            The loaded configuration merged with defaults.
        """
        config = copy.deepcopy(DEFAULT_CONFIG)
        self._user_config: dict[str, Any] = {}

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = read_yaml(f)

                if user_config is None:
                    user_config = {}

                if not isinstance(user_config, dict):
                    # A valid YAML document that isn't a mapping (a list, a bare
                    # scalar) has no config to contribute; the defaults stand.
                    print(
                        "Warning: great-docs.yml must be a mapping of options; "
                        f"got {type(user_config).__name__}. Using defaults."
                    )
                else:
                    self._user_config = cast("dict[str, Any]", user_config)
                    # Deep merge user config with defaults
                    config = self._merge(config, self._user_config)
            except ValueError as e:
                print(f"Warning: Error parsing great-docs.yml: {e}")
            except OSError as e:
                print(f"Warning: Could not read great-docs.yml: {e}")

        config = self._lift_legacy_site_keys(config)
        config = self._normalize_shorthands(config)
        return config

    def _lift_legacy_site_keys(self, config: dict[str, Any]) -> dict[str, Any]:
        """Move legacy great-docs keys out of `site` to the top level

        Older configs placed language/date settings under `site`; those are
        great-docs-owned, not Quarto `format.html` keys, so they now live at
        the top level. Any that still appear under `site` are lifted out so
        `site` stays a clean Quarto passthrough. An explicit top-level value
        wins over a legacy `site` value on conflict.

        Parameters
        ----------
        config
            The merged configuration.

        Returns
        -------
        dict
            The configuration with the legacy keys normalized to the top level.
        """
        site = config.get("site")
        if not isinstance(site, dict):
            return config

        for key in _LEGACY_SITE_KEYS:
            if key in site:
                value = site.pop(key)
                if key not in self._user_config:
                    config[key] = value
        return config

    # Options accepting a bool shorthand that collapses their dict subtree.
    # The bool sets `enabled`; other sub-fields fall back to the packaged
    # defaults. Kept for backward compatibility; no longer documented.
    _BOOL_SHORTHAND_KEYS: tuple[str, ...] = (
        "page_status",
        "tags",
        "social_cards",
        "markdown_pages",
        "mcp",
        "marimo",
    )

    def _normalize_shorthands(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Expand shorthand config values into their canonical dict form

        A user may write a scalar where the canonical form is a dict (e.g.
        `page_status: true`, or an explicit `social_cards: null`). Each such
        value is rebuilt into the full dict, with `enabled` set from the
        scalar, so downstream access is always a plain nested lookup.

        Parameters
        ----------
        config
            The merged configuration.

        Returns
        -------
        dict
            The configuration with shorthand values expanded.
        """
        for key in self._BOOL_SHORTHAND_KEYS:
            raw = config.get(key)
            if isinstance(raw, bool) or raw is None:
                merged = copy.deepcopy(DEFAULT_CONFIG[key])
                merged["enabled"] = bool(raw)
                config[key] = merged

        # `hero` is excluded from the loop above: its `enabled` sub-field
        # defaults to `None` (auto — enable when a logo exists), which the
        # bool-shorthand loop would collapse to `False`.
        raw = config.get("hero")
        if not isinstance(raw, dict):
            merged = copy.deepcopy(DEFAULT_CONFIG["hero"])
            if isinstance(raw, bool):
                merged["enabled"] = raw
            # raw is None -> keep enabled: null (auto)
            config["hero"] = merged
        else:
            user_hero = self._user_config.get("hero")
            if isinstance(user_hero, dict) and "enabled" not in user_hero:
                # Backward compatibility: a user-supplied hero mapping (of any
                # shape, even {}) used to enable the hero unconditionally, even
                # without a logo. No longer documented (see
                # user_guide/11-theming.qmd), but preserved silently for
                # existing configs.
                raw["enabled"] = True

        hero_logo = config["hero"].get("logo")
        if isinstance(hero_logo, dict) and not hero_logo.get("light") and hero_logo.get("dark"):
            # Mirror the top-level `logo` dark-only fallback: a dark-only
            # hero.logo must still resolve to a `light` asset, or
            # core.py's _build_hero_section silently drops the image.
            hero_logo["light"] = hero_logo["dark"]

        # A bare `seo: true`/`seo: false` collapses the whole subtree to a bool;
        # rebuild it into the full default dict with `enabled` set from the
        # scalar, same as the `_BOOL_SHORTHAND_KEYS` loop above.
        #
        # `seo.*` nested bool shorthands (e.g. `seo:\n  sitemap: true`) collapse
        # a dict subtree; expand each back to its full default dict so strict
        # `seo.<sub>.*` reads resolve.
        seo = config.get("seo")
        if isinstance(seo, bool):
            merged = copy.deepcopy(DEFAULT_CONFIG["seo"])
            merged["enabled"] = seo
            config["seo"] = merged
            seo = merged
        if isinstance(seo, dict):
            for sub in ("sitemap", "robots", "canonical", "structured_data"):
                raw = seo.get(sub)
                if isinstance(raw, bool):
                    merged = copy.deepcopy(DEFAULT_CONFIG["seo"][sub])
                    merged["enabled"] = raw
                    seo[sub] = merged

        # `announcement` is also excluded from the loop above: a string shorthand
        # sets `content`, not `enabled`.
        raw = config.get("announcement")
        if not isinstance(raw, dict):
            merged = copy.deepcopy(DEFAULT_CONFIG["announcement"])
            if isinstance(raw, str):
                merged["content"] = raw
            config["announcement"] = merged

        # `content_style` is also excluded from the loop above: a string
        # shorthand sets `preset`, not `enabled`.
        raw = config.get("content_style")
        if not isinstance(raw, dict):
            merged = copy.deepcopy(DEFAULT_CONFIG["content_style"])
            if isinstance(raw, str):
                merged["preset"] = raw
            config["content_style"] = merged

        # `logo` is also excluded from the loop above: a string shorthand
        # sets both `light` and `dark`, not `enabled`.
        raw = config.get("logo")
        if not isinstance(raw, dict):
            merged = copy.deepcopy(DEFAULT_CONFIG["logo"])
            if isinstance(raw, str):
                merged["light"] = raw
                merged["dark"] = raw
            config["logo"] = merged
            raw = config["logo"]
        if isinstance(raw, dict) and not raw.get("light") and raw.get("dark"):
            # A dark-only logo still needs a `light` asset for the primary
            # navbar <img>; fall back to the same file (core.py:11900 assumes
            # `light` is always present once Config.logo is not None).
            raw["light"] = raw["dark"]

        # `freeze` is also excluded from the loop above: a scalar shorthand
        # sets `mode`, not `enabled`.
        raw = config.get("freeze")
        if not isinstance(raw, dict):
            merged = copy.deepcopy(DEFAULT_CONFIG["freeze"])
            merged["mode"] = raw  # None | True | False | "auto" | "true"
            config["freeze"] = merged

        return config

    # A bare `key:` (null) switches these options off. For every other
    # dict-valued option a null means "not specified" and `_merge` keeps the
    # packaged defaults, so an empty or commented-out block reads the same as
    # an absent one. These four are the exception for backward compatibility:
    # each defaults to on, yet a null has always disabled it.
    _NULL_DISABLES: tuple[str, ...] = (
        "social_cards",
        "markdown_pages",
        "mcp",
        "freeze",
    )

    @staticmethod
    def _merge(defaults: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge two config-shaped mappings

        Values in `user` win; dicts present in both are merged recursively.
        A `None` where the default is a dict counts as "not specified" and
        leaves the default subtree standing, so an empty or commented-out
        block (`seo:` with nothing under it) reads the same as an absent one;
        `_NULL_DISABLES` names the few keys that opt out of this. `defaults`
        is not mutated — a new mapping is returned. Also used to overlay the
        `site` subtree onto `_quarto.yml` `format.html`.

        Parameters
        ----------
        defaults
            Base configuration values.
        user
            Overriding configuration values (take precedence).

        Returns
        -------
        dict
            Merged configuration.
        """
        result = defaults.copy()

        for key, value in user.items():
            if key not in result or not isinstance(result[key], dict):
                result[key] = value
            elif isinstance(value, dict):
                result[key] = Config._merge(result[key], value)
            elif value is None and key not in Config._NULL_DISABLES:
                pass  # keep the default subtree
            else:
                result[key] = value

        return result

    def __getitem__(self, key: str) -> Any:
        """
        Return the configuration value at a dot-separated key

        Parameters
        ----------
        key
            A dot-path such as `"seo.sitemap.enabled"`.

        Returns
        -------
        Any
            The value in the merged configuration at that path.

        Raises
        ------
        KeyError
            If any segment is absent or traversal reaches a non-mapping.
        """
        value: Any = self._config
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                raise KeyError(key)
        return value

    @property
    def exclude(self) -> list[str]:
        """Get the list of items to exclude."""
        return self["exclude"]

    @property
    def auto_include(self) -> list[str]:
        """Get names to force-include even if they match AUTO_EXCLUDE."""
        return self["auto_include"]

    @property
    def no_auto_exclude(self) -> bool:
        """Check if the built-in AUTO_EXCLUDE list should be bypassed."""
        return self["no_auto_exclude"]

    @property
    def project_type(self) -> list[str]:
        """Get the project type(s).

        Describes the primary ecosystem(s) the project belongs to.

        Returns
        -------
        list[str]
            Always a list, e.g. `["python"]`, `["go"]`, or `["python", "go"]` for mixed projects.
        """
        val = self["project_type"]
        if isinstance(val, list):
            return [str(t).lower() for t in val]
        return [str(val).lower()]

    @property
    def is_python_project(self) -> bool:
        """Return `True` when the project includes a Python component."""
        return "python" in self.project_type

    @property
    def pypi(self) -> bool | str:
        """Get the PyPI link configuration.

        Returns
        -------
        bool | str
            - True: auto-detect package name and link to pypi.org
            - False: disable the PyPI link entirely
            - str: custom package index URL
        """
        value = self["pypi"]
        if value is None:
            # Auto: a PyPI link makes sense only for a Python project.
            return self.is_python_project
        return value

    @property
    def repo(self) -> str | None:
        """Get the GitHub repository URL override."""
        return self["repo"]

    @property
    def site_url(self) -> str | None:
        """Get the site URL for subdirectory deployments."""
        return self["site_url"]

    @property
    def github_style(self) -> str:
        """Get the GitHub link style."""
        return self["github_style"]

    @property
    def source_enabled(self) -> bool:
        """Check if source links are enabled."""
        return self["source.enabled"]

    @property
    def source_branch(self) -> str | None:
        """Get the source link branch."""
        return self["source.branch"]

    @property
    def source_path(self) -> str | None:
        """Get the custom source path."""
        return self["source.path"]

    @property
    def source_placement(self) -> str:
        """Get the source link placement."""
        return self["source.placement"]

    @property
    def sidebar_filter_enabled(self) -> bool:
        """Check if sidebar filter is enabled."""
        return self["sidebar_filter.enabled"]

    @property
    def sidebar_filter_min_items(self) -> int:
        """Get the minimum items for sidebar filter."""
        return self["sidebar_filter.min_items"]

    @property
    def cli_enabled(self) -> bool:
        """Check if CLI documentation is enabled."""
        return self["cli.enabled"]

    @property
    def cli_module(self) -> str | None:
        """Get the CLI module path."""
        return self["cli.module"]

    @property
    def cli_name(self) -> str | None:
        """Get the CLI command name."""
        return self["cli.name"]

    @property
    def cli_title(self) -> str | None:
        """Get the custom CLI reference index title, if set.

        Supports `cli: {title: "Custom Title"}` in great-docs.yml. Returns `None` when no custom
        title is configured (the caller falls back to a translated default).
        """
        return self["cli.title"]

    @property
    def cli_desc(self) -> str | None:
        """Get the CLI reference index intro paragraph, if set.

        Supports `cli: {desc: "Intro text..."}` in great-docs.yml. Returns `None` when no
        description is configured.
        """
        return self["cli.desc"]

    @property
    def cli_sections(self) -> list[dict[str, Any]]:
        """Get the explicit CLI reference index sections.

        Mirrors the `reference:` config. Supports a list of section dicts under `cli.sections`::

            cli:
              sections:
                - title: Project setup
                  desc: "..."
                  contents: [init, config, uninstall]

        Each `contents` entry is a top-level command name (string). Returns an empty list when no
        explicit sections are configured (triggering auto-grouping by command group).
        """
        val = self["cli.sections"]
        if isinstance(val, list):
            return val
        return []

    @property
    def go_cli_enabled(self) -> bool:
        """Check if Go CLI documentation is enabled.

        When `True`, great-docs will detect the Go CLI project at the package root, compile it, and
        extract the command tree via `--help` to generate a CLI reference section.
        """
        return self["go_cli.enabled"]

    @property
    def rust_cli_enabled(self) -> bool:
        """Check if Rust CLI documentation is enabled.

        When `True`, great-docs will detect the Rust CLI project at the package root, compile it
        via ``cargo build``, and extract the command tree via ``--help`` to generate a CLI reference
        section.
        """
        return self["rust_cli.enabled"]

    @property
    def mcp_enabled(self) -> bool:
        """Check if MCP server documentation is enabled."""
        return self["mcp.enabled"]

    @property
    def mcp_module(self) -> str | None:
        """Get the MCP server module path."""
        return self["mcp.module"]

    @property
    def mcp_server_var(self) -> str | None:
        """Get the MCP server variable name."""
        return self["mcp.server_var"]

    @property
    def mcp_name(self) -> str | None:
        """Get the MCP server display name override."""
        return self["mcp.name"]

    @property
    def mcp_categories(self) -> dict:
        """Get manual MCP tool categories."""
        return self["mcp.categories"]

    @property
    def marimo_enabled(self) -> bool:
        """Check if marimo islands integration is enabled."""
        return self["marimo.enabled"]

    @property
    def marimo_version(self) -> str:
        """Get the @marimo-team/islands CDN runtime version.

        Defaults to the installed marimo version so the browser runtime matches
        the version that generated the island markup. An explicit ``version`` in
        the config overrides this.
        """
        version = self["marimo.version"]
        if version:
            return str(version)

        from great_docs._marimo import islands_runtime_version

        return islands_runtime_version()

    @property
    def skill_enabled(self) -> bool:
        """Check if skill.md generation is enabled."""
        return self["skill.enabled"]

    @property
    def skill_file(self) -> str | None:
        """Get the path to a hand-written SKILL.md override."""
        return self["skill.file"]

    @property
    def skill_well_known(self) -> bool:
        """Check if .well-known/agent-skills/ discovery files should be generated."""
        return self["skill.well_known"]

    @property
    def skill_gotchas(self) -> list[str]:
        """Get the list of gotcha strings for the SKILL.md Gotchas section."""
        return self["skill.gotchas"]

    @property
    def skill_best_practices(self) -> list[str]:
        """Get the list of best-practice strings for the SKILL.md."""
        return self["skill.best_practices"]

    @property
    def skill_decision_table(self) -> list[dict]:
        """Get manual decision table rows for the SKILL.md."""
        return self["skill.decision_table"]

    @property
    def skill_extra_body(self) -> str | None:
        """Get the path to extra Markdown to append to the generated SKILL.md body."""
        return self["skill.extra_body"]

    @property
    def skill_skills(self) -> list[dict]:
        """Get the list of named skills for multi-skill distribution.

        Each entry should have `name` and `file` keys. When non-empty, this overrides the single
        `skill.file` setting.
        """
        return self["skill.skills"]

    @property
    def changelog_enabled(self) -> bool:
        """Check if changelog generation from GitHub Releases is enabled."""
        return self["changelog.enabled"]

    @property
    def changelog_max_releases(self) -> int:
        """Get the maximum number of GitHub Releases to include."""
        return self["changelog.max_releases"]

    @property
    def sections(self) -> list[dict]:
        """Get the custom sections configuration."""
        return self["sections"]

    @property
    def custom_pages(self) -> list[dict[str, str]]:
        """Get normalized custom static page source directories.

        Returns a list of dicts with `dir` and `output` keys.

        - When `custom_pages` is omitted, falls back to `custom/`.
        - When `custom_pages` is `false`, returns an empty list.
        - When `custom_pages` is a string, that path is used and the output prefix defaults to the
          basename of the path.
        - When `custom_pages` is a dict, it may specify `dir` and optional `output`.
        - When `custom_pages` is a list, each entry may be a string or dict.
        """
        raw = self["custom_pages"]

        if raw is None:
            return [{"dir": "custom", "output": "custom"}]

        if raw is False:
            return []

        entries: list[Any]
        if isinstance(raw, list):
            entries = raw
        else:
            entries = [raw]

        normalized: list[dict[str, str]] = []

        for entry in entries:
            if isinstance(entry, str):
                output = Path(entry).name or entry
                normalized.append({"dir": entry, "output": output})
                continue

            if isinstance(entry, dict):
                source_dir = entry.get("dir")
                if not isinstance(source_dir, str) or not source_dir:
                    continue

                output = entry.get("output")
                if not isinstance(output, str) or not output:
                    output = Path(source_dir).name or source_dir

                normalized.append({"dir": source_dir, "output": output})

        return normalized

    @property
    def dark_mode_toggle(self) -> bool:
        """Check if dark mode toggle is enabled."""
        return self["dark_mode_toggle"]

    @property
    def keyboard_nav(self) -> bool:
        """Check if keyboard navigation shortcuts are enabled."""
        return self["keyboard_nav"]

    @property
    def package_info_page(self) -> bool:
        """Check if package info page generation is enabled."""
        return self["package_info_page"]

    @property
    def back_to_top(self) -> bool:
        """Check if back-to-top button is enabled."""
        return self["back_to_top"]

    @property
    def markdown_pages(self) -> bool:
        """Whether Markdown companion pages are generated"""
        return bool(self["markdown_pages.enabled"])

    @property
    def markdown_pages_widget(self) -> bool:
        """Whether the copy-page widget is shown (requires markdown_pages)"""
        return bool(self["markdown_pages.widget"]) and self.markdown_pages

    @property
    def parser(self) -> str:
        """Get the docstring parser format (numpy, google, or sphinx)."""
        return self["parser"]

    @property
    def callable_signatures_style(self) -> str:
        """Markup used for a callable's signature (highlighted or plain)"""
        return self["callable_signatures.style"]

    @property
    def callable_signatures_wrap(self) -> str:
        """Where a callable's signature breaks across lines (per_parameter or width)"""
        return self["callable_signatures.wrap"]

    @property
    def dynamic(self) -> bool:
        """Get the dynamic introspection mode for API reference generation."""
        return self["dynamic"]

    @property
    def module(self) -> str | None:
        """
        Get the explicit module name (importable name).

        Use this when the importable module name differs from the project name,
        e.g., project 'py-yaml12' with module 'yaml12'.
        """
        return self["module"]

    @property
    def display_name(self) -> str | None:
        """
        Get the display name for the site.

        Use this to customize how the package name appears in the navbar/title,
        e.g., 'Great Docs' instead of 'great_docs' or 'great-docs'.
        """
        return self["display_name"]

    @property
    def homepage(self) -> str:
        """Get the homepage mode ('index' or 'user_guide').

        Returns
        -------
        str
            The validated homepage mode. Falls back to 'index' if an
            invalid value is configured.
        """
        value = self["homepage"]
        if value not in ("index", "user_guide"):
            print(f"Warning: Invalid homepage value '{value}', defaulting to 'index'")
            return "index"
        return value

    @property
    def user_guide(self) -> str | list | None:
        """Get the user guide configuration.

        Returns
        -------
        str | list | None
            - None: auto-discover from conventional directories
            - str: custom directory path for user guide files
            - list: explicit section ordering (list of section dicts)
        """
        return self["user_guide"]

    @property
    def user_guide_is_explicit(self) -> bool:
        """Check if user guide uses explicit section ordering."""
        return isinstance(self["user_guide"], list)

    @property
    def user_guide_dir(self) -> str | None:
        """Get the user guide directory path (only when it's a string)."""
        val = self["user_guide"]
        return val if isinstance(val, str) else None

    @property
    def reference_enabled(self) -> bool:
        """Whether API reference generation is enabled.

        Returns `False` when the config contains `reference: false`. Defaults to `True`.
        """
        val = self["reference"]
        if val is False:
            return False
        return True

    @property
    def reference(self) -> list[dict[str, Any]]:
        """Get the API reference configuration (explicit section ordering).

        Supports two forms in great-docs.yml:

        1. List form (sections directly)::

            reference:
              - title: Core
                contents: [...]

        2. Dict form with embedded sections::

            reference:
              title: "API Docs"
              desc: "..."
              sections:
                - title: Core
                  contents: [...]

        Returns the list of section dicts, or an empty list when no
        explicit sections are configured (triggering auto-discovery).
        """
        val = self["reference"]
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            sections = val.get("sections")
            if isinstance(sections, list):
                return sections
        return []

    @property
    def reference_title(self) -> str | None:
        """Get the custom API reference title, if set.

        Supports `reference: {title: "Custom Title"}` in great-docs.yml. Returns `None` when no
        custom title is configured.
        """
        val = self["reference"]
        if isinstance(val, dict):
            return val.get("title")
        return None

    @property
    def reference_desc(self) -> str | None:
        """Get the custom API reference description, if set.

        Supports `reference: {desc: "Description text..."}` in great-docs.yml. Returns `None` when
        no description is configured.
        """
        val = self["reference"]
        if isinstance(val, dict):
            return val.get("desc")
        return None

    def should_split_methods(self, method_count: int) -> bool:
        """Whether a class with this many methods should split them to separate pages.

        Controlled by `inline_methods` in great-docs.yml:
        - true: never split (always inline)
        - false: always split
        - int N: split when method_count > N (default: 5)

        Items with no methods are never split regardless of the setting.
        """
        if method_count == 0:
            return False
        val = self["inline_methods"]
        if val is True:
            return False
        if val is False:
            return True
        try:
            return method_count > int(val)
        except (TypeError, ValueError):
            return method_count > int(DEFAULT_CONFIG["inline_methods"])

    @property
    def authors(self) -> list[dict[str, Any]]:
        """Get the rich author metadata."""
        return self["authors"]

    @property
    def funding(self) -> dict[str, Any] | None:
        """
        Get the funding organization metadata.

        Returns a dict with keys: name, roles (list), ror (ROR URL).
        Example: {"name": "Posit Software, PBC", "roles": ["Copyright holder", "funder"], "ror": "https://ror.org/03wc8by49"}
        """
        return self["funding"]

    @property
    def site(self) -> dict[str, Any]:
        """Get the site settings — a pure Quarto passthrough into format.html."""
        return self["site"]

    @property
    def site_quarto(self) -> dict[str, Any]:
        """Get the `site` subtree destined for `_quarto.yml` `format.html`

        Legacy great-docs keys are already normalized out of `site` at load;
        `css` is removed here because great-docs copies the file and references
        it by basename separately.

        Returns
        -------
        dict
            The site settings safe to merge blindly into `format.html`.
        """
        site = dict(self.site)
        site.pop("css", None)
        return site

    @property
    def show_dates(self) -> bool:
        """Whether to show page metadata timestamps in the footer."""
        return bool(self["show_dates"])

    @property
    def date_format(self) -> str:
        """Get the date format string (Python strftime format)."""
        return self["date_format"]

    @property
    def show_author(self) -> bool:
        """Whether to show author attribution when dates are enabled."""
        return bool(self["show_author"])

    @property
    def show_security(self) -> bool:
        """Whether to show the security policy page when SECURITY.md exists."""
        return bool(self["show_security"])

    @property
    def language(self) -> str:
        """Get the site UI language (BCP 47 code, default 'en')."""
        return self["language"]

    @property
    def team_author(self) -> dict[str, Any] | None:
        """Get the team author configuration for auto-generated pages.

        Returns
        -------
        dict | None
            A dict with keys: name (str), image (str|None), url (str|None).
            Returns None when not configured.
        """
        raw = self["team_author"]
        if raw is None:
            return None
        if isinstance(raw, dict) and raw.get("name"):
            return {
                "name": raw["name"],
                "image": raw.get("image"),
                "url": raw.get("url"),
            }
        return None

    @property
    def jupyter(self) -> str:
        """Get the Jupyter kernel for executing code cells."""
        return self["jupyter"]

    @property
    def logo(self) -> dict[str, Any] | None:
        """The logo config, or None when no logo is set"""
        if not (self["logo.light"] or self["logo.dark"]):
            return None
        return self["logo"]

    @property
    def logo_show_title(self) -> bool:
        """Whether the text title is shown alongside the logo"""
        return bool(self["logo.show_title"]) if self.logo else False

    @property
    def hero(self) -> dict[str, Any]:
        """Resolved hero configuration"""
        return self["hero"]

    @property
    def hero_enabled(self) -> bool:
        """Whether the hero section is shown"""
        enabled = self["hero.enabled"]
        if enabled is None:
            return self.logo is not None or self["hero.logo"] not in (None, False)
        return bool(enabled)

    @property
    def hero_explicitly_disabled(self) -> bool:
        """Whether the hero was turned off explicitly"""
        return self["hero.enabled"] is False

    @property
    def hero_logo(self) -> str | dict | None | bool:
        """The hero-specific logo, or `False` when suppressed"""
        return self["hero.logo"]

    @property
    def hero_logo_height(self) -> str:
        """The hero logo max-height CSS value"""
        return self["hero.logo_height"]

    @property
    def hero_name(self) -> str | bool | None:
        """The hero name, falling back to the display name"""
        val = self["hero.name"]
        if val is False:
            return False
        if val is not None:
            return val
        return self.display_name

    @property
    def hero_tagline(self) -> str | None:
        """The hero tagline, or `None` when suppressed"""
        val = self["hero.tagline"]
        return None if val is False else val

    @property
    def hero_starfield(self) -> bool:
        """Whether the starfield animation is enabled"""
        return bool(self["hero.starfield"])

    @property
    def hero_badges(self) -> str | list | None:
        """The hero badges config (`'auto'`, an explicit list, or `None`)"""
        val = self["hero.badges"]
        return None if val is False else val

    @property
    def favicon(self) -> dict[str, Any] | None:
        """Get the normalized favicon configuration.

        Returns
        -------
        dict | None
            Normalized favicon dict with at least `icon` key, or `None` if no favicon is explicitly
            configured (auto-generation may still produce one from the logo).
        """
        raw = self["favicon"]
        if raw is None:
            return None
        if isinstance(raw, str):
            return {"icon": raw}
        if isinstance(raw, dict):
            return raw
        return None

    @property
    def announcement(self) -> dict[str, Any] | None:
        """The announcement banner config, or None when there is no content"""
        content = self["announcement.content"]
        if not content:
            return None
        position = self["announcement.position"]
        if position not in ("above-navbar", "below-navbar"):
            position = "above-navbar"
        return {
            "content": content,
            "type": self["announcement.type"],
            "dismissable": self["announcement.dismissable"],
            "url": self["announcement.url"],
            "style": self["announcement.style"],
            "position": position,
        }

    @property
    def versions(self) -> list:
        """Get the raw versions list from config."""
        return self["versions"]

    @property
    def has_versions(self) -> bool:
        """Whether multi-version documentation is enabled."""
        return bool(self.versions)

    @property
    def version_selector_enabled(self) -> bool:
        """Whether the version selector widget is enabled."""
        if not self.has_versions:
            return False
        return self["version_selector.enabled"]

    @property
    def version_selector_placement(self) -> str:
        """Get the version selector placement."""
        return self["version_selector.placement"]

    @property
    def version_warning_banner(self) -> bool:
        """Whether to show warning banners on non-latest versions."""
        return self["version_selector.warning_banner"]

    @property
    def version_aliases(self) -> dict:
        """Get the version aliases configuration."""
        return self["version_aliases"]

    @property
    def include_in_header(self) -> list[dict[str, str]]:
        """Get the normalized include-in-header entries.

        Returns a list of Quarto-compatible include-in-header items (each a dict with either a
        "text" or "file" key).
        """
        raw = self["include_in_header"]
        if raw is None:
            return []
        if isinstance(raw, str):
            return [{"text": raw}]
        if isinstance(raw, list):
            result: list[dict[str, str]] = []
            for item in raw:
                if isinstance(item, str):
                    result.append({"text": item})
                elif isinstance(item, dict):
                    result.append(item)
            return result
        return []

    @property
    def freeze(self) -> str | bool | None:
        """The Quarto freeze mode (None disabled, 'auto', or True)"""
        mode = self["freeze.mode"]
        if mode is None or mode is False:
            return None
        if mode is True or mode == "auto":
            return mode
        if isinstance(mode, str) and mode.lower() == "true":
            return True
        return None

    @property
    def pre_render(self) -> list[str]:
        """Normalized pre-render script paths from freeze.pre_render and pre_render"""
        scripts: list[str] = []
        fr = self["freeze.pre_render"]
        if isinstance(fr, str):
            scripts.append(fr)
        elif isinstance(fr, list):
            scripts.extend(s for s in fr if isinstance(s, str))
        pr = self["pre_render"]
        if isinstance(pr, str):
            if pr not in scripts:
                scripts.append(pr)
        elif isinstance(pr, list):
            for s in pr:
                if isinstance(s, str) and s not in scripts:
                    scripts.append(s)
        return scripts

    @property
    def bibliography(self) -> list[str]:
        """Get the normalized list of bibliography file paths.

        Accepts a single path string or a list of paths in `great-docs.yml`. Paths are relative to
        the project root.

        Returns
        -------
        list[str]
            List of bibliography (`.bib`) file paths, or an empty list if none.
        """
        raw = self["bibliography"]
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [s for s in raw if isinstance(s, str)]
        return []

    @property
    def csl(self) -> str | None:
        """Get the citation style language (CSL) file path.

        Returns
        -------
        str | None
            Path to the `.csl` file relative to the project root, or `None`.
        """
        raw = self["csl"]
        if isinstance(raw, str):
            return raw
        return None

    @property
    def css(self) -> list[str]:
        """Get the normalized list of custom CSS file paths.

        Accepts a single path string or a list of paths under `site.css` in
        `great-docs.yml`. Paths are relative to the project root.

        Returns
        -------
        list[str]
            List of `.css` file paths, or an empty list if none.
        """
        raw = self.site.get("css")
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [s for s in raw if isinstance(s, str)]
        return []

    @property
    def nav_icons(self) -> dict[str, dict[str, str]] | None:
        """Get the normalized navigation icons configuration.

        Returns
        -------
        dict | None
            A dict with optional `navbar` and `sidebar` keys, each mapping navigation label text to
            a Lucide icon name. Returns `None` when not configured.
        """
        raw = self["nav_icons"]
        if raw is None or raw is False:
            return None
        if isinstance(raw, dict):
            result: dict[str, dict[str, str]] = {}
            for scope in ("navbar", "sidebar"):
                mapping = raw.get(scope)
                if isinstance(mapping, dict):
                    result[scope] = {str(k): str(v) for k, v in mapping.items()}
            return result if result else None
        return None

    @property
    def nav_icons_navbar(self) -> dict[str, str]:
        """Get the navbar icon mapping (label -> icon name)."""
        icons = self.nav_icons
        if icons is None:
            return {}
        return icons.get("navbar", {})

    @property
    def nav_icons_sidebar(self) -> dict[str, str]:
        """Get the sidebar icon mapping (label -> icon name)."""
        icons = self.nav_icons
        if icons is None:
            return {}
        return icons.get("sidebar", {})

    @property
    def attribution(self) -> bool:
        """Whether to show Great Docs attribution in the footer."""
        return bool(self["attribution"])

    @property
    def accent_color(self) -> dict[str, str] | None:
        """Get the normalized accent color configuration.

        Returns
        -------
        dict[str, str] | None
            A dict with `"light"` and/or `"dark"` keys mapping to CSS color strings. Returns `None`
            when not configured.
        """
        raw = self["accent_color"]
        if raw is None or raw is False:
            return None
        if isinstance(raw, str):
            return {"light": raw, "dark": raw}
        if isinstance(raw, dict):
            result: dict[str, str] = {}
            for key in ("light", "dark"):
                val = raw.get(key)
                if val and isinstance(val, str):
                    result[key] = val
            return result if result else None
        return None

    @property
    def navbar_style(self) -> str | None:
        """Get the navbar gradient preset name."""
        raw = self["navbar_style"]
        if raw and isinstance(raw, str):
            return raw
        return None

    @property
    def navbar_color(self) -> dict[str, str] | None:
        """Get the normalized navbar color configuration.

        Returns
        -------
        dict[str, str] | None
            A dict with `"light"` and/or `"dark"` keys mapping to CSS color strings. Returns `None`
            when not configured or when `navbar_style` (gradient) takes precedence.
        """
        if self.navbar_style:
            return None
        raw = self["navbar_color"]
        if raw is None or raw is False:
            return None
        if isinstance(raw, str):
            return {"light": raw, "dark": raw}
        if isinstance(raw, dict):
            result: dict[str, str] = {}
            for key in ("light", "dark"):
                val = raw.get(key)
                if val and isinstance(val, str):
                    result[key] = val
            return result if result else None
        return None

    @property
    def navbar_order(self) -> list[str] | None:
        """Explicit ordering of navbar items by their display text."""
        try:
            raw = self["navbar_order"]
        except KeyError:
            return None
        if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
            return raw
        return None

    @property
    def content_style(self) -> dict[str, str] | None:
        """The content-area gradient config, or None when no preset is set"""
        preset = self["content_style.preset"]
        if not preset or not isinstance(preset, str):
            return None
        pages = self["content_style.pages"]
        if pages not in ("all", "homepage"):
            pages = "all"
        return {"preset": preset, "pages": pages}

    @property
    def scale_to_fit(self) -> list[str] | None:
        """Get the list of CSS selectors for auto-scale-to-fit."""
        raw = self["scale_to_fit"]
        if raw is None or raw is False:
            return None
        if isinstance(raw, list):
            return [s for s in raw if isinstance(s, str) and s.strip()]
        if isinstance(raw, str):
            return [raw]
        return None

    # ── Social Cards Properties ────────────────────────────────────────────

    _SCALE_KEYWORDS = frozenset({"mobile", "tablet", "desktop"})

    @property
    def scale_to_fit_min_scale(self) -> float | str | None:
        """Get the minimum scale threshold for scale-to-fit.

        Returns a float (0-1), a keyword (`"mobile"`, `"tablet"`, `"desktop"`), or `None`.
        """
        raw = self["scale_to_fit_min_scale"]
        if raw is None or raw is False:
            return None
        if isinstance(raw, str):
            key = raw.strip().lower()
            if key in self._SCALE_KEYWORDS:
                return key
            return None
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return None
        if 0 < val < 1:
            return val
        return None

    @property
    def social_cards_enabled(self) -> bool:
        """Whether social card meta tags are enabled"""
        return bool(self["social_cards.enabled"])

    @property
    def social_cards_image(self) -> str | None:
        """Default social card image path"""
        return self["social_cards.image"]

    @property
    def social_cards_twitter_card(self) -> str | None:
        """Twitter card type override"""
        return self["social_cards.twitter_card"]

    @property
    def social_cards_twitter_site(self) -> str | None:
        """Twitter site `@handle`"""
        return self["social_cards.twitter_site"]

    # ── Page Status Properties ────────────────────────────────────────────

    @property
    def page_status_enabled(self) -> bool:
        """Whether page status badges are enabled"""
        return bool(self["page_status.enabled"])

    @property
    def page_status_show_in_sidebar(self) -> bool:
        """Whether status badges appear in the sidebar"""
        return self.page_status_enabled and self["page_status.show_in_sidebar"]

    @property
    def page_status_show_on_pages(self) -> bool:
        """Whether status indicators appear below page titles"""
        return self.page_status_enabled and self["page_status.show_on_pages"]

    @property
    def page_status_definitions(self) -> dict[str, dict[str, str]]:
        """Status definitions (built-in plus any user overrides)"""
        return self["page_status.statuses"]

    # ── Page Tags Properties ─────────────────────────────────────────────

    @property
    def tags_enabled(self) -> bool:
        """Whether page tags are enabled"""
        return bool(self["tags.enabled"])

    @property
    def tags_index_page(self) -> bool:
        """Whether a tags index page is generated"""
        return self.tags_enabled and self["tags.index_page"]

    @property
    def tags_show_on_pages(self) -> bool:
        """Whether tags are rendered above page titles"""
        return self.tags_enabled and self["tags.show_on_pages"]

    @property
    def tags_location(self) -> str:
        """Default tag pill placement, `"top"` or `"bottom"`"""
        val = self["tags.location"]
        if val in ("top", "bottom"):
            return val
        return "top"

    @property
    def tags_hierarchical(self) -> bool:
        """Whether hierarchical tags (using '/') are supported"""
        return self["tags.hierarchical"]

    @property
    def tags_icons(self) -> dict[str, str]:
        """Tag-to-icon mapping"""
        return self["tags.icons"]

    @property
    def tags_shadow(self) -> list[str]:
        """Shadow tags, hidden from public view"""
        return self["tags.shadow"]

    @property
    def tags_scoped(self) -> bool:
        """Whether scoped tag listings per section are enabled"""
        return self["tags.scoped"]

    # ── SEO Configuration Properties ─────────────────────────────────────────

    @property
    def seo_enabled(self) -> bool:
        """Check if SEO features are enabled."""
        return self["seo.enabled"]

    @property
    def sitemap_enabled(self) -> bool:
        """Check if sitemap.xml generation is enabled."""
        return self.seo_enabled and self["seo.sitemap.enabled"]

    @property
    def sitemap_changefreq(self) -> dict[str, str]:
        """Sitemap change frequency by page type"""
        return self["seo.sitemap.changefreq"]

    @property
    def sitemap_priority(self) -> dict[str, float]:
        """Sitemap priority by page type"""
        return self["seo.sitemap.priority"]

    @property
    def robots_enabled(self) -> bool:
        """Check if robots.txt generation is enabled."""
        return self.seo_enabled and self["seo.robots.enabled"]

    @property
    def robots_allow_all(self) -> bool:
        """Check if robots.txt should allow all crawlers."""
        return self["seo.robots.allow_all"]

    @property
    def robots_disallow(self) -> list[str]:
        """Get the list of paths to disallow in robots.txt."""
        return self["seo.robots.disallow"]

    @property
    def robots_crawl_delay(self) -> int | None:
        """Get the optional crawl delay in seconds."""
        return self["seo.robots.crawl_delay"]

    @property
    def robots_extra_rules(self) -> list[str]:
        """Get additional robots.txt rules."""
        return self["seo.robots.extra_rules"]

    @property
    def canonical_enabled(self) -> bool:
        """Check if canonical URLs are enabled."""
        return self.seo_enabled and self["seo.canonical.enabled"]

    @property
    def canonical_base_url(self) -> str | None:
        """Get the canonical base URL."""
        return self["seo.canonical.base_url"]

    @property
    def seo_title_template(self) -> str:
        """Get the page title template."""
        return self["seo.title_template"]

    @property
    def structured_data_enabled(self) -> bool:
        """Check if JSON-LD structured data is enabled."""
        return self.seo_enabled and self["seo.structured_data.enabled"]

    @property
    def structured_data_type(self) -> str:
        """Get the Schema.org type for structured data."""
        return self["seo.structured_data.type"]

    @property
    def seo_default_description(self) -> str | None:
        """Get the default meta description."""
        return self["seo.default_description"]

    def exists(self) -> bool:
        """Check if the configuration file exists."""
        return self.config_path.exists()

    def to_dict(self) -> dict[str, Any]:
        """
        Get the full configuration as a dictionary.

        Returns
        -------
        dict
            The complete configuration.
        """
        return self._config.copy()


def load_config(project_root: Path | str) -> Config:
    """
    Load Great Docs configuration from a project.

    Parameters
    ----------
    project_root
        Path to the project root directory.

    Returns
    -------
    Config
        The loaded configuration.
    """
    return Config(Path(project_root))


_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][\w-]*):")


def create_default_config(overrides: dict[str, str] | None = None) -> str:
    """
    Generate great-docs.yml content from the shipped default template

    The `great-docs.default.yml` template is emitted with every live value line
    commented out, so a fresh file documents every option without overriding
    the packaged defaults. A whole live block is commented as one unit: the
    top-level key and every line beneath it — nested keys *and* any interleaved
    prose comments — are prefixed with `# ` at column 0. Interleaved prose thus
    carries a second `#`, so a user can uncomment a whole block (strip one
    `# `) and get valid YAML with the prose still commented. Section headers and
    pure example blocks (comment-only, no live key) are left untouched. Any
    top-level key named in `overrides` is emitted live, with its default (and
    any indented block body) replaced by the supplied text.

    Parameters
    ----------
    overrides
        Maps a top-level key to pre-rendered YAML text that replaces the
        commented default for that key. Used by `great-docs init` to splice in
        detected values (`parser`, `dynamic`, `module`, `authors`, `reference`).

    Returns
    -------
    str
        The rendered great-docs.yml content.
    """
    text = (
        resources.files("great_docs")
        .joinpath("assets", "great-docs.default.yml")
        .read_text(encoding="utf-8")
    )
    overrides = overrides or {}
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_block = False
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1

        if not line.strip():
            out.append(line)  # blank line — preserve, stay in the current block
            continue

        body = line.lstrip(" ")
        indented = body != line

        if indented:
            # Inside a live block, comment every line (nested keys and
            # interleaved prose alike) at column 0; outside one, leave example
            # bodies untouched.
            out.append(f"# {line}" if in_block else line)
            continue

        if body.startswith("#"):
            out.append(line)  # section header / doc / pure example key
            in_block = False
            continue

        # Column-0 live key: opens a block whose indented body follows.
        match = _TOP_LEVEL_KEY.match(line)
        key = match.group(1) if match else None
        if key is not None and key in overrides:
            out.append(overrides[key] + "\n")
            # Drop the replaced key's old block body (indented lines).
            while i < len(lines) and lines[i].strip() and lines[i][:1] in (" ", "\t"):
                i += 1
            in_block = False
        else:
            out.append(f"# {line}")
            in_block = True
    return "".join(out)
