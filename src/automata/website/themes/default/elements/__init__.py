"""Elements for the default Automata theme.

This module contains the standard elements provided by the default theme:
- announcement_box: Display highlighted announcements
- listing: Render lists of course materials
- people: Display course staff information
- schedule: Show course schedules with topics and readings
"""

from . import announcement_box, listing, people, schedule

__all__ = ["announcement_box", "listing", "people", "schedule"]
