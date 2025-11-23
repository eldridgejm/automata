"""Announcement box element for displaying announcements.

An announcement box is a page element that renders a highlighted box containing
an announcement message. It is typically used to display important notices,
updates, or time-sensitive information on a course website.

Features
--------
- Supports markdown content for rich text formatting
- Optional "urgent" flag to visually distinguish critical announcements

Schema
------
content (str): The announcement text to display. Supports markdown.
urgent (bool, optional): If True, the announcement is styled as urgent
    (e.g., with a different color or icon). Defaults to False.

Example YAML configuration
--------------------------
::

    announcement_box:
      content: |
        **Midterm next week!** Review sessions available on Thursday.
      urgent: true
"""

from ._common import basic_element

SCHEMA = {
    "type": "dict",
    "required_keys": {"content": {"type": "string"}},
    "optional_keys": {"urgent": {"type": "boolean", "default": False}},
}


announcement_box = basic_element("announcement_box.html", SCHEMA)
