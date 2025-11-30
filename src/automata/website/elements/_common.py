"""Common utilities for element rendering."""

import importlib.resources
from types import ModuleType
from typing import Any, Callable, Mapping

import jinja2
import markdown  # type: ignore
import smartconfig
import smartconfig.types

from ... import materials
from .. import exceptions
from .._types import RenderContext


def _get_template_from_module(templates: ModuleType, template_name: str) -> str:
    """Get a template string from a module using importlib.resources."""
    return importlib.resources.read_text(templates, template_name)


def render_element_template(
    template_name: str,
    context: RenderContext,
    extra_vars: Mapping[str, Any],
) -> str:
    """Render an element template with shared filters and variables.

    Uses a filesystem loader rooted at ``context.theme_path / "elements"`` and
    installs the standard element filters:

    - ``evaluate``: render an inline template string using ``$(...)`` delimiters,
      raising ``ElementError`` on undefined variables.
    - ``markdown_to_html``: convert markdown to HTML.
    - ``get_dotted_attr``: navigate dotted attribute/index paths on objects/mappings.

    ``extra_vars`` are merged into the template context alongside the provided
    ``context``.

    Parameters
    ----------
    template_name : str
        Name of the element template file (under ``theme_path / "elements"``). E.g.,
        ``announcement_box.html``.
    context : RenderContext
        RenderContext providing theme path and page-level variables.
    extra_vars : Mapping[str, Any]
        Additional variables to inject into the template render.

    Returns
    -------
    str
        Rendered HTML string.
    """
    template_overrides: dict[str, str] = {}
    if context.theme.template_overrides is not None:
        template_overrides = dict(context.theme.template_overrides)

    load_from_module = jinja2.FunctionLoader(
        lambda name: _get_template_from_module(context.theme.templates, name)
    )

    load_from_overrides = jinja2.DictLoader(template_overrides)

    loader = jinja2.ChoiceLoader([load_from_overrides, load_from_module])

    element_environment = jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )

    def evaluate(s, **kwargs):
        if "context" not in kwargs:
            kwargs["context"] = context

        try:
            return jinja2.Template(
                s,
                undefined=jinja2.StrictUndefined,
                variable_start_string="$(",
                variable_end_string=")",
                block_start_string="(%",
                block_end_string="%)",
            ).render(**kwargs)
        except jinja2.UndefinedError as exc:
            raise exceptions.ElementError(
                f'Unknown variable in template string "{s}": {exc}'
            )

    def get_dotted_attr(obj, path):
        parts = list(reversed(path.split(".")))

        while parts:
            part = parts.pop()
            try:
                obj = obj[part]
            except TypeError:
                obj = getattr(obj, part)

        return obj

    def markdown_to_html(s):
        return markdown.markdown(s)

    element_environment.filters["evaluate"] = evaluate
    element_environment.filters["markdown_to_html"] = markdown_to_html
    element_environment.filters["get_dotted_attr"] = get_dotted_attr

    template = element_environment.get_template(template_name)
    return template.render(context=context, **extra_vars)


def basic_element(
    template_filename: str,
    config_schema: smartconfig.types.Schema,
    extra_render_vars: Callable[[RenderContext, Mapping[str, Any]], Mapping[str, Any]]
    | None = None,
) -> Callable[[RenderContext, smartconfig.types.ConfigurationDict], str]:
    """Create an element renderer with config validation and optional extras.

    Returns a callable that:
    1. Validates ``element_config`` with ``smartconfig`` against ``config_schema``.
    2. Computes any additional render vars via ``extra_render_vars``.
    3. Renders ``template_filename`` with the validated config and extras.

    Parameters
    ----------
    template_filename : str
        Element template filename relative to the elements directory.
    config_schema : smartconfig.types.Schema
        Smartconfig schema used to validate the element config.
    extra_render_vars : Callable | None
        Optional callable ``(RenderContext, Mapping[str, Any]) -> Mapping[str, Any]``
        to compute extra render variables from context/config.

    Returns
    -------
    Callable[[RenderContext, smartconfig.types.ConfigurationDict], str]
        A function that accepts a render context and element config, returning
        rendered HTML as a string.
    """

    def element(
        context: RenderContext, element_config: smartconfig.types.ConfigurationDict
    ) -> str:
        element_config = smartconfig.resolve(element_config, config_schema)
        assert isinstance(element_config, dict)

        if extra_render_vars is not None:
            extra_vars = extra_render_vars(context, element_config)
        else:
            extra_vars = {}

        return render_element_template(
            template_filename, context, {"element_config": element_config, **extra_vars}
        )

    return element


def is_something_missing(
    publication: materials.Publication, requirements: Mapping[str, list[str]]
) -> bool:
    """Return True when a publication lacks required artifacts/metadata.

    Parameters
    ----------
    publication : materials.Publication
        Publication object whose metadata/artifacts are checked.
    requirements : Mapping[str, list[str]]
        Dict containing lists for ``artifacts``, ``metadata``, and
        ``non_null_metadata`` keys.

    Returns
    -------
    bool
        True if any required artifact/metadata is missing or null.

    Examples
    --------
    requirements might be::

        {
            "artifacts": ["slides.pdf"],
            "metadata": ["name"],
            "non_null_metadata": ["due"],
        }
    """
    for artifact in requirements["artifacts"]:
        if artifact not in publication.artifacts:
            return True
    for metadata in requirements["non_null_metadata"]:
        if (
            metadata not in publication.metadata
            or publication.metadata[metadata] is None
        ):
            return True
    for metadata in requirements["metadata"]:
        if metadata not in publication.metadata:
            return True
    return False
