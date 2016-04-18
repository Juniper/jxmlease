#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides the XMLNodeBase class.

   This is the base class from which all the other XML node classes
   inherit.
"""
from __future__ import absolute_import

from xml.sax.saxutils import XMLGenerator
from copy import copy
from . import _node_refs, OrderedDict, StringIO, _unicode
from . import _XMLCDATAPlaceholder, _XMLDictPlaceholder, _XMLListPlaceholder

__all__ = ['XMLNodeBase']

class _NoArg(object): # pylint: disable=too-few-public-methods
    """Internal Use Only"""
    def __init__(self):
        pass

_common_docstring = lambda x: """Initialize an %s object.

The optional first parameter can be the value to which the
object should be initialized. All other parameters must be
given as keywords.

Normally, the user can simply run this as::

    >>> node = %s(initializer)

In fact, the best way to use this is::

    >>> root = XMLDictNode({'root': {'branch': { 'leaf': 'a'}}})

That will set all the tags, keys, etc. correctly. However,
if you really want to customize a node, there are other
parameters available. Note that these parameters only
impact *this* node and descendants. They don't actually
add the node to a tree. Therefore, their use is
discouraged. Instead, you can probably use the :py:meth:`add_node`
method to build your tree correctly.

The one exception to this general rule is when adding a
hunk of a tree. For example, assume you currently have this XML
structure::

    <a>
      <b>
        <node1>a</node1>
      </b>
    </a>

And, assume you want to add another node ``b`` to create this
XML structure::

    <a>
      <b>
        <node1>a</node1>
      </b>
      <b>
        <node2>b</node1>
      </b>
    </a>

In that case, you might do something like this::

    >>> root.prettyprint()
    {u'a': {u'b': {u'node1': u'a'}}}
    >>> new_b = {'node2': 'b'}
    >>> new_b = XMLDictNode(new_b, tag="b")
    >>> _ = root['a'].add_node(tag="b", new_node=new_b)
    >>> root.prettyprint()
    {u'a': {u'b': [{u'node1': u'a'}, {'node2': u'b'}]}}

And, you can print the XML to prove it is formatted correctly::

    >>> print root.emit_xml()
    <?xml version="1.0" encoding="utf-8"?>
    <a>
        <b>
            <node1>a</node1>
        </b>
        <b>
            <node2>b</node2>
        </b>
    </a>

Args:
    initializer (as appropriate for node): The initial value for
        the node.
    tag (string): The XML tag for this node.
    key (string or tuple): The dictionary key used for this node.
    xml_attrs (`dict`): The XML attributes for the node.
    text (string): The node's initial CDATA value. (Note
        that this is ignored for :py:class:`XMLCDATANode` objects.)
    parent (Instance of a sub-class of :py:class:`XMLNodeBase`): A
        reference to the object's parent node in the data structure.
    convert (bool): If True, the :py:meth:`convert` method is run on
        the object's children during object initialization.
    deep (bool): If True (and the :py:obj:`convert` parameter is
        True), the :py:meth:`convert` method is run recursively
        on the object's children during object initialization.
""" % (x, x)

def _docstring_fixup(cls):
    """Fixup docstrings for a subclass of XMLNodeBase.

       This method will find any class method with an unset docstring
       and try to copy it from the corresponding method in
       XMLNodeBase.
    """
    if hasattr(cls, '__init__') and not cls.__init__.__doc__:
        docstring = """Initialize an %s object.

        See the class documentation for initializer arguments.
        """ % (cls.__name__)
        try:
            cls.__init__.__doc__ = docstring
        except AttributeError:
            cls.__init__.__func__.__doc__ = docstring
    for k in dir(cls):
        if hasattr(getattr(cls, k), '__call__') and not getattr(cls, k).__doc__:
            if hasattr(XMLNodeBase, k):
                docstring = getattr(XMLNodeBase, k).__doc__
                try:
                    getattr(cls, k).__doc__ = docstring
                except AttributeError:
                    try:
                        getattr(cls, k).__func__.__doc__ = docstring
                    except AttributeError:
                        # You just can't update some methods...
                        pass

XMLCDATANode = _XMLCDATAPlaceholder
XMLDictNode = _XMLDictPlaceholder
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
    global XMLDictNode
    global XMLListNode
    global _resolve_references
    XMLCDATANode = _node_refs['XMLCDATANode']
    XMLDictNode = _node_refs['XMLDictNode']
    XMLListNode = _node_refs['XMLListNode']
    _resolve_references = lambda: None

_resolve_references = _resolve_references_once

class XMLNodeBase(object):
    """This module provides methods common to the XML node classes.

    This modules is not intended for standalone use.
    """

    def __new__(cls, *args, **kwargs):
        # Resolve delayed references, if necessary
        _resolve_references()

        # Make a copy of the kwargs dictonary. (We don't want to modify
        # the original; we only want to modify the values we pass on
        # to super classes.)
        kwargs = dict(kwargs)

        # Determine if we were called with an initial value. If so,
        # make sure there was only *one* initial value.
        initializer = kwargs.pop("initializer", _NoArg())
        if not isinstance(initializer, _NoArg):
            if len(args) > 0:
                raise TypeError("got multiple values for keyword "
                                "argument 'initializer'")
            args = (initializer,)
        elif len(args) == 1:
            initializer = args[0]


        # Pop off arguments that have a special meaning at our layer.
        for k in ("tag", "key", "parent", "xml_attrs", "text",
                  "convert", "deep"):
            _ = kwargs.pop(k, None)

        # Create the object.
        return super(XMLNodeBase, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        # Make a copy of the kwargs dictonary. (We don't want to modify
        # the original; we only want to modify the values we pass on
        # to super classes.)
        kwargs = dict(kwargs)

        # Determine if we were called with an initial value. If so,
        # make sure there was only *one* initial value.
        initializer = kwargs.pop("initializer", _NoArg())
        if not isinstance(initializer, _NoArg):
            if len(args) > 0:
                raise TypeError("got multiple values for keyword "
                                "argument 'initializer'")
            args = (initializer,)
        elif len(args) == 1:
            initializer = args[0]


        # Process arguments

        # Do not inherit tag, key, or parent in copies.
        tag = kwargs.pop("tag", None)
        key = kwargs.pop("key", tag)
        parent_node = kwargs.pop("parent", None)

        # If the initial value was an XMLNodeBase child, copy
        # node_text and xml_attrs.

        # Set some overall defaults
        xml_attrs = OrderedDict()
        node_text = _unicode()

        # Modify the defaults if the initial value was an XMLNodeBase object
        if isinstance(initializer, XMLNodeBase):
            xml_attrs = getattr(initializer, "xml_attrs", xml_attrs)
            node_text = getattr(initializer, "text", node_text)

        # Process the arguments to override the defaults
        xml_attrs = kwargs.pop("xml_attrs", xml_attrs)
        node_text = kwargs.pop("text", node_text)

        # Process other arguments
        convert = kwargs.pop('convert', True)
        deep = kwargs.pop('deep', True)

        # Initialize the object.
        super(XMLNodeBase, self).__init__(*args, **kwargs)

        # Add attributes to the object.
        self.tag = tag
        self.key = copy(key)
        self.xml_attrs = OrderedDict()
        for k in xml_attrs:
            self.xml_attrs[k] = _unicode(xml_attrs[k])
        if not hasattr(self, "text"):
            self.text = node_text
        self.parent = parent_node
        self._replacement_node = None
        if convert:
            self.standardize(deep=deep)

    def has_xml_attrs(self):
        """Determine if the node has XML attributes.

        Returns:
            A bool that is True if the node has XML attributes, and
                False otherwise.
        """
        if len(self.xml_attrs) > 0:
            return True
        return False

    def _check_replacement(self):
        # Ensure the object is current.
        if self._replacement_node:
            raise AttributeError(
                "Attempt to modify an out-of-date node. " +
                "Use get_current_node() to update the reference."
                )

    def set_xml_attr(self, attr, val):
        """Set an XML attribute.

        This method sets the XML attribute to the given value.  If the
        XML attribute already existed, its value is overridden by the
        new value.  If the XML attribute did not already exist, it is
        created.

        Args:
            attr (string): The name of the XML attribute.
            val (string): The value of the XML attribute.

        Returns:
            None

        Raises:
            :py:exc:`AttributeError`: If the node is out of date.
                (See :py:meth:`get_current_node`.)
        """
        self._check_replacement()
        self.xml_attrs[attr] = _unicode(val)

    def get_xml_attr(self, attr, defval=_NoArg()):
        """Get an XML attribute.

        This method returns the value of an XML attribute. If the XML
        attribute does not exist, it will return a user-supplied default value.
        If the user did not supply a default value, it raises a KeyError.

        Args:
            attr (string): The name of the XML attribute.
            defval (string): The default value. (Default: Raise a KeyError.)

        Returns:
            The string value of the XML attribute, or :py:obj:`defval`.

        Raises:
            :py:exc:`KeyError`: If the :py:obj:`attr` is not found and
                :py:obj:`defval` is not supplied.
        """
        try:
            return self.xml_attrs[attr]
        except KeyError:
            if not isinstance(defval, _NoArg):
                return defval
            raise

    def get_xml_attrs(self):
        """Return the XML attribute dictionary.

        This method returns the value of the XML attribute
        dictonary.  Note that it returns the actual XML attribute
        dictionary, rather than a copy.  Please take caution in
        modifying it.

        Returns:
            :py:class:`OrderedDict`: The XML attribute dictionary.
        """
        return self.xml_attrs

    def delete_xml_attr(self, attr):
        """Delete an XML attribute.

        This method deletes an XML attribute from the node.  If the
        attribute does not exist, it raises a KeyError.

        Args:
            attr (string): The name of the XML attribute.

        Returns:
            None

        Raises:
            :py:exc:`KeyError`: If the :py:obj:`attr` is not found.
            :py:exc:`AttributeError`: If the node is out of date. (See
                :py:meth:`get_current_node`.)
        """
        self._check_replacement()
        del self.xml_attrs[attr]

    def set_cdata(self, cdata, return_node=False):
        """Set a node's CDATA.

        This method sets a node's CDATA.  Note that any node can
        contain CDATA in what is called "semi-structured"
        XML. However, nodes that only contain CDATA are represented as
        :py:class:`XMLCDATANode` objects. Regardless of the node, you can use
        this same method to set the CDATA.

        **Note**: When running this on an XMLCDATANode, the actual node
        will be replaced with a new node in the tree. (This is a
        result of Python's string immutability.)  The function will
        update the XML tree, if necessary; however, any local
        references you have saved for the node will become stale.  You
        can obtain the updated node by setting the return_node
        parameter to True or by running the :py:meth:`get_current_node` method
        on the old node. For this reason, if you plan to keep a local
        reference to XML node in question, it is a good idea to run
        the method like this::

            >>> node = root['a']['b'][0]
            >>> node = node.set_cdata("foo", True)

        Args:
            cdata (string): The text value that should be used for the
                node's CDATA.
            return_node (bool): Whether the method should return the
                updated node.

        Returns:
            None or the updated node object if :py:obj:`return_node` is True.

        Raises:
            :py:exc:`AttributeError`: If the node is out of date. (See
                :py:meth:`get_current_node`.)
        """
        self._check_replacement()
        self.text = _unicode(cdata)
        if return_node:
            return self

    def append_cdata(self, cdata, return_node=False):
        """Append text to a node's CDATA.

        This method appends text to a node's CDATA.  Note that any
        node can contain CDATA in what is called "semi-structured"
        XML. However, nodes that only contain CDATA are represented as
        :py:class:`XMLCDATANode` objects. Regardless of the node, you can use
        this same method to append CDATA.

        **Note**: When running this on an :py:class:`XMLCDATANode`, the actual
        node will be replaced with a new node in the tree. (This is a
        result of Python's string immutability.)  The function will
        update the XML tree, if necessary; however, any local
        references you have saved for the node will become stale.  You
        can obtain the updated node by setting the :py:obj:`return_node`
        parameter to True or by running the :py:meth:`get_current_node` method
        on the old node. For this reason, if you plan to keep a local
        reference to XML node in question, it is a good idea to run
        the method like this::

            >>> node = root['a']['b'][0]
            >>> node = node.append_cdata("foo", True)

        Args:
            cdata (string): The text value that should be used for the
                node's CDATA.
            return_node (bool): Whether the method should return the
                updated node.

        Returns:
            None, if :py:obj:`return_node` is False, otherwise, the updated
                node object.

        Raises:
            :py:exc:`AttributeError`: If the node is out of date.
                (See :py:meth:`get_current_node`.)
        """
        self._check_replacement()
        self.text = self.text + cdata
        if return_node:
            return self

    def get_cdata(self):
        """Get a node's CDATA.

        Returns:
            A string containing the node's CDATA.
        """
        return self.text

    def strip_cdata(self, chars=None, return_node=False):
        """Strip leading/trailing characters from a node's CDATA.

        This method runs the string class' :py:meth:`strip` method on a node's
        CDATA and updates the node's CDATA with the result. (This is
        the functional equivalent to
        ``node.set_cdata(node.get_cdata().strip())``.)

        Note that any node can contain CDATA in what is called
        "semi-structured" XML. However, nodes that only contain CDATA
        are represented as :py:class:`XMLCDATANode` objects. Regardless of the
        node, you can use this same method to append CDATA.

        **Note**: When running this on an :py:class:`XMLCDATANode`, the actual
        node will be replaced with a new node in the tree. (This is a
        result of Python's string immutability.)  The function will
        update the XML tree, if necessary; however, any local
        references you have saved for the node will become stale.  You
        can obtain the updated node by setting the return_node
        parameter to True or by running the :py:meth:`get_current_node` method
        on the old node. For this reason, if you plan to keep a local
        reference to XML node in question, it is a good idea to run
        the method like this::

            >>> node = root['a']['b'][0]
            >>> node = node.strip_cdata(return_node=True)

        Args:
            chars (string): Contains the characters to strip. This is passed to
                the string class' :py:meth:`strip` method.
            return_node (bool): Whether the method should return the
                updated node.

        Returns:
            None if :py:obj:`return_node` is False; otherwise, the updated
                node object.

        Raises:
            :py:class:`AttributeError`: If the node is out of date.
                (See :py:meth:`get_current_node`.)
        """
        self._check_replacement()
        newtext = _unicode.strip(self.get_cdata(), chars)
        return self.set_cdata(newtext, return_node)

    def add_node(self, tag, key=None, text=_unicode(), new_node=None,
                 update=True, **kwargs):
        """Add an XML node to an XML tree.

        This method adds a new XML node as a child of the current
        node. If the current node is an :py:class:`XMLCDATANode`, it will be
        converted to an :py:class:`XMLDictNode` so that it can hold children.
        If the current node is an :py:class:`XMLDictNode` and you attempt to
        add a node with a duplicate key, the code will create a list to hold
        the existing node and add the new node to the list.

        By default, all new nodes are created as :py:class:`XMLCDATANode`
        objects. You can include any keyword parameters that you could
        provide when creating an :py:class:`XMLCDATANode` object. If supplied,
        these additional keyword parameters are passed to the
        :py:func:`XMLCDATANode.__init__` function.

        Args:
            tag (string): The XML tag of the node.
            key (string or tuple): The dictionary key that the method should
                use for the node. If None (the default), the :py:obj:`tag` is
                is used as the key.
            text (string): The CDATA for the new node. The default value is
                an empty string.
            new_node (instance of a subclass of :py:class:`XMLNodeBase`): If
                supplied, this will be used for the new node instead of a
                new instance of the :py:class:`XMLCDATANode`. If supplied, the
                :py:obj:`text` parameter and additional keyword arguments
                are ignored.
            update (bool): If True (the default), update the reverse linkages
                in the new node to point to the parent. If False, only create
                the one-way linkages from the parent to the child. (**Note**:
                This should always be True unless you are creating a temporary
                tree for some reason. Setting this to False may create
                inconsistent data that causes problems later.)

        Raises:
            :py:exc:`AttributeError`: If the node is out of date
                (See :py:meth:`get_current_node`) or the method encounters
                irrecoverable data inconsistency while making changes to the
                XML tree.
            :py:exc:`TypeError`: If :py:obj:`new_node` is not None and not
                an instance of :py:class:`XMLNodeBase`
        """
        raise NotImplementedError()

    def list(self, in_place=False):
        """Return a node as a list.

        This method returns a node as a list. This is useful when you
        are not sure whether a node will contain a single entry or a
        list. If the node contains a list, the node itself is
        returned. If the node does not already contain a list, the
        method creates a list, adds the node to it, and returns the
        list.

        If the :py:obj:`in_place` parameter is True, then the change is
        made in the XML tree. Otherwise, the XML tree is left unchanged and
        the method creates and returns a temporary list.

        Args:
            in_place (bool): Whether the change should be made in the
                XML tree.

        Returns:
            list or :py:class:`XMLListNode`
            If the current node is a list, the current node;
            otherwise, a list containing the current node as its sole
            member.

        Raises:
            :py:exc:`AttributeError`: If the node is out of date and
                :py:obj:`in_place` is True. (See :py:meth:`get_current_node`.)
        """
        if not in_place:
            return [self]
        new_node = XMLListNode(
            [self], tag=self.tag, key=self.key, parent=self.parent,
            convert=False
        )
        self._replace_node(new_node)

        # We weren't "replaced" in the destructive sense, so clear
        # the replacement node indicator.
        self._replacement_node = None

        # self._replace_node() may have updated our key if it was out
        # of date, so grab it.
        self.key = copy(new_node.key)

        # Reparent ourselves.
        self.parent = new_node

        # Return the list.
        return new_node

    def get_current_node(self):
        """Return the current node.

        There are times that the current node must be replaced in the
        XML tree for some reason. For example, due to the immutability
        of Python strings, a new XMLCDATANode (which masquerades as a
        string) is required anytime its CDATA value changes.

        When this occurs, you can retrieve the latest node using the
        get_current_node() method. This will attempt to find the node
        that succeeded the node in question. If the node is still
        current, it simply returns itself.

        Therefore, it should always be safe to run::

            >>> node = node.get_current_node()

        Returns:
            Subclass of :py:class:`XMLNodeBase` containing the current
            successor to the node (if any). If the node is still "current",
            the method returns the node itself.
        """
        if self._replacement_node is not None:
            # Recurse as deep as we can looking for replacement nodes.
            # If we hit an error, return the last replacement node we found.
            try:
                while self._replacement_node._replacement_node is not None:
                    self._replacement_node = (
                        self._replacement_node._replacement_node
                    )
            except: # pylint: disable=bare-except
                pass
            return self._replacement_node
        else:
            return self

    def _replace_node(self, newnode):
        # Replace a node with a new node. If the replacement node is
        # None, then the node is deleted.

        self._check_replacement()
        # We need to replace ourselves with a new node.
        if self.parent is None:
            raise AttributeError("Attempt to modify root document")
        # Record the replacement for anyone who still holds
        # references to this node.
        if newnode is not None:
            self._replacement_node = newnode
        # Case 1: Parent is dictionary
        try:
            # Plan A: Do the lookup by expected key.
            if self.key in self.parent:
                if self.parent[self.key] == self:
                    if newnode is not None:
                        self.parent[self.key] = newnode
                    else:
                        del self.parent[self.key]
                    return
            # Plan B: Brute force check, in case of some sort of
            # mismatch. We do our best, within reason.
            myiter = None
            try:
                # Python 2
                myiter = self.parent.iteritems()
            except AttributeError:
                # Python 3
                myiter = self.parent.items()
            for key, val in myiter:
                if val == self:
                    if newnode is not None:
                        # Update the new node's key
                        newnode.key = copy(key)
                        # Replace us
                        self.parent[key] = newnode
                    else:
                        del self.parent[key]
                    return
                elif isinstance(val, XMLListNode):
                    # Check the list
                    for i in range(0, len(val)):
                        if val[i] == self:
                            if newnode is not None:
                                # Update the new node's key and parent
                                newnode.key = copy(key)
                                newnode.parent = val
                                # Replace us
                                val[i] = newnode
                            else:
                                del val[i]
                                # Make sure we don't need to delete the
                                # enclosing list, too.
                                if len(val) == 0:
                                    val._replace_node(None)
                            return
        except: # pylint: disable=bare-except
            pass
        # Case 2: Parent is list
        try:
            made_change = False
            for i in range(0, len(self.parent)):
                if self.parent[i] == self:
                    if newnode is not None:
                        self.parent[i] = newnode
                        return
                    else:
                        del self.parent[i]
                        made_change = True
                        break
            if made_change:
                # Make sure we don't need to delete the enclosing list,
                # too.
                if len(self.parent) == 0:
                    self.parent._replace_node(None)
                return
        except: # pylint: disable=bare-except
            pass
        raise AttributeError("Unable to find existing node in parent")

    def dict(self, attrs=None, tags=None, func=None, in_place=False,
             promote=False):
        """Return a dictionary keyed as indicated by the parameters.

        This method lets you re-key your data with some
        flexibility. It takes the current node (whether a single node
        or a list) and turns it into a dictionary. If the current node
        is a list, all the list members are added to the
        dictionary. If the current node is not a list, just the
        current node is added to the dictonary.

        The key for each node is determined by the :py:obj:`attrs`,
        :py:obj:`tags`, and :py:obj:`func` parameters, in that order of
        precedence. For *each node*, the method looks for child nodes that
        have an XML attribute that exactly matches one of the attributes
        in the :py:obj:`attrs` argument. If it finds a match, it uses the
        *node's* (not the attribute's) CDATA as the key.

        If the method does not find a matching attribute, it looks for
        child nodes that have a tag that exactly matches one of the
        tags in the :py:obj:`tags` argument. If it finds a match, it uses
        the node's CDATA as the key.

        If the method does not find a matching tag, it passes the node
        to the user-suppled function (supplied by the :py:obj:`func` parameter)
        and uses the return value as the key.

        If the :py:obj:`func` is not provided or returns a value that
        evaluates to False (e.g. None or ""), the method uses the node's
        XML tag as the key.

        If there are multiple matches, the order of precedence is like
        this (again, this is applied for *each node* independent of
        the other nodes):

        1. The attributes in the attrs parameter, in the order they
           appear in the attrs parameter.
        2. The tags in the tags parameter, in the order they appear
           in the attrs parameter.
        3. The return value of the user-supplied function.
        4. The node's XML tag.

        If the :py:obj:`in_place` parameter is True, then the method will
        replace the current node in the hierarchy with the
        dictionary. Otherwise, it will create a new dictionary and
        return it.

        If both the :py:obj:`in_place` and :py:obj:`promote` parameters are
        True, then the method will make the changes as described above;
        however, it will add the nodes to the first dictionary it finds
        enclosing the curent node.

        Some examples should help with this. Here is an example of the
        simple functionality. Note how the original nodes are turned
        into a dictionary with the appropriate keys, but the original
        root is left untouched::

            >>> root.prettyprint()
            {'a': {'b': [{'name': u'foo', 'value': u'1'},
                         {'name': u'bar', 'value': u'2'}]}}
            >>> root['a']['b'].dict(tags=['name']).prettyprint()
            {u'bar': {'name': u'bar', 'value': u'2'},
             u'foo': {'name': u'foo', 'value': u'1'}}
            >>> root.prettyprint()
            {'a': {'b': [{'name': u'foo', 'value': u'1'},
                         {'name': u'bar', 'value': u'2'}]}}

        Here is an example of a dictionary changed in place. Note how
        the original nodes are turned into a dictionary with the
        appropriate keys and this dictionary replaces the current node
        in the hierarchy::

            >>> root.prettyprint()
            {'a': {'b': [{'name': u'foo', 'value': u'1'},
                         {'name': u'bar', 'value': u'2'}]}}
            >>> root['a']['b'].dict(tags=['name'], in_place=True).prettyprint()
            {u'bar': {'name': u'bar', 'value': u'2'},
             u'foo': {'name': u'foo', 'value': u'1'}}
            >>> root.prettyprint()
            {'a': {'b': {u'bar': {'name': u'bar', 'value': u'2'},
                         u'foo': {'name': u'foo', 'value': u'1'}}}}

        Here is an example of the "promotion" functionality. Note how
        the original nodes are added directly to the ``root['a']``
        enclosing dictionary::

            >>> root.prettyprint()
            {'a': {'b': [{'name': u'foo', 'value': u'1'},
                         {'name': u'bar', 'value': u'2'}]}}
            >>> root['a']['b'].dict(tags=['name'], in_place=True, promote=True).prettyprint()
            {u'bar': {'name': u'bar', 'value': u'2'},
             u'foo': {'name': u'foo', 'value': u'1'}}
            >>> root.prettyprint()
            {'a': {u'bar': {'name': u'bar', 'value': u'2'},
                   u'foo': {'name': u'foo', 'value': u'1'}}}

        Quirks:

        1. If the current node is the only member of a list in
           the XML tree, the operation will occur on that single-node
           list instead of the node itself.
        2. If the method encounters an exception while trying to
           modify the XML tree (``in_place == True``), it will attempt
           to undo its changes; however, this logic is not
           completely reliable.

        Args:
            attrs (`list`): The list of XML attributes that signal a node
                should be used as a key.
            tags (`list`): The list of XML tags that signal a node should be
                used as a key.
            func (function): A function that will accept a node as a parameter
                and return a key.
            in_place (bool): Whether the change should be made in the XML tree.
            promote (bool): Whether the new nodes should be added to a
                dictonary placed at the current node, or they should be
                "promoted" to the first enclosing dictionary.

        Returns:
            An :py:class:`XMLDictNode`. If :py:obj:`in_place` is False, the
            dictionary formulated from the current node. If :py:obj:`in_place`
            is True, the dictionary to which the nodes were added.
            (Note: If :py:obj:`promote` is True, this dictionary may contain
            additional entries that already existed in the enclosing
            dictionary.)

        Raises:
            :py:class:`AttributeError`: If the node is out of date and
                :py:obj:`in_place` is True. (See :py:meth:`get_current_node`.)
            :py:class:`AttributeError`: If :py:obj:`in_place`
                is True and the method encounters irrecoverable data
                inconsistency while making changes to the XML tree.
        """
        if attrs is None:
            attrs = []
        if tags is None:
            tags = []
        newlist = None
        if in_place:
            # If editing in place, check that we are current.
            self._check_replacement()

            # Save some information to help restore things, if needed.
            orig = dict(parent=self.parent, tag=self.tag, key=self.key)

            # If we were editing in place, we need to figure out how to
            # properly replace ourselves.
            #
            # If our parent is a single-member list, then we can just
            # convert it. If our parent is a dictionary, then we can
            # convert ourselves in place. If our parent is anything
            # else, we just convert ourselves in place and do our best
            # to replace ourselves with a dictionary -- even if that
            # doesn't make complete sense.
            parent = self.parent
            if (isinstance(parent, XMLListNode) and len(parent) == 1
                    and parent[0] == self):
                # Easy. Just convert our parent.
                newlist = parent
            else:
                # Turn us into a list.
                newlist = self.list(in_place=True)
        if newlist is None:
            # Make a list and add us to it.
            newlist = XMLListNode(
                [self], tag=self.tag, key=self.key, convert=False
            )

        # Now, let's turn the list node into a dict.
        try:
            # pylint: disable=no-member
            return newlist.dict(
                attrs=attrs, tags=tags, func=func, in_place=in_place,
                promote=promote
            )
        except:
            if in_place:
                # Try to restore us.
                self.parent = orig['parent']
                self.tag = orig['tag']
                self.key = orig['key']
                self._replacement_node = None
                newlist._replace_node(self) # pylint: disable=no-member
            raise

    def jdict(self, in_place=False, promote=False):
        """Return a dictionary keyed appropriately for Junos output.

        This method is a shortcut to call the :py:meth:`dict`
        method with these parameters::

            attrs=[('junos:key', 'junos:key', 'junos:key'),
                   ('junos:key', 'junos:key'), 'junos:key']
            tags=['name']

        This will attempt to produce the correct key for each
        node. Some nodes have a multi-field key. If that occurs, the
        dictionary key will be a tuple. In cases where there is a
        single key, the dictionary key will be a string. If there is
        no matching node, the key will simply be the XML tag name.

        Some Junos nodes use a different tag for the key. And, in some
        cases, the ``junos:key`` attribute is not available. In those
        circumstances, you should directly call the :py:meth:`dict`
        method with the correct attributes or tags.

        Please see the documentation for the :py:meth:`dict` method for
        further information.

        Args:
            in_place (bool): Whether the change should be made in the XML tree.
            promote (bool): Whether the new nodes should be added to a
                dictonary placed at the current node, or they should be
                "promoted" to the first enclosing dictionary.

        Returns:
            An :py:class:`XMLDictNode`. If :py:obj:`in_place` is False, the
            dictionary formulated from the current node. If :py:obj:`in_place`
            is True, the dictionary to which the nodes were added.
            (Note: If :py:obj:`promote` is True, this dictionary may contain
            additional entries that already existed in the enclosing
            dictionary.)

        Raises:
            :py:class:`AttributeError`: If the node is out of date and
                :py:obj:`in_place` is True. (See :py:meth:`get_current_node`.)
            :py:class:`AttributeError`: If :py:obj:`in_place`
                is True and the method encounters irrecoverable data
                inconsistency while making changes to the XML tree.
        """
        return self.dict(attrs=[('junos:key', 'junos:key', 'junos:key'),
                                ('junos:key', 'junos:key'), 'junos:key'],
                         tags=['name'], in_place=in_place, promote=promote)

    def standardize(self, deep=True):
        """Convert all child nodes to instances of an XMLNodeBase sub-class.

        This method is useful when you have added a child node
        directly to a dictionary or list and now want to convert it to
        the appropriate :py:class:`XMLNodeBase` sub-class.

        Args:
            deep (bool): If True (the default), recursively descend
                through all children, converting all nodes, as needed. If
                False, only convert direct children of the node.
        Returns:
            None
        """
        raise NotImplementedError()

    def emit_handler(self, content_handler, pretty=True, newl='\n',
                     indent='    ', full_document=None):
        """Pass the contents of the XML tree to a ContentHandler object.

        This method will pass the contents of the XML tree to a
        :py:obj:`ContentHandler` object.

        Args:
            content_handler (:py:obj:`ContentHandler`): The
                :py:obj:`ContentHandler` object to which the XML tree wll
                be passed.
            pretty (bool): If True, this method will call the
                :py:meth:`content_handler.ignorableWhitespace` method to add
            whitespace to the output document.
            newl (string): The string which the method should use for new
                lines when adding white space (see the :py:obj:`pretty`
                parameter).
            indent (text): The string which the method should use for each
                level of indentation when adding white space (see the
                :py:obj:`pretty` parameter).
            full_document (bool): If True, the method will call the
                :py:meth:`content_handler.startDocument` and
                :py:meth:`content_handler.endDocument` methods at the start
                and end of the document, respectively. If False, it will not
                call these methods. If the parameter is not set, the method
                will attempt to determine whether the current node is the root
                of an XML tree with a single root tag. If so, it will set
                the full_document parameter to True; otherwise, it will
                set it to False.

        Returns:
            None
        """
        full_document_ok = None
        curnode = self
        # See if it is OK to be a full document. If we will have
        # multiple root nodes, it is not OK. Otherwise, we assume
        # it is.
        while full_document_ok is None:
            if isinstance(curnode, XMLCDATANode):
                # Always OK
                full_document_ok = True
            elif not isinstance(curnode, XMLNodeBase):
                # Never OK -- will probably produce an error later
                full_document_ok = False
            elif isinstance(curnode, XMLListNode) and len(curnode) > 1:
                # We have multiple tags. We cannot be a full document.
                full_document_ok = False
            elif len(curnode) == 0:
                # Empty nodes are always OK.
                full_document_ok = True
            elif ((curnode.tag is None and isinstance(curnode, XMLDictNode)) or
                  isinstance(curnode, XMLListNode)):
                # If curnode.tag is None (or this is a list), this
                # amounts to a request to output the child(ren) of
                # this node. If there are multiple children, we know
                # that it is not OK to make this a full document (as
                # there will be multiple top-level tags). If there is
                # just one child, we need to look at the child to
                # determine whether it is OK to treat it as a full
                # document.
                if len(curnode) > 1:
                    full_document_ok = False
                else:
                    if isinstance(curnode, XMLListNode):
                        curnode = curnode[0]
                    elif isinstance(curnode, XMLDictNode):
                        curnode = curnode[[i for i in curnode][0]]
            elif isinstance(curnode.tag, (_unicode, str)):
                # We have a tag. That will produce a top-level tag.
                full_document_ok = True
            else:
                # We generally shouldn't get here, but let the user
                # do what they want.
                full_document_ok = True

        if full_document is not None:
            # We were given a full_document argument. Make sure it is
            # OK to treat this as a "full document".
            if full_document and not full_document_ok:
                raise ValueError("Document will have more than one root node. "
                                 "The full_document argument must be False.")
        else:
            # Default to full_document=True, if it is OK to treat this
            # as a full document and it looks like we are at the root.
            full_document = full_document_ok
            if full_document:
                # Guess that we are at the root if:
                # - self.tag is None, or
                # - self.tag is not None, but we have no parent, or
                # - self.tag is not None, but our parent looks like a
                #   single-member, tagless root
                if (self.tag is not None and self.parent is not None and
                        (self.parent.tag is not None or len(self.parent) > 1)):
                    full_document = False

        if full_document:
            content_handler.startDocument()
        curnode._emit_handler(content_handler, depth=0, pretty=pretty, newl=newl,
                              indent=indent)
        if full_document:
            content_handler.endDocument()

    def emit_xml(self, output=None, encoding='utf-8', handler=XMLGenerator,
                 **kwargs):
        """Return the contents of the XML tree as an XML document.

        This method will create a :py:obj:`ContentHandler` by calling the
        method provided by the handler parameter.  It will call
        :py:meth:`emit_handler` with this :py:obj:`ContentHandler` object.
        In addition, this method will accept any parameter that the
        :py:meth:`emit_handler` method accepts (except the
        :py:obj:`content_handler` parameter).  It will pass
        them to the :py:meth:`emit_handler` method when it calls it.

        Args:
            output (A file-like IO object, or None): The file-like IO object
                in which output should be placed. If None, the method will
                return the XML output as a string.
            encoding (string): The encoding that should be used for the output.
            handler (function): A method that will return a
                :py:obj:`ContentHandler` object. This method will be called
                with two positional parameters: the output parameter
                (or, if None, a file-like IO object) and the encoding parameter.
        Returns:
            If :py:obj:`output` was None, the method will return the XML
            output as a string. Otherwise, None.
        """
        if output is None:
            output = StringIO()
            return_text = True
        else:
            return_text = False

        content_handler = handler(output, encoding)

        self.emit_handler(content_handler, **kwargs)

        if return_text:
            value = output.getvalue()
            try:  # pragma no cover
                value = value.decode(encoding)
            except AttributeError:  # pragma no cover
                pass
            return value

    def _emit_handler(self, content_handler, depth, pretty, newl, indent):
        raise NotImplementedError()

    def prettyprint(self, *args, **kwargs):
        """Print a "pretty" representation of the data structure.

        This uses the :py:meth:`pprint` method from the :py:mod:`pprint`
        module to print a "pretty" representation of the data structure.
        The parameters are passed unchanged to the :py:meth:`pprint` method.

        The output from this method shows only the main data and not the meta
        data (such as XML attributes).

        When using :py:meth:`pprint`, it is necessary to use this method to
        get a reasonable representation of the data; otherwise,
        :py:meth:`pprint` will not know how to represent the object in a
        "pretty" way.
        """
        raise NotImplementedError()

    def find_nodes_with_tag(self, tag, recursive=True):
        """Iterates over nodes that have a matching tag.

        This method searches the current node and its children for
        nodes that have a matching tag. The :py:obj:`tag` parameter
        accepts either a string value or a tuple, allowing you to
        search for one or more tags with a single
        operation. Optionally (by providing a False value to the
        :py:obj:`recursive` parameter), you can limit the search to
        the current node and direct children of the current node.

        The method will return a generator, which you can use to
        iterate over the matching nodes.

        For example, this will print all "name" nodes from the XML
        snippet that is shown::

            >>> root = jxmlease.parse(\"\"\"\
            ... <?xml version="1.0" encoding="utf-8"?>
            ... <root>
            ...     <a>
            ...         <name>name #1</name>
            ...         <b>
            ...             <name>name #2</name>
            ...         </b>
            ...         <b>
            ...             <c>
            ...                 <name>name #3</name>
            ...             </c>
            ...         </b>
            ...     </a>
            ... </root>\"\"\")
            >>> print root
            {u'root': {u'a': {u'b': [{u'name': u'name #2'},
                                     {u'c': {u'name': u'name #3'}}],
                              u'name': u'name #1'}}}
            >>> for node in root.find_nodes_with_tag('name'):
            ...   print node
            ...
            name #1
            name #2
            name #3

        However, if we turn off recursion, you will see that this
        returns only the direct children (if any) of the node we
        select::

            >>> for node in root.find_nodes_with_tag('name', recursive=False):
            ...   print node
            ...
            >>> for node in root['root']['a'].find_nodes_with_tag('name', recursive=False):
            ...   print node
            ...
            name #1

        If you run this against an :py:class:`XMLDictNode` without a
        tag (for example, the tagless root node), then the command is
        run on each member of the dictionary. The impact of this is
        that a non-recursive search will search for tags in the
        grandchildren of the tagless :py:class:`XMLDictNode`, rather
        than searching the children of the tagless
        :py:class:`XMLDictNode`::

            >>> root = jxmlease.parse(\"\"\"\
            ... <a>
            ...   <name>second-level tag</name>
            ...   <b>
            ...     <name>third-level tag</name>
            ...   </b>
            ... </a>\"\"\")
            >>> for i in root.find_nodes_with_tag('name', recursive=False):
            ...   print i
            ...
            second-level tag
            >>> for i in root['a'].find_nodes_with_tag('name', recursive=False):
            ...   print i
            ...
            second-level tag

        This method never returns a list. Instead, lists pass the
        command through to their child nodes, which may be
        returned. This ensures you get back each node you requested.

        For example, here is a root node with two top-level "name"
        elements. Searching non-recursively for the "name" tag returns
        the two "name" elements, even though they are enclosed within
        a dictionary and list::

            >>> root = XMLDictNode()
            >>> _ = root.add_node(tag='name', text='tag #1')
            >>> _ = root.add_node(tag='name', text='tag #2')
            >>> print root
            {'name': [u'tag #1', u'tag #2']}
            >>> for i in root.find_nodes_with_tag('name', recursive=False):
            ...   print i
            ...
            tag #1
            tag #2
            >>>

        Even though our examples up to this point have
        demonstrated text, it is worth noting that this method returns
        the actual node, whatever that may be::

            >>> root = jxmlease.parse(\"\"\"\
            ... <a>
            ...   <b>
            ...     <c>
            ...       <foo>bar</foo>
            ...       <status>ok</status>
            ...     </c>
            ...   </b>
            ... </a>\"\"\")
            >>> for i in root.find_nodes_with_tag('b'):
            ...   print i
            ...
            {u'c': {u'foo': u'bar', u'status': u'ok'}}

        If the :py:obj:`recursive` parameter is False, the code will
        check the current node. If the current node does not match,
        the code will check the current node's direct
        children. However, if the current node has a matching tag and
        the :py:obj:`recursive` parameter is False, the code will stop
        its search and not check the children of the current node.

        If the :py:obj:`recursive` parameter is True (the default),
        the code will search the current node and all of its children,
        even the children of other matching nodes. Therefore, the
        method may even return children of other matches, if you
        specify a :py:obj:`recursive` search::

            >>> root = jxmlease.parse(\"\"\"
            ... <a>
            ...   <a>
            ...     <a>foo</a>
            ...     <a>bar</a>
            ...   </a>
            ... </a>\"\"\")
            >>> count = 0
            >>> for i in root.find_nodes_with_tag("a"):
            ...     count += 1
            ...     print("%d: %s" % (count, i))
            ...
            1: {u'a': {u'a': [u'foo', u'bar']}}
            2: {u'a': [u'foo', u'bar']}
            3: foo
            4: bar
            >>> count = 0
            >>> for i in root.find_nodes_with_tag("a", recursive=False):
            ...     count += 1
            ...     print("%d: %s" % (count, i))
            ...
            1: {u'a': {u'a': [u'foo', u'bar']}}

        You can also use a tuple as the tag parameter, in which case
        the method will return nodes with a tag that matches any of
        the given tag values.

        You can use this function to create somewhat complicated logic
        that mimics the functionality from XPath "//tag" matches. For
        example, here we check for <xnm:warning> and <xnm:error> nodes
        and return their value::

            >>> root = jxmlease.parse(\"\"\"\
            ... <foo>
            ...   <xnm:warning>
            ...     <message>This is bad.</message>
            ...   </xnm:warning>
            ...   <bar>
            ...     <xnm:error>
            ...       <message>This is very bad.</message>
            ...     </xnm:error>
            ...   </bar>
            ... </foot>\"\"\")
            >>> if root.has_node_with_tag(('xnm:warning', 'xnm:error')):
            ...   print "Something bad happened."
            ...
            Something bad happened.
            >>> for node in root.find_nodes_with_tag(('xnm:warning', 'xnm:error')):
            ...   if node.tag == 'xnm:error':
            ...     level = "Error:"
            ...   elif node.tag == 'xnm:warning':
            ...     level = "Warning:"
            ...   else:
            ...     level = "Unknown:"
            ...   print(level + " " + node.get("message", "(unknown)"))
            ...
            Warning: This is bad.
            Error: This is very bad.

        Args:
            tag (string or tuple): The XML tag (or tags) for which to search.
            recursive (bool): If True (the default), search recursively through
                all children. If False, only search direct children.

        Returns:
            A generator which iterates over all matching nodes.

        """
        if isinstance(tag, str):
            tag = (tag,)
        return self._find_nodes_with_tag(tuple(tag), recursive=recursive,
                                         top_level=True)

    def _find_nodes_with_tag(self, tag, recursive, top_level):
        raise NotImplementedError()

    def has_node_with_tag(self, tag, recursive=True):
        """Determine whether a node with a matching tag exists.

        This method uses the :py:meth:`find_nodes_with_tag` method to
        search the current node and its children for a node that has a
        matching tag.  The method returns a boolean value to indicate
        whether at least one matching node is found.

        Because this function uses the :py:meth:`find_nodes_with_tag` method,
        the parameters and algorithm are the same as the
        :py:meth:`find_nodes_with_tag` method.

        Args:
            tag (string or tuple): The XML tag (or tags) for which to search.
            recursive (bool): If True (the default), search recursively through
                all children. If False, only search direct children.

        Returns:
            True if at least one matching node is found; otherwise, False.

        """
        for _ in self.find_nodes_with_tag(tag, recursive=recursive):
            return True
        return False

    def __repr__(self):
        return "%s(xml_attrs=%r, value=%s)" % (
            getattr(self, "__const_class_name__", self.__class__.__name__),
            self.xml_attrs, super(XMLNodeBase, self).__repr__()
        )

    def __str__(self):
        io_obj = StringIO()
        self.prettyprint(io_obj)
        return io_obj.getvalue().strip()
