"""
Translations and text direction for sites in languages other than English

Quarto renders the translation bundle from a metadata partial and sets text
direction through its `dir` option. Raw custom pages bypass Quarto, so their
translation bundle and text direction are added directly.
"""

from __future__ import annotations

import html
import json
import re
from typing import TYPE_CHECKING, Any, cast

from .._translations import (
    QUARTO_LANGUAGE_KEYS,
    QUARTO_UNTRANSLATED_LANGUAGES,
    get_translation,
    get_translations_bundle,
    is_rtl,
)
from . import head

if TYPE_CHECKING:
    from ..config import Config

_META_NAME = 'name="gd-i18n"'
_HTML_TAG = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
_DIR_ATTRIBUTE = re.compile(r"\sdir\s*=", re.IGNORECASE)


def register(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Default to right-to-left text for RTL languages

    Preserve an explicit `dir` setting in `site`. Leave the configuration
    unchanged if it has no HTML mapping.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    """
    html_config = quarto_config.get("format", {}).get("html")
    if isinstance(html_config, dict) and is_rtl(config.lang):
        cast("dict[str, Any]", html_config).setdefault("dir", "rtl")


def register_toc_title(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Set the table-of-contents title in the site's language

    A title configured in `site.toc-title` takes precedence. Otherwise, each
    update replaces the title with the translation for the current `lang`.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place. It must have a
        `format.html` mapping.
    config
        Project configuration.

    Returns
    -------
    :
    """
    if "toc-title" not in config.site_quarto:
        html_config = cast("dict[str, Any]", quarto_config["format"]["html"])
        html_config["toc-title"] = get_translation("on_this_page", config.lang)


def register_quarto_strings(quarto_config: dict[str, Any], config: Config) -> None:
    """
    Supply interface strings for languages Quarto does not translate

    For a language without a Quarto translation, Great Docs' strings fill
    missing entries under `language.<lang>`. Existing entries and other
    languages are preserved. A non-mapping `language` value is unchanged.

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.

    Returns
    -------
    :
    """
    lang = config.lang
    if lang not in QUARTO_UNTRANSLATED_LANGUAGES:
        return
    language = quarto_config.get("language")
    if language is None:
        language = quarto_config["language"] = {}
    if isinstance(language, dict):
        strings = cast("dict[str, Any]", language).setdefault(lang, {})
        for quarto_key, key in QUARTO_LANGUAGE_KEYS.items():
            strings.setdefault(quarto_key, get_translation(key, lang))


def meta_tag(config: Config) -> str | None:
    """
    Build a meta element containing the translation bundle

    The `content` attribute contains an HTML-escaped JSON object of translated
    interface strings for client-side scripts.

    Parameters
    ----------
    config
        Project configuration.

    Returns
    -------
    :
        The element, or `None` for English. Client-side scripts already
        contain the English strings.
    """
    if config.lang == "en":
        return None
    bundle = json.dumps(
        get_translations_bundle(config.lang), ensure_ascii=False, separators=(",", ":")
    )
    return f'<meta {_META_NAME} content="{html.escape(bundle, quote=True)}">'


def _direction(config: Config) -> str | None:
    """
    Resolve the site's configured or language-default text direction

    Parameters
    ----------
    config
        Project configuration.

    Returns
    -------
    :
        The non-empty `site.dir` setting, or `"rtl"` for RTL languages when no
        direction is configured. Return `None` for other languages without a
        configured direction.
    """
    site_direction = config.site.get("dir")
    if site_direction:
        return str(site_direction)
    return "rtl" if is_rtl(config.lang) else None


def add_to_raw_page(page: str, config: Config) -> str:
    """
    Add the translation bundle and text direction to a raw custom page

    Parameters
    ----------
    page
        The page source.
    config
        Project configuration.

    Returns
    -------
    :
        The page with translations in `<head>` for non-English languages and
        the configured or language-default direction on `<html>`. Preserve
        any existing translation bundle or `dir` attribute.
    """
    tag = meta_tag(config)
    if tag is not None:
        page = head.insert(page, tag, unless=_META_NAME)

    direction = _direction(config)
    if direction is None:
        return page

    def _set_direction(match: re.Match[str]) -> str:
        element = match[0]
        if _DIR_ATTRIBUTE.search(element):
            return element
        return f'{element[:-1]} dir="{html.escape(direction, quote=True)}">'

    return _HTML_TAG.sub(_set_direction, page, count=1)
