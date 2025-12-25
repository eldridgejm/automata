from pytest import fixture, raises
from smartconfig.types import ConfigurationDict

from automata.materials import ExportedArtifact, Universe
from automata.website import BasicElement, RenderContext
from automata.website._config import Config
from automata.website._theme import Theme


@fixture
def render_context():
    """A minimal render context for testing."""
    config = Config(
        content_directory=".",
        build_directory=".",
    )
    materials = Universe[ExportedArtifact](collections={})
    theme = Theme(templates={})

    return RenderContext(
        config=config,
        materials=materials,
        url_for=lambda x: x,
        theme=theme,
    )


def test_basic_element_raises_if_config_does_not_fit_schema(render_context):
    class MyElement(BasicElement):
        schema = {"type": "dict", "required_keys": {"title": {"type": "string"}}}

        def render(self, config: ConfigurationDict, context) -> str:
            return f"Title: {config['title']}"

    element = MyElement()

    with raises(Exception):
        element({"wrong_key": "value"}, render_context)
