import dictconfig
import jinja2


def create_element_environment(input_path):
    """Create the element environment and its custom filters."""
    element_environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(input_path / "theme" / "elements"),
        undefined=jinja2.StrictUndefined,
    )

    def evaluate(s, **kwargs):
        _DELIMITER_KWARGS = dict(
            variable_start_string="${",
            variable_end_string="}",
            block_start_string="${%",
            block_end_string="%}",
        )

        try:
            return jinja2.Template(
                s, **_DELIMITER_KWARGS, undefined=jinja2.StrictUndefined
            ).render(**kwargs)
        except jinja2.UndefinedError as exc:
            raise exceptions.ElementError(
                f'Unknown variable in template string "{s}": {exc}'
            )

    element_environment.filters["evaluate"] = evaluate

    return element_environment


def basic_element(template_filename, config_schema, extra_render_vars=None):
    def element(context, element_config):
        element_config = dictconfig.resolve(element_config, config_schema)
        element_environment = create_element_environment(context.input_path)
        template = element_environment.get_template(template_filename)

        if extra_render_vars is not None:
            extra_vars = extra_render_vars(context, element_config)
        else:
            extra_vars = {}

        return template.render(element_config=element_config, **context._asdict(), **extra_vars)
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
