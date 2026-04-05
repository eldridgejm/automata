import pytest

from automata._extension import Extension, apply_extension
from automata.hooks import GenerateHooks, WebsiteInputs


def _make_extension(**kwargs):
    defaults = dict(name="test", hooks={})
    defaults.update(kwargs)
    return Extension(**defaults)


class TestExtensionDataclass:

    def test_extension_has_name_and_hooks(self):
        ext = Extension(name="my-ext", hooks={"on_generate_post": lambda args: None})
        assert ext.name == "my-ext"
        assert "on_generate_post" in ext.hooks

    def test_extension_defaults(self):
        ext = Extension(name="test", hooks={})
        assert ext.config == {}
        assert ext.schema is None


class TestApplyExtension:

    def test_registers_hooks_on_hooks_instance(self):
        call_log = []

        def my_collect(inputs: WebsiteInputs) -> WebsiteInputs:
            call_log.append("collect")
            inputs.templates["test.html"] = "<html></html>"
            return inputs

        ext = _make_extension(hooks={"on_website_collect": my_collect})
        hooks = GenerateHooks()
        apply_extension(ext, hooks)

        result = hooks.on_website_collect(WebsiteInputs())
        assert "collect" in call_log
        assert "test.html" in result.templates

    def test_priority_controls_execution_order(self):
        call_log = []

        def hook_a(inputs: WebsiteInputs) -> WebsiteInputs:
            call_log.append("a")
            return inputs

        def hook_b(inputs: WebsiteInputs) -> WebsiteInputs:
            call_log.append("b")
            return inputs

        ext_a = _make_extension(name="a", hooks={"on_website_collect": hook_a})
        ext_b = _make_extension(name="b", hooks={"on_website_collect": hook_b})

        hooks = GenerateHooks()
        apply_extension(ext_a, hooks, priority=10)
        apply_extension(ext_b, hooks, priority=0)

        hooks.on_website_collect(WebsiteInputs())
        assert call_log == ["b", "a"]

    def test_raises_on_unknown_hook_name(self):
        ext = _make_extension(hooks={"on_nonexistent_hook": lambda x: x})
        hooks = GenerateHooks()

        with pytest.raises(AttributeError):
            apply_extension(ext, hooks)


class TestMultipleExtensionsCompose:

    def test_later_extension_overrides_templates(self):
        def base_collect(inputs: WebsiteInputs) -> WebsiteInputs:
            inputs.templates["page.html"] = "<base>"
            return inputs

        def override_collect(inputs: WebsiteInputs) -> WebsiteInputs:
            inputs.templates["page.html"] = "<override>"
            return inputs

        hooks = GenerateHooks()
        apply_extension(
            _make_extension(name="base", hooks={"on_website_collect": base_collect}),
            hooks,
            priority=0,
        )
        apply_extension(
            _make_extension(
                name="override", hooks={"on_website_collect": override_collect}
            ),
            hooks,
            priority=1,
        )

        result = hooks.on_website_collect(WebsiteInputs())
        assert result.templates["page.html"] == "<override>"

    def test_extensions_accumulate_different_keys(self):
        def theme_collect(inputs: WebsiteInputs) -> WebsiteInputs:
            inputs.templates["page.html"] = "<html>"
            inputs.static_files["style.css"] = "body {}"
            return inputs

        def plugin_collect(inputs: WebsiteInputs) -> WebsiteInputs:
            inputs.pages["extra.html"] = "# Extra"
            inputs.vars["plugin_name"] = "my-plugin"
            return inputs

        hooks = GenerateHooks()
        apply_extension(
            _make_extension(name="theme", hooks={"on_website_collect": theme_collect}),
            hooks,
        )
        apply_extension(
            _make_extension(
                name="plugin", hooks={"on_website_collect": plugin_collect}
            ),
            hooks,
        )

        result = hooks.on_website_collect(WebsiteInputs())
        assert "page.html" in result.templates
        assert "style.css" in result.static_files
        assert "extra.html" in result.pages
        assert result.vars["plugin_name"] == "my-plugin"
