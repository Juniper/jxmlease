#!/usr/bin/env python
# Copyright (c) 2016, Juniper Networks, Inc.
# All rights reserved.
#
# Copyright (C) 2012 Martin Blech and individual contributors.
#
# See the LICENSE file for further information.

try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

try:
    from distutils.log import warn
except:
    import sys
    def warn(msg, *args):
        sys.stderr.write('warning: ' + (msg % args) + '\n')

import jxmlease

setup(name='jxmlease',
      version=jxmlease.__version__,
      description=jxmlease.__doc__,
      author=jxmlease.__author__,
      author_email='jxmlease@juniper.net',
      url='https://github.com/Juniper/jxmlease',
      license=jxmlease.__license__,
      platforms=['all'],
      classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          # Note: Jython not tested yet!
          # 'Programming Language :: Python :: Implementation :: Jython',
          'Programming Language :: Python :: Implementation :: PyPy',
          'Topic :: Text Processing :: Markup :: XML',
      ],
      py_modules=['jxmlease'],
      test_suite = "tests.test",
      )

try:
    from lxml import etree
except:
    warn("The lxml module is recommended, but not installed.")
