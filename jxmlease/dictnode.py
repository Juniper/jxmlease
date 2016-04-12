#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides the XMLDictNode class."""
from __future__ import absolute_import

from xml.sax.xmlreader import AttributesImpl
from copy import copy
from . import _node_refs, OrderedDict, pprint, _unicode
from . import _XMLCDATAPlaceholder, _XMLListPlaceholder
from ._basenode import _common_docstring, _docstring_fixup, XMLNodeBase

__all__ = ['XMLDictNode']

XMLCDATANode = _XMLCDATAPlaceholder
XMLListNode = _XMLListPlaceholder
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
    global XMLCDATANode
    global XMLListNode
    global _resolve_references
    XMLCDATANode = _node_refs['XMLCDATANode']
    XMLListNode = _node_refs['XMLListNode']
    _resolve_references = lambda: None

_resolve_references = _resolve_references_once


class XMLDictNode(XMLNodeBase, OrderedDict):
    """(docstring to be replaced by __doc__)"""
    __doc__ = _common_docstring("XMLDictNode")
    def __new__(cls, *args, **kwargs):
        _resolve_references()
        return super(XMLDictNode, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        super(XMLDictNode, self).__init__(*args, **kwargs)
        self.__const_class_name__ = self.__class__.__name__
        self._ignore_level = False

    def add_node(self, tag, key=None, text=_unicode(), new_node=None,
                 update=True, **kwargs):
        self._check_replacement()
        if new_node is None:
            # By default, we create a CDATA node.
            new_node = XMLCDATANode(text, tag=tag, **kwargs)

            if key:
                if update:
                    new_node.key = copy(key)
            else:
                key = tag
        else:
            if not isinstance(new_node, XMLNodeBase):
                raise TypeError("'new_node' argument must be a subclass of "
                                "XMLNodeBase, not '%s'"
                                % (type(new_node).__name__))
            if key:
                if update:
                    new_node.key = (key)
            elif new_node.key:
                key = new_node.key
            else:
                key = tag
            if update:
                new_node.tag = tag

        # Let's see if we already have an entry with this key. If so,
        # it needs to be a list.
        if key in self:
            # Make it a list, if not already.
            if not isinstance(self[key], XMLListNode):
                old_node = self[key]
                self[key] = XMLListNode([old_node], tag=tag, key=key,
                                        parent=self, convert=False)
                if update:
                    old_node.parent = self[key]
                del old_node

            # Add the new node to the list.
            if update:
                new_node.parent = self[key]
            self[key].append(new_node)
        else:
            # Add to the dictionary.
            if update:
                new_node.parent = self
            self[key] = new_node
        return new_node

    def standardize(self, deep=True):
        for k in self:
            node = self[k]
            if not isinstance(node, XMLNodeBase):
                # Set the key and parent. Assume the tag is the same
                # as the key.
                # If we were told to do a deep conversion, then convert
                # the child; otherwise, don't.
                kwargs = dict(convert=deep, deep=deep, tag=k, key=k,
                              parent=self)

                # Convert dicts to XMLDictNodes.
                # Convert lists to XMLListNodes.
                # Convert everything else to an XMLCDATANode with
                # a best guess for the correct string value.
                if isinstance(node, (OrderedDict, dict)):
                    self[k] = XMLDictNode(node, **kwargs)
                elif isinstance(node, list):
                    self[k] = XMLListNode(node, **kwargs)
                else:
                    if node is None:
                        node = _unicode('')
                    elif not isinstance(node, (_unicode, str)):
                        node = _unicode(node)
                    self[k] = XMLCDATANode(node, **kwargs)

            else:
                # Update the internal book-keeping entries that might
                # need to be changed.
                self._check_replacement()
                if not node.tag:
                    node.tag = k
                node.key = k
                node.parent = self
                if deep:
                    node.standardize(deep=deep)

    def _emit_handler(self, content_handler, depth, pretty, newl, indent):
        # Special case: If tag is None and depth is 0, then we might be the
        # root container, which is tagless.
        # Special case: If self._ignore_level is True, then we just want to
        # work on the children.
        if (self.tag is None and depth == 0) or self._ignore_level:
            first_element = True
            for k in self:
                if pretty and depth == 0 and not first_element:
                    content_handler.ignorableWhitespace(newl)
                self[k]._emit_handler(content_handler, depth, pretty, newl,
                                      indent)
                first_element = False
            return
        if pretty:
            content_handler.ignorableWhitespace(depth * indent)
        content_handler.startElement(self.tag, AttributesImpl(self.xml_attrs))
        if pretty and len(self) > 0:
            content_handler.ignorableWhitespace(newl)
        for k in self:
            self[k]._emit_handler(content_handler, depth+1, pretty, newl,
                                  indent)
        content_handler.characters(_unicode.strip(self.get_cdata()))
        if pretty and len(self) > 0:
            content_handler.ignorableWhitespace(depth * indent)
        content_handler.endElement(self.tag)
        if pretty and depth > 0:
            content_handler.ignorableWhitespace(newl)

    def prettyprint(self, *args, **kwargs):
        currdepth = kwargs.pop("currdepth", 0)
        depth = kwargs.get("depth", None)
        if depth is not None and depth < currdepth:
            return {}
        # Construct a new item, recursively.
        newdict = dict()
        for (k, v) in self.items():
            if hasattr(v, "prettyprint"):
                newdict[k] = v.prettyprint(*args, currdepth=currdepth+1,
                                           **kwargs)
            else:
                newdict[k] = v
        if currdepth == 0:
            pprint(newdict, *args, **kwargs)
        else:
            return newdict

    def _find_nodes_with_tag(self, tag, recursive=True, top_level=False):
        # Special case: If tag is None and top_level is True, then
        # we might be the root container, which is tagless.
        # Special case: If self._ignore_level is True, then we just
        # want to work on the children.
        pass_through = self._ignore_level or (self.tag is None and top_level)
        if self.tag in tag and not pass_through:
            matched = True
            yield self
        else:
            matched = False
        if recursive or (top_level and not matched):
            for node in self.values():
                kwargs = {'recursive': recursive}
                # Pass through the top_level arg, if appropriate.
                if pass_through:
                    kwargs['top_level'] = top_level
                for item in node._find_nodes_with_tag(tag, **kwargs):
                    yield item

_docstring_fixup(XMLDictNode)
