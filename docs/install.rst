Installation
============

Requirements
------------

* Python 2.6 or greater (Python 3.x is supported)
* ``pip`` the installation tool for the Python Package Index (PyPI)

Prerequisites
-------------

jxmlease requires an implementation of the :py:class:`ElementTree` API.

The preferred :py:class:`ElementTree` implementation is
`lxml`_. See `lxml installation`_ for details on installing lxml.

.. _lxml: http://lxml.de/
.. _lxml installation: http://lxml.de/installation.html

If lxml is not present, jxmlease attempts to use the `cElementTree`_
implementation of the :py:class:`ElementTree` API.

.. _cElementTree: http://effbot.org/zone/celementtree.htm

Finally, if neither lxml or cElementTree are present, jxmlease uses the
:py:class:`ElementTree` implementation available in the
`Python standard library`_.

.. _Python standard library: https://docs.python.org/2/library/xml.etree.elementtree.html

If lxml is not present, the original namespace identifiers on XML attributes
are not maintained. See the "Namespace Identifiers" section of
:py:class:`jxmlease.EtreeParser` for more details on this restriction.

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

