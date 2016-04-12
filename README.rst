jxmlease
========

Welcome to jxmlease: a Python module for converting XML to
intelligent Python data structures, and converting Python data
structures to XML.

What is jxmlease?
-----------------

Do you have a requirement to process XML data, but find it cumbersome
to process XML data in Python? If so, you are not alone.

The main problem with processing XML data in Python is that it doesn't
map well to native Python data structures. XML contains both data and
metadata, while native Python objects (lists, dictionaries, and
strings) only contain data.

But, wait! That's not completely true. Actually, Python objects *do*
have the ability to hold metadata. jxmlease subclasses Python list,
dictionary, and string types to create new, smart XML classes that can
represent the XML data as normal Python objects while also maintaining
the metadata for you to use.

For example, consider this sample XML document::

    <a>
      <b>
        <z changed="true">foo</z>
      </b>
      <c>
        <d>
          <z changed="true">bar</z>
        </d>
      </c>
      <e>
        <z>baz</z>
      </e>
    </a>

Using jxmlease, you can get a standard Python representation of the
*data* in this XML document::

    >>> root = jxmlease.parse(xml)
    >>> root.prettyprint()
    {u'a': {u'b': {u'z': u'foo'},
            u'c': {u'd': {u'z': u'bar'}},
            u'e': {u'z': u'baz'}}}

You can also still access the *metadata*::

    >>> root['a']['b']['z'].get_xml_attr("changed")
    u'true'

jxmlease also provides flexibility for parsing your data. If you only
need select information from your XML data, you can have jxmlease
return it while it is parsing the document::

    >>> for path, _, node in jxmlease.parse(xml, generator="z"):
    ...     changed = node.get_xml_attr("changed", None) is not None
    ...     print("%-8s: %s %s" % (path, node, "(changed)" if changed else ""))
    ...
    /a/b/z  : foo (changed)
    /a/c/d/z: bar (changed)
    /a/e/z  : baz

You can also iterate over the full, parsed document::

    >>> for node in root.find_nodes_with_tag("z"):
    ...     changed = node.get_xml_attr("changed", None) is not None
    ...     print("%s %s" % (node, "(changed)" if changed else ""))
    ...
    foo (changed)
    bar (changed)
    baz

These iterations can even return part of an XML tree::

    >>> for node in root.find_nodes_with_tag(("b", "c")):
    ...     print("<%s>: %s" % (node.tag, node))
    ...
    <b>: {u'z': u'foo'}
    <c>: {u'd': {u'z': u'bar'}}

And, importantly, these objects are subclasses of Python objects, so
things like string comparisons work correctly::

    >>> root['a']['b']['z'] == "foo"
    True
    >>> root['a']['b']['z'] == "bar"
    False

We think that these features, and others, combine to ease XML
processing in Python: hence, the name: jxmlease.

Documentation
-------------

The documentation is hosted on `readthedocs`_.

.. _readthedocs: http://jxmlease.readthedocs.org/

Installation
------------

See the `installation instructions`_.
for more information on installing jxmlease.

.. _installation instructions: http://jxmlease.readthedocs.org/en/stable/install.html
