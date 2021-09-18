import cerberus


SCHEMA = {
    "contents": {"type": "string", "nullable": True},
    "urgent": {"type": "boolean", "default": False},
}


def announcement_box(environment, context, element_config, now):
    validator = cerberus.Validator(SCHEMA)
    element_config = validator.validated(element_config)

    if element_config is None:
        raise RuntimeError(f"Invalid config: {validator.errors}")

    template = environment.get_template("announcement_box.html")
    return template.render(
        element_config=element_config,
        config=context["config"],
        published=context["published"],
    )
