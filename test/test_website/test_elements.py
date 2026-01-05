from pytest import fixture, raises
from smartconfig.types import ConfigurationDict

from automata.materials import ExportedArtifact, Universe
from automata.website import BasicElement, RenderContext
from automata.website._config import WebsiteConfig
from automata.website._theme import Theme


@fixture
def render_context():
    """A minimal render context for testing."""
    config = WebsiteConfig(
        content_directory=".",
        build_directory=".",
    )
    materials = Universe[ExportedArtifact](collections={})

    return RenderContext(
        website_config=config,
        materials=materials,
        url_for=lambda x: x,
    )


@fixture
def jinja_env():
    """A minimal Jinja environment for testing."""
    theme = Theme(templates={})
    return theme.create_jinja_environment()


def test_basic_element_raises_if_config_does_not_fit_schema(render_context, jinja_env):
    class MyElement(BasicElement):
        schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

        def render(self, config: ConfigurationDict) -> str:
            return f"Title: {config['title']}"

    element = MyElement(jinja_env, render_context)

    with raises(Exception):
        element({"wrong_key": "value"})
