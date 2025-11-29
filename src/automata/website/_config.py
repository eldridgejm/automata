from typing import Any

import smartconfig

from . import elements


class ThemeConfig(smartconfig.Prototype):
    name: str = "default"
    config: dict[str, Any] = {}


class ElementsConfig(smartconfig.Prototype):
    schedule: smartconfig.NotRequired[elements.schedule.Config]
    announcement_box: smartconfig.NotRequired[elements.announcement_box.Config]
    listing: smartconfig.NotRequired[elements.listing.Config]
    people: smartconfig.NotRequired[elements.people.Config]


class Config(smartconfig.Prototype):
    """Website configuration schema."""

    input_path: str
    output_path: str
    theme: ThemeConfig
    elements: ElementsConfig
