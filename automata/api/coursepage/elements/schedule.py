import datetime

import dictconfig

import automata.materials
from ._common import is_something_missing, render_element_template


RESOURCES_SCHEMA = {
    "type": "list",
    "element_schema": {
        "type": "dict",
        "required_keys": {
            "text": {"type": "string"},
        },
        "optional_keys": {
            "title": {"type": "string", "nullable": True, "default": None},
            "key_for_parts": {"type": "string"},
            "requires": {
                "type": "dict",
                "optional_keys": {
                    "artifacts": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                        "default": [],
                    },
                    "metadata": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                        "default": [],
                    },
                    "non_null_metadata": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                        "default": [],
                    },
                    "text_if_missing": {
                        "type": "string",
                        "nullable": True,
                        "default": None,
                    },
                },
                "default": None,
                "nullable": True,
            },
        },
    },
}

SCHEMA = {
    "type": "dict",
    "required_keys": {
        "week_topics": {"type": "list", "element_schema": {"type": "string"}},
        "first_week_start_date": {"type": "date"},
        "lecture": {
            "type": "dict",
            "required_keys": {
                "collection": {"type": "string"},
                "metadata_key_for_released": {"type": "string"},
                "title": {"type": "string"},
                "resources": RESOURCES_SCHEMA,
            },
            "optional_keys": {
            },
        },
        "assignments": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {
                    "collection": {"type": "string"},
                    "metadata_key_for_released": {"type": "string"},
                    "metadata_key_for_due": {"type": "string", "nullable": True},
                    "title": {"type": "string"},
                    "resources": RESOURCES_SCHEMA,
                },
            },
        },
        "discussions": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {
                    "collection": {"type": "string"},
                    "metadata_key_for_released": {"type": "string"},
                    "title": {"type": "string"},
                    "resources": RESOURCES_SCHEMA,
                },
            },
        },
    },
    "optional_keys": {
        "week_order": {
            "type": "string",
            "default": "this_week_first",
            # "allowed": ["this_week_first", "this_week_last"],
        },
        "exams": {
            "type": "dict",
            "extra_keys_schema": {"type": "date"},
        },
        "week_announcements": {
            "type": "list",
            "element_schema": {
                "type": "dict",
                "required_keys": {
                    "week": {"type": "integer"},
                    "content": {"type": "string"},
                },
                "optional_keys": {
                    "urgent": {"type": "boolean", "default": False},
                },
            },
        },
        "first_week_number": {"type": "integer", "default": 1},
    },
}


ONE_WEEK = datetime.timedelta(weeks=1)


def _publication_within_week(start_date, date_key):
    def filter(key, node):
        if not isinstance(node, automata.materials.Publication):
            return True
        else:
            date = node.metadata[date_key]
            if isinstance(date, datetime.datetime):
                date = date.date()

            return start_date <= date < start_date + ONE_WEEK

    return filter


class Week:
    def __init__(self, number, start_date, topic):
        self.number = number
        self.start_date = start_date
        self.topic = topic

    def filter(self, collection, date_key):
        return automata.materials.filter_nodes(
            collection, _publication_within_week(self.start_date, date_key)
        )

    def contains(self, date):
        return self.start_date <= date < self.start_date + ONE_WEEK


def generate_weeks(element_config, published):
    weeks = []
    for i, topic in enumerate(element_config["week_topics"]):
        week = Week(
            number=element_config["first_week_number"] + i,
            topic=topic,
            start_date=element_config["first_week_start_date"] + i * ONE_WEEK,
        )
        weeks.append(week)

    return weeks


def order_this_week_first(weeks, today):
    past_weeks = [w for w in weeks if w.start_date <= today]
    future_weeks = [w for w in weeks if w.start_date > today]

    past = sorted(past_weeks, key=lambda x: x.start_date, reverse=True)
    future = sorted(future_weeks, key=lambda x: x.start_date, reverse=False)

    return past + future


def order_this_week_last(weeks, today):
    return sorted(weeks, key=lambda x: x.start_date)


def order_weeks(element_config, weeks, today):
    if "week_order" not in element_config:
        week_order = "this_week_first"
    else:
        week_order = element_config["week_order"]

    return {
        "this_week_first": order_this_week_first,
        "this_week_last": order_this_week_last,
    }[week_order](weeks, today)


def schedule(context, element_config):
    element_config = dictconfig.resolve(element_config, SCHEMA)

    weeks = generate_weeks(element_config, context.materials)
    weeks = order_weeks(element_config, weeks, context.now.date())

    try:
        [this_week] = [w for w in weeks if w.contains(context.now.date())]
    except ValueError:
        this_week = None

    return render_element_template(
        "schedule.html",
        context,
        extra_vars=dict(
            element_config=element_config,
            weeks=weeks,
            this_week=this_week,
            is_something_missing=is_something_missing,
        ),
    )
