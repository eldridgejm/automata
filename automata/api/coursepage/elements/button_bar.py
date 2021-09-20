from ._common import basic_element


SCHEMA = {
    "type": "dict",
    "required_keys": {
        "buttons": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {
                    "text": {"type": "string"},
                    "subtext": {"type": "string"},
                    "icon": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        }
    }
}

button_bar = basic_element("button_bar.html", SCHEMA)
