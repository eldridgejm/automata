import yaml


def load_yaml(path):
    """Read a YAML file. Supports including other yaml files.

    Parameters
    ----------
    path : pathlib.Path
        The path to the configuration file.

    Returns
    -------
    dict
        The loaded YAML as a dictionary.

    Note
    ----

    This loader supports the ``!include`` tag, allowing the file to be split
    into several files. For instance:

    .. code-block:: yaml

        # config.yaml
        template:
            page_title: My Website

        schedule: !include schedule.yaml
        announcements: !include announcements.yaml

    """
    with path.open() as fileobj:
        raw_yaml = fileobj.read()

    # we'll subclass yaml.Loader and add a constructor
    class IncludingLoader(yaml.Loader):
        def include(self, node):
            included_path = path.parent / self.construct_scalar(node)
            with included_path.open() as fileobj:
                return yaml.load(fileobj, IncludingLoader)

    IncludingLoader.add_constructor("!include", IncludingLoader.include)

    return yaml.load(raw_yaml, Loader=IncludingLoader)
