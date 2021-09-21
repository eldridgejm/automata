from ._common import basic_element

PERSON_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "name": {"type": "string"}
    },
    "optional_keys": {
        "website": {"type": "string"},
        "role": {"type": "string"},
        "photo": {"type": "string"},
        "about": {"type": "string"},
    }
}

SCHEMA = {
    "type": "list",
    "element_schema": {
        "type": "dict",
        "required_keys": {
            "group": {"type": "string"},
            "members": {"type": "list", "element_schema": PERSON_SCHEMA}
        }
    }
}


people = basic_element("people.html", SCHEMA)
