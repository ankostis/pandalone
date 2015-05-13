#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import os
import sys
import unittest

import pandalone


mydir = os.path.dirname(__file__)
readme_path = os.path.join(mydir, '..', 'README.rst')


@unittest.skipIf(sys.version_info < (3, 4), "Doctests are made for py >= 3.3")
class TestDoctest(unittest.TestCase):

    def test_doctests(self):
        failure_count, test_count = doctest.testfile(
            readme_path, module_relative=False,
            optionflags=doctest.NORMALIZE_WHITESPACE)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEquals(failure_count, 0, (failure_count, test_count))

    def test_version(self):
        ver = pandalone.__version__
        header_len = 20
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            for i, l in enumerate(fd):
                if ver in l:
                    break
                elif i >= header_len:
                    msg = "Version(%s) not found in Readme's %s header-lines!"
                    raise AssertionError(msg % (ver, header_len))