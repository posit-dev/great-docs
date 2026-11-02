"""
The homepage body for a project with no index page or README
"""

from __future__ import annotations

__all__ = ["markdown"]


def markdown(
    package_name: str | None,
    description: str,
    *,
    has_api_reference: bool,
    has_user_guide: bool,
) -> str:
    """
    Write a landing page from the package's name and description

    The page shows the description, a `pip install` command and links to the API reference
    and the user guide when the site has them.

    Parameters
    ----------
    package_name
        The package name, or `None` if it is unknown.
    description
        The package description, or `""` if it has none.
    has_api_reference
        Whether the site has an API reference.
    has_user_guide
        Whether the site has a user guide.

    Returns
    -------
    :
        The page body in Markdown, without front matter.
    """
    name = package_name or "Package"
    lines = [f"## {name}", ""]
    if description:
        lines += [description, ""]
    lines += ["### Installation", "", "```bash", f"pip install {name}", "```", ""]

    links: list[str] = []
    if has_api_reference:
        links.append("- [API Reference](reference/index.qmd) — Full API documentation")
    if has_user_guide:
        links.append("- [User Guide](user-guide/index.qmd) — Guides and tutorials")
    if links:
        lines += ["### Get Started", "", *links, ""]

    return "\n".join(lines) + "\n"
