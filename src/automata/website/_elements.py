from abc import abstractmethod
from typing import Any, Protocol

import smartconfig

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
        return {}

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
