from datetime import date

from smartconfig import Prototype

from automata.website import TemplateElement


class DatePillConfig(Prototype):
    date: date
    text_before: str
    text_after: str
    text_class: str = "text-base"


class DatePill(TemplateElement):
    template = "elements/date_pill.html"
    schema = DatePillConfig._schema()
