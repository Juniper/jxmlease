Installation
============

Requirements
------------

* Python 2.6 or greater (Python 3.x is supported)
* ``pip`` the installation tool for the Python Package Index (PyPI)

Prerequisites
-------------

jxmlease requires an implementation of the :py:class:`ElementTree` API.
Python (beginning in version 2.5) includes an implementation in the
`standard library`_ which satisfies this prerequisite.

.. _standard library: https://docs.python.org/2/library/xml.etree.elementtree.html

While not a pre-requisite, jxmlease will use some of the advanced functionality
provided by the `lxml`_ module, if it is installed.

.. _lxml: http://lxml.de/

Of particular note is that :py:mod:`lxml` will maintain the original namespace
identifiers when you use jxmlease to iterate over an :py:mod:`lxml`
:py:class:`ElementTree` data structure.

The standard library's :py:class:`ElementTree` data structures do not maintain
the original namespace identifiers. See the “Namespace Identifiers” section of
:py:class:`jxmlease.EtreeParser` for more details on this restriction. *Note:*
This is only applicable when using jxmlease to parse ElementTree data
structures. This is not applicable when using jxmlease to parse text.

See `lxml installation`_ for details on installing lxml.

.. _lxml installation: http://lxml.de/installation.html

Installing the latest released version of jxmlease
--------------------------------------------------

Simply execute::

    pip install jxmlease

Installing the latest development version of the jxmlease master branch
-----------------------------------------------------------------------

Execute::

    pip install git+https://github.com/Juniper/jxmlease.git

(*Note* ``git`` must be installed).

Installing a specific version, branch, tag, etc.
------------------------------------------------

Execute::

    pip install git+https://github.com/Juniper/jxmlease.git@<branch,tag,commit>

(*Note* ``git`` must be installed).


Upgrading
---------

Upgrading has the same requirements as installation. Simply add the ``-U``
(upgrade) option to the ``pip`` command::

    pip install -U jxmlease

