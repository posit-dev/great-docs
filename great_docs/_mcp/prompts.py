"""Documentation prompt templates and argument expansion"""

from __future__ import annotations

from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)


async def list_prompts() -> list[Prompt]:
    """List pre-built prompt templates for documentation workflows."""
    return [
        Prompt(
            name="setup-docs",
            description=(
                "Guide the user through setting up Great Docs for a new Python project. "
                "Scans the package, generates config, and runs an initial build."
            ),
            arguments=[
                PromptArgument(
                    name="project_path",
                    description="Path to the Python project root directory.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="write-user-guide",
            description=(
                "Help write a user guide page for a specific topic. Generates well-structured "
                "Quarto markdown with examples, cross-references, and proper frontmatter."
            ),
            arguments=[
                PromptArgument(
                    name="topic",
                    description="The topic or feature to document.",
                    required=True,
                ),
                PromptArgument(
                    name="audience",
                    description="Target audience level (beginner, intermediate, advanced).",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="debug-build",
            description=(
                "Diagnose and fix a Great Docs build failure. Reads the build log, "
                "identifies the error, and suggests fixes."
            ),
            arguments=[
                PromptArgument(
                    name="error_message",
                    description="The error message or symptom observed.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="improve-docstrings",
            description=(
                "Review and improve docstrings for a module or class. Ensures "
                "consistent style, complete parameter documentation, and useful examples."
            ),
            arguments=[
                PromptArgument(
                    name="symbol",
                    description="The module, class, or function name to improve.",
                    required=True,
                ),
                PromptArgument(
                    name="style",
                    description="Docstring style: numpy, google, or sphinx.",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="api-changelog",
            description=(
                "Generate a changelog entry from API differences between two versions. "
                "Produces markdown suitable for a CHANGELOG or release notes."
            ),
            arguments=[
                PromptArgument(
                    name="base_version",
                    description="The base version to compare from (e.g., v0.9.0).",
                    required=False,
                ),
                PromptArgument(
                    name="head_version",
                    description="The target version to compare to (e.g., v0.10.0 or HEAD).",
                    required=False,
                ),
            ],
        ),
    ]


async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Return the expanded prompt messages for a given prompt template."""
    args = arguments or {}

    if name == "setup-docs":
        project = args.get("project_path", "the current directory")
        return GetPromptResult(
            description="Set up Great Docs for a Python project",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"I want to set up documentation for my Python project at {project}. "
                            "Please:\n"
                            "1. Use `gd_scan` to discover the package's public API\n"
                            "2. Use `gd_config` with generate=true to create a starter config\n"
                            "3. Use `gd_build` to run the initial build\n"
                            "4. Report what was documented and suggest next steps "
                            "(user guide pages, CLI docs, custom sections)"
                        ),
                    ),
                ),
            ],
        )

    elif name == "write-user-guide":
        topic = args.get("topic", "the feature")
        audience = args.get("audience", "intermediate")
        return GetPromptResult(
            description=f"Write a user guide page about: {topic}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Write a user guide page about '{topic}' for a {audience} audience.\n\n"
                            "Requirements:\n"
                            "- Use Quarto markdown (.qmd format)\n"
                            "- Start with a clear introduction explaining why this matters\n"
                            "- Include practical code examples with expected output\n"
                            "- Use cross-references to related API functions where relevant\n"
                            "- Add callout blocks (:::{.callout-tip}) for best practices\n"
                            "- End with a 'Next Steps' section linking to related pages\n\n"
                            "Use `gd_add_page` to create the page when done, "
                            "with section='user_guide'."
                        ),
                    ),
                ),
            ],
        )

    elif name == "debug-build":
        error = args.get("error_message", "")
        context = f" The error was: {error}" if error else ""
        return GetPromptResult(
            description="Debug a Great Docs build failure",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"My Great Docs build is failing.{context}\n\n"
                            "Please help me diagnose and fix it:\n"
                            "1. Read the `gd://build-log` resource for recent build output\n"
                            "2. Use `gd_status` to check project state\n"
                            "3. Use `gd_lint` to find configuration issues\n"
                            "4. Identify the root cause and provide a fix\n"
                            "5. Re-run `gd_build` to verify the fix works"
                        ),
                    ),
                ),
            ],
        )

    elif name == "improve-docstrings":
        symbol = args.get("symbol", "")
        style = args.get("style", "numpy")
        return GetPromptResult(
            description=f"Improve docstrings for: {symbol}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Review and improve the docstrings for `{symbol}` "
                            f"using {style} style.\n\n"
                            "Check for:\n"
                            "- Missing parameter descriptions\n"
                            "- Missing return type documentation\n"
                            "- Missing or outdated examples\n"
                            "- Inconsistent style with the rest of the project\n"
                            "- Opportunities to add cross-references (e.g., 'See Also')\n\n"
                            "Use `gd_scan` to see the full API surface, then "
                            "use `gd_lint` with checks=['docstrings'] to validate your changes."
                        ),
                    ),
                ),
            ],
        )

    elif name == "api-changelog":
        base = args.get("base_version", "the previous release")
        head = args.get("head_version", "HEAD")
        return GetPromptResult(
            description=f"Generate changelog: {base} → {head}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Generate a changelog entry for changes between {base} and {head}.\n\n"
                            "Steps:\n"
                            f"1. Use `gd_api_diff` with base='{base}' to get API changes\n"
                            "2. Categorize changes into: Added, Changed, Deprecated, Removed, Fixed\n"
                            "3. Write a markdown changelog entry with:\n"
                            "   - A summary paragraph describing the release theme\n"
                            "   - Categorized bullet points for each change\n"
                            "   - Migration notes for any breaking changes\n"
                            "   - Links to relevant documentation pages"
                        ),
                    ),
                ),
            ],
        )

    else:
        return GetPromptResult(
            description="Unknown prompt",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=f"Unknown prompt: {name}"),
                ),
            ],
        )
