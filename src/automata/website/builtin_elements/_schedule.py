"""Element for displaying a week-by-week course schedule."""

import datetime
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import smartconfig

import automata.materials
import automata.util.resolution
import automata.util.weeks
from automata.website import RenderContext, TemplateElement
from automata.website.exceptions import WebsiteError

# helpers ==============================================================================

T = TypeVar("T")


def flatten(list_of_lists: list[list[T]]) -> list[T]:
    """Flatten a list of lists into a single list."""
    return [item for sublist in list_of_lists for item in sublist]


# schemas ==============================================================================

# resource config schemas --------------------------------------------------------------


class HTMLResourceConfig(smartconfig.Prototype):
    """Configuration for an HTML resource item."""

    html: str
    title: str | None = None
    icon: str | None = None
    type: str = "html"


class MarkdownResourceConfig(smartconfig.Prototype):
    """Configuration for a Markdown resource."""

    type: str = "markdown"
    markdown: str
    title: str | None = None
    icon: str | None = None


class LinkConfig(smartconfig.Prototype):
    """Configuration for a single link item."""

    text: str
    url: str


class LinksResourceConfig(smartconfig.Prototype):
    """Configuration for a List resource."""

    type: str = "links"
    links: list[LinkConfig]
    title: str | None = None
    icon: str | None = None
    style: str | None = "numbered"  # e.g., "bulleted", "numbered", "buttons"


class MetadataLinksResourceConfig(smartconfig.Prototype):
    """Configuration for a Metadata List resource."""

    type: str = "metadata_links"
    metadata_key_for_links: str
    for_each_link: LinkConfig
    title: str | None = None
    icon: str | None = None
    style: str | None = "numbered"  # e.g., "bulleted", "numbered", "buttons"


class ArtifactLinkConfig(smartconfig.Prototype):
    """Configuration for a single artifact link item."""

    text: str
    artifact: str


class ArtifactLinksResourceConfig(smartconfig.Prototype):
    """Configuration for an Artifact List resource."""

    type: str = "artifact_links"
    links: list[ArtifactLinkConfig]
    title: str | None = None
    icon: str | None = None
    style: str | None = "buttons"  # e.g., "bulleted", "numbered", "buttons"


def resource_config_dynamic_schema(config: dict, keypath) -> smartconfig.types.Schema:
    """Determines the resource schema to use based on the configuration itself.

    An activity can contain a list of several resources, and each can be a different
    type. Because of this, we use a dynamic schema to determine the element schemas
    on-the-fly.

    """
    if "type" not in config:
        raise smartconfig.exceptions.ResolutionError(
            "Resource config missing required 'type' field.", keypath
        )

    resource_type = config["type"]
    if resource_type == "html":
        return HTMLResourceConfig._schema()
    elif resource_type == "markdown":
        return MarkdownResourceConfig._schema()
    elif resource_type == "links":
        return LinksResourceConfig._schema()
    elif resource_type == "metadata_links":
        return MetadataLinksResourceConfig._schema()
    elif resource_type == "artifact_links":
        return ArtifactLinksResourceConfig._schema()
    else:
        raise smartconfig.exceptions.ResolutionError(
            f"Unsupported resource type: {resource_type}.", keypath
        )


# activity config and activity collection config schemas -------------------------------

ACTIVITY_CONFIG_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "title": {"type": "string"},
        "start_displaying_on": {"type": "string"},
        "resources": {
            "type": "list",
            "element_schema": resource_config_dynamic_schema,
        },
    },
    "optional_keys": {
        "week_range_start": {"type": "string", "nullable": True, "default": None},
        "week_range_end": {"type": "string", "nullable": True, "default": None},
        "due_datetime": {"type": "string", "nullable": True, "default": None},
    },
}

_ACSWD: dict[str, Any] = deepcopy(ACTIVITY_CONFIG_SCHEMA)
_ACSWD["required_keys"]["start_displaying_on"]["type"] = "date"
_ACSWD["optional_keys"]["week_range_start"]["type"] = "date"
_ACSWD["optional_keys"]["week_range_end"]["type"] = "date"
_ACSWD["optional_keys"]["due_datetime"]["type"] = "datetime"
ACTIVITY_CONFIG_SCHEMA_WITH_DATES = _ACSWD


ACTIVITY_COLLECTION_CONFIG_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "collection": {"type": "string"},
        "for_each_publication": ACTIVITY_CONFIG_SCHEMA,
    },
}


# misc. configs  -----------------------------------------------------------------------


class AnnouncementConfig(smartconfig.Prototype):
    """Configuration for an announcement.

    If the week is None, the announcement is shown at the top of the most recent
    week, every week.

    """

    week: int | None
    content: str
    urgent: bool = False


class EventConfig(smartconfig.Prototype):
    """Configuration for an event."""

    name: str
    date: datetime.date


# full schema --------------------------------------------------------------------------

SCHEDULE_SCHEMA = {
    "type": "dict",
    "required_keys": {
        "week_topics": {"type": "list", "element_schema": {"type": "string"}},
        "first_week_start_date": {"type": "date"},
        "primary_activity_collections": {
            "type": "list",
            "element_schema": ACTIVITY_COLLECTION_CONFIG_SCHEMA,
        },
        "secondary_activity_collections": {
            "type": "list",
            "element_schema": ACTIVITY_COLLECTION_CONFIG_SCHEMA,
        },
    },
    "optional_keys": {
        "week_order": {"type": "string", "default": "this_week_first"},
        "events": {
            "type": "list",
            "element_schema": EventConfig._schema(),
            "default": [],
        },
        "announcements": {
            "type": "list",
            "element_schema": AnnouncementConfig._schema(),
        },
        "first_week_number": {"type": "integer", "default": 1},
        "extra_primary_activities": {
            "type": "list",
            "element_schema": ACTIVITY_CONFIG_SCHEMA_WITH_DATES,
            "default": [],
        },
        "extra_secondary_activities": {
            "type": "list",
            "element_schema": ACTIVITY_CONFIG_SCHEMA_WITH_DATES,
            "default": [],
        },
    },
}

# make_activities() ====================================================================


@dataclass
class Activity:
    title: str
    resources: list[HTMLResourceConfig | MarkdownResourceConfig | LinksResourceConfig]
    start_displaying_on: datetime.date
    week_range_start: datetime.date
    week_range_end: datetime.date
    due_datetime: datetime.datetime


# make_activity_from_config ------------------------------------------------------------


def make_activity_from_config(
    config: smartconfig.types.Configuration, context: RenderContext
) -> Activity:
    """Converts an activity configuration dict into an Activity instance.

    This does not do any conversion of the resources that require a publication, but
    it does resolve the activity configuration itself with the render context available.
    This is suitable for extra activities that do not depend on publications.

    Parameters
    ----------
    config : smartconfig.types.Configuration
        The activity configuration.
    context : RenderContext
        The rendering context.

    Returns
    -------
    Activity
        The resulting Activity instance.

    """
    config = automata.util.resolution.unwrap_raw_strings(config)

    resolved_config = automata.util.resolution.resolve(
        config,
        ACTIVITY_CONFIG_SCHEMA_WITH_DATES,
        global_variables=context.to_dict(),
    )

    resolved_config = cast(dict, resolved_config)

    # Validate that activities only use allowed resource types
    # (artifact_links and metadata_links require a publication context)
    for resource in resolved_config["resources"]:
        if resource["type"] not in ("html", "markdown", "links"):
            raise WebsiteError(
                f"Extra activities can only use 'html', 'markdown', or 'links' "
                f"resource types, but got '{resource['type']}'"
            )

    return Activity(
        title=resolved_config["title"],
        resources=resolved_config["resources"],
        start_displaying_on=resolved_config["start_displaying_on"],
        week_range_start=resolved_config["week_range_start"],
        week_range_end=resolved_config["week_range_end"],
        due_datetime=resolved_config["due_datetime"],
    )


# make_activities_from_collection_config -----------------------------------------------


def fixup_metadata_links_resource_config(
    config: dict, publication: automata.materials.Publication
):
    """Resolves each item in the metadata links resource configuration, resulting in a
    simple links resource configuration.

    This provides "publication" and "item" variables to the template at resolution time.

    Any markdown-to-html conversion is handled in the schedule.html template.

    Parameters
    ----------
    config : dict
        The items resource configuration.
    publication : automata.materials.Publication
        The publication from which to source the items.

    Returns
    -------
    dict
        The resolved links resource configuration.

    """
    # a new LinksResourceConfig
    new_config: dict[str, Any] = {
        "type": "links",
        "title": config.get("title"),
        "icon": config.get("icon"),
        "style": config.get("style"),
    }

    key = config["metadata_key_for_links"]
    if key in publication.metadata:
        links = publication.metadata[key]
    else:
        links = []

    link_config = config["for_each_link"]
    link_config = automata.util.resolution.unwrap_raw_strings(link_config)

    new_config["links"] = automata.util.resolution.resolve_for_each(
        links,
        link_config,
        LinkConfig._schema(),
        loop_variable="link",
        vars={"publication": publication},
    )

    return new_config


def fixup_artifact_links_resource_config(
    config: dict, publication: automata.materials.Publication
):
    """Converts artifact links resource configuration into links resource configuration.

    This function converts artifact references to actual URLs by looking up the artifact
    paths in the publication. If the artifact doesn't exist (i.e., it hasn't yet been
    released), that link is omitted.

    Parameters
    ----------
    config : dict
        The artifact links resource configuration.
    publication : automata.materials.Publication
        The publication from which to resolve artifact paths.

    Returns
    -------
    dict
        The resolved links resource configuration.

    """
    new_config: smartconfig.types.ConfigurationDict = {
        "type": "links",
        "title": config.get("title"),
        "icon": config.get("icon"),
        "style": config.get("style"),
    }

    # Convert each artifact link to a regular link
    new_config["links"] = []
    for link in config["links"]:
        if link["artifact"] in publication.artifacts:
            cast(list, new_config["links"]).append(
                {
                    "text": link["text"],
                    "url": publication.artifacts[link["artifact"]].path,
                }
            )

    return new_config


def make_activities_from_collection_config(
    config: dict, context: RenderContext
) -> list[Activity]:
    """Expands a collection config into a list of Activity instances, one for each pub.

    This is a main helper function for `make_activities` below. It is applied in a
    loop to all elements of `primary_activity_collections` and
    `secondary_activity_collections`.

    Notes
    -----

    This function is given a collection config of the form:

        ```yaml
        collection: "some_collection_name"
        for_each_publication:
          title: !raw "Activity for ${ publication.metadata.title }"
          start_displaying_on: !raw "${ publication.metadata.release_date }"
          resources:
              ...
        ```

    It then resolves the `for_each_publication` config against each publication in the
    specified collection, resulting in a list of activity configs.

    Some of the resources in each activity may require further resolution (e.g.,
    metadata links resources and artifact links resources), and this is done as part of
    a "fixup" step. This step "converts" all metadata links resources and artifact links
    resources into simple links resources.

    The activity configs are then each converted to Activity instances and returned as a
    list.

    Parameters
    ----------
    config : dict
        The collection configuration.
    context : RenderContext
        The rendering context.

    Returns
    -------
    list[Activity]
        The list of Activity instances.

    """

    collection = context.materials.collections[config["collection"]]
    publications = list(collection.publications.values())

    for_each_publication_config = config["for_each_publication"]

    # many of the entries of the `for_each_publication` config may be raw strings
    # whose evaluation is deferred until we have a specific publication to work with.
    # We need to unwrap these raw strings before passing the config to
    # `resolve_for_each_publication`. However, some of the resource types (e.g.,
    # metadata_links) need to remain as raw strings until after resolution, because they
    # need to be resolved in a nested loop. To do this, we define a `preserve` function
    # that tells `unwrap_raw_strings` which parts of the config to leave alone.

    def raw_strings_in_metadata_links(config):
        """Do not unwrap raw strings in metadata_links resource configs (yet)"""
        return (
            isinstance(config, dict)
            and "type" in config
            and config["type"] == "metadata_links"
        )

    for_each_publication_config = automata.util.resolution.unwrap_raw_strings(
        for_each_publication_config, preserve=raw_strings_in_metadata_links
    )

    # now that raw strings have been unwrapped as needed, we can resolve the
    # `for_each_publication` config for each publication. After each config has been
    # resolved, we will need to do some fixup on the resources:
    #
    # 1. Convert any artifact links resources into simple links resources by looking up
    #    artifact paths in the publication.
    #
    # 2. Expand any metadata links resources by resolving the link configuration against
    #    each item in the specified metadata key of the publication.

    def fixup(
        config: smartconfig.types.Configuration,
        publication: automata.materials.Publication,
    ) -> smartconfig.types.Configuration:
        """Fixes up resource configs in-place after resolution."""
        config_dict = cast(dict[str, dict], config)
        for i, resource in enumerate(config_dict["resources"]):
            assert isinstance(resource, dict)
            if resource["type"] == "artifact_links":
                config_dict["resources"][i] = fixup_artifact_links_resource_config(
                    resource, publication
                )
            elif resource["type"] == "metadata_links":
                config_dict["resources"][i] = fixup_metadata_links_resource_config(
                    resource, publication
                )
        return config

    activity_configs = automata.materials.resolve_for_each_publication(
        publications,
        for_each_publication_config,
        schema=ACTIVITY_CONFIG_SCHEMA_WITH_DATES,
        vars=context.to_dict(),
        fixup=fixup,
    )

    # finally, convert each activity config into an Activity instance
    return [
        Activity(**activity_config)
        for activity_config in cast(list[dict], activity_configs)
    ]


# make_activities ----------------------------------------------------------------------


def make_activities(
    config: dict, context: RenderContext, weeks: list[automata.util.weeks.Week]
) -> tuple[dict[int | None, list[Activity]], dict[int | None, list[Activity]]]:
    """Maps week numbers to Activities that should be displayed in that week.

    This function is provided a schedule configuration that has been resolved,
    but which requires further processing to produce activities. In particular,
    this function does the following:

        1. Make activities from each activity collection in the primary and
           secondary activity collections. This involves "expanding" each
           collection config by resolving the `for_each_publication` config
           against each publication in the specified collection, resulting in a
           list of activity configs. Some of the resources in each activity may
           require further resolution (e.g., metadata links resources and
           artifact links resources), and this is also done at this step.

        2. Make activities from each extra activity config in the primary and secondary
           extra activities. These activities are simpler, as they do not involve
           resolving against publications.

        3. Place each activity into the appropriate "display week" based on the
           activity's display date attributes. This step handles default values
           for display dates that are `None`.

    Parameters
    ----------
    config : dict
        The schedule configuration.
    context : RenderContext
        The rendering context.
    weeks : list[automata.util.weeks.Week]
        The list of weeks in the schedule.

    Returns
    -------
    tuple[dict[int | None, list[Activity]], dict[int | None, list[Activity]]]
        A pair of dictionaries (primary and secondary) mapping week numbers to lists
        of activities.

    """

    primary_activities = flatten(
        [
            make_activities_from_collection_config(activity_collection_config, context)
            for activity_collection_config in config["primary_activity_collections"]
        ]
    )

    secondary_activities = flatten(
        [
            make_activities_from_collection_config(activity_collection_config, context)
            for activity_collection_config in config["secondary_activity_collections"]
        ]
    )

    primary_activities += [
        make_activity_from_config(activity_config, context)
        for activity_config in config["extra_primary_activities"]
    ]

    secondary_activities += [
        make_activity_from_config(activity_config, context)
        for activity_config in config["extra_secondary_activities"]
    ]

    week_to_primary_activities = automata.util.weeks.place_into_display_weeks(
        primary_activities,
        weeks,
        current_date=context.current_time.date(),
        start_displaying_on=lambda a: a.start_displaying_on,
        week_range_start=lambda a: a.week_range_start,
        week_range_end=lambda a: a.week_range_end,
    )

    week_to_secondary_activities = automata.util.weeks.place_into_display_weeks(
        secondary_activities,
        weeks,
        current_date=context.current_time.date(),
        start_displaying_on=lambda a: a.start_displaying_on,
        week_range_start=lambda a: a.week_range_start,
        week_range_end=lambda a: a.week_range_end,
    )

    return week_to_primary_activities, week_to_secondary_activities


# make_events() ========================================================================


@dataclass
class Event:
    name: str
    date: datetime.date
    display_week: int | None


def make_events(element_config, weeks) -> dict[int | None, list[Event]]:
    """Produces a dict mapping week numbers to Event instances from the
    events in the config.

    This function determines the display week of the event. If the event date does not
    fall into any week, the display week is set to None.

    Parameters
    ----------
    element_config : dict
        The configuration for the schedule element.
    weeks : list[automata.util.weeks.Week]
        The list of weeks in the schedule.

    Returns
    -------
    dict[int | None, list[Event]]
        A dictionary mapping week numbers to lists of events.

    """
    week_to_events: dict[int | None, list[Event]] = {week.number: [] for week in weeks}
    week_to_events[None] = []

    for event_config in element_config["events"]:
        week = automata.util.weeks.find_week(weeks, event_config["date"])
        display_week_number = week.number if week else None

        event = Event(
            name=event_config["name"],
            date=event_config["date"],
            display_week=display_week_number,
        )

        week_to_events[display_week_number].append(event)

    return week_to_events


# make_announcements() =================================================================


@dataclass
class Announcement:
    week: int | None
    content: str
    urgent: bool
    display_week: int | None


def make_announcements(
    element_config, weeks: list[automata.util.weeks.Week], current_date: datetime.date
) -> dict[int | None, list[Announcement]]:
    """Produces a dict mapping week numbers to Announcement instances from
    the announcements in the config.

    This function determines the display week of the announcement. If the announcement's
    week attribute is None, the display week is set to the most recent week.

    Parameters
    ----------
    element_config : dict
        The configuration for the schedule element.
    weeks : list[automata.util.weeks.Week]
        The list of weeks in the schedule.
    current_date : datetime.date
        The current date used to determine the most recent week.

    Returns
    -------
    dict[int | None, list[Announcement]]
        A dictionary mapping week numbers to lists of announcements.

    """
    week_to_announcements: dict[int | None, list[Announcement]] = {
        week.number: [] for week in weeks
    }
    week_to_announcements[None] = []

    # Find the most recent week for announcements with week=None
    past_weeks, _ = automata.util.weeks.order_weeks_by_recency(weeks, current_date)
    most_recent_week = past_weeks[0] if past_weeks else None

    for announcement_config in element_config.get("announcements", []):
        if announcement_config["week"] is None:
            # Show at the top of the most recent week
            display_week = most_recent_week.number if most_recent_week else None
        else:
            # Show in the specified week
            display_week = announcement_config["week"]

        announcement = Announcement(
            week=announcement_config["week"],
            content=announcement_config["content"],
            urgent=announcement_config.get("urgent", False),
            display_week=display_week,
        )

        week_to_announcements[display_week].append(announcement)

    return week_to_announcements


# misc. ================================================================================


def order_weeks(
    week_order: str,
    weeks: list[automata.util.weeks.Week],
    current_date: datetime.date,
) -> list[automata.util.weeks.Week]:
    """Order weeks based on the specified week order.

    Parameters
    ----------
    week_order : str
        The order in which to arrange the weeks. Options are:
        - "this_week_first": Start with the current week, then past weeks (most recent
          first), then future weeks (soonest first).
        - "chronological": Start with the earliest week and proceed to the latest.
    weeks : list[automata.util.weeks.Week]
        The list of weeks to order.
    current_date : datetime.date
        The current date used to determine the current week.

    Returns
    -------
    list[automata.util.weeks.Week]
        The ordered list of weeks.
    """
    if week_order == "this_week_first":
        past, future = automata.util.weeks.order_weeks_by_recency(weeks, current_date)
        return past + future
    elif week_order == "chronological":
        return sorted(weeks, key=lambda w: w.start_date)
    else:
        raise WebsiteError(f"Unsupported week_order: {week_order}")


# schedule element =====================================================================


class Schedule(TemplateElement):
    """Element that displays a weekly course schedule."""

    template = "elements/schedule.html"
    schema = SCHEDULE_SCHEMA

    def template_vars(
        self,
        config: smartconfig.types.Configuration,
    ) -> dict[str, Any]:
        """
        Provide the template variables:

            weeks : list[Week]
                A list of Week objects, one for each topic in the config's `week_topics`
                field
            this_week : Week | None
                The Week object corresponding to the current date, if any.
            topics : dict[int, str]
                A mapping from week numbers to topics.
            primary_activities : dict[int | None, list[Activity]]
                A mapping from week numbers to the primary activities for that week.
            secondary_activities : dict[int | None, list[Activity]]
                A mapping from week numbers to the secondary activities for that week.
            announcements : dict[int | None, list[Announcement]]
                A mapping from week numbers to the announcements for that week.
            events : dict[int | None, list[Event]]
                A mapping from week numbers to the events for that week.

        For the last four mappings, the "None" key corresponds to activities, events,
        or announcements that did not land in any week.

        Parameters
        ----------
        config : smartconfig.types.Configuration
            The configuration for this element.

        Returns
        -------
        dict[str, Any]
            A dictionary of template variables to add to the context.
        """

        tvars = super().template_vars(config)

        config_dict = cast(dict[str, Any], config)

        weeks = automata.util.weeks.make_n_weeks(
            start_date=config_dict["first_week_start_date"],
            n=len(config_dict["week_topics"]),
            first_week_number=config_dict.get("first_week_number", 1),
        )

        topics = {
            week.number: topic for week, topic in zip(weeks, config_dict["week_topics"])
        }

        weeks = order_weeks(
            config_dict.get("week_order", "this_week_first"),
            weeks,
            self.context.current_time.date(),
        )

        this_week = automata.util.weeks.find_week(
            weeks, self.context.current_time.date()
        )

        events = make_events(config_dict, weeks)

        announcements = make_announcements(
            config_dict, weeks, self.context.current_time.date()
        )

        primary_activities, secondary_activities = make_activities(
            config_dict, self.context, weeks
        )

        tvars.update(
            {
                "weeks": weeks,
                "this_week": this_week,
                "topics": topics,
                "primary_activities": primary_activities,
                "secondary_activities": secondary_activities,
                "announcements": announcements,
                "events": events,
            }
        )

        return tvars
