#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""jxmlease converts between XML and intelligent Python data structures.

For a quick start, you can use the :py:meth:`parse` method to convert a
block of XML to a Python data structure. This example parses ``xml`` and uses
the :py:meth:`XMLDictNode.prettyprint` method to display the result::

    >>> xml = "<a><b><c>foo</c><c>bar</c></b></a>"
    >>> parse(xml).prettyprint()
    {u'a': {u'b': {u'c': [u'foo', u'bar']}}}

Or, you can use the :py:class:`XMLDictNode` class to convert a Python data
structure to an intelligent XML data structure. The following example creates an
:py:obj:`XMLDictNode` object from ``data_structure`` and outputs the resulting
XML using the :py:meth:`XMLNodeBase.emit_xml` method::

    >>> data_structure = {u'a': {u'b': {u'c': [u'foo', u'bar']}}}
    >>> print XMLDictNode(data_structure).emit_xml()
    <?xml version="1.0" encoding="utf-8"?>
    <a>
        <b>
            <c>foo</c>
            <c>bar</c>
        </b>
    </a>

"""

from __future__ import absolute_import

try:  # pragma no cover
    from cStringIO import StringIO
except ImportError:  # pragma no cover
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO
try:  # pragma no cover
    from collections import OrderedDict as _OrderedDict
except ImportError:  # pragma no cover
    try:
        from ordereddict import OrderedDict as _OrderedDict
    except ImportError:
        _OrderedDict = dict
try: # pragma no cover
    from pprint import pprint
except ImportError: # pragma no cover
    def pprint(obj, *args, **kwargs):
        """Internal backup substitute for the pprint library function."""
        if len(args) > 0:
            stream = args[0]
        else:
            stream = kwargs.get("stream", None)
        if stream is not None:
            stream.write("%r\n" % obj)
        else:
            print("%r" % obj) # pylint: disable=superfluous-parens

try:  # pragma no cover
    _unicode = unicode # pylint: disable=unicode-builtin
except NameError:  # pragma no cover
    _unicode = str

# While doing processing for a generator, process XML text 1KB at a
# time.
# Note: While parsing_increment is only used by one module, it makes sense
# to keep it here, since someone might want to override it, and we expect to
# only publicly expose the package (and not individual modules).
parsing_increment = 1024

# A user can use this to set their custom defaults for parsers.
parser_defaults = {}


__author__ = 'Juniper Networks'
__version__ = '1.0.1dev1'
__license__ = 'MIT'
__all__ = [
    'XMLDictNode', 'XMLListNode', 'XMLCDATANode', 'Parser', 'parse',
    'EtreeParser', 'parse_etree'
]

class OrderedDict(_OrderedDict):
    """Standard OrderedDict class, with a small local modification.

    This module uses the OrderedDict class to maintain ordering
    of the input data.
    """
    def __repr__(self, _repr_running=None):
        if _repr_running is None:
            _repr_running = {}
        temp = self.__class__.__name__
        try:
            # The OrderedDict.__repr__ function takes an
            # extra argument. It also prints the name of
            # the main object's class. This logic temporarily
            # resets the class name so this appears to be
            # what it (fundamentally) is: an OrderedDict
            # object. (For this reason, there is also extra
            # logic to make the XMLDictNode __repr__ function
            # work correctly.)
            self.__class__.__name__ = _OrderedDict.__name__
            rv = _OrderedDict.__repr__(self, _repr_running)
        except TypeError:
            # Looks like the class didn't understand the second
            # argument. Retry with just one argument.
            rv = _OrderedDict.__repr__(self)
        finally:
            self.__class__.__name__ = temp
        return rv

# Handle the node classes and import them first. This will ensure the
# references are fully resolved prior to importing other modules that
# may need them.

class _XMLCDATAPlaceholder(object): # pragma no cover
    """A placeholder class for XMLCDATANode.

       This class produces an error if called, but tries to give enough
       information about the underlying class to pylint to make its
       checks meaningful.
    """
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError("Class not properly inherited")
    def __init__(self, *args, **kwargs):
        super(_XMLCDATAPlaceholder, self).__init__(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_node_refs['XMLCDATANode'], name)

class _XMLDictPlaceholder(object): # pragma no cover
    """A placeholder class for XMLDictNode.

       This class produces an error if called, but tries to give enough
       information about the underlying class to pylint to make its
       checks meaningful.
    """
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError("Class not properly inherited")
    def __init__(self, *args, **kwargs):
        super(_XMLDictPlaceholder, self).__init__(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_node_refs['XMLDictNode'], name)

class _XMLListPlaceholder(object): # pragma no cover
    """A placeholder class for XMLLstNode.

       This class produces an error if called, but tries to give enough
       information about the underlying class to pylint to make its
       checks meaningful.
    """
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError("Class not properly inherited")
    def __init__(self, *args, **kwargs):
        super(_XMLListPlaceholder, self).__init__(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_node_refs['XMLListNode'], name)

# This is a silly little hack to get around the fact that we have circular
# references in the three different node type files.
_node_refs = {'XMLListNode': None, 'XMLCDATANode': None, 'XMLDictNode': None}

# These imports are purposely at the end because they depend on things that
# are defined above this line.
# pylint: disable=wrong-import-position

# Import the base node.
from ._basenode import XMLNodeBase

# Import the node classes, updating the references in the dictionary.
from .listnode import XMLListNode
_node_refs['XMLListNode'] = XMLListNode
from .cdatanode import XMLCDATANode
_node_refs['XMLCDATANode'] = XMLCDATANode
from .dictnode import XMLDictNode
_node_refs['XMLDictNode'] = XMLDictNode

# Now, import anything else we want.
from .xmlparser import Parser, parse
from .etreeparser import EtreeParser, parse_etree

def emit_xml(obj, *args, **kwargs):
    """Translate a Python dictionary or list to XML output.

    This method internally creates an :py:class:`XMLDictNode` or
    :py:class:`XMLListNode` object, as appropriate, and then calls the
    :py:meth:`emit_xml <XMLNodeBase.emit_xml>` method of that class.

    Any arguments you supply are passed on to the :py:meth:`emit_xml
    <XMLNodeBase.emit_xml>` method of that class. Please see the
    documentation for the class' :py:meth:`emit_xml <XMLNodeBase.emit_xml>`
    method for information on arguments and return values.

    Raises:
        :py:exc:`TypeError`: If the object is not an appropriate type
            to convert to an XML tree.
    """
    if isinstance(obj, (XMLDictNode, dict)):
        parsed_obj = XMLDictNode(obj)
    elif isinstance(obj, (XMLListNode, list, tuple)):
        parsed_obj = XMLListNode(obj)
    else:
        raise TypeError
    return parsed_obj.emit_xml(*args, **kwargs)
