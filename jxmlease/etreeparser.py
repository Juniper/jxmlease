#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Module that provides LXML/ElementTree parsing."""
from __future__ import absolute_import

# pylint: disable=wrong-import-position

QNameDecode = None # pylint: disable=invalid-name
try: # pragma no cover
    from lxml import etree
    QNameDecode = etree.QName # pylint: disable=invalid-name
except ImportError: # pragma no cover
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        import xml.etree.ElementTree as etree

from . import parser_defaults, _unicode
from ._parsehandler import _DictSAXHandler

# pylint: enable=wrong-import-position

__all__ = ['EtreeParser', 'parse_etree']

class QNameSeparator(object): # pylint: disable=too-few-public-methods
    """Class to separate an XML identifier into its namespace and name
       components.
    """
    def __init__(self, text):
        endidx = text.rfind('}')
        if text[0] != '{' or endidx < 0:
            self.namespace = None
            self.localname = text
        else:
            self.namespace = text[1:endidx]
            self.localname = text[endidx+1:]

if QNameDecode is None: # pragma no cover
    # pylint: disable=function-redefined
    class QNameDecode(QNameSeparator): # pylint: disable=too-few-public-methods
        """Internal backup substitute for the LXML QName class."""
        def __init__(self, node):
            QNameSeparator.__init__(self, node.tag)


class NamespaceError(Exception):
    """Raised when an XML namespace is not found in the namespace store.

       This is usually an expected condition, and simply tells the parsing
       code that it needs to allocate a new namespace identifier. For that
       reason, this is considered an internal exception, which users should
       not see.

       TODO: Should this be renamed with a leading _?
    """
    def __init__(self, namespace):
        self.namespace = namespace
        Exception.__init__(self)
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

        # Initialize the namespace dictionary attribute. This will be
        # overwritten each time we start parsing.
        self._namespace_dict = {}

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
        # pylint: disable=unexpected-keyword-arg
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
                        (not ns_resolve_dict.get(
                            parsed_tag.namespace, '@@NOMATCH@@'
                        ))):
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
                            newns = self._namespace_dict[parsed_tag.namespace]
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
                    except NamespaceError as e:
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
            # pylint: disable=no-member
            if isinstance(etree_root, etree._ElementTree):
                etree_root = etree_root.getroot()
        except AttributeError:
            try:
                if isinstance(etree_root, etree.ElementTree):
                    etree_root = etree_root.getroot()
            except AttributeError:
                if not hasattr(etree_root, 'tag'):
                    etree_root = etree_root.getroot()

        # Get the generator
        child_iter = self._parse(etree_root)

        # If we are supposed to run as a generator, return it.
        # Otherwise, simply loop through every item in the
        # generator (which should be just a single instance), and
        # return the item left over at the end.
        if self._kwargs.get("generator", False):
            return child_iter
        else:
            for _ in child_iter:
                pass
            return self._handler.item

def parse_etree(etree_root, **kwargs):
    """Create Python data structures from an :py:class:`ElementTree` object.

    See the :py:class:`EtreeParser` class documentation."""
    return EtreeParser(**kwargs)(etree_root)
