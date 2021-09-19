import cerberus


SCHEMA = {
    "*": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "text": {"type": "string"},
                "subtext": {"type": "string"},
                "url": {"type": "string"},
                "icon": {"type": "string"},
            },
        },
    }
}


def button_bar(context, element_config):
    templates = context.environment
    now = context.now

    validator = cerberus.Validator(SCHEMA)
    config_as_dict = {"*": element_config}
    config = validator.validated(config_as_dict)

    if config is None:
        raise RuntimeError(f"Invalid config: {validator.errors}")

    template = templates.get_template("button_bar.html")
    return template.render(config=config["*"])
