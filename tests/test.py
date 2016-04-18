#!/usr/bin/env python
# Copyright (c) 2015-2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.

import sys
if __name__ == "__main__":
    sys.path.append('..')

from jxmlease import parse, Parser, parse_etree, EtreeParser, XMLDictNode, XMLListNode, XMLCDATANode
from copy import deepcopy
from types import GeneratorType
import jxmlease
import jxmlease.xmlparser
from jxmlease.etreeparser import etree

import platform

try:
    import unittest2 as unittest
except ImportError:
    import unittest

StringIO = jxmlease.StringIO
try:
    from io import BytesIO
except ImportError:
    BytesIO = StringIO

unicode = jxmlease._unicode

ExpatError = jxmlease.xmlparser.expat.ExpatError

def _encode(s):
    try:
        return bytes(s, 'ascii')
    except (NameError, TypeError):
        return s

if not hasattr(unittest.TestCase, "assertIsInstance"):
    need_assertIsInstance = True
else:
    need_assertIsInstance = False

if not hasattr(unittest.TestCase, "assertIsNotInstance"):
    need_assertIsNotInstance = True
else:
    need_assertIsNotInstance = False

if not hasattr(unittest.TestCase, "assertIn"):
    need_assertIn = True
else:
    need_assertIn = False

# Deal with Python 2.6 unittest, which does not have the
# unittest.skip or unittest.skipUnless decorators.
if hasattr(unittest, "skip"):
    skip = unittest.skip
else:
    def skip(reason):
        def decorate(f):
            def donothing(*args, **kwargs):
                pass
            return donothing
        return decorate
if hasattr(unittest, "skipUnless"):
    skipUnless = unittest.skipUnless
else:
    def skipUnless(condition, reason):
        if not condition:
            return skip(reason)
        else:
            return lambda func: func
if hasattr(unittest, "skipIf"):
    skipIf = unittest.skipIf
else:
    def skipIf(condition, reason):
        if condition:
            return skip(reason)
        else:
            return lambda func: func

# Setup a large XML string we will use in more than one test.
large_xml_string = '<a x="y">\n'
large_xml_values = []
for i in range(1,10240):
    large_xml_string += "<b>%d</b>\n<c>%d</c>\n" % (i, i + 100000)
    large_xml_values.append(str(i))
large_xml_string += '</a>'
large_xml_path = "/a/b"

class ParsingInterrupted(Exception):
    pass

# Test to see whether the expat parser will call the handler
# functions "as it goes", or only once the entire document
# is processed.
def _test_expat_partial_processing():
    xml = _encode(large_xml_string)
    ioObj = BytesIO(xml)
    parser = jxmlease.xmlparser.expat.ParserCreate('ascii')
    def raise_error(full_name):
        raise ParsingInterrupted()
    parser.EndElementHandler = raise_error
    try:
        parser.ParseFile(ioObj)
    except ParsingInterrupted:
        pass
    return (ioObj.tell() < len(xml))

class XMLToObjTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.parse = parse
        self.Parser = Parser

    if need_assertIsInstance:
        def assertIsInstance(self, a, b, msg=None):
            self.assertTrue(isinstance(a, b), msg=msg)

    if need_assertIsNotInstance:
        def assertIsNotInstance(self, a, b, msg=None):
            self.assertFalse(isinstance(a, b), msg=msg)

    def xmlTextToTestFormat(self, xml):
        return xml

    def test_parse_class(self):
        xml = '<a>data</a>'
        xml = self.xmlTextToTestFormat(xml)
        parser = self.Parser()
        self.assertIsInstance(parser, self.Parser)
        for i in range(0,2):
            rv = parser(xml)
            self.assertIsInstance(rv, XMLDictNode)
            self.assertIsNotInstance(rv, GeneratorType)
            self.assertEqual(rv, {'a': 'data'})
            rv = parser(xml, generator=["/"])
            self.assertIsInstance(rv, GeneratorType)

    def test_parse_class_defaults(self):
        xml = '<a>data</a>'
        xml = self.xmlTextToTestFormat(xml)
        parser = self.Parser(generator=["/"])
        for i in range(0,2):
            rv = parser(xml, generator=[])
            self.assertIsInstance(rv, XMLDictNode)
            self.assertIsNotInstance(rv, GeneratorType)
            self.assertEqual(rv, {'a': 'data'})
            rv = parser(xml)
            self.assertIsInstance(rv, GeneratorType)

    def test_string_vs_file(self):
        xml = '<a>data</a>'
        xml = self.xmlTextToTestFormat(xml)
        self.assertEqual(self.parse(xml),
                         self.parse(BytesIO(_encode(xml))))

    def test_minimal(self):
        xml = '<a/>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': ''}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertEqual(rv.get_xml_attrs(), {})

    def test_simple(self):
        xml = '<a>data</a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': 'data'}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertEqual(rv.get_xml_attrs(), {})

    def test_list_simple(self):
        xml = '<a><b>data1</b><b>data2</b></a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': {'b': ['data1', 'data2']}}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertEqual(rv.get_xml_attrs(), {})
        self.assertFalse(rv['a'].has_xml_attrs())
        self.assertFalse(rv['a']['b'].has_xml_attrs())
        self.assertFalse(rv['a']['b'][0].has_xml_attrs())
        self.assertFalse(rv['a']['b'][1].has_xml_attrs())

    def test_list(self):
        xml = '<a><b>1</b><b>2</b><b>3</b></a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': {'b': ['1', '2', '3']}}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertEqual(rv.get_xml_attrs(), {})

    def test_attrib_root(self):
        xml = '<a href="xyz"/>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': ''}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertTrue(rv['a'].has_xml_attrs())
        self.assertEqual(rv['a'].get_xml_attr("href", None), 'xyz')
        self.assertEqual(rv['a'].get_xml_attrs(), {'href': 'xyz'})

    def test_attrib_leaf(self):
        xml = '<root><a href="xyz"/></root>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'root': {'a': ''}}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['root'].has_xml_attrs())
        nodea = rv['root']['a']
        self.assertTrue(nodea.has_xml_attrs())
        self.assertEqual(nodea.get_xml_attr("href", None), 'xyz')
        self.assertEqual(nodea.get_xml_attrs(), {'href': 'xyz'})

    def test_skip_attrib(self):
        xml = '<a href="xyz"/>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': ''}
        rv = self.parse(xml, xml_attribs=False)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['a'].has_xml_attrs())

    def test_attrib_and_cdata(self):
        xml = '<a href="xyz">123</a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': '123'}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertTrue(rv['a'].has_xml_attrs())
        self.assertEqual(rv['a'].get_xml_attrs(),
                         {'href': 'xyz'})

    def test_semi_structured(self):
        xml = '<a>abc<b/>def</a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': {'b': ''}}
        parser = self.Parser()
        rv = parser(xml)
        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_cdata(), '')
        self.assertEqual(rv['a'].get_cdata(), 'abcdef')
        self.assertEqual(rv['a']['b'].get_cdata(), '')
        rv = parser(xml, cdata_separator='\n')
        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_cdata(), '')
        self.assertEqual(rv['a'].get_cdata(), 'abc\ndef')
        self.assertEqual(rv['a']['b'].get_cdata(), '')

    def test_nested_semi_structured(self):
        xml = '<a>abc<b>123<c/>456</b>def</a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': {'b': {'c': ''}}}
        parser = self.Parser()
        rv = parser(xml)
        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_cdata(), '')
        self.assertEqual(rv['a'].get_cdata(), 'abcdef')
        self.assertEqual(rv['a']['b'].get_cdata(), '123456')
        self.assertEqual(rv['a']['b']['c'].get_cdata(), '')
        rv = parser(xml, cdata_separator='\n')
        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_cdata(), '')
        self.assertEqual(rv['a'].get_cdata(), 'abc\ndef')
        self.assertEqual(rv['a']['b'].get_cdata(), '123\n456')
        self.assertEqual(rv['a']['b']['c'].get_cdata(), '')

    def test_skip_whitespace(self):
        xml = """
        <root>


          <emptya>           </emptya>
          <emptyb attr="attrvalue">


          </emptyb>
          <value>hello</value>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'root': {'emptya': '',
                                   'emptyb': '',
                                   'value': 'hello'}}
        rv = self.parse(xml)
        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_cdata(), '')
        self.assertEqual(rv['root'].get_cdata(), '')
        self.assertEqual(rv['root']['emptya'].get_cdata(), '')
        self.assertEqual(rv['root']['emptyb'].get_cdata(), '')
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['root'].has_xml_attrs())
        self.assertFalse(rv['root']['emptya'].has_xml_attrs())
        self.assertFalse(rv['root']['value'].has_xml_attrs())
        self.assertTrue(rv['root']['emptyb'].has_xml_attrs())
        self.assertEqual(rv['root']['emptyb'].get_xml_attrs(),
                         {'attr': 'attrvalue'})

    def test_keep_whitespace(self):
        xml = "<root> </root>"
        xml = self.xmlTextToTestFormat(xml)
        self.assertEqual(self.parse(xml), dict(root=''))
        self.assertEqual(self.parse(xml, strip_whitespace=False), dict(root=' '))

    def test_generator_string_basic(self):
        xml = '<a x="y"><b>1</b><b>2</b><b>3</b></a>'
        xml = self.xmlTextToTestFormat(xml)
        expected_values = ['1', '2', '3']
        for (path, match, value) in self.parse(xml, generator="/a/b"):
            self.assertEqual(path, "/a/b")
            self.assertEqual(match, "/a/b")
            self.assertTrue(len(expected_values) > 0)
            self.assertEqual(value, expected_values.pop(0))
        self.assertEqual(len(expected_values), 0)

    def test_generator_string_relative(self):
        xml = '<a x="y"><b>1</b><b>2</b><b>3</b></a>'
        xml = self.xmlTextToTestFormat(xml)
        expected_values = ['1', '2', '3']
        for (path, match, value) in self.parse(xml, generator="b"):
            self.assertEqual(path, "/a/b")
            self.assertEqual(match, "b")
            self.assertTrue(len(expected_values) > 0)
            self.assertEqual(value, expected_values.pop(0))
        self.assertEqual(len(expected_values), 0)

    def test_generator_string_relative_complex(self):
        xml = '<a x="y"><b><z>1</z><z>2</z></b><c><d><e><z>3</z><zz>4</zz></e></d></c></a>'
        xml = self.xmlTextToTestFormat(xml)
        expected_values = [{'path': '/a/b/z', 'value': '1'},
                           {'path': '/a/b/z', 'value': '2'},
                           {'path': '/a/c/d/e/z', 'value': '3'}]
        for (path, match, value) in self.parse(xml, generator="z"):
            self.assertEqual(match, "z")
            self.assertTrue(len(expected_values) > 0)
            expectedResult = expected_values.pop(0)
            self.assertEqual(path, expectedResult['path'])
            self.assertEqual(value, expectedResult['value'])
        self.assertEqual(len(expected_values), 0)

    def test_generator_string_relative_partial(self):
        xml = '<a x="y"><b><z>1</z><z>2</z></b><c><d><e><z>3</z><zz>4</zz></e></d></c></a>'
        xml = self.xmlTextToTestFormat(xml)
        expected_values = [{'path': '/a/c/d/e/z', 'value': '3'}]
        for (path, match, value) in self.parse(xml, generator=["a/c/d/e/z","/z"]):
            self.assertEqual(match, "a/c/d/e/z")
            self.assertTrue(len(expected_values) > 0)
            expectedResult = expected_values.pop(0)
            self.assertEqual(path, expectedResult['path'])
            self.assertEqual(value, expectedResult['value'])
        self.assertEqual(len(expected_values), 0)

    def test_generator_list_basic(self):
        xml = '<a x="y"><b>1</b><b>2</b><b>3</b></a>'
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': {'b': ['1', '2', '3']}}
        expected_values = ['1', '2', '3']
        saw_root = False
        matches = ['/', '/a/b']
        for (path, match, value) in self.parse(xml, generator=matches):
            self.assertTrue(path in matches)
            self.assertTrue(match in matches)
            if path == '/a/b':
                self.assertEqual(path, match)
                self.assertTrue(len(expected_values) > 0)
                self.assertEqual(value, expected_values.pop(0))
            elif path == '/':
                self.assertEqual(path, match)
                saw_root = True
                self.assertEqual(value, expectedResult)
                self.assertFalse(value.has_xml_attrs())
                self.assertTrue(value['a'].has_xml_attrs())
                self.assertEqual(value['a'].get_xml_attrs(), {'x': 'y'})
                for node in value['a']['b']:
                    self.assertFalse(node.has_xml_attrs())
        self.assertEqual(len(expected_values), 0)
        self.assertTrue(saw_root)

    @skipUnless(_test_expat_partial_processing(), "Expat does not do partial processing of a file; no need to check for generator correctness.")
    def test_generator_file_is_incremental(self):
        xml = _encode(large_xml_string)
        ioObj = BytesIO(xml)
        count = 0
        for i in self.parse(ioObj, generator="/a/b"):
            count += 1
            if count >= 10:
                break
        self.assertTrue(
            ioObj.tell() < len(xml),
            msg="Bytes read (%d) is not less than the length of the full XML document (%d)" % (ioObj.tell(), len(xml))
        )

    def _generator_string_vs_file(self, xml_string, xml_values, xml_path):
        """Common code used to implement two tests: one for a small string and
           one for a large string.
        """
        xml = xml_string
        expected_values = list(xml_values)
        ioObj = BytesIO(_encode(xml))

        # file-like IO: Must produce the same values as working on the
        # string, and must produce the same values as expected.
        parser = self.Parser(generator=xml_path)
        fileio_values = list()
        for (path, match, value) in parser(ioObj):
            self.assertEqual(path, xml_path)
            self.assertEqual(match, xml_path)
            fileio_values.append(value)

        # string: Must produce the same values as working on file-like
        # IO, and must produce the same values as expected.
        stringio_values = list()
        for (path, match, value) in parser(xml):
            self.assertEqual(path, xml_path)
            self.assertEqual(match, xml_path)
            stringio_values.append(value)

        self.assertEqual(fileio_values, stringio_values)
        self.assertEqual(fileio_values, expected_values)
        self.assertEqual(stringio_values, expected_values)

    @skipIf(platform.python_implementation() == 'PyPy', 'PyPy seems to dump core in this test')
    def test_generator_string_vs_file_large(self):
        self._generator_string_vs_file(
            large_xml_string, large_xml_values, large_xml_path
        )

    def test_generator_string_vs_file_small(self):
        small_xml_string = '<a x="y">\n'
        small_xml_values = []
        for i in range(1,128):
            small_xml_string += "<b>%d</b>\n<c>%d</c>\n" % (i, i + 100000)
            small_xml_values.append(str(i))
        small_xml_string += '</a>'
        small_xml_path = "/a/b"
        self._generator_string_vs_file(
            small_xml_string, small_xml_values, small_xml_path
        )

    def test_unicode(self):
        try:
            value = unichr(39321)
        except NameError:
            value = chr(39321)
        xml = '<a>%s</a>' % value
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {'a': value}
        self.assertEqual(self.parse(xml), expectedResult)

    def test_encoded_string(self):
        try:
            value = unichr(39321)
        except NameError:
            value = chr(39321)
        xml = '<a>%s</a>' % value
        xml = self.xmlTextToTestFormat(xml)

        self.assertEqual(self.parse(xml),
                         self.parse(xml.encode('utf-8')))

    def test_namespace_support(self):
        xml = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x a:attr="val">1</x>
          <a:y>2</a:y>
          <b:z>3</b:z>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'http://defaultns.com/:root': {
                'http://defaultns.com/:x': '1',
                'http://a.com/:y': '2',
                'http://b.com/:z': '3',
            }
        }
        rv = self.parse(xml, process_namespaces=True)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['http://defaultns.com/:root'].has_xml_attrs())
        self.assertFalse(rv['http://defaultns.com/:root']['http://a.com/:y'].has_xml_attrs())
        self.assertFalse(rv['http://defaultns.com/:root']['http://b.com/:z'].has_xml_attrs())
        self.assertTrue(rv['http://defaultns.com/:root']['http://defaultns.com/:x'].has_xml_attrs())
        self.assertEqual(
            rv['http://defaultns.com/:root']['http://defaultns.com/:x'].get_xml_attrs(),
            {'http://a.com/:attr': 'val'})

    def test_namespace_collapse(self):
        xml = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x a:attr="val">1</x>
          <a:y>2</a:y>
          <b:z>3</b:z>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        namespaces = {
            'http://defaultns.com/': None,
            'http://a.com/': 'ns_a',
        }
        expectedResult = {
            'root': {
                'x': '1',
                'ns_a:y': '2',
                'http://b.com/:z': '3',
            }
        }
        rv = self.parse(xml, process_namespaces=True, namespaces=namespaces)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['root'].has_xml_attrs())
        self.assertFalse(rv['root']['ns_a:y'].has_xml_attrs())
        self.assertFalse(rv['root']['http://b.com/:z'].has_xml_attrs())
        self.assertTrue(rv['root']['x'].has_xml_attrs())
        self.assertEqual(rv['root']['x'].get_xml_attrs(),
                         {'ns_a:attr': 'val'})

    def translate_namespace_identifier(self, identifier, ns_url_map,
                                       ns_id_map):
        # Translate the namespace for the tag/attribute, if necessary.
        index = identifier.rfind(":")
        if index < 0:
            nsurl = ns_id_map.get("")
        else:
            nsurl = ns_id_map.get(identifier[:index])
            self.assertTrue(
                nsurl,
                msg="Mapping for namespace \"%s\" not found" % (
                    identifier[:index],
                ))
            identifier = identifier[index+1:]
        if (not nsurl) or (not ns_url_map.get(nsurl, '@@NOMATCH@@')):
            return identifier
        else:
            self.assertTrue(nsurl in ns_url_map)
            return ns_url_map[nsurl] + ":" + identifier

    def translate_namespace(self, root, ns_map, _inherited_ns={}):
        """
        Recursively translate the namespace identifiers. Return a
        new dictionary with the new namespace identifiers, but NO
        xmlns attributes.

        The initial callers hould NOT specify _inherited_ns. That
        will be populated on recursive calls.

        The initial caller should specify a `root`, which points to
        the dictionary that contains the root node; and, the `ns_map`,
        which is a dictionary with URLs as keys and NS identifiers
        as values. (The default NS identifier should be specified as
        "".)

        KNOWN BUG: If the namespaces are defined in child nodes that
        are in a list and the child nodes in the list have different
        xmlns attributes, this may not work correctly.
        """
        if isinstance(root, list):
            rv = XMLListNode()
            for v in root:
                rv.append(self.translate_namespace(v, ns_map, _inherited_ns, force_cdata))
            return rv

        if not isinstance(root, (XMLDictNode, XMLCDATANode)):
            return root

        if isinstance(root, XMLCDATANode):
            rv = XMLCDATANode(jxmlease._unicode(root))
        else:
            rv = XMLDictNode()

        # Do a first pass to extract xmlns attributes.
        new_ns = dict(_inherited_ns)
        for k in root.get_xml_attrs():
            if not k.startswith("xmlns"):
                continue

            v = root.get_xml_attr(k)
            index = k.rfind(":")
            if index < 0:
                self.assertEqual(k, "xmlns")
                new_ns[""] = v
            else:
                new_ns[k[index+1:]] = v

        # Now, translate the namespace for the attributes.
        for k in root.get_xml_attrs():
            v = root.get_xml_attr(k)
            if k.startswith("xmlns"):
                self.assertTrue(v in ns_map)
                if ns_map[v] == "":
                    newK = "xmlns"
                else:
                    newK = "xmlns:" + ns_map[v]
            else:
                newK = self.translate_namespace_identifier(k, ns_map, new_ns)
            rv.set_xml_attr(newK, v)

        # Translate the namespace for our own tag.
        if root.tag is not None:
            rv.tag = self.translate_namespace_identifier(root.tag, ns_map, new_ns)
        else:
            rv.tag = None

        # Now, translate the namespace for the nodes, as we rebuild them.
        if isinstance(root, XMLDictNode):
            for child in root.values():
                if not isinstance(child, XMLListNode):
                    child = XMLListNode([child])
                for node in child:
                    new_node = self.translate_namespace(node, ns_map, new_ns)
                    _ = rv.add_node(new_node.tag, new_node=new_node)
        return rv

    def test_namespace_ignore(self):
        xml = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/"
              xmlns:c="http://c.com/">
          <x>1</x>
          <a:y c:attr="val">2</a:y>
          <b:z>3</b:z>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'root': {
                'x': '1',
                'a:y': '2',
                'b:z': '3',
            },
        }

        expectedAttrsCorrect = {
            '/': {},
            '/root': {
                'xmlns': 'http://defaultns.com/',
                'xmlns:a': 'http://a.com/',
                'xmlns:b': 'http://b.com/',
                'xmlns:c': 'http://c.com/',
            },
            '/root/x': {},
            '/root/y': {
                'c:attr': 'val',
            },
            '/root/z': {},
        }
        expectedAttrsRecreated = {
            '/': {},
            '/root': {
                'xmlns': 'http://defaultns.com/',
            },
            '/root/x': {},
            '/root/y': {
                'xmlns:a': 'http://a.com/',
                'xmlns:c': 'http://c.com/',
                'c:attr': 'val',
            },
            '/root/z': {
                'xmlns:b': 'http://b.com/',
            },
        }

        # In this case, we expect a correct mapping.
        if isinstance(xml, (str, unicode)) or hasattr(xml, "nsmap") or (hasattr(xml, "getroot") and hasattr(xml.getroot(), "nsmap")):
            rv = self.parse(xml)
            expectedAttrs = expectedAttrsCorrect
        # In this case, the NS identifiers may be different because they
        # were lost during parsing.
        # The key thing is that the NS relationships be the same, so we
        # will translate the NS identifiers back to what we expect.
        else:
            ns_map = dict()
            for k in expectedAttrsCorrect['/root'].keys():
                v = expectedAttrsCorrect['/root'][k]
                if k.startswith('xmlns'):
                    if k.rfind(":") >= 0:
                        k = k[k.rfind(":")+1:]
                    else:
                        k = ""
                    ns_map[v] = k
            rv = self.translate_namespace(self.parse(xml), ns_map)
            expectedAttrs = expectedAttrsRecreated

        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_xml_attrs(), expectedAttrs['/'])
        self.assertEqual(rv['root'].get_xml_attrs(), expectedAttrs['/root'])
        self.assertEqual(rv['root']['x'].get_xml_attrs(), expectedAttrs['/root/x'])
        self.assertEqual(rv['root']['a:y'].get_xml_attrs(), expectedAttrs['/root/y'])
        self.assertEqual(rv['root']['b:z'].get_xml_attrs(), expectedAttrs['/root/z'])
            

    def test_namespace_ignore_mixed(self):
        xml = """
        <test>
          <root xmlns="http://defaultns.com/"
                xmlns:a="http://a.com/"
                xmlns:b="http://b.com/"
                xmlns:c="http://c.com/">
            <x>1</x>
            <a:y c:attr="val">2</a:y>
            <b:z>3</b:z>
          </root>
        </test>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'test': {
                'root': {
                    'x': '1',
                    'a:y': '2',
                    'b:z': '3',
                },
            },
        }

        expectedAttrsCorrect = {
            '/': {},
            '/test': {},
            '/test/root': {
                'xmlns': 'http://defaultns.com/',
                'xmlns:a': 'http://a.com/',
                'xmlns:b': 'http://b.com/',
                'xmlns:c': 'http://c.com/',
            },
            '/test/root/x': {},
            '/test/root/y': {
                'c:attr': 'val',
            },
            '/test/root/z': {},
        }
        expectedAttrsRecreated = {
            '/': {},
            '/test': {},
            '/test/root': {
                'xmlns': 'http://defaultns.com/',
            },
            '/test/root/x': {},
            '/test/root/y': {
                'xmlns:a': 'http://a.com/',
                'xmlns:c': 'http://c.com/',
                'c:attr': 'val',
            },
            '/test/root/z': {
                'xmlns:b': 'http://b.com/',
            },
        }

        # In this case, we expect a correct mapping.
        if isinstance(xml, (str, unicode)) or hasattr(xml, "nsmap") or (hasattr(xml, "getroot") and hasattr(xml.getroot(), "nsmap")):
            rv = self.parse(xml)
            expectedAttrs = expectedAttrsCorrect
        # In this case, the NS identifiers may be different because they
        # were lost during parsing.
        # The key thing is that the NS relationships be the same, so we
        # will translate the NS identifiers back to what we expect.
        else:
            ns_map = dict()
            for k in expectedAttrsCorrect['/test/root'].keys():
                v = expectedAttrsCorrect['/test/root'][k]
                if k.startswith('xmlns'):
                    if k.rfind(":") >= 0:
                        k = k[k.rfind(":")+1:]
                    else:
                        k = ""
                    ns_map[v] = k
            rv = self.translate_namespace(self.parse(xml), ns_map)
            expectedAttrs = expectedAttrsRecreated

        self.assertEqual(rv, expectedResult)
        self.assertEqual(rv.get_xml_attrs(), expectedAttrs['/'])
        self.assertEqual(rv['test'].get_xml_attrs(), expectedAttrs['/test'])
        self.assertEqual(rv['test']['root'].get_xml_attrs(), expectedAttrs['/test/root'])
        self.assertEqual(rv['test']['root']['x'].get_xml_attrs(), expectedAttrs['/test/root/x'])
        self.assertEqual(rv['test']['root']['a:y'].get_xml_attrs(), expectedAttrs['/test/root/y'])
        self.assertEqual(rv['test']['root']['b:z'].get_xml_attrs(), expectedAttrs['/test/root/z'])
            

    def test_namespace_strip_basic(self):
        xml = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x>1</x>
          <a:y>2</a:y>
          <b:z>3</b:z>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'root': {
                'x': '1',
                'y': '2',
                'z': '3',
            }
        }
        rv = self.parse(xml, strip_namespace=True)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['root'].has_xml_attrs())
        for k in rv['root'].keys():
            self.assertFalse(rv['root'][k].has_xml_attrs())

    def test_namespace_strip_mixed(self):
        xml = """
        <test>
          <root xmlns="http://defaultns.com/"
                xmlns:a="http://a.com/"
                xmlns:b="http://b.com/">
            <x>1</x>
            <a:y>2</a:y>
            <b:z>3</b:z>
          </root>
        </test>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'test': {
                'root': {
                    'x': '1',
                    'y': '2',
                    'z': '3',
                },
            },
        }
        rv = self.parse(xml, strip_namespace=True)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['test'].has_xml_attrs())
        self.assertFalse(rv['test']['root'].has_xml_attrs())
        for k in rv['test']['root'].keys():
            self.assertFalse(rv['test']['root'][k].has_xml_attrs())

    def test_namespace_strip_attributes_positive(self):
        xml = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x>1</x>
          <a:y a:a="val">2</a:y>
          <b:z a="val1" a:b="val2">3</b:z>
        </root>
        """
        xml = self.xmlTextToTestFormat(xml)
        expectedResult = {
            'root': {
                'x': '1',
                'y': '2',
                'z': '3',
            }
        }
        rv = self.parse(xml, strip_namespace=True)
        self.assertEqual(rv, expectedResult)
        self.assertFalse(rv.has_xml_attrs())
        self.assertFalse(rv['root'].has_xml_attrs())
        self.assertFalse(rv['root']['x'].has_xml_attrs())
        self.assertEqual(rv['root']['y'].get_xml_attrs(),
                         {'a': 'val'})
        self.assertEqual(rv['root']['z'].get_xml_attrs(),
                         {'a': 'val1', 'b': 'val2'})

    def test_namespace_strip_attributes_negative(self):
        xml1 = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x a="val1" a:a="val2">1</x>
        </root>
        """
        xml1 = self.xmlTextToTestFormat(xml1)
        xml2 = """
        <root xmlns="http://defaultns.com/"
              xmlns:a="http://a.com/"
              xmlns:b="http://b.com/">
          <x a:a="val1" b:a="val2">1</x>
        </root>
        """
        xml2 = self.xmlTextToTestFormat(xml2)
        parser = self.Parser(strip_namespace=True)
        for xml in (xml1, xml2):
            self.assertRaises(ValueError, parser, xml)

    def test_empty_node(self):
        test_strings = [
            "",
            "<!-- comment -->",
            """<?xml version="1.0" encoding="utf-8"?>""",
            "           "
        ]
        def run_test_empty_node(tc, expected, fx, *args, **kwargs):
            e = None
            try:
                result = fx(*args, **kwargs)
            except ExpatError as e:
                result = None

            tc.assertTrue(e is None)
            tc.assertEqual(result, expected)

        for xml in test_strings:
            run_test_empty_node(self, {}, self.parse, xml)
            run_test_empty_node(self, [], list, self.parse(xml, generator="z"))
            run_test_empty_node(self, [], list, self.parse(xml, generator="w/x/y/z"))

    def test_corrupt_xml(self):
        for xml in ["<a><b><c>foo</c></b>", "xxx", "</b>"]:
            self.assertRaises(ExpatError, self.parse, xml)
            self.assertRaises(ExpatError, list, self.parse(xml, generator="z"))
            self.assertRaises(ExpatError, list, self.parse(xml, generator="w/x/y/z"))

class EtreeToObjTestCase(XMLToObjTestCase):
    def __init__(self, *args, **kwargs):
        XMLToObjTestCase.__init__(self, *args, **kwargs)
        self.parse=parse_etree
        self.Parser=EtreeParser

    def xmlTextToTestFormat(self, xml):
        try:
            return etree.fromstring(xml)
        except UnicodeEncodeError:
            xml = xml.encode('utf-8')
            return etree.fromstring(xml)

    # XMLToObjTestCase tests that do not make sense to run in the
    # ElementTree context.
    @skip("Test does not make sense in the Etree context")
    def test_string_vs_file(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_encoded_string(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_generator_file_cb_vs_generator(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_generator_string_vs_file_small(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_generator_string_vs_file_large(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_generator_file_is_incremental(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_empty_node(self):
        pass

    @skip("Test does not make sense in the Etree context")
    def test_corrupt_xml(self):
        pass

    # Additional test case(s) that are specific to
    # ElementTree parsing.
    def test_element_vs_element_tree(self):
        xml = '<a>data</a>'
        xml_element = etree.fromstring(xml)
        xml_elementtree = etree.ElementTree(xml_element)
        self.assertEqual(self.parse(xml_element),
                         self.parse(xml_elementtree))

class XMLNodeTestCase(unittest.TestCase):
    if need_assertIn:
        def assertIn(self, a, b, msg=None):
            self.assertTrue(a in b, msg=msg)

    def pprint_compare(self, obj1, obj2, **kwargs):
        ioObj1 = StringIO()
        obj1.prettyprint(width=1000, stream=ioObj1, **kwargs)
        ioObj2 = StringIO()
        jxmlease.pprint(obj2, width=1000, stream=ioObj2, **kwargs)
        self.assertEqual(ioObj1.getvalue(), ioObj2.getvalue())

    def test_newstyle_prettyprint(self):
        data1_orig = unicode("data1")
        data1 = XMLCDATANode(data1_orig)
        data2_orig = unicode("data2")
        data2 = XMLCDATANode(data2_orig)
        list1_orig = [data1_orig, data2_orig]
        list1 = XMLListNode((data1, data2))
        nodec = XMLDictNode({'c': list1})
        nodeb = XMLDictNode({'b': nodec})
        nodea = XMLDictNode({'a': nodeb})

        for depth in (None, 1, 2, 3, 4, 5):
            #dict level
            self.pprint_compare(nodea,
                                {'a': {'b': {'c': list1_orig}}},
                                depth=depth)

            # list level
            self.pprint_compare(list1, list1_orig, depth=depth)

            # CDATA level
            self.pprint_compare(data1, data1_orig, depth=depth)

        # Check non-XML*Node elements under an XML*Node element
        list1 = XMLListNode((data1, data2_orig))
        self.pprint_compare(list1, list1_orig)
        nodec['d'] = data2_orig
        self.pprint_compare(nodec,
                            {'c': list1_orig, 'd': data2_orig})

    def test_object_repr(self):
        if jxmlease._OrderedDict == dict:
            dict_repr = '{}'
        else:
            dict_repr = 'OrderedDict()'
        self.assertEqual(
            repr(XMLDictNode()),
            "XMLDictNode(xml_attrs=%s, value=%s)" % (dict_repr, dict_repr)
        )
        self.assertEqual(
            repr(XMLListNode()),
            "XMLListNode(xml_attrs=%s, value=[])" % dict_repr
        )
        self.assertTrue(
            repr(XMLCDATANode()).startswith(
                "XMLCDATANode(xml_attrs=%s, value=" % dict_repr
            )
        )
        OrderedDict = jxmlease.OrderedDict
        myDict = OrderedDict()
        stdDict = jxmlease._OrderedDict()
        self.assertEqual(repr(myDict), repr(stdDict))
        myDict['a'] = OrderedDict()
        stdDict['a'] = jxmlease._OrderedDict()
        self.assertEqual(repr(myDict), repr(stdDict))
        myDict['a'] = {}
        stdDict['a'] = {}
        self.assertEqual(repr(myDict), repr(stdDict))

    def test_CDATA(self):
        # Initialization
        CDATANode = XMLCDATANode("a", tag="mynode", text="b")
        DictNode = XMLDictNode(text="z")
        self.assertEqual(CDATANode, "a")
        self.assertEqual(CDATANode.get_cdata(), "a")
        self.assertEqual(DictNode.get_cdata(), "z")

        _ = DictNode.add_node(tag="mynode", new_node=CDATANode)
        self.assertEqual(DictNode['mynode'], CDATANode)

        # Reset
        new_node = CDATANode.set_cdata("b", return_node=True)
        self.assertTrue(new_node is DictNode['mynode'])
        self.assertEqual(new_node, "b")
        self.assertEqual(new_node.get_cdata(), "b")
        DictNode.set_cdata("c")
        self.assertEqual(DictNode.get_cdata(), "c")

        # Check for up-to-date nodes
        self.assertRaises(AttributeError, CDATANode.append_cdata, "b")
        CDATANode = CDATANode.get_current_node()
        self.assertEqual(new_node, CDATANode)
        CDATANode = CDATANode.get_current_node()
        self.assertEqual(new_node, CDATANode)

        # Append CDATA
        CDATANode.append_cdata("b ")
        CDATANode = CDATANode.get_current_node()
        self.assertTrue(DictNode['mynode'] is CDATANode)
        self.assertEqual(DictNode['mynode'], "bb ")
        self.assertEqual(DictNode['mynode'].get_cdata(), "bb ")
        DictNode.append_cdata("c ")
        self.assertEqual(DictNode.get_cdata(), "cc ")

        # Strip CDATA
        CDATANode.strip_cdata()
        CDATANode = CDATANode.get_current_node()
        self.assertTrue(DictNode['mynode'] is CDATANode)
        self.assertEqual(DictNode['mynode'], "bb")
        self.assertEqual(DictNode['mynode'].get_cdata(), "bb")
        DictNode.strip_cdata()
        self.assertEqual(DictNode.get_cdata(), "cc")

    def test_cdata_multiple_replacements(self):
        # Check multiple replacements.
        root = XMLDictNode()
        root.add_node("a", text="foo")
        old = root['a']
        self.assertTrue(isinstance(old, XMLCDATANode))
        new = old.append_cdata("bar", return_node=True)
        new = new.append_cdata("baz", return_node=True)
        self.assertEqual(old, "foo")
        self.assertEqual(new, "foobarbaz")
        self.assertTrue(root['a'] is new)
        self.assertTrue(old.get_current_node() is new)

        # Check behavior if the chain ends in a non-XML node object.
        testnode = "hi"
        new._replacement_node= testnode
        self.assertTrue(old.get_current_node() is testnode)
        self.assertTrue(new.get_current_node() is testnode)

    def test_build_node(self):
        # Modifying root node (CDATA->Dict) is not allowed.
        root = XMLCDATANode("hi")
        self.assertRaises(AttributeError, root.add_node, tag="foo", key="bar")

        # Lists - not allowed
        self.assertRaises(TypeError, XMLListNode().add_node, tag="foo")

        # Build a tree
        root = XMLDictNode({'a': "hi"})
        root['a'].add_node(tag="foo", key="bar")
        self.assertTrue(isinstance(root['a'], XMLDictNode))
        self.assertEqual(list(root['a'].keys()), ['bar'])
        self.assertTrue(isinstance(root['a']['bar'], XMLCDATANode))
        self.assertEqual(root['a'].get_cdata(), "hi")
        self.assertEqual(root['a']['bar'].get_cdata(), "")
        self.assertTrue(root['a']['bar'].parent is root['a'])
        self.assertTrue(root['a'].parent is root)
        self.assertEqual(root['a']['bar'].tag, "foo")
        self.assertEqual(root['a']['bar'].key, "bar")
        self.assertEqual(root['a'].tag, "a")
        self.assertEqual(root['a'].key, "a")

    def test_list(self):
        # Return
        CDATANode = XMLCDATANode("xxxx")
        self.assertTrue(isinstance(CDATANode, XMLCDATANode))
        self.assertTrue(isinstance(CDATANode.list(), list))
        self.assertEqual(len(CDATANode.list()), 1)
        self.assertEqual(CDATANode.list()[0], CDATANode)

        # In place
        root = XMLDictNode()
        root.add_node("a")
        root['a'].add_node('b', text='xxxx')
        rv = root['a']['b'].list(in_place=True)
        self.assertEqual(rv, root['a']['b'])
        self.assertEqual(len(root['a']['b']), 1)
        self.assertEqual(root['a']['b'][0].get_cdata(), 'xxxx')

        # List of list
        root = XMLListNode()
        self.assertTrue(root is root.list())

    def test_dict_single(self):
        root = XMLDictNode()
        root.add_node("a")
        root['a'].add_node('b')
        root['a']['b'].add_node('name', text="xxxx")
        root['a']['b'].add_node('foo', text='bar', xml_attrs={'key': 'key'})
        def cb(_):
            return 'baz'
        self.assertEqual(root['a']['b']['name'].dict(tags=['name']), {'xxxx': root['a']['b']['name']})
        self.assertEqual(root['a']['b'].dict(tags=['name']), {'xxxx': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(attrs=['key']), {'bar': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(func=cb), {'baz': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(func=cb, tags=['name'], attrs=['key']), {'bar': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(func=cb, tags=['name'], attrs=['none']), {'xxxx': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(func=cb, tags=['none'], attrs=['none']), {'baz': root['a']['b']})
        self.assertEqual(root['a']['b'].dict(), {'b': root['a']['b']})

        rootab = dict(root['a']['b'])
        _ = root['a']['b'].dict(tags=['name'], in_place=True)
        self.assertEqual(root['a']['b'], {'xxxx': rootab})

    def test_dict_list_single(self):
        root = XMLDictNode()
        root.add_node("a")
        root['a'].add_node('b')
        root['a']['b'].add_node('name', text="xxxx")
        root['a']['b'].add_node('foo', text='bar', xml_attrs={'key': 'key'})
        rootab = dict(root['a']['b'])
        _ = root['a']['b'].list(in_place=True)

        self.assertEqual(root['a']['b'][0].dict(tags=['name']), {'xxxx': rootab})
        self.assertEqual(root['a']['b'].dict(tags=['name']), {'xxxx': rootab})

        _ = root['a']['b'][0].dict(tags=['name'], in_place=True)
        self.assertEqual(root['a']['b'], {'xxxx': rootab})

    def test_dict_list_multi(self):
        root = XMLDictNode()
        root.add_node("a")
        root['a'].add_node('b')
        root['a']['b'].add_node('name', text="xxxx")
        root['a']['b'].add_node('foo', text='bar', xml_attrs={'key': 'key'})
        root['a'].add_node('b')
        root['a']['b'][1].add_node('name', text="yyyy")
        root['a']['b'][1].add_node('foo', text='baz', xml_attrs={'key': 'key'})
        xxxx = dict(root['a']['b'][0])
        yyyy = dict(root['a']['b'][1])

        self.assertEqual(root['a']['b'][0].dict(tags=['name']), {'xxxx': xxxx})
        self.assertEqual(root['a']['b'][1].dict(tags=['name']), {'yyyy': yyyy})
        self.assertEqual(root['a']['b'].dict(tags=['name']), {'xxxx': xxxx, 'yyyy': yyyy})

        _ = root['a']['b'].dict(tags=['name'], in_place=True)
        self.assertEqual(root['a']['b'], {'xxxx': xxxx, 'yyyy': yyyy})

        root = XMLDictNode()
        root.add_node("a")
        root['a'].add_node('b')
        root['a']['b'].add_node('name', text="xxxx")
        root['a']['b'].add_node('foo', text='bar', xml_attrs={'key': 'key'})
        root['a'].add_node('b')
        root['a']['b'][1].add_node('name', text="yyyy")
        root['a']['b'][1].add_node('foo', text='baz', xml_attrs={'key': 'key'})
        xxxx = dict(root['a']['b'][0])
        yyyy = dict(root['a']['b'][1])

        _ = root['a']['b'][0].dict(tags=['name'], in_place=True)
        self.assertEqual(root['a']['b'], [{'xxxx': xxxx}, yyyy])

    def test_dict_negative(self):
        root = XMLDictNode({'a': {'b': [[{'name': 'foo'}]]}})
        self.assertRaises(TypeError, root['a']['b'].dict, tags=['name'])

    def assertDictKeyListEqual(self, iter1, iter2):
        a = list(iter1)
        b = list(iter2)
        if jxmlease._OrderedDict == dict:
            a.sort()
            b.sort()
        self.assertEqual(a, b)

    def test_dict_promotion(self):
        test_foo = {'key': 'foo', 'val': '17'}
        test_bar = {'key': 'bar', 'val': '1001'}

        # child dict
        root = XMLDictNode({'a': {'b': dict(test_foo)}})
        rv = root['a']['b'].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['foo'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])

        # child single-member list (run on list)
        root = XMLDictNode({'a': {'b': [dict(test_foo)]}})
        rv = root['a']['b'].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['foo'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])

        # child single-member list (run on list member)
        root = XMLDictNode({'a': {'b': [dict(test_foo)]}})
        rv = root['a']['b'][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['foo'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])

        # child multi-member list (run on list)
        root = XMLDictNode({'a': {'b': [dict(test_foo), dict(test_bar)]}})
        rv = root['a']['b'].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['foo', 'bar'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(root['a']['bar'], test_bar)
        self.assertEqual(root['a']['bar'].tag, 'b')
        self.assertEqual(root['a']['bar'].key, 'bar')
        self.assertTrue(root['a']['bar'].parent is root['a'])

        # child multi-member list (run on list member)
        root = XMLDictNode({'a': {'b': [dict(test_foo), dict(test_bar)]}})
        rv = root['a']['b'][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['b', 'foo'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(len(root['a']['b']), 1)
        self.assertEqual(root['a']['b'][0], test_bar)
        rv = root['a']['b'][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertDictKeyListEqual(root['a'].keys(), ['foo', 'bar'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(root['a']['bar'], test_bar)
        self.assertEqual(root['a']['bar'].tag, 'b')
        self.assertEqual(root['a']['bar'].key, 'bar')
        self.assertTrue(root['a']['bar'].parent is root['a'])

        # deep list (run on list)
        root = XMLDictNode({'a': {'b': [[[[dict(test_foo), dict(test_bar)]]]]}})
        rv = root['a']['b'][0][0][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['foo', 'bar'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(root['a']['bar'], test_bar)
        self.assertEqual(root['a']['bar'].tag, 'b')
        self.assertEqual(root['a']['bar'].key, 'bar')
        self.assertTrue(root['a']['bar'].parent is root['a'])

        # deep list (run on list member)
        root = XMLDictNode({'a': {'b': [[[[dict(test_foo), dict(test_bar)]]]]}})
        # Verify starting values
        self.assertEqual(root['a']['b'][0][0][0][1].tag, 'b')
        self.assertEqual(root['a']['b'][0][0][0][1].key, 'b')
        self.assertTrue(root['a']['b'][0][0][0][1].parent is root['a']['b'][0][0][0])
        # Now, do the changes and verify them
        rv = root['a']['b'][0][0][0][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertEqual(list(root['a'].keys()), ['b', 'foo'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(len(root['a']['b']), 1)
        self.assertEqual(len(root['a']['b'][0]), 1)
        self.assertEqual(len(root['a']['b'][0][0]), 1)
        self.assertEqual(len(root['a']['b'][0][0][0]), 1)
        self.assertEqual(root['a']['b'][0][0][0][0], test_bar)
        self.assertEqual(root['a']['b'][0][0][0][0].tag, 'b')
        self.assertEqual(root['a']['b'][0][0][0][0].key, 'b')
        self.assertTrue(root['a']['b'][0][0][0][0].parent is root['a']['b'][0][0][0])
        rv = root['a']['b'][0][0][0][0].dict(tags=['key'], in_place=True, promote=True)
        self.assertTrue(rv is root['a'])
        self.assertDictKeyListEqual(root['a'].keys(), ['foo', 'bar'])
        self.assertEqual(root['a']['foo'], test_foo)
        self.assertEqual(root['a']['foo'].tag, 'b')
        self.assertEqual(root['a']['foo'].key, 'foo')
        self.assertTrue(root['a']['foo'].parent is root['a'])
        self.assertEqual(root['a']['bar'], test_bar)
        self.assertEqual(root['a']['bar'].tag, 'b')
        self.assertEqual(root['a']['bar'].key, 'bar')
        self.assertTrue(root['a']['bar'].parent is root['a'])

    def test_replace_corrupt(self):
        # Wrong key - replace
        rv = XMLDictNode({'a': 'foo', 'b': 'bar'})
        rv['a'].tag = 'xxx'
        rv['a'].key = 'b'
        rv['a'].set_cdata('baz')
        self.assertEqual(rv, {'a': 'baz', 'b': 'bar'})
        self.assertEqual(rv['a'].tag, 'xxx')
        self.assertEqual(rv['a'].key, 'a')

        # Buried in a list - replace
        rv = XMLDictNode({'a': ['foo'], 'b': 'bar'})
        rv['a'][0].tag = 'xxx'
        rv['a'][0].key = 'b'
        rv['a'][0].parent = rv
        rv['a'][0].set_cdata('baz')
        self.assertEqual(rv, {'a': ['baz'], 'b': 'bar'})
        self.assertEqual(rv['a'][0].tag, 'xxx')
        self.assertEqual(rv['a'][0].key, 'a')
        self.assertTrue(rv['a'][0].parent is rv['a'])

        # Wrong key - delete
        rv = XMLDictNode({'a': {'name': 'foo'}, 'b': {'name': 'bar'}})
        rv['a'].tag = 'xxx'
        rv['a'].key = 'bbb'
        rv['a']._replace_node(None)
        self.assertEqual(list(rv.keys()), ['b'])
        self.assertEqual(rv['b'], {'name': 'bar'})

        # Buried in a list - delete
        rv = XMLDictNode({'a': ['foo'], 'b': 'bar'})
        rv['a'][0].tag = 'xxx'
        rv['a'][0].key = 'b'
        rv['a'][0].parent = rv
        rv['a'][0]._replace_node(None)
        self.assertEqual(rv, {'b': 'bar'})

    def test_conversion_deep(self):
        testdict = {'a': {'b': ['a', 'b', None], 'c': None}}
        rv = XMLDictNode(testdict)
        self.assertTrue(rv['a'] is not testdict['a'])
        self.assertTrue(rv['a']['b'] is not testdict['a']['b'])
        self.assertTrue(rv['a']['b'][2] is not testdict['a']['b'][2])
        self.assertTrue(rv['a']['c'] is not testdict['a']['c'])
        testdict['a']['b'][2] = ''
        testdict['a']['c'] = ''
        self.assertEqual(rv, testdict)
        self.assertTrue(isinstance(rv, XMLDictNode))
        self.assertTrue(isinstance(rv['a'], XMLDictNode))
        self.assertEqual(rv['a'].key, 'a')
        self.assertEqual(rv['a'].tag, 'a')
        self.assertTrue(rv['a'].parent is rv)
        self.assertTrue(isinstance(rv['a']['b'], XMLListNode))
        self.assertEqual(rv['a']['b'].key, 'b')
        self.assertEqual(rv['a']['b'].tag, 'b')
        self.assertTrue(rv['a']['b'].parent is rv['a'])
        for node in rv['a']['b']:
            self.assertTrue(isinstance(node, XMLCDATANode))
            self.assertEqual(node.key, 'b')
            self.assertEqual(node.tag, 'b')
            self.assertTrue(node.parent is rv['a']['b'])
        self.assertTrue(isinstance(rv['a']['c'], XMLCDATANode))
        self.assertEqual(rv['a']['c'].key, 'c')
        self.assertEqual(rv['a']['c'].tag, 'c')
        self.assertTrue(rv['a']['c'].parent is rv['a'])

    def test_conversion_shallow(self):
        testdict = {'a': {'b': {'c': ['a', 'b']}}}
        rv = XMLDictNode(testdict, deep=False)
        self.assertEqual(rv, testdict)
        self.assertTrue(isinstance(rv, XMLDictNode))
        self.assertTrue(isinstance(rv['a'], XMLDictNode))
        self.assertEqual(rv['a'].key, 'a')
        self.assertEqual(rv['a'].tag, 'a')
        self.assertTrue(rv['a'].parent is rv)
        self.assertFalse(isinstance(rv['a']['b'], XMLDictNode))
        self.assertFalse(isinstance(rv['a']['b']['c'], XMLListNode))
        for node in rv['a']['b']['c']:
            self.assertFalse(isinstance(node, XMLCDATANode))

    def test_conversion_nonstring(self):
        testdict = {'a': [1,2,None]}
        rv = XMLDictNode(testdict)
        self.assertEqual(rv, {'a': ["1", "2", ""]})

    def test_conversion_inheritence(self):
        class FakeXMLNode(dict):
            def __init__(self, *args, **kwargs):
                dict.__init__(self, *args, **kwargs)
                self.xml_attrs = {'a': 'b', 'b': 'c'}
                self.text = jxmlease._unicode("foobar")
                self.key = 'foo'
                self.tag = 'bar'
                self.parent = str

        testroot = XMLDictNode({'a': {'b': ''}})
        testdict = testroot['a']
        testdict.set_cdata("foo")
        testdict.set_xml_attr("y", "z")

        # Make a copy of the node.
        newdict = XMLDictNode(testdict)

        # The contents, text, and attributes should be equal, but the
        # attributes should not point to the same dictionary. (Because
        # string objects are immutable, it is fine if the text points
        # to the same object.)
        self.assertEqual(newdict, testdict)
        self.assertEqual(newdict.get_xml_attrs(), testdict.get_xml_attrs())
        self.assertFalse(newdict.get_xml_attrs() is testdict.get_xml_attrs())
        self.assertEqual(newdict.get_cdata(), testdict.get_cdata())

        # The tag, key, and parent should be set to correct defaults.
        self.assertTrue(newdict.tag is None)
        self.assertTrue(newdict.key is None)
        self.assertTrue(newdict.parent is None)


        # Now, try with a different object that has the same attributes.
        testdict = FakeXMLNode({'b': ''})
        newdict = XMLDictNode(testdict)

        # The contents should be the same, but everything else should
        # be set to default values.
        self.assertEqual(newdict, testdict)
        self.assertEqual(newdict.get_xml_attrs(), dict())
        self.assertEqual(newdict.get_cdata(), '')
        self.assertTrue(newdict.tag is None)
        self.assertTrue(newdict.key is None)
        self.assertTrue(newdict.parent is None)

    def test_xml_attr(self):
        attrs = jxmlease.OrderedDict(aa=1)
        node = XMLCDATANode("", xml_attrs=attrs)
        self.assertNotEqual(node.get_xml_attrs(), attrs)
        self.assertTrue(node.get_xml_attrs() is not attrs)
        attrs['aa'] = '1'
        self.assertEqual(node.get_xml_attrs(), attrs)
        self.assertEqual(node.get_xml_attr('aa'), '1')
        self.assertEqual(node.get_xml_attr('aa', 'bb'), '1')
        self.assertRaises(KeyError, node.get_xml_attr, 'a')
        self.assertEqual(node.get_xml_attr('a', 'b'), 'b')
        self.assertTrue(node.has_xml_attrs())
        newval = 'zz'
        node.set_xml_attr('bb', newval)
        self.assertNotEqual(node.get_xml_attrs(), attrs)
        attrs['bb'] = newval
        self.assertEqual(node.get_xml_attrs(), attrs)
        self.assertEqual(node.get_xml_attr('bb'), newval)
        self.assertTrue(node.has_xml_attrs())
        node.delete_xml_attr('aa')
        self.assertNotEqual(node.get_xml_attrs(), attrs)
        del attrs['aa']
        self.assertEqual(node.get_xml_attrs(), attrs)
        self.assertTrue(node.has_xml_attrs())
        node.delete_xml_attr('bb')
        self.assertNotEqual(node.get_xml_attrs(), attrs)
        del attrs['bb']
        self.assertEqual(node.get_xml_attrs(), attrs)
        self.assertFalse(node.has_xml_attrs())
        newval = 1
        node.set_xml_attr('cc', newval)
        self.assertNotEqual(node.get_xml_attrs(), attrs)
        attrs['cc'] = str(newval)
        self.assertEqual(node.get_xml_attrs(), attrs)
        self.assertTrue(isinstance(node.get_xml_attr('cc'), jxmlease._unicode))
        self.assertTrue(node.get_xml_attr('cc') is not newval)
        self.assertTrue(node.has_xml_attrs())

    def test_output_basic(self):
        self.assertTrue(XMLDictNode({'root': {'a': ['foo', 'bar'], 'b': 'baz', 'c': {'d': 'barbar'}}}).emit_xml(),
                        """<?xml version="1.0" encoding="utf-8"?>
<root>
    <a>foo</a>
    <a>bar</a>
    <b>baz</b>
    <c>
        <d>barbar</d>
    </c>
</root>""")

    def test_output_fulldocument(self):
        root = XMLDictNode({'root': {'a': ['foo', 'bar'], 'b': 'baz'}})

        # Autodetection
        self.assertTrue(root.emit_xml().startswith("<?xml"))
        self.assertTrue(root['root'].emit_xml().startswith("<?xml"))
        self.assertFalse(root['root']['a'].emit_xml().startswith("<?xml"))
        self.assertFalse(root['root']['b'].emit_xml().startswith("<?xml"))
        self.assertFalse(root['root']['a'][0].emit_xml().startswith("<?xml"))
        self.assertFalse(root['root']['a'][1].emit_xml().startswith("<?xml"))

        # Force on
        self.assertTrue(root.emit_xml(full_document=True).startswith("<?xml"))
        self.assertTrue(root['root'].emit_xml(full_document=True).startswith("<?xml"))
        self.assertTrue(root['root']['b'].emit_xml(full_document=True).startswith("<?xml"))
        self.assertRaises(ValueError, root['root']['a'].emit_xml, full_document=True)

        # Force off
        for node in (root, root['root'], root['root']['a'],
                     root['root']['a'][0], root['root']['a'][1],
                     root['root']['b']):
            self.assertFalse(node.emit_xml(full_document=False).startswith("<?xml"))

    def test_output_notpretty_basic(self):
        xml = "<aa><ab><ac>1</ac><ac>2</ac></ab><ab><ac>3</ac><ac>4</ac></ab></aa>"
        self.assertEqual(parse(xml).emit_xml(full_document=False, pretty=False), xml)

    def test_output_notpretty_attr(self):
        ns_attr = 'xmlns:a="http://www.example.com/"'
        other_attr = 'a:b="foo"'
        xml_template = "<aa %s %s><ab><ac>1</ac><ac>2</ac></ab><ab><ac>3</ac><ac>4</ac></ab></aa>"
        xml_in = xml_template % (ns_attr, other_attr)
        xml_out = parse(xml_in).emit_xml(full_document=False, pretty=False)
        if jxmlease._OrderedDict == dict:
            self.assertTrue(xml_out == xml_in or
                            xml_out == xml_template % (other_attr, ns_attr)
            )
        else:
            self.assertEqual(xml_in, xml_out)

    def test_output_notpretty_semistructured(self):
        xml = "<aa><ab><ac>1</ac><ac>2</ac>foo</ab><ab><ac>3</ac><ac>4</ac>bar</ab>baz</aa>"
        self.assertEqual(parse(xml).emit_xml(full_document=False, pretty=False), xml)

    def test_output_noclass(self):
        cases = [
            ({'a': ''}, True, ("<a></a>",)),
            ({'a': 'foo'}, True, ("<a>foo</a>",)),
            ({'a': ['foo', 'bar']}, False, ("<a>foo</a><a>bar</a>",)),
            ({'a': {'b': ['foo', 'bar']}}, True, ("<a><b>foo</b><b>bar</b></a>",)),
            ({'a': {'b': 'foo'}}, True, ("<a><b>foo</b></a>",)),
            ({'a': 'foo', 'b': 'bar'}, False, (
                "<a>foo</a><b>bar</b>", "<b>bar</b><a>foo</a>"
            )),
            ([{'a': 'foo'}, {'a': 'bar'}], False, ("<a>foo</a><a>bar</a>",)),
            ([{'a': 'foo'}], True, ("<a>foo</a>",)),
        ]
        for obj, full_doc, xml in cases:
            if full_doc:
                header = """<?xml version="1.0" encoding="utf-8"?>\n"""
                expected_result = [header + i for i in xml]
            else:
                expected_result = list(xml)
            emit_xml = jxmlease.emit_xml
            self.assertIn(emit_xml(obj, pretty=False), expected_result)
            if full_doc:
                self.assertIn(emit_xml(obj, full_document=True, pretty=False), expected_result)
            else:
                self.assertRaises(ValueError, emit_xml, obj, full_document=True)
            self.assertIn(emit_xml(obj, full_document=False, pretty=False), xml)

            self.assertRaises(TypeError, emit_xml, "test")

    def test_find_with_tag_non_recursive(self):
        xml = "<z><aa><ab><ac>1</ac><ac>2</ac></ab><ab><ac>3</ac></ab></aa><aa><empty/></aa></z>"
        root = parse(xml)

        # We should be able to find "z" and "aa" at both the tagless
        # root node and the real root node.
        for tag in ("z", "aa"):
            self.assertTrue(root.has_node_with_tag(tag, recursive=False))
            self.assertTrue(root.has_node_with_tag(tag, recursive=False))

        # We should not find children of <aa>.
        for tag in ("ab", "ac"):
            self.assertFalse(root.has_node_with_tag(tag, recursive=False))
            self.assertFalse(root.has_node_with_tag(tag, recursive=False))

        # We should be able to find 1 <z> and 2 <aa> nodes from the top level.
        for tag, count in (("z", 1), ("aa", 2)):
            self.assertEqual(len(list(root.find_nodes_with_tag(tag, recursive=False))), count)
            self.assertEqual(len(list(root["z"].find_nodes_with_tag(tag, recursive=False))), count)

        # At the <aa> node level, we should be able to find a total of
        # 2 <aa> nodes and 2 <ab> nodes.
        self.assertEqual(len(list(root["z"]["aa"].find_nodes_with_tag("aa", recursive=False))), 2)
        self.assertEqual(len(list(root["z"]["aa"].find_nodes_with_tag("ab", recursive=False))), 2)
        self.assertEqual(len(list(root["z"]["aa"].find_nodes_with_tag("ac", recursive=False))), 0)
        for node, count in zip(root["z"]["aa"], [2, 0]):
            self.assertEqual(len(list(node.find_nodes_with_tag("aa", recursive=False))), 1)
            self.assertEqual(len(list(node.find_nodes_with_tag("ab", recursive=False))), count)
            self.assertEqual(len(list(node.find_nodes_with_tag("ac", recursive=False))), 0)

        # At the <ab> node level, we should be able to find a total of
        # 2 <ab> nodes and 3 <ac> nodes.
        ab_node = root["z"]["aa"][0]["ab"]
        self.assertEqual(len(list(ab_node.find_nodes_with_tag("aa", recursive=False))), 0)
        self.assertEqual(len(list(ab_node.find_nodes_with_tag("ab", recursive=False))), 2)
        self.assertEqual(len(list(ab_node.find_nodes_with_tag("ac", recursive=False))), 3)
        for node, count in zip(ab_node, [2, 1]):
            self.assertEqual(len(list(node.find_nodes_with_tag("aa", recursive=False))), 0)
            self.assertEqual(len(list(node.find_nodes_with_tag("ab", recursive=False))), 1)
            self.assertEqual(len(list(node.find_nodes_with_tag("ac", recursive=False))), count)

        # At the <ac> node level, we should be able to find a total of
        # 3 <ac> nodes.
        self.assertEqual(len(list(ab_node[0]["ac"].find_nodes_with_tag("ac", recursive=False))), 2)
        for ac_node in (ab_node[0]["ac"][0], ab_node[0]["ac"][1], ab_node[1]["ac"]):
            self.assertEqual(len(list(node.find_nodes_with_tag("ac", recursive=False))), 1)

    def test_find_with_tag_recursive(self):
        xml = "<z><aa><ab><ac>1</ac><ac>2</ac></ab><ab><ac>3</ac></ab></aa><aa><empty/></aa></z>"
        root = parse(xml)

        # We should be able to find all tags at both the tagless
        # root node and the real root node.
        for tag in ("z", "aa", "ab", "ac", "empty"):
            self.assertTrue(root.has_node_with_tag(tag))
            self.assertTrue(root.has_node_with_tag(tag))

        # We should not find non-existent tags.
        for tag in ("not_here", ""):
            self.assertFalse(root.has_node_with_tag(tag))
            self.assertFalse(root.has_node_with_tag(tag))

        # From the top level, we should be able to find 1 <z>, 2 <aa>,
        # 2 <ab>, 3 <ac>, and 1 <empty> node.
        expected_results = [("z", 1), ("aa", 2), ("ab", 2), ("ac", 3), ("empty", 1), ("not_here", 0), ("", 0)]
        for tag, count in expected_results:
            self.assertEqual(len(list(root.find_nodes_with_tag(tag))), count)
            self.assertEqual(len(list(root["z"].find_nodes_with_tag(tag))), count)

        # At the <aa> node level, we should be able to find 2 <aa>, 2
        # <ab>, 3 <ac>, and 1 <empty> node.
        expected_results = expected_results[1:]
        for tag, count in expected_results:
            self.assertEqual(len(list(root["z"]["aa"].find_nodes_with_tag(tag))), count)

        # Replace the "aa" node and drop the "empty" node. Then look in the
        # individual "aa" nodes.
        expected_results = [("aa", 1)] + expected_results[1:3] + expected_results[4:]
        for tag, count in expected_results[1:3] + expected_results[4:]:
            self.assertEqual(len(list(root["z"]["aa"][0].find_nodes_with_tag(tag))), count)
            self.assertEqual(len(list(root["z"]["aa"][1].find_nodes_with_tag(tag))), 0)

        # At the <ab> node level, we should be able to find 2 <ab> and
        # 3 <ac> nodes.
        expected_results = expected_results[1:]
        ab_node = root["z"]["aa"][0]["ab"]
        for tag, count in expected_results:
            self.assertEqual(len(list(ab_node.find_nodes_with_tag(tag))), count)

        self.assertEqual(list(ab_node.find_nodes_with_tag("ac")), ["1", "2", "3"])

        for node, count in zip(ab_node, [2, 1]):
            self.assertEqual(len(list(node.find_nodes_with_tag("aa"))), 0)
            self.assertEqual(len(list(node.find_nodes_with_tag("ab"))), 1)
            self.assertEqual(len(list(node.find_nodes_with_tag("ac"))), count)

        # At the <ac> node level, we should be able to find a total of
        # 3 <ac> nodes.
        self.assertEqual(len(list(ab_node[0]["ac"].find_nodes_with_tag("ac"))), 2)
        for ac_node in (ab_node[0]["ac"][0], ab_node[0]["ac"][1], ab_node[1]["ac"]):
            self.assertEqual(len(list(node.find_nodes_with_tag("ac"))), 1)

    def test_find_with_tag_tuple(self):
        xml = "<z><aa><ab><ac>1</ac><ac>2</ac></ab><ab><ac>3</ac></ab></aa><aa><empty/></aa></z>"
        root = parse(xml)

        # We should be able to find 3 <ac> tags, 2 <ab> tags, and 2 <aa> tags.
        self.assertEqual(len(list(root.find_nodes_with_tag(("ac", "foo")))), 3)
        self.assertEqual(len(list(root.find_nodes_with_tag(("ab", "ac", "foo")))), 5)
        self.assertEqual(len(list(root.find_nodes_with_tag(["aa", "ab", "ac", "foo"]))), 7)
        self.assertEqual(len(list(root.find_nodes_with_tag(tuple()))), 0)
        self.assertEqual(len(list(root.find_nodes_with_tag(("foo", "bar")))), 0)

if __name__ == '__main__':
    unittest.main()
