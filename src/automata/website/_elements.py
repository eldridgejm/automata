from functools import wraps
from typing import Callable, TypeAlias

import smartconfig

from ._render import RenderContext

Element: TypeAlias = Callable[[smartconfig.types.Configuration, RenderContext], str]
"""A type alias for an element function.

An element is a function that takes a configuration and a render context
and returns a rendered string (usually HTML).
"""


def element(
    schema: smartconfig.types.Schema | type[smartconfig.Prototype],
):
    """Decorator for a basic element.

    This decorator checks and resolves the configuration against the provided
    schema before passing it to the decorated function.

    Parameters
    ----------
    schema : smartconfig.types.Schema | type[smartconfig.Prototype]
        The schema to validate the configuration against.

    Returns
    -------
    Callable
        A decorator that transforms a function into an ``Element``.

    """
    if isinstance(schema, smartconfig.Prototype):
        schema = schema._schema()

    def decorator(func):
        @wraps(func)
        def wrapper(config, context: RenderContext):
            resolved_config = smartconfig.resolve(config, schema)
            return func(resolved_config, context)

        return wrapper

    return decorator


def template_element(
    schema: smartconfig.types.Schema | type[smartconfig.Prototype],
    template_name: str,
):
    """Decorator for a template-based element.

    This decorator resolves the configuration against the provided schema, and
    then renders the specified Jinja2 template.

    The decorated function should accept the resolved configuration and a
    render context, and return a dictionary of extra variables to pass to the
    template.

    Parameters
    ----------
    schema : smartconfig.types.Schema | type[smartconfig.Prototype]
        The schema to validate the configuration against.
    template_name : str
        The name of the Jinja2 template to render.

    Returns
    -------
    Callable
        A decorator that transforms a function into an ``Element``.

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
