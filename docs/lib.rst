Library API
===========

:mod:`automata.lib.materials`
-----------------------------

.. currentmodule:: automata.lib.materials

**Exceptions**

.. autosummary::

    Error
    ValidationError
    DiscoveryError
    BuildError

**Types**

.. autosummary:: 
    UnbuiltArtifact
    BuiltArtifact
    PublishedArtifact
    Publication
    Collection
    Universe
    Schema

**Functions**

.. autosummary::
    discover
    build
    publish
    deserialize
    filter_nodes
    read_collection_file
    read_publication_file
    serialize


Types
~~~~~

*publish* provides several types for representing collections, publications,
and artifacts.

.. autosummary::

    UnbuiltArtifact
    BuiltArtifact
    PublishedArtifact
    Publication
    Collection
    Universe

There are three artifact types, each used to represent artifacts at different
stages of the discover -> build -> publish process. Each are subclasses of
:class:`typing.NamedTuple`.

.. autoclass:: UnbuiltArtifact

.. autoclass:: BuiltArtifact

.. autoclass:: PublishedArtifact

For convenience, all three of these types inherit from an :class:`Artifact`
base class. This makes it easy to check whether an object is an artifact of
any kind using ``isinstance(x, publish.Artifact)``.

Publications and collections are represented with the :class:`Publication` and
:class:`Collection` types. Furthermore, a set of collections is represented
with the :class:`Universe` type. These three types all inherit from
:class:`typing.NamedTuple`.

.. autoclass:: Publication

.. autoclass:: Collection

.. autoclass:: Universe

These types exist within a hierarchy: A :class:`Universe` contains instances of
:class:`Collection` which contain instances of :class:`Publication` which
contain instances of :class:`Artifact`. :class:`Universe`, :class:`Collection`,
and :class:`Publication` are *internal nodes* of the hierarchy, while
:class:`Artifact` instances are leaf nodes.

Internal node types share several methods and attributes, almost as if they
were inherited from a parent "InternalNode" base class (which doesn't exist in
actuality):

.. class:: InternalNode

    .. method:: _deep_asdict(self)

        Recursively compute a dictionary representation of the object.

    .. method:: _replace_children(self, new_children)

        Replace the node's children with a new set of children.

    .. attribute:: _children

        The node's children.

For instance, the ``._children`` attribute of a :class:`Collection` returns a
dictionary mapping publication keys to :class:`Publication` instances.

Schemas and Validation
~~~~~~~~~~~~~~~~~~~~~~

Schemas used to validate publications are represented with the :class:`PublicationSchema` class.

.. autoclass:: PublicationSchema


Discovery
~~~~~~~~~

The discovery of collections, publications, and artifacts is performed using the
:func:`discover` function.

.. autofunction:: discover

Callbacks are invoked at certain points during the discovery. To provide
callbacks to the function, subclass and override the desired members of the
below class, and provide an instance to :func:`discover`.

.. autoclass:: DiscoverCallbacks
    :members:

Two low-level functions :func:`read_collection_file` and
:func:`read_publication_file` are also available for reading individual
collection and publication files. Note that they are not recursive: reading a
collection file does not load any publications into the collection. Most of the
time, you probably want :func:`discover`.

.. autofunction:: read_collection_file
.. autofunction:: read_publication_file


Build
~~~~~

The building of whole collections, publications, and artifacts is performed
with the :func:`build` function.

.. autofunction:: build

Callbacks are invoked at certain points during the build. To provide callbacks
to the function, subclass and override the desired members of the below class,
and provide an instance to :func:`build`.

.. autoclass:: BuildCallbacks
    :members:

Publish
~~~~~~~

.. autofunction:: publish

Callbacks are invoked at certain points during the publication. To provide
callbacks to the function, subclass and override the desired members of the
below class, and provide an instance to :func:`publish`.

.. autoclass:: PublishCallbacks
    :members:


Serialization
~~~~~~~~~~~~~

Two functions are provided for serializing and deserializing objects to and
from JSON.

.. autofunction:: serialize
.. autofunction:: deserialize


Filtering
~~~~~~~~~

Collections, publications, and artifacts can be removed using
:func:`filter_nodes`.


.. autofunction:: filter_nodes


:mod:`automata.lib.coursepage`
------------------------------
