#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides the XMLCDATANode class."""
from __future__ import absolute_import

from xml.sax.xmlreader import AttributesImpl
from . import _node_refs, pprint, _unicode
from . import _XMLDictPlaceholder
from ._basenode import _common_docstring, _docstring_fixup, XMLNodeBase

__all__ = ['XMLCDATANode']

XMLDictNode = _XMLDictPlaceholder
def _resolve_references_once():
    """Internal function to resolve late references.

    There are circular references between the three node types. If we try
    to import all of the references into each module at parse time, the
    parser (rightly) complains about an infinite loop. This function "solves"
    that by doing a one-time load of the symbols the first time an
    instance of the class is changed. The function then replaces its own
    name in the module symbol table with a lambda function to turn this
    into a no-op.
    """
    # pylint: disable=global-statement
    # pylint: disable=invalid-name
    global XMLDictNode
    global _resolve_references
    XMLDictNode = _node_refs['XMLDictNode']
    _resolve_references = lambda: None

_resolve_references = _resolve_references_once


class XMLCDATANode(XMLNodeBase, _unicode):
    """(docstring to be replaced by __doc__)"""
    __doc__ = _common_docstring("XMLCDATANode")
    def __new__(cls, *args, **kwargs):
        _resolve_references()
        return super(XMLCDATANode, cls).__new__(cls, *args, **kwargs)
    def __init__(self, *args, **kwargs): # pylint: disable=unused-argument
        self.text = self
        super(XMLCDATANode, self).__init__(**kwargs)

    def add_node(self, tag, key=None, *args, **kwargs):
        self._check_replacement()
        # Hmmm... We were a CDATA node, but we need to become a
        # dictionary so we can have members.
        newnode = XMLDictNode(tag=self.tag, key=self.key, parent=self.parent,
                              text=_unicode(self), xml_attrs=self.xml_attrs)
        # Now, add the new node as a child of our replacement.
        rv = newnode.add_node(tag, key, *args, **kwargs)
        # Finally, replace ourselves.
        self._replace_node(newnode)
        return rv

    def set_cdata(self, cdata, return_node=False):
        self._check_replacement()
        newnode = XMLCDATANode(cdata, tag=self.tag, key=self.key,
                               parent=self.parent, xml_attrs=self.xml_attrs)
        self._replace_node(newnode)
        if return_node:
            return newnode

    def append_cdata(self, cdata, return_node=False):
        self._check_replacement()
        return self.set_cdata(_unicode(self) + cdata, return_node)

    def get_cdata(self):
        return _unicode(self)

    def standardize(self, deep=True):
        # There is nothing to do.
        return

    def _emit_handler(self, content_handler, depth, pretty, newl, indent):
        if pretty:
            content_handler.ignorableWhitespace(depth * indent)
        content_handler.startElement(self.tag, AttributesImpl(self.xml_attrs))
        content_handler.characters(self.get_cdata())
        content_handler.endElement(self.tag)
        if pretty and depth > 0:
            content_handler.ignorableWhitespace(newl)

    def prettyprint(self, *args, **kwargs):
        currdepth = kwargs.pop("currdepth", 0)
        newobj = _unicode(self)
        if currdepth == 0:
            pprint(newobj, *args, **kwargs)
        else:
            return newobj

    def _find_nodes_with_tag(self, tag, recursive=True, top_level=False):
        if self.tag in tag:
            yield self

    def __str__(self):
        # Purposely skip over the XMLNodeBase class.
        #pylint: disable=bad-super-call
        return super(XMLNodeBase, self).__str__()

_docstring_fixup(XMLCDATANode)
