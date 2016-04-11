#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides the XMLListNode class."""
from __future__ import absolute_import

from . import _node_refs, OrderedDict, pprint, _unicode
from . import _XMLCDATAPlaceholder, _XMLDictPlaceholder
from ._basenode import _common_docstring, _docstring_fixup, XMLNodeBase

__all__ = ['XMLListNode']

XMLCDATANode = _XMLCDATAPlaceholder
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
    global XMLCDATANode
    global XMLDictNode
    global _resolve_references
    XMLCDATANode = _node_refs['XMLCDATANode']
    XMLDictNode = _node_refs['XMLDictNode']
    _resolve_references = lambda: None

_resolve_references = _resolve_references_once

def _get_dict_value_iter(arg, descr="node"):
    if isinstance(arg, XMLDictNode):
        try:
            # Python 2
            return arg.itervalues()
        except AttributeError:
            # Python 3
            return arg.values()
    elif isinstance(arg, XMLCDATANode):
        return [arg]
    else:
        raise TypeError("Unexpected type %s for %s" % (str(type(arg)), descr))

class XMLListNode(XMLNodeBase, list):
    """(docstring to be replaced by __doc__)"""
    __doc__ = _common_docstring("XMLListNode")
    def __new__(cls, *args, **kwargs):
        _resolve_references()
        return super(XMLListNode, cls).__new__(cls, *args, **kwargs)

    def add_node(self, *args, **kwargs): # pylint: disable=unused-argument
        """Add an XML node to the XML tree.

        You should **NOT** call this method on an XMLListNode. Instead,
        call the add_node method on an :py:class:`XMLCDATANode` or an
        :py:class:`XMLDictNode`.

        Raises:
            :py:exc:`AttributeError`: If the node is out of date.
                (See :py:class:`get_current_node`.)
            :py:exc:`TypeError`: If called on an :py:class:`XMLListNode`.
        """
        self._check_replacement()
        raise TypeError("Unable to add a child node to a list. Either add the "
                        "node to the list's parent or one of the list members.")

    def list(self, in_place=False):
        return self

    def dict(self, attrs=None, tags=None, func=None, in_place=False,
             promote=False):
        if attrs is None:
            attrs = []
        if tags is None:
            tags = []
        class KeyBuilder(object):
            """Given a key and a series of key/value pairs, return
               the value of the key, if found.

               Note that the key on which to match can be a list or tuple,
               in which case the key is only considered to match if every
               key in the list/tuple is a key in the series of key/value
               pairs.

               Args:
                   matches (an item, or a list/tuple): The key (or
                       multi-part key) on which the class should match.
            """
            def __init__(self, matches):
                if isinstance(matches, (tuple, list)):
                    self.key_list = list(matches)
                    self.tuple = True
                else:
                    self.key_list = [matches]
                    self.tuple = False
                self.value_list = [None for _ in range(0, len(self.key_list))]

            def eval_key(self, key_list, val):
                """Evaluate whether a key/value pair completes a match.

                   Args:
                       key_list (list): One or more keys.
                       val (item): The value associated with all of the
                           keys in the list.

                   Returns:
                       The value associated with the key. If the key
                       is a multi-part key (which occurs when the class
                       instance was initialized with a list or tuple),
                       the result will be a tuple of values ordered in
                       the same order as the keys appeared in the
                       multi-part key.

                       If no match is found, the method returns None.
                """
                found_match = False
                for k in key_list:
                    for idx in range(0, len(self.key_list)):
                        if k == self.key_list[idx]:
                            self.value_list[idx] = val
                            self.key_list[idx] = None
                            found_match = True
                            break
                    if found_match:
                        break
                if None in self.value_list:
                    return None
                if self.tuple:
                    return tuple(self.value_list)
                else:
                    return self.value_list[0]

        newnode = None
        if in_place:
            self._check_replacement()
            if promote:
                parent = self.parent
                while not isinstance(parent, XMLDictNode):
                    parent = parent.parent
                if not parent:
                    raise ValueError("promote argument is True, "
                                     "but no parent was a dictionary")
                newnode = parent
                self._replace_node(None)
        if newnode is None:
            newnode = XMLDictNode(tag=self.tag, key=self.key,
                                  parent=self.parent)
            newnode._ignore_level = True
        try:
            for child in self:
                newkey = None
                for attr_keys in attrs:
                    key_check = KeyBuilder(attr_keys)

                    for grandchild in _get_dict_value_iter(child, "child node attributes"):
                        # The grandchild might be a list.
                        for item in grandchild.list():
                            newkey = key_check.eval_key(
                                list(item.xml_attrs.keys()),
                                item.get_cdata().strip()
                            )
                            if newkey is not None:
                                break
                        if newkey is not None:
                            break
                    if newkey is not None:
                        break
                if newkey is None:
                    for tag_keys in tags:
                        key_check = KeyBuilder(tag_keys)
                        for grandchild in _get_dict_value_iter(child,
                                                               "child node"):
                            for item in grandchild.list():
                                newkey = key_check.eval_key(
                                    [item.tag],
                                    item.get_cdata().strip()
                                )
                                if newkey is not None:
                                    break
                            if newkey is not None:
                                break
                        if newkey is not None:
                            break
                if newkey is None:
                    if func:
                        newkey = func(child)
                if not newkey:
                    newkey = child.tag
                newnode.add_node(tag=child.tag, key=newkey, new_node=child,
                                 update=in_place)
        except:
            # Do our best to restore things if something goes wrong
            # after we've already made changes. (Actually, even this
            # is bogus. If we've already re-added some of the nodes,
            # they will end up in both places.)
            if in_place and promote:
                if isinstance(self.parent, XMLListNode):
                    self.parent.append(self)
                else:
                    self.parent.add_node(self.tag, key=self.key, new_node=self)
            raise
        if in_place and not promote:
            self._replace_node(newnode)
        return newnode

    def standardize(self, deep=True):
        for idx in range(0, len(self)):
            node = self[idx]
            if not isinstance(node, XMLNodeBase):
                # Guess at the tag/key based on our own values. Set
                # the parent value correctly.
                # If we were told to do a deep conversion, then convert
                # the child; otherwise, don't.
                kwargs = dict(convert=deep, deep=deep, tag=self.tag,
                              key=self.key, parent=self)

                # Convert dicts to XMLDictNodes.
                # Convert lists to XMLListNodes.
                # Convert everything else to an XMLCDATANode with
                # a best guess for the correct string value.
                if isinstance(node, (OrderedDict, dict)):
                    self[idx] = XMLDictNode(node, **kwargs)
                elif isinstance(node, list):
                    self[idx] = XMLListNode(node, **kwargs)
                else:
                    if node is None:
                        node = _unicode('')
                    elif not isinstance(node, (_unicode, str)):
                        node = _unicode(node)
                    self[idx] = XMLCDATANode(node, **kwargs)

            else:
                # Update the internal book-keeping entries that might
                # need to be changed.
                self._check_replacement()
                if not node.tag:
                    node.tag = self.tag
                node.key = self.key
                node.parent = self
                if deep:
                    node.standardize(deep=deep)

    def _emit_handler(self, content_handler, depth, pretty, newl, indent):
        first_element = True
        for child in self:
            if pretty and depth == 0 and not first_element:
                content_handler.ignorableWhitespace(newl)
            child._emit_handler(content_handler, depth, pretty, newl, indent)
            first_element = False

    def prettyprint(self, *args, **kwargs):
        currdepth = kwargs.pop("currdepth", 0)
        depth = kwargs.get("depth", None)
        if depth is not None and depth < currdepth:
            return {}
        # Construct a new item, recursively.
        newlist = list()
        for v in self:
            if hasattr(v, "prettyprint"):
                newlist.append(v.prettyprint(*args, currdepth=currdepth+1,
                                             **kwargs))
            else:
                newlist.append(v)
        if currdepth == 0:
            pprint(newlist, *args, **kwargs)
        else:
            return newlist

    def _find_nodes_with_tag(self, tag, recursive=True, top_level=False):
        # Never return a list; only its descendants. When code calls
        # this method on a list, always call it for all the list
        # children.
        for node in self:
            kwargs = {'recursive': recursive}

            # If the list child has the same tag as the list, then
            # assume that the list is an automatic list to group
            # multiple items with the same tag. Therefore, run
            # this function on the list child as if it were being
            # run on the list itself.
            #
            # In this case, that means to pass on the top_level
            # marker unchanged.
            if node.tag == self.tag:
                kwargs['top_level'] = top_level
            for item in node._find_nodes_with_tag(tag, **kwargs):
                yield item

_docstring_fixup(XMLListNode)
