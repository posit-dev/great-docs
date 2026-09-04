"""Tests for great_docs._apiref._render.mixin_call."""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import griffe as gf


class TestMixinCallReceives:
    def test_render_receives_section(self):
        """render_receives_section delegates to render_definition_items."""
        import great_docs._apiref._render.mixin_call as mod

        cls = vars(mod)["__RenderDocCallMixin"]
        fake_self = types.SimpleNamespace(
            render_definition_items=lambda el: "rendered"
        )
        el = MagicMock(spec=gf.DocstringSectionReceives)
        result = cls.render_receives_section(fake_self, el)
        assert result == "rendered"


class TestMixinCallOverloadNoParams:
    def test_overload_without_parameters_skipped(self):
        """Overload entry without parameters attr is skipped."""
        import great_docs._apiref._render.mixin_call as mod

        cls = vars(mod)["__RenderDocCallMixin"]
        fake_obj = MagicMock()
        fake_obj.kind = "function"
        fake_self = types.SimpleNamespace(obj=fake_obj)

        ov_bad = MagicMock(spec=[])  # no 'parameters' attr

        result = cls._overload_signature_lines(fake_self, "func", [ov_bad])
        assert result == [("func()", [])]
