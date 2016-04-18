Producing XML Output
====================

.. py:currentmodule:: jxmlease

You can create XML output using the
:py:meth:`emit_xml <XMLNodeBase.emit_xml>` method of one of the XML
node classes to produce XML output from the node's data.
You can also use the package's :py:func:`emit_xml` function to directly
convert a Python object to XML output.

Producing XML Output from an XML Node Object
--------------------------------------------

You can produce XML output from an :py:class:`XMLDictNode`,
:py:class:`XMLListNode`, or :py:class:`XMLCDATNode` instance. You use
the :py:meth:`emit_xml <XMLNodeBase.emit_xml>` class method to produce
the output.

.. automethod:: XMLNodeBase.emit_xml

.. automethod:: XMLNodeBase.emit_handler

Producing XML Output from a Python Object
-----------------------------------------

You can produce XML output from a normal Python dictionary or list
using the :py:func:`emit_xml` function.

.. autofunction:: emit_xml
