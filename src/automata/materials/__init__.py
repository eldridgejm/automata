"""This module provides tools for finding, building, and exporting course materials.

This module may be useful to you if you want to work with your course materials in
a programmatic way (perhaps even without using `automata` to build your course website).
Beyond implementing a static site generator, `automata` establishes a
convention for annotating course materials that can be leveraged to build other
tools. This module provides the core functionality of `automata`, but it can
also be useful as a library for other applications.

The functionality in this module is rather low-level. If you are simply looking for a
way to invoke `automata` from a Python script, you might be more interested in the
higher-level functions in the :mod:`automata.api` module.

**Functions**

.. autosummary::

   read_collection_file
   read_publication_file
   discover
   build_node
   export_node
   filter_nodes
   serialize
   deserialize

**Node Types**

.. autosummary::

   types.Artifact
   types.UnbuiltArtifact
   types.BuiltArtifact
   types.ExportedArtifact
   types.Publication
   types.Collection

**Other Types**

.. autosummary::

   types.PublicationSchema
   types.DateContext

Functions
---------

.. autofunction:: read_collection_file
.. autofunction:: read_publication_file
.. autofunction:: discover
.. autofunction:: build_node
.. autofunction:: export_node
.. autofunction:: filter_nodes
.. autofunction:: serialize
.. autofunction:: deserialize

:mod:`automata.materials.types`
-------------------------------

.. automodule:: automata.materials.types

:mod:`automata.materials.exceptions`
------------------------------------

.. automodule:: automata.materials.exceptions

"""

from . import types, exceptions
from ._read_collection_file import read_collection_file
from ._read_publication_file import read_publication_file
from ._discover import *
from ._build_node import *
from ._export_node import *
from ._filter import *
from ._serialize import *
