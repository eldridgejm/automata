import smartconfig

from automata.website import TemplateElement


class PersonConfig(smartconfig.Prototype):
    """Configuration for a single person."""

    name: str
    website: str | None = None
    role: str | None = None
    photo: str | None = None
    about: str | None = None


class GroupConfig(smartconfig.Prototype):
    """Configuration for a group of people."""

    group: str
    members: list[PersonConfig]


class People(TemplateElement):
    """Element that displays groups of people with photos and info."""

    template = "elements/people.html"
    schema = {"type": "list", "element_schema": GroupConfig._schema()}
