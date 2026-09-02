from great_docs._apiref._globals import SIGNATURE_STYLE, SignatureStyle
from great_docs._apiref.api_reference import Settings, apply_signature_settings


def test_settings_default_to_todays_rendering():
    """The defaults reproduce what sites already publish"""
    settings = Settings()

    assert settings.call_signature_highlight_style == "pygments"
    assert settings.call_signature_wrap_style == "per_parameter"


def test_settings_read_the_api_reference_block():
    """Both keys come from the generated api-reference block"""
    settings = Settings.make(
        {
            "package": "pkg",
            "call_signature_highlight_style": "spans",
            "call_signature_wrap_style": "width",
        }
    )

    assert settings.call_signature_highlight_style == "spans"
    assert settings.call_signature_wrap_style == "width"


def test_applying_settings_reaches_the_render_side():
    """The renderer reads the style from module state, not from Settings"""
    original = SignatureStyle(SIGNATURE_STYLE.highlight, SIGNATURE_STYLE.wrap)
    try:
        apply_signature_settings(
            Settings(
                call_signature_highlight_style="spans",
                call_signature_wrap_style="width",
            )
        )
        assert SIGNATURE_STYLE.highlight == "spans"
        assert SIGNATURE_STYLE.wrap == "width"
    finally:
        SIGNATURE_STYLE.highlight = original.highlight
        SIGNATURE_STYLE.wrap = original.wrap
