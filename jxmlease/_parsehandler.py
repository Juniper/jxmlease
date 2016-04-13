#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.
"""Internal module that provides a common parsing handler."""
from __future__ import absolute_import

from . import OrderedDict, _unicode
from .dictnode import XMLDictNode

__all__ = []

class _GeneratorMatch(object):
    # Essentially, a data structure used to hold information on matches.
    def __init__(self, rooted=False, elements=None, depth=0, match_string=""):
        if elements is None:
            elements = []
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
                 generator=None):
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
        elif generator is not None:
            for i in generator:
                self.match_tests.append(self._parse_generator_matches(i))
        if len(self.match_tests) > 0:
            self.match_depth = 1000000 # effectively, infinity
            for match in self.match_tests:
                if match.depth < self.match_depth:
                    self.match_depth = match.depth
        else:
            self.match_depth = -1
        self.in_ignore = (self.match_depth > 0)
        self.cdata_separator = cdata_separator
        self.need_cdata_separator = False
        self.processing_started = False

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
            rv = OrderedDict(zip(attrs[0::2], attrs[1::2])) # pylint: disable=zip-builtin-not-iterating
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
        """Handle the start of an element."""
        self.processing_started = True
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

    def end_element(self, full_name): # pylint: disable=unused-argument
        """Handle the end of an element."""
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
        """Handle character data."""
        self.processing_started = True
        if not self.in_ignore:
            if self.need_cdata_separator:
                data = self.cdata_separator + data
                self.need_cdata_separator = False
            self.item = self.item.append_cdata(data, return_node=True)

    def end_document(self):
        """Handle the end of the document."""
        assert len(self.path) == 0, "endDocument() called with open elements"
        self._check_generator_matches()

    def pop_matches(self):
        """Return a match from the cache.

           When called as a generator, the calling function may process a
           chunk of the document and then pull matches, if any, from the
           cache using this function.

           This function also clears the match cache.

           Args:
               None

           Returns:
               A list which contains zero or more matches. Each match is
                   a tuple of: ``(path,match_string,xml_node)``, where the
                   *path* is the calculated absolute path to the matching
                   node, *match_string* is the user-supplied match string
                   that triggered the match, and *xml_node* is the object
                   representing that node (an instance of a
                   :py:class:`XMLNodeBase` subclass).
        """
        rv = self.matches
        self.matches = []
        return rv

