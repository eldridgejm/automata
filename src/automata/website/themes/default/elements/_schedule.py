"""Schedule element for displaying a weekly course schedule."""

import datetime
from typing import Any, cast

import smartconfig

import automata.materials
from automata.website import RenderContext, TemplateElement


class Week:
    """Represents a single week in the schedule."""

    def __init__(self, number: int, start_date: datetime.date, topic: str):
        self.number = number
        self.start_date = start_date
        self.topic = topic

    def filter(
        self, collection: automata.materials.Collection, date_key: str
    ) -> automata.materials.Collection:
        """Filter publications in a collection that fall within this week."""
        end_date = self.start_date + datetime.timedelta(weeks=1)

        def _publication_within_week(key: str, node: Any) -> bool:
            if not isinstance(node, automata.materials.Publication):
                return True

            if date_key not in node.metadata:
                return False

            date_value = node.metadata[date_key]
            if isinstance(date_value, datetime.datetime):
                date_value = date_value.date()

            return bool(self.start_date <= date_value < end_date)

        return automata.materials.filter(collection, predicate=_publication_within_week)

    def contains(self, date: datetime.date) -> bool:
        """Check if a date falls within this week."""
        return self.start_date <= date < self.start_date + datetime.timedelta(weeks=1)


class ResourceConfig(smartconfig.Prototype):
    """Configuration for a resource item."""

    text: str
    title: str | None = None
    key_for_parts: str | None = None
    requires: dict[str, Any] | None = None


class LectureConfig(smartconfig.Prototype):
    """Configuration for lecture display."""

    collection: str
    metadata_key_for_released: str
    title: str
    resources: list[ResourceConfig]


class AssignmentConfig(smartconfig.Prototype):
    """Configuration for assignment display."""

    collection: str
    metadata_key_for_released: str
    metadata_key_for_due: str | None
    title: str
    resources: list[ResourceConfig]


class DiscussionConfig(smartconfig.Prototype):
    """Configuration for discussion display."""

    collection: str
    metadata_key_for_released: str
    title: str
    resources: list[ResourceConfig]


class WeekAnnouncementConfig(smartconfig.Prototype):
    """Configuration for a week announcement."""

    week: int
    content: str
    urgent: bool = False


class Schedule(TemplateElement):
    """Element that displays a weekly course schedule."""

    template = "elements/schedule.html"
    schema = {
        "type": "dict",
        "required_keys": {
            "week_topics": {"type": "list", "element_schema": {"type": "string"}},
            "first_week_start_date": {"type": "date"},
            "lecture": LectureConfig._schema(),
            "assignments": {
                "type": "list",
                "element_schema": AssignmentConfig._schema(),
            },
            "discussions": {
                "type": "list",
                "element_schema": DiscussionConfig._schema(),
            },
        },
        "optional_keys": {
            "week_order": {"type": "string", "default": "this_week_first"},
            "exams": {"type": "dict", "extra_keys_schema": {"type": "date"}},
            "week_announcements": {
                "type": "list",
                "element_schema": WeekAnnouncementConfig._schema(),
            },
            "first_week_number": {"type": "integer", "default": 1},
        },
    }

    def template_vars(
        self,
        context: RenderContext,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        """Provide additional template variables."""
        tvars = super().template_vars(context, config)

        config_dict = cast(dict[str, Any], config)

        # Generate weeks
        weeks = self._generate_weeks(config_dict)

        # Order weeks based on configuration
        weeks = self._order_weeks(config_dict, weeks, context.now.date())

        # Find current week
        this_week = None
        for week in weeks:
            if week.contains(context.now.date()):
                this_week = week
                break

        tvars.update(
            {
                "weeks": weeks,
                "this_week": this_week,
            }
        )

        return tvars

    def _generate_weeks(self, config: dict[str, Any]) -> list[Week]:
        """Generate Week objects from configuration."""
        weeks = []
        first_week_number = config.get("first_week_number", 1)
        first_week_start_date = config["first_week_start_date"]

        for i, topic in enumerate(config["week_topics"]):
            week = Week(
                number=first_week_number + i,
                topic=topic,
                start_date=first_week_start_date + datetime.timedelta(weeks=i),
            )
            weeks.append(week)

        return weeks

    def _order_weeks(
        self, config: dict[str, Any], weeks: list[Week], today: datetime.date
    ) -> list[Week]:
        """Order weeks based on configuration."""
        week_order = config.get("week_order", "this_week_first")

        if week_order == "this_week_last":
            return sorted(weeks, key=lambda w: w.start_date)
        else:  # this_week_first
            past_weeks = [w for w in weeks if w.start_date <= today]
            future_weeks = [w for w in weeks if w.start_date > today]

            past = sorted(past_weeks, key=lambda w: w.start_date, reverse=True)
            future = sorted(future_weeks, key=lambda w: w.start_date)

            return past + future
