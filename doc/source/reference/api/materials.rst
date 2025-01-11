:mod:`automata.materials` - low-level tools for working with course materials
=============================================================================

.. automodule:: automata.materials

This module may be useful to you if you want to work with your course materials
in a programmatic way (perhaps even without using `automata` to build your
course website). It provides the core functionality of `automata`, but it can
also be useful as a library for third party applications. However, this module
is rather low-level. If you are simply looking for a way to invoke `automata`
from a Python script, you might be more interested in the higher-level
functions in the :mod:`automata.api` module.

**Core Types**

:mod:`automata.materials.types` defines a number of classes for representing course
materials, following the convention described in the tutorial.

.. autosummary::
   :nosignatures:

   types.Artifact
   types.UnbuiltArtifact
   types.BuiltArtifact
   types.ExportedArtifact
   types.Publication
   types.Collection

**Other Types**

These miscellaneous types define the interface for information passed into some
of the core functions below.

.. autosummary::
   :nosignatures:

   types.PublicationSchema
   types.DateContext

**Core Functions**

These functions provide the core functionality of `automata`.

.. module:: automata.materials
.. autosummary::
   :nosignatures:

   read_collection_file
   read_publication_file
   discover
   build
   export
   filter
   serialize
   deserialize

**Callback Interfaces**

Certain core functions, such as :func:`build`, accept callbacks. The below
classes define the interface for these callbacks, and can be subclassed and
their methods overridden to provide custom behavior.

.. autosummary::
   :nosignatures:

   BuildCallbacks

Core types for representing course materials
--------------------------------------------

.. module:: automata.materials.types

As described in :ref:`convention`, `automata` establishes a convention for
organizing and annotating course materials. In this convention, individual
files to be published are called *artifacts*. A group of related artifacts
(such as the files for a single homework) are called a *publication*. A
collection of publications is called a *collection*. Collections, publications,
and artifacts are all defined in the filesystem using YAML files placed alongside
the course materials they describe.

The :mod:`automata.materials.types` module defines classes for representing
collections, publications, and artifacts in Python. Because `automata`'s
convention is *hierarchical* (with artifacts contained in publications, and
publications contained in collections), a collection of course materials can be
represented as a tree of Python objects, with each node in the tree
representing a collection, publication, or artifact. Therefore, the classes
below often adopt the language of trees, with "children" referring to the nodes
directly under a given node in the hierarchy. For instance, the children of a
publication are the artifacts it contains.

At the bottom of the hierarchy (the leaves of the tree) are the individual artifacts.
Artifacts are files that are to be published, but they may not be static -- instead,
they could be the result of a build process. A classic example of this is a PDF
of homework problems that is generated from a LaTeX source file.

There are three main stages in the lifecycle of an artifact:

- **Unbuilt**: The artifact has been discovered, but has not yet been built.
- **Built**: The artifact has been built.
- **Exported**: The artifact has been built and exported to the output directory.

These three stages are represented by three different classes:

.. autoclass:: UnbuiltArtifact
.. autoclass:: BuiltArtifact
.. autoclass:: ExportedArtifact

All three of these inherit from a common base class, :class:`Artifact`:

.. autoclass:: Artifact

Artifacts are the "leaf nodes" of the course material hierarchy, and do not
contain any children. On the other hand, publications are "internal nodes", and
they do potentially contain artifacts as their children. They are represented
by the :class:`Publication` class:

.. autoclass:: Publication
   :members: _asdict, _deep_asdict, _deep_fromdict, _children, _replace_children

Publications are contained within collections, which are also represented by the
:class:`Collection` class:

.. autoclass:: Collection
   :members: _asdict, _deep_asdict, _deep_fromdict, _children, _replace_children

Collections may define a *publication schema*, which is a set of rules that
determine the properties that a publication within should have. For example, a
publication schema for a collection of homeworks might require that every
:class:`Publication` within have a `due_date` property in its metadata, as well
as ``problems.pdf`` and a ``solutions.pdf`` artifacts. This publication schema should
be an instance of the :class:`PublicationSchema` class:

.. autoclass:: PublicationSchema

The set of all collections in a course is called the *universe*; it is the root
of the course materials hierarchy. In `automata`, the universe is represented by
a :class:`Universe` object:

.. autoclass:: Universe
   :members: _asdict, _deep_asdict, _deep_fromdict, _children, _replace_children

.. module:: automata.materials

Finding, filtering, building and exporting materials
----------------------------------------------------

Reading configuration files
---------------------------

In most cases, you'll want to use :func:`discover` to recursively find all the
course materials in a directory. However, if you want to read a single
collection or publication file, you can use the following functions:

.. autofunction:: read_collection_file
.. autofunction:: read_publication_file

Serialization and deserialization
---------------------------------

Exception types
---------------


:mod:`automata.materials`
-------------------------

.. autofunction:: read_collection_file
.. autofunction:: read_publication_file
.. autofunction:: discover
.. autofunction:: build
.. autoclass:: BuildCallbacks
    :members:
.. autofunction:: export
.. autofunction:: filter
.. autofunction:: serialize
.. autofunction:: deserialize



Types for schemas and dates
---------------------------

.. autoclass:: PublicationSchema
.. autoclass:: DateContext


:mod:`automata.materials.exceptions`
------------------------------------

.. automodule:: automata.materials.exceptions

