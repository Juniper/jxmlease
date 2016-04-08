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

import sys
from xml.parsers import expat
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl
from copy import copy
try:  # pragma no cover
    from cStringIO import StringIO
except ImportError:  # pragma no cover
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO
try: # pragma no cover
    from io import BytesIO
except ImportError: # pragma no cover
    BytesIO = StringIO
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
        if len(args) > 0:
            stream = args[0]
        else:
            stream = kwargs.get("stream", None)
        if stream is not None:
            stream.write("%r\n" % obj)
        else:
            print("%r" % obj)

QNameDecode = None
try: # pragma no cover
    from lxml import etree
    QNameDecode = etree.QName
except ImportError: # pragma no cover
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
            # Not tested; but, should be the same as cElementTree
        except ImportError:
            try:
                import cElementTree as etree
                print("Warning: Not tested with cElementTree")
            except ImportError:
                try:
                    import elementtree.ElementTree as etree
                    print("Warning: Not tested with elementtree.ElementTree")
                except ImportError:
                    print("Unable to import etree: lxml functionality disabled")

class QNameSeparator():
    def __init__(self, text):
        endidx = text.rfind('}')
        if text[0] != '{' or endidx < 0:
            self.namespace = None
            self.localname = text
        else:
            self.namespace = text[1:endidx]
            self.localname = text[endidx+1:]

if etree and QNameDecode == None: # pragma no cover
    class QNameDecode(QNameSeparator):
        def __init__(self, node):
            QNameSeparator.__init__(self, node.tag)

try:  # pragma no cover
    _basestring = basestring
except NameError:  # pragma no cover
    _basestring = str
try:  # pragma no cover
    _unicode = unicode
except NameError:  # pragma no cover
    _unicode = str
try:  # pragma no cover
    _bytes = bytes
except NameError:  # pragma no cover
    _bytes = str

# While doing processing for a generator, process XML text 1KB at a
# time.
parsing_increment = 1024

# A user can use this to set their custom defaults for parsers.
parser_defaults = {}


__author__ = 'Juniper Networks'
__version__ = '1.0a1'
__license__ = 'MIT'

class _NoArg():
    """Internal Use Only"""
    pass

class OrderedDict(_OrderedDict):
    """Standard OrderedDict class, with a small local modification.

    This module uses the OrderedDict class to maintain ordering
    of the input data.
    """

    def __repr__(self, _repr_running={}):
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
        except:
            rv = _OrderedDict.__repr__(self)
        finally:
            self.__class__.__name__ = temp
        return rv

class _XMLNodeMetaClass(type):
    """Internal Use Only"""
    def __new__(cls, name, bases, dict):
        # Record parent class for later use.
        dict["__parent_class__"] = bases[-1]

        # Handle doc string inheritance. This is all a fancy way of
        # inheriting doc strings from earlier classes. It will only
        # overwrite doc strings if they are not already set.
        for k in dict:
            if hasattr(dict[k], '__call__') and not dict[k].__doc__:
                try:
                    if hasattr(XMLNodeBase, k):
                        dict[k].__doc__ = getattr(XMLNodeBase, k).__doc__
                except:
                    pass

        if '__init__' in dict and not dict['__init__'].__doc__:
            dict['__init__'].__doc__ = """Initialize an %s object.
            
            See the class documentation for initializer arguments.
            """ % (name,)
        if not '__doc__' in dict:
            dict['__doc__'] = """Initialize an %s object.
            
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
                xml_attrs (dict): The XML attributes for the node.
                text (string): The node's initial CDATA value. (Note
                    that this is ignored for :py:class:`XMLCDATANode` objects.)
                parent (Instance of a sub-class of :py:class:`XMLNodeBase`): A
                    reference to the object's parent node in the data structure.
                convert (bool): If True, the :py:meth:`convert` method is run on
                    the object's children during object initialization.
                deep (bool): If True (and the :py:obj:`convert` parameter is
                    True), the :py:meth:`convert` method is run recursively
                    on the object's children during object initialization.
            """ % (name, name)
        # Create and return the class.
        return type.__new__(cls, name, bases, dict)

    def __call__(self, *args, **kwargs):
        # Determine if we were called with an initial value. If so,
        # make sure there was only *one* initial value.
        initializer = kwargs.pop("initializer", _NoArg())
        if not isinstance(initializer, _NoArg):
            if len(args) > 0:
                raise TypeError("got multiple values for keyword "
                                "argument 'initializer'")
            args.append(initializer)
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

        # Create the object.
        obj = type.__call__(self, *args, **kwargs)

        # Add attributes to the object.
        obj.tag = tag
        obj.key = copy(key)
        obj.xml_attrs = OrderedDict()
        for k in xml_attrs:
            obj.xml_attrs[k] = _unicode(xml_attrs[k])
        if not hasattr(obj, "text"):
            obj.text = node_text
        obj.parent = parent_node
        obj._replacement_node = None
        if convert:
            obj.standardize(deep=deep)
        return obj


# The below is Python 2/3 Portable equivalent to
#   class XMLNodeMetaClass(object, metaclass=_XMLNodeMetaClass):
#       pass
if sys.version_info[0] >= 3:
    _temp_class_dict = {'__module__': _XMLNodeMetaClass.__module__,
                        '__qualname__': 'XMLNodeMetaClass'}
else:
    _temp_class_dict = {'__module__': _XMLNodeMetaClass.__module__,
                        '__metaclass__': _XMLNodeMetaClass}

XMLNodeMetaClass = _XMLNodeMetaClass(str("XMLNodeMetaClass"),
                                     (object,), _temp_class_dict)

del _temp_class_dict

class XMLNodeBase(XMLNodeMetaClass):
    """This module provides methods common to the XML node classes.

    This modules is not intended for standalone use.
    """

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
            except:
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
            except:
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
        except:
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
        except:
            pass
        raise AttributeError("Unable to find existing node in parent")

    def dict(self, attrs=[], tags=[], func=None, in_place=False,
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
            attrs (list): The list of XML attributes that signal a node
                should be used as a key.
            tags (list): The list of XML tags that signal a node should be used
                as a key.
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
                newlist._replace_node(self)
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
                     indent='    ', full_document=_NoArg()):
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
        if not isinstance(full_document, _NoArg):
            # Make sure there is only one root in a "full" document.
            if (full_document and isinstance(self, XMLListNode) and
                    len(self) > 1):
                raise ValueError("Document will have more than one root node. "
                                 "The full_document argument must be False.")
        elif isinstance(self, XMLListNode) and len(self) > 1:
            # We have multiple tags. We cannot be a full document.
            full_document = False
        elif (self.tag is None and
              isinstance(self, (XMLDictNode, XMLListNode)) and
              len(self) <= 1):
            # We are the root. We have a single root tag.
            full_document = True
        elif (isinstance(self.tag, (_unicode, str)) and
              (self.parent is None or
               (self.parent.tag is None and len(self.parent) == 1))):
            # We look like the only child of the root node. In other words,
            # we look like the root tag. Treat us as a full document.
            full_document = True
        else:
            # We don't appear to be the root, or it appears there is a multi-
            # member root.
            full_document = False

        if full_document:
            content_handler.startDocument()
        self._emit_handler(content_handler, depth=0, pretty=pretty, newl=newl,
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

        **NOTE**: This documentation needs to be updated to take into
        account the changes to list handling and always checking the
        current node's tag.

        This method searches for a node that is a descendant of the
        current node and has a matching tag. Optionally (by providing
        a False value to the :py:obj:`recursive` parameter), you can limit
        the search to direct children of the current node. In either
        case, the tag of the current node is not checked.

        For example, this will print all "name" nodes from the XML
        snippet that is shown::

            >>> root = jxmlease.parse(\"\"\"\
            ... <?xml version="1.0" encoding="utf-8"?>
            ... <name>
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
            ... </name>\"\"\")
            >>> print root
            {u'name': {u'a': {u'b': [{u'name': u'name #2'},
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
            >>> for node in root['name']['a'].find_nodes_with_tag('name', recursive=False):
            ...   print node
            ...
            name #1

        If you run this against an :py:class:`XMLDictNode` without a tag (for
        example, the tagless root node), then the command is run on
        each member of the dictionary. The impact of this is that it
        will search for tags in the grandchildren of the tagless
        :py:class:`XMLDictNode`, rather than searching the children of the
        tagless :py:class:`XMLDictNode`::

            >>> root = jxmlease.parse("<name>top-level tag</name>")
            >>> for i in root.find_nodes_with_tag('name'):
            ...   print i
            ...
            >>> root = jxmlease.parse(\"\"\"\
            ... <a>
            ...   <name>second-level tag</name>
            ... </a>\"\"\")
            >>> for i in root.find_nodes_with_tag('name'):
            ...   print i
            ...
            second-level tag

        If the current node is a list and it appears that the list was
        created to hold multiple elements with the same tag, then the
        command is run on each member of the list (rather than on the
        list itself). The impact of this is that it will search for
        tags in the grandchildren of the :py:class:`XMLListNode`, rather
        than searching the children of the :py:class:`XMLListNode`.

        As confusing as this may sound, the point is simple: we never
        check the tag of the "current" element. Because lists can be
        homogenous or heterogenous, that statement is ambiguous for
        lists. We resolve the ambiguity by comparing the tag stored
        with the list and the tag of the children.

        For example, here is a root node with two top-level "name"
        elements. Searching for the "name" tag does not find these
        top-level elements because both the top-level dictionary and
        top-level list pass through the search::

            >>> root = XMLDictNode()
            >>> _ = root.add_node(tag='name', text='tag #1')
            >>> _ = root.add_node(tag='name', text='tag #2')
            >>> print root
            {'name': [u'tag #1', u'tag #2']}
            >>> for i in root.find_nodes_with_tag('name'):
            ...   print i
            ...
            >>>

        On the other hand, we create a root :py:class:`XMLListNode` and add
        two name tags to it. Because the :py:class:`XMLListNode` has no internal
        representation of its tag, it checks for matches in its
        children. Note that you shouldn't really create XML trees this
        way; rather, you should always have an XMLDictNode as the
        root. However, this shows the concept::

            >>> badroot = XMLListNode()
            >>> badroot.append(XMLCDATANode('tag #1', tag='name'))
            >>> badroot.append(XMLCDATANode('tag #2', tag='name'))
            >>> print badroot
            [u'tag #1', u'tag #2']
            >>> print root.emit_xml()
            <name>tag #1</name>
            <name>tag #2</name>
            >>> for i in badroot.find_nodes_with_tag('name'):
            ...   print i
            ...
            tag #1
            tag #2

        Also, note that this method returns the actual node::

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

        Once a given node matches, the method does not check that
        node's children.

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

        This method uses the :py:meth:`find_nodes_with_tag` method to search
        for a node that is a child of the current node and has a
        matching tag. The tag of the current node is not checked. The
        method returns a boolean value to indicate whether at least
        one matching node is found.

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
        for node in self.find_nodes_with_tag(tag, recursive=recursive):
            return True
        return False

    def __repr__(self):
        return "%s(xml_attrs=%r, value=%s)" % (
            getattr(self, "__const_class_name__", self.__class__.__name__),
            self.xml_attrs, self.__parent_class__.__repr__(self)
        )

    def __str__(self):
        io_obj = StringIO()
        self.prettyprint(io_obj)
        return io_obj.getvalue().strip()


class XMLCDATANode(XMLNodeBase, _unicode):
    def __init__(self, *args, **kwargs):
        self.text = self
        _unicode.__init__(self)

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
        newobj = self.__parent_class__(self)
        if currdepth == 0:
            pprint(newobj, *args, **kwargs)
        else:
            return newobj

    def _find_nodes_with_tag(self, tag, recursive=True, top_level=False):
        if self.tag in tag:
            yield self

    def __str__(self):
        return self.__parent_class__.__str__(self)

def _get_dict_value_iter(arg, descr="node"):
    if isinstance(arg, XMLDictNode):
        try:
            # Python 2
            return arg.itervalues()
        except:
            # Python 3
            return arg.values()
    elif isinstance(arg, XMLCDATANode):
        return [arg]
    else:
        raise TypeError("Unexpected type %s for %s" % (str(type(arg)), descr))

class XMLListNode(XMLNodeBase, list):
    def add_node(self, *args, **kwargs):
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

    def dict(self, attrs=[], tags=[], func=None, in_place=False,
             promote=False):
        class KeyBuilder(object):
            def __init__(self, matches):
                if isinstance(matches, (tuple, list)):
                    self.key_list = list(matches)
                    self.tuple = True
                else:
                    self.key_list = [matches]
                    self.tuple = False
                self.value_list = [None for i in range(0, len(self.key_list))]

            def eval_key(self, key_list, val):
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
                if not (node.tag):
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

class XMLDictNode(XMLNodeBase, OrderedDict):
    def __init__(self, *args, **kwargs):
        self.__const_class_name__ = self.__class__.__name__
        self._ignore_level = False
        OrderedDict.__init__(self, *args, **kwargs)

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
            yield self
        elif recursive or top_level:
            for node in self.values():
                kwargs = {'recursive': recursive}
                # Pass through the top_level arg, if appropriate.
                if pass_through:
                    kwargs['top_level'] = top_level
                for item in node._find_nodes_with_tag(tag, **kwargs):
                    yield item

class _GeneratorMatch(object):
    # Essentially, a data structure used to hold information on matches.
    def __init__(self, rooted=False, elements=[], depth=0, match_string=""):
        self.rooted = rooted
        self.elements = elements
        self.depth = depth
        self.match_string = match_string

class _DictSAXHandler(object):
    # A handler for SAX events.
    # parameters are documented under the Parser class.
    def __init__(self,
                 xml_attribs=True,
                 strip_whitespace=True,
                 namespace_separator=_unicode(':'),
                 namespaces=None,
                 strip_namespace=False,
                 cdata_separator=_unicode(''),
                 generator=[]):
        self.path = []
        self.stack = []
        self.matches = []
        self.root = XMLDictNode()
        self.item = self.root
        self.item_depth = 0
        self.xml_attribs = xml_attribs
        self.strip_whitespace = strip_whitespace
        self.namespace_separator = namespace_separator
        self.namespaces = namespaces
        self.strip_namespace = strip_namespace
        self.match_tests = []
        self.matches = []
        if isinstance(generator, str):
            self.match_tests.append(self._parse_generator_matches(generator))
        else:
            for i in generator:
                self.match_tests.append(self._parse_generator_matches(i))
        if len(self.match_tests) > 0:
            self.match_depth = 1000000 # effectively, infinity
            for match in self.match_tests:
                if match.depth < self.match_depth:
                    self.match_depth = match.depth
        else:
            self.match_depth = -1
        if self.match_depth > 0:
            self.in_ignore = True
        else:
            self.in_ignore = False
        self.cdata_separator = cdata_separator
        self.need_cdata_separator = False

    def _parse_generator_matches(self, match_string):
        match_obj = _GeneratorMatch(match_string=match_string)
        parsed_match_string = match_string.split("/")

        # Determine if we had a leading slash
        if parsed_match_string[0] == "":
            match_obj.rooted = True
            del parsed_match_string[0]

        # Pop a single trailing slash
        if parsed_match_string[-1] == "":
            del parsed_match_string[-1]

        # Verify there are no other empty elements.
        for i in parsed_match_string:
            if i == "":
                raise Warning(
                    "Match condition contains empty path elements (%s)" %
                    (match_string,)
                    )
        # Get the depth and the element list.
        match_obj.depth = len(parsed_match_string)
        match_obj.elements = parsed_match_string

        return match_obj

    def _check_generator_matches(self):
        if self.match_depth > len(self.path):
            return
        for match in self.match_tests:
            if match.rooted and len(self.path) != match.depth:
                continue
            if not(match.rooted) and len(self.path) < match.depth:
                continue
            if match.elements == self.path[-match.depth:]:
                path = '/'.join([""] + self.path)
                if path == "":
                    path = _unicode('/')
                self.matches.append((path, match.match_string, self.item))
                break

    def _build_name(self, full_name):
        if (not self.namespaces) and (not self.strip_namespace):
            return full_name
        i = full_name.rfind(self.namespace_separator)
        if i == -1:
            return full_name
        namespace, name = full_name[:i], full_name[i+1:]
        if self.strip_namespace:
            return name
        short_namespace = self.namespaces.get(namespace, namespace)
        if not short_namespace:
            return name
        else:
            return self.namespace_separator.join((short_namespace, name))

    def _attrs_to_dict(self, attrs):
        if isinstance(attrs, dict):
            rv = attrs
        else:
            rv = OrderedDict(zip(attrs[0::2], attrs[1::2]))
        if self.strip_namespace:
            for k in list(rv.keys()):
                if k == "xmlns" or k.startswith("xmlns" +
                                                self.namespace_separator):
                    del rv[k]
            for k in list(rv.keys()):
                if k.rfind(self.namespace_separator) >= 0:
                    newkey = k[k.rfind(self.namespace_separator) + 1:]
                    if newkey in rv:
                        raise ValueError("Stripping namespace causes duplicate "
                                         "attribute \"%s\"" % newkey)
                    rv[newkey] = rv[k]
                    del rv[k]
        return rv

    def start_element(self, full_name, attrs):
        name = self._build_name(full_name)
        attrs = self._attrs_to_dict(attrs)
        self.path.append(name)
        if self.xml_attribs:
            attrs = OrderedDict(
                (self._build_name(key), value)
                for (key, value) in attrs.items()
            )
        else:
            attrs = OrderedDict()
        if self.in_ignore and len(self.path) >= self.match_depth:
            # We were ignoring lower levels of the hierarchy. Get a new
            # root.
            self.item = XMLDictNode()
            self.in_ignore = False

        if not self.in_ignore:
            # Add a new item
            newnode = self.item.add_node(name, xml_attrs=attrs)
            # Save the old item (which may have been updated).
            self.stack.append(self.item.get_current_node())
            # Change the current focus to the new item.
            self.item = newnode
            # We don't need a CDATA separator when starting an item.
            self.need_cdata_separator = False

    def end_element(self, full_name):
        if not self.in_ignore:
            if self.strip_whitespace:
                self.item = self.item.strip_cdata(return_node=True)
            self._check_generator_matches()
            self.item = self.stack.pop()

        self.path.pop()
        if len(self.path) < self.match_depth:
            self.in_ignore = True

        if not self.in_ignore:
            # We may need a CDATA separator when ending an item.
            if len(self.item.get_cdata()) > 0:
                self.need_cdata_separator = True

    def characters(self, data):
        if not self.in_ignore:
            if self.need_cdata_separator:
                data = self.cdata_separator + data
                self.need_cdata_separator = False
            self.item = self.item.append_cdata(data, return_node=True)

    def end_document(self):
        assert len(self.path) == 0, "endDocument() called with open elements"
        self._check_generator_matches()

    def pop_matches(self):
        rv = self.matches
        self.matches = []
        return rv

class Parser(object):
    """Creates Python data structures from raw XML.

    This class creates a callable object used to parse XML into Python data
    structures. You can provide optional parameters at the class creation time.
    These parameters modify the default behavior of the parser. When you invoke
    the callable object to parse a document, you can supply additional
    parameters to override the values specified when the :py:class:`Parser`
    object was created.

    General usage is::

        >>> myparser = Parser()
        >>> root = myparser("<a>foo</a>")

    Calling a :py:class:`Parser` object returns an :py:class:`XMLDictNode`
    containing the parsed XML tree.

    In this example, ``root`` is an :py:class:`XMLDictNode` which contains a
    representation of the parsed XML::

        >>> isinstance(root, XMLDictNode)
        True
        >>> root.prettyprint()
        {u'a': u'foo'}
        >>> print root.emit_xml()
        <?xml version="1.0" encoding="utf-8"?>
        <a>foo</a>

    If you will just be using a parser once, you can just use the
    :py:meth:`parse` method, which is a shortcut way of creating a
    :py:class:`Parser` class and calling it all in one call. You can provide
    the same arguments to the :py:meth:`parse` method that you provide to the
    :py:class:`Parser` class.

    For example::

          >>> root = jxmlease.parse('<a x="y"><b>1</b><b>2</b><b>3</b></a>')
          >>> root.prettyprint()
          {u'a': {u'b': [u'1', u'2', u'3']}}

    It is possible to call a :py:class:`Parser` object as a generator by
    specifying the :py:obj:`generator` parameter. The :py:obj:`generator`
    parameter contains a list of paths to match. If paths are provided in this
    parameter, the behavior of the parser is changed. Instead of returning the
    root node of a parsed XML hierarchy, the parser returns a generator object.
    On each call to the generator object, it will return the next node that
    matches one of the provided paths.

    Paths are provided in a format similar to XPath expressions. For example,
    ``/a/b`` will match node ``<b>`` in this XML::

        <a>
            <b/>
        </a>

    If a path begins with a ``/``, it must exactly match the full path to a
    node. If a path does not begin with a ``/``, it must exactly match the
    "right side" of the path to a node. For example, consider this XML::

        <a>
            <b>
                <c/>
            </b>
        </a>

    In this example, ``/a/b/c``, ``c``, ``b/c``, and ``a/b/c`` all match the
    ``<c>`` node.

    For each match, the generator returns a tuple of:
    ``(path,match_string,xml_node)``, where the *path* is
    the calculated absolute path to the matching node, *match_string* is the
    user-supplied match string that triggered the match, and *xml_node* is the
    object representing that node (an instance of a :py:class:`XMLNodeBase`
    subclass).

    For example::

        >>> xml = '<a x="y"><b>1</b><b>2</b><b>3</b></a>'
        >>> myparser = Parser(generator=["/a/b"])
        >>> for (path, match, value) in myparser(xml):
        ...   print "%s: %s" % (path, value)
        ...
        /a/b: 1
        /a/b: 2
        /a/b: 3

    When calling the parser, you can specify all of these parameters. When
    creating a parsing instance, you can specify all of these parameters
    except :py:obj:`xml_input`:

    Args:
	xml_input (stirng or file-like object): Ccontains the XML to parse.
	encoding (string or None): The input's encoding. If not provided, this
            defaults to 'utf-8'.
        expat (An expat, or equivalent, parser class): Used for parsing the XML
            input. If not provided, defaults to the expat parser in
            :py:data:`xml.parsers`.
        process_namespaces (bool): If True, namespaces in tags and attributes
            are converted to their full URL value. If False (the default), the
            namespaces in tags and attributes are left unchanged.
	namespace_separator (string): If :py:obj:`process_namespaces` is True,
            this specifies the separator that expat should use between
            namespaces and identifiers in tags and attributes
	xml_attribs (bool): If True (the default), include XML attributes.
            If False, ignore them.
        strip_whitespace (bool): If True (the default), strip whitespace
            at the start and end of CDATA. If False, keep all whitespace.
        namespaces (dict): A remapping for namespaces. If supplied, identifiers
            with a namespace prefix will have their namespace prefix rewritten
            based on the dictionary. The code will look for
            :py:obj:`namespaces[current_namespace]`. If found,
            :py:obj:`current_namespace` will be replaced with the result of
            the lookup.
        strip_namespace (bool): If True, the namespace prefix will be
            removed from all identifiers. If False (the default), the namespace
            prefix will be retained.
        cdata_separator (string): When encountering "semi-structured" XML
            (where the XML has CDATA and tags intermixed at the same level), the
            :py:obj:`cdata_separator` will be placed between the different
            groups of CDATA. By default, the :py:obj:`cdata_separator`
            parameter is '', which results in the CDATA groups being
            concatenated without separator.
        generator (list of strings): A list of paths to match. If paths are
            provided here, the behavior of the parser is changed. Instead of
            returning the root node of a parsed XML hierarchy, the parser
            returns a :py:obj:`generator` object. On each call to the
            :py:obj:`generator` object, it will return the next node that
            matches one of the provided paths.

    Returns:
        A callable instance of the :py:class:`Parser` class.

        Calling a :py:class:`Parser` object returns an :py:class:`XMLDictNode`
        containing the parsed XML tree.

        Alternatively, if the :py:obj:`generator` parameter is specified, a
        :py:obj:`generator` object is returned.

    """

    def __init__(self, **kwargs):
        """See class documentation."""
        # Populate a dictionary with default arguments.
        self._default_kwargs = dict(encoding=None, expat=expat,
                                    process_namespaces=False,
                                    namespace_separator=":")

        # Update the dictionary with user-provided defaults.
        self._default_kwargs.update(parser_defaults)

        # Update the dictionary with the provided arguments. We will save
        # the arguments for later use.
        self._default_kwargs.update(kwargs)

        # Process the arguments.
        self._process_args()

        # Make a default handler, which will also try the arguments to catch
        # argument errors now.
        self._make_handler()

        # Try the arguments to catch argument errors now. We will
        # throw this one away (as the encoding is unpredictable).
        if not self._encoding:
            self._encoding = 'utf-8'
        self._make_parser()

        # Stash the handler for future use.
        self._default_handler = self._handler
        self._handler = None

    def _process_args(self, **kwargs):
        # Make a copy of the default kwargs database.
        self._kwargs = dict(self._default_kwargs)

        # Update the dictionary with the provided arguments.
        self._kwargs.update(kwargs)

        # Pop off and save the arguments that we don't want to pass to
        # the handler class.
        self._encoding = self._kwargs.pop('encoding')
        self._expat = self._kwargs.pop('expat')
        self._process_namespaces = self._kwargs.pop('process_namespaces')

    def _make_handler(self):
        self._handler = _DictSAXHandler(**self._kwargs)

    def _make_parser(self):
        # We don't need a namespace separator if we're not processing
        # namespaces.
        if not self._process_namespaces:
            namespace_separator = None
        else:
            namespace_separator = self._kwargs['namespace_separator']
        self._parser = self._expat.ParserCreate(
            self._encoding, namespace_separator
        )

        # Setup some parser attributes
        self._parser.buffer_text = True
        try:
            self._parser.ordered_attributes = True
        except AttributeError: # pragma no cover
            # Jython's expat does not support ordered_attributes
            pass

        # Assign the handler methods to the parser
        self._parser.StartElementHandler = self._handler.start_element
        self._parser.EndElementHandler = self._handler.end_element
        self._parser.CharacterDataHandler = self._handler.characters

    def _parse_generator(self, xml_input):
        if isinstance(xml_input, (str, _unicode)):
            io_obj = StringIO(xml_input)
        elif isinstance(xml_input, _bytes):
            io_obj = BytesIO(xml_input)
        else:
            io_obj = xml_input

        at_eof = False
        while not at_eof:
            buf = io_obj.read(parsing_increment)
            if len(buf) == 0:
                at_eof = True
            try:
                self._parser.Parse(buf, at_eof)
            except expat.ExpatError:
                # Note: "except expat.ExpatError as e" is not
                # supported in older Python version. Once support for
                # those versions is deprecated, we should consider
                # changing this to the more standard syntax.
                e = sys.exc_info()[1]

                # If the only error was parsing an empty document, ignore
                # the error and return the empty dictionary.
                raise_error = True
                if (hasattr(expat, "errors") and
                        hasattr(expat.errors, "XML_ERROR_NO_ELEMENTS") and
                        at_eof):
                    if str(e).startswith(expat.errors.XML_ERROR_NO_ELEMENTS +
                                         ":"):
                        raise_error = False

                # If needed, raise the error
                if raise_error:
                    raise

            if at_eof:
                self._handler.end_document()
            for rv in self._handler.pop_matches():
                yield rv

    def __call__(self, xml_input, **kwargs):
        """See class documentation."""
        # Make a copy of the default arguments and update that copy with
        # our new arguments.
        self._process_args(**kwargs)

        # Did we get keyword arguments? If so, we need to recreate the
        # default handler. Otherwise, we can try to use it (if the default
        # parser exists).
        if len(kwargs) == 0 and self._default_handler is not None:
            self._handler = self._default_handler
            self._default_handler = None
        else:
            self._make_handler()

        # Make sure our unicode text (if any) is properly encoded.
        if isinstance(xml_input, _unicode):
            if not self._encoding:
                self._encoding = 'utf-8'
            xml_input = xml_input.encode(self._encoding)

        # Create our parser.
        self._make_parser()

        # Do the actual parsing.
        if self._kwargs.get("generator", False):
            return self._parse_generator(xml_input)
        else:
            try:
                if isinstance(xml_input, (str, _unicode, _bytes)):
                    self._parser.Parse(xml_input, True)
                else:
                    self._parser.ParseFile(xml_input)
            except expat.ExpatError:
                # Note: "except expat.ExpatError as e" is not
                # supported in older Python version. Once support for
                # those versions is deprecated, we should consider
                # changing this to the more standard syntax.
                e = sys.exc_info()[1]

                # If the only error was parsing an empty document, ignore
                # the error and return the empty dictionary.
                raise_error = True
                if (hasattr(expat, "errors") and
                        hasattr(expat.errors, "XML_ERROR_NO_ELEMENTS")):
                    if str(e).startswith(expat.errors.XML_ERROR_NO_ELEMENTS +
                                         ":"):
                        raise_error = False

                # If needed, raise the error
                if raise_error:
                    raise

        return self._handler.item

def parse(xml_input, **kwargs):
    """Create Python data structures from raw XML.

    See the :py:class:`Parser` class documentation."""
    return Parser(**kwargs)(xml_input)

if etree:
    class NamespaceError(ValueError):
        def __init__(self, namespace):
            self.namespace = namespace
        def __str__(self):
            return "Namespace \"%s\" not found in namespace store." % (
                self.namespace
                )
        def __repr__(self):
            return "%s(namespace=%s)" % (self.__class__.__name__,
                                         self.namespace)

    class EtreeParser(object):
        """Creates Python data structures from an ElementTree object.

        This class returns a callable object. You can provide parameters at
        the class creation time. These parameters modify the default
        parameters for the parser. When you call the callable object to
        parse a document, you can supply additional parameters to override
        the default values.

        General usage is like this::

            >>> myparser = Parser()
            >>> root = myparser(etree_root)

        For detailed usage information, please see the :py:class`Parser`
        class. Other than the differences noted below, the behavior of
        the two classes should be the same.

        Namespace Identifiers:

        In certain versions of :py:mod:`ElementTree`, the original namespace
        identifiers are not maintained. In these cases, the class will recreate
        namespace identfiers to represent the original namespaces. It will add
        appropriate xmlns attributes to maintain the original namespace
        mapping. However, the actual identifier will be lost. As best I can
        tell, this is a bug with :py:mod:`ElementTree`, rather than this code.
        To avoid this problem, use :py:mod:`lxml`.

        Single-invocation Parsing:

        If you will just be using a parser once, you can just use the
        :py:meth:`parse_etree` method, which is a shortcut way of creating a
        :py:class:`EtreeParser` class and calling it all in one call. You
        can provide the same arguments to the :py:meth:`parse_etree` method
        that you can provide to the :py:class:`EtreeParser` class.

        Args:
            etree_root (:py:class:`ElementTree`): An :py:class:`ElementTree`
                object representing the tree you wish to parse.

        Also accepts most of the same arguments as the :py:class:`Parser` class.
        However, it does not accept the :py:obj:`xml_input`, :py:obj:`expat`,
        or :py:obj:`encoding` parameters.

        """

        def __init__(self, **kwargs):
            """See the class documentation."""
            # Populate a dictionary with default arguments.
            self._default_kwargs = dict(process_namespaces=False,
                                        namespace_separator=':',
                                        strip_namespace=False)

            # Update the dictionary with user-provided defaults, after
            # stripping out arguments not appropriate for this
            # context.
            local_parser_defaults = parser_defaults
            for k in ('encoding', 'expat'):
                if k in local_parser_defaults:
                    del local_parser_defaults[k]
            self._default_kwargs.update(local_parser_defaults)

            # Update the dictionary with the provided arguments. We will save
            # the arguments for later use.
            self._default_kwargs.update(kwargs)

            # Process the arguments.
            self._process_args()

            # Make a default handler, which will also try the arguments to
            # catch argument errors now.
            self._make_handler()

            # Stash the handler for future use.
            self._default_handler = self._handler
            self._handler = None

        def _process_args(self, **kwargs):
            # Make a copy of the default kwargs database.
            self._kwargs = dict(self._default_kwargs)

            # Update the dictionary with the provided arguments.
            self._kwargs.update(kwargs)

            # Pop off and save the argument(s) that we don't want to pass
            # to the handler class.
            self._process_namespaces = self._kwargs.pop('process_namespaces')

            # Get local versions of the arguments we want.
            self._namespace_separator = self._kwargs['namespace_separator']
            self._strip_namespace = self._kwargs['strip_namespace']

        def _make_handler(self):
            self._handler = _DictSAXHandler(**self._kwargs)

        def _parse(self, node):
            # Initialize the namespace_dict. We use this to store locally-
            # generated namespace mappings if the originals are lost.
            self._namespace_dict = {'nexttag': _unicode('ns0')}

            # Call the main parsing function
            return self._parse_node(node, root_element=True)

        def _parse_attrib(self, in_dict, out_dict, nsdict):
            for (k, v) in list(in_dict.items()):
                parsed_attr = QNameSeparator(k)
                if not parsed_attr.namespace:
                    out_dict[k] = v
                    del in_dict[k]
                else:
                    try:
                        new_ns = nsdict[parsed_attr.namespace]
                    except KeyError:
                        raise NamespaceError(parsed_attr.namespace)
                    new_k = self._namespace_separator.join(
                        (new_ns,
                         parsed_attr.localname)
                    )
                    out_dict[new_k] = v
                    del in_dict[k]

        def _parse_node(self, node, local_nsdict=None, root_element=False):
            # Parsing LXML/ElementTree is actually quite simple. We
            # can just recursively call this function to walk through
            # the tree of elements and call the same handler we use
            # for parsing the text version through a SAX parser.
            # Almost all of the complexity is handling the namespaces.

            # Make a local copy of the namespace dict. This lets us
            # track whether we need to add xmlns attributes to lower
            # levels.
            if local_nsdict is None:
                local_nsdict = self._namespace_dict
            local_nsdict = dict(local_nsdict)

            # Ignore processing instructions and comments.
            if node.tag not in (etree.PI, etree.Comment):
                # Figure out NS:
                # If 'strip_namespace' or 'process_namespaces' are set, we
                # can do the same thing. In these cases, we just care about
                # making sure the attributes and tags are formed correctly so
                # that the handler will do the correct thing. In general, our
                # goal is to emulate what the expat processor would do if
                # process_namespaces was set to True.
                #
                # Otherwise, try to restore the original nodename ("ns:tag")
                # and XMLNS attributes. (Again, this emulates what the expat
                # processor would do.) If we've lost the original
                # namespace identifiers, make up our own.
                if self._strip_namespace or self._process_namespaces:
                    parsed_tag = QNameDecode(node)
                    if not parsed_tag.namespace:
                        tag = parsed_tag.localname
                    else:
                        tag = self._namespace_separator.join(
                            (parsed_tag.namespace, parsed_tag.localname)
                        )

                    # Fix the attributes. Just paste them together with
                    # the namespace separator. The standard parsing code
                    # can handle them further. (In the case where
                    # strip_namespace is set, it can check for name
                    # conflicts (e.g.  <a a:attr1="" b:attr1=""
                    # c:attr1=""/>). That is the reason we don't strip
                    # them out here when strip_namespace is true. It seems
                    # best to have the logic in a single place.
                    attrib = dict()
                    for (k, v) in node.attrib.items():
                        parsed_attr = QNameSeparator(k)
                        if not parsed_attr.namespace:
                            attrib[k] = v
                        else:
                            new_k = self._namespace_separator.join(
                                (parsed_attr.namespace,
                                 parsed_attr.localname)
                            )
                            attrib[new_k] = v

                elif hasattr(node, 'nsmap') and len(node.nsmap) == 0:
                    # If nsmap is present (lxml) and it is 0, then we
                    # should have no namespace information to process.
                    # If nsmap is present and it is greater than 0,
                    # then we want to process the namespace information,
                    # even if all we do is create proper xmlns attributes.
                    tag = node.tag
                    attrib = dict(node.attrib)
                else:
                    # If the node has the nsmap attribute, reverse it to
                    # create a namespace lookup dictionary for us.
                    if hasattr(node, 'nsmap'):
                        ns_resolve_dict = dict(zip(node.nsmap.values(),
                                                   node.nsmap.keys()))
                    # If the node doesn't have the nsmap attribute, all NS
                    # identfiers are lost. We can recreate them with
                    # locally-generated identifiers, which we store in the
                    # namespace_dict.
                    else:
                        ns_resolve_dict = local_nsdict

                    # Initialize the new attributes
                    attrib = dict()

                    # Determine if we need to add a namespace to the tag.
                    parsed_tag = QNameDecode(node)
                    if ((not parsed_tag.namespace) or
                        (not ns_resolve_dict.get(parsed_tag.namespace,
                                                 '@@NOMATCH@@'))):
                        tag = parsed_tag.localname
                    else:
                        # If the namespace isn't in our resolver dictionary,
                        # add it to the namespace_dict. Note that this
                        # will not work correctly if the node had an nsmap.
                        # It isn't supposed to work correctly in that case.
                        # If the tag uses a namespace that isn't in the
                        # nsmap, that seems like a bug.
                        if parsed_tag.namespace not in ns_resolve_dict:
                            # If we've already seen this in a sibling branch,
                            # use a consistent NS identifier. Otherwise, add
                            # the identifier to the main database.
                            if parsed_tag.namespace in self._namespace_dict:
                                newns = self._namespace_dict[parsed_tag.namespacein]
                            else:
                                newns = self._namespace_dict['nexttag']
                                self._namespace_dict[parsed_tag.namespace] = newns
                                self._namespace_dict['nexttag'] = _unicode(
                                    "ns%d" % (int(newns[2:]) + 1, )
                                )
                            # Add the identifier to the local database, and
                            # add an xmlns: attribute to cover this branch.
                            ns_resolve_dict[parsed_tag.namespace] = newns
                            attrib[_unicode("xmlns:" + newns)] = parsed_tag.namespace
                        tag = self._namespace_separator.join(
                            (ns_resolve_dict[parsed_tag.namespace],
                             parsed_tag.localname)
                        )

                    # Deal with the attributes.
                    old_attrib = dict(node.attrib)
                    while len(old_attrib) > 0:
                        try:
                            self._parse_attrib(
                                old_attrib, attrib, ns_resolve_dict
                            )
                        except NamespaceError:
                            # NOTE: "except NamespaceError as e" is not
                            # supported in older Python versions. Once
                            # support for those versions is deprecated, we
                            # should consider changing this to the more
                            # standard syntax.
                            e = sys.exc_info()[1]
                            if hasattr(node, 'nsmap'):
                                raise

                            # If we've already seen this in a sibling branch,
                            # use a consistent NS identifier. Otherwise, add
                            # the identifier to the main database.
                            if e.namespace in self._namespace_dict:
                                newns = self._namespace_dict[e.namespace]
                            else:
                                newns = self._namespace_dict['nexttag']
                                self._namespace_dict[e.namespace] = newns
                                self._namespace_dict['nexttag'] = _unicode(
                                    "ns%d" % (int(newns[2:]) + 1, )
                                )

                            # Add the identifier to the local database, and
                            # add an xmlns: attribute to cover this branch.
                            ns_resolve_dict[e.namespace] = newns
                            attrib[_unicode("xmlns:" + newns)] = e.namespace

                    # Add any necessary xmlns tags.
                    if hasattr(node, "nsmap"):
                        if root_element:
                            parent_nsmap = {}
                        else:
                            parent_nsmap = node.getparent().nsmap
                        for (k, v) in node.nsmap.items():
                            if parent_nsmap.get(k, '@@NOMATCH@@') != v:
                                if k:
                                    attrib[_unicode("xmlns:" + k)] = v
                                else:
                                    attrib[_unicode("xmlns")] = v

                self._handler.start_element(tag, attrib)
                if node.text and len(node.text) > 0:
                    self._handler.characters(node.text)
                for child in node:
                    for rv in self._parse_node(child, local_nsdict):
                        yield rv
                    for rv in self._handler.pop_matches():
                        yield rv
                self._handler.end_element(tag)
            if (not root_element) and node.tail and len(node.tail) > 0:
                self._handler.characters(node.tail)
            if root_element:
                self._handler.end_document()
                for rv in self._handler.pop_matches():
                    yield rv

        def __call__(self, etree_root, **kwargs):
            """See the class documentation."""
            # Make a copy of the default arguments and update that copy with
            # our new arguments.
            self._process_args(**kwargs)

            # Did we get keyword arguments? If so, we need to recreate the
            # default handler. Otherwise, we can try to use it (if the default
            # parser exists).
            if len(kwargs) == 0 and self._default_handler is not None:
                self._handler = self._default_handler
                self._default_handler = None
            else:
                self._make_handler()

            # Figure out which node we should hand to the parser.
            try:
                if isinstance(etree_root, etree._ElementTree):
                    etree_root = etree_root.getroot()
            except:
                try:
                    if isinstance(etree_root, etree.ElementTree):
                        etree_root = etree_root.getroot()
                except:
                    if not hasattr(etree_root, 'tag'):
                        etree_root = etree_root.getroot()

            # Get the generator
            childIter = self._parse(etree_root)

            # If we are supposed to run as a generator, return it.
            # Otherwise, simply loop through every item in the
            # generator (which should be just a single instance), and
            # return the item left over at the end.
            if self._kwargs.get("generator", False):
                return childIter
            else:
                for i in childIter:
                    pass
                return self._handler.item

    def parse_etree(etree_root, **kwargs):
        """Create Python data structures from an :py:class:`ElementTree` object.

        See the :py:class:`EtreeParser` class documentation."""
        return EtreeParser(**kwargs)(etree_root)
