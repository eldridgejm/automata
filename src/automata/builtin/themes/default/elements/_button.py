from smartconfig import Prototype

from automata.website import TemplateElement


class ButtonConfig(Prototype):
    label: str
    url: str


class Button(TemplateElement):
    template = "elements/button.html"
    schema = ButtonConfig._schema()
