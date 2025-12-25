import smartconfig

from automata.website import TemplateElement


class AnnouncementBoxConfig(smartconfig.Prototype):
    content: str | None
    urgent: bool = False


class AnnouncementBox(TemplateElement):
    template = "elements/announcement_box.html"
    schema = AnnouncementBoxConfig._schema()
