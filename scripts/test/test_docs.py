import doctest
import unittest

import autochecklist.messenger.tk.responsive_textbox as responsive_textbox


def load_tests(
    loader: object, tests: unittest.TestSuite, ignore: object
) -> unittest.TestSuite:
    """Add doctests to the testing suite."""
    tests.addTests(doctest.DocTestSuite(responsive_textbox))
    return tests
