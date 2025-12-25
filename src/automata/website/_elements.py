from functools import wraps
from typing import Callable, TypeAlias

import smartconfig

from ._render import RenderContext

Element: TypeAlias = Callable[[smartconfig.types.Configuration, RenderContext], str]


def element(
    schema: smartconfig.types.Schema | type[smartconfig.Prototype],
):
    """Decorator for a basic element.

    This decorator simply checks and resolves the configuration against the provided
    schema.

    """
    if isinstance(schema, smartconfig.Prototype):
        schema = schema._schema()

    def decorator(func):
        @wraps(func)
        def wrapper(config: smartconfig.types.Configuration, context: RenderContext):
            resolved_config = smartconfig.resolve(config, schema)
            return func(resolved_config, context)

        return wrapper

    return decorator


def template_element(
    schema: smartconfig.types.Schema | type[smartconfig.Prototype],
    template_name: str,
):
    """Decorator for a template-based element.

    This decorator resolves the configuration against the provided schema, and then
    renders the specified Jinja2 template. The decorated function should return a
    dictionary of extra variables to pass to the template.

    """
    if isinstance(schema, smartconfig.Prototype):
        schema = schema._schema()

    def decorator(func):
        @element(schema)
        def wrapper(
            config: smartconfig.types.Configuration, context: RenderContext
        ) -> str:
            extra_vars = func(config, context)
            jinja_environment = context.theme.create_jinja_environment()
            template = jinja_environment.get_template(template_name)
            return template.render(
                element_config=config,
                context=context,
                **extra_vars,
            )

        return wrapper

    return decorator
