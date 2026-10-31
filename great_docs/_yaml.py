"""
Typed access to parsed YAML and page front matter

Read parsed YAML values using the types callers expect. Treat values of
other types as absent. Preserve yaml12's nested value types so callers can
narrow them with `isinstance`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from yaml12 import Yaml, parse_yaml

YamlScalar: TypeAlias = None | bool | int | float | str | Yaml
"""A parsed YAML scalar or tagged node"""

YamlValue: TypeAlias = "YamlScalar | list[YamlValue] | dict[YamlScalar, YamlValue]"
"""A parsed YAML value from front matter or `_metadata.yml`"""


@dataclass(frozen=True)
class YamlMapping:
    """A parsed YAML mapping with accessors for expected value types"""

    data: Mapping[Any, YamlValue] = field(default_factory=dict[Any, YamlValue])
    """The parsed mapping, which may also contain non-string keys"""

    def get(self, key: str, default: YamlValue = None) -> YamlValue:
        """
        Read a value of any type

        Parameters
        ----------
        key
            The key to read.
        default
            The value when the key is absent.

        Returns
        -------
        :
            The value, including `None`, or `default` when the key is absent.
        """
        return self.data.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def __len__(self) -> int:
        return len(self.data)

    def string(self, key: str) -> str | None:
        """
        Read a string

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The value, or `None` when it is absent or not a string.
        """
        value = self.data.get(key)
        return value if isinstance(value, str) else None

    def number(self, key: str) -> int | float | None:
        """
        Read a number

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The numeric value, or `None` when it is absent, a boolean, or
            another non-numeric value.
        """
        value = self.data.get(key)
        if isinstance(value, bool):
            return None
        return value if isinstance(value, int | float) else None

    def strings(self, key: str) -> list[str]:
        """
        Read a string or a list of strings

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The list of strings, or a single string wrapped in a list. Return
            an empty list for an absent value, another value type, or a list
            containing any non-string item.
        """
        value = self.data.get(key)
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, str)]
            return items if len(items) == len(value) else []
        return []

    def sequence(self, key: str) -> list[YamlValue]:
        """
        Read a list

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The list, or an empty list when the value is absent or not a list.
        """
        value = self.data.get(key)
        return value if isinstance(value, list) else []

    def entries(self, key: str) -> list[YamlValue]:
        """
        Read a value that Quarto accepts either alone or as a list

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The list with `None` items removed, or a single value wrapped in a
            list. Return an empty list when the value is absent or `None`.
        """
        value = self.data.get(key)
        items = value if isinstance(value, list) else [value]
        return [item for item in items if item is not None]

    def mapping(self, key: str) -> YamlMapping:
        """
        Read a nested mapping

        Parameters
        ----------
        key
            The key to read.

        Returns
        -------
        :
            The nested mapping, or an empty mapping when the value is absent
            or not a mapping. Subsequent reads can use the same accessors.
        """
        value = self.data.get(key)
        return YamlMapping(value) if isinstance(value, dict) else YamlMapping()


FRONT_MATTER_OPENING = re.compile(r"---[ \t]*\n")
"""The first line of a page that opens front matter"""


@dataclass(frozen=True)
class FrontMatterBlock:
    """The front matter that opens a page"""

    mapping: YamlMapping
    """The parsed front matter, empty when it is not a valid YAML mapping"""

    end: int
    """The offset just past the closing `---` line, where the body starts"""


def locate_front_matter(content: str) -> FrontMatterBlock | None:
    """
    Find and parse the front matter that opens a page

    Front matter must start with `---` on the first line, optionally followed
    by spaces or tabs, and ends at the next line beginning with `---`. A page
    with leading blank lines has no front matter, as in Quarto.

    Parameters
    ----------
    content
        The page source.

    Returns
    -------
    :
        The front matter, or `None` when the page does not open with a closed
        block.
    """
    opening = FRONT_MATTER_OPENING.match(content)
    if opening is None:
        return None
    closing = content.find("\n---", opening.end() - 1)
    if closing == -1:
        return None
    try:
        parsed = parse_yaml(content[opening.end() : closing + 1])
    except ValueError:
        parsed = None
    mapping = YamlMapping(parsed) if isinstance(parsed, dict) else YamlMapping()
    line_end = content.find("\n", closing + 4)
    return FrontMatterBlock(mapping, len(content) if line_end == -1 else line_end + 1)


def split_front_matter(content: str) -> tuple[YamlMapping, str]:
    """
    Separate a page's front matter from its body

    Parameters
    ----------
    content
        The page source.

    Returns
    -------
    :
        The front matter, empty when the page has none or it is not a valid
        YAML mapping, and the body. The body is all of `content` when the page
        does not open with a closed block.
    """
    block = locate_front_matter(content)
    if block is None:
        return YamlMapping(), content
    return block.mapping, content[block.end :]


def set_front_matter_option(content: str, key: str, value: bool | int | str) -> str:
    """
    Set a top-level option in a page's front matter

    The page's other lines keep their text, so comments and formatting survive.

    Parameters
    ----------
    content
        The page source.
    key
        The option to set.
    value
        The value. A string is written in double quotes.

    Returns
    -------
    :
        The page with `key` set to `value`. An existing `key` line is replaced, a new one is
        appended to the block, and a page without front matter gains a block.
    """
    if isinstance(value, bool):
        yaml_value = "true" if value else "false"
    elif isinstance(value, str):
        yaml_value = f'"{value}"'
    else:
        yaml_value = str(value)

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            rest = parts[2]

            key_pattern = rf"^{re.escape(key)}:\s*.*$"
            if re.search(key_pattern, frontmatter, re.MULTILINE):
                frontmatter = re.sub(
                    key_pattern, f"{key}: {yaml_value}", frontmatter, flags=re.MULTILINE
                )
            else:
                frontmatter = frontmatter.rstrip() + f"\n{key}: {yaml_value}\n"

            return f"---{frontmatter}---{rest}"

    return f"---\n{key}: {yaml_value}\n---\n\n{content}"
