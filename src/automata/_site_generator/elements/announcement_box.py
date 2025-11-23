"""Announcement box element for displaying announcements."""

from ._common import basic_element

SCHEMA = {
    "type": "dict",
    "required_keys": {"content": {"type": "string", "nullable": True}},
    "optional_keys": {"urgent": {"type": "boolean", "default": False}},
}


announcement_box = basic_element("announcement_box.html", SCHEMA)
