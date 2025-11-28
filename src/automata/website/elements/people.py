"""People element for displaying instructors and staff.

A people element renders a display of course staff organized into groups,
such as instructors, teaching assistants, and tutors. Each group contains
a list of members with their details, typically rendered as profile cards.

Features
--------
- Organizes staff into named groups within a top-level config for clarity
- Supports optional profile photos, websites, roles, and bios
- Flexible structure accommodates various course staffing arrangements

Schema
------
The element expects a mapping with a ``groups`` key, whose value is a list of
groups. Each group contains:

groups (list):
  - name (str): The group name (e.g., "Instructors", "Teaching Assistants").
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
      groups:
        - name: Instructors
          members:
            - name: Dr. Jane Smith
              website: https://example.com/jsmith
              role: Professor
              photo: /images/staff/jsmith.jpg
              about: Research interests in algorithms and data structures.
            - name: Dr. John Doe
              role: Lecturer
        - name: Teaching Assistants
          members:
            - name: Alice Johnson
              role: Head TA
              about: Office hours on Tuesdays 2-4pm.
            - name: Bob Williams
"""

from smartconfig import NotRequired, Prototype

from ._common import basic_element


class Person(Prototype):
    name: str
    website: NotRequired[str]
    role: NotRequired[str]
    photo: NotRequired[str]
    about: NotRequired[str]


class Group(Prototype):
    name: str
    members: list[Person]


class Config(Prototype):
    groups: list[Group]


SCHEMA = Config._schema()


people = basic_element("people.html", SCHEMA)
