from ._common import basic_element

SCHEMA = {
    "type": "dict",
    "required_keys": {"contents": {"type": "string", "nullable": True}},
    "optional_keys": {"urgent": {"type": "boolean", "default": False}},
}


announcement_box = basic_element("announcement_box.html", SCHEMA)

# return template.render(
#     element_config=element_config,
#     config=context.config,
#     published=context.materials
# )
