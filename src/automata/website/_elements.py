from abc import abstractmethod
from dataclasses import asdict
from functools import partial
from typing import Any, Protocol

import jinja2
import markdown
import smartconfig

from ..materials import Publication
from ..util.resolution import resolve
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
            config = resolve(config, self.schema)
        config = self.extra_resolution(config, context)
        return self.render(config, context)

    @abstractmethod
    def render(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str: ...

    def extra_resolution(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> smartconfig.types.Configuration:
        """Perform any extra resolution/validation on the resolved configuration.

        Parameters
        ----------
        config : smartconfig.types.Configuration
            The resolved configuration for this element.
        context : RenderContext
            The rendering context.

        Returns
        -------
        smartconfig.types.Configuration
            The further resolved/validated configuration.

        """
        return config


# Helper function to evaluate template strings
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

    vars = asdict(context)
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


def _md_to_html(md_text: str) -> str:
    """Convert markdown text to HTML."""
    md_text = md_text.strip()
    html = markdown.markdown(md_text).strip()
    if html.startswith("<p>") and html.endswith("</p>"):
        html = html[3:-4]
    return html


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
            "resolve": partial(_resolve, context),
            "is_something_missing": _is_something_missing,
            **asdict(context),
        }

    def template_filters(
        self,
        context: RenderContext,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        return {
            "md_to_html": _md_to_html,
        }

    def render(
        self,
        config: smartconfig.types.Configuration,
        context: RenderContext,
    ) -> str:
        jinja_env = context.theme.create_jinja_environment()

        filters = self.template_filters(context, config)
        jinja_env.filters.update(**filters)

        template = jinja_env.get_template(self.template)
        extra_vars = self.template_vars(context, config)
        return template.render(
            element_config=config,
            context=context,
            **extra_vars,
        )
