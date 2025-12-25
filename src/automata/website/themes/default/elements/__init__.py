import smartconfig

from automata.website._elements import template_element
from automata.website._render import RenderContext


class AnnouncementBoxSchema(smartconfig.Prototype):
    content: str | None
    urgent: bool = False


@template_element(AnnouncementBoxSchema, "elements/announcement_box.html")
def announcement_box(config: AnnouncementBoxSchema, context: RenderContext) -> dict:
    return {}


elements = {
    "announcement_box": announcement_box,
}
