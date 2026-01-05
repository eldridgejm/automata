from abc import ABC, abstractmethod
from functools import partial
from typing import Any

import jinja2
import markdown
import smartconfig

from ..materials import Publication
from ..util.resolution import resolve
from ._render import RenderContext


class Element(ABC):
    """Base class for all elements."""

    def __init__(self, jinja_env: jinja2.Environment, context: RenderContext):
        """Initialize the element with a Jinja environment and render context.

        Parameters
        ----------
        jinja_env : jinja2.Environment
            The Jinja2 environment to use for template rendering.
        context : RenderContext
            The rendering context.

        """
        self.jinja_env = jinja_env
        self.context = context

    @abstractmethod
    def __call__(
        self,
        config: smartconfig.types.Configuration,
    ) -> str: ...


class BasicElement(Element):
    """An Element that does basic configuration resolution and validation.

    Subclasses should provide the ``schema`` attribute and implement the ``render``
    method.

    """

    schema: smartconfig.types.Schema | None

    def __call__(
        self,
        config: smartconfig.types.Configuration,
    ) -> str:
        if self.schema is not None:
            config = resolve(config, self.schema)
        config = self.extra_resolution(config)
        return self.render(config)

    @abstractmethod
    def render(
        self,
        config: smartconfig.types.Configuration,
    ) -> str: ...

    def extra_resolution(
        self,
        config: smartconfig.types.Configuration,
    ) -> smartconfig.types.Configuration:
        """Perform any extra resolution/validation on the resolved configuration.

        Parameters
        ----------
        config : smartconfig.types.Configuration
            The resolved configuration for this element.

        Returns
        -------
        smartconfig.types.Configuration
            The further resolved/validated configuration.

        """
        return config


def _resolve(
    context: RenderContext, template_str: str, extra_vars: dict[str, Any] | None = None
) -> str:
    """Evaluate a Jinja2 template string with variables available."""
    if extra_vars is None:
        extra_vars = {}

    # Check if template_str is actually undefined
    if isinstance(template_str, jinja2.Undefined):
        raise ValueError(
            f"Cannot resolve undefined template string. "
            f"The template variable is undefined: {template_str._undefined_name}"
        )

    vars = context.to_dict()
    vars = {**vars, **extra_vars}

    try:
        template = jinja2.Template(
            template_str,
            undefined=jinja2.StrictUndefined,
            variable_start_string="${",
            variable_end_string="}",
            block_start_string="{%",
            block_end_string="%}",
        )
        return template.render(**vars)
    except jinja2.UndefinedError as exc:
        raise Exception(f"Error evaluating template: {exc}")


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


def _md_to_html(md_text: str) -> str:
    """Convert markdown text to HTML."""
    md_text = md_text.strip()
    html = markdown.markdown(md_text).strip()
    if html.startswith("<p>") and html.endswith("</p>"):
        html = html[3:-4]
    return html


class TemplateElement(BasicElement):
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
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        return {
            "resolve": partial(_resolve, self.context),
            "is_something_missing": _is_something_missing,
            **self.context.to_dict(),
        }

    def template_filters(
        self,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        return {
            "md_to_html": _md_to_html,
        }

    def render(
        self,
        config: smartconfig.types.Configuration,
    ) -> str:
        filters = self.template_filters(config)
        self.jinja_env.filters.update(**filters)

        template = self.jinja_env.get_template(self.template)
        extra_vars = self.template_vars(config)
        return template.render(
            element_config=config,
            context=self.context,
            **extra_vars,
        )
