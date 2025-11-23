"""People element for displaying instructors and staff.

A people element renders a display of course staff organized into groups,
such as instructors, teaching assistants, and tutors. Each group contains
a list of members with their details, typically rendered as profile cards.

Features
--------
- Organizes staff into named groups for clear hierarchy
- Supports optional profile photos, websites, roles, and bios
- Flexible structure accommodates various course staffing arrangements

Schema
------
The element expects a list of groups, where each group contains:

group (str): The group name (e.g., "Instructors", "Teaching Assistants").
members (list): List of people in the group, each containing:
    - name (str): The person's name.
    - website (str, optional): URL to the person's website or profile.
    - role (str, optional): The person's specific role or title.
    - photo (str, optional): Path or URL to a profile photo.
    - about (str, optional): A short bio or description.

Example YAML configuration
--------------------------
::

    people:
      - group: Instructors
        members:
          - name: Dr. Jane Smith
            website: https://example.com/jsmith
            role: Professor
            photo: /images/staff/jsmith.jpg
            about: Research interests in algorithms and data structures.
          - name: Dr. John Doe
            role: Lecturer
      - group: Teaching Assistants
        members:
          - name: Alice Johnson
            role: Head TA
            about: Office hours on Tuesdays 2-4pm.
          - name: Bob Williams
"""

from ._common import basic_element

PERSON_SCHEMA = {
    "type": "dict",
    "required_keys": {"name": {"type": "string"}},
    "optional_keys": {
        "website": {"type": "string"},
        "role": {"type": "string"},
        "photo": {"type": "string"},
        "about": {"type": "string"},
    },
}

SCHEMA = {
    "type": "list",
    "element_schema": {
        "type": "dict",
        "required_keys": {
            "group": {"type": "string"},
            "members": {"type": "list", "element_schema": PERSON_SCHEMA},
        },
    },
}


people = basic_element("people.html", SCHEMA)
