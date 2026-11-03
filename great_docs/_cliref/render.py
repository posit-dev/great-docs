"""
Write the command-line reference pages and their sidebar entries

Pages go under `reference/cli/` in the build directory: an index listing every command, a page
for the root command, and one page per subcommand, nested in a directory per group.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

from .._translations import get_translation
from .model import CliCommand

if TYPE_CHECKING:
    from ..config import Config

SidebarItem: TypeAlias = str | dict[str, Any]
"""A sidebar entry: a page path, a labelled link, or a section with its own contents."""


def write_pages(
    config: Config, build_dir: Path, cli: CliCommand, *, report: Callable[[str], None]
) -> list[SidebarItem]:
    """
    Write the reference pages for a command line

    Parameters
    ----------
    config
        The site configuration, for `cli.sections`, `cli.title`, `cli.desc` and `lang`.
    build_dir
        The build directory.
    cli
        The root command.
    report
        Receives the list of pages written.

    Returns
    -------
    :
        The sidebar entries: a labelled link to the index, the root command's page, then a path
        per leaf command and a section per group. When `cli.sections` is set, only the
        top-level commands it names get a page, in the order it names them.
    """
    if not cli:
        return []

    # Explicit `cli.sections` are authoritative, as `reference.sections` are for the API
    # reference: top-level commands they don't name get no page, sidebar entry or index entry.
    if config.cli_sections:
        listed = {name for section in config.cli_sections for name in section.get("contents", [])}
        cli = cli.copy()
        cli["commands"] = [c for c in cli.get("commands", []) if c["name"] in listed]

    cli_ref_dir = build_dir / "reference" / "cli"
    cli_ref_dir.mkdir(parents=True, exist_ok=True)

    generated_files: list[SidebarItem] = []
    generated_paths: list[str] = []

    entry_name = cli.get("entry_point_name") or cli["name"]
    entry_safe = entry_name.replace("-", "_")

    # The index lists every command, as the API reference index lists objects; the root
    # command's own `--help` goes on its own page.
    index_path = cli_ref_dir / "index.qmd"
    _ = index_path.write_text(index_page(config, cli, entry_safe))
    # Label the index entry so it reads apart from the enclosing "CLI Reference" section title,
    # as the "API Index" link does.
    cli_index_label = get_translation("cli_index", config.lang)
    generated_files.append({"text": cli_index_label, "href": "reference/cli/index.qmd"})
    generated_paths.append(str(index_path.relative_to(build_dir)))

    root_path = cli_ref_dir / f"{entry_safe}.qmd"
    _ = root_path.write_text(command_page(config, cli, is_main=True))
    generated_files.append(f"reference/cli/{entry_safe}.qmd")
    generated_paths.append(str(root_path.relative_to(build_dir)))

    subcommand_items = _write_subcommand_pages(
        config, build_dir, cli, cli_ref_dir, "reference/cli", generated_paths
    )

    if config.cli_sections:  # pragma: no cover
        subcommand_items = order_sidebar_items(  # pragma: no cover
            subcommand_items, config.cli_sections
        )
    generated_files.extend(subcommand_items)

    if generated_paths:
        report("Generating CLI reference .qmd files:")
        for p in generated_paths:
            report(f"  - {p}")

    return generated_files


def _write_subcommand_pages(
    config: Config,
    build_dir: Path,
    cmd: CliCommand,
    output_dir: Path,
    rel_prefix: str,
    paths: list[str],
) -> list[SidebarItem]:
    """
    Write a page for each subcommand of a command, recursing into groups

    Parameters
    ----------
    config
        The site configuration, for `lang`.
    build_dir
        The build directory.
    cmd
        The command whose subcommands get pages.
    output_dir
        The directory for the pages.
    rel_prefix
        The sidebar path of `output_dir`, such as `reference/cli/task`.
    paths
        Receives the path of each page written, relative to the build directory.

    Returns
    -------
    :
        A path per leaf command and, per group, a section holding the group's own page and its
        subcommands.
    """
    sidebar_items: list[SidebarItem] = []

    for subcmd in cmd.get("commands", []):
        safe_name = subcmd["name"].replace("-", "_")
        page_path = output_dir / f"{safe_name}.qmd"

        _ = page_path.write_text(command_page(config, subcmd, is_main=False))

        rel_path = f"{rel_prefix}/{safe_name}.qmd"
        paths.append(str(page_path.relative_to(build_dir)))

        if subcmd.get("commands"):
            subcmd_dir = output_dir / safe_name
            subcmd_dir.mkdir(exist_ok=True)
            nested = _write_subcommand_pages(
                config, build_dir, subcmd, subcmd_dir, f"{rel_prefix}/{safe_name}", paths
            )
            sidebar_items.append({"section": subcmd["name"], "contents": [rel_path, *nested]})
        else:
            sidebar_items.append(rel_path)

    return sidebar_items


def index_page(config: Config, cli: CliCommand, entry_safe: str) -> str:
    """
    Render the index page of the command-line reference

    The page links the root command, then one `## Section {.doc-group}` block per section, each
    a definition list of command links with their short help. `cli.sections` gives the
    sections; without it, leaf commands come first, in code order, then one section per group.

    Parameters
    ----------
    config
        The site configuration, for `cli.title`, `cli.desc`, `cli.sections` and `lang`.
    cli
        The root command.
    entry_safe
        The file name, without extension, of the root command's page.

    Returns
    -------
    :
        The Quarto Markdown for `reference/cli/index.qmd`.
    """
    lang = config.lang
    title = config.cli_title or get_translation("cli_reference", lang)

    lines: list[str] = []

    lines.append("---")
    lines.append(f'title: "{title}"')
    lines.append("body-classes: doc-reference doc-cli-reference")
    lines.append("sidebar: cli-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    lines.append("shift-heading-level-by: 0")
    # Disabling breadcrumbs lets Quarto use the page title in the narrow-screen
    # navigation bar; CSS adds the prefix for the reference type.
    lines.append("bread-crumbs: false")
    lines.append("---")
    lines.append("")

    # No body `# {title}` heading: the front matter title provides the page title block (as on
    # the API reference index), which keeps the `## {.doc-group}` sections at level 2.

    if config.cli_desc:
        lines.append("::: {.doc-description}")
        lines.append(config.cli_desc.strip())
        lines.append(":::")
        lines.append("")

    entry_name = cli.get("entry_point_name") or cli["name"]
    top_commands = [c for c in cli.get("commands", []) if not c.get("hidden")]
    by_name = {c["name"]: c for c in top_commands}

    def emit_entry(cmd: CliCommand, href: str) -> None:
        """
        Append a command's link and short help to the page

        Parameters
        ----------
        cmd
            The command.
        href
            The command page's path, relative to the index.

        Returns
        -------
        :
        """
        label = "doc-label-cli-group" if cmd.get("is_group") else "doc-label-cli"
        # Show the full invocation (e.g. `great-docs init`), as on the command page titles
        name = cmd.get("full_path") or cmd["name"]
        short = (cmd.get("short_help") or "").strip()
        lines.append(f"[{name}]({href}){{.doc-function .doc-label .{label}}}")
        lines.append(f":   {short}" if short else ":   &nbsp;")
        lines.append("")

    def emit_section(section_title: str, section_desc: str | None = None) -> None:
        """
        Append a section heading and its optional description to the page

        Parameters
        ----------
        section_title
            The heading text.
        section_desc
            The paragraph under the heading.

        Returns
        -------
        :
        """
        lines.append(f"## {section_title} {{.doc-group}}")
        lines.append("")
        if section_desc:
            lines.append("::: {.doc-description}")
            lines.append(section_desc.strip())
            lines.append(":::")
            lines.append("")

    root_short = (cli.get("short_help") or "").strip()
    lines.append(
        f"[{entry_name}]({entry_safe}.qmd){{.doc-function .doc-label .doc-label-cli-group}}"
    )
    lines.append(f":   {root_short}" if root_short else ":   &nbsp;")
    lines.append("")

    cli_sections = config.cli_sections
    if cli_sections:
        for section in cli_sections:
            emit_section(section.get("title", ""), section.get("desc"))
            for cmd_name in section.get("contents", []):
                cmd = by_name.get(cmd_name)
                if not cmd:  # pragma: no cover
                    continue  # pragma: no cover
                emit_entry(cmd, f"{cmd_name.replace('-', '_')}.qmd")
    else:
        leaf = [c for c in top_commands if not c.get("is_group")]
        groups = [c for c in top_commands if c.get("is_group")]

        if leaf:
            emit_section(get_translation("cli_commands", lang))
            for cmd in leaf:
                emit_entry(cmd, f"{cmd['name'].replace('-', '_')}.qmd")

        for group in groups:
            gsafe = group["name"].replace("-", "_")
            emit_section(group["name"], (group.get("short_help") or "").strip() or None)
            # The group's own overview page, then each subcommand.
            emit_entry(group, f"{gsafe}.qmd")
            for sub in group.get("commands", []):
                if sub.get("hidden"):  # pragma: no cover
                    continue  # pragma: no cover
                ssafe = sub["name"].replace("-", "_")
                emit_entry(sub, f"{gsafe}/{ssafe}.qmd")

    return "\n".join(lines)


def command_page(config: Config, cmd: CliCommand, is_main: bool = False) -> str:
    """
    Render the reference page of a command

    The page has the layout of an API reference page: a labelled title, a short description, a
    usage block, the extended description, the full `--help` output in a collapsed block, then
    Arguments, Options, Commands and Examples sections for those the command has.

    Parameters
    ----------
    config
        The site configuration, for `lang`.
    cmd
        The command.
    is_main
        Whether the command is the root, whose title is its name rather than its invocation and
        whose subcommand pages sit beside its own.

    Returns
    -------
    :
        The Quarto Markdown for the page.
    """
    lines: list[str] = []

    title = cmd["full_path"] if not is_main else cmd["name"]
    label_class = "doc-label-cli-group" if cmd.get("is_group") else "doc-label-cli"

    lines.append("---")
    lines.append(f'title: "[{title}]{{.doc-object-name .doc-function .doc-label .{label_class}}}"')
    lines.append("body-classes: doc-api-page doc-cli-api-page")
    lines.append("sidebar: cli-reference")
    lines.append("page-navigation: false")
    lines.append("html-table-processing: none")
    # Front matter provides the page's only `h1`; render body sections at
    # their written levels.
    lines.append("shift-heading-level-by: 0")
    # Disabling breadcrumbs lets Quarto use the page title in the narrow-screen
    # navigation bar; CSS adds the prefix for the reference type.
    lines.append("bread-crumbs: false")
    lines.append("---")
    lines.append("")

    description = cmd.get("description", "") or cmd.get("help", "")
    option_names: set[str] = set()
    for opt in cmd.get("options", []):
        for n in opt.get("names", []):
            option_names.add(n)
    if description:
        # The first paragraph is the short subject
        paragraphs = description.split("\n\n")
        short_desc = paragraphs[0].replace("\n", " ").strip()
        short_desc = backtick_prose(short_desc, option_names)
        lines.append("::: {.doc-subject}")
        lines.append(short_desc)
        lines.append(":::")
        lines.append("")

    arguments = cmd.get("arguments", [])
    options = cmd.get("options", [])
    usage_parts = [title]
    if options:
        usage_parts.append("[OPTIONS]")
    for arg in arguments:
        arg_display = arg.get("name_display", arg.get("name", "")).upper()
        if not arg.get("required", True):
            arg_display = f"[{arg_display}]"
        if arg.get("nargs", 1) == -1:
            arg_display += "..."
        usage_parts.append(arg_display)
    if cmd.get("is_group") and cmd.get("commands"):
        usage_parts.append("COMMAND [ARGS]...")

    lines.append("::: {.doc-signature .doc-function}")
    lines.append("```bash")
    lines.append(" ".join(usage_parts))
    lines.append("```")
    lines.append(":::")
    lines.append("")

    if description:
        paragraphs = description.split("\n\n")
        extra = [p.strip() for p in paragraphs[1:] if p.strip()]
        if extra:
            lines.append("::: {.doc-text}")
            for para in extra:
                para_lines = para.split("\n")
                # Click help writes bullet lists with `•`, `-` or `*`
                if any(
                    line.strip().startswith(("•", "- ", "* "))
                    for line in para_lines
                    if line.strip()
                ):
                    for bline in para_lines:
                        stripped = bline.strip()
                        if not stripped:  # pragma: no cover
                            continue  # pragma: no cover
                        if stripped.startswith("•"):  # pragma: no cover
                            stripped = stripped[1:].strip()  # pragma: no cover
                        elif stripped.startswith(("- ", "* ")):  # pragma: no cover
                            stripped = stripped[2:].strip()  # pragma: no cover
                        if stripped:
                            stripped = backtick_prose(stripped, option_names)
                            lines.append(f"- {stripped}")
                # Keep the line breaks of blocks with indented content (e.g. "Quick start:")
                elif any(line.startswith("  ") for line in para_lines):
                    for bline in para_lines:
                        lines.append(backtick_prose(bline, option_names))
                else:
                    text = para.replace("\n", " ")
                    lines.append(backtick_prose(text, option_names))
                lines.append("")
            lines.append(":::")
            lines.append("")

    help_text = cmd.get("help_text", "")
    if help_text:
        help_summary = get_translation("cli_full_help", config.lang)
        lines.append(f'::: {{.details summary="{help_summary}"}}')
        lines.append("")
        lines.append("::: {.cli-manpage}")
        lines.append("")
        lines.append("```")
        lines.append(help_text.rstrip())
        lines.append("```")
        lines.append("")
        lines.append(":::")
        lines.append("")
        lines.append(":::")
        lines.append("")

    if arguments:
        lines.append("## Arguments {.doc-parameters}")
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for arg in arguments:
            display = arg.get("name_display", arg.get("name", "")).upper()
            type_str = arg.get("type")
            if type_str:
                lines.append(
                    f'<code><span class="doc-parameter-name">{display}</span>'
                    f'<span class="doc-parameter-annotation-sep">:</span>'
                    f' <span class="doc-parameter-annotation">{type_str}</span></code>'
                )
            else:
                lines.append(f'<code><span class="doc-parameter-name">{display}</span></code>')
            req = "Required." if arg.get("required", True) else "Optional."
            lines.append(f":   {req}")
            lines.append("")
        lines.append(":::")
        lines.append("")

    if options:
        lines.append("## Options {.doc-parameters}")
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for opt in options:
            if opt.get("hidden"):
                continue
            name_display = opt.get("name_display", "")
            type_str = opt.get("type")

            # Pandoc's smart extension turns `--` into an en dash even inside inline HTML.
            name_display_html = name_display.replace("--", "&#45;&#45;")

            code_parts = [f'<span class="doc-parameter-name">{name_display_html}</span>']
            if type_str and not opt.get("is_flag"):
                code_parts.append(
                    f'<span class="doc-parameter-annotation-sep">:</span>'
                    f' <span class="doc-parameter-annotation">{type_str}</span>'
                )
            default_val = opt.get("default")
            if default_val is not None and not opt.get("is_flag"):
                code_parts.append(
                    f' <span class="doc-parameter-default-sep op">=</span>'
                    f' <span class="doc-parameter-default">{default_val}</span>'
                )

            lines.append(f"<code>{''.join(code_parts)}</code>")

            help_str = opt.get("help", "")
            if opt.get("required"):
                help_str = f"**Required.** {help_str}" if help_str else "**Required.**"
            envvar = opt.get("envvar")
            if envvar:
                if isinstance(envvar, (list, tuple)):
                    envvar = ", ".join(envvar)
                help_str += f" Environment variable: `{envvar}`."
            help_str = backtick_prose(help_str.strip(), option_names)

            lines.append(f":   {help_str}" if help_str else ":   &nbsp;")
            lines.append("")

        lines.append(":::")
        lines.append("")

    commands = cmd.get("commands", [])
    if commands:
        lines.append("## Commands {.doc-parameters}")
        lines.append("")
        lines.append("::: {.doc-definition-items}")
        for subcmd in commands:
            subcmd_name = subcmd["name"]
            safe_name = subcmd_name.replace("-", "_")
            short_help = subcmd.get("short_help", "") or ""
            # The root's subcommand pages sit beside its own page; a group's sit in a directory
            # named after the group.
            if is_main:
                href = f"{safe_name}.qmd"
            else:
                parent_safe = cmd["name"].replace("-", "_")
                href = f"{parent_safe}/{safe_name}.qmd"
            lines.append(f"<code>[{subcmd_name}]{{.doc-parameter-name}}</code>")
            link_text = f"[{short_help}]({href})" if short_help else f"[{subcmd_name}]({href})"
            lines.append(f":   {link_text}")
            lines.append("")
        lines.append(":::")
        lines.append("")

    examples = cmd.get("examples", [])
    if examples:
        lines.append("## Examples {.doc-examples}")
        lines.append("")
        lines.append("```bash")
        for ex in examples:
            lines.append(ex)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def backtick_prose(text: str, option_names: set[str]) -> str:
    """
    Format option names and single-quoted tokens in help prose as code

    Parameters
    ----------
    text
        A passage of help text.
    option_names
        The command's option flags, such as `--watch`.

    Returns
    -------
    :
        The text with each option name and each single-quoted token of two or more characters,
        such as `'great-docs/'`, wrapped in backticks. Tokens already in backticks, and
        apostrophes in words such as "package's", are left alone.
    """
    if not text:
        return text

    # The opening quote must follow whitespace or start the text, and the content must be at
    # least two characters, so possessives such as "package's" do not match.
    text = re.sub(r"(?<=\s)'([^']{2,})'(?=[\s,.\)!?;:]|$)", r"`\1`", text)
    text = re.sub(r"^'([^']{2,})'(?=[\s,.\)!?;:]|$)", r"`\1`", text)

    if option_names:
        sorted_names = sorted(option_names, key=len, reverse=True)
        pattern = "|".join(re.escape(n) for n in sorted_names)
        text = re.sub(
            rf"(?<!`)({pattern})(?!`)",
            r"`\1`",
            text,
        )

    return text


def order_sidebar_items(
    items: list[SidebarItem], cli_sections: Sequence[dict[str, Any]]
) -> list[SidebarItem]:
    """
    Order top-level command entries as `cli.sections` lists them

    Parameters
    ----------
    items
        The sidebar entries of the top-level commands.
    cli_sections
        The `cli.sections` setting.

    Returns
    -------
    :
        The leaf command paths in the order the sections name them, then the paths the sections
        do not name, in code order, then the group sections, in their original order.
    """
    rank: dict[str, int] = {}
    for section in cli_sections:
        for cmd_name in section.get("contents", []):
            safe = cmd_name.replace("-", "_")
            _ = rank.setdefault(f"reference/cli/{safe}.qmd", len(rank))

    strings = [i for i in items if isinstance(i, str)]
    groups = [i for i in items if not isinstance(i, str)]

    base = len(rank)
    ordered = sorted(enumerate(strings), key=lambda iv: (rank.get(iv[1], base + iv[0]),))
    return [path for _, path in ordered] + groups


def count_pages(items: Sequence[SidebarItem]) -> int:
    """
    Count the pages in a reference sidebar

    Parameters
    ----------
    items
        Sidebar entries, which may nest sections.

    Returns
    -------
    :
        The number of page paths and labelled links, counted through every section.
    """
    count = 0
    for item in items:
        if isinstance(item, str):
            count += 1
        elif item.get("href"):
            count += 1
        else:
            count += count_pages(item.get("contents", []))
    return count
