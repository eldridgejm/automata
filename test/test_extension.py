import types

import pytest

from automata.exceptions import Error
from automata.extensions import (
    EXTENSIONS_GROUP,
    THEMES_GROUP,
    Extension,
    apply_extension,
    apply_extensions,
    extension_from_entry_point,
)
from automata.hooks import RenderHooks, WebsiteInputs


def _make_extension(**kwargs):
    defaults = dict(name="test", hooks={})
    defaults.update(kwargs)
    return Extension(**defaults)


class _FakeEntryPoint:
    """An installed entry point, as far as extension_from_entry_point cares."""

    def __init__(self, group, name, **module_attrs):
        self.group = group
        self.name = name
        self._module = types.SimpleNamespace(**module_attrs)

    def load(self):
        return self._module


def _factory(name, schema=None):
    """Return a make_extension factory that records the config it was given."""

    def make_extension(config):
        return Extension(name=name, hooks={}, config=config, schema=schema)

    return make_extension


_TITLE_SCHEMA = {
    "type": "dict",
    "required_keys": {"title": {"type": "string"}},
    "optional_keys": {"subtitle": {"type": "string", "default": "none"}},
}


# Extension dataclass ==================================================================


def test_extension_has_name_and_hooks():
    ext = Extension(name="my-ext", hooks={"on_render_post": lambda args: None})
    assert ext.name == "my-ext"
    assert "on_render_post" in ext.hooks


def test_extension_defaults():
    ext = Extension(name="test", hooks={})
    assert ext.config == {}
    assert ext.schema is None


# apply_extension() ====================================================================


def test_apply_extension_registers_hooks_on_hooks_instance():
    call_log = []

    def my_collect(inputs: WebsiteInputs) -> WebsiteInputs:
        call_log.append("collect")
        inputs.templates["test.html"] = "<html></html>"
        return inputs

    ext = _make_extension(hooks={"on_render_collect": my_collect})
    hooks = RenderHooks()
    apply_extension(ext, hooks)

    result = hooks.on_render_collect(WebsiteInputs())
    assert "collect" in call_log
    assert "test.html" in result.templates


def test_apply_extension_priority_controls_execution_order():
    call_log = []

    def hook_a(inputs: WebsiteInputs) -> WebsiteInputs:
        call_log.append("a")
        return inputs

    def hook_b(inputs: WebsiteInputs) -> WebsiteInputs:
        call_log.append("b")
        return inputs

    ext_a = _make_extension(name="a", hooks={"on_render_collect": hook_a})
    ext_b = _make_extension(name="b", hooks={"on_render_collect": hook_b})

    hooks = RenderHooks()
    apply_extension(ext_a, hooks, priority=10)
    apply_extension(ext_b, hooks, priority=0)

    hooks.on_render_collect(WebsiteInputs())
    assert call_log == ["b", "a"]


def test_apply_extension_raises_on_unknown_hook_name():
    ext = _make_extension(hooks={"on_nonexistent_hook": lambda x: x})
    hooks = RenderHooks()

    with pytest.raises(AttributeError):
        apply_extension(ext, hooks)


# composing multiple extensions ========================================================


def test_later_extension_overrides_templates():
    def base_collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<base>"
        return inputs

    def override_collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<override>"
        return inputs

    hooks = RenderHooks()
    apply_extension(
        _make_extension(name="base", hooks={"on_render_collect": base_collect}),
        hooks,
        priority=0,
    )
    apply_extension(
        _make_extension(name="override", hooks={"on_render_collect": override_collect}),
        hooks,
        priority=1,
    )

    result = hooks.on_render_collect(WebsiteInputs())
    assert result.templates["page.html"] == "<override>"


def test_extensions_accumulate_different_keys():
    def theme_collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html>"
        inputs.static_files["style.css"] = "body {}"
        return inputs

    def plugin_collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.pages["extra.html"] = "# Extra"
        return inputs

    hooks = RenderHooks()
    apply_extension(
        _make_extension(name="theme", hooks={"on_render_collect": theme_collect}),
        hooks,
    )
    apply_extension(
        _make_extension(name="plugin", hooks={"on_render_collect": plugin_collect}),
        hooks,
    )

    result = hooks.on_render_collect(WebsiteInputs())
    assert "page.html" in result.templates
    assert "style.css" in result.static_files
    assert "extra.html" in result.pages


# apply_extensions() ===================================================================


def test_apply_extensions_registers_shared_dependency_once():
    calls = []

    def dep_collect(inputs):
        calls.append("dep")
        return inputs

    dep = _make_extension(name="dep", hooks={"on_render_collect": dep_collect})
    a = _make_extension(name="a", dependencies=[dep])
    b = _make_extension(name="b", dependencies=[dep])

    hooks = RenderHooks()
    apply_extensions([a, b], hooks)
    hooks.on_render_collect(WebsiteInputs())

    assert calls == ["dep"]


# extension_from_entry_point() =========================================================


def test_extension_from_entry_point_raises_helpful_error_on_unknown_name():
    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("schedule")

    assert 'Unknown extension "schedule"' in str(excinfo.value)


def test_extension_from_entry_point_raises_helpful_error_on_unknown_theme():
    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("dark", group=THEMES_GROUP)

    message = str(excinfo.value)
    assert 'Unknown theme "dark"' in message
    assert "default" in message


def test_extension_from_entry_point_hints_when_theme_is_used_as_extension():
    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("default", group=EXTENSIONS_GROUP)

    assert "website.theme" in str(excinfo.value)


def test_extension_from_entry_point_hints_when_extension_is_used_as_theme():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP, "my-ext", extension=_make_extension(name="my-ext")
        )
    ]

    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("my-ext", group=THEMES_GROUP, entry_points=eps)

    assert "extensions" in str(excinfo.value)


def test_extension_from_entry_point_calls_factory_with_validated_config():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP,
            "my-ext",
            schema=_TITLE_SCHEMA,
            make_extension=_factory("my-ext"),
        )
    ]

    ext = extension_from_entry_point(
        "my-ext", config={"title": "Hello"}, entry_points=eps
    )

    assert ext.config == {"title": "Hello", "subtitle": "none"}


def test_extension_from_entry_point_factory_builds_independent_extensions():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP,
            "my-ext",
            schema=_TITLE_SCHEMA,
            make_extension=_factory("my-ext"),
        )
    ]

    first = extension_from_entry_point(
        "my-ext", config={"title": "First"}, entry_points=eps
    )
    second = extension_from_entry_point(
        "my-ext", config={"title": "Second"}, entry_points=eps
    )

    assert first is not second
    assert first.config["title"] == "First"
    assert second.config["title"] == "Second"


def test_extension_from_entry_point_applies_defaults_when_config_omitted():
    schema = {
        "type": "dict",
        "optional_keys": {"subtitle": {"type": "string", "default": "none"}},
    }
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP, "my-ext", schema=schema, make_extension=_factory("my-ext")
        )
    ]

    ext = extension_from_entry_point("my-ext", entry_points=eps)

    assert ext.config == {"subtitle": "none"}


def test_extension_from_entry_point_raises_on_missing_required_config():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP,
            "my-ext",
            schema=_TITLE_SCHEMA,
            make_extension=_factory("my-ext"),
        )
    ]

    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("my-ext", entry_points=eps)

    message = str(excinfo.value)
    assert "my-ext" in message
    assert "title" in message


def test_extension_from_entry_point_raises_on_invalid_config():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP,
            "my-ext",
            schema=_TITLE_SCHEMA,
            make_extension=_factory("my-ext"),
        )
    ]

    with pytest.raises(Error):
        extension_from_entry_point(
            "my-ext", config={"title": "Hi", "bogus": 1}, entry_points=eps
        )


def test_extension_from_entry_point_uses_plain_extension_attribute():
    plain = _make_extension(name="my-ext")
    eps = [_FakeEntryPoint(EXTENSIONS_GROUP, "my-ext", extension=plain)]

    ext = extension_from_entry_point("my-ext", entry_points=eps)

    assert ext.name == "my-ext"
    assert ext.config == {}


def test_extension_from_entry_point_raises_if_plain_extension_given_config():
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP, "my-ext", extension=_make_extension(name="my-ext")
        )
    ]

    with pytest.raises(Error) as excinfo:
        extension_from_entry_point(
            "my-ext", config={"title": "Hello"}, entry_points=eps
        )

    assert "my-ext" in str(excinfo.value)


def test_extension_from_entry_point_raises_if_module_exports_no_extension():
    eps = [_FakeEntryPoint(EXTENSIONS_GROUP, "my-ext")]

    with pytest.raises(Error) as excinfo:
        extension_from_entry_point("my-ext", entry_points=eps)

    message = str(excinfo.value)
    assert "make_extension" in message
    assert "extension" in message


# public API ===========================================================================


def test_extensions_package_exports_the_public_api():
    import automata.extensions

    assert set(automata.extensions.__all__) == {
        "EXTENSIONS_GROUP",
        "THEMES_GROUP",
        "Extension",
        "apply_extension",
        "apply_extensions",
        "extension_from_directory",
        "extension_from_entry_point",
    }
    for name in automata.extensions.__all__:
        assert getattr(automata.extensions, name) is not None


def test_website_does_not_reexport_extension_loaders():
    import automata.website

    assert not hasattr(automata.website, "extension_from_directory")
    assert not hasattr(automata.website, "extension_from_entry_point")


def test_docs_do_not_import_the_private_extension_module():
    from pathlib import Path

    docs = Path(__file__).parent.parent / "doc" / "source"
    offenders = [
        f"{path.relative_to(docs)}:{lineno}"
        for path in docs.rglob("*.rst")
        for lineno, line in enumerate(path.read_text().splitlines(), start=1)
        if "automata._extension" in line
    ]

    assert offenders == []


def test_extension_config_accepts_date_phrases():
    import datetime

    schema = {"type": "dict", "required_keys": {"start": {"type": "date"}}}
    eps = [
        _FakeEntryPoint(
            EXTENSIONS_GROUP, "my-ext", schema=schema, make_extension=_factory("my-ext")
        )
    ]

    ext = extension_from_entry_point(
        "my-ext", config={"start": "7 days after 2026-01-01"}, entry_points=eps
    )

    assert ext.config["start"] == datetime.date(2026, 1, 8)
