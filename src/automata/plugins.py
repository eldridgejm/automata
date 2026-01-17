"""Plugin configuration prototypes."""

from typing import Any

import smartconfig


class PluginConfig(smartconfig.Prototype):
    """Configuration for a plugin."""

    # which plugin to use. If this contains slashes, it is treated as a path to a
    # plugin directory. Otherwise, it is treated as the name of an entry point.
    use: str

    # additional configuration options to pass to the plugin
    config: Any = {}
