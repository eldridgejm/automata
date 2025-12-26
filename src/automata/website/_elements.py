from abc import abstractmethod
from dataclasses import asdict
from typing import Any, Protocol

import jinja2
import smartconfig

from ..materials import Publication
from ._render import RenderContext


class Element(Protocol):
    @abstractmethod
    def __call__(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str: ...


class BasicElement(Element, Protocol):
    """An Element that does basic configuration resolution and validation.

    Subclasses should provide the ``schema`` attribute and implement the ``render``
    method.

    """

    schema: smartconfig.types.Schema | None

    def __call__(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str:
        if self.schema is not None:
            config = smartconfig.resolve(config, self.schema)
        return self.render(config, context)

    @abstractmethod
    def render(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str: ...


# Helper function to evaluate template strings
def _resolve(template_str: str, vars: dict[str, Any] | None = None) -> str:
    """Evaluate a Jinja2 template string with variables available."""
    if vars is None:
        vars = {}

    try:
        template = jinja2.Template(
            template_str,
            undefined=jinja2.StrictUndefined,
        )
        return template.render(**vars)
    except jinja2.UndefinedError as exc:
        raise Exception(f"Error evaluating template: {exc}")


# Helper function to check if something is missing
def _is_something_missing(publication: Publication, requirements) -> bool:
    """Check if a publication is missing required artifacts or metadata."""
    if requirements is None:
        return False

    # Check for missing artifacts
    for artifact in requirements.get("artifacts", []):
        if artifact not in publication.artifacts:
            return True

    # Check for missing metadata
    for metadata_key in requirements.get("metadata", []):
        if metadata_key not in publication.metadata:
            return True

    # Check for null metadata
    for metadata_key in requirements.get("non_null_metadata", []):
        if (
            metadata_key not in publication.metadata
            or publication.metadata[metadata_key] is None
        ):
            return True

    return False


class TemplateElement(BasicElement, Protocol):
    """An Element that renders a Jinja2 template.

    Subclasses should provide both the ``schema`` attribute and the ``template``
    attribute. They may optionally override the ``template_vars`` method to provide
    additional variables to the template context.

    This inherits from BasicElement, so configuration resolution and validation
    is handled automatically.

    """

    template: str

    def template_vars(
        self,
        context: RenderContext,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        return {
            "resolve": _resolve,
            "is_something_missing": _is_something_missing,
            **asdict(context),
        }

    def render(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str:
        jinja_env = context.theme.create_jinja_environment()
        template = jinja_env.get_template(self.template)
        extra_vars = self.template_vars(context, config)
        return template.render(
            element_config=config,
            context=context,
            **extra_vars,
        )
