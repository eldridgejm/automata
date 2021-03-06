"""
publish
=======

A tool to build and publish certain artifacts at certain times.

`publish` was desgined specifically for the automatic publication of course
materials, such as homeworks, lecture slides, etc.


Terminology
-----------

An **artifact** is a file -- usually one that is generated by some build process.

A **publication** is a coherent group of one or more artifacts and their metadata.

A **collection** is a group of publications which all satisfy the same **schema**.

A **schema** is a set of constraints on a publication's artifacts and metadata.

This establishes a **collection -> publication -> artifact hierarchy**: each
artifact belongs to exactly one publication, and each publication belongs to
exactly one collection.

An example of such a hierarchy is the following: all homeworks in a course form
a collection. Each publication within the collection is an individual
homework. Each publication may have several artifacts, such as the PDF of the
problem set, the PDF of the solutions, and a .zip containing the homework's
data.

An artifact may have a **release time**, before which it will not be built or published.
Likewise, entire publications can have release times, too.

Discovering, Building, and Publishing
-------------------------------------

When run as a script, this package follows a three step process of discovering,
building, and publishing artifacts. 

In the **discovery** step, the script constructs a collection -> publication ->
artifact hierarchy by recursively searching an input directory for artifacts.

In the **build** step, the script builds every artifact whose release time has passed.

In the **publish** step, the script copies every released artifact to an output
directory. 


Discovery
~~~~~~~~~

In the discovery step, the **input directory** is recursively searched for collections,
publications, and artifacts.

A collection is defined by creating a file named ``collections.yaml`` in a directory.
The contents of the file describe the artifacts and metadata that are required
of each of the publications within the collection. For instance: 

.. code-block:: yaml

    # <input_directory>/homeworks/collection.yaml

    schema:
        required_artifacts:
            - homework.pdf
            - solution.pdf

        optional_artifacts:
            - template.zip

        metadata_schema:
            name: 
                type: string
            due:
                type: datetime
            released:
                type: date

The file above specifies that publications must have ``homework.pdf`` and
``solution.pdf`` artifacts, and may or may not have a ``template.zip``
artifact. The publications must also have *name*, *due*, and *released* fields
in their metadata with the listed types. The metadata specification is given in a form
recognizable by the *cerberus* Python package.


A publication and its artifacts are defined by creating a ``publish.yaml`` file
in the directory containing the publication. For instance, the file below
describes how and when to build two artifacts named ``homework.pdf`` and ``solution.pdf``,
along with metadata:

.. code-block:: yaml

    # <input_directory>/homeworks/01-intro/publish.yaml

    metadata:
        name: Homework 01
        due: 2020-09-04 23:59:00
        released: 2020-09-01

    artifacts:
        homework.pdf:
            recipe: make homework
        solution.pdf:
            file: ./build/solution.pdf
            recipe: make solution
            release_time: 1 day after metadata.due
            ready: false
            missing_ok: false

The ``file`` field tells *publish* where the file will appear when the recipe
is run.  is omitted, its value is assumed to be the artifact's key -- for
instance, ``homework.pdf``'s ``file`` field is simply ``homework.pdf``.

The ``release_time`` field provides the artifact's release time. It can be a
specific datetime in ISO 8601 format, like ``2020-09-18 17:00:00``, or a
*relative* date of the form "<number> (hour|day)[s]{0,1} (before|after)
metadata.<field>", in which case the date will be calculated relative to the
metadata field.  The field it refers to must be a datetime.

The ``ready`` field is a manual override which prevents the artifact from
being built and published before it is ready. If not provided, the artifact
is assumed to be ready.

THe ``missing_ok`` field is a boolean which, if ``false``, causes an error to
be raised if the artifact's file is missing after the build. This is the
default behavior.  If set to ``true``, no error is raised. This can be useful
when the artifact file is manually placed in the directory and it is
undesirable to repeatedly edit ``publish.yaml`` to add the artifact.

Publications may also have ``release_time`` and ``ready`` attributes. If these
are provided they will take precedence over the attributes of an individual
artifact in the publication. The release time of the publication can be used
to control when its metadata becomes available -- before the release time,
the publication in effect does not exist.

The file hierarchy determines which publications belong to which collections.
If a publication file is placed in a directory that is a descendent of a
directory containing a collection file, the publication will be placed in that
collection and its contents will be validated against the collection's schema.
Publications which are not under a directory containing a ``collection.yaml``
are placed into a "default" collection with no schema. They may contain any
number of artifacts and metadata keys.

Collections, publications, and artifacts all have **keys** which locate them
within the hierarchy. These keys are inferred from their position in the
filesystem. For example, a collection file placed at
``<input_directory>/homeworks/collection.yaml`` will create a collection keyed
"homeworks". A publication within the collection at
``<input_directory>/homeworks/01-intro/publish.yaml`` will be keyed "01-intro".
The keys of the artifacts are simply their keys within the ``publish.yaml``
file.


Building
~~~~~~~~

Once all collections, publications, and artifacts have been discovered, the
script moves to the build phase.

Artifacts are built by running the command given in the artifact's `recipe`
field within the directory containing the artifact's ``publication.yaml`` file.
Different artifacts should have "orthogonal" build processes so that the order
in which the artifacts are built is inconsequential.

If an error occurs during any build the entire process is halted and the
program returns without continuing on to the publish phase. An error is
considered to occur if the build process returns a nonzero error code, or if
the artifact file is missing after the recipe is run.


Publishing
~~~~~~~~~~

In the publish phase, all published artifacts -- that is, those which are ready
and whose release date has passed -- are copied to an **output directory**.
Additionally, a JSON file containing information about the collection ->
publication -> artifact hierarchy is placed at the root of the output
directory.

Artifacts are copied to a location within the output directory according to the
following "formula":

.. code-block:: text

    <output_directory>/<collection_key>/<publication_key>/<artifact_key>

For instance, an artifact keyed ``homework.pdf`` in the ``01-intro`` publication
of the ``homeworks`` collection will be copied to::

    <output_directory>/homeworks/01-intro/homework.pdf

An artifact which has not been released will not be copied, even if the
artifact file exists.

*publish* will create a JSON file named ``<output_directory>/published.json``.
This file contains nested dictionaries describing the structure of the
collection -> publication -> artifact hierarchy. 

For example, the below code will load the JSON file and print the path of a published
artifact relative to the output directory, as well as a publication's metadata.

.. code-block:: python

    >>> import json
    >>> d = json.load(open('published.json'))
    >>> d['collections']['homeworks']['publications']['01-intro']['artifacts']['homework.pdf']['path']
    homeworks/01-intro/homework.pdf
    >>> d['collections']['homeworks']['publications']['01-intro']['metadata']['due']
    2020-09-10 23:59:00

Only those publications and artifacts which have been published appear in the
JSON file. In particular, if an artifact has not reached its release time, it
will be missing from the JSON representation entirely.

"""

from .types import *
from .exceptions import *
from ._discover import *
from ._build import *
from ._publish import *
from ._filter import *
from ._serialize import *

__version__ = (0, 2, 1)
