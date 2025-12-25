import smartconfig

from automata.materials import Universe
from automata.website import Config, RenderContext, Theme, ThemeConfig
from automata.website._elements import element, template_element


class ElementConfig(smartconfig.Prototype):
    key: str = "default"


def test_element_decorator_resolves_config():
    # given
    config_dict = {"key": "resolved_value"}
    materials = Universe(collections={})
    theme = Theme(templates={})

    # We need a valid Config object
    app_config = Config(
        content_directory="content", build_directory="build", theme=ThemeConfig()
    )

    context = RenderContext(
        config=app_config, materials=materials, url_for=lambda x: x, theme=theme
    )

    @element(ElementConfig)
    def my_element(conf, ctx):
        return f"Processed: {conf.key}"

    # when
    result = my_element(config_dict, context)

    # then
    assert result == "Processed: resolved_value"


def test_template_element_renders_template():
    # given
    template_name = "test.html"
    template_content = "Value: ${ element_config.key }, Extra: ${ extra_var }"

    materials = Universe(collections={})
    theme = Theme(templates={template_name: template_content})

    app_config = Config(
        content_directory="content", build_directory="build", theme=ThemeConfig()
    )

    context = RenderContext(
        config=app_config, materials=materials, url_for=lambda x: x, theme=theme
    )

    config_dict: smartconfig.types.ConfigurationDict = {"key": "config_value"}

    @template_element(ElementConfig, template_name)
    def my_template_element(conf, ctx):
        return {"extra_var": "extra_value"}

    # when
    result = my_template_element(config_dict, context)

    # then
    # The template should receive:
    # - element_config (resolved config)
    # - context
    # - extra_vars returned by the function
    assert "Value: config_value" in result
    assert "Extra: extra_value" in result
