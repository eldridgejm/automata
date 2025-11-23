:mod:`automata.lib` - a library for working with course materials
=======================================================================

.. automodule:: automata.lib

This module may be useful to you if you want to work with your course materials
in a programmatic way (perhaps even without using `automata` to build your
course website). It provides the core functionality of `automata`, but it can
also be used as a library within third party applications. However, this module
is rather low-level. If you are simply looking for a way to invoke `automata`
from a Python script, you might be more interested in the higher-level
functions in the :mod:`automata.api` module.

The functions and classes in this module are as follows:

**Core Types**

:mod:`automata.lib` defines a number of classes for representing course
materials, following the convention described in the tutorial of grouping them into
collections, publications, and artifacts.

.. autosummary::
   :nosignatures:

   UnbuiltArtifact
   BuiltArtifact
   ExportedArtifact
   Artifact
   Publication
   PublicationSchema
   Collection

**Core Functions**

These functions provide the core functionality of `automata`.

.. module:: automata.lib
.. autosummary::
   :nosignatures:

   discover
   filter
   build
   export
   serialize
   deserialize
   read_collection_file
   read_publication_file

**Callback Interfaces**

The four core functions of :func:`discover`, :func:`filter`, :func:`build`, and
:func:`export` accept callbacks which are primarily used to provide feedback to
the user about the progress of these operations. The below classes define the
interface for these callbacks, and can be subclassed and their methods
overridden to provide custom behavior.

.. autosummary::
   :nosignatures:

   DiscoverCallbacks
   FilterCallbacks
   BuildCallbacks
   ExportCallbacks


Core types for representing course materials
--------------------------------------------

As described in :ref:`convention`, `automata` establishes a convention for
organizing and annotating course materials. In this convention, individual
files (or directories) to be published are called *artifacts*. A group of
related artifacts (such as the files for a single homework) are called a
*publication*. A collection of publications is called a *collection*.
Collections, publications, and artifacts are all defined in the filesystem
using YAML files placed alongside the course materials they describe.

The :mod:`automata.lib` module defines classes for representing
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

.. module:: automata.lib

Discovering, filtering, building and exporting materials
--------------------------------------------------------

The four core functions in `automata.lib` are :func:`discover`,
:func:`filter`, :func:`build`, and :func:`export`. These functions allow you to
read course materials from the filesystem, filter them based on various criteria,
build them (i.e., run any necessary build processes to generate artifacts), and
export them to a directory.

.. autofunction:: discover
.. autofunction:: filter
.. autofunction:: build
.. autofunction:: export

It is common to use these functions within user-facing code, such as a command
line interface. The functions themselves do not print any output, but they do
accept callbacks that can be used to provide feedback to the user. These callbacks
can be provided by subclassing the appropriate callback interface below:

.. autoclass:: DiscoverCallbacks
    :members:

.. autoclass:: FilterCallbacks
   :members:

.. autoclass:: BuildCallbacks
    :members:

.. autoclass:: ExportCallbacks
    :members:

Serialization and deserialization
---------------------------------

The node types (collections, publications, and artifacts) described above are primarily
used for representing course materials in memory. However, you may want to save these
objects to disk, or read them from disk. The :func:`serialize` and :func:`deserialize`
functions provide a way to do this.

.. autofunction:: serialize
.. autofunction:: deserialize

Reading configuration files
---------------------------

In most cases, you'll want to use :func:`discover` to recursively find all the
course materials in a directory, resulting in a :class:`Universe` instance that
(through its descendants) contains all information about the course materials.
However, if you want to read a single collection or publication file, you can
use the following functions:

.. autofunction:: read_collection_file
.. autofunction:: read_publication_file


Exception types
---------------

Because :mod:`automata.lib` is designed to be used as a library, it
provides a number of exception types that can be used to isolate and handle
errors that originate from within. These are all contained in the
:mod:`automata.lib.exceptions` module.

.. module:: automata.lib.exceptions

.. autoclass:: Error
.. autoclass:: ValidationError
.. autoclass:: DiscoveryError
.. autoclass:: BuildError


.. module:: automata.lib.exceptions
