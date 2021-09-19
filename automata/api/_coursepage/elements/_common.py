import dictconfig
import jinja2

from .. import exceptions


def render_element_template(template_name, context, extra_vars=None):
    if extra_vars is None:
        extra_vars = {}

    element_environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(context.theme_path / 'elements'),
        undefined=jinja2.StrictUndefined,
    )

    def evaluate(s, **kwargs):
        try:
            return jinja2.Template(
                s, undefined=jinja2.StrictUndefined
            ).render(**kwargs)
        except jinja2.UndefinedError as exc:
            raise exceptions.ElementError(
                f'Unknown variable in template string "{s}": {exc}'
            )

    def markdown_to_html(s):
        return s

    element_environment.filters["evaluate"] = evaluate
    element_environment.filters["markdown_to_html"] = markdown_to_html

    template = element_environment.get_template(template_name)
    return template.render(context=context, **extra_vars)

def basic_element(template_filename, config_schema, extra_render_vars=None):
    def element(context, element_config):
        element_config = dictconfig.resolve(element_config, config_schema)

        if extra_render_vars is not None:
            extra_vars = extra_render_vars(context, element_config)
        else:
            extra_vars = {}

        return render_element_template(template_filename, context, {'element_config': element_config, **extra_vars})
    return element

def is_something_missing(publication, requirements):
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
