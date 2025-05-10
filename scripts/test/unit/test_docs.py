import doctest
import unittest

import autochecklist.messenger.tk.responsive_textbox as responsive_textbox
import captions.edit
import captions.vttplus as vttplus
import lib.diff


def load_tests(
    loader: object, tests: unittest.TestSuite, ignore: object
) -> unittest.TestSuite:
    """Add doctests to the testing suite."""
    tests.addTests(doctest.DocTestSuite(responsive_textbox))
    tests.addTests(doctest.DocTestSuite(vttplus))
    tests.addTests(doctest.DocTestSuite(captions.edit))
    tests.addTests(doctest.DocTestSuite(lib.diff))
    return tests
