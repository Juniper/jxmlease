#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides XML parsing."""
from __future__ import absolute_import

from xml.parsers import expat
from . import parser_defaults, parsing_increment, StringIO, _unicode
from ._parsehandler import _DictSAXHandler
try: # pragma no cover
    from io import BytesIO # pylint: disable=wrong-import-order
except ImportError: # pragma no cover
    BytesIO = StringIO
try:  # pragma no cover
    _bytes = bytes
except NameError:  # pragma no cover
    _bytes = str

__all__ = ['Parser', 'parse']

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
	xml_input (stirng or file-like object): Contains the XML to parse.
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
        namespaces (`dict`): A remapping for namespaces. If supplied, identifiers
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
        # pylint: disable=unexpected-keyword-arg
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
            except expat.ExpatError as e:
                # If the only error was parsing an empty document, ignore
                # the error and return the empty dictionary.
                raise_error = True
                if (hasattr(expat, "errors") and
                        hasattr(expat.errors, "XML_ERROR_NO_ELEMENTS") and
                        str(e).startswith(expat.errors.XML_ERROR_NO_ELEMENTS + ":") and
                        at_eof and
                        not self._handler.processing_started):
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
            except expat.ExpatError as e:
                # If the only error was parsing an empty document, ignore
                # the error and return the empty dictionary.
                raise_error = True
                if (hasattr(expat, "errors") and
                        hasattr(expat.errors, "XML_ERROR_NO_ELEMENTS") and
                        str(e).startswith(expat.errors.XML_ERROR_NO_ELEMENTS + ":") and
                        not self._handler.processing_started):
                    raise_error = False

                # If needed, raise the error
                if raise_error:
                    raise

        return self._handler.item

def parse(xml_input, **kwargs):
    """Create Python data structures from raw XML.

    See the :py:class:`Parser` class documentation."""
    return Parser(**kwargs)(xml_input)
