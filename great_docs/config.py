from pathlib import Path
from typing import Any

from yaml12 import read_yaml

# Default configuration values
DEFAULT_CONFIG: dict[str, Any] = {
    # Module name (importable name, if different from project name)
    # e.g., project 'py-yaml12' might have module 'yaml12'
    "module": None,
    # Display name for the site (used in navbar/title)
    # If not provided, uses the package name as-is
    "display_name": None,
    # Docstring parser format
    "parser": "numpy",  # "numpy" (default), "google", or "sphinx"
    # Dynamic introspection mode for API reference generation
    "dynamic": True,  # True (default) or False for packages with cyclic aliases
    # Jupyter kernel for executing code cells
    "jupyter": "python3",  # Default kernel for Quarto computations
    # API discovery settings
    "exclude": [],
    # GitHub integration
    "repo": None,  # GitHub repository URL override (e.g., "https://github.com/owner/repo")
    "github_style": "widget",  # "widget" (shows stars) or "icon"
    # Source link configuration
    "source": {
        "enabled": True,
        "branch": None,  # Auto-detect from git
        "path": None,  # Auto-detect
        "placement": "usage",  # "usage" (default) or "title"
    },
    # Sidebar filter configuration
    "sidebar_filter": {
        "enabled": True,
        "min_items": 20,
    },
    # CLI documentation configuration
    "cli": {
        "enabled": False,
        "module": None,
        "name": None,
    },
    # Dark mode toggle
    "dark_mode_toggle": True,
    # Authors (rich author metadata)
    "authors": [],
    # Funding organization (copyright holder, funder)
    # Example: {"name": "Posit Software, PBC", "roles": ["Copyright holder", "funder"], "ror": "https://ror.org/03wc8by49"}
    "funding": None,
    # Site settings (forwarded to _quarto.yml format.html)
    "site": {
        "theme": "flatly",
        "toc": True,
        "toc-depth": 2,
        # Language for UI text (BCP 47 code, e.g., "en", "fr", "de", "ja", "zh-Hans")
        # Translates navbar labels, widget text, tooltips, and accessibility labels
        "language": "en",
        # Page metadata timestamps
        "show_dates": False,  # Display creation/modification dates in footer
        "date_format": "%B %d, %Y",  # Python strftime format (e.g., "March 24, 2026")
        "show_author": True,  # Show author attribution when show_dates is enabled
        "show_security": True,  # Show security policy page when SECURITY.md exists
    },
    # Team author (catch-all for auto-generated pages when authorship is shown)
    # Example: {"name": "Great Tables Team", "image": "assets/team-avatar.png", "url": "https://..."}
    "team_author": None,
    # Changelog configuration (from GitHub Releases)
    "changelog": {
        "enabled": True,
        "max_releases": 50,
    },
    # Custom sections (generic page groups: examples, tutorials, blog, etc.)
    # Each entry: {"title": str, "dir": str, "index": bool, "navbar_after": str | None}
    "sections": [],
    # Custom static HTML pages.
    # None: auto-discover from project_root/custom/
    # False: disable custom page discovery entirely
    # str: one source directory, output defaults to its basename
    # dict: {"dir": str, "output": str | None}
    # list[str | dict]: multiple source directories
    "custom_pages": None,
    # Homepage mode
    # "index" (default): separate homepage from README / index source
    # "user_guide": first user-guide page becomes the landing page
    "homepage": "index",
    # User Guide configuration
    # If None, auto-discovers from user_guide/ directory
    # If a string, uses that as the directory path
    # If a list of section dicts, uses explicit ordering (overrides frontmatter sections)
    "user_guide": None,
    # API Reference configuration (explicit section ordering)
    # If not provided, auto-generates sections from discovered exports
    "reference": [],
    # Logo configuration
    # str: path to a single logo file (used for all contexts)
    # dict: {"light": "...", "dark": "...", "alt": "...", "height": "...", "href": "...", "show_title": False}
    # None: auto-detect from conventional paths, or skip if nothing found
    "logo": None,
    # Favicon configuration
    # str: path to a single favicon file
    # dict: {"icon": "...", "apple_touch": "...", "og_image": "..."}
    # None: auto-generate from logo, or skip if no logo
    "favicon": None,
    # Hero section configuration for the landing page
    # None: auto-enable when a logo is configured
    # True/False: force enable/disable
    # dict: {"enabled": bool, "logo": str|dict|false, "logo_height": str,
    #        "name": str|false, "tagline": str|false, "badges": "auto"|list|false}
    "hero": None,
    # Markdown pages (.md generation + copy-page widget)
    # True (default): generate .md pages and show the copy/view widget.
    # False: disable both.
    # Dict form: {"widget": False} generates .md pages but hides the widget.
    "markdown_pages": True,
    # Announcement banner (site-wide banner above the navbar)
    # None/False: no banner (default)
    # str: banner message text (plain text or inline HTML)
    # dict: {"content": str, "type": "info"|"warning"|"success"|"danger",
    #        "dismissable": bool, "url": str|None}
    "announcement": None,
    # Navbar gradient preset (e.g., "sky", "peach", "lilac", etc.)
    "navbar_style": None,
    # Navbar solid background color (CSS color: hex, named, etc.)
    # str: same color for both light and dark mode
    # dict: {"light": str, "dark": str} for per-mode colors
    # Text color is automatically chosen (light or dark) for contrast using APCA.
    # Overridden when navbar_style (gradient) is set.
    "navbar_color": None,
    # Content area gradient preset (same preset names as navbar_style)
    # Adds a subtle radial glow at the top of the main content area
    # str: preset name (applies to all pages)
    # dict: {"preset": str, "pages": "all"|"homepage"}
    "content_style": None,
    # Navigation icons (Lucide icon set)
    # Prepend icons to sidebar and navbar navigation entries.
    # None/False: disabled (default)
    # dict: {"navbar": {"Label": "icon-name"}, "sidebar": {"Label": "icon-name"}}
    "nav_icons": None,
    # Keyboard navigation & shortcuts
    # True (default): enable keyboard shortcuts and help overlay
    # False: disable keyboard navigation
    "keyboard_nav": True,
    # Back-to-top floating button
    # True (default): show back-to-top button on all pages
    # False: disable back-to-top button
    "back_to_top": True,
    # Attribution text in the footer ("Site created with Great Docs")
    # True (default): show attribution
    # False: hide attribution
    "attribution": True,
    # Custom HTML to include in the <head> of every page
    # str: inline HTML text (e.g., a <script> or <link> tag)
    # list[str | dict]: list of inline text strings or {"text": ...} / {"file": ...} entries
    "include_in_header": [],
    # Agent Skills (skill.md) generation
    # Generates a SKILL.md file conforming to the Agent Skills specification
    # (https://agentskills.io/) so coding agents can learn to use the package.
    "skill": {
        "enabled": True,
        "file": None,  # Path to a hand-written SKILL.md (overrides auto-generation)
        "well_known": True,  # Also serve at /.well-known/skills/default/SKILL.md
        "gotchas": [],  # List of gotcha strings for the Gotchas section
        "best_practices": [],  # List of best-practice strings
        "decision_table": [],  # Manual rows: [{"need": "...", "use": "..."}]
        "extra_body": None,  # Path to extra Markdown to append to the generated body
    },
    # Social Cards & Open Graph
    # Auto-generate <meta> tags for social media previews (LinkedIn, Discord, Slack,
    # Bluesky, Mastodon, X/Twitter, etc.)
    # True: enable with defaults
    # False/None: disable
    # dict: fine-grained control
    "social_cards": {
        "enabled": True,  # Master switch for social card meta tags
        # Default image for og:image / twitter:image (path relative to project root)
        # None: no default image (individual pages can still set via frontmatter)
        "image": None,
        # Twitter/X card type: "summary", "summary_large_image"
        # "summary_large_image" is used when an image is provided, "summary" otherwise
        "twitter_card": None,  # None = auto-detect based on image
        # Twitter/X @handle for the site (e.g., "@posaboron")
        "twitter_site": None,
    },
    # Page Status Badges
    # Visual indicators for page lifecycle status in sidebar navigation.
    # Pages set `status: new` (or `deprecated`, etc.) in frontmatter.
    # True: enable with defaults
    # False: disable
    # dict: fine-grained control
    "page_status": {
        "enabled": False,  # Master switch for page status badges
        # Show status badges next to sidebar navigation links
        "show_in_sidebar": True,
        # Show status indicator below page titles (like tags)
        "show_on_pages": True,
        # Built-in status definitions (can be extended/overridden)
        # Each status: {label, icon, color, description}
        "statuses": {
            "new": {
                "label": "New",
                "icon": "sparkles",
                "color": "#10b981",  # Emerald green
                "description": "Recently added",
            },
            "updated": {
                "label": "Updated",
                "icon": "refresh-cw",
                "color": "#3b82f6",  # Blue
                "description": "Recently updated",
            },
            "beta": {
                "label": "Beta",
                "icon": "flask-conical",
                "color": "#f59e0b",  # Amber
                "description": "Beta feature",
            },
            "deprecated": {
                "label": "Deprecated",
                "icon": "triangle-alert",
                "color": "#ef4444",  # Red
                "description": "May be removed in a future release",
            },
            "experimental": {
                "label": "Experimental",
                "icon": "beaker",
                "color": "#8b5cf6",  # Purple
                "description": "API may change without notice",
            },
        },
    },
    # Page Tags
    # Categorize pages with tags for improved discoverability.
    # Tags are added via frontmatter (`tags: [Python, Testing, API]`).
    # True: enable with defaults
    # False: disable
    # dict: fine-grained control
    "tags": {
        "enabled": False,  # Master switch for page tags
        # Auto-generate a tags index page listing all tags and linked pages
        "index_page": True,
        # Render tag pills above page titles with links to the tag index
        "show_on_pages": True,
        # Support hierarchical tags with "/" separator (e.g., "Python/Testing")
        "hierarchical": True,
        # Optional tag icons: dict mapping tag names to Lucide icon names
        # e.g., {"Python": "code", "Tutorial": "book-open"}
        "icons": {},
        # Shadow tags: list of tag names hidden from public view (for internal
        # organization only). Shadow-tagged pages are indexed but tags are not
        # rendered on the page or shown in the tag index.
        "shadow": [],
        # Scoped listings: when True, section pages (user guide, recipes, etc.)
        # show a tag cloud scoped to that section
        "scoped": False,
    },
    # SEO configuration for search engine optimization
    # Generates sitemap.xml, robots.txt, and adds metadata for better discoverability
    "seo": {
        "enabled": True,  # Master switch for all SEO features
        # Sitemap configuration
        "sitemap": {
            "enabled": True,  # Generate sitemap.xml
            "changefreq": {
                # Change frequencies by page type (always|hourly|daily|weekly|monthly|yearly|never)
                "homepage": "weekly",
                "reference": "monthly",
                "user_guide": "monthly",
                "changelog": "weekly",
                "default": "monthly",
            },
            "priority": {
                # Priority values by page type (0.0 to 1.0)
                "homepage": 1.0,
                "reference": 0.8,
                "user_guide": 0.9,
                "changelog": 0.6,
                "default": 0.5,
            },
        },
        # Robots.txt configuration
        "robots": {
            "enabled": True,  # Generate robots.txt
            "allow_all": True,  # Allow all crawlers by default
            "disallow": [],  # List of paths to disallow (e.g., ["/drafts/", "/_internal/"])
            "crawl_delay": None,  # Optional crawl delay in seconds
            "extra_rules": [],  # Additional rules as strings (e.g., ["User-agent: GPTBot", "Disallow: /"])
        },
        # Canonical URL configuration
        "canonical": {
            "enabled": True,  # Add canonical URLs to pages
            "base_url": None,  # Base URL (e.g., "https://example.github.io/pkg/")
            # Auto-detected from GitHub Pages URL if not provided
        },
        # Page title template
        # Supports {page_title} and {site_name} placeholders
        "title_template": "{page_title} | {site_name}",
        # JSON-LD structured data for software documentation
        "structured_data": {
            "enabled": True,  # Add JSON-LD to pages
            "type": "SoftwareSourceCode",  # Schema.org type
            # Additional fields auto-populated from package metadata
        },
        # Default meta description (used when page has no description)
        "default_description": None,  # Falls back to package description
    },
}


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
        config = DEFAULT_CONFIG.copy()

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    user_config = read_yaml(f) or {}

                # Deep merge user config with defaults
                config = self._merge_config(config, user_config)
            except ValueError as e:
                print(f"Warning: Error parsing great-docs.yml: {e}")
            except Exception as e:
                print(f"Warning: Could not read great-docs.yml: {e}")

        return config

    def _merge_config(self, defaults: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        """
        Deep merge user configuration with defaults.

        Parameters
        ----------
        defaults
            Default configuration values.
        user
            User-provided configuration values.

        Returns
        -------
        dict
            Merged configuration.
        """
        result = defaults.copy()

        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value

        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Parameters
        ----------
        key
            The configuration key (supports dot notation for nested keys).
        default
            Default value if key is not found.

        Returns
        -------
        Any
            The configuration value or default.
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def exclude(self) -> list[str]:
        """Get the list of items to exclude."""
        return self.get("exclude", [])

    @property
    def repo(self) -> str | None:
        """Get the GitHub repository URL override."""
        return self.get("repo")

    @property
    def github_style(self) -> str:
        """Get the GitHub link style."""
        return self.get("github_style", "widget")

    @property
    def source_enabled(self) -> bool:
        """Check if source links are enabled."""
        return self.get("source.enabled", True)

    @property
    def source_branch(self) -> str | None:
        """Get the source link branch."""
        return self.get("source.branch")

    @property
    def source_path(self) -> str | None:
        """Get the custom source path."""
        return self.get("source.path")

    @property
    def source_placement(self) -> str:
        """Get the source link placement."""
        return self.get("source.placement", "usage")

    @property
    def sidebar_filter_enabled(self) -> bool:
        """Check if sidebar filter is enabled."""
        return self.get("sidebar_filter.enabled", True)

    @property
    def sidebar_filter_min_items(self) -> int:
        """Get the minimum items for sidebar filter."""
        return self.get("sidebar_filter.min_items", 20)

    @property
    def cli_enabled(self) -> bool:
        """Check if CLI documentation is enabled."""
        return self.get("cli.enabled", False)

    @property
    def cli_module(self) -> str | None:
        """Get the CLI module path."""
        return self.get("cli.module")

    @property
    def cli_name(self) -> str | None:
        """Get the CLI command name."""
        return self.get("cli.name")

    @property
    def skill_enabled(self) -> bool:
        """Check if skill.md generation is enabled."""
        return self.get("skill.enabled", True)

    @property
    def skill_file(self) -> str | None:
        """Get the path to a hand-written SKILL.md override."""
        return self.get("skill.file")

    @property
    def skill_well_known(self) -> bool:
        """Check if .well-known/skills/default/SKILL.md should be generated."""
        return self.get("skill.well_known", True)

    @property
    def skill_gotchas(self) -> list[str]:
        """Get the list of gotcha strings for the SKILL.md Gotchas section."""
        return self.get("skill.gotchas", [])

    @property
    def skill_best_practices(self) -> list[str]:
        """Get the list of best-practice strings for the SKILL.md."""
        return self.get("skill.best_practices", [])

    @property
    def skill_decision_table(self) -> list[dict]:
        """Get manual decision table rows for the SKILL.md."""
        return self.get("skill.decision_table", [])

    @property
    def skill_extra_body(self) -> str | None:
        """Get the path to extra Markdown to append to the generated SKILL.md body."""
        return self.get("skill.extra_body")

    @property
    def changelog_enabled(self) -> bool:
        """Check if changelog generation from GitHub Releases is enabled."""
        return self.get("changelog.enabled", True)

    @property
    def changelog_max_releases(self) -> int:
        """Get the maximum number of GitHub Releases to include."""
        return self.get("changelog.max_releases", 50)

    @property
    def sections(self) -> list[dict]:
        """Get the custom sections configuration."""
        return self.get("sections", [])

    @property
    def custom_pages(self) -> list[dict[str, str]]:
        """Get normalized custom static page source directories.

        Returns a list of dicts with ``dir`` and ``output`` keys.

        - When ``custom_pages`` is omitted, falls back to ``custom/``.
        - When ``custom_pages`` is ``false``, returns an empty list.
        - When ``custom_pages`` is a string, that path is used and the output
          prefix defaults to the basename of the path.
        - When ``custom_pages`` is a dict, it may specify ``dir`` and optional
          ``output``.
        - When ``custom_pages`` is a list, each entry may be a string or dict.
        """
        raw = self.get("custom_pages")

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
        return self.get("dark_mode_toggle", True)

    @property
    def keyboard_nav(self) -> bool:
        """Check if keyboard navigation shortcuts are enabled."""
        return self.get("keyboard_nav", True)

    @property
    def back_to_top(self) -> bool:
        """Check if back-to-top button is enabled."""
        return self.get("back_to_top", True)

    @property
    def markdown_pages(self) -> bool:
        """Check if Markdown page generation is enabled."""
        val = self.get("markdown_pages", True)
        if isinstance(val, dict):
            return val.get("enabled", True)
        return bool(val)

    @property
    def markdown_pages_widget(self) -> bool:
        """Check if the copy-page widget is shown (requires markdown_pages)."""
        val = self.get("markdown_pages", True)
        if isinstance(val, dict):
            return val.get("widget", True) and val.get("enabled", True)
        return bool(val)

    @property
    def parser(self) -> str:
        """Get the docstring parser format (numpy, google, or sphinx)."""
        return self.get("parser", "numpy")

    @property
    def dynamic(self) -> bool:
        """Get the dynamic introspection mode for API reference generation."""
        return self.get("dynamic", True)

    @property
    def module(self) -> str | None:
        """
        Get the explicit module name (importable name).

        Use this when the importable module name differs from the project name,
        e.g., project 'py-yaml12' with module 'yaml12'.
        """
        return self.get("module")

    @property
    def display_name(self) -> str | None:
        """
        Get the display name for the site.

        Use this to customize how the package name appears in the navbar/title,
        e.g., 'Great Docs' instead of 'great_docs' or 'great-docs'.
        """
        return self.get("display_name")

    @property
    def homepage(self) -> str:
        """Get the homepage mode ('index' or 'user_guide').

        Returns
        -------
        str
            The validated homepage mode. Falls back to 'index' if an
            invalid value is configured.
        """
        value = self.get("homepage", "index")
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
        return self.get("user_guide")

    @property
    def user_guide_is_explicit(self) -> bool:
        """Check if user guide uses explicit section ordering."""
        return isinstance(self.get("user_guide"), list)

    @property
    def user_guide_dir(self) -> str | None:
        """Get the user guide directory path (only when it's a string)."""
        val = self.get("user_guide")
        return val if isinstance(val, str) else None

    @property
    def reference_enabled(self) -> bool:
        """Whether API reference generation is enabled.

        Returns `False` when the config contains `reference: false`. Defaults to `True`.
        """
        val = self.get("reference", [])
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
        val = self.get("reference", [])
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
        val = self.get("reference", [])
        if isinstance(val, dict):
            return val.get("title")
        return None

    @property
    def reference_desc(self) -> str | None:
        """Get the custom API reference description, if set.

        Supports `reference: {desc: "Description text..."}` in great-docs.yml. Returns `None` when
        no description is configured.
        """
        val = self.get("reference", [])
        if isinstance(val, dict):
            return val.get("desc")
        return None

    @property
    def authors(self) -> list[dict[str, Any]]:
        """Get the rich author metadata."""
        return self.get("authors", [])

    @property
    def funding(self) -> dict[str, Any] | None:
        """
        Get the funding organization metadata.

        Returns a dict with keys: name, roles (list), ror (ROR URL).
        Example: {"name": "Posit Software, PBC", "roles": ["Copyright holder", "funder"], "ror": "https://ror.org/03wc8by49"}
        """
        return self.get("funding")

    @property
    def site(self) -> dict[str, Any]:
        """Get the site settings (forwarded to _quarto.yml format.html)."""
        return self.get("site", {})

    @property
    def show_dates(self) -> bool:
        """Whether to show page metadata timestamps in the footer."""
        return bool(self.site.get("show_dates", False))

    @property
    def date_format(self) -> str:
        """Get the date format string (Python strftime format)."""
        return self.site.get("date_format", "%B %d, %Y")

    @property
    def show_author(self) -> bool:
        """Whether to show author attribution when dates are enabled."""
        return bool(self.site.get("show_author", True))

    @property
    def show_security(self) -> bool:
        """Whether to show the security policy page when SECURITY.md exists."""
        return bool(self.site.get("show_security", True))

    @property
    def language(self) -> str:
        """Get the site UI language (BCP 47 code, default: 'en')."""
        return self.site.get("language", "en")

    @property
    def team_author(self) -> dict[str, Any] | None:
        """Get the team author configuration for auto-generated pages.

        Returns
        -------
        dict | None
            A dict with keys: name (str), image (str|None), url (str|None).
            Returns None when not configured.
        """
        raw = self.get("team_author")
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
        return self.get("jupyter", "python3")

    @property
    def logo(self) -> dict[str, Any] | None:
        """Get the normalized logo configuration.

        Returns
        -------
        dict | None
            Normalized logo dict with at least `light` key, or `None` if no logo is configured.  A
            bare string in `great-docs.yml` is expanded to `{"light": "<path>", "dark": "<path>"}`.
        """
        raw = self.get("logo")
        if raw is None:
            return None
        if isinstance(raw, str):
            return {"light": raw, "dark": raw}
        if isinstance(raw, dict):
            return raw
        return None

    @property
    def logo_show_title(self) -> bool:
        """Whether to show the text title alongside the logo."""
        logo = self.logo
        if isinstance(logo, dict):
            return bool(logo.get("show_title", False))
        return False

    @property
    def hero_enabled(self) -> bool:
        """Whether the hero section is enabled.

        Auto-enables when a logo is configured and `hero` is not explicitly set to `False`.
        """
        raw = self.get("hero")
        if raw is False:
            return False
        if raw is True or isinstance(raw, dict):
            if isinstance(raw, dict) and raw.get("enabled") is False:
                return False
            return True
        # None (default): auto-enable when logo exists
        return self.logo is not None

    @property
    def hero_explicitly_disabled(self) -> bool:
        """Whether the hero was explicitly turned off by the user."""
        raw = self.get("hero")
        if raw is False:
            return True
        if isinstance(raw, dict) and raw.get("enabled") is False:
            return True
        return False

    @property
    def hero(self) -> dict[str, Any]:
        """Get the resolved hero configuration dict.

        Returns a dict with keys: enabled, logo, logo_height, name,
        tagline, badges.  Missing keys are filled with defaults.
        """
        raw = self.get("hero")
        if isinstance(raw, dict):
            return raw
        return {}

    @property
    def hero_logo(self) -> str | dict | None | bool:
        """Get the explicit hero logo config.

        Returns the hero-specific logo value only.  Returns `False` when explicitly suppressed,
        `None` when not configured. The full fallback chain (auto-detected hero logos, navbar logo)
        is handled in `core._build_hero_section`.
        """
        hero = self.hero
        val = hero.get("logo") if hero else None
        if val is False:
            return False
        if val is not None:
            return val
        return None

    @property
    def hero_logo_height(self) -> str:
        """Get the hero logo max-height CSS value."""
        hero = self.hero
        return hero.get("logo_height", "200px") if hero else "200px"

    @property
    def hero_name(self) -> str | None:
        """Get the hero name, falling back to display_name.

        Returns `None` when explicitly suppressed (`false`).
        """
        hero = self.hero
        val = hero.get("name") if hero else None
        if val is False:
            return None
        if val is not None:
            return val
        return self.display_name

    @property
    def hero_tagline(self) -> str | None:
        """Get the hero tagline.

        Returns `None` when explicitly suppressed (`false`). Auto-resolved from package metadata in
        core.py.
        """
        hero = self.hero
        val = hero.get("tagline") if hero else None
        if val is False:
            return None
        return val

    @property
    def hero_badges(self) -> str | list | None:
        """Get the hero badges config.

        Returns `"auto"` (default, extract from README), an explicit list of badge dicts, or `None`
        (disabled).
        """
        hero = self.hero
        val = hero.get("badges") if hero else None
        if val is False:
            return None
        if val is not None:
            return val
        # Default: auto-extract from README
        return "auto"

    @property
    def favicon(self) -> dict[str, Any] | None:
        """Get the normalized favicon configuration.

        Returns
        -------
        dict | None
            Normalized favicon dict with at least `icon` key, or `None` if no favicon is explicitly
            configured (auto-generation may still produce one from the logo).
        """
        raw = self.get("favicon")
        if raw is None:
            return None
        if isinstance(raw, str):
            return {"icon": raw}
        if isinstance(raw, dict):
            return raw
        return None

    @property
    def announcement(self) -> dict[str, Any] | None:
        """Get the normalized announcement banner configuration.

        Returns
        -------
        dict | None
            Normalized dict with keys: content, type, dismissable, url. Returns `None` if no
            announcement is configured.
        """
        raw = self.get("announcement")
        if raw is None or raw is False:
            return None
        if isinstance(raw, str):
            return {"content": raw, "type": "info", "dismissable": True, "url": None, "style": None}
        if isinstance(raw, dict):
            content = raw.get("content")
            if not content:
                return None
            return {
                "content": content,
                "type": raw.get("type", "info"),
                "dismissable": raw.get("dismissable", True),
                "url": raw.get("url"),
                "style": raw.get("style"),
            }
        return None

    @property
    def include_in_header(self) -> list[dict[str, str]]:
        """Get the normalized include-in-header entries.

        Returns a list of Quarto-compatible include-in-header items (each a dict with either a
        "text" or "file" key).
        """
        raw = self.get("include_in_header", [])
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
    def nav_icons(self) -> dict[str, dict[str, str]] | None:
        """Get the normalized navigation icons configuration.

        Returns
        -------
        dict | None
            A dict with optional `navbar` and `sidebar` keys, each mapping navigation label text to
            a Lucide icon name. Returns `None` when not configured.
        """
        raw = self.get("nav_icons")
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
        return bool(self.get("attribution", True))

    @property
    def navbar_style(self) -> str | None:
        """Get the navbar gradient preset name."""
        raw = self.get("navbar_style")
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
        raw = self.get("navbar_color")
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
    def content_style(self) -> dict[str, str] | None:
        """Get the normalized content area gradient configuration."""
        raw = self.get("content_style")
        if raw is None or raw is False:
            return None
        if isinstance(raw, str):
            return {"preset": raw, "pages": "all"}
        if isinstance(raw, dict):
            preset = raw.get("preset")
            if not preset or not isinstance(preset, str):
                return None
            pages = raw.get("pages", "all")
            if pages not in ("all", "homepage"):
                pages = "all"
            return {"preset": preset, "pages": pages}
        return None

    # ── Social Cards Properties ────────────────────────────────────────────

    @property
    def social_cards_enabled(self) -> bool:
        """Check if social card meta tags are enabled."""
        raw = self.get("social_cards")
        if raw is None or raw is False:
            return False
        if raw is True:
            return True
        if isinstance(raw, dict):
            return raw.get("enabled", True)
        return True

    @property
    def social_cards_image(self) -> str | None:
        """Get the default social card image path."""
        raw = self.get("social_cards")
        if isinstance(raw, dict):
            return raw.get("image")
        return None

    @property
    def social_cards_twitter_card(self) -> str | None:
        """Get the Twitter card type override."""
        raw = self.get("social_cards")
        if isinstance(raw, dict):
            return raw.get("twitter_card")
        return None

    @property
    def social_cards_twitter_site(self) -> str | None:
        """Get the Twitter site @handle."""
        raw = self.get("social_cards")
        if isinstance(raw, dict):
            return raw.get("twitter_site")
        return None

    # ── Page Status Properties ────────────────────────────────────────────

    @property
    def page_status_enabled(self) -> bool:
        """Check if page status badges are enabled."""
        raw = self.get("page_status")
        if raw is None or raw is False:
            return False
        if raw is True:
            return True
        if isinstance(raw, dict):
            return raw.get("enabled", False)
        return False

    @property
    def page_status_show_in_sidebar(self) -> bool:
        """Check if status badges should appear in the sidebar."""
        return self.page_status_enabled and self.get("page_status.show_in_sidebar", True)

    @property
    def page_status_show_on_pages(self) -> bool:
        """Check if status indicators should appear below page titles."""
        return self.page_status_enabled and self.get("page_status.show_on_pages", True)

    @property
    def page_status_definitions(self) -> dict[str, dict[str, str]]:
        """Get the status definitions (built-in + custom overrides)."""
        defs = self.get("page_status.statuses")
        if defs and isinstance(defs, dict):
            return defs
        # Shorthand `page_status: true` replaces the entire dict with a bool,
        # so fall back to the built-in defaults.
        return DEFAULT_CONFIG.get("page_status", {}).get("statuses", {})

    # ── Page Tags Properties ─────────────────────────────────────────────

    @property
    def tags_enabled(self) -> bool:
        """Check if page tags are enabled."""
        raw = self.get("tags")
        if raw is None or raw is False:
            return False
        if raw is True:
            return True
        if isinstance(raw, dict):
            return raw.get("enabled", False)
        return False

    @property
    def tags_index_page(self) -> bool:
        """Check if a tags index page should be generated."""
        return self.tags_enabled and self.get("tags.index_page", True)

    @property
    def tags_show_on_pages(self) -> bool:
        """Check if tags should be rendered above page titles."""
        return self.tags_enabled and self.get("tags.show_on_pages", True)

    @property
    def tags_location(self) -> str:
        """Get the default tag pill placement: ``"top"`` or ``"bottom"``."""
        val = self.get("tags.location", "top")
        if val in ("top", "bottom"):
            return val
        return "top"

    @property
    def tags_hierarchical(self) -> bool:
        """Check if hierarchical tags (using '/') are supported."""
        return self.get("tags.hierarchical", True)

    @property
    def tags_icons(self) -> dict[str, str]:
        """Get the tag-to-icon mapping."""
        return self.get("tags.icons", {})

    @property
    def tags_shadow(self) -> list[str]:
        """Get the list of shadow tags (hidden from public view)."""
        return self.get("tags.shadow", [])

    @property
    def tags_scoped(self) -> bool:
        """Check if scoped tag listings per section are enabled."""
        return self.get("tags.scoped", False)

    # ── SEO Configuration Properties ─────────────────────────────────────────

    @property
    def seo_enabled(self) -> bool:
        """Check if SEO features are enabled."""
        return self.get("seo.enabled", True)

    @property
    def sitemap_enabled(self) -> bool:
        """Check if sitemap.xml generation is enabled."""
        return self.seo_enabled and self.get("seo.sitemap.enabled", True)

    @property
    def sitemap_changefreq(self) -> dict[str, str]:
        """Get the sitemap change frequency by page type."""
        defaults = {
            "homepage": "weekly",
            "reference": "monthly",
            "user_guide": "monthly",
            "changelog": "weekly",
            "default": "monthly",
        }
        return {**defaults, **self.get("seo.sitemap.changefreq", {})}

    @property
    def sitemap_priority(self) -> dict[str, float]:
        """Get the sitemap priority by page type."""
        defaults = {
            "homepage": 1.0,
            "reference": 0.8,
            "user_guide": 0.9,
            "changelog": 0.6,
            "default": 0.5,
        }
        return {**defaults, **self.get("seo.sitemap.priority", {})}

    @property
    def robots_enabled(self) -> bool:
        """Check if robots.txt generation is enabled."""
        return self.seo_enabled and self.get("seo.robots.enabled", True)

    @property
    def robots_allow_all(self) -> bool:
        """Check if robots.txt should allow all crawlers."""
        return self.get("seo.robots.allow_all", True)

    @property
    def robots_disallow(self) -> list[str]:
        """Get the list of paths to disallow in robots.txt."""
        return self.get("seo.robots.disallow", [])

    @property
    def robots_crawl_delay(self) -> int | None:
        """Get the optional crawl delay in seconds."""
        return self.get("seo.robots.crawl_delay")

    @property
    def robots_extra_rules(self) -> list[str]:
        """Get additional robots.txt rules."""
        return self.get("seo.robots.extra_rules", [])

    @property
    def canonical_enabled(self) -> bool:
        """Check if canonical URLs are enabled."""
        return self.seo_enabled and self.get("seo.canonical.enabled", True)

    @property
    def canonical_base_url(self) -> str | None:
        """Get the canonical base URL."""
        return self.get("seo.canonical.base_url")

    @property
    def seo_title_template(self) -> str:
        """Get the page title template."""
        return self.get("seo.title_template", "{page_title} | {site_name}")

    @property
    def structured_data_enabled(self) -> bool:
        """Check if JSON-LD structured data is enabled."""
        return self.seo_enabled and self.get("seo.structured_data.enabled", True)

    @property
    def structured_data_type(self) -> str:
        """Get the Schema.org type for structured data."""
        return self.get("seo.structured_data.type", "SoftwareSourceCode")

    @property
    def seo_default_description(self) -> str | None:
        """Get the default meta description."""
        return self.get("seo.default_description")

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


def create_default_config() -> str:
    """
    Generate a default great-docs.yml configuration file content.

    Returns
    -------
    str
        YAML content for a default configuration file.
    """
    return """# Great Docs Configuration
# See https://posit-dev.github.io/great-docs/user-guide/03-configuration.html

# Display Name
# ------------
# Custom display name for your package in the site navbar/title.
# If not provided, uses the actual package name (e.g., 'my_package' or 'my-package').
# Use this to provide a marketing/presentation name (e.g., 'My Package').
# display_name: My Package

# Docstring Parser
# ----------------
# The docstring format used in your package (numpy, google, or sphinx)
# This is auto-detected during initialization, but can be overridden here.
# parser: numpy

# Dynamic Introspection
# ---------------------
# When true, the renderer uses runtime introspection (more accurate for complex packages).
# When false, uses static analysis only (better for packages with cyclic aliases).
# This is auto-detected during initialization based on what works for your package.
# dynamic: true

# Exclusions
# ----------
# Items to exclude from auto-documentation (affects 'init' and 'scan')
# exclude:
#   - InternalClass
#   - helper_function

# Logo & Favicon
# ---------------
# Point to a single logo file (replaces the text title in the navbar):
# logo: assets/logo.svg
#
# For light/dark variants:
# logo:
#   light: assets/logo-light.svg
#   dark: assets/logo-dark.svg
#
# To show the text title alongside the logo, add: show_title: true

# GitHub Integration
# ------------------
# GitHub link style: "widget" (shows stars count) or "icon" (simple icon)
# github_style: widget

# Source Link Configuration
# -------------------------
# source:
#   enabled: true              # Enable/disable source links (default: true)
#   branch: main               # Git branch/tag to link to (default: auto-detect)
#   path: src/package          # Custom source path for monorepos (default: auto-detect)
#   placement: usage           # Where to place the link: "usage" (default) or "title"

# Sidebar Filter
# --------------
# sidebar_filter:
#   enabled: true              # Enable/disable filter (default: true)
#   min_items: 20              # Minimum items before showing filter (default: 20)

# CLI Documentation
# -----------------
# cli:
#   enabled: false             # Enable CLI documentation (default: false)
#   module: my_package.cli     # Module containing Click commands (auto-detected)
#   name: cli                  # Name of the Click command object (auto-detected)

# Changelog (GitHub Releases)
# ---------------------------
# Auto-generate a Changelog page from GitHub Releases.
# changelog:
#   enabled: true              # Enable/disable changelog (default: true)
#   max_releases: 50           # Max releases to include (default: 50)

# Custom Sections
# ---------------
# Add custom page groups (examples, tutorials, blog, etc.) to the site.
# Each section gets a navbar link and a sidebar. An auto-generated
# card-based index page is created only when ``index: true`` is set;
# otherwise the navbar links directly to the first page in the section.
# If you provide your own index.qmd in the directory it is always used.
#
# sections:
#   - title: Examples            # Navbar link text
#     dir: examples              # Source directory (relative to project root)
#     index: true                # Generate card-based index page (default: false)
#     navbar_after: User Guide   # Place after this navbar item (optional)
#   - title: Tutorials
#     dir: tutorials             # No index — navbar links to first page
#   - title: Blog                # Blog section using Quarto's listing directive
#     dir: blog
#     type: blog                 # "blog" for Quarto listing, omit for card grid

# Custom Static Pages
# -------------------
# Add hand-written HTML pages that Great Docs should either wrap with the site
# shell (layout: passthrough) or copy through unchanged (layout: raw).
#
# Omit `custom_pages` to use the conventional `custom/` directory.
# Set `custom_pages: false` to disable discovery.
#
# custom_pages:
#   - dir: marketing             # Source directory (relative to project root)
#     output: py                 # URL/output prefix (optional; defaults to dir basename)
#   - dir: playgrounds
#     output: demos
#
# Short form for a single directory:
# custom_pages: marketing

# Dark Mode Toggle
# ----------------
# Enable/disable the dark mode toggle in navbar (default: true)
# dark_mode_toggle: true

# Markdown Pages
# --------------
# Generate .md companions for every HTML page and show a copy/view-as-Markdown
# widget on each page.  Set to false to disable both (default: true).
# markdown_pages: true
#
# To generate .md pages but hide the widget:
# markdown_pages:
#   widget: false

# User Guide
# ----------
# Custom directory for User Guide .qmd files (relative to project root).
# If not provided, looks for user_guide/ in the project root.
# user_guide: docs/guides
#
# For explicit control over section ordering and grouping:
# user_guide:
#   - section: "Get Started"
#     contents:
#       - text: "Welcome"
#         href: index.qmd
#       - quickstart.qmd
#       - installation.qmd
#   - section: "Advanced Topics"
#     contents:
#       - advanced-config.qmd
#       - extending.qmd
#
# File paths are relative to the user guide directory (no user_guide/ prefix).
# When using explicit ordering, numeric filename prefixes are preserved as-is.

# Author Information
# ------------------
# Author metadata for display in the landing page sidebar and page attribution
# authors:
#   - name: Your Name
#     email: you@example.com
#     role: Lead Developer
#     affiliation: Organization
#     github: yourusername
#     homepage: https://yoursite.com
#     orcid: 0000-0002-1234-5678
#     image: https://github.com/yourusername.png  # Avatar (GitHub URL or local path)

# Team Author
# -----------
# Optional catch-all author for auto-generated pages (reference, changelog, etc.)
# team_author:
#   name: "Project Team"
#   image: "assets/team-avatar.png"
#   url: "https://github.com/org/project"

# Site Settings
# -------------
# These settings are forwarded to _quarto.yml (format.html section)
# site:
#   theme: flatly              # Quarto theme (default: flatly)
#   toc: true                  # Show table of contents (default: true)
#   toc-depth: 2               # TOC heading depth (default: 2)
#   toc-title: On this page    # TOC title (default: "On this page")
#   show_dates: false          # Show page timestamps in footer
#   date_format: "%B %d, %Y"   # Date format (Python strftime)
#   show_author: true          # Show author attribution with dates
#   show_security: true        # Show security policy page (from SECURITY.md)

# Social Cards & Open Graph
# -------------------------
# Auto-generate <meta> tags for social media previews (LinkedIn, Discord, Slack,
# Bluesky, Mastodon, X/Twitter, and other platforms). Enabled by default.
# social_cards: true           # Enable with defaults (same as omitting the key)
# social_cards: false          # Disable social card meta tags
#
# Fine-grained control:
# social_cards:
#   enabled: true
#   image: assets/social-card.png   # Default og:image for all pages
#   twitter_site: "@myhandle"       # Twitter/X site @handle
#   twitter_card: summary_large_image  # "summary" or "summary_large_image"

# Jupyter Kernel
# --------------
# Jupyter kernel to use for executing code cells in .qmd files.
# This is set at the project level so it applies to all pages, including
# auto-generated API reference pages. Can be overridden in individual .qmd
# file frontmatter if needed for special cases.
# jupyter: python3             # Default: python3

# API Reference Structure
# -----------------------
# Explicit control over API reference sections. If not provided, sections are
# auto-generated from discovered exports. Each section has a title, description,
# and list of contents.
#
# For classes, use `members: true` (default) to document methods inline on the
# class page, or `members: false` to exclude methods (you can place them
# explicitly elsewhere in the reference if needed).
#
# reference:
#   - title: Core Classes
#     desc: Main classes for working with the package
#     contents:
#       - name: MyClass
#         members: false       # Don't document methods here
#       - SimpleClass          # Methods documented inline (default)
#
#   - title: Utility Functions
#     desc: Helper functions for common tasks
#     contents:
#       - helper_func
#       - another_func
"""
